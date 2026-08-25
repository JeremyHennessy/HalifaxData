# Source map — Builds 001–004

Research date: 2026-08-25. This document records the initial official/public-body source universe and current ingestion status. It is a discovery map, not a claim that every Halifax financial dataset is already ingested.

## Priority 1 — machine or repeatably extractable

1. **HRM annual Statements of Compensation (2016–2025 located and extracted)** — employee/person name, business unit where applicable, position, salary/wages, other benefits and total. The configured statements include HRM plus Halifax Water and Halifax Public Libraries sections. Build 003 validates 10,228 threshold-disclosure rows across the ten statements. The 2025 Library/Water pages require a narrowly scoped text-layer fallback because their PDF table structure collapses under the normal extractor.
2. **2025/26 HRM Budget & Business Plan service-area overviews (extracted)** — Build 004 extracts 104 rows from 18 business-unit service-area overview tables: 86 detail rows plus 18 Net Totals. Each row retains 2023/24 actual, 2024/25 budget, 2024/25 projection, 2025/26 budget, source-published change columns, independently derived change arithmetic, raw source label and PDF page locator.
3. **March 31, 2025 audited consolidated Statement of Operations (extracted)** — Build 004 extracts 20 PSAS revenue/expense/surplus rows from PDF page 8 / printed page 4. The source publishes in $000s; HalifaxData converts to CAD while retaining source-unit provenance. These rows are not force-joined to budget-book business units.
4. **HRM capital project ArcGIS service** — project number, name, category, budget year, location/work descriptions and geometry. Service metadata currently appears historical (data last edited 2022; budget year types through 2021), so it must not be treated as the current capital universe.
5. **Nova Scotia public tender notices** — tender discovery and awards for HRM procurements.
6. **Nova Scotia alternative procurement award notices** — entity/vendor/procurement-circumstance discovery for non-competitive awards.
7. **HRM eSCRIBE** — Council/committee agenda reports, recommendations, minutes and decisions; essential for post-budget amendments and contract increases.

## Priority 2 — structured PDFs

- Annual approved Budget & Business Plan beyond the currently extracted 2025/26 service-area layer.
- Annual Capital Plan and detailed project work plans.
- Quarterly financial/capital reporting.
- Audited consolidated financial statements beyond the currently extracted Statement of Operations layer.
- Procurement award / alternative procurement reports.
- Halifax Water annual business plans, financial statements and regulatory submissions.
- Nova Scotia municipal financial condition indicators.

## Priority 3 — investigative context

- HRM Auditor General reports and historical Office of the Auditor General records.
- Nova Scotia OIPC review reports involving HRM/Halifax Water.
- Municipal Archives finance, payroll, assessment and governance records.
- Property assessment/tax-base sources and external transfer/grant records (next research pass).

## Confirmed source-data issues

These are issues in published source records, not inferred wrongdoing.

### Compensation statements — Build 003

- **2018 Halifax Public Libraries — Debra Lebel:** published salary/wages plus benefits do not equal the published total; HalifaxData preserves all published numbers and records a +$130.81 delta.
- **2025 Halifax Public Libraries — Heather MacKenzie:** the official statement publishes $113,978.57 wages, no benefits and a $111,827.16 total; HalifaxData preserves the values and records the -$2,151.41 delta.

### 2025/26 Budget & Business Plan — Build 004

Build 004 independently recalculates each service-area budget change from the published 2024/25 and 2025/26 budget endpoints. The source contains **11 rows** where the published change amount and/or percentage does not reconcile beyond rounding. All source values are retained and tagged. Confirmed examples include:

- **Information Technology — Service Management & Operations:** published endpoints imply a $2,106,000 increase, while the service-area overview prints a $2,406,000 / 16.2% change.
- **Information Technology — Net Total:** the service-area overview prints a $6,609,300 / 17.2% change while the same page later prints $6,309,300 / 16.4%; the published endpoint budgets imply $6,309,300.
- **Human Resources — Employee Relations:** published endpoints imply a $443,000 increase while the overview prints $329,200 / 13.9%.
- **Human Resources — Net Total:** published endpoints imply $1,534,800 while the overview prints $1,421,000 / 13.9%.
- **Planning & Development — Engineering & Building Standards:** the published dollar change reconciles, but the source prints a 0.8% change while the endpoint budgets imply approximately 49.4% in magnitude.

The validator fails any unexplained arithmetic mismatch. Only explicitly tagged source-reported discrepancies with independently verified delta fields pass as warnings.

## Label normalization provenance — Build 004

The current budget table exposes three shortened/typo service-area labels. HalifaxData retains every raw label and uses a canonical label only where official HRM budget evidence independently establishes the complete form:

- `Infrastructure Maintenance & Operatons` → `Infrastructure Maintenance & Operations` — complete heading appears elsewhere in the same 2025/26 budget book.
- `Government Relations & Externa` → `Government Relations & External Affairs` — complete heading appears elsewhere in the same 2025/26 budget book.
- `Information Technology/Collecti` → `Information Technology/Collections` — complete service-area label appears in prior official HRM Budget & Business Plans.

No general fuzzy label cleanup is permitted by the Build 004 contract.

## Planned analytical tests

These are screening tests only; each requires provenance before any conclusion.

- Budget-to-actual variance and repeated forecast misses.
- Budget-book service-area growth and projection drift, with source-arithmetic warnings separated from derived metrics.
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
- Build 004 does not claim a service-area-to-PSAS reconciliation crosswalk; those source classifications remain separate until explicit reconciliation evidence is collected.
- A final, reliably retrievable 2026/27 Budget & Business Plan PDF has not yet been verified for ingestion; current Build 004 budget-book coverage is 2025/26.
- A 2025/26 (year ended March 31, 2026) HRM Statement of Compensation was not located in the initial web search; absence from search results is not proof that it has not been published.
