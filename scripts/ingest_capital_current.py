#!/usr/bin/env python3
"""Extract current 2025/26 HRM capital-project sheets from the final Capital Plan.

The final plan publishes project-level budget and lifecycle fields that are not
present in the historical ArcGIS layer. This collector keeps the PDF source
structure/provenance, uses strict single-money-cell parsing, and links to the
historical layer only when the official project code matches exactly.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pdfplumber
import requests

from ingest_domains import clean, fetch_pdf, now, provenance, strict_money_cell

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/sources.json"
HISTORICAL = ROOT / "data/generated/capital.json"
DEFAULT_OUT = ROOT / "data/generated/capital_current.json"
SOURCE_ID = "hrm-capital-2025-26"
PARSER_VERSION = "build008-capital-current-v1"
PLAN_STATED_ACTIVE_PROJECTS = 194
MIN_PROJECT_ROWS = 175

PROJECT_MARKER = "2025/26 Capital Project"
PROJECT_CODE_RE = re.compile(r"Capital Project\s*#:\s*([A-Za-z0-9-]+)", re.I)

LABELS = {
    "project_code": ["Capital Project #"],
    "previous_project_code": ["Previous #"],
    "project_name": ["Capital Project Name"],
    "executive_director": ["Executive Director / Chief", "Executive Director", "Chief"],
    "asset_category": ["Asset Category"],
    "service_area": ["Service Area"],
    "project_type": ["Project Type"],
    "estimated_asset_operational_date": ["Estimated Asset Operational Date"],
}
SUMMARY_LABELS = {
    "previously_approved_budget": "Previously Approved Budget",
    "four_year_budget": "2025/26 - 2028/29 Budgets",
    "estimated_remaining_budget_required": "Estimated Remaining Budget Required",
    "total_estimated_project_cost": "Total Estimated Project Cost",
    "work_in_process_subtotal": "Work in Process Sub-Total",
    "new_activities_subtotal": "2025/26 New Activities Sub-Total",
    "total_work_2025_26": "Total Work to be Completed in 2025/26",
}
ANNUAL_LABELS = {
    "gross_capital_budget": "Gross Capital Budget",
    "external_funding": "External Funding",
    "reserve": "Reserve",
    "capital_renewal": "Capital Renewal",
    "debt": "Debt",
    "ongoing_operating_costs": "Ongoing Operating Costs (Savings)",
    "one_time_operating_costs": "One-Time Operating Costs (Savings)",
}
ANNUAL_KEYS = ["unspent_previous_budget", "2025_26", "2026_27", "2027_28", "2028_29"]


def normalized_rows(page) -> list[list[str]]:
    rows: list[list[str]] = []
    for table in page.extract_tables() or []:
        for raw_row in table or []:
            row = [clean(cell) for cell in (raw_row or [])]
            if any(row):
                rows.append(row)
    return rows


def label_matches(cell: str, label: str) -> bool:
    left = re.sub(r"[^a-z0-9]+", " ", clean(cell).casefold()).strip()
    right = re.sub(r"[^a-z0-9]+", " ", label.casefold()).strip()
    return left == right or left.startswith(right + " ")


def value_after_label(rows: list[list[str]], labels: list[str]) -> str | None:
    for row in rows:
        for idx, cell in enumerate(row):
            if any(label_matches(cell, label) for label in labels):
                for candidate in row[idx + 1 :]:
                    candidate = clean(candidate)
                    if candidate and not any(label_matches(candidate, other) for values in LABELS.values() for other in values):
                        return candidate
    return None


def regex_field(text: str, label: str, stop_labels: tuple[str, ...] = ()) -> str | None:
    escaped = re.escape(label)
    stop = "|".join(re.escape(item) for item in stop_labels)
    if stop:
        pattern = rf"{escaped}\s*:?\s*(.+?)(?=\s+(?:{stop})\s*:|\n|$)"
    else:
        pattern = rf"{escaped}\s*:?\s*([^\n]+)"
    match = re.search(pattern, text, flags=re.I)
    return clean(match.group(1)) if match else None


def project_identity(text: str, rows: list[list[str]]) -> dict:
    result = {key: value_after_label(rows, labels) for key, labels in LABELS.items()}
    if not result["project_code"]:
        match = PROJECT_CODE_RE.search(text)
        result["project_code"] = clean(match.group(1)) if match else None
    if not result["project_name"]:
        result["project_name"] = regex_field(text, "Capital Project Name", ("Executive Director / Chief", "Executive Director"))
    if not result["previous_project_code"]:
        match = re.search(r"Previous\s*#:\s*([A-Za-z0-9-]+)", text, flags=re.I)
        result["previous_project_code"] = clean(match.group(1)) if match else None
    return result


def strict_money_values(cells: list[str]) -> list[float | None]:
    values: list[float | None] = []
    for cell in cells:
        value, valid = strict_money_cell(cell)
        if valid:
            values.append(value)
    return values


def annual_row(rows: list[list[str]], label: str) -> dict[str, float | None] | None:
    for row in rows:
        label_index = next((idx for idx, cell in enumerate(row) if label_matches(cell, label)), None)
        if label_index is None:
            continue
        values = strict_money_values(row[label_index + 1 :])
        # PDF table extraction may include blank columns; strict_money_values
        # intentionally retains valid blank/dash cells as None.
        if not values:
            return {key: None for key in ANNUAL_KEYS}
        if len(values) > 5:
            values = values[:5]
        while len(values) < 5:
            values.append(None)
        return dict(zip(ANNUAL_KEYS, values, strict=True))
    return None


def summary_money(rows: list[list[str]], label: str) -> float | None:
    for row_index, row in enumerate(rows):
        for idx, cell in enumerate(row):
            if not label_matches(cell, label):
                continue
            # Prefer a monetary value on the same row.
            same_row = strict_money_values(row[idx + 1 :])
            finite = [value for value in same_row if value is not None]
            if finite:
                return finite[-1]
            # Some PDF tables place the summary values in a neighboring row.
            for lookahead in rows[row_index + 1 : row_index + 3]:
                look_values = strict_money_values(lookahead)
                finite = [value for value in look_values if value is not None]
                if finite:
                    return finite[-1]
            return None
    return None


def timing(text: str, heading: str) -> dict[str, str | None]:
    pattern = rf"{re.escape(heading)}.*?Start:\s*([^\s]+).*?End:\s*([^\s]+)"
    match = re.search(pattern, text, flags=re.I | re.S)
    if not match:
        return {"start": None, "end": None}
    return {"start": clean(match.group(1)), "end": clean(match.group(2))}


def extract_text_section(text: str, start: str, ends: tuple[str, ...]) -> str | None:
    start_match = re.search(re.escape(start), text, flags=re.I)
    if not start_match:
        return None
    remaining = text[start_match.end() :]
    stop_positions = []
    for end in ends:
        match = re.search(re.escape(end), remaining, flags=re.I)
        if match:
            stop_positions.append(match.start())
    if stop_positions:
        remaining = remaining[: min(stop_positions)]
    value = clean(remaining)
    return value[:4000] if value else None


def historical_codes() -> dict[str, list[str]]:
    if not HISTORICAL.exists():
        return {}
    payload = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    mapping: dict[str, list[str]] = {}
    for row in payload.get("records", []):
        code = clean(row.get("project_code"))
        if not code:
            continue
        mapping.setdefault(code, []).append(clean(row.get("project_id")))
    return mapping


def parse_project(page_num: int, page, source_url: str, historical: dict[str, list[str]]) -> dict | None:
    text = page.extract_text() or ""
    if PROJECT_MARKER.casefold() not in text.casefold() or "Capital Project #:".casefold() not in text.casefold():
        return None
    rows = normalized_rows(page)
    identity = project_identity(text, rows)
    code = clean(identity.get("project_code"))
    if not code:
        return None

    annual = {key: annual_row(rows, label) for key, label in ANNUAL_LABELS.items()}
    summaries = {key: summary_money(rows, label) for key, label in SUMMARY_LABELS.items()}
    matched_historical_ids = historical.get(code, [])

    return {
        "project_code": code,
        "previous_project_code": clean(identity.get("previous_project_code")) or None,
        "project_name": clean(identity.get("project_name")) or None,
        "executive_director": clean(identity.get("executive_director")) or None,
        "asset_category": clean(identity.get("asset_category")) or None,
        "service_area": clean(identity.get("service_area")) or None,
        "project_type": clean(identity.get("project_type")) or None,
        "project_deliverables": extract_text_section(text, "Project Deliverables", ("Impact to Service", "Strategic Plan")),
        "impact_to_service": extract_text_section(text, "Impact to Service", ("Strategic Plan", "Estimated Project Planning")),
        "planning_design_timing": timing(text, "Estimated Project Planning & Design Phase Timing"),
        "execution_timing": timing(text, "Estimated Project Execution Phase Timing"),
        "estimated_asset_operational_date": clean(identity.get("estimated_asset_operational_date")) or None,
        "annual_budget": annual.get("gross_capital_budget"),
        "annual_funding": {
            "external_funding": annual.get("external_funding"),
            "reserve": annual.get("reserve"),
            "capital_renewal": annual.get("capital_renewal"),
            "debt": annual.get("debt"),
        },
        "operating_impacts": {
            "ongoing": annual.get("ongoing_operating_costs"),
            "one_time": annual.get("one_time_operating_costs"),
        },
        **summaries,
        "historical_exact_match": bool(matched_historical_ids),
        "historical_project_object_ids": matched_historical_ids,
        "source_id": SOURCE_ID,
        "source_page": page_num,
        "provenance": provenance(SOURCE_ID, source_url, "pdf-page", f"p{page_num}", PARSER_VERSION),
    }


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source = next(item for item in registry["sources"] if item["id"] == SOURCE_ID)
    session = requests.Session()
    session.headers["User-Agent"] = "HalifaxData/0.8 (+https://github.com/JeremyHennessy/HalifaxData)"
    blob = fetch_pdf(session, source)
    historical = historical_codes()

    records = []
    project_marker_pages = 0
    missing_code_pages = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if PROJECT_MARKER.casefold() not in text.casefold():
                continue
            project_marker_pages += 1
            row = parse_project(page_num, page, source["url"], historical)
            if row is None:
                missing_code_pages.append(page_num)
            else:
                records.append(row)

    by_code: dict[str, dict] = {}
    duplicates = []
    for row in records:
        code = row["project_code"]
        if code in by_code:
            duplicates.append({"project_code": code, "pages": [by_code[code]["source_page"], row["source_page"]]})
            continue
        by_code[code] = row
    records = sorted(by_code.values(), key=lambda row: row["project_code"])

    if duplicates:
        raise RuntimeError(f"Duplicate current project codes found; refusing artifact: {duplicates[:10]!r}")
    if len(records) < MIN_PROJECT_ROWS:
        raise RuntimeError(
            f"Only {len(records)} unique current capital projects extracted from {project_marker_pages} project-marker pages; "
            f"expected at least {MIN_PROJECT_ROWS}. Missing-code pages: {missing_code_pages[:20]}"
        )

    summary_complete = sum(
        1 for row in records
        if row.get("previously_approved_budget") is not None
        or row.get("four_year_budget") is not None
        or row.get("total_estimated_project_cost") is not None
    )
    annual_complete = sum(1 for row in records if row.get("annual_budget") is not None)
    historical_matches = sum(1 for row in records if row["historical_exact_match"])

    payload = {
        "metadata": {
            "generated_at": now(),
            "dataset_status": "final_2025_26_capital_plan_project_extraction",
            "parser_version": PARSER_VERSION,
            "source_id": SOURCE_ID,
            "records": len(records),
            "project_marker_pages": project_marker_pages,
            "missing_code_pages": missing_code_pages,
            "plan_stated_active_projects": PLAN_STATED_ACTIVE_PROJECTS,
            "summary_budget_rows": summary_complete,
            "annual_budget_rows": annual_complete,
            "historical_exact_project_code_matches": historical_matches,
            "exact_join_only": True,
            "note": (
                "Final 2025/26 Capital Plan project sheets. Budget fields are source-plan amounts, not actual paid amounts. "
                "Historical ArcGIS linkage is permitted only when project_code matches exactly; no fuzzy project matching."
            ),
        },
        "records": records,
    }

    DEFAULT_OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"current capital: {len(records)} unique project sheets; marker_pages={project_marker_pages}; "
        f"annual_budget_rows={annual_complete}; summary_budget_rows={summary_complete}; "
        f"historical_exact_matches={historical_matches}; missing_code_pages={missing_code_pages}"
    )


if __name__ == "__main__":
    main()
