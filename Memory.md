# Memory - living progress log

**Instructions for the AI: read this file FIRST every session, before the codebase. Update it at the end of every phase and after any significant decision. Newest entries at the top. Keep entries to one or two lines.**

---

## Current status

- Current phase: 1 (complete, awaiting go-ahead for Phase 2)
- Last completed phase: 1
- Gold contracts frozen: no (freezes at end of Phase 4)
- Blockers: `make` is not installed on the dev/demo machine and `choco install make -y` fails here (needs an elevated shell this session doesn't have). `pipeline/generate_data.py` was verified directly with `python` and meets Phase 1's DoD, but the literal `make data` / PRD N1 "one command" path is unverified. Resolve before Phase 7 (README quickstart, `make demo`) — either install make in an elevated shell or reconsider the orchestration choice.

## Decisions log

Format: date, decision, reason.

- 2026-07-15: Added `interest_rate` (5.5-14%, base rate per `loan_type` plus jitter, standing in for a risk_band that doesn't exist yet at Bronze) and `channel` (direct/broker, 50/50) to `loans_raw.csv` and to Architecture.md's `silver_loans` contract (both class N, no PII). `risk_band` derivation in Silver is unchanged: still loan_amount/loan_type only, per Phases.md Phase 3 (interest_rate was not wired in as a derivation input). The 6 planted defects are untouched (still LOAN-0050/0150/0200/0100-dup/0400) and reruns remain byte-identical.
- 2026-07-15: Phase 1 complete. `pipeline/generate_data.py` (stdlib only: csv, random, datetime) writes `data/landing/loans_raw.csv` (500 rows, seed 42) and 3 transcripts to `data/landing/transcripts/`. Used a fixed `TODAY` anchor (2026-07-15) instead of `datetime.now()` so output stays byte-identical regardless of the real run date. Verified: 6 planted defects land exactly as spec'd (LOAN-0050/0150 null state, LOAN-0200 negative amount, LOAN-0300 rewritten to duplicate LOAN-0100, LOAN-0400 future-dated), two consecutive runs diff clean. Makefile added with all 6 Phase 1 targets (`data` runs now; `pipeline`/`dashboard`/`service`/`demo`/`test` are stubs pointing at scripts later phases will create).
- 2026-07-15: Plan v2 adopted. Masking added to Silver. Whisper deferred to optional Phase 8. Production concerns documented in ARCHITECTURE_MAPPING.md, not built (Rules R1).
- 2026-07-15: Adversarial review run against PRD/Architecture/Rules/Phases. Fixed 7 real issues: quarantine no longer stores full raw row (PII leak risk), planted defects rebalanced to net exactly 6 quarantined rows, customer_id column dropped entirely (unused), PRD "aggregates only" claim corrected for row-level gold_call_insights, added R3a restricting the AI service demo to the 3 official transcripts only, Docker moved out of the live demo critical path (packaging artifact only), dashboard auto-refresh replaced with a manual Refresh button for presenter control. Also added: Delta-vs-DuckDB concurrency spike moved to Phase 2, pandera-on-polars behaviour spike added to Phase 3, time-overrun fallback order added to Phase 7, fixed-salt-vs-production-HMAC talking point added to Architecture.md.

## Parking lot (good ideas, out of scope)

One line each. Nothing here gets built without the human asking.

- (empty)

## Environment notes

Record Python version, OS, and anything a fresh session must know to reproduce the setup.

- Python 3.11.3, Windows 11. Repo uses `make` (GNU Make must be on PATH) plus plain `python`/`pip`, no venv tooling mandated yet.
