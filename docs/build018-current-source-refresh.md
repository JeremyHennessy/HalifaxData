# Build 018 — Current Source Refresh

Production baseline before Build 018: Build 017 at `84fe1abcf62cd52bbd12b7f36ae90020ab64753c`.

Recovery baseline: `baseline/build-017`.

Build 018 refreshes the current fiscal source layer without replacing the proven 2025/26 budget, 2025/26 capital-project-sheet, quarterly-financial, procurement, Council-decision or audited-history evidence already in production.

## Scope

Build 018 adds two separate approved-current evidence types:

1. **2026/27 service-area operating-budget authority** from the final March 25, 2026 post-Budget-Adjustment-List staff package, linked separately to Regional Council's March 31, 2026 ratification.
2. **2026/27 Capital Multi-Year Projects cashflow/budget schedule** from Attachment 2 of the revised March 3, 2026 capital-plan report, linked separately to the March 31 Capital Plan ratification.

The new layers are additive. The established 2025/26 budget explorer and Build 010 capital project-sheet/adjustment surfaces remain intact beneath the Build 018 panels.

## Ratified-current 2026/27 budget

Amount source:

- source ID: `hrm-budget-2026-27-final-package`
- eSCRIBE document: `4584`
- staff package date: March 25, 2026
- source stage: final staff package after Budget Adjustment List deliberations

Approval source:

- source ID: `hrm-council-2026-03-31-budget-ratification`
- Regional Council date: March 31, 2026
- Council record separately establishes ratification of the operating budgets, Capital Plan and tax rates for fiscal 2026/27

Validated Build 018 artifact:

- `data/generated/current_budget_2026_27.json`
- parser: `build018-current-budget-v2`
- **105 source rows**
- **20 service-area overview pages**
- **20 Net Total rows**
- published municipal-expenditure control: **$1,211,700,000**
- published gross-capital-spending control in the final package: **$331,500,000**
- independent Halifax Regional Police Net Total control: **$102,182,400**

### Source-layout controls

The final 2026/27 PDF does not use one stable set of x-coordinates across every service-area table. Build 018 does not modify Build 004's proven 2025/26 parser. Instead it uses a source-specific wrapper whose geometry was established from the live final package:

- every page derives its label/value boundary from that page's own `Net Total` first-value token, capped at the Build 004 legacy boundary;
- a full-source diagnostic across 20 overview pages and 105 amount rows found the furthest-right change-value token at x=`513.65801625` and the earliest percentage token at x=`518.984896`;
- Build 018 therefore uses x=`516.32`, inside that observed empty gap, to separate the change amount from the percentage column;
- rows with no numeric token are treated as text rows rather than being forced through numeric parsing.

### Preserved budget source discrepancy

Exactly one source row is allowed to carry a published arithmetic flag:

- business unit: Parks & Recreation
- service area: Strategic Planning and Design
- source page: 140
- 2025/26 budget: **$3,922,100**
- 2026/27 budget: **$4,255,900**
- published dollar change: **$333,800**
- published percentage change: **8.9%**
- independently derived percentage change: **8.5107%**

The source percentage is retained as source evidence. HalifaxData does not silently rewrite it and does not characterize the discrepancy as wrongdoing.

A repeat official-source proof rebuilt all 105 rows and reported that the checked artifact reproduced exactly without advancing the branch.

## Approved-current 2026/27 capital multi-year schedule

Owning source:

- March 3, 2026 Budget Committee agenda
- report title: `7 - Revised 202627 Multi-Year Capital Plan.pdf`
- staff report date: February 22, 2026
- Attachment 2 / PDF page 9: `2026/27 Capital Multi-Year Projects`

The previously indexed filestream URL, `DocumentId=4406`, now returns 404. Build 018 does not substitute a draft or infer a replacement ID. It re-reads the owning March 3 agenda and requires exactly one unique link whose visible title exactly matches the report. That process currently resolves the live official attachment to `DocumentId=4622`.

