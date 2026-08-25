# Build 005 multi-domain contract

Build 005 integrates the wider HalifaxData ingestion workstream without replacing the Build 004 current-budget contract or the verified light dashboard baseline.

## Dataset boundaries

- `procurement.json` — official public-tender award records. These are **not** an accounts-payable ledger and do not guarantee complete alternative-procurement or amendment coverage.
- `capital.json` — official historical/planned-project evidence, including the HRM historical ArcGIS layer and registered capital-plan history. It is **not** the current HRM capital universe.
- `spending.json` — official quarterly financial-report summary-table rows. `metadata.is_transaction_ledger` must remain `false`; rows are **not** vendor transactions.
- `budget_history.json` — historical budget-table extraction. It is deliberately separate from Build 004 `budget.json`; proposed/pre-COVID/final source status must remain visible.
- `financials.json` — audited comparative financial-statement rows with source page, raw source value, unit multiplier and extraction method.
- `council.json` — published eSCRIBE meeting index.
- `council_documents.json` — meeting-to-document attachment graph. `finance_tags` are title-keyword search aids only, not findings, approvals or parsed document semantics.
- `benchmarks.json` / `external_funding.json` — every row carries explicit scope: `hrm`, `regional_type_comparator`, or `province_program_context`. Context rows must never be attributed to HRM.

## Refresh architecture

`scripts/refresh_all.py` runs collectors serially, then runs both validation gates before the refresh is eligible to commit. Current budget extraction runs before historical budget extraction, and those scripts write different files. Historical capital augmentation runs only after the base historical ArcGIS collection.

The scheduled workflow commits `data/sources.json` and `data/generated/*` together after successful validation, preventing multiple data jobs from racing to push independent partial states.

## UI requirements

The Build 005 UI is additive (`domains-ui.js` / `domains-ui.css`) and does not replace `app.js`, compensation integration, budget integration, or `light-theme.css`. The light theme remains the final stylesheet.

Large domain tables render a maximum of 100 rows per page. Evidence drawers preserve source links and scope caveats. Missing, historical, report-level and contextual evidence must never be converted into synthetic current facts.
