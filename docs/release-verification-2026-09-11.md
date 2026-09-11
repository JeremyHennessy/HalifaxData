# Release verification and continuation, September 11, 2026

## State recovered before editing

- Freshness checkpoint: `fcad5779948e3d7d7773723070d0ae72d84d7c53`.
- Build 019 candidate: `3c8790726bc88ed5cda3d90d83df9c5d22e35381`; merged by PR 27 to `ae0b214e2dc6b54b0ad538d6fb05ccc2946111f4`.
- Existing `baseline/build-019`: `ae0b214e2dc6b54b0ad538d6fb05ccc2946111f4`; preserved without moving or recreating it. The ref's historical creation time was not independently recovered.
- Current main and latest verified deployment: `a731452f9d786d5ea1b706e5bace29f44e0d98e3`, freshness expansion PR 28.
- Existing Build 020 branch: `agent/build020-tax-payment-graph`, starting head `fcade3844aab5507fcd1091ba10ef47b0f6fd5d4`, 35 files different from main. No open PR at inspection.
- A clean local clone was used. Synced project reference files were not modified.

## Gates recovered and rerun

| Gate | Evidence |
| --- | --- |
| Exact freshness budget proof | [34595693225](https://github.com/JeremyHennessy/HalifaxData/actions/runs/34595693225): successful checkout and artifact identify `fcad5779` |
| Exact freshness hosted acceptance | [34595693281](https://github.com/JeremyHennessy/HalifaxData/actions/runs/34595693281): exact deployment SHA, hosted URL, desktop/mobile and Build 018 verification |
| Build 019 reconciliation | [34597747467](https://github.com/JeremyHennessy/HalifaxData/actions/runs/34597747467): rerun passed; repeat and checked-artifact equality required |
| Build 019 investigations | [34597747719](https://github.com/JeremyHennessy/HalifaxData/actions/runs/34597747719): rerun passed; repeat and checked-artifact equality required |
| Build 019 full UI | [34597747633](https://github.com/JeremyHennessy/HalifaxData/actions/runs/34597747633): rerun passed |
| Build 019 hosted acceptance | [34598109979](https://github.com/JeremyHennessy/HalifaxData/actions/runs/34598109979): `ae0b214`, desktop 1440 and mobile 390, 29 lifecycle targets, 0 payment evidence, 133 prior investigation cards, no Build 019 errors |
| Current freshness monitor | [34604167683](https://github.com/JeremyHennessy/HalifaxData/actions/runs/34604167683): all seven independent domain jobs passed |
| Current hosted acceptance | [34604167814](https://github.com/JeremyHennessy/HalifaxData/actions/runs/34604167814): successful current-main deployment and hosted checks |

The later `fcad5779`-associated runs from PR 26 check out a synthetic merge. They must not substitute for the exact-main freshness proof above. Hosted reports explicitly allow the established optional missing `signals.json`; this is not counted as an unexpected HTTP error.

Local payment, lifecycle, capital-identifier, component, investigation and pinned release guards passed. A fresh hosted Build 019 browser check against current production passed on desktop and mobile. Production still reports 0 payment-backed lifecycle targets.

## Deterministic path portability

The Windows lifecycle builder was repeatable, but eight source-snapshot paths used backslashes while the released Linux artifact uses forward slashes. Using `Path.as_posix()` removes that platform difference without changing identifiers, links, values, scores or generated production data. Both resulting rebuilds match the checked artifact byte-for-byte. Windows checkout SHA-256: `4887e1d217138566ee757a222fedb6ac1eaf0f1e1b7e1f3e168d9d23759aa7a8`. Investigation repeat SHA-256: `bf92fabb8d7b5a0d5be6260e2ceb307a7f1ca9ea7dabd7354b48416a842df0a4`.

## Historical Council failure diagnosis

[Failed proof 34618218040](https://github.com/JeremyHennessy/HalifaxData/actions/runs/34618218040) preserved 5,059 decisions from 241 sources and four zero-result sources. All four PDFs were downloaded, checked against the artifact hashes, text-inspected and visually reviewed. Each is a swearing-in ceremony: February 3, 2016; November 1, 2016; October 29, 2020; November 5, 2024. None records a motion/result pair.

`data/council_no_motion_sources_build020.json` records the exact dates, URLs, hashes, page counts and review rationale. The historical collector may mark only those exact documents `verified_no_motion_outcomes`, and only with readable text, no motion markers, no records and zero unpaired-result diagnostics. Changed or unknown documents remain gaps. Every source remains in the denominator. No production decisions or lifecycle artifacts are published by this correction.

The preserved candidate plus the four freshly verified PDFs passes the full archive validator: 245 accounted sources, 241 parsed, 4 reviewed no-motion sources, 5,059 decisions, 233 additional historical meeting dates and exact equivalence for all seven legacy seeds. Negative tests reject changed identity, missing text, motion-bearing documents and unpaired outcomes. A fresh network proof remains a separate requirement from this preserved-artifact verification.

## Remaining boundaries

Build 020 already contains a separate AP research register and an unsent routine-access request draft. No invoice/payment ledger has been acquired; summary reports remain summary evidence. Its 2018 OCR adapter covers four primary statements only; schedules remain a gap. Historical decision candidates are not released by this fix. The missing 2024/25 Q1 report, newer authoritative releases, deterministic service/project and PSAS crosswalks, and validated previous-code continuity require independent evidence before promotion. Investigation scoring and the approved light-theme shell are unchanged by this continuation.
