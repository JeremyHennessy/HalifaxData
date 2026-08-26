#!/usr/bin/env python3
"""Validate Build 011 quarterly alternative-procurement report evidence fail-closed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "generated" / "procurement_quarterly.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()

    payload = json.loads(args.path.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    reports = payload.get("reports") or []
    rows = payload.get("alternative_procurement") or []

    assert meta.get("dataset_status") == "official_quarterly_alternative_procurement_report_sections", meta
    assert meta.get("parser_version") == "build011-procurement-quarterly-v2", meta
    assert meta.get("alternative_reporting_threshold_wording") == "awards exceeding $50,000", meta
    assert meta.get("is_accounts_payable_ledger") is False, meta
    assert meta.get("is_complete_procurement_ledger") is False, meta
    assert meta.get("is_final_paid_value") is False, meta
    assert len(reports) == 8, len(reports)
    assert len(rows) == 84, len(rows)
    assert meta.get("report_count") == len(reports), meta
    assert meta.get("alternative_procurement_rows") == len(rows), meta
    assert round(meta.get("alternative_procurement_value", 0), 2) == 25_252_794.75, meta
    assert round(meta.get("alternative_procurement_value", 0), 2) == round(sum(row["award_value"] for row in rows), 2)
    assert meta.get("source_rows_at_exact_threshold") == 7, meta

    periods = [row.get("report_period") for row in reports]
    assert all(periods), periods
    assert len(periods) == len(set(periods)), periods

    controlled_counts = 0
    controlled_values = 0
    published_count_sum = 0
    changed_reports = 0
    for report in reports:
        parsed_count = report.get("parsed_alternative_rows")
        parsed_value = report.get("parsed_alternative_value")
        control_count = report.get("alternative_count")
        control_value = report.get("alternative_value")
        assert parsed_count and parsed_count > 0, report
        assert control_count is not None and control_count > 0, report
        assert report.get("source_url_registry"), report
        assert report.get("source_url_resolved"), report
        assert report.get("source_url_resolution") in {"checked_in_graph_url_live", "exact_title_live_agenda_resolution"}, report
        assert report.get("source_url_changed_since_graph") is (report["source_url_registry"] != report["source_url_resolved"]), report
        if report.get("source_url_changed_since_graph"):
            changed_reports += 1
        controlled_counts += 1
        published_count_sum += control_count
        assert parsed_count == control_count, report
        assert report.get("control_count_reconciled") is True, report
        if control_value is not None:
            controlled_values += 1
            assert abs(parsed_value - control_value) <= 0.02, report
            assert report.get("control_value_reconciled") is True, report
    assert controlled_counts == 8, controlled_counts
    assert controlled_values >= 5, controlled_values
    assert len(rows) == published_count_sum, (len(rows), published_count_sum)
    assert changed_reports == meta.get("reports_with_replaced_attachment_url"), (changed_reports, meta)

    expected = {
        "January 2025 to March 2025": (12, None),
        "April 2025 to June 2025": (17, 3_395_725.58),
        "July 2025 to September 2025": (5, 3_466_598.64),
        "October 2025 to December 2025": (8, 2_372_869.21),
        "January 2026 to March 2026": (10, 1_431_779.15),
        "April 2026 to June 2026": (21, 6_857_600.17),
    }
    for period_fragment, (count, value) in expected.items():
        report = next((row for row in reports if period_fragment in row.get("report_period", "")), None)
        assert report, periods
        assert report.get("alternative_count") == count, report
        assert report.get("parsed_alternative_rows") == count, report
        if value is not None:
            assert abs((report.get("alternative_value") or 0) - value) <= 0.02, report
            assert abs((report.get("parsed_alternative_value") or 0) - value) <= 0.02, report

    latest = next(row for row in reports if "April 2026 to June 2026" in row.get("report_period", ""))
    assert latest.get("document_id") == "5716", latest
    assert latest.get("source_url_registry", "").endswith("DocumentId=5716"), latest
    assert latest.get("source_url_resolved", "").endswith("DocumentId=5776"), latest
    assert latest.get("source_url_resolution") == "exact_title_live_agenda_resolution", latest
    assert latest.get("source_url_changed_since_graph") is True, latest

    keys = set()
    exact_threshold_rows = 0
    non_literal_alt_type_rows = 0
    unresolved_vendor_rows = 0
    legacy_rows = 0
    eligible_vendor_rows = 0
    for row in rows:
        assert row.get("procurement_class") == "reported_alternative_procurement_section", row
        assert row.get("source_report_section") == "alternative_procurement_over_50000", row
        assert row.get("source_id") == "hrm-escribe", row
        assert row.get("report_document_id"), row
        assert row.get("report_period"), row
        assert row.get("award_title"), row
        assert row.get("vendor_name"), row
        assert row.get("vendor_display_name"), row
        assert row.get("vendor_identity_status"), row
        assert isinstance(row.get("vendor_identity_eligible_for_grouping"), bool), row
        assert row.get("award_value") is not None and row["award_value"] >= 50_000, row
        assert row.get("source_url"), row
        assert row.get("source_url_registry"), row
        assert row.get("source_url_resolved"), row
        assert row.get("source_url_resolution") in {"checked_in_graph_url_live", "exact_title_live_agenda_resolution"}, row
        assert row.get("source_url_changed_since_graph") is (row["source_url_registry"] != row["source_url_resolved"]), row
        assert row.get("source_page"), row
        assert row.get("source_table"), row
        assert row.get("source_row"), row
        assert row.get("source_schema") in {"legacy_alternative_awards_table", "modern_dedicated_alternative_table"}, row
        assert row.get("procurement_type_source"), row
        assert row.get("procurement_type_display"), row
        assert isinstance(row.get("procurement_type_is_literal_column"), bool), row
        if row["source_schema"] == "legacy_alternative_awards_table":
            legacy_rows += 1
            assert row.get("procurement_type_is_literal_column") is False, row
            assert "no separate source type column" in row.get("procurement_type_display", "").lower(), row
        else:
            assert row.get("procurement_type_is_literal_column") is True, row
            assert row.get("procurement_type_display") == row.get("procurement_type_source"), row
        if row.get("vendor_identity_eligible_for_grouping"):
            eligible_vendor_rows += 1
        else:
            unresolved_vendor_rows += 1
            assert row.get("vendor_identity_status", "").startswith("unresolved_"), row
        provenance = row.get("provenance") or {}
        assert provenance.get("source_url_registry") == row.get("source_url_registry"), row
        assert provenance.get("source_url_resolved") == row.get("source_url_resolved"), row
        assert provenance.get("source_url_resolution") == row.get("source_url_resolution"), row
        key = (row["report_document_id"], row["source_page"], row["source_table"], row["source_row"])
        assert key not in keys, key
        keys.add(key)
        if abs(row["award_value"] - 50_000) <= 0.005:
            exact_threshold_rows += 1
        if row.get("procurement_type_is_literal_column") and "alternative" not in str(row.get("procurement_type_source") or "").lower():
            non_literal_alt_type_rows += 1

    assert exact_threshold_rows == 7, exact_threshold_rows
    assert unresolved_vendor_rows == meta.get("vendor_identity_unresolved_rows"), (unresolved_vendor_rows, meta)
    assert unresolved_vendor_rows == 4, unresolved_vendor_rows
    assert eligible_vendor_rows == 80, eligible_vendor_rows
    assert legacy_rows == 23, legacy_rows
    # HRM's controlled section can include rows with literal source procurement types
    # such as Agreement Adoption or Exemption. Preserve rather than rewrite those facts.
    assert non_literal_alt_type_rows > 0, non_literal_alt_type_rows

    blob = json.dumps(payload).lower()
    for forbidden in ["invoice amount", "accounts payable transaction", "payment date", "final paid value\": true"]:
        assert forbidden not in blob, forbidden

    print(
        f"validated {len(rows)} report-controlled alternative-procurement rows / ${meta['alternative_procurement_value']:,.2f} "
        f"across {len(reports)} quarterly reports; {controlled_counts} count controls and {controlled_values} value controls reconciled; "
        f"{exact_threshold_rows} exact-$50,000 rows; {eligible_vendor_rows} grouping-eligible vendor identities; "
        f"{unresolved_vendor_rows} unresolved vendor summaries; {changed_reports} replaced attachment URL"
    )


if __name__ == "__main__":
    main()
