# HalifaxData

HalifaxData is an evidence-first public-finance intelligence project for Halifax Regional Municipality (HRM). It is intended to reconstruct the lifecycle of public money from approved budget through Council changes, procurement, delivery and audited results, while preserving source provenance.

## Current foundation

### Build 001 — evidence and ingestion foundation

- Static dependency-free web app suitable for GitHub Pages.
- Official-source registry covering compensation, budgets/actuals, capital, procurement, Council records, Halifax Water, oversight and historical sources.
- Initial compensation-history model, guarded extraction pipeline, CI, scheduled public-data refresh and Pages deployment.

### Build 002 — investigation dashboard suite

- Command Center, Budget & Actuals, Spend Explorer, Vendors & Contracts, People & Compensation, Capital Projects, Signals Lab, and Sources & Evidence.
- Evidence drawer, global search and cross-view filters.
- Explicit missing-data states instead of fabricated zeroes.
- Optional generated-domain contracts for budget, spending, procurement, capital, financials, Council and signals.

### Build 003 — full configured compensation extraction + UI integration

- Automated extraction of every currently configured HRM Statement of Compensation from fiscal years ended 2016 through 2025.
- **10,228 validated threshold-disclosure rows** across HRM, Halifax Water and Halifax Public Libraries.
- 2025 Library/Water text fallback for a confirmed PDF table-layout change; the normal table path remains unchanged where table extraction works.
- Longitudinal name keys normalize harmless typography differences such as Åsa/Asa while person histories remain isolated by reporting entity.
- Strong validation of source coverage, year/source consistency, duplicates, threshold rules, annual row counts and source-reported arithmetic discrepancies.
- Published arithmetic mismatches are preserved and explicitly flagged rather than silently corrected.
- The Build 002 dashboard remains the UI baseline; Build 003 adds reporting-entity filtering, bounded/paged compensation tables, entity-safe history joins and source-quality evidence.

### Build 004 — budget and audited actuals bridge

- Guarded structured extraction from the official **2025/26 Budget & Business Plan** and the **March 31, 2025 audited consolidated financial statements**.
- **104 budget-book service-area rows**: 86 detail rows plus one Net Total for each of 18 business units.
- Budget-book history preserves 2023/24 actual, 2024/25 budget, 2024/25 projection and 2025/26 budget, plus both source-reported and independently derived budget-change arithmetic.
- **20 audited PSAS operating rows** from the Consolidated Statement of Operations and Accumulated Surplus; source $000 values are converted to CAD with source units retained.
- The two accounting views remain separate. HalifaxData does not force PSAS categories onto departmental/service-area budgets without an explicit reconciliation source.
- Published budget-table arithmetic inconsistencies are preserved and flagged instead of silently corrected.
- Three truncated/typo service-area labels are canonicalized only where other official HRM budget evidence establishes the complete name; every row retains the raw source label and normalization provenance.
- Budget & Actuals now has a dedicated local business-unit/search filter, evidence drawers, source-arithmetic flags, and audited budget-vs-actual metrics while preserving the Build 002/003 application shell.

### Builds 005–011 — longitudinal and investigation intelligence

- Expanded source-backed history for budgets, audited financials, quarterly spending, capital projects, municipal benchmarks, Council records and procurement.
- Cross-domain Investigations surfaces distinguish fiscal-review leads from data-quality issues and retain direct source provenance.
- Automated pattern analysis covers multi-year budget pressure, exact-name procurement persistence/concentration, like-for-like quarterly spending trajectories and conservative cross-domain corroboration.
- Current-capital analysis compares exact project codes across released plans and keeps project estimates/schedules separate from transaction-level spend.
- Procurement lifecycle evidence adds quarterly public-award reporting, alternative-procurement context, department/supplier histories and explicit boundaries where bidder counts, amendments or final-paid values are unavailable.
- Candidate entity aliases remain review aids rather than silently merged identities.

### Build 012 — integrity and oversight evidence

- Adds **six authority-backed HRM Auditor General findings** from the June 2026 Office of the Mayor Expenses and Capital Budgeting audits without converting them into anomaly scores.
- Adds **five selected CAO contract-amendment records** with original value, cumulative increase, published new value, source explanation and independently checked arithmetic.
- Preserves a confirmed **$95.23 arithmetic inconsistency in the published Fathom amendment table** rather than silently correcting the source.
- Adds **nine supplemental integrity-source definitions** covering Auditor General reports, CAO contract-amendment reports and 2024 campaign-finance disclosure/rule sources.
- Introduces an explicit evidence hierarchy: **Anomaly → Control weakness → Policy noncompliance → Referred for investigation → Substantiated wrongdoing**.
- The checked-in Build 012 artifact contains **0 referred-for-investigation records, 0 substantiated-wrongdoing records and 0 campaign-to-vendor relationship assertions**. Higher evidence tiers are never inferred from anomaly scores or name matches.
- Command Center, Investigations, Vendors & Contracts and Sources & Evidence receive additive light-theme panels while the established application shell and prior scoring logic remain unchanged.

## Compensation interpretation

The compensation dataset is the complete extraction from the **currently configured annual $100k+ disclosure statements**, not the complete HRM workforce or a transaction-level payroll ledger. A missing person/year is therefore not evidence that the person left employment or received no compensation.

Salary/wages can include acting pay and overtime. Other benefits can include retirement/severance, vacation payouts, allowances and other items defined by the disclosure policy. Review signals are leads for source-level investigation, not findings of waste or wrongdoing.

The configured statements currently contain two arithmetic inconsistencies detected by the validator. HalifaxData stores the published component values and published total, records the delta and exposes the inconsistency as a review signal.

## Budget / actual interpretation

The 2025/26 Budget & Business Plan service-area tables and the March 31, 2025 audited PSAS statement are **not the same accounting view**. A service-area budget line should not be treated as directly reconciled to an audited PSAS category unless an explicit source supports that crosswalk.

Budget change columns published by HRM are retained as source facts. HalifaxData also calculates the same change from the published endpoint budgets. Where the two disagree beyond source rounding, the row is flagged for source review; the published value is not overwritten.

## Integrity / oversight interpretation

Authority-backed findings are stored separately from analytical anomalies. A control weakness or policy-noncompliance finding is evidence that an independent authority identified a specific problem; it is not automatically evidence of fraud, corruption or a criminal offence.

Contract-amendment rows are selected published oversight examples, not a complete amendment ledger or accounts-payable transaction feed. Campaign-finance records are relationship evidence only and must not be treated as evidence of favoritism or wrongdoing without an independently supported decision/procurement link.

See `docs/build012-integrity-oversight.md` for the Build 012 evidence boundaries and validation controls.

## Run locally

Because the UI is dependency-free, serve the repository with any static server, for example:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000`.

## Refresh public data

```bash
python -m pip install -r requirements.txt
python scripts/ingest_compensation.py
python scripts/ingest_budget.py
python scripts/validate_data.py
```

The same atomic sequence is configured in `.github/workflows/data-refresh.yml`.

## Data model direction

The long-term reconciliation graph is:

`SOURCE → APPROVAL → BUDGET → PROCUREMENT → VENDOR → PROJECT → AMENDMENT → ACTUAL → AUDIT`

Compensation is modeled separately as:

`PERSON DISCLOSURE → FISCAL YEAR → REPORTING ENTITY → BUSINESS UNIT → POSITION → WAGES → BENEFITS → TOTAL → SOURCE`

See `docs/PRODUCT_SPEC.md`, `docs/DATA_CONTRACT.md`, and `docs/source-map.md`.
