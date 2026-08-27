# Build 017 — Audited Financial History

Build 017 extends HalifaxData's conservative audited-financial statement extraction from the previously checked two-source layer to a released **2019–2025 annual source-year series**, while preserving the established parser semantics and keeping an incompatible 2018 official source explicit as a coverage/parser gap.

## Released evidence contract

- **7 released annual HRM audited-financial source years:** 2019, 2020, 2021, 2022, 2023, 2024 and 2025.
- **1,243 normalized audited statement/schedule facts** in the reproduced checked artifact.
- Existing parser version remains **`build005-financials-v4`**; Build 017 expands source coverage rather than changing extraction rules.
- Every released source must be on an approved official Halifax host, return eligible statement/schedule pages under the established parser and contribute at least 10 normalized facts.
- Source-presented prior-year comparators remain attached to the annual statement in which HRM published them. They are not converted into independent source-year rows.

## 2018 source boundary

The official 2018 Regional Council financial-statement attachment is located and registered as `hrm-financials-2018`, but the established heading-anchored parser returns **zero eligible statement pages** from that source format.

Build 017 therefore does not manufacture, OCR, remap or relabel 2018 source rows simply to make the annual series appear complete. The source is retained with status **`research-parse-gap`**. The released source-year series begins in 2019.

The 2019 audited statement contains HRM-published 2018 comparative values. Those remain `prior_year` comparator values belonging to the 2019 source and are not represented as a successful 2018 extraction.

## Accounting and interpretation boundary

This layer contains audited consolidated financial-statement and schedule facts. It does **not** create:

- a departmental/service-area operating-budget crosswalk;
- an accounts-payable or invoice ledger;
- transaction-level vendor payments;
- project-level actual-spend records;
- a claim that similarly named audited and budget categories are directly reconcilable; or
- additive time-series observations from repeated prior-year comparator values.

Where annual statements restate or reclassify a prior-year comparator, HalifaxData preserves the source-year context instead of silently collapsing those values into a synthetic chronology.

## UI

Build 017 is additive to the established light application shell. It adds audited-financial-history coverage to the existing financial surfaces and Sources & Evidence, including:

- released source-year coverage for 2019–2025;
- normalized fact counts and parser semantics;
- the explicit 2018 parser-gap notice;
- official source links from evidence drawers; and
- source-series interpretation boundaries.

No navigation redesign, scoring change, theme change or unrelated application refactor is part of Build 017.

## Validation and release gates

`scripts/validate_financial_history_build017.py` enforces:

- exactly the released 2019–2025 source-year set;
- exactly seven released source statuses;
- official Halifax source hosts;
- the existing `build005-financials-v4` parser version;
- a minimum 1,100-row expansion floor;
- at least one eligible statement page and at least 10 facts per released source;
- no released `hrm-financials-2018` status or rows;
- preserved 2019-source prior-year comparator values; and
- source-year, extraction-method and parser-provenance consistency on every normalized row.

The Build 017 proof workflow independently re-fetches the configured official sources, reproduces `financials.json`, validates both the established and Build 017 contracts, rebuilds the entity index and publishes the exact reproduced artifact when it differs from the checked branch artifact.

The normal CI gate now syntax-checks the Build 017 client and browser test and runs the Build 017 validator. The normal UI Smoke workflow runs the dedicated Build 017 browser gate on desktop/mobile surfaces, and the Pages workflow runs the same Build 017 browser verification against the hosted application after merge.

## Next sequence after release

Build 017 deliberately stops at audited-history expansion. The approved next execution phase is a **current-source refresh**, followed by deeper deterministic lifecycle reconciliation and then stronger cross-domain investigation logic. Those later phases must preserve the evidence and identity boundaries established here.
