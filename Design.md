# Design - visual and output standards

**Version 2.0 | Applies to the dashboard, console output, and README**

---

## 1. Principle

The dashboard stands in for Power BI in front of a Head of Data and AI at a lender. Calm, corporate, finance grade. Clean and boring beats flashy. Nothing animates, nothing surprises.

## 2. Palette

| Role | Colour | Hex |
|---|---|---|
| Primary (headers, sidebar) | Deep navy | #1B2A4A |
| Positive (passed checks, healthy metrics) | Teal | #2A9D8F |
| Warning (quarantine counts) | Amber | #E9A03B |
| Alert (hardship, complaint, failed checks) | Muted red | #C1494B |
| Background | Off white | #F7F8FA |
| Text | Charcoal | #2B2D31 |

Do NOT use Liberty's brand colours or logo. Uninvited branding reads as presumptuous. Neutral finance palette only.

## 3. Typography

Streamlit defaults are acceptable. If customising: Inter or system sans for UI, monospace for IDs, hashes, and table values. Headline metrics as large number tiles.

## 4. Dashboard layout

- Title: **LendingLens - One Curated Layer, Two Consumers**
- Row 1: four metric tiles: total loans, total amount, calls processed, checks passed
- Row 2: bar chart of loans by state, donut of loans by risk band
- Row 3: call insights table. Hardship and complaint shown as coloured badges, not True/False text. Transcript column truncated with expand
- Row 4 (collapsible): data quality panel from dq_audit with green ticks and amber counts, plus quarantine total
- A manual **Refresh** button, not a timer. Presenter clicks it on cue during demo moment 3, giving full control over demo timing (see Rules.md R4 and Phases.md Phase 5)
- Masked identifiers display as shortened hashes, e.g. `a3f9…c21b`, reinforcing the privacy story visually

## 5. Console output (visible during the demo)

- One aligned line per stage, plain ASCII, no emoji:

```
BRONZE  loans:  500 landed          calls: 3 landed
SILVER  loans:  494 passed          6 quarantined -> dq_audit
MASK    names:  494 hashed          0 raw names downstream
GOLD    summary: 24 rows            call_insights: ready
```

Note: 500 minus 6 quarantined equals 494 passed. The 6 must match exactly what Phase 1's planted defects produce (see Phases.md Phase 1 for the arithmetic). Verify this number after the Phase 3 pandera spike, before rehearsing the console output verbatim.

## 6. Charts

Two chart types maximum: bar and donut. Every axis and segment labelled. No 3D, no animation, no gradients.
