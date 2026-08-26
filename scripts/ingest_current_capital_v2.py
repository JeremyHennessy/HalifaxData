#!/usr/bin/env python3
"""Build 010 refinement: merge exact-code continuation pages conservatively."""
from __future__ import annotations

import io

import pdfplumber

import ingest_current_capital as base


MERGE_FIELDS = (
    "previous_code",
    "executive_director",
    "asset_category",
    "service_area",
    "project_type",
    "planning_start",
    "planning_end",
    "execution_start",
    "execution_end",
    "operational_date",
    "unspent_previous_budget",
    "previously_approved_budget",
    "estimated_remaining_budget_required",
    "total_estimated_project_cost",
    "total_work_current_year",
)


def same_value(left, right) -> bool:
    if isinstance(left, str) or isinstance(right, str):
        return base.clean(left).lower() == base.clean(right).lower()
    return left == right


def merge_record(existing: dict, incoming: dict, source_id: str) -> dict:
    if base.clean(existing.get("project_name")).lower() != base.clean(incoming.get("project_name")).lower():
        raise RuntimeError(
            f"{source_id}: repeated project code {existing['project_code']} has conflicting names: "
            f"{existing.get('project_name')!r} vs {incoming.get('project_name')!r}"
        )
    result = dict(existing)
    pages = set(result.get("source_pages") or [result.get("source_page")])
    pages.update(incoming.get("source_pages") or [incoming.get("source_page")])
    result["source_pages"] = sorted(page for page in pages if page is not None)

    for field in MERGE_FIELDS:
        current = result.get(field)
        candidate = incoming.get(field)
        if current in (None, "") and candidate not in (None, ""):
            result[field] = candidate
        elif current not in (None, "") and candidate not in (None, "") and not same_value(current, candidate):
            raise RuntimeError(
                f"{source_id}: repeated project code {result['project_code']} has conflicting {field}: "
                f"{current!r} vs {candidate!r}"
            )

    annual = dict(result.get("annual_budgets") or {})
    for year, candidate in (incoming.get("annual_budgets") or {}).items():
        if year not in annual:
            annual[year] = candidate
        elif candidate is not None and annual[year] is not None and annual[year] != candidate:
            raise RuntimeError(
                f"{source_id}: repeated project code {result['project_code']} has conflicting annual budget "
                f"for {year}: {annual[year]!r} vs {candidate!r}"
            )
    result["annual_budgets"] = annual
    return result


def collect_plan_refined(session, source: dict, plan_year: str) -> list[dict]:
    blob = base.fetch_pdf(session, source["url"])
    grouped: dict[str, dict] = {}
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            record = base.extract_project_page(source["id"], source["url"], plan_year, page_num, page)
            if not record:
                continue
            record["source_pages"] = [page_num]
            code = record["project_code"]
            if code in grouped:
                grouped[code] = merge_record(grouped[code], record, source["id"])
            else:
                grouped[code] = record
    if len(grouped) < 75:
        raise RuntimeError(f"{source['id']}: only {len(grouped)} exact-code project sheets extracted; refusing publication")
    return sorted(grouped.values(), key=lambda row: row["project_code"])


base.collect_plan = collect_plan_refined

if __name__ == "__main__":
    base.main()
