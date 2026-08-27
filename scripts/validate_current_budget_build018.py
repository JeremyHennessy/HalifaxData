#!/usr/bin/env python3
"""Validate Build 018 ratified 2026/27 service-area budget evidence."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "current_budget_sources.json"
DATA = ROOT / "data" / "generated" / "current_budget_2026_27.json"
PARSER_VERSION = "build018-current-budget-v2"

FORBIDDEN_RECORD_FIELDS = {
    "vendor_name",
    "invoice_id",
    "payment_id",
    "cheque_number",
    "paid_amount",
    "final_cost",
    "accounts_payable_id",
}


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    metadata = payload.get("metadata") or {}
    records = payload.get("records") or []
    pages = payload.get("overview_pages") or []

    assert metadata.get("dataset_status") == "ratified_current_budget_service_area_tables"
    assert metadata.get("parser_version") == PARSER_VERSION
    assert metadata.get("fiscal_year") == "2026/27"
    assert metadata.get("source_id") == config["budget_source"]["id"]
    assert metadata.get("source_url") == config["budget_source"]["url"]
    assert metadata.get("approval_status") == "ratified"
    assert metadata.get("approval_source_id") == config["approval_source"]["id"]
    assert metadata.get("approval_date") == "2026-03-31"
    assert metadata.get("is_accounts_payable_ledger") is False
    assert metadata.get("is_payment_evidence") is False
    assert metadata.get("is_final_cost_evidence") is False

    controls = metadata.get("published_controls") or {}
    expected_controls = config["budget_source"]["published_controls"]
    assert controls.get("municipal_expenditures") == expected_controls["municipal_expenditures"]
    assert controls.get("gross_capital_spending") == expected_controls["gross_capital_spending"]

    assert metadata.get("overview_page_count") == len(pages) >= 12
    assert metadata.get("service_area_record_count") == len(records) >= 45
    assert metadata.get("net_total_count") == sum(bool(row.get("is_total")) for row in records) == len(pages)
    assert len({page.get("source_page") for page in pages}) == len(pages)

    ids = set()
    hrp_control = 0
    for row in records:
        assert row.get("record_type") == "current_service_area_budget"
        assert row.get("fiscal_year") == "2026/27"
        assert row.get("fiscal_year_end") == 2027
        assert row.get("prior_actual_period") == "2024/25"
        assert row.get("prior_budget_period") == "2025/26"
        assert row.get("projection_period") == "2025/26"
        assert row.get("current_budget_period") == "2026/27"
        assert row.get("source_id") == config["budget_source"]["id"]
        assert row.get("approval_status") == "ratified"
        assert row.get("approval_source_id") == config["approval_source"]["id"]
        assert not (FORBIDDEN_RECORD_FIELDS & set(row))
        assert row.get("business_unit_source_heading")
        assert row.get("source_service_area_label")
        assert isinstance(row.get("source_page"), int) and row["source_page"] > 0
        provenance = row.get("provenance") or {}
        assert provenance.get("source_id") == config["budget_source"]["id"]
        assert provenance.get("parser_version") == PARSER_VERSION
        assert provenance.get("validation_status") == "parsed"
        identity = (
            row.get("source_page"),
            row.get("business_unit_source_heading"),
            row.get("source_service_area_label"),
        )
        assert identity not in ids, f"duplicate current-budget source row: {identity}"
        ids.add(identity)
        if (
            row.get("is_total")
            and "halifax regional police" in row.get("business_unit_source_heading", "").lower()
            and row.get("current_budget") == expected_controls["halifax_regional_police_net_budget"]
        ):
            hrp_control += 1

    assert hrp_control == 1, f"expected one final-package HRP net control, found {hrp_control}"

    # Each scanned overview page must reconcile to exactly one row-level Net Total.
    for page in pages:
        totals = [
            row for row in records
            if row.get("source_page") == page.get("source_page") and row.get("is_total")
        ]
        assert len(totals) == 1
        assert totals[0].get("current_budget") == page.get("net_total")

    print(
        "Build 018 current budget valid: "
        f"{len(records)} rows / {len(pages)} overview pages / "
        f"{metadata.get('source_arithmetic_discrepancy_rows')} source-arithmetic review rows"
    )


if __name__ == "__main__":
    main()
