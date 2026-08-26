#!/usr/bin/env python3
"""Collect current HRM capital-plan project sheets and approved 2025/26 adjustments.

This collector deliberately keeps three evidence types separate:
1. final 2024/25 and 2025/26 capital-plan project sheets,
2. exact-code plan-over-plan estimate/schedule comparisons,
3. post-ratification 2025/26 capital-budget adjustments approved by Council.

Nothing in this artifact is transaction-level spend, invoice data, commitments, or
proof of a cost overrun. Plan estimates and approved budget changes remain source-
scoped facts with page/document provenance.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "sources.json"
COUNCIL = ROOT / "data" / "generated" / "council.json"
COUNCIL_DOCS = ROOT / "data" / "generated" / "council_documents.json"
DEFAULT_OUT = ROOT / "data" / "generated" / "current_capital.json"
UA = "HalifaxData/0.10 (+https://github.com/JeremyHennessy/HalifaxData)"
PARSER_VERSION = "build010-current-capital-v1"
PLAN_SOURCE_IDS = ("hrm-capital-2024-25", "hrm-capital-2025-26")
ADJUSTMENT_SOURCE_ID = "hrm-capital-adjustments-2025-26"
ADJUSTMENT_TITLE_TOKEN = "2025-26 Capital Budget Adjustments"
ADJUSTMENT_MEETING_ID = "d170b0da-a5f9-4e87-80c4-f58ea1f9b47f"
MAX_ABS_MONEY = 10_000_000_000
PROJECT_CODE_RE = re.compile(r"\b[A-Z]{1,3}\d{6}\b")
MONEY_RE = re.compile(r"(?:\(\s*\$?\s*[\d,]+(?:\.\d+)?\s*\)|-?\s*\$?\s*[\d,]+(?:\.\d+)?)")
MONTH_YEAR_RE = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}\b", re.I)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()


def money(value):
    text = clean(value)
    if not text or text in {"-", "$ -", "$-"}:
        return 0.0 if text else None
    negative = text.startswith("(") and text.endswith(")")
    compact = text.replace("$", "").replace(",", "").replace(" ", "")
    if negative:
        compact = compact[1:-1]
    if compact in {"", "-"}:
        return 0.0
    try:
        result = float(compact)
    except ValueError:
        return None
    if negative:
        result = -result
    if abs(result) > MAX_ABS_MONEY:
        return None
    return round(result, 2)


def money_tokens(text: str) -> list[float]:
    values = []
    for match in MONEY_RE.finditer(text or ""):
        raw = clean(match.group())
        # A plain small integer in narrative text is not treated as money.
        if not any(marker in raw for marker in ("$", ",", "(", ")")):
            continue
        value = money(raw)
        if value is not None:
            values.append(value)
    return values


def provenance(source_id: str, source_url: str, page: int | None, locator: str, method: str) -> dict:
    return {
        "source_id": source_id,
        "source_url": source_url,
        "retrieved_at": now(),
        "locator_type": method,
        "locator_value": locator,
        "source_page": page,
        "parser_version": PARSER_VERSION,
        "validation_status": "parsed",
    }


def fetch_pdf(session: requests.Session, url: str) -> bytes:
    response = session.get(url, timeout=180)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise RuntimeError(f"Expected PDF from {url}, received {response.headers.get('content-type')!r}")
    return response.content


def table_rows(page) -> list[list[str]]:
    rows: list[list[str]] = []
    for table in page.extract_tables() or []:
        for row in table or []:
            normalized = [clean(cell) for cell in (row or [])]
            if any(normalized):
                rows.append(normalized)
    return rows


def table_value(rows: list[list[str]], label: str) -> str:
    wanted = clean(label).rstrip(":").lower()
    for row in rows:
        for index, cell in enumerate(row):
            key = clean(cell).rstrip(":").lower()
            if key == wanted:
                for candidate in row[index + 1 :]:
                    if clean(candidate):
                        return clean(candidate)
    return ""


def text_field(text: str, label: str) -> str:
    lines = [clean(line) for line in (text or "").splitlines() if clean(line)]
    wanted = label.lower().rstrip(":")
    for i, line in enumerate(lines):
        low = line.lower()
        marker = f"{wanted}:"
        if marker in low:
            start = low.index(marker) + len(marker)
            value = clean(line[start:])
            if value:
                return value
            if i + 1 < len(lines):
                return lines[i + 1]
    return ""


def field(rows: list[list[str]], text: str, label: str) -> str:
    return table_value(rows, label) or text_field(text, label)


def line_money(text: str, label: str) -> float | None:
    lines = [clean(line) for line in (text or "").splitlines() if clean(line)]
    wanted = label.lower()
    for i, line in enumerate(lines):
        if wanted in line.lower():
            values = money_tokens(line)
            if values:
                return values[-1]
            # PDF extraction sometimes places the value immediately before/after the label.
            for neighbor in (i - 1, i + 1):
                if 0 <= neighbor < len(lines):
                    values = money_tokens(lines[neighbor])
                    if values:
                        return values[-1]
    return None


def extract_timing(text: str, label: str) -> tuple[str | None, str | None]:
    lines = [clean(line) for line in (text or "").splitlines() if clean(line)]
    wanted = label.lower()
    for i, line in enumerate(lines):
        if wanted in line.lower():
            context = " ".join(lines[i : i + 3])
            months = MONTH_YEAR_RE.findall(context)
            if len(months) >= 2:
                return months[0], months[1]
    return None, None


def extract_operational_date(text: str) -> str | None:
    lines = [clean(line) for line in (text or "").splitlines() if clean(line)]
    for i, line in enumerate(lines):
        if "estimated asset operational date" in line.lower():
            context = " ".join(lines[i : i + 2])
            match = MONTH_YEAR_RE.search(context)
            if match:
                return match.group(0)
    return None


def extract_gross_schedule(rows: list[list[str]], plan_year: str) -> dict:
    for row_index, row in enumerate(rows):
        if not any("gross capital budget" == clean(cell).lower() for cell in row):
            continue
        header = rows[row_index - 1] if row_index > 0 else []
        labels = [clean(cell) for cell in header]
        values = []
        for cell in row:
            cell_clean = clean(cell)
            if not cell_clean or cell_clean.lower() == "gross capital budget":
                continue
            parsed = money(cell_clean)
            if parsed is not None:
                values.append(parsed)
        if not values:
            continue
        fiscal_labels = [label for label in labels if re.fullmatch(r"20\d{2}/\d{2}", label)]
        result = {"unspent_previous_budget": None, "annual_budgets": {}}
        if len(values) >= len(fiscal_labels) + 1:
            result["unspent_previous_budget"] = values[0]
            fiscal_values = values[1 : 1 + len(fiscal_labels)]
        else:
            fiscal_values = values[: len(fiscal_labels)]
        result["annual_budgets"] = dict(zip(fiscal_labels, fiscal_values))
        if plan_year not in result["annual_budgets"] and values:
            # Fail-soft display aid only; validation never relies on this fallback.
            result["annual_budgets"][plan_year] = values[1] if len(values) > 1 else values[0]
        return result
    return {"unspent_previous_budget": None, "annual_budgets": {}}


def extract_project_page(source_id: str, source_url: str, plan_year: str, page_num: int, page) -> dict | None:
    text = page.extract_text() or ""
    if "Capital Project" not in text or "Capital Project #:" not in text:
        return None
    rows = table_rows(page)
    project_code = field(rows, text, "Capital Project #")
    code_match = PROJECT_CODE_RE.search(project_code) or PROJECT_CODE_RE.search(text)
    if not code_match:
        return None
    project_code = code_match.group(0)
    project_name = field(rows, text, "Capital Project Name")
    if not project_name:
        return None
    planning_start, planning_end = extract_timing(text, "Estimated Project Planning & Design Phase Timing")
    execution_start, execution_end = extract_timing(text, "Estimated Project Execution Phase Timing")
    gross = extract_gross_schedule(rows, plan_year)
    record = {
        "plan_year": plan_year,
        "project_code": project_code,
        "project_name": project_name,
        "previous_code": field(rows, text, "Previous #") or None,
        "executive_director": field(rows, text, "Executive Director / Chief") or field(rows, text, "Executive Director") or None,
        "asset_category": field(rows, text, "Asset Category") or None,
        "service_area": field(rows, text, "Service Area") or None,
        "project_type": field(rows, text, "Project Type") or None,
        "planning_start": planning_start,
        "planning_end": planning_end,
        "execution_start": execution_start,
        "execution_end": execution_end,
        "operational_date": extract_operational_date(text),
        "unspent_previous_budget": gross["unspent_previous_budget"],
        "annual_budgets": gross["annual_budgets"],
        "previously_approved_budget": line_money(text, "Previously Approved Budget"),
        "estimated_remaining_budget_required": line_money(text, "Estimated Remaining Budget Required"),
        "total_estimated_project_cost": line_money(text, "Total Estimated Project Cost"),
        "total_work_current_year": line_money(text, f"Total Work to be Completed in {plan_year}"),
        "source_id": source_id,
        "source_page": page_num,
        "provenance": provenance(source_id, source_url, page_num, f"p{page_num}/{project_code}", "pdf-project-sheet"),
    }
    return record


def collect_plan(session: requests.Session, source: dict, plan_year: str) -> list[dict]:
    blob = fetch_pdf(session, source["url"])
    records = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            record = extract_project_page(source["id"], source["url"], plan_year, page_num, page)
            if record:
                records.append(record)
    unique: dict[str, dict] = {}
    duplicates = []
    for row in records:
        code = row["project_code"]
        if code in unique:
            duplicates.append(code)
            continue
        unique[code] = row
    if duplicates:
        raise RuntimeError(f"{source['id']}: duplicate project codes extracted: {sorted(set(duplicates))[:10]}")
    if len(unique) < 75:
        raise RuntimeError(f"{source['id']}: only {len(unique)} project sheets extracted; refusing publication")
    return sorted(unique.values(), key=lambda row: row["project_code"])


def month_index(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"([A-Za-z]{3})-(\d{2})", value)
    if not match:
        return None
    month_names = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    month = match.group(1).lower()
    if month not in month_names:
        return None
    year = 2000 + int(match.group(2))
    return year * 12 + month_names.index(month)


def compare_plans(prior: list[dict], current: list[dict]) -> list[dict]:
    prior_by_code = {row["project_code"]: row for row in prior}
    comparisons = []
    for current_row in current:
        prior_row = prior_by_code.get(current_row["project_code"])
        if not prior_row:
            continue
        prior_cost = prior_row.get("total_estimated_project_cost")
        current_cost = current_row.get("total_estimated_project_cost")
        cost_change = None
        cost_change_pct = None
        if prior_cost is not None and current_cost is not None:
            cost_change = round(current_cost - prior_cost, 2)
            if abs(prior_cost) >= 1:
                cost_change_pct = cost_change / abs(prior_cost)
        prior_end = month_index(prior_row.get("execution_end"))
        current_end = month_index(current_row.get("execution_end"))
        execution_end_change_months = None if prior_end is None or current_end is None else current_end - prior_end
        prior_operational = month_index(prior_row.get("operational_date"))
        current_operational = month_index(current_row.get("operational_date"))
        operational_date_change_months = None if prior_operational is None or current_operational is None else current_operational - prior_operational
        comparisons.append({
            "project_code": current_row["project_code"],
            "project_name_2024_25": prior_row["project_name"],
            "project_name_2025_26": current_row["project_name"],
            "prior_total_estimated_project_cost": prior_cost,
            "current_total_estimated_project_cost": current_cost,
            "estimated_project_cost_change": cost_change,
            "estimated_project_cost_change_pct": cost_change_pct,
            "prior_execution_end": prior_row.get("execution_end"),
            "current_execution_end": current_row.get("execution_end"),
            "execution_end_change_months": execution_end_change_months,
            "prior_operational_date": prior_row.get("operational_date"),
            "current_operational_date": current_row.get("operational_date"),
            "operational_date_change_months": operational_date_change_months,
            "prior_source_id": prior_row["source_id"],
            "current_source_id": current_row["source_id"],
            "prior_source_page": prior_row["source_page"],
            "current_source_page": current_row["source_page"],
            "comparison_method": "exact_project_code",
        })
    return sorted(comparisons, key=lambda row: row["project_code"])


SECTION_LABELS = {
    "new external cost sharing awards": "external_cost_sharing_award",
    "capital budget transfers": "capital_budget_transfer",
    "capital budget increases": "capital_budget_increase",
}


def section_at(text: str, position: int) -> str | None:
    candidates = []
    low = text.lower()
    for heading, section in SECTION_LABELS.items():
        start = 0
        while True:
            index = low.find(heading, start)
            if index < 0:
                break
            if index <= position:
                candidates.append((index, section))
            start = index + len(heading)
    return max(candidates, default=(None, None), key=lambda pair: -1 if pair[0] is None else pair[0])[1]


def collect_adjustments(session: requests.Session, report_url: str) -> list[dict]:
    blob = fetch_pdf(session, report_url)
    rows = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            matches = list(PROJECT_CODE_RE.finditer(text))
            for index, match in enumerate(matches):
                section = section_at(text, match.start())
                if not section:
                    continue
                segment_end = matches[index + 1].start() if index + 1 < len(matches) else min(len(text), match.end() + 500)
                segment = clean(text[match.start() : segment_end])
                values = money_tokens(segment)
                if len(values) < 3:
                    continue
                code = match.group(0)
                project_name = clean(segment[len(code) :])
                # Remove monetary suffix from display name.
                money_match = MONEY_RE.search(project_name)
                if money_match:
                    project_name = clean(project_name[: money_match.start()])
                baseline, adjustment, adjusted = values[:3]
                if round(baseline + adjustment - adjusted, 2) != 0:
                    continue
                rows.append({
                    "adjustment_type": section,
                    "project_code": code,
                    "project_name": project_name or code,
                    "approved_budget_before": baseline,
                    "adjustment_amount": adjustment,
                    "approved_budget_after": adjusted,
                    "source_id": ADJUSTMENT_SOURCE_ID,
                    "source_page": page_num,
                    "provenance": provenance(ADJUSTMENT_SOURCE_ID, report_url, page_num, f"p{page_num}/{code}/{section}", "council-report-table-text"),
                })
    unique = {}
    for row in rows:
        key = (row["adjustment_type"], row["project_code"], row["approved_budget_before"], row["adjustment_amount"], row["approved_budget_after"])
        unique.setdefault(key, row)
    return sorted(unique.values(), key=lambda row: (row["adjustment_type"], row["project_code"]))


def resolve_adjustment_document(council_docs: dict) -> dict:
    matches = [
        row for row in (council_docs.get("records") or [])
        if ADJUSTMENT_TITLE_TOKEN.lower() in clean(row.get("title")).lower()
    ]
    exact = [row for row in matches if row.get("meeting_id") == ADJUSTMENT_MEETING_ID]
    if len(exact) != 1:
        raise RuntimeError(f"Expected one exact Capital Budget Adjustments document on May 27, 2025; found {len(exact)}")
    return exact[0]


def verify_council_decision(session: requests.Session, council: dict) -> dict:
    meeting = next((row for row in (council.get("records") or []) if row.get("meeting_id") == ADJUSTMENT_MEETING_ID), None)
    if not meeting:
        raise RuntimeError("May 27, 2025 Regional Council meeting missing from council artifact")
    minutes_url = meeting.get("minutes_pdf_url")
    if not minutes_url:
        raise RuntimeError("Capital adjustment meeting has no minutes PDF URL")
    blob = fetch_pdf(session, minutes_url)
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    normalized = clean(text).lower()
    item_index = normalized.find("15.2.1")
    if item_index < 0 or "capital budget adjustments" not in normalized[item_index : item_index + 7000]:
        raise RuntimeError("Council minutes do not contain item 15.2.1 Capital Budget Adjustments")
    item_text = normalized[item_index : item_index + 12000]
    passed_unanimously = "motion put and passed unanimously" in item_text
    if not passed_unanimously:
        raise RuntimeError("Council minutes did not verify unanimous passage for item 15.2.1")
    return {
        "decision_status": "approved",
        "decision_date": "2025-05-27",
        "meeting_id": ADJUSTMENT_MEETING_ID,
        "meeting_name": meeting.get("meeting_name"),
        "minutes_url": minutes_url,
        "motion_result": "MOTION PUT AND PASSED UNANIMOUSLY",
        "source_id": "hrm-escribe",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sources = {row["id"]: row for row in registry.get("sources", [])}
    for source_id in PLAN_SOURCE_IDS:
        if source_id not in sources:
            raise RuntimeError(f"Missing required source registry entry: {source_id}")
    council = json.loads(COUNCIL.read_text(encoding="utf-8"))
    council_docs = json.loads(COUNCIL_DOCS.read_text(encoding="utf-8"))
    adjustment_doc = resolve_adjustment_document(council_docs)

    session = requests.Session()
    session.headers["User-Agent"] = UA

    prior_projects = collect_plan(session, sources["hrm-capital-2024-25"], "2024/25")
    current_projects = collect_plan(session, sources["hrm-capital-2025-26"], "2025/26")
    comparisons = compare_plans(prior_projects, current_projects)
    adjustments = collect_adjustments(session, adjustment_doc["url"])
    decision = verify_council_decision(session, council)

    for row in adjustments:
        row["decision"] = decision

    payload = {
        "metadata": {
            "dataset_status": "current_capital_plan_and_approved_adjustments",
            "parser_version": PARSER_VERSION,
            "generated_at": now(),
            "current_plan_source_id": "hrm-capital-2025-26",
            "prior_plan_source_id": "hrm-capital-2024-25",
            "adjustment_source_id": ADJUSTMENT_SOURCE_ID,
            "current_projects": len(current_projects),
            "prior_projects": len(prior_projects),
            "exact_code_plan_comparisons": len(comparisons),
            "approved_adjustments": len(adjustments),
            "is_transaction_ledger": False,
            "has_project_spend_to_date": False,
            "note": (
                "Current/final capital-plan project sheets, exact project-code plan-over-plan comparisons, "
                "and Council-approved 2025/26 capital-budget adjustment rows. These are planning/budget "
                "facts, not transaction-level spend, invoices, commitments, final project costs, or proof of overrun."
            ),
        },
        "decision": decision,
        "current_projects": current_projects,
        "prior_projects": prior_projects,
        "plan_comparisons": comparisons,
        "adjustments": adjustments,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print(
        f"current capital: {len(current_projects)} current projects, {len(prior_projects)} prior projects, "
        f"{len(comparisons)} exact-code comparisons, {len(adjustments)} approved adjustments"
    )


if __name__ == "__main__":
    main()
