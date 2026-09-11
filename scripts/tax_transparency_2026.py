#!/usr/bin/env python3
"""Deterministic 2026 Nova Scotia tax-transparency calculations.

This module intentionally separates:

* federal and Nova Scotia personal income tax;
* CPP/CPP2 and EI statutory contributions; and
* Halifax municipal property tax.

It does not create a municipal income tax and it does not claim that an individual's
remittance can be transaction-traced to specific government expenditures.
"""
from __future__ import annotations

import argparse
import json
import math
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "data/tax_transparency_2026.json"
CENT = Decimal("0.01")
ZERO = Decimal("0")
getcontext().prec = 32


def D(value: Any) -> Decimal:
    return Decimal(str(value))


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def money_float(value: Decimal) -> float:
    return float(money(value))


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_nonnegative_number(value: Any, name: str) -> Decimal:
    try:
        number = D(value)
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        raise ValueError(f"{name} must be numeric") from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return number


def bracket_tax(taxable_income: Decimal, brackets: list[dict]) -> Decimal:
    for row in brackets:
        upper = row.get("upper")
        if upper is None or taxable_income <= D(upper):
            return taxable_income * D(row["rate"]) - D(row["constant"])
    raise ValueError("tax bracket contract has no open-ended terminal bracket")


def federal_bpa(net_income: Decimal, contract: dict) -> Decimal:
    bpa = contract["salary_tax"]["federal"]["basic_personal_amount"]
    maximum = D(bpa["maximum"])
    minimum = D(bpa["minimum"])
    start = D(bpa["phase_down_start"])
    end = D(bpa["phase_down_end"])
    phase_amount = D(bpa["phase_down_amount"])
    if net_income <= start:
        return maximum
    if net_income >= end:
        return minimum
    return maximum - (net_income - start) * phase_amount / (end - start)


def cpp_components(salary: Decimal, contract: dict) -> dict[str, Decimal]:
    cpp = contract["salary_tax"]["cpp"]
    exemption = D(cpp["basic_exemption"])
    combined = min(
        max(salary - exemption, ZERO) * D(cpp["combined_rate"]),
        D(cpp["combined_max"]),
    )
    base = combined * D(cpp["base_rate"]) / D(cpp["combined_rate"])
    first_additional = combined - base
    cpp2 = min(
        max(salary - D(cpp["ympe"]), ZERO) * D(cpp["cpp2_rate"]),
        D(cpp["cpp2_max"]),
    )
    return {
        "combined": combined,
        "base": base,
        "first_additional": first_additional,
        "cpp2": cpp2,
    }


def ei_contribution(salary: Decimal, contract: dict) -> Decimal:
    ei = contract["salary_tax"]["ei"]
    return min(salary * D(ei["employee_rate"]), D(ei["employee_max"]))


def normalized_allocations(amount: Decimal, rows: list[tuple[str, Decimal]]) -> list[dict]:
    denominator = sum((value for _, value in rows), ZERO)
    if denominator <= 0:
        raise ValueError("allocation denominator must be positive")
    result = []
    for category, value in rows:
        share = value / denominator
        result.append(
            {
                "category": category,
                "share": float(share),
                "allocated_amount": money_float(amount * share),
            }
        )
    return result


def nested_federal_allocations(federal_tax: Decimal, contract: dict) -> list[dict]:
    federal = contract["federal_spending_allocation"]
    denominator = D(federal["denominator_billion"])
    rows = federal["categories"]
    result = []
    for row in rows:
        amount_billion = D(row["amount_billion"])
        share = amount_billion / denominator
        item = {
            "category": row["category"],
            "share": float(share),
            "allocated_amount": money_float(federal_tax * share),
        }
        children = row.get("children") or []
        if children:
            item["children"] = []
            for child in children:
                child_amount = D(child["amount_billion"])
                child_share = child_amount / denominator
                item["children"].append(
                    {
                        "category": child["category"],
                        "share": float(child_share),
                        "allocated_amount": money_float(federal_tax * child_share),
                    }
                )
        result.append(item)
    return result


def nova_scotia_allocations(provincial_tax: Decimal, contract: dict) -> list[dict]:
    rows = [
        (row["category"], D(row["share_pct"]))
        for row in contract["nova_scotia_spending_allocation"]["categories"]
    ]
    return normalized_allocations(provincial_tax, rows)


