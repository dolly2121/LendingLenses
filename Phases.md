# Phases - build order

**Version 2.0 | One phase at a time. A phase is done only when its Definition of Done passes. Update Memory.md after every phase.**

Each phase is independently buildable and independently testable. No phase depends on a later one.

---

## Phase 1 - Scaffold and synthetic data

**Goal**: a runnable skeleton and deterministic test data with planted defects.

**Build**
- Folder structure from Architecture.md section 5. Makefile targets: `data`, `pipeline`, `dashboard`, `service`, `demo`, `test`
- `generate_data.py` producing `loans_raw.csv` with 500 rows and columns: loan_id, customer_name (synthetic), state, loan_amount, loan_type, application_date, status. No `customer_id` column: nothing downstream uses it, so it is not generated at all (simpler than masking or classifying an unused field)
- Planted defects, each commented in the generator, netting to EXACTLY 6 quarantined rows: 2 rows with null state, 1 row with negative loan_amount, 1 duplicate loan_id pair (both rows fail the uniqueness check = 2 rows), 1 row with a future application_date. 2+1+2+1 = 6. Verify this arithmetic against pandera's actual uniqueness-check behaviour in the Phase 3 spike below before relying on it live
- 3 call transcripts as .txt: a normal enquiry, a clear hardship call, a clear complaint call. These are the ONLY transcripts ever used with the AI service, including live in front of Katherine. See Rules.md R3a
- Use a fixed random seed so every run produces identical data

**Definition of Done**
- `make data` creates the CSV and 3 transcripts
- Running it twice produces byte-identical output
- Defect rows are findable by their commented IDs

## Phase 2 - Bronze layer

**Goal**: land raw data unmodified with ingest metadata, and de-risk the concurrency decision early.

**Build**
- FIRST, a 15 minute spike: write to a Delta table from two separate processes concurrently (simulate the Phase 6 dashboard-reads-while-service-writes scenario). Confirm no lock errors or corruption on your OS. This decision is made now, not discovered under time pressure during Phase 6 rehearsal. If Delta is flaky, switch Gold storage to DuckDB and record the decision in Memory.md immediately
- `lake_io.py` with `append(table_path, dataframe)` as the sole write function
- `bronze.py` landing loans and call metadata into `bronze_loans` and `bronze_calls`, adding `ingest_timestamp` and `source_file`. No cleaning, no masking. Bronze means as landed

**Definition of Done**
- Concurrency spike result recorded in Memory.md, storage engine decided
- Row counts in Bronze match source files exactly
- Re-running Bronze does not duplicate rows (idempotent by source_file)
- `customer_name` is present in Bronze, proving the masking happens later, not here

## Phase 3 - Silver layer (quality and privacy)

**Time budget note**: this phase carries the most demo weight and the most distinct logic (schema validation, quarantine, masking, derivation, audit logging). Budget most of evening 1 for it. If evening 1 runs long, that is expected, do not compress this phase to protect Phase 5 or 7.

**Goal**: the two most important demo assets: the quality gate and the masking step.

**Build**
- FIRST, a 15 minute spike: confirm pandera's range, uniqueness, non-null, and categorical checks behave as expected on polars DataFrames (pandera's polars support is newer and thinner than its pandas support). Confirm the uniqueness check's exact row-flagging behaviour on the duplicate loan_id pair, since Phase 1's defect count depends on it. Record the outcome in Memory.md
- pandera schema for loans: loan_amount between 0 and 5,000,000 exclusive, application_date not in the future, loan_id unique, state within valid AU states, no nulls in key fields
- Failing rows written to `quarantine`. Store ONLY the offending field name, its value, check_name, and reason, never the full raw row. This avoids ever writing a raw synthetic name into a table described as PII-masked (see Architecture.md quarantine contract). Passing rows continue
- Masking: `customer_name` becomes `customer_ref_hash` (SHA-256, fixed salt). Raw name column is dropped from Silver
- Derivation: `risk_band` (LOW, MEDIUM, HIGH) from loan_amount and loan_type thresholds, documented in the function docstring
- One `dq_audit` row per check per run
- Light call checks: file exists, transcript non-empty
- Console output per Design.md: one aligned line per stage with counts

**Definition of Done**
- `make pipeline` quarantines exactly the planted defects, nothing else
- `tests/test_silver_quality.py` covers 3 or more checks, green
- `tests/test_masking.py` proves: same name gives same hash, no raw name survives into Silver
- **Demo moment 1 and 2 rehearsable from console plus a table peek**

## Phase 4 - Gold layer

**Goal**: business-ready tables, contracts frozen.

