# HalifaxData

HalifaxData is an evidence-first public-finance intelligence project for Halifax Regional Municipality (HRM). It reconstructs public-money flows from approved plans through procurement, delivery and audited results while preserving enough provenance to verify every normalized fact.

## Current Build 003 scope

The current ingestion branch expands the original GitHub Pages prototype into a multi-domain public-finance dataset and investigation dashboard.

- **Compensation:** automated extraction of all currently configured HRM Statements of Compensation for fiscal years ended 2016–2025: **10,228 $100k+ disclosure rows** across HRM, Halifax Water and Halifax Public Libraries. The files preserve wages/salary, benefits/other compensation, total, business unit/position, reporting entity and source ID.
- **Source acquisition:** the source registry is independently fetched and hashed so a parser failure cannot hide a source-access failure. Ready sources currently include HRM budgets, audited statements, quarterly reports, capital plans, provincial procurement data, eSCRIBE, Halifax Water and Nova Scotia municipal datasets.
- **Budget & actuals:** structured tables are extracted from HRM budget books, quarterly reporting and audited financial statements. Raw table/page context is retained when semantic normalization is not yet strong enough for a fact assertion.
- **Procurement:** Nova Scotia awarded-public-tender records are filtered to HRM/Halifax municipal bodies with award/vendor/value/date provenance. This is contract-award evidence, **not** an accounts-payable ledger.
- **Capital:** official historical ArcGIS project data plus capital-plan document history. Historical GIS rows are explicitly marked historical and are not presented as the current capital universe.
- **Spending / quarterly detail:** generated from the most granular official financial-report tables currently mapped. Missing transaction-level AP data remains a visible data gap rather than being replaced with inferred transactions.
- **Council decisions:** eSCRIBE discovery is being deepened to connect approvals, amendments and reports to financial facts rather than treating agenda records as isolated documents.
- **External benchmarks/funding:** Nova Scotia Financial Condition Indicator and municipal-capacity-grant records are retained as HRM facts when the source explicitly identifies HRM. Municipality-type and province-program totals are retained only as clearly labelled context.

## Evidence rules

HalifaxData separates **source facts**, **derived metrics**, **review signals**, **interpretations** and **confirmed findings**. A signal is never automatically described as waste, wrongdoing or a policy breach.

The compensation disclosures are threshold disclosures, not a workforce census. A missing person/year therefore does not mean the person left employment or received zero compensation. Salary/wages can include acting pay and overtime; benefits/other compensation can include retirement or severance payments, vacation payouts, allowances and other source-defined items.

Two arithmetic inconsistencies are currently preserved exactly as published and explicitly flagged rather than silently corrected: one in the 2018 Halifax Public Libraries disclosure and one in the 2025 Halifax Public Libraries disclosure.

## Run locally

The dashboard is dependency-free and GitHub Pages-native:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000`.

## Rebuild data

```bash
python -m pip install -r requirements.txt
python scripts/acquire_sources.py
python scripts/ingest_compensation.py
python scripts/ingest_domains.py
python scripts/ingest_budget_history.py
python scripts/ingest_capital_history.py
python scripts/ingest_financial_history.py
python scripts/ingest_quarterly_spending.py
python scripts/ingest_municipal_benchmarks.py
python scripts/validate_data.py
python scripts/validate_domains.py
```

Each collector is designed to retain a clear domain status so a hard source/parser problem in one domain does not erase valid data produced by another.

## Data model direction

The public-money reconciliation graph is:

`SOURCE → APPROVAL → BUDGET → PROCUREMENT → VENDOR → PROJECT → AMENDMENT → ACTUAL → AUDIT`

Compensation is modeled separately as:

`REPORTING ENTITY → PERSON DISCLOSURE → FISCAL YEAR → BUSINESS UNIT → POSITION → WAGES → BENEFITS → TOTAL → SOURCE`

See `docs/DATA_CONTRACT.md` and `docs/source-map.md` for the current contract and source inventory.
