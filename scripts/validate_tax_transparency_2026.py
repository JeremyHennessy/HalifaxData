#!/usr/bin/env python3
"""Validate Build 020 tax-transparency parameters and deterministic calculations."""
from __future__ import annotations

import json
import math
from decimal import Decimal
from pathlib import Path

from tax_transparency_2026 import (
    DEFAULT_CONTRACT,
    D,
    federal_bpa,
    halifax_property_tax,
    load_contract,
    salary_breakdown,
)

ROOT = Path(__file__).resolve().parents[1]


def close(actual: float, expected: float, tolerance: float = 0.011) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_contract(contract: dict) -> None:
    metadata = contract.get("metadata") or {}
    require(metadata.get("build") == "020", "tax contract must be Build 020")
    require(
        "does not levy municipal personal income tax" in metadata.get("municipal_semantics", ""),
        "municipal semantics must explicitly reject a Halifax personal-income-tax interpretation",
    )
    require(
        "do not trace" in metadata.get("allocation_semantics", ""),
        "allocation semantics must reject transaction tracing",
    )

    sources = contract.get("sources") or []
    source_ids = {row.get("id") for row in sources}
    required_sources = {
        "cra-t4032ns-2026",
        "cra-t4127-2026",
        "canada-spring-update-2026",
        "ns-budget-2026-27-expense-shares",
        "hrm-budget-ratification-2026-03-31",
        "hrm-budget-resolution-2026-27",
        "hrm-budget-rate-presentation-2026-27",
    }
    require(required_sources.issubset(source_ids), f"missing authoritative sources: {sorted(required_sources - source_ids)}")
    for row in sources:
        require(str(row.get("url") or "").startswith("https://"), f"source {row.get('id')} has no HTTPS URL")
        require(row.get("authority"), f"source {row.get('id')} missing authority")
        require(row.get("supports"), f"source {row.get('id')} missing supports list")

    salary = contract.get("salary_tax") or {}
    require(salary.get("tax_year") == 2026, "salary contract tax year must be 2026")
    require(salary.get("province") == "NS", "salary contract must be Nova Scotia")

    federal = salary["federal"]
    require(federal["brackets"][-1]["upper"] is None, "federal brackets need open terminal bracket")
    require([row["rate"] for row in federal["brackets"]] == [0.14, 0.205, 0.26, 0.29, 0.33], "unexpected federal rates")
    require(federal["canada_employment_amount"] == 1501, "unexpected Canada employment amount")
    require(federal["basic_personal_amount"]["maximum"] == 16452, "unexpected maximum federal BPA")
    require(federal["basic_personal_amount"]["minimum"] == 14829, "unexpected minimum federal BPA")

    province = salary["nova_scotia"]
    require(province["brackets"][-1]["upper"] is None, "Nova Scotia brackets need open terminal bracket")
    require(
        [row["rate"] for row in province["brackets"]] == [0.0879, 0.1495, 0.1667, 0.175, 0.21],
        "unexpected Nova Scotia rates",
    )
    require(province["basic_personal_amount"] == 11932, "unexpected Nova Scotia BPA")

    cpp = salary["cpp"]
    require(cpp["ympe"] == 74600 and cpp["yampe"] == 85000, "unexpected CPP earnings limits")
    require(close(cpp["combined_max"], 4230.45), "unexpected CPP maximum")
    require(close(cpp["cpp2_max"], 416.00), "unexpected CPP2 maximum")
    ei = salary["ei"]
    require(ei["max_insurable_earnings"] == 68900, "unexpected EI maximum insurable earnings")
    require(close(ei["employee_max"], 1123.07), "unexpected EI maximum")

    federal_allocation = contract["federal_spending_allocation"]
    top_total = sum(D(row["amount_billion"]) for row in federal_allocation["categories"])
    require(top_total == D(federal_allocation["denominator_billion"]), "federal top-level expense categories do not reconcile")

    ns_allocation = contract["nova_scotia_spending_allocation"]
    ns_share_total = sum(D(row["share_pct"]) for row in ns_allocation["categories"])
    require(D("99") <= ns_share_total <= D("101"), f"Nova Scotia source-rounded expense shares are implausible: {ns_share_total}")
    require(
        ns_allocation.get("source_rounding_note"),
        "Nova Scotia rounded share contract must disclose source rounding",
    )

    municipal = contract["halifax_property_tax"]
    require(municipal["status"] == "adopted_by_regional_council_2026-03-31", "HRM rates must be adopted, not proposed")
    require(municipal["rate_unit"] == "dollars_per_100_taxable_assessment", "unexpected HRM rate unit")
    require(municipal["general_rates"] == {"urban": 0.687, "suburban": 0.654, "rural": 0.654}, "unexpected HRM general rates")


