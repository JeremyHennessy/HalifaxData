#!/usr/bin/env python3
"""Validate Build 020 AP/payment-source research without creating payment facts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data/payment_source_research_build020.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    require(meta.get("build") == "020", "payment research must be Build 020")
    require(meta.get("domain") == "accounts_payable_vendor_payments", "unexpected research domain")
    require(meta.get("ready_for_transaction_analysis") is False, "AP research must remain blocked without transactions")
    require(meta.get("verified_public_transaction_ledger") is False, "public AP ledger must not be marked verified")
    require(meta.get("verified_internal_transaction_records_exist") is True, "internal AP record existence should be evidence-backed")
    require(meta.get("payment_facts_available_to_halifaxdata") == 0, "Build 020 must still expose zero payment facts")
    require(meta.get("is_evidence_of_source_absence") is False, "targeted research cannot prove source absence")

    internal = payload.get("confirmed_internal_record_evidence") or []
    by_id = {row.get("id"): row for row in internal}
    require("hrm-oag-ap-audit-2021" in by_id, "missing 2021 HRM AP audit evidence")
    audit = by_id["hrm-oag-ap-audit-2021"]
    findings = " ".join(audit.get("findings") or [])
    for token in ("122,328", "11,317", "vendor number", "invoice number", "invoice date", "amount"):
        require(token.lower() in findings.lower(), f"AP audit evidence missing control token {token!r}")
    require(
        audit.get("evidence_class") == "internal_transaction_records_confirmed_not_public_ledger",
        "AP audit evidence must not be represented as a public ledger",
    )

    precedents = payload.get("disclosure_precedent") or []
    precedent_ids = {row.get("id") for row in precedents}
    require("oipc-review-24-06" in precedent_ids, "missing HRM invoice disclosure precedent")
    p2406 = next(row for row in precedents if row.get("id") == "oipc-review-24-06")
    precedent_text = " ".join(p2406.get("findings") or []).lower()
    require("bottom-line totals" in precedent_text, "24-06 precedent must preserve bottom-line-total finding")
    require("not a ruling" in precedent_text, "24-06 precedent must preserve limited-scope caveat")

    access = payload.get("official_access_path") or {}
    require(
        access.get("strategy") == "request_machine_readable_register_before_requesting_invoice_documents",
        "AP workstream must prioritize structured records before invoice PDFs",
    )
    sequence = access.get("preferred_sequence") or []
    require(len(sequence) >= 4, "AP access sequence is incomplete")
    require(any("routine" in step.lower() for step in sequence), "routine access must be attempted")
    require(any("part xx" in step.lower() for step in sequence), "Part XX fallback must be explicit")

    fields = payload.get("minimum_machine_readable_fields") or []
    required_fields = {
        "payment_or_accounting_document_id",
        "vendor_name_or_payee_name",
        "invoice_date_if_releasable",
        "payment_date_or_clearing_date",
        "gross_or_document_amount",
        "purchase_order_number_if_applicable",
        "business_unit",
        "cost_centre_or_responsibility_centre",
        "gl_account_or_expense_category",
        "capital_project_or_internal_order_code_if_applicable",
        "credit_reversal_void_or_cancellation_indicator",
        "document_or_payment_status",
    }
    require(required_fields.issubset(fields), f"AP requested field contract missing {sorted(required_fields - set(fields))}")

    exclusions = set(payload.get("privacy_and_security_exclusions") or [])
    for field in ("bank_account_numbers", "routing_or_transit_numbers", "payment_card_numbers_or_full_card_data", "tax_identification_numbers"):
        require(field in exclusions, f"sensitive field exclusion missing: {field}")

    public_results = payload.get("public_source_search_results") or []
    require(public_results, "public-source search results are missing")
    result_text = " ".join(row.get("result", "") for row in public_results).lower()
    require("no current public" in result_text, "targeted public-ledger research result is missing")
    require("not an hrm ap source" in result_text, "provincial payment benchmark must not become HRM payment data")

    blocked = set(payload.get("analysis_families_blocked_until_payment_source_is_acquired_and_validated") or [])
    for family in (
        "award_to_paid_reconciliation",
        "duplicate_invoice_or_payment_detection",
        "payment_concentration",
        "final_paid_value_assertions",
    ):
        require(family in blocked, f"unsafe payment analysis was not blocked: {family}")

    next_action = payload.get("next_action") or {}
    require(next_action.get("priority") == 1, "AP data request must remain first AP next action")
    require("zero" in next_action.get("production_rule", "").lower(), "production rule must retain zero payment facts")

    print(
        "validated Build 020 AP research: internal transaction records confirmed, "
        "public transaction source not acquired, payment facts remain 0"
    )


if __name__ == "__main__":
    main()
