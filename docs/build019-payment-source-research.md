# Build 019 — Accounts-Payable / Vendor-Payment Source Research

Build 019 resumes the payment-source track separately from deterministic lifecycle reconciliation.

Research date: **2026-08-29**.

Current status: **not yet verified public transaction source**.

This wording is deliberate. Targeted public research did not verify a current public HRM accounts-payable, invoice-level, cheque-register or vendor-payment transaction ledger. That is **not** proof that the records do not exist internally, cannot be released, or will never be published.

## Why this source matters

A validated payment-level source is required before HalifaxData can defensibly perform:

- award-to-paid reconciliation;
- contract-value-to-paid-value analysis;
- project spend-to-date from vendor payments;
- payment concentration analysis;
- duplicate invoice/payment detection;
- split-payment detection;
- payment-timing anomaly analysis;
- final-paid-value assertions.

Budget authorization, tender awards, contract amendments, quarterly financial summaries and audited statements cannot substitute for payment evidence.

## Verified process evidence

Build 019 verified evidence that HRM has an internal accounts-payable/payment process, while preserving the distinction between an internal process and a public ledger.

### Standard Terms and Conditions for Goods and Services

Official HRM source:

`https://www.halifax.ca/sites/default/files/documents/business/doing-business-halifax/Standard_Terms_for_Goods_and_Services_2020-01-03.pdf`

Relevant process facts include purchase-order information on supplier invoices and an electronic payment process. This supports the existence of structured internal payment processing; it does not expose public payment rows.

### Finance accounts-payable function

Historical HRM Finance documentation describes Accounts Payable Processing as recording approved invoices and paying vendors for HRM and related entities. Again, this establishes an internal function, not public transaction coverage.

## Current public-source boundary

The Nova Scotia Awarded Public Tenders dataset and HRM quarterly procurement reports provide procurement/award evidence. An award amount is not evidence that:

- the vendor invoiced HRM for that amount;
- the invoice was approved;
- the amount was paid;
- the amount was the final paid value;
- the payment was associated with one particular project unless a deterministic identifier establishes that relationship.

HalifaxData therefore keeps payment-dependent analyses disabled.

## Acquisition path

The preferred evidence acquisition sequence is:

1. **Routine/informal access first.** Ask the appropriate HRM business unit for a machine-readable accounts-payable/vendor-payment export.
2. **Access-to-information request if necessary.** If the records are not routinely available, request access under the applicable municipal access framework.
3. Request an **electronic machine-readable release** plus data dictionary and code lists. If line-level invoice information cannot be released, request the most granular releasable vendor/payment extract that preserves stable identifiers.

The request should explicitly exclude sensitive banking, tax and personal information that is unnecessary for public-money reconciliation.

## Preferred machine-readable scope

Request the longest practical retention period and one row per releasable payment/disbursement or invoice-payment event.

Preferred fields:

- payment/document ID;
- vendor ID, if releasable;
- vendor name;
- invoice/source-document ID, if releasable;
- invoice date, if releasable;
- posting date;
- payment date;
- gross amount;
- net amount, if available;
- tax amount, if available;
- currency;
- purchase-order number;
- contract/tender/solicitation ID;
- business unit or cost centre;
- GL account or expense category;
- capital project code, where applicable;
- credit/reversal/void indicator;
- payment status, if available.

Supporting metadata requested with the extract:

- field data dictionary;
- code lists for business unit/cost centre/account/status fields;
- coverage start/end dates;
- retention limitations;
- known exclusions or suppression rules;
- credit/reversal/void semantics.

## Explicit exclusions

The requested public-money dataset does not need and should not request unnecessary sensitive data such as:

- bank account numbers;
- routing/transit numbers;
- payment-card data;
- tax-identification numbers;
- personal home addresses;
- personal phone numbers or personal email addresses;
- unrelated protected personal information.

## Checked research contract

Build 019 records the current research boundary in:

`data/payment_source_research_build019.json`

The validator requires:

- `status = not_yet_verified_public_transaction_source`;
- `ready_for_transaction_analysis = false`;
- `is_evidence_of_source_absence = false`;
- the future machine-readable field contract;
- the routine-access → access-request acquisition sequence;
- payment-dependent analysis families to remain blocked;
- the lifecycle graph to continue reporting `has_vendor_payment_facts = false`;
- no checked `payments.json` rows unless the source contract is deliberately updated and separately validated.

The established Build 007 guard remains in force as a second independent control.

## What HalifaxData can do before payment data arrives

Current evidence supports:

- budget-authority analysis;
- capital-schedule analysis;
- procurement-award analysis;
- contract-amendment analysis;
- Council-approval analysis;
- quarterly financial-summary analysis;
- audited financial-statement analysis;
- deterministic identifier lifecycle reconciliation that makes no payment claim.

These analyses should continue to expose their own source semantics rather than being combined into a synthetic transaction history.

## Next action on this track

The next meaningful AP milestone is **source acquisition**, not a speculative parser.

Once a real release is obtained:

1. preserve the original file and retrieval metadata;
2. document its exact entity/time/granularity coverage;
3. determine whether rows are invoices, payments, payment lines, journal postings or another record type;
4. validate identifiers and totals before joining anything;
5. keep credits/reversals/voids explicit;
6. join to procurement/project evidence only through stable source identifiers;
7. only then enable payment-dependent investigations.

Until those steps occur, payment coverage remains zero by evidence—not because HalifaxData assumes zero municipal payments, but because it refuses to invent transaction facts.
