# LendingLens — Handover (HOTO) Kit

Purpose of this document: give any AI assistant or developer full context on this project in one read, so the owner (Doll) never has to re-explain it.

---

## 1. HIGH LEVEL — what this is

**LendingLens** is a working demo of a lender's data platform, built to demonstrate skills for a Data Engineer role at Liberty Financial (Australian non-bank lender). It implements the exact architecture in their JD: a **Medallion lakehouse (Bronze → Silver → Gold)** where one trusted Gold layer feeds **two consumers at once**: BI dashboards (Power BI + Streamlit) and an AI service (speech-to-text + NLP call flagging).

Everything runs locally on a Windows laptop. Delta Lake files on disk are the "database" — this is a deliberate choice: Delta is the exact open format that Microsoft Fabric's OneLake uses natively, so this local setup is a faithful, working stand-in for Fabric, not a simplification that loses the point. The AI service is built as a containerised FastAPI app, the same shape a service on AKS would take; it was never deployed to AKS because doing so requires a paid Azure environment and real infrastructure setup that a local demo does not need in order to prove the pattern. The full mapping from this local build to Fabric + AKS in production is written out in ARCHITECTURE_MAPPING.md.

**Repo:** github.com/dolly2121/LendingLenses (public)
**Owner:** Doll. Built with Claude Code + Ponytail plugin, phase by phase, with planning docs driving everything.

**The three scripted demo moments:**
1. Quality gate — pipeline runs, exactly 6 planted bad records are quarantined with reasons
2. PII masking — a customer name visible in Bronze becomes a hash in Silver, absent in Gold
3. Dual consumer — a hardship call posted to the AI service appears on the dashboard after one manual Refresh click, from the same Gold table

---

## 2. MID LEVEL — how it is organised

### The planning docs are law
Seven markdown files at repo root drive all work. Any AI touching this project must read them first, in this order:
1. **CLAUDE.md** — session entry point, hard rules
2. **Memory.md** — current status, full decision log (single source of truth for history)
3. **PRD.md** — features FR1–FR8, nothing outside them gets built
4. **Architecture.md** — binding data contracts, stack, folder layout
5. **Rules.md** — R0–R8 boundaries (see key rules below)
6. **Phases.md** — 8 phases, each with a Definition of Done. All complete.
7. **Design.md** — dashboard/console visual standards

### Key rules that must never be broken
- **R0/R1:** This is a demo. Simpler always wins. Production concerns (scale, security, streaming) are DOCUMENTED in ARCHITECTURE_MAPPING.md, never implemented.
- **R3:** All data is synthetic. Raw names may exist ONLY in Bronze. Silver hashes names (SHA-256, fixed demo salt). Gold carries no identifiers, enforced by a pandera schema check.
- **R3a:** The masking is keyword-based against a fixed synthetic name list, NOT real NER. The AI service demo only ever uses the 3 official transcripts or reviewed mic recordings. A human reviews every mic transcript before sending.
- **R4:** All lake writes go through ONE module (`pipeline/lake_io.py`). Dashboard is read-only with retry.
- **R7:** Gold contracts froze at end of Phase 4. `gold_call_insights` later gained `enquiry_type` via an explicit, coordinated change (both writers updated in lockstep). New Gold tables are allowed; changing existing ones needs explicit owner approval.

### Data flow (two parallel paths, same pattern)

**Batch path (loans + 3 official call transcripts):**
```
loans_raw.csv / transcripts → bronze_loans, bronze_calls
                            → silver_loans (+ quarantine, dq_audit)
                            → gold_loan_summary, gold_loan_ops,
                              gold_channel_by_state, gold_call_insights (init)
```
Run with: `make pipeline` (or `make demo` for full startup with services).

**Live voice path (browser mic):**
```
record.html (whisper.js transcribes in-browser, human reviews)
  → POST /process-call
  → bronze_calls_live (raw)
  → silver_calls_live (masked + sentiment + flags + enquiry_type)
  → gold_call_insights (append)
```

---

## 3. LOW LEVEL — components and tables

