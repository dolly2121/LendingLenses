# Memory - living progress log

**Instructions for the AI: read this file FIRST every session, before the codebase. Update it at the end of every phase and after any significant decision. Newest entries at the top. Keep entries to one or two lines.**

---

## Current status

- Current phase: 0 (not started)
- Last completed phase: none
- Gold contracts frozen: no (freezes at end of Phase 4)
- Blockers: none

## Decisions log

Format: date, decision, reason.

- 2026-07-15: Plan v2 adopted. Masking added to Silver. Whisper deferred to optional Phase 8. Production concerns documented in ARCHITECTURE_MAPPING.md, not built (Rules R1).
- 2026-07-15: Adversarial review run against PRD/Architecture/Rules/Phases. Fixed 7 real issues: quarantine no longer stores full raw row (PII leak risk), planted defects rebalanced to net exactly 6 quarantined rows, customer_id column dropped entirely (unused), PRD "aggregates only" claim corrected for row-level gold_call_insights, added R3a restricting the AI service demo to the 3 official transcripts only, Docker moved out of the live demo critical path (packaging artifact only), dashboard auto-refresh replaced with a manual Refresh button for presenter control. Also added: Delta-vs-DuckDB concurrency spike moved to Phase 2, pandera-on-polars behaviour spike added to Phase 3, time-overrun fallback order added to Phase 7, fixed-salt-vs-production-HMAC talking point added to Architecture.md.

## Parking lot (good ideas, out of scope)

One line each. Nothing here gets built without the human asking.

- (empty)

## Environment notes

Record Python version, OS, and anything a fresh session must know to reproduce the setup.

- (empty)
