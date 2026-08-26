# Build 010 — Current Capital Cost Control

Baseline: Build 009 (`32a868372b45828f35bca83dc8ba3f9ac1ff56cc`).

Build 010 adds a current capital-planning and approved-budget-adjustment layer while preserving the existing 2,650-row historical ArcGIS capital archive as a separate evidence source.

## Verified source contract

The production collector entry point is `scripts/ingest_current_capital_v5.py`, publishing parser provenance `build010-current-capital-v5`.

Validated checked-in artifact: `data/generated/current_capital.json`.

- 219 current project sheets from the final 2025/26 HRM Capital Plan.
- 212 project sheets from the final 2024/25 HRM Capital Plan.
- 176 plan-over-plan comparisons using the exact authoritative `Capital Project #` in both plans.
- 14 Council-approved 2025/26 capital-budget adjustment rows from the May 27, 2025 staff report.
- 4 new external cost-sharing award rows totaling +$1.785M.
- 8 capital-budget transfer rows that net to $0.
- 2 explicit capital-budget increases totaling +$9.5M.
- Council minutes verify item 15.2.1 was approved on May 27, 2025 and record `MOTION PUT AND PASSED UNANIMOUSLY`.

## Project identity rules

The current project identity comes only from the explicit `Capital Project #` field. HRM uses both conventional identifiers such as `CT000007` and shorter/alphanumeric identifiers such as `BT36` and `Transit3`.

`Previous #` is retained as evidence but is never promoted to current identity. This rule prevents Corporate Cashiering (`BT36`, previous `CI200002`) from colliding with Finance & HR Business Foundations, whose current code is legitimately `CI200002`.

Continuation pages may be merged only when the current project code and project name match exactly. Conflicting non-null financial or timing fields fail closed.

## Adjustment rules

Only rows from extracted tables containing exactly one of these report headings are eligible:

- New External Cost Sharing Awards
- Capital Budget Transfers
- Capital Budget Increases

Every accepted row must independently reconcile:

`approved budget before + adjustment amount = approved budget after`

The following attachment's multi-year project schedule is excluded from adjustment classification even when its rows contain project codes and monetary values.

## Analytical surface

Build 010 adds a current-capital control section above the historical project archive with:

- current 2025/26 project explorer;
- approved-budget adjustment separation;
- exact-code final-plan estimated-project-cost movement;
- schedule endpoint movement;
- Capital-domain investigation leads integrated into the existing cross-domain Investigations queue.

Two Council-approved budget increases are elevated as explicit Capital review leads. Larger plan-estimate changes are also ranked for review using exact-code comparisons.

## Interpretation boundary

Build 010 does **not** contain or infer:

- transaction-level capital payments;
- invoices;
- commitments or encumbrances;
- project spend-to-date;
- final project costs;
- contract amendment totals unless separately published as such;
- a finding that a project is over budget or improperly managed.

A higher total estimated project cost in the 2025/26 plan than in the 2024/25 plan is described as a **plan estimate movement**, not an overrun. A Council-approved budget increase is an approved budget fact, not evidence the added amount has been spent.

Only 76 of the 176 exact-code comparisons currently expose usable total-estimated-project-cost values in both plan years. Missing values are not imputed. Published timing is an estimated planning/execution/operational endpoint, not authoritative completion status.
