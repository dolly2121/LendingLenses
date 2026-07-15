# CLAUDE.md - session entry point

Project: **LendingLens**, a demo lakehouse built for a live technical conversation with Liberty Financial. Simplicity is a requirement, not a preference.

## Every session, in this order, before any code

1. **Memory.md** for current phase, frozen contracts, and past decisions
2. **PRD.md** for what and why (FR1 to FR8 are the full feature list)
3. **Architecture.md** for structure, stack, and binding data contracts
4. **Rules.md** and obey it strictly, especially R1 (document scale, build simple), R3 (PII), R4 (concurrency)
5. **Phases.md** and work ONLY on the phase named in Memory.md
6. **Design.md** when touching the dashboard, console output, or README

## Hard rules that override everything

- One phase at a time. Never begin the next phase without the human saying so
- A phase is complete only when its Definition of Done passes, including tests
- Update Memory.md at the end of every phase and after any significant decision
- Production concerns are documented in ARCHITECTURE_MAPPING.md, never implemented (Rules R1)
- If anything is ambiguous or seems wrong, STOP and ask. Do not guess
- Less code is better code. Ponytail's ladder applies to every task
