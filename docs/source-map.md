# Source map — current HalifaxData coverage

Research date: 2026-08-27. This document records the official/public-body source universe and current ingestion status. It is a discovery and coverage map, not a claim that every Halifax financial dataset is already ingested.

## Priority 1 — machine or repeatably extractable

1. **HRM annual Statements of Compensation (2016–2025 located and extracted)** — employee/person name, business unit where applicable, position, salary/wages, other benefits and total. The configured statements include HRM plus Halifax Water and Halifax Public Libraries sections. Build 003 validates 10,228 threshold-disclosure rows across the ten statements. The 2025 Library/Water pages require a narrowly scoped text-layer fallback because their PDF table structure collapses under the normal extractor.
2. **2025/26 HRM Budget & Business Plan service-area overviews (extracted)** — Build 004 extracts 104 rows from 18 business-unit service-area overview tables: 86 detail rows plus 18 Net Totals. Each row retains 2023/24 actual, 2024/25 budget, 2024/25 projection, 2025/26 budget, source-published change columns, independently derived change arithmetic, raw source label and PDF page locator.
3. **HRM audited consolidated financial statements (2019–2025 released source-year series)** — Build 017 extends the established conservative statement/schedule parser to seven released annual source years and 1,243 normalized facts. The parser remains `build005-financials-v4`; source-presented prior-year comparators remain attached to their source-year statement rather than being collapsed into synthetic time-series rows. The official 2018 Council attachment is separately registered as an explicit parser gap because the established parser finds zero eligible statement pages. Audited PSAS classifications are not force-joined to budget-book business units without an explicit reconciliation source.
4. **HRM capital project ArcGIS service** — project number, name, category, budget year, location/work descriptions and geometry. Service metadata currently appears historical (data last edited 2022; budget year types through 2021), so it must not be treated as the current capital universe.
5. **Nova Scotia public tender notices** — tender discovery and awards for HRM procurements.
6. **Nova Scotia alternative procurement award notices** — entity/vendor/procurement-circumstance discovery for non-competitive awards.
7. **HRM Council approved minutes and eSCRIBE** — modern eSCRIBE calendar/agenda/minutes coverage plus Build 016 semantic decision extraction from approved Regional Council minutes. The Build 016 source proof validates 986 motion outcomes: 812 from the checked modern posted-minutes window and 174 from a seven-meeting pre-2024 legacy seed. The legacy set is explicitly incomplete and must not be represented as a complete historical archive. Agenda presence remains distinct from approval; motion/result evidence comes from approved minutes.
8. **HRM quarterly financial reports (extracted through Q3 2025/26)** — Build 015 validates 1,753 conservative source-table rows across eight official reports: 2023/24 Q1–Q3, 2024/25 Q2–Q3 and 2025/26 Q1–Q3. The original five-report Build 005 baseline reproduces exactly at 1,094 rows; Build 015 adds 190 Q1, 232 Q2 and 237 Q3 2025/26 rows. These are quarterly financial-summary facts, not invoices, accounts-payable transactions or vendor-payment records. The absent 2024/25 Q1 report remains an explicit source-coverage gap and is not imputed.
9. **Ratified-current 2026/27 HRM service-area budget authority (Build 018)** — the final March 25, 2026 post-Budget-Adjustment-List staff package plus separate March 31 Regional Council ratification evidence. Build 018 validates 105 source rows across 20 service-area overview pages and 20 Net Totals. The final package controls $1.2117B of municipal expenditures and $331.5M of gross capital spending. Budget authority remains distinct from payments, commitments and final actuals.
10. **Approved-current 2026/27 Capital Multi-Year Projects schedule (Build 018)** — Attachment 2 of the revised March 3 capital report resolves from the owning eSCRIBE agenda by exact visible title after its previously indexed filestream URL began returning 404. The checked schedule contains 52 identified rows: 29 discrete projects and 23 ongoing programs, with exact project account IDs and fiscal-year cashflow/budget columns. The 2026/27 scheduled amount across those rows is $196.656M. This is a multi-year capital budget/cashflow schedule, not a complete capital-project ledger or project spend-to-date source.

## Priority 2 — structured PDFs

- Standalone/final published Budget & Business Plan books beyond the currently extracted source layers, including a separately published 2026/27 budget book if HRM exposes one with useful additional structure beyond the verified final March 25 package.
- Annual Capital Plan detailed project work plans beyond the current Build 018 multi-year schedule; the Build 018 Attachment 2 layer does not replace project-sheet evidence or establish spend-to-date.
- Additional quarterly financial/capital reporting outside the currently checked eight-report series, including the unresolved 2024/25 Q1 gap and future quarters as published.
- Audited consolidated financial statements outside the released 2019–2025 source-year series, including resolution of the documented 2018 parser gap only if a defensible extraction path can preserve the established semantics.
- Procurement award / alternative procurement reports beyond the currently normalized public-tender and alternative-procurement series.
- Complete pre-2024 Regional Council approved-minutes archive enumeration beyond the current seven-meeting Build 016 legacy seed.
- Halifax Water annual business plans, financial statements and regulatory submissions.
- Nova Scotia municipal financial condition indicators.

## Priority 3 — investigative context

- HRM Auditor General reports and historical Office of the Auditor General records.
- Nova Scotia OIPC review reports involving HRM/Halifax Water.
- Municipal Archives finance, payroll, assessment and governance records.
- Property assessment/tax-base sources and external transfer/grant records.

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

### Quarterly financial reports — Build 015

- The checked public series currently has no 2024/25 Q1 report. HalifaxData leaves that quarter missing; it is not treated as a zero or interpolated observation.
- The initially indexed eSCRIBE item attachment for the 2025/26 Q3 report returned 404 during source proof. The official HRM static staff-report PDF at `260225afsc1313.pdf` was independently probed and returned a valid PDF, so the stable HRM-hosted staff-report source is used instead.
- Source wording such as **spent or committed** is retained as source context and is not converted into evidence of a cash payment.

