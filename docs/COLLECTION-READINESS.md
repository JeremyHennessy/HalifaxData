# Why automatic collection is inactive

The public site publishes reviewed historical evidence. The 139-reference register is not 139 integrations, and its suggested cadences do not install source jobs. The repository release workflow verifies and deploys already admitted public files; it does not ingest sources. No external scheduler or private hold registry has been inspected by this diagnostic.

The physician-category package is the only proposed collector. Its canonical CLI has `MANUAL_TRANSPORT_ENABLED=False`. This is an intentional operational gate, not a claim that its reusable transport class cannot be called directly. The package's original manifest status is a retained integration-era label, not an operational acceptance receipt. Its integration and current exact file pins are checked separately.

## Run the offline readiness diagnostic

Run `npm run collection:readiness`, or `python3 pipeline/collection_readiness.py` for JSON without npm's command banner. It uses only Python's standard library, never imports the collector, makes no source request, and does not create, read or modify runtime state. The report goes to stdout, not into the public application.

The check verifies the exact package manifest and all listed files, accepted baseline and receipt bindings, retained foundation/receipt bytes, and the sole reviewed release workflow. Missing, modified or symlinked inputs, extra workflows, or local runtime-state presence require review. It does not audit arbitrary scripts outside those checked inputs or prove that no scheduler exists elsewhere.

- Exit 0: the checked inactive repository boundary matches its pins. The report still says `inactive_requires_operational_review`, `collectionAuthorized: false` and `publicationAllowed: false`.
- Exit 2: repository drift or runtime-state presence needs review. Changed provenance is withheld, never silently trusted.
- A missing state directory means state is absent in this checkout, not that historical endpoint holds are clear. A present directory is not opened or evaluated here.

The command checks the same original accepted 435-observation physician-category baseline. Its October 28 retrieval plus seven days yields November 4, 2026 at 12:00:04.365699 UTC. This is only a historical minimum. Later attempts, unresolved holds and hosted scheduling remain unknown, so it is **not a next-run date or permission to fetch now**.

## Retained holds and source restrictions

The exact reviewed foundation records retain access-hold statements for the provincial Public Accounts index (three reference entries sharing one URL) and the original February 2026–27 provincial budget PDF (one supplementary source). Those URLs have not been retried. These historical statements are not a complete current registry, and the absence of a statement for another URL does not establish clearance.

The proposed physician-category scope is only the exact Nova Scotia open-data robots URL, xpt9-p9is metadata URL and full CSV URL recorded by the report. Metadata must still identify the official dataset, original owner, published stage, exact schema and Nova Scotia open-government licence. Known category labels, signed decimal amounts, explicit zeroes and unknown currency/accounting basis must stay intact. New categories stop for semantic/privacy review. No recipients, patient information, inferred totals or financial allegations are introduced.

A same-attempt robots allow match is separate from authorization and never removes an existing hold. Retained policies and synthetic request fixtures are not current source-access evidence. Historical publication receipts authorize only their bound evidence bytes, not a fresh collection or automatic publication.

## What must happen before any activation

1. Review the exact source/endpoints, permitted use and privacy scope. Obtain and reconcile the complete existing attempt/hold history; preserve every unresolved restriction. Do not treat a fresh directory, different URL, elapsed week or new machine as a reset.
2. Select durable private canonical state and review migration of accepted retrievals, attempts, outcomes, reservations, locks and holds. Establish one operational owner, concurrency handling, failure review and rollback. No such state migration or registration is included here.
3. Review the activation change and operational registration explicitly. Verify bounded cadence and request limits, failure stops, state durability and recovery tests before installing any job. Do not infer that passing this diagnostic approves activation.
4. Preserve exact-URL/no-redirect/no-retry behavior; 200,000-byte robots and 1 MiB metadata/CSV caps; 40-second request and 150-second whole-attempt limits; same-attempt policy binding; and persistent holds for denied, challenged, partial, failed or uncertain outcomes. An unreaped worker must stop further requests. Any recovery needs review of the original outcome before another attempt.
5. Keep candidate output private and publication-disallowed. A successful fetch or clean arithmetic comparison is not a publication decision. Independent exact-byte evidence review, public allowlist checks, application/browser checks and exact deployed-asset verification remain separate gates.

No collector setting, source hold, accepted baseline, evidence artifact, collection count, public bundle or deployment schedule is changed by the diagnostic. Repository tests cover both the current inactive state and mutated/missing/symlinked inputs, unknown history, workflow drift, private-state handling and non-authorizing exit codes.
