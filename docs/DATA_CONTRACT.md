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

### `data/generated/budget.json`

Build 004 publishes two intentionally separate record types in one source-provenance artifact. `metadata.dataset_status` is `automated_structured_extraction`.

#### `service_area_budget`

One row per published 2025/26 Budget & Business Plan service-area line, including each business-unit `Net Total`.

Required fields:

- `record_type = service_area_budget`
- `fiscal_year = 2025/26`
- `fiscal_year_end = 2026`
- `business_unit`
- `service_area` — canonical display label
- `source_service_area_label` — raw label extracted from the current source table
- `prior_actual` / `prior_actual_period = 2023/24`
- `prior_budget` / `prior_budget_period = 2024/25`
- `projection` / `projection_period = 2024/25`
- `current_budget` / `current_budget_period = 2025/26`
- `source_reported_budget_change`
- `source_reported_budget_change_pct`
- `derived_budget_change`
- `derived_budget_change_pct` when prior budget is non-zero
- `is_total`
- `source_id = hrm-budget-2025-26`
- `pdf_page`

Where the source's published change arithmetic does not reconcile to the same row's published endpoint budgets, the row may also include:

- `validation_flags[]`
- `source_budget_change_delta`
- `source_budget_change_pct_delta`

Supported flags are `reported_budget_change_mismatch` and `reported_budget_change_pct_mismatch`. These describe a source-data arithmetic inconsistency, not a finding of wrongdoing. The UI must show both source-reported and independently derived values; it must not replace the source value.

A canonical label may differ from `source_service_area_label` only under the allowlisted evidence-backed normalization contract. Such rows also require:

- `label_normalization_basis`
- `label_normalization_evidence`

Build 004 currently has exactly three such rows. Raw source labels must never be discarded.

#### `audited_psas`

Rows from the March 31, 2025 Consolidated Statement of Operations and Accumulated Surplus. The source publishes amounts in thousands of dollars; HalifaxData converts them to CAD while retaining `source_units = thousands_of_cad`.

Required fields:

- `record_type = audited_psas`
- `fiscal_year = 2024/25`
- `fiscal_year_end = 2025`
- `statement_section` — `revenue`, `expense`, or `surplus`
- `category`
- `budget`
- `actual`
- `prior_actual`
- `prior_actual_fiscal_year_end = 2024`
- `variance = actual - budget`
- `source_id = hrm-financials-2025`
- `source_units = thousands_of_cad`
- `pdf_page = 8`
- `printed_page = 4`

### Accounting-basis boundary

`service_area_budget` and `audited_psas` are **not join-compatible dimensions by default**. The budget book is organized by HRM business unit/service area; the audited statement uses PSAS presentation categories. Do not add `business_unit` or `service_area` to an audited row, and do not infer a crosswalk from similar wording. A future reconciliation requires explicit source evidence and a documented transformation.

## Optional generated domain files

The dashboard automatically activates richer views when these files appear:

```text
data/generated/spending.json
data/generated/procurement.json
data/generated/capital.json
data/generated/financials.json
data/generated/council.json
data/generated/signals.json
```

`data/generated/budget.json` is now a required generated artifact for the Build 004 product state. Until another optional file exists, the application shows registered source coverage and an explicit “awaiting generated artifact” state.

## Cross-domain entity index

`data/generated/entity_index.json` is a deterministic derived join artifact over the checked-in `budget.json`, `compensation.json`, `procurement.json`, `capital.json`, and `spending.json` inputs. It does not replace source-domain records.

Current Build 005 normalization rules are deliberately conservative:

- fuzzy matching is disabled;
- current budget-book `service_area_budget` labels anchor operational business units;
- `audited_psas` categories must never be attached to operational business units without a future evidence-backed crosswalk;
- compensation history identity is **reporting organization + existing `person_key`**; `person_key` must never merge people across reporting entities;
- vendor-name clusters are lexical exact provisional clusters and must not be represented as verified legal-entity identities;
- capital rows use exact official project codes where present; an `OBJECTID` fallback remains isolated rather than being joined by project-name similarity;
- a business-unit label with no exact budget anchor remains explicitly unmatched rather than being guessed.

The artifact records SHA-256 hashes and record counts for all five source-domain inputs. `python scripts/build_entity_index.py --check` fails when the checked-in derived artifact is stale. `python scripts/validate_entity_index.py` independently checks source references, dimension IDs, referential integrity, prohibited joins, compensation entity scope, project identity rules, and metadata counts.

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

Build 004's concrete budget fact is the `service_area_budget` contract above. Future budget facts may add fund/account detail but must retain source-defined organizational history and must not overwrite the source-published change fields with derived arithmetic.

### Audited actual fact

Build 004's concrete audited operating fact is the `audited_psas` contract above. A future detailed reconciliation layer should reference this fact rather than mutating it into a departmental budget row.

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

Current Build 004 budget rows additionally retain physical PDF page locators and raw source labels. Source-file SHA-256 hashes are stored in artifact metadata.

## Signal contract

A generated signal should include `signal_id`, `signal_type`, `entity_type`, `entity_id`, `score`, optional `confidence`, `observed_facts[]`, `derived_metrics[]`, `reason_codes[]`, `source_refs[]`, `status`, and optional human `interpretation`.

Signals are review prompts, not findings. The UI must be able to show why a signal exists and what evidence supports it.

## Publication strategy

Start with static JSON because it is inspectable and GitHub Pages-native. Precompute summary values used for first paint. Partition larger facts by fiscal year/domain rather than shipping one unbounded file. When a fact table becomes too large for practical browser JSON, publish Parquet partitions and query them with DuckDB-WASM without moving analytical semantics into opaque client-only transforms.