#!/usr/bin/env python3
"""Independent validation for 2025/26 capital category actuals/projections."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data/generated/capital_actuals_current.json"
EXPECTED = {
    "Q1": {"actual": 60_200_000, "projected": 421_800_000, "wip": 198_700_000},
    "Q2": {"actual": 147_800_000, "projected": 349_100_000, "wip": 219_900_000},
    "Q3": {"actual": 255_400_000, "projected": 109_300_000, "wip": 343_100_000},
}
REQUIRED_QUARTERS = {"Q1", "Q2"}
ROUNDING_TOLERANCE = 100_000
ARITHMETIC_TOLERANCE = 2


def fail(message: str) -> None:
    raise SystemExit(f"current-capital-actuals validation failed: {message}")


def n(value) -> float:
    return float(value or 0)


def main() -> None:
    if not PATH.exists():
        fail("artifact missing")
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    rows = payload.get("records") or []
    if meta.get("dataset_status") != "official_2025_26_capital_projection_summaries":
        fail("unexpected dataset status")
    if meta.get("parser_version") != "build008-capital-actuals-v2":
        fail("unexpected parser version")
    if meta.get("granularity") != "asset_category_summary_not_project_actuals":
        fail("granularity boundary missing")
    if meta.get("project_level_actuals_available") is not False:
        fail("project-level actuals must remain false")
    if len(rows) != meta.get("records") or meta.get("source_count_configured") != 3:
        fail("metadata counts do not match")
    if any("project_code" in row or "vendor_name" in row for row in rows):
        fail("category actuals artifact contains unsupported project/vendor fields")

    quarters: dict[str, list[dict]] = {}
    for index, row in enumerate(rows):
        if row.get("granularity") != "capital_asset_category_summary":
            fail(f"row {index} wrong granularity")
        q = row.get("quarter")
        if q not in EXPECTED:
            fail(f"row {index} unexpected quarter {q!r}")
        quarters.setdefault(q, []).append(row)
        if row.get("fiscal_year") != "2025/26" or not row.get("budget_category"):
            fail(f"row {index} missing fiscal/category identity")
        if not row.get("source_id") or not isinstance(row.get("source_page"), int):
            fail(f"row {index} missing source provenance")
        prov = row.get("provenance") or {}
        if prov.get("source_id") != row.get("source_id") or prov.get("parser_version") != "build008-capital-actuals-v2":
            fail(f"row {index} provenance mismatch")

        available_expected = n(row.get("budget_remaining_at_prior_year_end")) + n(row.get("budget_2025_26")) + n(row.get("budget_increases_decreases"))
        if abs(n(row.get("budget_available_at_period_end")) - available_expected) > ARITHMETIC_TOLERANCE:
            fail(f"row {index} budget-available arithmetic mismatch")
        exp_commit_expected = n(row.get("ytd_expenditures")) + n(row.get("ytd_commitments"))
        if abs(n(row.get("ytd_expenditures_and_commitments")) - exp_commit_expected) > ARITHMETIC_TOLERANCE:
            fail(f"row {index} expenditure/commitment arithmetic mismatch")

    if not REQUIRED_QUARTERS.issubset(quarters):
        fail(f"required quarter coverage missing: {sorted(set(REQUIRED_QUARTERS) - set(quarters))}")
    if sorted(quarters) != sorted(meta.get("materialized_quarters") or []):
        fail("materialized_quarters metadata mismatch")
    if len(quarters) != meta.get("source_count_materialized"):
        fail("source_count_materialized metadata mismatch")

    statuses = {item.get("quarter"): item for item in (meta.get("source_status") or [])}
    if set(statuses) != set(EXPECTED):
        fail(f"source-status quarter coverage mismatch: {sorted(statuses)}")
    for quarter in REQUIRED_QUARTERS:
        if statuses[quarter].get("status") != "ok":
            fail(f"required {quarter} source is not ok")

    previous_actual = -1.0
    for quarter in [q for q in ["Q1", "Q2", "Q3"] if q in quarters]:
        qrows = quarters[quarter]
        if len(qrows) != 10:
            fail(f"{quarter} must contain 9 categories + GRAND TOTAL, found {len(qrows)}")
        totals = [row for row in qrows if row["budget_category"].casefold() == "grand total"]
        if len(totals) != 1:
            fail(f"{quarter} must have exactly one GRAND TOTAL, found {len(totals)}")
        total = totals[0]
        expected = EXPECTED[quarter]
        actual = n(total.get("ytd_expenditures"))
        projected = n(total.get("projected_spend_remaining_2025_26"))
        wip = n(total.get("projected_work_in_progress_2026_27"))
        for label, observed, target in [("actual", actual, expected["actual"]), ("projected", projected, expected["projected"]), ("wip", wip, expected["wip"])]:
            if abs(observed - target) > ROUNDING_TOLERANCE:
                fail(f"{quarter} {label} {observed} does not reconcile to narrative {target}")
        if actual <= previous_actual:
            fail(f"YTD actual expenditures are not increasing through {quarter}")
        previous_actual = actual

    if "Q3" not in quarters:
        q3_status = statuses["Q3"]
        if q3_status.get("status") != "source_access_error" or q3_status.get("records") != 0:
            fail("unmaterialized Q3 must be explicit source_access_error with zero rows")
        # The known narrative values are retained only as source-status context;
        # they must not appear as normalized data rows without the source table.
        if q3_status.get("narrative_actual_expenditures") != EXPECTED["Q3"]["actual"]:
            fail("Q3 source-status narrative context changed unexpectedly")

    print(
        "Current capital actuals validated: "
        + ", ".join(f"{q}={len(quarters[q])} rows" for q in sorted(quarters))
        + ("; Q3 source access blocked, no rows fabricated" if "Q3" not in quarters else "; Q3 materialized")
    )


if __name__ == "__main__":
    main()
