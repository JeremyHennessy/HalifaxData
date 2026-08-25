# Source map — Builds 001–002

Research date: 2026-08-25. This document records the initial official/public-body source universe and current ingestion status. It is a discovery map, not a claim that every Halifax financial dataset is already ingested.

## Priority 1 — machine or repeatably extractable

1. **HRM annual Statements of Compensation (2016–2025 located and extracted)** — employee/person name, business unit where applicable, position, salary/wages, other benefits and total. The configured statements include HRM plus Halifax Water and Halifax Public Libraries sections. Build 002 validates 10,228 threshold-disclosure rows across the ten statements. The 2025 Library/Water pages require a narrowly scoped text-layer fallback because their PDF table structure collapses under the normal extractor.
2. **HRM capital project ArcGIS service** — project number, name, category, budget year, location/work descriptions and geometry. Service metadata currently appears historical (data last edited 2022; budget year types through 2021), so it must not be treated as the current capital universe.
3. **Nova Scotia public tender notices** — tender discovery and awards for HRM procurements.
4. **Nova Scotia alternative procurement award notices** — entity/vendor/procurement-circumstance discovery for non-competitive awards.
5. **HRM eSCRIBE** — Council/committee agenda reports, recommendations, minutes and decisions; essential for post-budget amendments and contract increases.

## Priority 2 — structured PDFs

- Annual approved Budget & Business Plan.
- Annual Capital Plan and detailed project work plans.
- Quarterly financial/capital reporting.
- Audited consolidated financial statements.
- Procurement award / alternative procurement reports.
- Halifax Water annual business plans, financial statements and regulatory submissions.
- Nova Scotia municipal financial condition indicators.

## Priority 3 — investigative context

- HRM Auditor General reports and historical Office of the Auditor General records.
- Nova Scotia OIPC review reports involving HRM/Halifax Water.
- Municipal Archives finance, payroll, assessment and governance records.
- Property assessment/tax-base sources and external transfer/grant records (next research pass).

## Confirmed source-data issues found during Build 002

These are issues in the published statements, not inferred wrongdoing:

- **2018 Halifax Public Libraries — Debra Lebel:** published salary/wages plus benefits do not equal the published total; HalifaxData preserves all published numbers and records a +$130.81 delta.
- **2025 Halifax Public Libraries — Heather MacKenzie:** the official statement publishes $113,978.57 wages, no benefits and a $111,827.16 total; HalifaxData preserves the values and records the -$2,151.41 delta.

The validator fails any unexplained arithmetic mismatch. Only explicitly tagged source-reported discrepancies pass as warnings.

## Planned analytical tests

These are screening tests only; each requires provenance before any conclusion.

- Budget-to-actual variance and repeated forecast misses.
- Capital carry-forward persistence and delivery ratio.
- Project budget escalation from first approval to current authorization.
- Vendor concentration by department/project category.
- Competitive vs alternative procurement mix.
- Contract amendments relative to original award.
- Reserve withdrawals relative to stated purpose and Council authorization.
- Compensation year-over-year outliers, role changes, benefits-heavy years and source arithmetic mismatches.
- Duplicate/similar procurement descriptions near approval thresholds **only when transaction-level evidence exists**.

## Known gaps

- No complete public transaction-level accounts-payable ledger has been verified yet.
- Public procurement information is fragmented between HRM reports/eSCRIBE and the provincial tender system.
- The located HRM capital ArcGIS service is historical and cannot stand in for current capital plans.
- A 2025/26 (year ended March 31, 2026) HRM Statement of Compensation was not located in the initial web search; absence from search results is not proof that it has not been published.
