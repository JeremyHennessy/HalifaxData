#!/usr/bin/env python3
"""Validate Build 019 AP/vendor-payment research and keep payment analyses disabled."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/payment_source_research_build019.json"
LEGACY_STATUS = ROOT / "data/generated/payment_source_status.json"
PAYMENTS = ROOT / "data/generated/payments.json"
LIFECYCLE = ROOT / "data/generated/lifecycle_reconciliation.json"

REQUIRED_FIELDS = {
    "payment_or_document_id",
    "vendor_name",
    "payment_date",
    "gross_amount",
    "purchase_order_number",
    "contract_or_tender_id",
    "business_unit_or_cost_centre",
    "gl_account_or_expense_category",
    "capital_project_code_if_applicable",
    "credit_reversal_or_void_indicator",
}
REQUIRED_BLOCKED = {
    "award_to_paid_reconciliation",
    "contract_value_to_paid_value",
    "project_spend_to_date_from_vendor_payments",
    "payment_concentration",
    "duplicate_invoice_or_payment_detection",
    "final_paid_value_assertions",
}


def fail(message: str) -> None:
    raise SystemExit(f"Build 019 payment-source validation failed: {message}")


def main() -> None:
    payload = json.loads(RESEARCH.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    if meta.get("build") != "019":
        fail("unexpected build marker")
    if meta.get("status") != "not_yet_verified_public_transaction_source":
        fail("research status must remain not_yet_verified until a payment source is actually acquired")
    if meta.get("ready_for_transaction_analysis") is not False:
        fail("transaction analysis must remain disabled")
    if meta.get("is_evidence_of_source_absence") is not False:
        fail("research must not claim proof that a public/payment source does not exist")
    if "not proof" not in str(meta.get("principle") or "").lower():
        fail("source-absence interpretation boundary is missing")

    process = payload.get("verified_process_evidence") or []
    boundaries = payload.get("public_source_boundary_evidence") or []
    if len(process) < 2 or len(boundaries) < 2:
        fail("research evidence set is incomplete")
    for row in [*process, *boundaries]:
        if not row.get("url") or not row.get("finding") or not row.get("evidence_class"):
            fail(f"research evidence record incomplete: {row.get('id')}")

    fields = set(payload.get("minimum_machine_readable_fields") or [])
    missing = REQUIRED_FIELDS - fields
    if missing:
        fail(f"future payment ingestion contract missing fields: {sorted(missing)}")

    blocked = set(payload.get("analysis_families_blocked_until_payment_source_is_acquired_and_validated") or [])
    if REQUIRED_BLOCKED - blocked:
        fail(f"unsupported payment analyses not all blocked: {sorted(REQUIRED_BLOCKED - blocked)}")

    access_path = payload.get("access_path") or {}
    sequence = access_path.get("preferred_sequence") or []
    if len(sequence) < 2 or "routine-access" not in sequence[0].lower() or "access-to-information" not in sequence[1].lower():
        fail("routine-access -> access-request acquisition sequence is not explicit")
    if not access_path.get("requested_record_scope") or not access_path.get("fallback_scope"):
        fail("payment-record request scope/fallback missing")

    if PAYMENTS.exists():
        payments = json.loads(PAYMENTS.read_text(encoding="utf-8"))
        rows = payments.get("records") if isinstance(payments, dict) else None
        if rows:
            fail("payments.json contains records before the Build 019 source contract is updated and validated")

    legacy = json.loads(LEGACY_STATUS.read_text(encoding="utf-8"))
    if (legacy.get("metadata") or {}).get("ready_for_transaction_analysis") is not False:
        fail("legacy payment-source guard no longer disables transaction analysis")

    if LIFECYCLE.exists():
        lifecycle = json.loads(LIFECYCLE.read_text(encoding="utf-8"))
        lm = lifecycle.get("metadata") or {}
        if lm.get("has_vendor_payment_facts") is not False or lm.get("is_accounts_payable_ledger") is not False:
            fail("lifecycle graph claims payment evidence")
        if (lifecycle.get("summary") or {}).get("components_with_payment", 0) != 0:
            fail("lifecycle component summary claims payment coverage")

    print(json.dumps({
        "status": "ok",
        "research_status": meta.get("status"),
        "process_evidence": len(process),
        "public_boundary_evidence": len(boundaries),
        "minimum_machine_readable_fields": len(fields),
        "blocked_payment_analysis_families": len(blocked),
        "transaction_analysis_enabled": False,
    }, indent=2))


if __name__ == "__main__":
    main()
