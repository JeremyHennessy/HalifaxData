#!/usr/bin/env python3
"""Validate Build 018 approved-current 2026/27 capital multi-year schedule."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "current_capital_sources.json"
DATA = ROOT / "data" / "generated" / "current_capital_2026_27_multiyear.json"
PARSER_VERSION = "build018-current-capital-v1"

FORBIDDEN_FIELDS = {
    "invoice_id",
    "payment_id",
    "paid_amount",
    "spend_to_date",
    "commitment_amount",
    "final_project_cost",
    "overrun_amount",
}


def nz(value) -> int:
    return 0 if value is None else int(value)


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    source = config["schedule_source"]
    approval = config["approval_source"]
    controls = source["published_controls"]
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    metadata = payload.get("metadata") or {}
    records = payload.get("records") or []
    source_controls = payload.get("source_controls") or {}

    assert metadata.get("dataset_status") == "ratified_current_capital_multiyear_schedule"
    assert metadata.get("parser_version") == PARSER_VERSION
    assert metadata.get("fiscal_year") == "2026/27"
    assert metadata.get("source_id") == source["id"]
    assert metadata.get("source_agenda_url") == source["agenda_url"]
    assert metadata.get("source_url_resolution") == "exact_title_live_agenda_resolution"
    assert metadata.get("source_url_changed_since_registry") is True
    assert metadata.get("source_url_resolved") == source["known_live_attachment_url"]
    assert metadata.get("source_pdf_page") == source["attachment_pdf_page"] == 9
    assert metadata.get("source_table_rows") == controls["source_table_rows"] == 60
    assert metadata.get("project_rows") == len(records) == controls["project_rows"] == 52
    assert metadata.get("discrete_project_rows") == controls["discrete_project_rows"] == 29
    assert metadata.get("ongoing_program_rows") == controls["ongoing_program_rows"] == 23
    assert metadata.get("current_2026_27_multiyear_budget") == controls["current_2026_27_multiyear_budget"] == 196656000
    assert metadata.get("computed_previous_years_gross_budget") == controls["computed_previous_years_gross_budget"] == 672458423
    assert metadata.get("source_grand_total_previous_years_gross_budget") == controls["source_grand_total_previous_years_gross_budget"] == 207710978
    assert metadata.get("schedule_grand_total") == controls["source_grand_total"] == 2152999430
    assert metadata.get("approval_status") == "ratified_capital_plan"
    assert metadata.get("approval_source_id") == approval["id"]
    assert metadata.get("approval_date") == "2026-03-31"
    assert metadata.get("is_complete_capital_project_ledger") is False
    assert metadata.get("is_spend_to_date") is False
    assert metadata.get("is_accounts_payable_ledger") is False
    assert metadata.get("is_commitment_ledger") is False
    assert metadata.get("is_final_project_cost") is False

    expected_discrepancy = source["known_source_discrepancy"]
    assert metadata.get("source_grand_total_discrepancies") == [{
        "field": "total_previous_years_gross_budget",
        "source_value": expected_discrepancy["source_value"],
        "computed_value": expected_discrepancy["computed_from_discrete_and_ongoing_subtotals"],
        "difference_source_minus_computed": expected_discrepancy["difference_source_minus_computed"],
    }]

    ids = set()
    discrete = 0
    ongoing = 0
    current_total = 0
    grand_total = 0
    for row in records:
        assert row.get("record_type") == "current_capital_multiyear_schedule"
        assert row.get("fiscal_year") == "2026/27"
        assert row.get("source_id") == source["id"]
        assert row.get("source_page") == 9 and row.get("source_table") == 1
        assert row.get("approval_status") == "ratified_capital_plan"
        assert row.get("approval_source_id") == approval["id"]
        assert not (FORBIDDEN_FIELDS & set(row))
        project_id = row.get("project_account_id")
        assert project_id and project_id not in ids, f"duplicate current capital project account id: {project_id}"
        ids.add(project_id)
        assert row.get("project_name")
        assert row.get("schedule_class") in {"discrete_project", "ongoing_program"}
        if row["schedule_class"] == "discrete_project":
            discrete += 1
        else:
            ongoing += 1
        computed = sum(nz(row.get(field)) for field in (
            "total_previous_years_gross_budget",
            "capital_budget_2025_26",
            "capital_budget_2026_27",
            "capital_budget_2027_28",
            "capital_budget_2028_29",
            "capital_budget_2029_30",
            "capital_budget_2030_31_to_2035_36",
        ))
        assert computed == row.get("computed_grand_total") == row.get("grand_total")
        current_total += nz(row.get("capital_budget_2026_27"))
        grand_total += nz(row.get("grand_total"))
        provenance = row.get("provenance") or {}
        assert provenance.get("source_id") == source["id"]
        assert provenance.get("source_url_resolution") == "exact_title_live_agenda_resolution"
        assert provenance.get("parser_version") == PARSER_VERSION
        assert provenance.get("validation_status") == "parsed"

    assert discrete == 29 and ongoing == 23
    assert current_total == 196656000
    assert grand_total == 2152999430

    computed_all = source_controls.get("computed_all_projects") or {}
    assert computed_all.get("capital_budget_2026_27") == current_total
    assert computed_all.get("grand_total") == grand_total
    assert computed_all.get("total_previous_years_gross_budget") == 672458423
    source_grand = source_controls.get("source_grand_total_row") or {}
    assert source_grand.get("total_previous_years_gross_budget") == 207710978
    assert source_grand.get("grand_total") == 2152999430

    print(
        "Build 018 current capital valid: "
        f"{len(records)} rows / 2026/27 ${current_total:,} / schedule ${grand_total:,} / "
        "1 preserved source Grand Total defect"
    )


if __name__ == "__main__":
    main()
