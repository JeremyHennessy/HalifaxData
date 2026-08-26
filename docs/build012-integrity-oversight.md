# Build 012 — Integrity & Oversight Evidence

Build 012 adds authority-backed oversight evidence to HalifaxData without changing the approved application shell or redefining the existing anomaly scores.

## Scope

This build adds four related capabilities:

1. **Auditor General findings** — structured records from the June 2026 Office of the Mayor Expenses and Capital Budgeting audits.
2. **Contract-amendment oversight** — selected records from HRM CAO Contract Amendment reports, preserving published amounts, percentages, explanations and source arithmetic.
3. **Campaign-finance source coverage** — official 2024 mayoral disclosure and candidate-rule sources registered for future relationship analysis. No donor/vendor relationship is asserted by this build.
4. **Evidence-status taxonomy** — explicit separation between an anomaly, a control weakness, policy noncompliance, a formal referral, and substantiated wrongdoing.

## Evidence-status taxonomy

| Status | Meaning |
| --- | --- |
| `anomaly` | Reproducible pattern that warrants review. No independent finding of a control or policy failure. |
| `control_weakness` | An independent authority identified deficient controls, governance, documentation or review. |
| `policy_noncompliance` | An authoritative source concluded an applicable policy or requirement was not followed. |
| `referred_for_investigation` | A competent authority formally referred a matter for investigation. Referral is not an offence finding. |
| `substantiated_wrongdoing` | Used only when an appropriate authority actually substantiates wrongdoing. Never inferred from scores. |

The checked-in Build 012 artifact contains **zero** `referred_for_investigation` records and **zero** `substantiated_wrongdoing` records. Those tiers remain visible in the UI so absence is explicit rather than silently inferred.

## Authority findings

`data/generated/integrity_oversight.json` contains six authority-backed records:

- four Office of the Mayor procurement-policy noncompliance findings;
- two Capital Budgeting control-weakness findings.

These records are **not scored** by the Build 008/009 anomaly engine. They are shown in a separate authority-backed surface because an official oversight conclusion is a different type of evidence from a statistical screening condition.

The Mayor audit records preserve mitigating facts where the source provides them, including valid-invoice context and reimbursement of the two legal invoices. The Capital Budgeting records expressly distinguish a published-plan overstatement from an improper payment.

## Contract amendments

The Build 012 amendment seed contains five selected records from HRM CAO reporting. It is deliberately **not** represented as a complete contract-amendment ledger or a complete procurement denominator.

For every record HalifaxData stores:

- original value;
- cumulative increase;
- published cumulative percentage;
- published new value;
- independently derived `original + cumulative increase` value;
- published arithmetic delta;
- the source-provided explanation/context;
- exact source ID and locator.

One source table — Contract 24-016 with Fathom Studio Inc. — contains a $95.23 arithmetic inconsistency between the published original/cumulative values and the published new contract value. HalifaxData retains the source values and flags the discrepancy rather than silently correcting it.

## Campaign finance

`data/integrity_sources.json` registers official campaign-finance disclosure/rule sources. Build 012 asserts **0 campaign-to-vendor relationship records**.

A contribution, donor name, corporate association or name match must never be promoted to an integrity finding on its own. Future relationship analysis must preserve entity-resolution confidence, decision chronology and procurement evidence separately.

## UI behavior

Build 012 is injected into existing views only:

- **Command Center:** authority-backed oversight panel after the existing headline metrics;
- **Investigations:** evidence-status ladder, full authority findings and planned Auditor General work;
- **Vendors & Contracts:** contract-amendment oversight after the Build 011 procurement lifecycle section;
- **Sources & Evidence:** integrity-source coverage plus the nine supplemental source records in the normal source registry.

No navigation item, theme, approved layout system, existing anomaly scoring formula, ingestion contract or prior dataset semantics are changed.

## Validation

`python scripts/validate_integrity_oversight.py` enforces:

- taxonomy ordering and semantics;
- exact authority-finding counts/statuses;
- zero inferred referral/wrongdoing records;
- campaign relationship count remains zero;
- source-ID integrity;
- contract-amendment arithmetic and percentage controls;
- preservation of the known Fathom source arithmetic discrepancy;
- explicit incompleteness boundaries for transaction and amendment coverage.