**Build**
- `gold_loan_summary` aggregated by state and risk_band
- `gold_call_insights` initialised empty with the agreed schema
- A pandera check on both Gold schemas asserting no direct identifier columns exist

**Definition of Done**
- Summary numbers reconcile with Silver counts
- Running the full pipeline twice yields identical Gold row counts
- Contracts recorded as frozen in Memory.md

## Phase 5 - Consumer 1: dashboard

**Goal**: the BI face of the Gold layer.

**Build**
- Streamlit app per Design.md: metric tiles, loan charts from `gold_loan_summary`, call insights table from `gold_call_insights`, collapsible quality panel from `dq_audit`
- A manual "Refresh" button, not a timer. Reads only Gold and audit tables. Read retry per Rules R4. This is deliberate: a presenter-controlled click on cue is more reliable live than hoping a 5 second auto-refresh lines up with narration (see demo moment 3 in Phase 6)

**Definition of Done**
- `make dashboard` renders all four sections from a fresh pipeline run
- Killing and restarting the dashboard mid-demo recovers cleanly

## Phase 6 - Consumer 2: AI service

**Goal**: the AI face of the Gold layer, and demo moment 3.

**Build**
- FastAPI app: `POST /process-call` accepting a .txt transcript. Flow: read transcript, VADER sentiment, hardship and complaint flags from keyword rules in `nlp_flags.py`, mask any name tokens found in the transcript, append one row to `gold_call_insights` via `lake_io`
- `GET /health`
- Errors return clean status codes with short messages

**Definition of Done**
- `tests/test_nlp_flags.py`: hardship transcript flags hardship, complaint flags complaint, normal flags neither. Also asserts masking removes any name tokens from the 3 official transcripts (not general NER, see Rules.md R3a)
- Posting the hardship call while the dashboard is open, then clicking Refresh, shows the flagged row
- The R4 rehearsal gate passes: 5 consecutive posts with the dashboard open, clicking Refresh after each, zero errors
- ONLY the 3 transcripts from Phase 1 are ever used with this service, including live. Never a name typed live or suggested by the audience (Rules.md R3a)

## Phase 7 - Packaging and the production story

**Goal**: a packaging artifact that proves production readiness, WITHOUT it being part of the live demo path. The live demo runs via local `make demo`, never `docker compose up`, on stage. Docker exists to be shown in the repo, not to be run in front of Katherine, it adds container and volume-locking risk for zero audience-visible payoff.

**Build**
- `make demo` target that sequences startup with readiness checks: run pipeline, confirm Gold tables exist, start dashboard, start AI service, poll `GET /health` until 200, then print "ready". No race conditions on stage
- Dockerfiles for the service and dashboard, `docker-compose.yml` with a shared volume for `data/lake`. Test that `docker compose up` works at least once, but this is a packaging proof point, not the rehearsed path
- `terraform/main.tf`: one small, briefly commented azurerm resource block (illustrative only, clearly marked as not applied). Keep this minimal, a single paragraph in ARCHITECTURE_MAPPING.md does most of the same credibility work
- `ARCHITECTURE_MAPPING.md`: one short section per row of the mapping table, each ending with its scale, security, or governance note from Architecture.md section 6. Include one sentence on why the demo uses a fixed salt for masking versus keyed HMAC in production, so the presenter is armed if asked
- `README.md`: 3 step quickstart (`make demo` is the real path) plus a Demo Script section listing the exact click path and the three demo moments
- **Time-overrun fallback, written down now so it is not improvised under pressure**: if evening 3 runs short, drop in this order: Terraform polish first, then Docker/compose, then ARCHITECTURE_MAPPING.md polish. `make demo` running locally is the non-negotiable deliverable, everything else in this phase is secondary

**Definition of Done**
- `make demo` runs the full live path locally with correct startup ordering
- `docker compose up` works from a fresh clone at least once (not required live)
- `make test` green
- A stranger could run the demo from README alone

## Phase 8 - Optional polish (only if rehearsed and stable)

In priority order, each independently skippable:
1. Run summary table at the end of `run_pipeline.py`, surfaced in the dashboard quality panel
2. Optional audio: faster-whisper behind the existing endpoint. The .txt path must remain unchanged. Ships only if it survives two full rehearsals
3. Rebuild the dashboard's loan summary view in Power BI Desktop (free, local), pointing at the same `gold_loan_summary` Delta table via the Delta connector. Streamlit stays as the primary rehearsed demo; Power BI is a bonus if time allows, strengthens the "this maps to Power BI" claim into "this is Power BI."

**Definition of Done**: item by item, demo remains stable after each addition.
