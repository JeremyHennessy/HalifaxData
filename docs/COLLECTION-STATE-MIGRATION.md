# Private collection-state migration preparation

The collector remains disabled. This is a read-only planning tool, not a migration command, state backend or activation receipt. No complete private history or durable destination has been supplied or verified. A fresh directory must never reset holds or cadence.

## Offline review manifest

Run `npm run collection:migration-plan` for the pinned baseline, retained source holds and outstanding migration requirements. With no arguments it reads no private state contents and makes no source requests. It first runs the repository readiness checks, including the existing presence-only canonical-state check. It never imports the collector.

To rehearse inventories, a reviewer may explicitly supply **frozen private copies**, outside the checkout/public directories:

```
python3 pipeline/collection_migration.py \
  --snapshot /private-review/export-a \
  --snapshot /private-review/export-b
```

These are illustrative paths, not configured storage. This tool does not locate, export, copy, lock, change permissions, register or migrate any state. Do not point it at a running journal. The stdout manifest is private when snapshots are supplied: it contains relative filenames, sizes, hashes and review findings, but no raw record contents or absolute snapshot paths. Keep it outside the repository and public build. `*.migration.private.json` is additionally ignored by Git; that is an accident-prevention rule, not access control.

- Every regular file and directory in each bounded snapshot is inventoried. Empty interrupted-run directories and unknown artifacts are retained for review, not discarded.
- The original accepted baseline must match its exact pinned provenance. The report retains the four historical source-register hold statements covering two URLs; these are not a complete hold registry.
- Native `hold.json`, `active.lock`, failed/unknown outcomes, incomplete records and uncertain responses stay unresolved. No status or successful response clears them.
- Candidate/outcome and response/body hash bindings, expected request URLs and explicit request times receive structural checks. The policy/admission objects are only parsed and inventoried. This command does **not** replay policy, evaluate body content, validate candidates semantically or certify that an attempt was authorized/successful. A manifest with no structural findings is still only a review plan.
- Each origin remains separate. If the same relative path has different bytes or a different type in two supplied snapshots, both versions are retained as a conflict. The tool never chooses the newer-looking copy, overwrites a record or deduplicates history. Matching filenames/bytes do not prove the snapshots describe all operational history. Missing paths are not a clearance or a verified copy-equality claim; independently compare complete inventories before migration.
- The historical lower bound preserves the maximum known accepted retrieval, native hold/lock, request and completion clock plus seven days. Unknown/invalid clocks are flagged. This is not a next-run date. Later unseen attempts, reservations and restrictions remain unknown.
- Inputs are limited to eight snapshots, 4,096 files, 8,192 entries, four directory levels, 8 MiB per file and 64 MiB per snapshot. Unsupported or larger exports require separate review, not selective trimming to make them pass.
- Descriptor-relative no-follow reads reject symlinks and special files. Size, identity and observed-change checks stop when the inventory changes. These checks do not prove an atomic snapshot, filesystem durability or a complete export.

Exit 0 means the limited plan was constructed without structural findings, **not** that state is ready to migrate or collect. Exit 2 means an unsafe/unreadable input, repository drift, conflict or structural finding needs review. All outputs set `migrationAuthorized`, `collectionAuthorized` and `publicationAllowed` to false. The tool never writes a runtime-state file or clears a hold.

## Actual migration remains a separate operation

1. Identify the operational owner and obtain the complete prior attempts, original accepted retrieval, endpoint restrictions, reservations, locks and holds from every relevant location. Retain provenance and explicit history gaps. No history is reconstructed from lack of files.
2. Select private durable storage with an appropriate single-writer/transaction model. Review access boundaries, backing filesystem/database guarantees, backup/restore, retention, capacity, failure ownership and cost before registration. No provider, credential or new access is created here.
3. Freeze/export without dropping an in-flight or uncertain request. Preserve every original artifact and its origin, including denied/partial responses, unknown reservations and unresolved worker termination. Review disagreements rather than choosing a convenient version.
4. Rehearse a separately reviewed atomic import into a **noncanonical** private staging target. Check complete source/destination inventories, semantic hold preservation, cadence, concurrent admission, crash recovery and restore/rollback. Do not delete or mutate the original journals.
5. Register a canonical destination only after the history, source access and operational change have been explicitly reviewed. No state migration or passing diagnostic implies collector activation. Candidate publication still needs independent exact-byte evidence review and the normal release gates.

The current change adds only this offline preparation and synthetic tests. It does not change the byte-pinned foundation package, accepted observations, public evidence, existing workflow, denied endpoints, transport switch or collection count.
