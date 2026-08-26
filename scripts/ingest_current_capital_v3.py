#!/usr/bin/env python3
"""Build 010 identity refinement: trust the explicit Capital Project # field only.

HRM uses both conventional codes (for example CT000007) and shorter/alphanumeric
codes (for example BT36 or Transit3). A Previous # value must never be promoted
into the current project identity when the current code uses a different format.
"""
from __future__ import annotations

import re

import ingest_current_capital as base
import ingest_current_capital_v2 as continuation  # applies conservative continuation-page merge

CURRENT_CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,24}$")
TEXT_CODE_RE = re.compile(r"Capital\s+Project\s*#:\s*([A-Za-z][A-Za-z0-9_-]{2,24})", re.I)


def authoritative_project_code(rows: list[list[str]], text: str) -> str | None:
    raw = base.field(rows, text, "Capital Project #")
    for token in re.split(r"\s+", base.clean(raw)):
        token = token.strip(" ,;:()")
        if CURRENT_CODE_RE.fullmatch(token):
            return token
    match = TEXT_CODE_RE.search(text or "")
    return match.group(1) if match else None


def extract_project_page_refined(source_id: str, source_url: str, plan_year: str, page_num: int, page) -> dict | None:
    text = page.extract_text() or ""
    if "Capital Project" not in text or "Capital Project #:" not in text:
        return None
    rows = base.table_rows(page)
    project_code = authoritative_project_code(rows, text)
    if not project_code:
        return None
    project_name = base.field(rows, text, "Capital Project Name")
    if not project_name:
        return None
    planning_start, planning_end = base.extract_timing(text, "Estimated Project Planning & Design Phase Timing")
    execution_start, execution_end = base.extract_timing(text, "Estimated Project Execution Phase Timing")
    gross = base.extract_gross_schedule(rows, plan_year)
    return {
        "plan_year": plan_year,
        "project_code": project_code,
        "project_name": project_name,
        "previous_code": base.field(rows, text, "Previous #") or None,
        "executive_director": base.field(rows, text, "Executive Director / Chief") or base.field(rows, text, "Executive Director") or None,
        "asset_category": base.field(rows, text, "Asset Category") or None,
        "service_area": base.field(rows, text, "Service Area") or None,
        "project_type": base.field(rows, text, "Project Type") or None,
        "planning_start": planning_start,
        "planning_end": planning_end,
        "execution_start": execution_start,
        "execution_end": execution_end,
        "operational_date": base.extract_operational_date(text),
        "unspent_previous_budget": gross["unspent_previous_budget"],
        "annual_budgets": gross["annual_budgets"],
        "previously_approved_budget": base.line_money(text, "Previously Approved Budget"),
        "estimated_remaining_budget_required": base.line_money(text, "Estimated Remaining Budget Required"),
        "total_estimated_project_cost": base.line_money(text, "Total Estimated Project Cost"),
        "total_work_current_year": base.line_money(text, f"Total Work to be Completed in {plan_year}"),
        "source_id": source_id,
        "source_page": page_num,
        "provenance": base.provenance(source_id, source_url, page_num, f"p{page_num}/{project_code}", "pdf-project-sheet"),
    }


base.extract_project_page = extract_project_page_refined
# continuation.collect_plan_refined resolves base.extract_project_page dynamically.
base.collect_plan = continuation.collect_plan_refined

if __name__ == "__main__":
    base.main()
