# HalifaxData

HalifaxData is an evidence-first public-finance intelligence project for Halifax Regional Municipality (HRM). It is intended to reconstruct the lifecycle of public money from approved budget through Council changes, procurement, delivery and audited results, while preserving source provenance.

## Build 001 scope

- Static dependency-free web app suitable for GitHub Pages.
- Official-source registry covering compensation, budgets/actuals, capital, procurement, Council records, Halifax Water, oversight and historical sources.
- Compensation history model with a verified partial seed from HRM statements.
- Annual compensation PDF extraction pipeline for 2016–2025.
- Neutral review signals for large year-over-year changes, role/unit changes and benefit concentration.
- CI validation that refuses inconsistent compensation arithmetic or unknown source references.

### Important limitation

The checked-in compensation file is currently a **partial verified seed**, not the complete $100k+ disclosure population. It exists to validate the product and longitudinal model before automated extraction is allowed to replace it. The refresh script refuses to overwrite the seed if any configured annual statement parses below a conservative minimum row count.

HRM's disclosure threshold means a missing person/year is not evidence that the person left HRM or received no compensation. Salary/wages can include acting pay and overtime, while other benefits can include retirement/severance, vacation payout, allowances and other items defined by the disclosure policy. Review signals are therefore leads for source-level investigation, not findings.

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

`PERSON DISCLOSURE → FISCAL YEAR → BUSINESS UNIT → POSITION → WAGES → BENEFITS → TOTAL → SOURCE`

See `docs/source-map.md` for the initial research map.
