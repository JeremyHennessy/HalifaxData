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

## Compensation interpretation

The compensation dataset is the complete extraction from the **currently configured annual $100k+ disclosure statements**, not the complete HRM workforce or a transaction-level payroll ledger. A missing person/year is therefore not evidence that the person left employment or received no compensation.

Salary/wages can include acting pay and overtime. Other benefits can include retirement/severance, vacation payouts, allowances and other items defined by the disclosure policy. Review signals are leads for source-level investigation, not findings of waste or wrongdoing.

The configured statements currently contain two arithmetic inconsistencies detected by the validator. HalifaxData stores the published component values and published total, records the delta and exposes the inconsistency as a review signal.

## Run locally

Because the UI is dependency-free, serve the repository with any static server, for example:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000`.

## Refresh compensation data

```bash
python -m pip install -r requirements.txt
python scripts/ingest_compensation.py
python scripts/validate_data.py
```

The same process is configured in `.github/workflows/data-refresh.yml`.

## Data model direction

The long-term reconciliation graph is:

`SOURCE → APPROVAL → BUDGET → PROCUREMENT → VENDOR → PROJECT → AMENDMENT → ACTUAL → AUDIT`

Compensation is modeled separately as:

`PERSON DISCLOSURE → FISCAL YEAR → REPORTING ENTITY → BUSINESS UNIT → POSITION → WAGES → BENEFITS → TOTAL → SOURCE`

See `docs/PRODUCT_SPEC.md`, `docs/DATA_CONTRACT.md`, and `docs/source-map.md`.