def salary_breakdown(salary_value: Any, contract: dict | None = None) -> dict:
    contract = contract or load_contract()
    salary = validate_nonnegative_number(salary_value, "salary")
    salary_tax = contract["salary_tax"]

    cpp = cpp_components(salary, contract)
    ei = ei_contribution(salary, contract)

    # CRA annual taxable-income payroll formula deducts the first additional CPP
    # contribution and CPP2 before applying the income-tax brackets.
    annual_taxable_income = salary - cpp["first_additional"] - cpp["cpp2"]

    federal = salary_tax["federal"]
    fed_gross = bracket_tax(annual_taxable_income, federal["brackets"])
    fed_bpa = federal_bpa(annual_taxable_income, contract)
    fed_base_cpp_ei_credit = D(federal["lowest_rate"]) * (cpp["base"] + ei)
    fed_employment_credit = D(federal["lowest_rate"]) * min(
        salary, D(federal["canada_employment_amount"])
    )
    federal_tax = max(
        fed_gross
        - D(federal["lowest_rate"]) * fed_bpa
        - fed_base_cpp_ei_credit
        - fed_employment_credit,
        ZERO,
    )

    province = salary_tax["nova_scotia"]
    ns_gross = bracket_tax(annual_taxable_income, province["brackets"])
    ns_tax = max(
        ns_gross
        - D(province["lowest_rate"]) * D(province["basic_personal_amount"])
        - D(province["lowest_rate"]) * (cpp["base"] + ei),
        ZERO,
    )

    # Income-tax calculations are retained at full precision until the final annual
    # totals are rounded. This is an annualized estimate, not a sum of per-pay-period
    # withholding amounts.
    total_income_tax = federal_tax + ns_tax
    total_contributions = cpp["combined"] + cpp["cpp2"] + ei
    total_deductions = total_income_tax + total_contributions
    take_home = salary - total_deductions

    # Display components are rounded independently. A one-cent display reconciliation
    # can occur because the internal calculation keeps full precision until totals.
    rounded_components = (
        money(federal_tax)
        + money(ns_tax)
        + money(cpp["combined"])
        + money(cpp["cpp2"])
        + money(ei)
    )
    rounded_total = money(total_deductions)
    display_rounding_adjustment = rounded_total - rounded_components

    result = {
        "tax_year": salary_tax["tax_year"],
        "province": salary_tax["province"],
        "gross_salary": money_float(salary),
        "annual_taxable_income": money_float(annual_taxable_income),
        "income_tax": {
            "federal": money_float(federal_tax),
            "nova_scotia": money_float(ns_tax),
            "total": money_float(total_income_tax),
        },
        "statutory_contributions": {
            "cpp": money_float(cpp["combined"]),
            "cpp2": money_float(cpp["cpp2"]),
            "ei": money_float(ei),
            "total": money_float(total_contributions),
        },
        "total_deductions": money_float(total_deductions),
        "take_home": money_float(take_home),
        "effective_income_tax_rate": float(total_income_tax / salary) if salary else 0.0,
        "effective_deduction_rate": float(total_deductions / salary) if salary else 0.0,
        "display_rounding_adjustment": money_float(display_rounding_adjustment),
        "federal_spending_allocation": nested_federal_allocations(federal_tax, contract),
        "nova_scotia_spending_allocation": nova_scotia_allocations(ns_tax, contract),
        "allocation_disclaimer": contract["metadata"]["allocation_semantics"],
        "calculation_disclaimer": contract["metadata"]["calculation_semantics"],
    }
    return result


def halifax_property_tax(
    assessment_value: Any,
    area: str,
    *,
    local_transit: bool = False,
    strategic_infrastructure_and_climate: bool = False,
    contract: dict | None = None,
) -> dict:
    contract = contract or load_contract()
    assessment = validate_nonnegative_number(assessment_value, "assessment")
    property_tax = contract["halifax_property_tax"]
    area_key = str(area).strip().lower()
    rates = property_tax["general_rates"]
    if area_key not in rates:
        raise ValueError(f"area must be one of {', '.join(sorted(rates))}")

    components = [{"name": f"{area_key}_general", "rate": D(rates[area_key])}]
    optional = property_tax["optional_or_area_components"]
    if local_transit:
        components.append({"name": "local_transit", "rate": D(optional["local_transit"])})
    if strategic_infrastructure_and_climate:
        components.append(
            {
                "name": "strategic_infrastructure_and_climate",
                "rate": D(optional["strategic_infrastructure_and_climate"]),
            }
        )

    total_rate = sum((row["rate"] for row in components), ZERO)
    component_results = []
    for row in components:
        amount = assessment / D("100") * row["rate"]
        component_results.append(
            {
                "component": row["name"],
                "rate_per_100": float(row["rate"]),
                "amount": money_float(amount),
            }
        )
    municipal_tax = assessment / D("100") * total_rate
    return {
        "fiscal_year": property_tax["fiscal_year"],
        "assessment": money_float(assessment),
        "area": area_key,
        "combined_rate_per_100": float(total_rate),
        "components": component_results,
        "municipal_tax": money_float(municipal_tax),
        "caveat": property_tax["caveat"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salary", type=str, help="Annual employment income in CAD")
    parser.add_argument("--assessment", type=str, help="HRM taxable property assessment in CAD")
    parser.add_argument("--area", choices=["urban", "suburban", "rural"], default="urban")
    parser.add_argument("--local-transit", action="store_true")
    parser.add_argument("--strategic-infrastructure-climate", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args()

    if args.salary is None and args.assessment is None:
        parser.error("provide --salary and/or --assessment")

    contract = load_contract(args.contract)
    payload: dict[str, Any] = {}
    if args.salary is not None:
        payload["salary"] = salary_breakdown(args.salary, contract)
    if args.assessment is not None:
        payload["halifax_property_tax"] = halifax_property_tax(
            args.assessment,
            args.area,
            local_transit=args.local_transit,
            strategic_infrastructure_and_climate=args.strategic_infrastructure_climate,
            contract=contract,
        )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
