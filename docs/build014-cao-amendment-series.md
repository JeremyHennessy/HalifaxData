# Build 014 — Public CAO Contract-Amendment Series

Build 014 expands the single Nov. 15, 2023 amendment context introduced in Build 013 into a longitudinal series built from 12 identified official public Halifax Regional Municipality CAO contract-amendment reports spanning May 17, 2023 through Nov. 25, 2025.

## What is new

- 12 official HRM public report PDFs registered in `data/contract_amendment_sources.json`.
- A reproducible `pdfplumber`/`requests` ingestor in `scripts/ingest_contract_amendments.py`.
- A checked normalized artifact at `data/generated/contract_amendments.json` reproduced from the live official PDFs by GitHub Actions.
- 58 normalized public amendment observations across the identified report set.
- 54 observations with defensible exact PO or source procurement/contract identifiers and three observations without an exact cross-report key.
- One recurring exact identifier in the current public series: Contract 21-302, observed in the Nov. 15, 2023 and May 21, 2025 reports.
- Contract 21-302 shows a $23,216 movement in the published cumulative amendment between those two public reports. This is not assumed to be one change order.
- Three preserved source arithmetic discrepancies: West Bedford Fire Station/HQ design (-$30,000), Slayter Street (-$180), and Fire Boat Infrastructure (-$1).
- Vendors & Contracts now exposes a 12-report timeline, full observation table, exact-identifier trajectories, source arithmetic controls and source/derived amount semantics.
- Investigations replaces the old Build 013 one-report amendment leads with Build 014 full-series review leads. Scores order review only and are not probabilities of corruption, fraud, waste, illegality or policy breach.
- Sources & Evidence exposes all 12 identified report sources.

## Source-schema controls

The public reports do not use one stable table schema across the entire period, so Build 014 does not force them into false source semantics.

- May 17, 2023 publishes `PO Awarded Amount`, `Increase Total to Date`, and `% Increase`. The amendment amount is derived as total-to-date minus original; it is not represented as source-published.
- September 2023 through mid-2025 generally publish `Original PO Awarded Amount`, `Value of Amendment`, `Updated Value of PO`, `% Increase`, and reason. `Value of Amendment` is treated as the published cumulative amendment used to reach the updated value, not necessarily the current incremental request.
- Nov. 25, 2025 publishes `Original PO Value`, `Cumulative Amendment(s) Value`, cumulative percentage and discussion, without an explicit updated-value column. The updated value is derived as original plus cumulative amendments and labelled as derived in the client.

The normalized observations retain source schema, source amount semantics, page/table/row location, extracted source cells, published amounts, derived amounts, published percentage, derived percentage, and source arithmetic controls separately.

## Identity and longitudinal-link boundary

A cross-report trajectory is created only when the same exact source identifier is available:

- exact PO number; or
- source procurement/contract reference after whitespace/hyphen normalization only.

Build 014 does **not** create cross-report links from vendor-name similarity, project-name similarity, fuzzy text matching, or candidate vendor aliases.

## Interpretation boundary

This dataset is public CAO contract-amendment reporting evidence. It is **not**:

- an invoice dataset;
- an accounts-payable or payment transaction ledger;
- a final-paid-value dataset;
- a complete contract history;
- a claim that the 12 identified public reports represent the complete universe of HRM amendments; or
- evidence that a large or repeated amendment is improper.

Public amendment reports may exclude Private & Confidential amendment records. Contract amendments can reflect legitimate scope, schedule, site-condition, utility, market, safety, or operational changes.

## Validation and release gates

`python scripts/validate_contract_amendments.py` checks the 12-report source registry, report/date coverage, source/derived semantic boundaries, 58-observation floor, exact trajectory controls, preserved source arithmetic discrepancies, and the no-AP/no-payment/no-wrongdoing assertions.

`.github/workflows/build014-amendment-proof.yml` re-fetches the official PDFs, reproduces the normalized artifact, validates it, and uploads the proof artifact. `tools/build014-ui-smoke.mjs` validates the new desktop/mobile surfaces and semantic boundaries. The normal CI, UI Smoke, and Pages hosted-verification workflows include Build 014 release coverage.
