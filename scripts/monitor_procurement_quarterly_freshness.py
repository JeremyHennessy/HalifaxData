#!/usr/bin/env python3
"""Compare live quarterly-procurement discovery with the checked evidence artifact.

The checked artifact intentionally preserves historical eSCRIBE document identity. A live
agenda may later expose the same report under a replacement DocumentId. This monitor
therefore treats report-period/count/value semantics as the stable evidence contract and
records source-identity relocation separately. It never publishes the live artifact and
never interprets awards as payments or final paid values.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

EXPECTED_STATUS = "official_quarterly_alternative_procurement_report_sections"
ALLOWED_SCHEMAS = {"legacy_alternative_awards_table", "modern_dedicated_alternative_table"}
ALLOWED_RESOLUTION = {"checked_in_graph_url_live", "exact_title_live_agenda_resolution"}
TOLERANCE = 0.02


def load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: expected JSON object")
    return payload


def close(a: object, b: object) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return math.isclose(float(a), float(b), abs_tol=TOLERANCE)
    except (TypeError, ValueError):
        return False


def report_map(payload: dict, label: str, errors: list[str]) -> dict[str, dict]:
    reports = payload.get("reports")
    if not isinstance(reports, list) or not reports:
        errors.append(f"{label}: reports must be a non-empty list")
        return {}
    result: dict[str, dict] = {}
    for index, report in enumerate(reports):
        period = str(report.get("report_period") or "").strip()
        if not period:
            errors.append(f"{label}: report {index} has blank report_period")
            continue
        if period in result:
            errors.append(f"{label}: duplicate report_period {period!r}")
            continue
        result[period] = report
    return result


def validate_live(payload: dict, errors: list[str]) -> None:
    meta = payload.get("metadata") or {}
    reports = payload.get("reports") or []
    rows = payload.get("alternative_procurement") or []

    if meta.get("dataset_status") != EXPECTED_STATUS:
        errors.append(f"live: dataset_status {meta.get('dataset_status')!r} != {EXPECTED_STATUS!r}")
    if meta.get("is_accounts_payable_ledger") is not False:
        errors.append("live: is_accounts_payable_ledger must remain false")
    if meta.get("is_complete_procurement_ledger") is not False:
        errors.append("live: is_complete_procurement_ledger must remain false")
    if meta.get("is_final_paid_value") is not False:
        errors.append("live: is_final_paid_value must remain false")
    if meta.get("report_count") != len(reports):
        errors.append(f"live: metadata report_count {meta.get('report_count')} != {len(reports)}")
    if meta.get("alternative_procurement_rows") != len(rows):
        errors.append(
            f"live: metadata alternative_procurement_rows {meta.get('alternative_procurement_rows')} != {len(rows)}"
        )

    by_period = Counter(str(row.get("report_period") or "") for row in rows)
    value_by_period: dict[str, float] = {}
    for row in rows:
        period = str(row.get("report_period") or "")
        value = row.get("award_value")
        if not period:
            errors.append("live row has blank report_period")
        if row.get("procurement_class") != "reported_alternative_procurement_section":
            errors.append(f"live row {period!r}: unexpected procurement_class")
        if row.get("source_report_section") != "alternative_procurement_over_50000":
            errors.append(f"live row {period!r}: unexpected source_report_section")
        if row.get("source_id") != "hrm-escribe":
            errors.append(f"live row {period!r}: unexpected source_id {row.get('source_id')!r}")
        if row.get("source_schema") not in ALLOWED_SCHEMAS:
            errors.append(f"live row {period!r}: unexpected source_schema {row.get('source_schema')!r}")
        if row.get("source_url_resolution") not in ALLOWED_RESOLUTION:
            errors.append(f"live row {period!r}: unexpected source_url_resolution")
        if value is None or float(value) < 50_000:
            errors.append(f"live row {period!r}: award_value below report threshold or missing: {value!r}")
        else:
            value_by_period[period] = value_by_period.get(period, 0.0) + float(value)

    for report in reports:
        period = str(report.get("report_period") or "")
        count = report.get("alternative_count")
        parsed_count = report.get("parsed_alternative_rows")
        published_value = report.get("alternative_value")
        parsed_value = report.get("parsed_alternative_value")
        if report.get("source_id") != "hrm-escribe":
            errors.append(f"live report {period!r}: unexpected source_id {report.get('source_id')!r}")
        if report.get("source_schema") not in ALLOWED_SCHEMAS:
            errors.append(f"live report {period!r}: unexpected source_schema {report.get('source_schema')!r}")
        if report.get("source_url_resolution") not in ALLOWED_RESOLUTION:
            errors.append(f"live report {period!r}: unexpected source_url_resolution")
        if not report.get("document_id") or not report.get("url") or not report.get("agenda_url"):
            errors.append(f"live report {period!r}: source identity is incomplete")
        if count != parsed_count or count != by_period.get(period, 0):
            errors.append(
                f"live report {period!r}: count mismatch published={count!r} parsed={parsed_count!r} rows={by_period.get(period, 0)}"
            )
        if report.get("control_count_reconciled") is not True:
            errors.append(f"live report {period!r}: count control did not reconcile")
        if parsed_value is None or not close(parsed_value, value_by_period.get(period, 0.0)):
            errors.append(
                f"live report {period!r}: parsed value {parsed_value!r} != row sum {value_by_period.get(period, 0.0)!r}"
            )
        if published_value is not None:
            if not close(parsed_value, published_value):
                errors.append(
                    f"live report {period!r}: parsed value {parsed_value!r} != published control {published_value!r}"
                )
            if report.get("control_value_reconciled") is not True:
                errors.append(f"live report {period!r}: value control did not reconcile")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checked", type=Path, required=True)
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    checked = load(args.checked)
    live = load(args.live)
    errors: list[str] = []
    validate_live(live, errors)
    checked_by_period = report_map(checked, "checked", errors)
    live_by_period = report_map(live, "live", errors)

    missing_periods = sorted(set(checked_by_period) - set(live_by_period))
    new_periods = sorted(set(live_by_period) - set(checked_by_period))
    if missing_periods:
        errors.append(f"live discovery is missing checked report periods: {missing_periods}")

    semantic_changes: list[dict] = []
    source_identity_changes: list[dict] = []
    for period in sorted(set(checked_by_period) & set(live_by_period)):
        old = checked_by_period[period]
        new = live_by_period[period]
        comparisons = {
            "alternative_count": old.get("alternative_count") == new.get("alternative_count"),
            "parsed_alternative_rows": old.get("parsed_alternative_rows") == new.get("parsed_alternative_rows"),
            "alternative_value": close(old.get("alternative_value"), new.get("alternative_value")),
            "parsed_alternative_value": close(old.get("parsed_alternative_value"), new.get("parsed_alternative_value")),
            "source_schema": old.get("source_schema") == new.get("source_schema"),
        }
        if not all(comparisons.values()):
            semantic_changes.append({
                "report_period": period,
                "comparisons": comparisons,
                "checked": {
                    "alternative_count": old.get("alternative_count"),
                    "alternative_value": old.get("alternative_value"),
                    "parsed_alternative_rows": old.get("parsed_alternative_rows"),
                    "parsed_alternative_value": old.get("parsed_alternative_value"),
                    "source_schema": old.get("source_schema"),
                },
                "live": {
                    "alternative_count": new.get("alternative_count"),
                    "alternative_value": new.get("alternative_value"),
                    "parsed_alternative_rows": new.get("parsed_alternative_rows"),
                    "parsed_alternative_value": new.get("parsed_alternative_value"),
                    "source_schema": new.get("source_schema"),
                },
            })
        checked_identity = {
            "document_id": old.get("document_id"),
            "source_url_registry": old.get("source_url_registry") or old.get("url"),
            "source_url_resolved": old.get("source_url_resolved") or old.get("url"),
        }
        live_identity = {
            "document_id": new.get("document_id"),
            "source_url_registry": new.get("source_url_registry") or new.get("url"),
            "source_url_resolved": new.get("source_url_resolved") or new.get("url"),
        }
        if checked_identity != live_identity:
            source_identity_changes.append({
                "report_period": period,
                "checked": checked_identity,
                "live": live_identity,
            })

    if semantic_changes:
        errors.append(f"{len(semantic_changes)} checked report period(s) changed semantic controls")

    summary = {
        "checked_report_count": len(checked_by_period),
        "live_report_count": len(live_by_period),
        "checked_rows": len(checked.get("alternative_procurement") or []),
        "live_rows": len(live.get("alternative_procurement") or []),
        "new_report_periods": new_periods,
        "missing_checked_report_periods": missing_periods,
        "source_identity_changes": source_identity_changes,
        "semantic_changes": semantic_changes,
        "errors": errors,
        "interpretation": (
            "Source identity changes are evidence of eSCRIBE document relocation/replacement and do not rewrite historical provenance. "
            "New report periods are freshness candidates only. Awards are not payments, invoices, or final paid values."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if errors:
        print("QUARTERLY PROCUREMENT FRESHNESS MONITOR FAILED", file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
