# Build 011 — Procurement Lifecycle / Alternative Procurement

Baseline: Build 010 hotfix (`b4c3cc053c1d39285f7e147355157013f4f738af`).

Build 011 adds a source-backed HRM quarterly Award of Contracts evidence layer for rows that HRM places inside its controlled **Alternative Awards / Alternative Procurement** appendix sections. This layer is intentionally separate from the Nova Scotia public-tender award dataset.

## Released evidence contract

- 8 quarterly HRM Award of Contracts reports.
- 84 report-controlled appendix rows.
- $25,252,794.75 collected appendix award value.
- 7 source rows at exactly $50,000 are retained because HRM includes them inside the controlled appendix and the report controls only reconcile when they remain.
- 80 rows have supplier identities eligible for conservative repeat/concentration grouping.
- 4 source summaries remain visible but are explicitly excluded from supplier grouping because the supplier identity is not reliable enough to normalize.
- Grouping-eligible collected value is $24,332,031.75 and is the only denominator used for Build 011 supplier concentration.
- Supplier grouping is case/whitespace-normalized only. Legal-name, punctuation and corporate-suffix variants are not silently merged.

## Report controls

Every quarterly report must reconcile to HRM's published alternative-procurement row count. Later report formats that publish an alternative-procurement dollar control must also reconcile to that value within $0.02.

The collector supports only source-observed schemas:

1. legacy `Alternative Awards` section rows following an explicit section marker through `Net Total`;
2. dedicated modern appendix tables using `Award Total Project Value` / `Project Value`;
3. the Apr–Jun 2026 dedicated appendix using the renamed `Award Total` column.

A general competitive-award table is not reclassified merely because an individual row says `Alternative Procurement`.

## eSCRIBE attachment replacement

The checked-in Council document graph records the Aug. 25, 2026 quarterly report at eSCRIBE `DocumentId=5716`. That attachment later returned 404 while the owning agenda exposed the exact same visible report title at `DocumentId=5776`.

Build 011 preserves this mutation instead of rewriting history:

- the checked-in graph URL is attempted first;
- if it no longer serves a PDF, the owning checked-in agenda is re-read;
- exactly one `filestream.ashx` link whose visible text exactly matches the checked-in report title is required;
- the historical graph URL, live resolved URL and resolution method are retained in report and row provenance.

## Procurement-type boundary

Membership in HRM's controlled alternative-procurement appendix is distinct from the row's literal procurement-type field. Modern rows preserve literal values such as `Alternative Procurement`, `Agreement Adoption` and `Exemption`. Legacy rows explicitly state that the report format has no separate source procurement-type column.

## Interpretation boundary

This layer is not:

- an accounts-payable or transaction ledger;
- a complete procurement ledger;
- a list of every amendment, renewal or change order;
- evidence of every bidder or procurement method considered;
- final paid value;
- proof of improper, unlawful or non-competitive procurement.

Build 011 concentration/repeat scores are review-ordering aids within this report-controlled layer only. Values are never added to the public-tender award denominator.
