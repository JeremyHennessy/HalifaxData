#!/usr/bin/env python3
"""Validate Build 011 quarterly Alternative Procurement evidence fail-closed."""
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

    assert meta.get("dataset_status") == "official_quarterly_award_reports", meta
    assert meta.get("parser_version") == "build011-procurement-quarterly-v1", meta
    assert meta.get("alternative_reporting_threshold") == 50000, meta
    assert meta.get("is_accounts_payable_ledger") is False, meta
    assert meta.get("is_complete_procurement_ledger") is False, meta
    assert len(reports) >= 8, len(reports)
    assert len(rows) >= 40, len(rows)
    assert meta.get("report_count") == len(reports), meta
    assert meta.get("alternative_procurement_rows") == len(rows), meta
    assert round(meta.get("alternative_procurement_value", 0), 2) == round(sum(row["award_value"] for row in rows), 2)

    periods = [row.get("report_period") for row in reports]
    assert all(periods), periods
    assert len(periods) == len(set(periods)), periods

    controlled_counts = 0
    controlled_values = 0
    for report in reports:
        parsed_count = report.get("parsed_alternative_rows")
        parsed_value = report.get("parsed_alternative_value")
        control_count = report.get("alternative_count")
        control_value = report.get("alternative_value")
        assert parsed_count and parsed_count > 0, report
        if control_count is not None:
            controlled_counts += 1
            assert parsed_count == control_count, report
        if control_value is not None:
            controlled_values += 1
            assert abs(parsed_value - control_value) <= 0.02, report
    assert controlled_counts >= 8, controlled_counts
    assert controlled_values >= 4, controlled_values

    jan_mar_2025 = next((row for row in reports if "January 2025 to March 2025" in row.get("report_period", "")), None)
    assert jan_mar_2025, periods
    assert jan_mar_2025.get("alternative_count") == 12, jan_mar_2025
    assert jan_mar_2025.get("parsed_alternative_rows") == 12, jan_mar_2025

    apr_jun_2025 = next((row for row in reports if "April 2025 to June 2025" in row.get("report_period", "")), None)
    assert apr_jun_2025, periods
    assert apr_jun_2025.get("alternative_count") == 17, apr_jun_2025
    assert abs((apr_jun_2025.get("alternative_value") or 0) - 3_395_725.58) <= 0.02, apr_jun_2025
    assert apr_jun_2025.get("parsed_alternative_rows") == 17, apr_jun_2025
    assert abs(apr_jun_2025.get("parsed_alternative_value", 0) - 3_395_725.58) <= 0.02, apr_jun_2025

    keys = set()
    for row in rows:
        assert row.get("procurement_class") == "alternative_procurement", row
        assert row.get("source_id") == "hrm-escribe", row
        assert row.get("report_document_id"), row
        assert row.get("report_period"), row
        assert row.get("award_title"), row
        assert row.get("vendor_name"), row
        assert row.get("award_value") is not None and row["award_value"] > 50000, row
        assert row.get("source_url"), row
        assert row.get("source_page"), row
        key = (row["report_document_id"], row["award_title"], row["vendor_name"], row["award_value"])
        assert key not in keys, key
        keys.add(key)

    blob = json.dumps(payload).lower()
    for forbidden in ["invoice amount", "accounts payable transaction", "payment date", "final paid value"]:
        assert forbidden not in blob, forbidden

    print(
        f"validated {len(rows)} source-declared Alternative Procurement awards across {len(reports)} quarterly reports; "
        f"{controlled_counts} report count controls and {controlled_values} report value controls reconciled"
    )


if __name__ == "__main__":
    main()
