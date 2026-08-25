# HalifaxData

HalifaxData is an evidence-first public-finance intelligence project for Halifax Regional Municipality (HRM). It is intended to reconstruct the lifecycle of public money from approved budget through Council changes, procurement, delivery and audited results, while preserving source provenance.

## Current foundation

### Build 001

- Static dependency-free web app suitable for GitHub Pages.
- Official-source registry covering compensation, budgets/actuals, capital, procurement, Council records, Halifax Water, oversight and historical sources.
- Compensation-history model and neutral review-signal UI.
- CI, scheduled public-data refresh and Pages deployment.

### Build 002

- Automated extraction of every currently configured HRM Statement of Compensation from fiscal years ended 2016 through 2025.
- HRM, Halifax Water and Halifax Public Libraries rows retained with reporting-entity provenance.
- 2025 Library/Water text fallback for a confirmed PDF table-layout change; the normal table path remains unchanged for pages that parse correctly.
- Longitudinal name keys normalize harmless typography changes such as Åsa/Asa while the UI keeps histories isolated by reporting entity to avoid unsupported same-name joins.
- Stronger validation of source coverage, year/source consistency, duplicates, threshold rules, annual row counts and source-reported arithmetic discrepancies.
- Published arithmetic mismatches are preserved and explicitly flagged rather than silently corrected.

## Compensation interpretation

The compensation dataset is the complete extraction from the **currently configured annual disclosure statements**, not the complete HRM workforce. The disclosure threshold is $100,000. A missing person/year is therefore not evidence that the person left employment or received no compensation.

Salary/wages can include acting pay and overtime. Other benefits can include retirement/severance, vacation payouts, allowances and other items defined by the disclosure policy. Review signals are leads for source-level investigation, not findings of waste or wrongdoing.

The source statements themselves currently contain two arithmetic inconsistencies detected by the validator. HalifaxData stores the published component values and published total, records the delta and exposes the inconsistency as a review signal.

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

See `docs/source-map.md` for the initial research map and known gaps.
