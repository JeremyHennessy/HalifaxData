# Offline watchdog pipeline foundation

Python3.11+ standard library, no AI calls, dependencies or installed schedules. This combines independently reviewed components for a **repository test/infrastructure layer**, not a new public data collection.

## Components

- `watchdog_checks/`: six pinned historical arithmetic rules. Exact Decimal, source/fact/receipt bindings; no currency inference or cross-source subtraction. Expected replay: one private unreviewed arithmetic flag, three numeric explanations, two insufficient-evidence results. These are existing historical fixtures, not new cases.
- `source_policies/robots.py`: pure retained-policy matcher. Exact case-insensitive product groups, merging, wildcard/end-anchor support, longest normalized rule/Allow ties, percent encoding. Malformed or unsupported policy returns review-required. An allow match is never access authorization.
- `physician_refresh/`: candidate-only category dataset adapter and an **inactive manual collector**. The repository CLI cannot activate transport: `MANUAL_TRANSPORT_ENABLED=False`. No scheduler exists. Future hosting requires a reviewed canonical state/hold migration and explicit operational registration.

## Test integration

```sh
python3 pipeline/foundation/run_tests.py
```

Copy this package into `pipeline/foundation` and append the command above to the existing `npm test` script. Do not replace existing app tests. The complete package currently has139offline tests; actual app-plus-package counts must be verified after integration.

The build must retain its explicit public allowlist. Do not add this directory, test inputs, baseline copies, generated reports or runtime state to public assets, collection counts or CI uploads. No existing public evidence bytes need change for this code-only integration.

## Candidate collection boundaries

The three exact proposed endpoints are the source robots policy, xpt9-p9is metadata and its full CSV download. The matched product token is exactly the token sent by the collector. A policy decision is bound to its same-attempt successful receipt and origin, not read from an arbitrary aged cache. Actual endpoint holds, original accepted retrieval cadence and one-use reservations are checked independently of policy matching.

The accepted baseline retrieval was2026-10-28T12:00:04.365699Z. New state inherits that cadence floor; the first ordinary weekly check cannot be earlier than2026-11-04T12:00:04.365699Z. This is an eligibility calculation, not a scheduled promise. No live calls were made while building/testing this package.

The inactive transport implementation has exact-URL/no-redirect/no-retry gates, bounded bytes, absolute request deadlines in a separate process, durable journal reservations, persistent failed/unknown holds, metadata identity/schema/licence checks, and candidate-only output. Unreaped workers stop further requests. No current source holds may be removed or bypassed by relocating the package or choosing a fresh state directory. The disabled CLI prevents accidental bootstrap before a hosted state location is separately reviewed.

## Public fixtures versus synthetic tests

`fixtures/` contains already admitted public snapshots/receipts for historical arithmetic replay and retained public robots policies. `physician_refresh/baseline/` is the accepted public category projection and receipt. No private PDF, raw personal rows, investigation log or original source capture is bundled.

`physician_refresh/test-inputs/` is **synthetic**, reconstructed from admitted public category facts, minimal metadata and explicitly marked test receipts. It is not evidence of an actual request. Tests require no original workspace/capture paths.

Generated detector reports and refreshed candidates always remain unreviewed and publication-disallowed. A changed annual category label is held for semantic/privacy review. No totals, currency guess, payment identities or medical/person-level data are inferred.

## Separate operational review needed

This package does not authorize a new source call. Before enabling any manual transport, establish a durable hosted canonical state, migrate the original source/hold history without resetting cadence, verify the complete app test/build boundary and review the activation change. No credentials, spending, automatic publication, alerts or cron activation are part of this package.
