#!/usr/bin/env python3
"""Validate the Build 007 payment-source research contract.

This deliberately fails if HalifaxData starts claiming transaction-level payment
coverage without a real transaction artifact and documented source.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/generated/payment_source_status.json"
PAYMENTS = ROOT / "data/generated/payments.json"

REQUIRED_FIELDS = {
    "payment_or_document_id",
    "vendor_id_or_vendor_name",
    "posting_date",
    "payment_date",
    "gross_amount",
    "purchase_order_number",
    "contract_or_tender_id",
    "business_unit_or_cost_centre",
    "gl_account_or_expense_category",
    "capital_project_code_if_applicable",
}


def fail(message: str) -> None:
    raise SystemExit(f"payment-source validation failed: {message}")


def main() -> None:
    if not STATUS.exists():
        fail("payment_source_status.json is missing")
    payload = json.loads(STATUS.read_text(encoding="utf-8"))
    metadata = payload.get("metadata") or {}
    if metadata.get("build") != "007":
        fail("unexpected build marker")
    if metadata.get("status") != "public_transaction_source_not_found":
        fail("status must remain public_transaction_source_not_found until a real source is acquired")
    if metadata.get("ready_for_transaction_analysis") is not False:
        fail("transaction analysis must be explicitly disabled")

    evidence = payload.get("evidence") or []
    if len(evidence) < 4:
        fail("source audit must retain at least four evidence entries")
    if any(not item.get("url") or not item.get("finding") for item in evidence):
        fail("every evidence entry needs URL and finding")

    fields = set(payload.get("minimum_requested_transaction_fields") or [])
    missing = REQUIRED_FIELDS - fields
    if missing:
        fail(f"minimum future payment contract is missing fields: {sorted(missing)}")

    blocked = set(payload.get("analysis_families_blocked_until_source_exists") or [])
    if "duplicate_invoice_detection" not in blocked or "award_to_payment_reconciliation" not in blocked:
        fail("key unsupported analyses are not explicitly blocked")

    if PAYMENTS.exists():
        payments = json.loads(PAYMENTS.read_text(encoding="utf-8"))
        rows = payments.get("records") if isinstance(payments, dict) else None
        if rows:
            fail("payments.json contains records while Build 007 still declares no public transaction source")

    print(f"Payment-source gap validated: {len(evidence)} evidence entries; transaction analyses remain disabled")


if __name__ == "__main__":
    main()