### Council decision evidence — Build 016

- The checked modern eSCRIBE calendar does not expose pre-2024 meetings, but official older approved minutes remain retrievable from Halifax.ca / legacycontent. Build 016 therefore treats the modern window as an eSCRIBE coverage boundary rather than the beginning of Council history.
- The current pre-2024 decision layer is an explicit seven-meeting **legacy seed**, not a complete archive.
- Build 016 validates 986 motion/result records, including 960 passed/passed-unanimously motions, 291 fiscal-relevant screening records and 78 records containing source-text dollar mentions.
- A dollar amount in an approved motion remains Council decision text. It is not converted into evidence of an invoice, cash payment, final project cost or final paid contract value.

### Audited financial statements — Build 017

- The official `hrm-financials-2018` Council attachment is located and fetchable, but the established heading-anchored parser finds **zero eligible statement pages** in that source format.
- HalifaxData therefore releases audited source-year rows for **2019–2025**, not 2018–2025. The 2018 source remains registered as `research-parse-gap` rather than being hidden or synthetically filled.
- HRM-published 2018 comparator values inside the 2019 statement remain prior-year comparator values belonging to the 2019 source. They are not relabelled as a successful 2018 extraction.

### 2026/27 final budget package — Build 018

Build 018 independently recalculates the budget change from the printed 2025/26 and 2026/27 endpoints. Exactly one checked row has a source-published percentage discrepancy:

- **Parks & Recreation — Strategic Planning and Design:** the source prints $3,922,100 for the 2025/26 budget, $4,255,900 for the 2026/27 budget, a $333,800 increase and an 8.9% increase. The endpoint arithmetic yields approximately 8.5107%. HalifaxData retains the printed 8.9% and the independently derived value and tags the row as a source-data review item.

No other Build 018 current-budget arithmetic discrepancy is accepted by the validator.

### 2026/27 Capital Multi-Year Projects — Build 018

All 52 project/program rows independently reconcile to their own printed Grand Total. The source control rows contain two underlying defects represented by four exact field-level mismatches:

- the 29 discrete project rows sum to **$207,710,979** of previous-years gross budget and **$1,014,838,979** Grand Total, while the printed discrete subtotal is one dollar lower at **$207,710,978** and **$1,014,838,978**;
- the final Grand Total row repeats the printed discrete previous-years subtotal (**$207,710,978**) rather than discrete plus ongoing previous-years rows (**$672,458,424**), a difference of **-$464,747,446** after the discrete subtotal's one-dollar defect;
- the same one-dollar defect carries into the final source schedule Grand Total: project/program rows compute to **$2,152,999,431** while the source prints **$2,152,999,430**;
- all other fiscal-year control columns reconcile, and the 23 ongoing-program rows reconcile numerically to their source subtotal.

The previously indexed `DocumentId=4406` attachment returns 404. The collector re-reads the owning March 3 agenda and requires one unique exact-title link, currently resolving the official report to `DocumentId=4622`. The source rows and source controls are preserved rather than rewritten.

## Label normalization provenance — Build 004

The 2025/26 budget table exposes three shortened/typo service-area labels. HalifaxData retains every raw label and uses a canonical label only where official HRM budget evidence independently establishes the complete form:

- `Infrastructure Maintenance & Operatons` → `Infrastructure Maintenance & Operations` — complete heading appears elsewhere in the same 2025/26 budget book.
- `Government Relations & Externa` → `Government Relations & External Affairs` — complete heading appears elsewhere in the same 2025/26 budget book.
- `Information Technology/Collecti` → `Information Technology/Collections` — complete service-area label appears in prior official HRM Budget & Business Plans.

No general fuzzy label cleanup is permitted by the Build 004 contract. Build 018 likewise retains current source headings rather than force-mapping them onto the prior-year organization taxonomy.

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

- **No complete public transaction-level accounts-payable/vendor-payment ledger has been verified.** Quarterly financial reports, tender awards, Council decisions, amendment reports and Build 018 budget/capital schedules do not close this gap.
- Public procurement information remains fragmented between HRM reports/eSCRIBE and the provincial tender system.
- The located HRM capital ArcGIS service is historical and cannot stand in for current capital plans. Build 018 adds an approved-current multi-year schedule but not a complete current project-sheet universe, spend-to-date ledger or final-cost source.
- The checked quarterly financial series has an explicit 2024/25 Q1 source gap. A 2025/26 Q4/year-end quarterly report was not verified during the August 27 Build 018 refresh and is not treated as zero activity.
- Pre-2024 Council decision coverage is still incomplete; Build 016 currently proves the legacy approved-minutes path with seven source meetings rather than claiming a complete historical archive.
- The official 2018 audited-financial source remains an explicit parser gap; no 2018 source-year rows are released under the established parser semantics.
- HalifaxData does not claim a service-area-to-PSAS reconciliation crosswalk; those source classifications remain separate until explicit reconciliation evidence is collected.
- Build 018 verifies the final March 25 staff budget package and March 31 ratification for current 2026/27 service-area authority. A separately published final standalone 2026/27 Budget & Business Plan book may still provide additional structure and should be treated as a separate source-discovery task if located.
- A 2025/26 (year ended March 31, 2026) HRM Statement of Compensation was not verified during the August 27 Build 018 refresh; absence from the checked search is not proof that it has not been published.
- A 2026 CAO contract-amendment report was not verified during the August 27 Build 018 refresh; the current checked public amendment series ends November 25, 2025 and absence is not treated as zero amendment activity.
