# HalifaxData frontend data contract

This contract keeps the collection work and GitHub Pages application decoupled. Existing Build 001 files remain authoritative and are not renamed by the dashboard work.

## Existing required files

### `data/sources.json`

Current source registry. Each entry currently includes `id`, `name`, `publisher`, `category`, `coverage`, `ingestion`, `status`, and `url`.

### `data/generated/compensation.json`

Current compensation output. The checked-in file may explicitly be a `partial_verified_seed`. Current row fields are:

- `fiscal_year_end`
- `entity`
- `name`
- `person_key`
- `business_unit`
- `position`
- `wages`
- `benefits`
- `total`
- `source_id`

The UI must preserve the metadata warning that absence from a threshold-based disclosure year is not zero compensation.

## Optional generated domain files

The dashboard automatically activates richer views when these files appear:

```text
data/generated/budget.json
data/generated/spending.json
data/generated/procurement.json
data/generated/capital.json
data/generated/financials.json
data/generated/council.json
data/generated/signals.json
```

Until a file exists, the application shows registered source coverage and an explicit “awaiting generated artifact” state.

## Canonical dimensions

### Fiscal period

`fiscal_year_id`, `label`, `period_start`, `period_end`, optional `quarter`, `as_of_date`.

### Business unit

`business_unit_id`, `name`, `parent_business_unit_id`, `valid_from`, `valid_to`, `raw_name`. Reorganizations and historical names must not be overwritten.

### Account / service

`account_id`, optional `account_code`, `category`, `subcategory`, `fund`, `service_area`.

### Vendor

`vendor_id`, `canonical_name`, `raw_name`, optional `aliases`, `match_method`, `match_confidence`. Never merge entities on a fuzzy name alone without retaining the source name.

### Person

`person_id` or stable `person_key`, `display_name`, `raw_name`, `municipal_body`, optional match metadata.

### Project

`project_id`, optional `project_code`, `name`, `business_unit_id`, `status`, optional official `location_id`/geometry reference.

## Core facts

### Budget fact

Recommended fields: fiscal year, fund, business unit, service area, account/category, prior actual, prior budget, projection/forecast, current/final budget, variance amount, variance percentage and provenance.

### Compensation fact

Person, fiscal year, wages/salary, benefits/other compensation, total, disclosure threshold, municipal body, source-defined raw fields and provenance.

### Procurement fact

Award ID, vendor, solicitation, PO, award date, method, original award value, current contract value, funding account, business unit, optional submission count only when explicitly disclosed, and provenance.

### Contract amendment fact

Award ID, amendment number, approval date, amount, cumulative contract value, reason text, approval authority and provenance.

### Spending fact

Publish only fields supported by official data: transaction/document ID, posting date, vendor, amount, account, business unit, project and provenance.

### Capital project fact

Project, fiscal year, original/current approved budget, commitments, actual spend, forecast final cost, target/completion dates, status and provenance.

## Provenance

Production facts should retain enough information to reproduce the record:

- `source_id`
- `source_url` or resolvable registry reference
- `source_title`
- `source_date`
- `retrieved_at`
- `locator_type` (page/table/row/API-record/etc.)
- `locator_value`
- `raw_hash`
- `parser_version`
- `transform_notes`
- `validation_status`

## Signal contract

A generated signal should include:

- `signal_id`
- `signal_type`
- `entity_type`
- `entity_id`
- `score`
- `confidence` where meaningful
- `observed_facts[]`
- `derived_metrics[]`
- `reason_codes[]`
- `source_refs[]`
- `status`
- optional human `interpretation`

The UI must be able to show why a signal was created and what evidence supports its inputs.

## Publication strategy

Start with static JSON because it is inspectable and GitHub Pages-native. Precompute summary values used for first paint. Partition larger facts by fiscal year/domain rather than shipping one unbounded file. When a fact table becomes too large for practical browser JSON, publish Parquet partitions and query them with DuckDB-WASM; do not move analytical semantics into opaque client-only transforms.