### Components
| File | What it is | Purpose |
|---|---|---|
| `pipeline/generate_data.py` | script | 500 synthetic loan rows (seed 42, byte-identical reruns) + 3 transcripts. 6 defects planted deliberately: 2 null states, 1 negative amount, 1 duplicate loan_id pair (=2 rows), 1 future date |
| `pipeline/lake_io.py` | library | sole lake writer. Uses `to_arrow(compat_level=oldest)` + `write_deltalake` so Parquet stays readable by older readers incl. Power BI (this fixed a real bug) |
| `pipeline/bronze.py` | batch job | land raw, add ingest_timestamp + source_file, idempotent by source_file |
| `pipeline/silver.py` | batch job | 10 pandera checks, quarantine failures (offending field only, never full row), mask names, derive risk_band, log dq_audit |
| `pipeline/gold.py` | batch job | build all Gold tables, strict pandera self-check (crashes loudly if an identifier column appears) |
| `pipeline/run_pipeline.py` | orchestrator | Bronze → Silver → Gold in order, prints per-stage counts, writes run_summary |
| `ai_service/main.py` | FastAPI service | POST /process-call, GET /health, serves record.html. The "AKS service" of the demo |
| `ai_service/call_pipeline.py` | library | live Bronze → Silver → Gold for calls |
| `ai_service/nlp_flags.py` | library | VADER sentiment, keyword hardship/complaint flags, enquiry_type classifier (priority: complaint > hardship > emi_query > account_update > general_enquiry > other), keyword name masking |
| `ai_service/record.html` | browser page | mic capture (manual Start/Stop, 120s safety cap), whisper.js transcription (Xenova/whisper-tiny.en with chunk_length_s=30, stride 5, return_timestamps=true — required, or audio past 30s is SILENTLY truncated), closing-phrase detection ("bye bye" etc.), human review box, Send |
| `dashboard/app.py` | Streamlit app | reads Gold + dq_audit only. Manual Refresh button (deliberate, presenter-controlled) |
| `tests/` | pytest | 14 tests: silver quality, masking, nlp flags. `make test` |
| `Makefile` | targets | data, pipeline, dashboard, service, demo (full sequenced startup with health poll), test |
| Docker files + `terraform/main.tf` | packaging artifacts | Dockerfiles and docker-compose.yml are written and built successfully at least once, but not verified end-to-end as the live demo path (Docker Desktop is unstable on this machine, so this was deliberately kept OUT of the rehearsed demo per Rules R0/R1: simpler and more reliable wins). Terraform is a small, commented, illustrative Azure resource sample — written to show IaC literacy, never applied, by design, since this is a local demo not a cloud deployment |

### Delta tables
**Bronze:** `bronze_loans`, `bronze_calls` (batch, 3 official transcripts only), `bronze_calls_live` (mic recordings, raw)
**Silver:** `silver_loans`, `silver_calls_live`, `quarantine`, `dq_audit`, `run_summary`
**Gold:** `gold_loan_summary` (state×risk_band → Risk team), `gold_loan_ops` (channel×loan_type → Marketing+Ops), `gold_channel_by_state` (state×channel → regional marketing), `gold_call_insights` (row per call → Compliance)

### silver_loans columns
loan_id, customer_ref_hash, state, loan_amount, loan_type, interest_rate, channel, risk_band (derived), application_date, status, loan_issue_date, first_reimbursement_date

### Environment facts (Windows machine quirks)
- `make` installed via choco (needed admin shell)
- faster-whisper (a Python speech-to-text library) was tried first and caused a native-library crash specific to this machine's environment, unrelated to the code. Rather than lose the speech-to-text feature, it was replaced with whisper.js, the same underlying Whisper AI model running in-browser via WebAssembly instead. This is a resolved engineering decision, not an outstanding gap — do not re-attempt faster-whisper, whisper.js is the working, verified solution
- Port 8000 sometimes gets stuck at OS level (phantom PID); use 8001 or reboot
- Docker Desktop crashes intermittently; never make it demo-critical
- Power BI Desktop's Delta/Folder connector works ONLY because lake_io writes oldest-compat Arrow metadata; do not "simplify" that code away

---

## 4. STATUS + HOW TO CONTINUE

- All 8 phases complete. 14/14 tests green. Repo pushed.
- Power BI Desktop file (LendingLens.pbix, in repo folder locally) connects live to Gold tables; new tables need a new Folder connection, existing ones just need Refresh.
- A 9-slide presentation exists (LendingLens_Demo.pptx) with speaker notes.

**To work on this project as an AI assistant:**
1. Read CLAUDE.md then Memory.md FIRST, every session.
2. One change at a time. Verify against tests. Update Memory.md after every significant decision.
3. Never violate R3/R3a (PII), never write to the lake outside lake_io, never break the frozen Gold contracts without explicit owner approval.
4. Owner communication style: one step at a time, minimal words, plain English, no double hyphens, no semicolons.

**Deliberate scope decisions, each with a stated reason (not oversights):**
- **Quarantine has no automated retry/alerting workflow.** Today it is manual review with full, logged reasons per failed record — this proves the quality-gate concept correctly. Automated retry and alerting are natural next steps for a production system, not something a local demo needs to fake.
- **Name masking is keyword-based, not full NER.** This was a conscious choice for a demo: explainable, testable, and fast to build, versus a heavier ML model with new dependencies and new failure modes. The gap is compensated for correctly: a human reviews every live call transcript before it is sent, specifically because the current tool's limit is known. Real NER is the named next step.
- **Azure, AKS, and Fabric are not deployed.** They require a paid cloud environment and infrastructure setup that adds no value to proving the architecture pattern locally. The local build already uses Fabric's native Delta format and a container-shaped AI service, so the design is proven; only the cloud hosting itself remains as a next step, and it is mapped out in ARCHITECTURE_MAPPING.md.
- **docker compose is built and has run successfully, but was not made part of the rehearsed live demo**, because Docker Desktop is unstable on this specific machine. This is a considered reliability decision (Rules R0/R1: simpler and more reliable wins for a live demo), not a sign the packaging doesn't work.
