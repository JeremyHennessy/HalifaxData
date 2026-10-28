# HalifaxData

A new, independent public watchdog for Halifax and Nova Scotia.

**Investigate first. Explain clearly. Prove what can be proven. Show what remains unanswered.**

This repository starts from an empty history. Its application, evidence contracts and interface are written anew. It is separate from HalifaxSourced.

## Mission

Trace public revenue, budget requests, approvals, government decisions, contracts, vendors, amendments, disclosed payments, delivery and outcomes. Identify reproducible accountability questions without treating anomalies as proof of misconduct.

The implementation is intentionally bounded: a transparent 139-reference source register, 29 source-linked fiscal facts, a neutral budget comparison, 33,670 reviewed tender observations, a 71-label supplier subset, 555 historical municipal operating records, and a reviewed unresolved reporting question. Later bounded collections add historical audit follow-up, captured budget tables, federal transfer program traces, exact government-decision links, institutional statements, supplemental authorizations, a cash/accrual explanation and a separate historical municipal capital-assets table. These are different record types—not a complete financial ledger or 139 working integrations. The source register derives collection scope, count units, review dates and refresh limits from matching accepted receipts.

Each collection has an exact-byte independent review receipt and explicit limitations. Application tests, hosted browser checks and live asset verification are separate gates; a local implementation is not a claim of deployed functionality.

## Evidence principles

- Keep budget, authority, award, invoice, payment, expense and final cost distinct.
- Preserve source locators, time periods, accounting bases and limitations.
- Never invent joins from similar names, dates or amounts.
- Treat unavailable evidence as unknown, not zero or proof of absence.
- Keep unreviewed consequential allegations out of public bundles.
- Review competing explanations, corrections and official responses.
- Protect personal, patient and complainant information.

## Development

The public application uses native JavaScript modules and CSS. The offline publisher uses Python's standard library. No paid service, AI API or account credential is required.

- `npm ci` installs the test dependency.
- `npm test` runs deterministic evidence/model tests.
- `npm run build` creates a strict public-file allowlist in `dist/`.
- `python3 -m http.server 4173 --directory dist` serves the built site.
- `npm run test:browser` exercises the public routes against that server.

Original raw captures and private investigations must remain outside this repository. CI must pass before deployment. A local build is not a verified live release.

## Long-term scope

Investigation and case review; financial reconciliation; procurement and vendor evidence; government decisions; all 16 Halifax districts with valid-time representation; provincial healthcare and public-service investigations. Validated policy simulations come later, after the investigative foundation.

## Exact-reference coverage and procurement context

The Sources page has a separately reviewed, frozen **2026-10-28 12:34:39 UTC** reconciliation: 139 original references, 121 distinct URLs, four exact URLs with reviewed subsets and three with retained capture evidence. These are not live completeness measures, working integrations or a proportion of government data. Publisher-family documents are listed separately; the existing application collection directory remains independent.

An optional procurement methodology annotation preserves the captured 33,670 observations and explains recurring identifiers and the generic awarded-amount field, including a short reviewed surplus-sale description. It does not deduplicate records, establish expenditure, assign vendor risk or add an evidence collection. Both artifacts and their independent receipts are admitted by exact SHA-256 at build and runtime. The methodology also verifies its exact tender-index target. Optional context failures do not block the underlying collection directory or tender explorer.

## Halifax Water historical project evidence

The Water explorer is one grouped collection: six page-39 project closeouts from a September 2024 staff report, with ten source-reported regulatory references. Costs are cumulative through March 31, 2024, not annual cash payments. Source budgets, signed differences, six blank Over Budget cells and Burnside’s explicit zero remain distinct. Two selected-subset narrative reconciliations do not add money or records. Completion is staff-reported, not independently inspected.

One optional original M10687 approval context is tied to Churchill Drive project 300003121 by exact reported matter and approval date. Version 2 adds reviewed public H-1/H-2 clarification and preserves version 1 for provenance. The 8,825,000 original estimate/funding plan is not reconciled to the later 9,805,000 report budget; no cross-stage overrun or payment calculation is made. Percentage bases and total rounding are labelled arithmetic inferences. No raw letters, signatures, contacts or package facsimiles are published. The optional context adds no project, regulatory-reference or collection count.

### Additional original Water approval contexts

Cowie Hill and Akerley now have separately reviewed, optional original-decision contexts on their existing project rows. Cowie’s explicit original/additional-funding chain reproduces an inclusive revised total, numerically matching the later staff budget without asserting complete accounting reconciliation. Akerley preserves the report’s Design Work label, the broader rehabilitation approval and a later budget of unreconciled scope. Each context independently verifies its exact parent bytes, project number, matter references, dates and receipt. Failure of one cannot suppress the others or the six-row report. No project, regulatory-reference or collection count is added.

### Richmond organization register
`#/richmond-register` presents the independently reviewed 85 organization-role entries from the County of Richmond’s January 2026 register—not Halifax, all register rows or cleared payments. Exact source labels/identifiers, four source sections, date filters, 20-row pagination, entry locators and review-bound JSON export preserve source scope. The fixed $482,855.06 source-dollar face-amount sum appears only in an explicitly bounded evidence disclosure; arithmetic uses integer cents, not floating-point totals. Personal, redacted and unreviewed labels remain excluded. The independent receipt/artifact are byte-pinned; optional failure does not disable other collections.

Hosted collection-failure checks use `tests/reviewed-count.mjs`, an explicit validated release baseline, rather than scattered literal totals. The homepage additionally asserts its independently fixed expected label, so a wrong manifest and wrong page cannot validate one another.
## Offline pipeline foundation (inactive)

`pipeline/foundation` adds reviewed historical arithmetic checks, retained robots-policy matching and a disabled candidate collector. Its 139 offline tests are included explicitly in `npm test`. No scheduler, source fetch, public finding or new collection is activated. The public build allowlist is unchanged; package fixtures, generated reports and runtime state must stay outside `dist`. See `docs/OFFLINE-PIPELINE-FOUNDATION.md`.
