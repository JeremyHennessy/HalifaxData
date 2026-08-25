# HalifaxData frontend data contract

This contract keeps collection and GitHub Pages presentation decoupled. Existing source IDs and generated paths are stable interfaces; UI work must not silently rewrite collector semantics.

## Required files

### `data/sources.json`

Source registry. Current entries include `id`, `name`, `publisher`, `category`, `coverage`, `ingestion`, `status`, and `url`.

### `data/generated/compensation.json`

Compensation disclosure output. `metadata.dataset_status` currently supports:

- `partial_verified_seed` — guarded development/verification subset.
- `automated_full_extraction` — complete extraction from every currently configured annual compensation statement that passed the collector and validation gates.

`automated_full_extraction` does **not** mean full workforce payroll. The public statements use a $100,000 disclosure threshold.

Current row fields:

- `fiscal_year_end`
- `entity` — reporting entity such as Halifax Regional Municipality, Halifax Water, or Halifax Public Libraries
- `name`
- `person_key`
- `business_unit`
- `position`
- `wages`
- `benefits`
- `total`
- `source_id`

Optional row-level evidence/quality fields currently used by the extractor:

- `extraction_method` — emitted when a fallback path, such as `pdf_text_fallback`, was required
- `validation_flags[]`
- `source_total_delta`

When `validation_flags` contains `reported_total_mismatch`, `source_total_delta` records `published total - (published wages + published benefits)`. The UI must preserve the published values and show the discrepancy; it must not silently correct the source.

## Compensation identity rule

Longitudinal history joins are scoped by **reporting entity + `person_key`**. The same normalized name in two entities must not be assumed to represent the same person. Raw display names remain source-visible.

A missing person/year is missing threshold-disclosure evidence, not zero compensation and not proof of departure from employment.

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

Stable identity requires `entity` plus `person_key` unless a stronger explicit cross-entity identifier is later established.

### Project

`project_id`, optional `project_code`, `name`, `business_unit_id`, `status`, optional official `location_id`/geometry reference.

## Core facts

### Budget fact

Recommended fields: fiscal year, fund, business unit, service area, account/category, prior actual, prior budget, projection/forecast, current/final budget, variance amount, variance percentage and provenance.

### Compensation fact

Reporting entity, person, fiscal year, wages/salary, benefits/other compensation, published total, disclosure threshold, source-defined raw fields, validation flags and provenance.

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
- `locator_type`
- `locator_value`
- `raw_hash`
- `parser_version`
- `transform_notes`
- `validation_status`

## Signal contract

A generated signal should include `signal_id`, `signal_type`, `entity_type`, `entity_id`, `score`, optional `confidence`, `observed_facts[]`, `derived_metrics[]`, `reason_codes[]`, `source_refs[]`, `status`, and optional human `interpretation`.

Signals are review prompts, not findings. The UI must be able to show why a signal exists and what evidence supports it.

## Publication strategy

Start with static JSON because it is inspectable and GitHub Pages-native. Precompute summary values used for first paint. Partition larger facts by fiscal year/domain rather than shipping one unbounded file. When a fact table becomes too large for practical browser JSON, publish Parquet partitions and query them with DuckDB-WASM without moving analytical semantics into opaque client-only transforms.
