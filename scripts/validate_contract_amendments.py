#!/usr/bin/env python3
"""Validate Build 014 public CAO contract-amendment series controls."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DEFAULT = Path("data/generated/contract_amendments.json")
SOURCES = Path("data/contract_amendment_sources.json")
EXPECTED_DATES = [
    "2023-05-17", "2023-09-20", "2023-11-15", "2024-01-17",
    "2024-06-19", "2024-10-09", "2024-12-11", "2025-01-15",
    "2025-04-16", "2025-05-21", "2025-06-18", "2025-11-25",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def close(actual: float, expected: float, tolerance: float = 0.02) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=tolerance)


def main(path: Path) -> None:
    source_doc = json.loads(SOURCES.read_text(encoding="utf-8"))
    sources = source_doc["sources"]
    require(len(sources) == 12, "Build 014 source registry must contain exactly 12 identified public reports")
    require([row["report_date"] for row in sources] == EXPECTED_DATES, "Build 014 source dates changed")
    require(len({row["id"] for row in sources}) == 12, "Duplicate Build 014 source IDs")
    require(len({row["url"] for row in sources}) == 12, "Duplicate Build 014 source URLs")
    require(all(row["url"].startswith("https://cdn.halifax.ca/") for row in sources), "Build 014 sources must remain official HRM CDN PDFs")

    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data["metadata"]
    summary = data["summary"]
    require(meta["dataset_status"] == "official_public_cao_contract_amendment_series", "Unexpected Build 014 dataset status")
    require(meta["identified_public_report_count"] == 12, "Build 014 report-count boundary changed")
    require(meta["coverage_start"] == EXPECTED_DATES[0] and meta["coverage_end"] == EXPECTED_DATES[-1], "Build 014 date coverage changed")
    require(meta["is_complete_contract_amendment_ledger"] is False, "Build 014 must not claim a complete amendment ledger")
    require(meta["is_transaction_ledger"] is False, "Build 014 must not claim transaction coverage")
    require(meta["is_accounts_payable_ledger"] is False, "Build 014 must not claim AP coverage")
    require(meta["is_final_paid_value_data"] is False, "Build 014 must not claim final paid values")
    require(meta["creates_wrongdoing_assertions"] is False, "Build 014 must not create wrongdoing assertions")
    require(meta["vendor_aliases_auto_merged"] is False, "Build 014 must not auto-merge vendor aliases")
    require(meta["fuzzy_contract_links_created"] is False, "Build 014 must not create fuzzy contract links")

    reports = data["reports"]
    require(len(reports) == 12, "Expected 12 Build 014 report controls")
    require([row["report_date"] for row in reports] == EXPECTED_DATES, "Build 014 report ordering changed")
    require(all(row["status"] == "ready" for row in reports), "Every identified Build 014 report must reproduce at least one public aggregate-table observation")
    require(all(int(row.get("http_status") or 0) == 200 for row in reports), "Every reproduced Build 014 source must return HTTP 200")
    require(all(int(row.get("observation_count") or 0) > 0 for row in reports), "Every Build 014 report must have observations")
    require(summary["ready_report_count"] == 12, "Build 014 ready-report count changed")

    observations = data["observations"]
    require(len(observations) == summary["observation_count"], "Build 014 observation summary mismatch")
    require(len(observations) >= 58, "Build 014 lost observations from the verified source-table diagnostic")
    ids = [row["id"] for row in observations]
    require(len(ids) == len(set(ids)), "Duplicate Build 014 observation IDs")
    require(all(row["is_invoice_or_payment"] is False for row in observations), "Amendment rows must not become invoice/payment records")
    require(all(row["is_final_paid_value"] is False for row in observations), "Amendment rows must not become final-paid-value records")
    require(all(row["creates_wrongdoing_assertion"] is False for row in observations), "Amendment rows must not assert wrongdoing")

    by_date = {date: [row for row in observations if row["report_date"] == date] for date in EXPECTED_DATES}
    require(len(by_date["2023-05-17"]) >= 2, "May 2023 legacy table extraction changed")
    require(all(row["source_schema"] == "original_updated_total_to_date" for row in by_date["2023-05-17"]), "May 2023 legacy amount semantics changed")
    require(all(row["amendment_value_source"] is None for row in by_date["2023-05-17"]), "May 2023 must not fabricate a source-published amendment value")
    require(len(by_date["2025-11-25"]) >= 11, "November 2025 cumulative-table extraction changed")
    require(all(row["source_schema"] == "original_cumulative_amendment" for row in by_date["2025-11-25"]), "November 2025 cumulative amount semantics changed")
    require(all(row["updated_value_source"] is None for row in by_date["2025-11-25"]), "November 2025 must not fabricate a source-published updated value")

    slayter = next((row for row in observations if row.get("po") == "2070887247" and row["report_date"] == "2023-11-15"), None)
    require(slayter is not None, "Missing Slayter Street source-control row")
    require(close(slayter["source_arithmetic_delta"], -180), "Slayter Street $180 source arithmetic discrepancy changed")
    require(slayter["source_arithmetic_consistent"] is False, "Slayter Street discrepancy must remain explicitly flagged")

    west_bedford = next((row for row in observations if row.get("po") == "2070837342" and row["report_date"] == "2023-09-20"), None)
    require(west_bedford is not None and close(west_bedford["source_arithmetic_delta"], -30000), "West Bedford $30,000 source arithmetic discrepancy changed")
    fire_boat = next((row for row in observations if row.get("po") == "2070920062" and row["report_date"] == "2025-04-16"), None)
    require(fire_boat is not None and close(fire_boat["source_arithmetic_delta"], -1), "Fire Boat $1 source arithmetic discrepancy changed")
    require(summary["source_arithmetic_flags"] >= 3, "Expected source arithmetic flags were lost")

    trajectories = data["trajectories"]
    require(summary["recurring_exact_contract_keys"] == len(trajectories), "Recurring-contract summary mismatch")
    contract_21302 = next((row for row in trajectories if row["contract_key"] == "contract:21-302"), None)
    require(contract_21302 is not None, "Exact Contract 21-302 longitudinal trajectory missing")
    require(contract_21302["first_report_date"] == "2023-11-15" and contract_21302["last_report_date"] == "2025-05-21", "Contract 21-302 report span changed")
    require(contract_21302["report_count"] == 2, "Contract 21-302 should be linked across exactly two identified public reports")
    require(close(contract_21302["first_original_value"], 185204), "Contract 21-302 original-value control changed")
    require(close(contract_21302["latest_effective_cumulative_amendment_value"], 58120), "Contract 21-302 latest cumulative amendment control changed")
    require(close(contract_21302["steps"][0]["published_cumulative_amendment_delta"], 23216), "Contract 21-302 longitudinal cumulative-amendment movement changed")

    print(json.dumps({
        "status": "ok",
        "reports": len(reports),
        "observations": len(observations),
        "unique_contract_keys": summary["unique_contract_keys"],
        "recurring_exact_contract_keys": summary["recurring_exact_contract_keys"],
        "source_arithmetic_flags": summary["source_arithmetic_flags"],
        "contract_21_302_delta": contract_21302["steps"][0]["published_cumulative_amendment_delta"],
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT)
    args = parser.parse_args()
    main(args.path)
