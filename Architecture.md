# Architecture - LendingLens

**Version 2.0 | Companion to PRD.md | Contracts in section 4 are binding**

---

## 1. System overview

```
        SOURCES                      LAKEHOUSE (local Delta)                CONSUMERS
┌─────────────────────┐   ┌───────────────────────────────────┐   ┌──────────────────────┐
│ loans_raw.csv       │──▶│ BRONZE   raw, immutable, as landed│   │ Streamlit dashboard  │
│ call transcripts    │──▶│  bronze_loans   bronze_calls      │   │ (= Power BI)         │
└─────────────────────┘   │        │                          │   │  reads Gold + audit  │
                          │        ▼ validate · mask · derive │   └──────────▲───────────┘
                          │ SILVER  trusted, PII-masked       │              │
                          │  silver_loans   silver_calls      │              │ read only
                          │  quarantine     dq_audit          │              │
                          │        │                          │   ┌──────────┴───────────┐
                          │        ▼ aggregate · publish      │   │ FastAPI AI service   │
                          │ GOLD    business ready, no PII    │◀──│ NLP flags + sentiment│
                          │  gold_loan_summary                │   │ (= Python svc on AKS)│
                          │  gold_call_insights               │   │ writes via lake_io   │
                          └───────────────────────────────────┘   └──────────────────────┘
```

The architectural claim being demonstrated: **one governed Gold layer is the contract between BI and AI.** Everything else exists to make that claim credible.

## 2. Component responsibilities

| Component | Responsibility | Production equivalent |
|---|---|---|
| `pipeline/` scripts | Batch ETL, Bronze to Silver to Gold | Fabric pipelines and Spark notebooks |
| `pipeline/lake_io.py` | The only module that writes to the lake. Atomic appends | OneLake write patterns, table ACLs |
| pandera schemas | Declared, versioned quality rules | DQ framework in Fabric |
| Masking step in Silver | Hash direct identifiers before curated zones | Purview classification plus masking policy |
| `dq_audit` table | Per-run, per-check results | Lineage and observability tooling |
| Streamlit app | Read-only BI consumer | Power BI on a semantic model |
| FastAPI service | AI consumer and producer of call insights | Containerised Python service on AKS |
| docker compose | Local runtime wiring | AKS plus CI/CD templates |
| `terraform/` | Illustrative IaC sample | Terraform with Liberty CI/CD templates |

## 3. Technology stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | JD requirement |
| Storage | Delta Lake via `deltalake` package | Same open format Fabric OneLake uses, no Spark needed locally |
| Processing | polars | Fast, modern, clean API |
| Data quality | pandera | Declarative schemas, readable on screen |
| AI service | FastAPI plus VADER sentiment plus keyword rules | Explainable beats clever in a risk context |
| Speech to text | faster-whisper, **optional, Phase 8 only** | Heavy dependency, must never block the core demo |
| Dashboard | Streamlit | Fast to build, stands in for Power BI |
| Orchestration | Plain `run_pipeline.py` plus Makefile | Airflow class tools are overkill at this size |
| Fallback | DuckDB for Gold if Delta concurrency misbehaves | Decision logged in Memory.md if taken |

## 4. Data contracts (binding after Phase 4)

PII class: **D** = direct identifier, **I** = indirect, **N** = none.

**silver_loans**: loan_id (I), customer_ref_hash (D, masked), state (I), loan_amount (N), loan_type (N), risk_band (N, derived), application_date (I), status (N). No `customer_id`: nothing downstream needs it, so it is never generated (see Phases.md Phase 1)

**quarantine**: source_table, source_row_id, offending_field, offending_value, check_name, reason, run_id, quarantined_at. Deliberately does NOT store the full raw row or a `record_json` blob: doing so would risk writing an unmasked synthetic name into a table this architecture calls trusted and PII-masked. Only the specific field that failed is stored

**dq_audit**: run_id, table, check_name, passed_count, failed_count, run_timestamp

**gold_loan_summary**: state, risk_band, loan_count, total_amount, avg_amount, last_updated. *No identifiers of any class.*

**gold_call_insights**: call_id (I), transcript_masked, sentiment_score, hardship_flag, complaint_flag, processed_at

Raw Bronze retains original values including synthetic names. Silver applies masking. Gold is aggregate or flag level only. This three zone privacy posture is itself a demo talking point.

## 5. Folder structure

```
lendinglens/
├── CLAUDE.md  PRD.md  Architecture.md  Rules.md  Phases.md  Design.md  Memory.md
├── README.md  ARCHITECTURE_MAPPING.md  Makefile  docker-compose.yml
├── data/
│   ├── landing/            # raw inputs land here
│   └── lake/               # bronze/ silver/ gold/ delta tables
├── pipeline/
│   ├── generate_data.py    # synthetic data with planted defects
│   ├── lake_io.py          # sole lake writer, atomic appends
│   ├── bronze.py  silver.py  gold.py  run_pipeline.py
├── ai_service/
│   ├── main.py  nlp_flags.py  Dockerfile
├── dashboard/
│   ├── app.py  Dockerfile
├── terraform/main.tf
└── tests/
    ├── test_silver_quality.py  test_masking.py  test_nlp_flags.py
```

## 6. Production evolution (documented, not built)

This section is the honest answer to "how does this scale," expanded per row in `ARCHITECTURE_MAPPING.md`.

**Scale to millions of rows.** Partition Delta tables by `application_date`. Replace full reloads with incremental watermark loads at Bronze. Move transforms to Fabric Spark, sized by capacity units. Gold aggregates become incremental merges. The Medallion pattern and the contracts do not change, only the compute underneath them.

**Security.** Identity via Entra ID. Fabric workspace RBAC separating engineering, analytics, and service principals. Encryption at rest and in transit is platform default. Secrets in Azure Key Vault. The AI service gets a managed identity on AKS with least privilege access to only the Gold tables it needs.

**Privacy and governance.** Columns classified in Microsoft Purview using the same PII classes as section 4. Masking enforced at Silver as policy, not convention. Lineage captured from pipeline runs, discoverability through the Purview catalog, and a semantic model over Gold so Power BI consumers never touch lower zones. Retention rules applied per Australian Privacy Principles.

**On the demo's fixed salt.** The demo hashes names with a fixed salt so results are deterministic and reproducible across runs (a stated demo requirement). This is a deliberate simplification: a fixed salt over a small, known name pool is reversible by dictionary attack, so it would never be acceptable in production. Production uses keyed HMAC with the key held in Azure Key Vault, rotated per policy, never an application-level constant.
