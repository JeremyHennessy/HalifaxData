#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data/generated/procurement_quarterly.json"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    reports = payload.get("reports") or []
    rows = payload.get("alternative_procurement") or []

    assert meta.get("dataset_status") == "official_quarterly_alternative_procurement_report_sections", meta
    assert meta.get("parser_version") == "build011-procurement-quarterly-v2", meta
    assert meta.get("is_accounts_payable_ledger") is False, meta
    assert meta.get("is_complete_procurement_ledger") is False, meta
    assert meta.get("is_final_paid_value") is False, meta
    assert meta.get("report_count") == len(reports), (meta, len(reports))
    assert meta.get("alternative_procurement_rows") == len(rows), (meta, len(rows))
    assert meta.get("alternative_reporting_threshold_wording") == "awards exceeding $50,000", meta

    report_by_period = {}
    periods = []
    changed_reports = 0
    controlled_counts = 0
    controlled_values = 0
    published_count_sum = 0
    for report in reports:
        period = report.get("report_period")
        assert period and period not in report_by_period, period
        report_by_period[period] = report
        periods.append(period)
        assert report.get("source_id") == "hrm-escribe", report
        assert report.get("document_id"), report
        assert report.get("meeting_id"), report
        assert report.get("meeting_start_date"), report
        assert report.get("title"), report
        assert report.get("url"), report
        assert report.get("agenda_url"), report
        assert report.get("source_url_registry"), report
        assert report.get("source_url_resolved"), report
        assert report.get("source_url_resolution") in {"checked_in_graph_url_live", "exact_title_live_agenda_resolution"}, report
        assert report.get("source_url_changed_since_graph") is (report["source_url_registry"] != report["source_url_resolved"]), report
        if report.get("source_url_changed_since_graph"):
            changed_reports += 1
        assert report.get("source_schema") in {"legacy_alternative_awards_table", "modern_dedicated_alternative_table"}, report
        parsed_count = report.get("parsed_alternative_rows")
        parsed_value = report.get("parsed_alternative_value")
        control_count = report.get("alternative_count")
        control_value = report.get("alternative_value")
        assert isinstance(parsed_count, int) and parsed_count > 0, report
        assert isinstance(parsed_value, (int, float)) and parsed_value > 0, report
        assert isinstance(control_count, int) and control_count > 0, report
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
    resolved = latest.get("source_url_resolved", "")
    assert resolved.startswith("https://pub-halifax.escribemeetings.com/filestream.ashx?DocumentId="), latest
    assert resolved != latest.get("source_url_registry"), latest
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
        if row["award_value"] == 50_000:
            exact_threshold_rows += 1
        if row["procurement_type_is_literal_column"] is False:
            non_literal_alt_type_rows += 1
        if row.get("vendor_identity_eligible_for_grouping"):
            eligible_vendor_rows += 1
        else:
            unresolved_vendor_rows += 1
        key = (row["report_document_id"], row["source_page"], row["source_table"], row["source_row"])
        assert key not in keys, key
        keys.add(key)

    assert exact_threshold_rows == meta.get("source_rows_at_exact_threshold"), (exact_threshold_rows, meta)
    assert exact_threshold_rows > 0, exact_threshold_rows
    assert unresolved_vendor_rows == meta.get("vendor_identity_unresolved_rows"), (unresolved_vendor_rows, meta)
    assert unresolved_vendor_rows > 0, unresolved_vendor_rows
    assert eligible_vendor_rows + unresolved_vendor_rows == len(rows)
    assert legacy_rows > 0, legacy_rows
    assert non_literal_alt_type_rows > 0, non_literal_alt_type_rows

    per_period = Counter(row["report_period"] for row in rows)
    value_per_period = defaultdict(float)
    for row in rows:
        value_per_period[row["report_period"]] += float(row["award_value"])
    for report in reports:
        period = report["report_period"]
        assert per_period[period] == report["alternative_count"], (period, per_period[period], report)
        assert abs(value_per_period[period] - report["parsed_alternative_value"]) <= 0.02, (period, value_per_period[period], report)

    print(
        "validated quarterly procurement: "
        f"{len(reports)} reports; {len(rows)} alternative rows; "
        f"{eligible_vendor_rows} grouping-eligible vendors; {unresolved_vendor_rows} unresolved vendor identities; "
        f"{changed_reports} live attachment replacement(s)"
    )


if __name__ == "__main__":
    main()
