# HalifaxData

A new, independent public watchdog for Halifax and Nova Scotia.

**Investigate first. Explain clearly. Prove what can be proven. Show what remains unanswered.**

This repository starts from an empty history. Its application, evidence contracts and interface are written anew. It is separate from HalifaxSourced.

## Mission

Trace public revenue, budget requests, approvals, government decisions, contracts, vendors, amendments, disclosed payments, delivery and outcomes. Identify reproducible accountability questions without treating anomalies as proof of misconduct.

The implementation is intentionally bounded: a transparent 139-reference source register, 29 source-linked fiscal facts, a neutral budget comparison, 33,670 reviewed tender observations, a 71-label supplier subset, 555 historical municipal operating records, and a reviewed unresolved reporting question. These are different record types—not a complete financial ledger or 139 working integrations.

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
