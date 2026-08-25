#!/usr/bin/env python3
"""Extract current 2025/26 HRM capital-project sheets from the final Capital Plan.

The final plan publishes project-level budget and lifecycle fields that are not
present in the historical ArcGIS layer. This collector preserves source-page
provenance, aligns money by the PDF's explicit period headers, and links to the
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
PARSER_VERSION = "build008-capital-current-v2"
PLAN_NARRATIVE_ACTIVE_PROJECTS = 194
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
    "gross_capital_budget": ("Gross Capital Budget", True),
    "external_funding": ("External Funding", True),
    "reserve": ("Reserve", True),
    "capital_renewal": ("Capital Renewal", True),
    "debt": ("Debt", True),
    "ongoing_operating_costs": ("Ongoing Operating Costs (Savings)", False),
    "one_time_operating_costs": ("One-Time Operating Costs (Savings)", False),
}
CAPITAL_PERIODS = [
    ("unspent_previous_budget", "unspent prev"),
    ("2025_26", "2025/26"),
    ("2026_27", "2026/27"),
    ("2027_28", "2027/28"),
    ("2028_29", "2028/29"),
]
OPERATING_PERIODS = CAPITAL_PERIODS[1:]


def normalized_rows(page) -> list[list[str]]:
    rows: list[list[str]] = []
    for table in page.extract_tables() or []:
        for raw_row in table or []:
            row = [clean(cell) for cell in (raw_row or [])]
            if any(row):
                rows.append(row)
    return rows


def normalized_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean(value).casefold()).strip()


def label_matches(cell: str, label: str) -> bool:
    left = normalized_label(cell)
    right = normalized_label(label)
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
    pattern = rf"{escaped}\s*:?\s*(.+?)(?=\s+(?:{stop})\s*:|\n|$)" if stop else rf"{escaped}\s*:?\s*([^\n]+)"
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


def parse_money_segment(cells: list[str], *, context: str) -> float | None:
    tokens = [clean(cell) for cell in cells if clean(cell) and clean(cell) != "$"]
    if not tokens:
        return None
    if len(tokens) != 1:
        raise RuntimeError(f"Ambiguous money segment for {context}: {tokens!r}")
    value, valid = strict_money_cell(tokens[0])
    if not valid:
        raise RuntimeError(f"Invalid money cell for {context}: {tokens[0]!r}")
    return value


def period_anchors(rows: list[list[str]], target_index: int, include_unspent: bool) -> list[tuple[str, int]] | None:
    periods = CAPITAL_PERIODS if include_unspent else OPERATING_PERIODS
    for row in reversed(rows[:target_index]):
        anchors = []
        for key, marker in periods:
            match_index = next((idx for idx, cell in enumerate(row) if marker in clean(cell).casefold()), None)
            if match_index is None:
                anchors = []
                break
            anchors.append((key, match_index))
        if anchors and all(anchors[i][1] < anchors[i + 1][1] for i in range(len(anchors) - 1)):
            return anchors
    return None


def annual_row(rows: list[list[str]], label: str, include_unspent: bool) -> dict[str, float | None] | None:
    for row_index, row in enumerate(rows):
        label_index = next((idx for idx, cell in enumerate(row) if label_matches(cell, label)), None)
        if label_index is None:
            continue
        anchors = period_anchors(rows, row_index, include_unspent)
        periods = CAPITAL_PERIODS if include_unspent else OPERATING_PERIODS
        if anchors is None:
            return {key: None for key, _ in periods}
        result: dict[str, float | None] = {}
        for anchor_index, (key, start) in enumerate(anchors):
            end = anchors[anchor_index + 1][1] if anchor_index + 1 < len(anchors) else len(row)
            result[key] = parse_money_segment(row[start:end], context=f"{label}/{key}")
        return result
    return None


def summary_money(rows: list[list[str]], label: str) -> float | None:
    for row in rows:
        for idx, cell in enumerate(row):
            if not label_matches(cell, label):
                continue
            # Summary/work-plan values are printed on the same source row. Never
            # borrow a value from a neighboring row: a blank source cell means null.
            return parse_money_segment(row[idx + 1 :], context=label)
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
        if code:
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

    annual = {key: annual_row(rows, label, include_unspent) for key, (label, include_unspent) in ANNUAL_LABELS.items()}
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

    summary_complete = sum(1 for row in records if row.get("total_estimated_project_cost") is not None)
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
            "plan_narrative_active_projects": PLAN_NARRATIVE_ACTIVE_PROJECTS,
            "project_sheets_extracted": len(records),
            "project_cost_summary_rows": summary_complete,
            "annual_budget_rows": annual_complete,
            "historical_exact_project_code_matches": historical_matches,
            "exact_join_only": True,
            "note": (
                "Final 2025/26 Capital Plan project sheets. Some program-style sheets do not publish a total-project-cost summary; "
                "blank summary fields remain null. Budget fields are source-plan amounts, not actual paid amounts. Historical ArcGIS "
                "linkage is permitted only when project_code matches exactly; no fuzzy project matching."
            ),
        },
        "records": records,
    }

    DEFAULT_OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"current capital: {len(records)} unique project sheets; marker_pages={project_marker_pages}; "
        f"annual_budget_rows={annual_complete}; project_cost_summary_rows={summary_complete}; "
        f"historical_exact_matches={historical_matches}; missing_code_pages={missing_code_pages}"
    )


if __name__ == "__main__":
    main()
