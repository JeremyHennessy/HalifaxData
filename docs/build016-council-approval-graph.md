# Build 016 — Council Approval / Decision Evidence

Build 016 closes a specific evidence gap in HalifaxData: the existing Council layer could establish that a meeting, agenda or attachment existed, but that fact alone did not establish what Halifax Regional Council actually adopted or defeated.

The Build 016 layer extracts motion/result pairs from **official approved Regional Council minutes** and keeps those decision facts separate from agenda recommendations, payments, final costs and policy conclusions.

## Verified source reproduction

The first live-source proof on August 27, 2026 reproduced and validated **986 Council motion outcomes**:

- **812 modern eSCRIBE decision records** from every Halifax Regional Council meeting in the checked modern calendar window that has a posted approved-minutes PDF;
- **174 legacy-seed decision records** from seven explicitly registered pre-2024 approved-minutes PDFs;
- **960 passed / passed-unanimously motions**;
- **291 fiscal-relevant screening records** based on source-text fiscal keywords and/or dollar mentions; and
- **78 decisions containing source-text dollar mentions**.

The legacy set is intentionally a **seed, not a complete historical Council archive**. Its purpose in this build is to prove the older Halifax.ca / legacycontent minutes path and to prevent the eSCRIBE 2024 availability boundary from being mistaken for the start of public Council decision history.

## Evidence model

Each normalized decision record retains, where the approved minutes support it:

- meeting date and modern eSCRIBE meeting ID when applicable;
- agenda item number/title when parsable from the minutes text;
- mover and seconder;
- recorded motion text;
- source-recorded outcome;
- canonical outcome (`passed`, `passed_unanimously`, `defeated`, `tied`, `withdrawn`, or `other`);
- a boolean `motion_passed` derived only from the recorded result;
- source-text dollar mentions;
- exact procurement / planning-case / capital-account tokens when a conservative pattern is present;
- source PDF URL, page locator and SHA-256; and
- an explicit coverage layer distinguishing modern posted-minutes coverage from the incomplete legacy seed.

The collector pairs each `MOTION PUT AND ...` result with the nearest preceding `MOVED by ..., seconded by ...` motion block inside a bounded window. It fails publication if any registered source cannot be fetched as a PDF or if a checked minutes source yields no paired decisions.

## Interpretation boundary

A passed motion is evidence that Council adopted the motion printed in the approved minutes. It is **not** evidence that:

- a referenced amount was invoiced or paid;
- a project or contract ultimately cost that amount;
- a budget authorization was fully spent;
- a procurement complied with every applicable policy; or
- wrongdoing occurred.

Dollar values remain source-text mentions until another evidence layer establishes their semantics. Build 016 explicitly sets `is_payment_ledger=false`.

## UI

The existing **Council & Decisions** route is extended, without redesigning the approved shell, with an **Approved-minutes decision evidence** panel:

- outcome counts;
- fiscal-relevant and dollar-bearing counts;
- year/result/fiscal filters;
- motion text and item context;
- exact reference tokens; and
- evidence drawers linked directly to the official approved minutes.

**Sources & Evidence** adds a Build 016 coverage panel showing modern decision coverage and the seven-source historical seed with an explicit incomplete-history warning.

## Validation / release gates

`validate_council_decisions.py` fails if:

- the artifact is represented as a payment ledger;
- a legacy seed is represented as complete history;
- decision IDs are missing/duplicated;
- modern records reference unknown checked eSCRIBE meetings;
- legacy records reference unregistered sources;
- a source URL is not on an approved official Halifax host;
- source hashes/pages/provenance are absent;
- payment-level fields appear;
- canonical result and `motion_passed` disagree; or
- source/record metadata counts do not reconcile.

The Build 016 live-source workflow independently downloads the approved minutes PDFs, reproduces the artifact, validates it, and publishes the exact checked artifact. Browser smoke validates desktop/mobile Council and Sources surfaces while rerunning all existing Build 009–015 UI gates. GitHub Pages verification will run the same Build 016 browser gate after merge.

## What remains after Build 016

This build does **not** claim a complete pre-2024 Council archive. A later archival expansion can enumerate historical meeting/minutes coverage systematically.

It also deliberately stops before cross-domain relationship construction. The exact reference tokens captured here are inputs for the later project/contract evidence-graph phase, after the audited-history expansion in the approved execution sequence.
