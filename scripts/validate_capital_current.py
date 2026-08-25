#!/usr/bin/env python3
"""Independent structural/semantic validation for capital_current.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "data/generated/capital_current.json"
HISTORICAL = ROOT / "data/generated/capital.json"

CODE_RE = re.compile(r"^[A-Za-z0-9-]+$")
ANNUAL_KEYS = {"unspent_previous_budget", "2025_26", "2026_27", "2027_28", "2028_29"}
TOLERANCE = 2.0


def fail(message: str) -> None:
    raise SystemExit(f"current-capital validation failed: {message}")


def finite_or_none(value) -> bool:
    return value is None or (isinstance(value, (int, float)) and abs(value) < 50_000_000_000)


def n(value) -> float:
    return float(value or 0)


def close(left: float, right: float, tolerance: float = TOLERANCE) -> bool:
    return abs(left - right) <= tolerance


def main() -> None:
    if not CURRENT.exists():
        fail("capital_current.json missing")
    payload = json.loads(CURRENT.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    rows = payload.get("records") or []

    if meta.get("dataset_status") != "final_2025_26_capital_plan_project_extraction":
        fail("unexpected dataset status")
    if meta.get("parser_version") != "build008-capital-current-v2":
        fail("unexpected parser version")
    if meta.get("exact_join_only") is not True:
        fail("exact_join_only must be true")
    if len(rows) != meta.get("records") or len(rows) != meta.get("project_sheets_extracted"):
        fail("metadata record count mismatch")
    if len(rows) < 175:
        fail(f"only {len(rows)} project rows")
    if meta.get("project_marker_pages", 0) != len(rows):
        fail("each project-marker page must normalize to exactly one unique project sheet")
    if meta.get("missing_code_pages"):
        fail(f"project marker pages missing codes: {meta.get('missing_code_pages')}")

    codes = set()
    annual_count = 0
    project_cost_count = 0
    four_year_checks = 0
    total_cost_checks = 0
    work_plan_checks = 0

    for index, row in enumerate(rows):
        code = str(row.get("project_code") or "").strip()
        if not code or not CODE_RE.fullmatch(code):
            fail(f"row {index} invalid project code {code!r}")
        if code in codes:
            fail(f"duplicate project code {code}")
        codes.add(code)
        if row.get("source_id") != "hrm-capital-2025-26":
            fail(f"row {index} wrong source_id")
        if not isinstance(row.get("source_page"), int) or row["source_page"] < 1:
            fail(f"row {index} missing source page")
        provenance = row.get("provenance") or {}
        if provenance.get("source_id") != "hrm-capital-2025-26" or provenance.get("locator_value") != f"p{row['source_page']}":
            fail(f"row {index} provenance mismatch")

        annual = row.get("annual_budget")
        if annual is None or set(annual) != ANNUAL_KEYS:
            fail(f"row {index} annual budget structure missing/invalid")
        annual_count += 1
        if not all(finite_or_none(value) for value in annual.values()):
            fail(f"row {index} implausible annual budget")

        for collection_name in ["annual_funding", "operating_impacts"]:
            collection = row.get(collection_name) or {}
            for series_name, series in collection.items():
                if series is not None and not all(finite_or_none(value) for value in series.values()):
                    fail(f"row {index} implausible {collection_name}/{series_name}")

        for field in [
            "previously_approved_budget", "four_year_budget", "estimated_remaining_budget_required",
            "total_estimated_project_cost", "work_in_process_subtotal", "new_activities_subtotal", "total_work_2025_26",
        ]:
            if not finite_or_none(row.get(field)):
                fail(f"row {index} implausible {field}")

        four_year = row.get("four_year_budget")
        annual_four_year = sum(n(annual[key]) for key in ["2025_26", "2026_27", "2027_28", "2028_29"])
        if four_year is not None:
            four_year_checks += 1
            if not close(n(four_year), annual_four_year):
                fail(f"{code} four-year summary {four_year} != annual budget sum {annual_four_year}")
        elif annual_four_year and row.get("total_estimated_project_cost") is not None:
            # A detailed project cost summary with planned four-year spending must
            # publish the corresponding four-year summary amount.
            fail(f"{code} has annual four-year budget {annual_four_year} but missing four_year_budget summary")

        total_cost = row.get("total_estimated_project_cost")
        if total_cost is not None:
            project_cost_count += 1
            total_cost_checks += 1
            components = n(row.get("previously_approved_budget")) + n(row.get("four_year_budget")) + n(row.get("estimated_remaining_budget_required"))
            if not close(n(total_cost), components):
                fail(f"{code} total project cost {total_cost} != source summary components {components}")

        total_work = row.get("total_work_2025_26")
        if total_work is not None:
            work_plan_checks += 1
            expected_work = n(annual.get("unspent_previous_budget")) + n(annual.get("2025_26"))
            if not close(n(total_work), expected_work):
                fail(f"{code} 2025/26 work plan total {total_work} != unspent + 2025/26 gross budget {expected_work}")

    historical_codes = {}
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    for row in historical.get("records", []):
        code = str(row.get("project_code") or "").strip()
        if code:
            historical_codes.setdefault(code, []).append(str(row.get("project_id") or "").strip())

    exact_match_count = 0
    for row in rows:
        expected_ids = historical_codes.get(row["project_code"], [])
        if bool(expected_ids) != bool(row.get("historical_exact_match")):
            fail(f"historical exact-match flag wrong for {row['project_code']}")
        if sorted(expected_ids) != sorted(row.get("historical_project_object_ids") or []):
            fail(f"historical object IDs wrong for {row['project_code']}")
        exact_match_count += int(bool(expected_ids))

    if exact_match_count != meta.get("historical_exact_project_code_matches"):
        fail("historical exact-match metadata count mismatch")
    if annual_count != meta.get("annual_budget_rows"):
        fail("annual-budget metadata count mismatch")
    if project_cost_count != meta.get("project_cost_summary_rows"):
        fail("project-cost-summary metadata count mismatch")
    if project_cost_count < 100:
        fail(f"only {project_cost_count} project sheets publish a validated total-project-cost summary")
    if four_year_checks < 100 or total_cost_checks < 100 or work_plan_checks < 150:
        fail(f"insufficient arithmetic coverage: four_year={four_year_checks}, total_cost={total_cost_checks}, work_plan={work_plan_checks}")

    print(
        f"Current capital validated: {len(rows)} projects; annual={annual_count}; project_cost={project_cost_count}; "
        f"four_year_checks={four_year_checks}; total_cost_checks={total_cost_checks}; work_plan_checks={work_plan_checks}; "
        f"historical_exact={exact_match_count}"
    )


if __name__ == "__main__":
    main()