Validated Build 018 artifact:

- `data/generated/current_capital_2026_27_multiyear.json`
- parser: `build018-current-capital-v1`
- source table rows: **60**
- identified project/program rows: **52**
- discrete projects: **29**
- ongoing programs: **23**
- 2026/27 multi-year-project cashflow/budget: **$196,656,000**
- row-computed schedule Grand Total: **$2,152,999,431**
- source-printed schedule Grand Total: **$2,152,999,430**

Every project/program row must reconcile independently from its fiscal-year columns to its own source Grand Total. Exact project account IDs are retained for the next lifecycle-reconciliation phase.

### Preserved capital source-control defects

The source has two underlying control-table defects represented by four exact field-level mismatches. These are allowed only by exact control-row/field/value identity; any additional mismatch fails validation.

1. **Discrete-project subtotal is $1 low.** The 29 individually reconciled discrete project rows sum to $207,710,979 of previous-years gross budget and $1,014,838,979 Grand Total. The source subtotal prints $207,710,978 and $1,014,838,978.
2. **Final previous-years control omits the ongoing-program previous-years subtotal.** The 52 project/program rows sum to $672,458,424 of previous-years gross budget, while the source final Grand Total row prints $207,710,978. The source therefore differs by -$464,747,446 after including the discrete subtotal's one-dollar defect.
3. The discrete one-dollar defect also carries into the final schedule Grand Total: row-computed $2,152,999,431 versus source-printed $2,152,999,430.
4. All other fiscal-year control columns reconcile to the project/program row sums. The 23 ongoing-program rows reconcile numerically to the source ongoing subtotal.

These are source-control defects, not findings about project management, spending or legality.

## Interpretation boundaries

Build 018 does **not** create or infer:

- accounts-payable transactions;
- invoices or cheque/payment records;
- cash paid to vendors;
- commitments or encumbrances;
- capital project spend-to-date;
- final project cost;
- cost overruns;
- a service-area budget ↔ audited-PSAS crosswalk;
- wrongdoing from a source arithmetic discrepancy.

A budget or capital cashflow amount is budget authority/planning evidence unless a different source explicitly establishes a transaction, commitment or final actual.

## Other current-source review results

The current-source review also established:

- procurement already includes the April–June 2026 Award of Contracts quarterly report, so the checked procurement series is current through June 30, 2026;
- Council decision evidence was re-researched on August 27, 2026 under Build 016 coverage rules;
- no verified 2025/26 Q4/year-end HRM quarterly financial report was added in Build 018;
- no verified HRM Statement of Compensation for the year ended March 31, 2026 was added in Build 018;
- no verified 2026 CAO contract-amendment report was added in Build 018.

Those absent current sources remain explicit research gaps. They are not treated as zero activity and are not synthetically filled.

## Release gates

Build 018 is not production-complete merely because the source collectors pass. Release requires:

1. full repository CI including both Build 018 validators;
2. repeat official-source proof for the 2026/27 current budget with no artifact mutation;
3. repeat official-source proof for the 2026/27 current capital schedule with no artifact mutation;
4. full browser smoke through Build 018 on desktop and mobile, including assertions that the existing 2025/26 budget and Build 010 capital surfaces remain present;
5. PR-context CI, both source proofs and browser smoke on the exact PR head;
6. exact-head merge to `main`;
7. post-merge CI and both source proofs;
8. successful GitHub Pages deploy; and
9. hosted Build 018 browser verification.

Only after those gates pass should Build 018 be preserved as `baseline/build-018` and the project advance to deterministic lifecycle reconciliation.

## Next approved phase

After Build 018 production closeout, the next phase is **deeper lifecycle reconciliation**. The primary new deterministic key is the 2026/27 capital schedule's exact `project_account_id`. Reconciliation should prefer exact project/account/solicitation identifiers and direct Council/document links; it must not rely on dollar-only or fuzzy-name matches. Stronger cross-domain investigations come only after that linkage layer is verified.
