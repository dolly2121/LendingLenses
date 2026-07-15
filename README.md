# LendingLens

A working demonstration of a modern lakehouse pattern for a non-bank lender: one governed Gold layer serving two consumers at once, a BI dashboard and a Python AI service. Bronze -> Silver -> Gold, built entirely with local, open-source tooling that maps one to one to Microsoft Fabric, Power BI, and AKS. See [PRD.md](PRD.md) and [Architecture.md](Architecture.md) for the full story, and [ARCHITECTURE_MAPPING.md](ARCHITECTURE_MAPPING.md) for the path to production.

## Quickstart

1. `git clone` this repo and `cd` into it
2. `make demo`
3. Open [http://localhost:8501](http://localhost:8501) for the dashboard (the AI service is at [http://localhost:8000](http://localhost:8000))

`make demo` installs dependencies, runs the full pipeline, starts the dashboard and the AI service, and waits for both to be ready before printing `DEMO ready`.

## Demo Script

Three moments, in order, once `make demo` is showing `DEMO ready` and the dashboard is open in a browser:

**1. Quality gate.** Point at the console output from `make demo`: `SILVER loans: 494 passed  6 quarantined -> dq_audit`. Expand the dashboard's **Data Quality** panel to show the 6 quarantined rows and their reasons, per check.

**2. PII masking.** Show a row of `data/landing/loans_raw.csv` with a raw `customer_name`. Show the same record in `silver_loans` (via a Python/Delta read, or `pipeline/silver.py`'s `mask_name`) carrying only `customer_ref_hash`. Point out `gold_loan_summary` on the dashboard carries no identifier of any kind - it is a pure aggregate.

**3. Dual consumer.** Post the hardship call transcript to the AI service:
   ```
   curl -X POST http://localhost:8000/process-call -F "file=@data/landing/transcripts/hardship_call.txt"
   ```
   Click **Refresh** on the dashboard. The new row appears in **Call Insights** with a red **Hardship** badge - written by the AI service, read by the dashboard, same `gold_call_insights` table.

Only the 3 official transcripts in `data/landing/transcripts/` are ever posted to the AI service, including live. If asked for an arbitrary or audience-suggested transcript, the answer is to decline and show the code path instead - the transcript masking is keyword-based, not general NER, and is only proven to work against these 3 (see Rules.md R3a).

## Other commands

| Command | What it does |
|---|---|
| `make data` | Regenerate the synthetic loans CSV and call transcripts |
| `make pipeline` | Run Bronze -> Silver -> Gold once |
| `make dashboard` | Run only the Streamlit dashboard |
| `make service` | Run only the AI service |
| `make test` | Run the test suite |

## Packaging (not the live demo path)

`docker compose up` builds and runs the pipeline, dashboard, and AI service as containers sharing a `data/lake` volume - a packaging proof point only. The live demo always runs via `make demo` on the presenter's own machine; Docker adds container and volume-locking risk for zero audience-visible payoff (see Phases.md Phase 7).
