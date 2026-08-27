# Build 015 — Current Fiscal Quarterly Refresh

Build 015 refreshes HalifaxData's quarterly financial-report evidence through the third quarter of fiscal 2025/26 without changing the core interpretation boundary: the dataset contains conservative source-table summaries, **not** accounts-payable transactions, invoices, vendor payments or final paid values.

## Scope

The checked source set is moved into `data/quarterly_financial_sources.json` so fiscal-year, quarter and period-end semantics are explicit source metadata rather than inferred from source IDs.

The identified public set contains eight official HRM quarterly financial reports and **1,753 validated conservative summary rows**:

- 2023/24 Q1 — period ended June 30, 2023 — 346 rows
- 2023/24 Q2 — period ended September 30, 2023 — 135 rows
- 2023/24 Q3 — period ended December 31, 2023 — 166 rows
- 2024/25 Q2 — period ended September 30, 2024 — 195 rows
- 2024/25 Q3 — period ended December 31, 2024 — 252 rows
- 2025/26 Q1 — period ended June 30, 2025 — 190 rows
- 2025/26 Q2 — period ended September 30, 2025 — 232 rows
- 2025/26 Q3 — period ended December 31, 2025 — 237 rows

The original five-report Build 005 baseline therefore reproduces **exactly 1,094 rows**, while the three 2025/26 reports add **659 rows**. The missing 2024/25 Q1 report is an explicit coverage gap in this checked series. It is not imputed, synthesized or treated as zero.

### Q3 source resolution

The Q3 2025/26 report was indexed through an eSCRIBE item attachment whose `DocumentId=4479` endpoint returned HTTP 404 during the network proof, even after session/referer probing. A temporary source probe independently confirmed that HRM's stable staff-report PDF at `260225afsc1313.pdf` returns a valid official PDF (about 2.19 MB), while the compiled eSCRIBE agenda/minutes remain separately accessible. Build 015 therefore uses the stable HRM-hosted staff-report PDF rather than the stale item-attachment URL. The temporary probe workflow was removed after resolution.

## Parser continuity

`scripts/ingest_quarterly_spending.py` retains the Build 005 conservative table-classification semantics for the previously released five reports. Build 015 changes source configuration and adds new reports; it does not intentionally broaden the historical extraction definition. The exact historical row-count reproduction above is a regression control on this boundary.

The Build 015 parser:

- fetches every registered ready source and fails closed if any source is unavailable;
- requires a real PDF response;
- preserves page/table/row source coordinates;
- identifies the first descriptive row label and independently tokenizes source monetary cells;
- retains every independently tokenized monetary value in `values`;
- exposes the last monetary value in the source row as `amount` with the explicit semantic `last_monetary_value_in_source_row`;
- stores fiscal year and quarter directly from the source registry;
- keeps `is_transaction_ledger=false` and `granularity=quarterly financial summary tables` in metadata.

Parser version: `build015-quarterly-financial-v1`.

## Interpretation boundary

The quarterly reports contain operating, reserve, capital, district-fund, area-rate, hospitality and other financial-summary tables. Source wording can include phrases such as **spent or committed**. HalifaxData does not convert those phrases into evidence of a cash payment.

This Build does **not** create:

- accounts-payable records;
- invoice records;
- vendor-payment records;
- cheque/payment identifiers;
- final paid contract values; or
- transaction-level vendor attribution.

The validator explicitly rejects transaction/vendor fields that would imply unsupported granularity.

## Analytical effect

The existing Build 009 trajectory engine automatically consumes the refreshed `spending.json` artifact. This increases the available chronology for like-for-like source-row series and enables additional exact same-period year-over-year comparisons where dates and row identities support them.

The analytical joins remain conservative:

- exact normalized source-row label/context/amount-semantics series only;
- ambiguous duplicate key/date combinations excluded;
- cross-domain corroboration uses exact operating labels only;
- dollar values from different accounting views are never summed together.

A larger movement or more persistent trajectory remains a review signal only, not evidence of overspending, waste, misconduct, corruption, illegality or policy breach.

## UI

The Spend Explorer adds a Current Quarterly Financial Series panel with:

- report and row coverage;
- Q1-Q3 2025/26 current-fiscal report cards;
- latest represented period;
- same-period year-over-year comparison count;
- matched trajectory and ambiguity counts;
- a complete eight-report timeline;
- direct source-evidence drawers; and
- explicit non-transaction and missing-quarter boundaries.

Sources & Evidence adds the Build 015 quarterly source timeline while retaining the rest of the source registry.

## Validation and release gates

- `python scripts/validate_spending.py` independently validates source registry membership, quarter/fiscal/date alignment, tokenizer output, provenance, source counts, current 2025/26 Q1-Q3 presence and the no-payment/no-vendor-field boundary.
- `.github/workflows/build015-quarterly-proof.yml` re-fetches every official source, reproduces `data/generated/spending.json`, validates it and publishes the exact reproducible artifact onto the latest Build 015 branch head.
- The first complete eight-report network proof validated all **1,753** rows before its original publish step encountered a non-fast-forward race; the workflow was then hardened to publish onto the latest remote branch head rather than discarding concurrent UI/documentation commits.
- `tools/build015-ui-smoke.mjs` verifies desktop/mobile current-fiscal coverage, source drawers, the explicit 2024/25 Q1 gap and no horizontal overflow.
- CI checks Build 015 JavaScript/Python syntax and the expanded spending validator.
- Pages hosted verification runs the Build 015 browser gate against the deployed application before release is considered complete.
