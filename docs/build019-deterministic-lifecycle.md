# Build 019 — Deterministic Lifecycle Reconciliation

Production baseline before Build 019: Build 018 at `93fd8b769a48271b5f1f12782a3fa4a25a1d38d9`.

Recovery baseline before this build: `baseline/build-018`.

Build 019 creates an evidence-first lifecycle graph from already validated HalifaxData artifacts. It does not replace source-specific records, infer missing transactions, or merge entities because their names or dollar values look similar.

## Objective

Connect public-finance evidence only where a deterministic identifier or direct documentary key proves the relationship:

- capital project/account identifiers;
- solicitation / procurement identifiers;
- purchase-order identifiers;
- exact Council meeting/item evidence;
- exact Council document identifiers.

The lifecycle path remains an evidence graph, not an accounting ledger:

`CAPITAL / PROJECT → PROCUREMENT → AWARD / VENDOR → AMENDMENT → COUNCIL / DOCUMENT`

The following stages remain unproved unless a separate authoritative source is acquired:

`SERVICE-AREA BUDGET ↛ PROJECT` where no shared deterministic key exists.

`AWARD / PO ↛ PAYMENT` while no validated public AP/vendor-payment ledger exists.

`PROJECT ↛ AUDITED PSAS LINE` without a validated crosswalk.

## Authoritative matching policy

Build 019 authoritative links may use only:

1. the same explicit structured identifier on two evidence records;
2. a source-parser-extracted identifier, with formatting normalization only;
3. an exact known project identifier inside a structured internal-reference field;
4. an exact document ID;
5. an exact meeting + item reference;
6. a narrow cross-identifier bridge whose source structure proves both identifiers belong to the same record-level event.

Build 019 does **not** use:

- fuzzy project-name matching;
- fuzzy vendor-name matching;
- equal/similar dollar values;
- timing proximity by itself;
- same business unit by itself;
- a shared phrase/title by itself;
- inferred budget or audited-account crosswalks.

Vendor names are retained for context only and never create a Build 019 authoritative edge.

## Procurement reference normalization

The only permitted normalization for procurement identifiers is source-format normalization:

- optional literal `HRM-` prefix may be ignored;
- spaces around a hyphen may be ignored;
- a two-digit year is normalized to `20YY`;
- the numeric solicitation sequence must remain the same.

For Council evidence, the normalized identifier must also occur literally in the approved motion text. Source forms such as `RFP2024-0662` remain valid because the exact `2024-0662` year-number token is present; the adjacent `RFP` prefix does not create or alter the identifier.

## Council motion-context rule

Build 016 Council parsing can attach the nearest heading to an aggregate/consent motion. Build 019 therefore does **not** use parsed `item_title` or `item_ref` to establish a procurement/capital identifier edge.

A Council identifier edge is accepted only when the identifier itself is present in the approved `motion_text`.

This rule was established during Build 019 review after `2025-0441` appeared under a misleading inherited item title. The approved motion itself explicitly contains `Award – RFP# 2025-0441 – Mobile Wireless Service`, so the identifier evidence was valid but the inherited title was unsafe as a linkage label. Build 019 labels such evidence generically as a Council motion and retains the parsed heading only as non-linking context.

The final checked graph contains **22 Council identifier links verified directly against approved motion text** and **0 quarantined Council identifier links**.

## Capital identifier safety rule

Build 018 `project_account_id` and Build 010 `project_code` are the authoritative capital identifiers for this milestone.

Raw Build 010 `previous_code` is **not** authoritative in Build 019. Source review found that the field currently contains a mixture of:

- actual previous project codes;
- multiple comma-separated codes;
- parser text such as `Capital Project Name: ...`;
- reused labels such as `Transit26`.

An early Build 019 experiment treated all exact `previous_code` strings as identifiers. That produced large capital-only components and incorrectly collapsed unrelated records. The experiment was not released. Build 019 now excludes those edges explicitly until a separate one-to-one project-code continuity parser is validated.

Final control:

- **258** authoritative capital identifiers in the safe structured-code set;
- **431** candidate capital-identifier edges explicitly excluded from authoritative Build 019 linking;
- `previous_code_authoritative = false`.

## Same-identifier evidence graph

The validated Build 019 artifact is:

`data/generated/lifecycle_reconciliation.json`

Parser identity:

`build019-deterministic-lifecycle-v1`

Final same-identifier controls:

- **2,811** identifier evidence links;
- **98** direct documentary links;
- **53** cross-domain same-identifier chains;
- **33** capital identifier chains;
- **20** procurement identifier chains;
- **52** chains span two domains;
- **1** chain spans three domains;
- **16 of 52** Build 018 current capital schedule accounts already connect to another evidence domain;
- **22** Council identifier links independently verified against approved motion text;
- **0** payment facts.

These counts measure deterministic evidence connectivity, not completeness of HRM financial activity.

## Cross-identifier bridges

Different explicit identifiers are joined only under narrow source-structure rules.

### Quarterly award → capital project/account

