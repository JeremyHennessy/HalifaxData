# HalifaxData dashboard suite — product specification

## Product objective

HalifaxData should let an investigator move from a municipality-wide change to the exact public record that supports it. The product is not a generic civic KPI dashboard and it is not an accusation engine. Its primary job is to reconstruct the lifecycle of public money and make unusual changes easy to inspect without hiding uncertainty or source gaps.

The canonical reconciliation graph is:

`SOURCE → APPROVAL → BUDGET → PROCUREMENT → VENDOR → PROJECT → AMENDMENT → ACTUAL → AUDIT`

Compensation is a parallel evidence graph:

`PERSON DISCLOSURE → FISCAL YEAR → BUSINESS UNIT → POSITION → WAGES → BENEFITS → TOTAL → SOURCE`

## Application suite

### 1. Command Center

Municipality-wide landing page with source coverage, generated-data health, high-priority review signals and the current reconciliation graph. It must distinguish **registered source availability** from **successfully generated analytical data**.

### 2. Budget & Actuals

Analyze prior actual, prior budget, projection/forecast and current/final budget by fiscal period, fund, business unit, service area and account/category. Core lenses: variance, year-over-year growth, cost mix, forecast accuracy, FTE context and Council-approved reallocations.

### 3. Spend Explorer

Trace expenditures from municipality to fund → business unit → service → account → vendor/project → source record. The interface must stop at the most granular official level available; an unavailable transaction layer must be shown as unavailable rather than inferred.

### 4. Vendors & Contracts

Canonical vendor pages joining tender/solicitation, award, purchase order, procurement method, original value, amendments, current value, funding account, business unit, project and approval evidence. Raw vendor names and entity-resolution confidence must remain recoverable.

### 5. People & Compensation

Longitudinal annual compensation disclosure with employee search, fiscal-year and unit filters, role/unit changes, wages, benefits/other compensation, total and source evidence. A missing year cannot be treated as zero or as proof the person left HRM because the disclosure has a threshold.

### 6. Capital Projects

Project history joining original authorization, revised budget, commitments, actual spend, forecast final cost, target/completion dates, awards, amendments, Council decisions and geography where official GIS data exists.

### 7. Signals Lab

Ranked, explainable review queue. Every signal exposes observed facts, derived metrics, rule/reason code, score, caveats and source references. A signal is never automatically promoted to a finding.

### 8. Sources & Evidence

First-class registry for source publisher, category, coverage, ingestion method, current/historical/research status, source URL and data-generation health. Parser or collection failures are product data and must remain visible.

## Cross-application behavior

- Global search across people, sources, review signals and eventually vendors/projects/records.
- Global fiscal-year and business-unit filters where those dimensions exist.
- Evidence drawer from every important row, signal and source card.
- Clear empty states for data that is not yet collected.
- CSV/JSON export in a later build, preserving source IDs.
- Saved comparisons and URL-encoded filter state in a later build.
- Optional entity compare tray for 2–5 people/vendors/projects/programs in a later build.

## Interpretation states

HalifaxData must preserve five distinct states:

1. **Source fact** — direct value from a public record.
2. **Derived metric** — reproducible calculation from source facts.
3. **Review signal** — rule/threshold identifies an item for review.
4. **Human interpretation** — context added after inspecting the evidence.
5. **Confirmed finding** — conclusion supported by separate evidence.

Terms such as fraud, corruption, waste, illegality or policy violation must not be inferred from a signal score.

## GitHub Pages architecture

```text
Official/public-body sources
          ↓
Collectors and parsers (Python / GitHub Actions)
          ↓
Raw snapshots + hashes
          ↓
Normalization / entity resolution / validation
          ↓
Generated facts + derived metrics + signals
          ↓
Static publication bundle
          ↓
GitHub Pages browser application
```

The browser application remains dependency-free for the initial builds. Small and medium datasets should publish JSON partitions. If high-volume facts make JSON impractical, migrate those facts to Parquet and query them in-browser with DuckDB-WASM without changing the product information architecture.

## Deployment / quality gates

Deployment should fail when required generated files are invalid, compensation arithmetic is inconsistent, a generated record references an unknown required source, identifiers duplicate unexpectedly, non-finite numbers appear, or mandatory provenance is absent once a dataset is declared production-complete.

A passing code/data gate is not the same as live verification. After merge, the hosted GitHub Pages build should be checked for desktop and narrow/mobile layouts, navigation, filters, evidence drawer, search, compensation history, source links and graceful missing-domain states.