def validate_examples(contract: dict) -> None:
    controls = contract["validation_controls"]["salary_examples"]
    for expected in controls:
        result = salary_breakdown(expected["salary"], contract)
        checks = {
            "federal_income_tax": result["income_tax"]["federal"],
            "nova_scotia_income_tax": result["income_tax"]["nova_scotia"],
            "cpp": result["statutory_contributions"]["cpp"],
            "cpp2": result["statutory_contributions"]["cpp2"],
            "ei": result["statutory_contributions"]["ei"],
            "take_home": result["take_home"],
        }
        for field, actual in checks.items():
            require(
                close(actual, expected[field]),
                f"salary {expected['salary']}: {field} {actual} != control {expected[field]}",
            )

        require(result["gross_salary"] >= result["take_home"] >= 0, f"salary {expected['salary']}: invalid take-home")
        require(result["income_tax"]["total"] >= 0, f"salary {expected['salary']}: negative income tax")
        require(result["statutory_contributions"]["total"] >= 0, f"salary {expected['salary']}: negative contributions")
        require(abs(result["display_rounding_adjustment"]) <= 0.01, f"salary {expected['salary']}: excessive display rounding adjustment")

        federal_share = sum(row["share"] for row in result["federal_spending_allocation"])
        ns_share = sum(row["share"] for row in result["nova_scotia_spending_allocation"])
        require(math.isclose(federal_share, 1.0, abs_tol=1e-12), f"salary {expected['salary']}: federal allocation shares do not sum to 1")
        require(math.isclose(ns_share, 1.0, abs_tol=1e-12), f"salary {expected['salary']}: Nova Scotia normalized allocation shares do not sum to 1")

    zero = salary_breakdown(0, contract)
    require(zero["total_deductions"] == 0 and zero["take_home"] == 0, "zero salary must produce zero deductions")

    # Federal BPA must be monotonic through the legislated phase-down window.
    start = federal_bpa(D("181440"), contract)
    middle = federal_bpa(D("220000"), contract)
    end = federal_bpa(D("258482"), contract)
    require(start == D("16452"), "federal BPA phase-down start incorrect")
    require(D("14829") < middle < D("16452"), "federal BPA middle point is outside the phase-down range")
    require(end == D("14829"), "federal BPA phase-down end incorrect")


def validate_property_tax(contract: dict) -> None:
    municipal = contract["halifax_property_tax"]
    example = municipal["average_urban_example"]
    result = halifax_property_tax(
        example["assessment"],
        "urban",
        local_transit=True,
        strategic_infrastructure_and_climate=True,
        contract=contract,
    )
    require(close(result["combined_rate_per_100"], example["combined_rate"], tolerance=1e-12), "HRM example combined rate mismatch")
    require(close(result["municipal_tax"], example["municipal_tax"]), "HRM example municipal tax mismatch")

    base_only = halifax_property_tax(100000, "urban", contract=contract)
    require(close(base_only["municipal_tax"], 687.00), "urban base-rate calculation mismatch")
    rural = halifax_property_tax(100000, "rural", contract=contract)
    require(close(rural["municipal_tax"], 654.00), "rural base-rate calculation mismatch")


def validate_bad_inputs(contract: dict) -> None:
    for value in (-1, float("inf"), float("nan")):
        try:
            salary_breakdown(value, contract)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid salary input was accepted: {value!r}")
    try:
        halifax_property_tax(100000, "unknown", contract=contract)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown HRM tax area was accepted")


def main() -> None:
    contract = load_contract(DEFAULT_CONTRACT)
    validate_contract(contract)
    validate_examples(contract)
    validate_property_tax(contract)
    validate_bad_inputs(contract)
    print(
        "validated Build 020 tax transparency: CRA 2026 salary deductions, "
        "federal/NS proportional expense allocations, and separate HRM property-tax rates"
    )


if __name__ == "__main__":
    main()