The official quarterly alternative-procurement table publishes the solicitation/project identifier and an `Internal Reference / Cost Centre Project Number` field on the same award row.

Build 019 may therefore connect an exact procurement reference to an exact safe capital project code when both are published on that same structured award row.

Examples from the checked artifact include:

- `CP180002 ↔ 2025-0355`;
- `CP180002 ↔ 2025-0573`;
- `CR200001 ↔ 2026-0317`;
- `CR200001 ↔ 2026-0338`;
- `CR200003 ↔ 2026-0306`;
- `CZ230100 ↔ 2025-0548`;
- `CZ230100 ↔ 2026-0110`;
- `CZ230100 ↔ 2026-0184`;
- `CT000007 ↔ 2025-0204`;
- `CT000007 ↔ 2026-0329`.

These are row-level source associations, not name matches.

### Procurement reference → purchase order

A CAO contract-amendment observation may connect one procurement/contract reference to one purchase order when that observation contains exactly one of each.

Examples include:

- `2018-186 → PO 2070924188`;
- `2018-302 → PO 2070796457`;
- `2022-169 → PO 2070887951`;
- `2023-159 → PO 2070901586`;
- `2024-0034 → PO 2070920062`.

A shared procurement reference can legitimately connect to more than one PO when separate source observations explicitly establish each pair. Build 019 does not merge the POs merely because they appear in the same aggregate report.

### Council procurement → capital

A specific Council motion may bridge a procurement reference to a capital account only when:

- the Council record has a specific item reference;
- the procurement identifier and capital identifier are both explicitly present in the same approved motion;
- both identifiers already pass their source-specific validation rules.

Aggregate/consent motions remain valid evidence for individual identifiers but do not cross-bridge unrelated identifiers appearing in a bundled motion.

## Final lifecycle components

After excluding unsafe legacy capital-code edges, Build 019 produces **40** explicit cross-identifier bridges and **31** connected lifecycle components.

Domain profiles:

- **18** `capital + council_document + procurement`;
- **3** `capital + council + council_document + procurement`;
- **8** `amendment + procurement`;
- **2** amendment-only identifier components retained by the bridge graph.

Higher-value verified component controls:

- **21** components connect capital ↔ procurement;
- **8** components connect procurement ↔ public CAO amendment evidence;
- **3** capital/procurement components also carry approved Council evidence;
- **0** components contain payment evidence.

A component groups only explicit identifier relationships already proved by its source records. It is not evidence of wrongdoing or proof that all lifecycle stages are complete.

## Deterministic lifecycle investigation queue

Build 019 derives an additive review queue from the verified lifecycle components:

`data/generated/lifecycle_investigations.json`

The queue contains **29** targets:

- **21** capital ↔ procurement targets;
- **8** procurement ↔ amendment targets;
- **3** carry approved Council evidence;
- **2** `priority_review`;
- **2** `review`;
- **25** `context`;
- **0** payment-backed targets.

The review score ranks **evidence depth and lifecycle complexity**. It is not a probability of corruption, waste, illegality, policy breach, overpayment or misconduct.

Review reasons are limited to reproducible conditions such as:

- capital account linked to procurement award evidence;
- multiple procurement references linked to the same capital component;
- approved Council motion in the lifecycle evidence;
- procurement reference linked to public CAO amendment evidence;
- multiple POs linked to one procurement reference through separate exact observations.

Build 019 does not automatically characterize any of these as suspicious.

## UI integration

The Build 019 UI is additive to the existing Investigations page.

- Existing Build 008 analytical investigations remain present below the new panel.
- Build 019 uses the already approved investigation card/grid styling rather than redesigning the page.
- The panel exposes exact identifiers, evidence depth, source links and interpretation boundaries.
- Desktop/mobile browser gates assert that the old Build 008 cards remain present.
- Payment evidence is displayed as `0` and transaction analyses remain disabled.

## Release gates

Build 019 is not production-complete until all of the following pass on the same exact candidate head:

1. ordinary repository CI including all Build 019 validators;
2. deterministic lifecycle rebuild with no artifact mutation on a repeat run;
3. Build 019 payment-source research guard;
4. deterministic lifecycle-investigation rebuild with no artifact mutation on a repeat run;
5. full desktop/mobile browser regression through Build 019, with Build 008 investigations preserved;
6. PR-context CI and Build 019 workflows on the exact PR head;
7. exact-head merge to `main`;
8. post-merge CI and Build 019 data/research gates;
9. successful GitHub Pages deployment; and
10. hosted Build 019 browser verification.

Only then should `baseline/build-019` be created.

## Remaining boundaries after Build 019

Build 019 materially improves lifecycle connectivity, but it does not solve every requested link.

- Current operating-budget service-area rows do not expose a deterministic project/solicitation key sufficient for authoritative award linkage.
- No validated public AP/vendor-payment source is available yet.
- No audited PSAS ↔ service/project crosswalk has been validated.
- `previous_code` continuity remains a separate parser/reconciliation problem.
- Public CAO amendment reports are not a complete contract history and may exclude Private & Confidential records.

These remain explicit evidence gaps, not zeros and not negative findings.
