# Reviewed minimum tender collection

The public tender explorer contains 33,670 publisher observations from the 2026-10-28 snapshot of Nova Scotia's Awarded Public Tenders dataset. This is a separately acquired collection, not a claim that all 139 catalogue sources are integrated.

Only seven reviewed fields are included: observation identity, source row identity, tender string, publisher entity label, three source-labelled calendar dates, raw amount string and category flags. Supplier names, descriptions, source maintainer metadata and private investigative cases are absent from every public shard.

## Meaning and limits

- 239 publisher labels are not verified legal entities, provincial departments or beneficial owners.
- 32,002 tender strings are not necessarily unique contracts.
- The source includes unawarded RFIs and excludes cancelled/multiple-vendor tenders. It is not all procurement or a payments ledger.
- Currency, tax basis and unit-versus-total amount basis are unknown. No dollar symbol, aggregation, price comparison, overrun or threshold score is generated.
- Dates retain floating calendar meanings. They do not assert independently verified award events.

## Independent review and reproducibility

The publication receipt binds the exact index hash. The index binds 34 reviewed shard hashes, byte lengths and record counts. Build validation rejects changed bytes, extra field names, unsafe paths and duplicate IDs. The browser checks these hashes before presenting a complete search result. Missing or corrupt shards produce an unavailable state, never partial counts presented as complete.

The collection is loaded only when a user submits a search, approximately 12 MB across 34 static files with three concurrent requests. It does not contact or scrape the original publisher from the browser. Navigating away or pressing Cancel aborts remaining requests. No query or address is saved to a server or local storage.

Search matches tender/source identifiers and publisher labels; source award dates and category flags provide additional filters. These filters do not make inferred entity relationships or award-to-payment joins.

## Attribution

Contains information licensed under the Open Government Licence – Nova Scotia.

Source: https://data.novascotia.ca/Procurement-and-Contracts/Awarded-Public-Tenders/m6ps-8j6u

Licence: https://support.novascotia.ca/services/open-data-portal-licence

No official endorsement is implied. New captures, additional fields or changed semantics require a new review.
