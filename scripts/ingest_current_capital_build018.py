#!/usr/bin/env python3
"""Collect HRM's approved-current 2026/27 Capital Multi-Year Projects schedule.

Build 018 keeps this source separate from Build 010's 2024/25 and 2025/26 project-sheet
layer. Attachment 2 is a fiscal-year cashflow/budget schedule for named multi-year
projects and ongoing programs. It is not project spend-to-date, an AP/payment ledger,
a commitment ledger, final project cost or evidence of an overrun.
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "current_capital_sources.json"
OUTPUT = ROOT / "data" / "generated" / "current_capital_2026_27_multiyear.json"
UA = "HalifaxData/0.18 (+https://github.com/JeremyHennessy/HalifaxData)"
PARSER_VERSION = "build018-current-capital-v1"

EXPECTED_HEADER = [
    "Project Account #",
    "Project Name",
    "Total Previous Yrs' Gross Budget",
    "2025/26 Capital Budget",
    "2026/27 Capital Budget",
    "2027/28 Capital Budget",
    "2028/29 Capital Budget",
    "2029/30 Capital Budget",
    "2030/31 - 2035/36 Capital Budget",
    "Grand Total",
]

VALUE_FIELDS = [
    "total_previous_years_gross_budget",
    "capital_budget_2025_26",
    "capital_budget_2026_27",
    "capital_budget_2027_28",
    "capital_budget_2028_29",
    "capital_budget_2029_30",
    "capital_budget_2030_31_to_2035_36",
]


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def money(value: object) -> int | None:
    text = clean(value).replace("$", "").replace(",", "").replace(" ", "")
    if text in {"", "-", "–", "—"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        raise RuntimeError(f"cannot parse capital amount {value!r}")
    number = float(text)
    if negative:
        number = -number
    if not number.is_integer():
        raise RuntimeError(f"capital schedule contains non-integer dollar amount {value!r}")
    return int(number)


def value_or_zero(value: int | None) -> int:
    return 0 if value is None else value


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current: dict | None = None
        self.links: list[dict] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.current = {"href": href, "text": []}

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"].append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or self.current is None:
            return
        self.current["text"] = clean(html.unescape(" ".join(self.current["text"])))
        self.links.append(self.current)
        self.current = None


def resolve_attachment(session: requests.Session, source: dict) -> str:
    response = session.get(source["agenda_url"], timeout=180)
    response.raise_for_status()
    parser = LinkParser()
    parser.feed(response.text)
    urls = {
        urljoin(source["agenda_url"], link["href"])
        for link in parser.links
        if clean(link["text"]) == source["attachment_visible_title"]
    }
    if len(urls) != 1:
        raise RuntimeError(
            f"expected exactly one unique revised-capital attachment for "
            f"{source['attachment_visible_title']!r}; found {sorted(urls)}"
        )
    return next(iter(urls))


def fetch_pdf(session: requests.Session, source: dict, resolved_url: str) -> bytes:
    response = session.get(resolved_url, headers={"Referer": source["agenda_url"]}, timeout=180)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise RuntimeError(
            f"expected capital PDF from {resolved_url}; got {response.headers.get('content-type')!r}"
        )
    return response.content


def parse_project_row(cells: list[str], schedule_class: str, row_number: int, source: dict, resolved_url: str, retrieved_at: str) -> dict:
    if len(cells) != 10:
        raise RuntimeError(f"Attachment 2 row {row_number}: expected 10 cells, found {len(cells)}")
    project_account_id = clean(cells[0])
    project_name = clean(cells[1])
    if not project_account_id or not project_name:
        raise RuntimeError(f"Attachment 2 row {row_number}: project identity is incomplete")

    amounts = [money(cell) for cell in cells[2:9]]
    source_grand_total = money(cells[9])
    if source_grand_total is None:
        raise RuntimeError(f"Attachment 2 row {row_number}: project Grand Total is blank")
    computed_grand_total = sum(value_or_zero(value) for value in amounts)
    if computed_grand_total != source_grand_total:
        raise RuntimeError(
            f"Attachment 2 row {row_number} {project_account_id}: Grand Total mismatch "
            f"{computed_grand_total} != {source_grand_total}"
        )

    return {
        "record_type": "current_capital_multiyear_schedule",
        "fiscal_year": "2026/27",
        "project_account_id": project_account_id,
        "project_name": project_name,
        "schedule_class": schedule_class,
        "total_previous_years_gross_budget": amounts[0],
        "capital_budget_2025_26": amounts[1],
        "capital_budget_2026_27": amounts[2],
        "capital_budget_2027_28": amounts[3],
        "capital_budget_2028_29": amounts[4],
        "capital_budget_2029_30": amounts[5],
        "capital_budget_2030_31_to_2035_36": amounts[6],
        "grand_total": source_grand_total,
        "computed_grand_total": computed_grand_total,
        "source_id": source["id"],
        "source_page": source["attachment_pdf_page"],
        "source_table": 1,
        "source_row": row_number,
        "source_url": resolved_url,
        "raw_cells": cells,
        "approval_status": "ratified_capital_plan",
        "approval_source_id": "hrm-council-2026-03-31-budget-ratification",
        "provenance": {
            "source_id": source["id"],
            "source_url": resolved_url,
            "source_url_registry": source["previous_indexed_attachment_url"],
            "source_url_resolution": "exact_title_live_agenda_resolution",
            "source_page": source["attachment_pdf_page"],
            "locator_type": "capital-multiyear-schedule-table-row",
            "locator_value": f"attachment2/p{source['attachment_pdf_page']}/t1/r{row_number}/{project_account_id}",
            "parser_version": PARSER_VERSION,
            "retrieved_at": retrieved_at,
            "validation_status": "parsed",
        },
    }


def parse_total_row(cells: list[str]) -> dict:
    if len(cells) != 10:
        raise RuntimeError("capital total row does not have 10 cells")
    values = [money(cell) for cell in cells[2:10]]
    return dict(zip([*VALUE_FIELDS, "grand_total"], values))


def sum_records(records: list[dict]) -> dict:
    result = {}
    for field in [*VALUE_FIELDS, "grand_total"]:
        result[field] = sum(value_or_zero(row.get(field)) for row in records)
    return result


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    source = config["schedule_source"]
    approval = config["approval_source"]
    retrieved_at = config["metadata"]["last_researched"] + "T00:00:00Z"

    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    resolved_url = resolve_attachment(session, source)
    blob = fetch_pdf(session, source, resolved_url)
    source_sha256 = hashlib.sha256(blob).hexdigest()

    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        if len(pdf.pages) != 9:
            raise RuntimeError(f"revised capital PDF expected 9 pages, found {len(pdf.pages)}")
        page = pdf.pages[source["attachment_pdf_page"] - 1]
        page_text = clean(page.extract_text() or "")
        if "ATTACHMENT 2" not in page_text or "2026/27 Capital Multi-Year Projects" not in page_text:
            raise RuntimeError("Attachment 2 heading not found on configured source page")
        tables = page.extract_tables() or []
        if len(tables) != 1:
            raise RuntimeError(f"Attachment 2 expected exactly one table, found {len(tables)}")
        table = [[clean(cell) for cell in (row or [])] for row in tables[0]]

    if table[0] != EXPECTED_HEADER:
        raise RuntimeError(f"Attachment 2 header changed: {table[0]!r}")
    if len(table) != source["published_controls"]["source_table_rows"]:
        raise RuntimeError(f"Attachment 2 row-count changed: {len(table)}")

    records: list[dict] = []
    schedule_class: str | None = None
    discrete_subtotal = None
    ongoing_subtotal = None
    source_grand_total = None

    for row_number, cells in enumerate(table[1:], 2):
        first = clean(cells[0])
        second = clean(cells[1])
        if first == "Discrete Projects":
            schedule_class = "discrete_project"
            continue
        if first == "Ongoing Programs":
            schedule_class = "ongoing_program"
            continue
        if first == "Subtotal Discrete Projects":
            discrete_subtotal = parse_total_row(cells)
            continue
        if first == "Subtotal Ongoing Programs":
            ongoing_subtotal = parse_total_row(cells)
            continue
        if second == "Grand Total 2026/27 Muti-Year Projects":
            source_grand_total = parse_total_row(cells)
            continue
        if not first and not second:
            continue
        if schedule_class is None:
            raise RuntimeError(f"Attachment 2 row {row_number}: project row before schedule class")
        records.append(parse_project_row(cells, schedule_class, row_number, source, resolved_url, retrieved_at))

    if discrete_subtotal is None or ongoing_subtotal is None or source_grand_total is None:
        raise RuntimeError("Attachment 2 source control rows are incomplete")

    discrete = [row for row in records if row["schedule_class"] == "discrete_project"]
    ongoing = [row for row in records if row["schedule_class"] == "ongoing_program"]
    computed_discrete = sum_records(discrete)
    computed_ongoing = sum_records(ongoing)
    computed_all = sum_records(records)

    if computed_discrete != discrete_subtotal:
        raise RuntimeError(f"discrete-project subtotal mismatch: {computed_discrete} != {discrete_subtotal}")
    if computed_ongoing != ongoing_subtotal:
        raise RuntimeError(f"ongoing-program subtotal mismatch: {computed_ongoing} != {ongoing_subtotal}")

    grand_total_discrepancies = []
    for field, computed_value in computed_all.items():
        source_value = source_grand_total.get(field)
        if source_value != computed_value:
            grand_total_discrepancies.append({
                "field": field,
                "source_value": source_value,
                "computed_value": computed_value,
                "difference_source_minus_computed": value_or_zero(source_value) - computed_value,
            })

    expected_gap = source["known_source_discrepancy"]
    if grand_total_discrepancies != [{
        "field": "total_previous_years_gross_budget",
        "source_value": expected_gap["source_value"],
        "computed_value": expected_gap["computed_from_discrete_and_ongoing_subtotals"],
        "difference_source_minus_computed": expected_gap["difference_source_minus_computed"],
    }]:
        raise RuntimeError(f"unexpected capital Grand Total discrepancies: {grand_total_discrepancies}")

    controls = source["published_controls"]
    if len(records) != controls["project_rows"] or len(discrete) != controls["discrete_project_rows"] or len(ongoing) != controls["ongoing_program_rows"]:
        raise RuntimeError(
            f"capital project-count controls changed: total={len(records)} discrete={len(discrete)} ongoing={len(ongoing)}"
        )
    if computed_all["capital_budget_2026_27"] != controls["current_2026_27_multiyear_budget"]:
        raise RuntimeError("2026/27 multi-year capital budget control mismatch")
    if computed_all["grand_total"] != controls["source_grand_total"]:
        raise RuntimeError("multi-year project grand-total control mismatch")

    payload = {
        "metadata": {
            "dataset_status": "ratified_current_capital_multiyear_schedule",
            "parser_version": PARSER_VERSION,
            "fiscal_year": "2026/27",
            "source_id": source["id"],
            "source_agenda_url": source["agenda_url"],
            "source_url_registry": source["previous_indexed_attachment_url"],
            "source_url_resolved": resolved_url,
            "source_url_resolution": "exact_title_live_agenda_resolution",
            "source_url_changed_since_registry": resolved_url != source["previous_indexed_attachment_url"],
            "source_sha256": source_sha256,
            "source_stage": source["source_stage"],
            "source_pdf_page": source["attachment_pdf_page"],
            "source_table_rows": len(table),
            "project_rows": len(records),
            "discrete_project_rows": len(discrete),
            "ongoing_program_rows": len(ongoing),
            "current_2026_27_multiyear_budget": computed_all["capital_budget_2026_27"],
            "computed_previous_years_gross_budget": computed_all["total_previous_years_gross_budget"],
            "source_grand_total_previous_years_gross_budget": source_grand_total["total_previous_years_gross_budget"],
            "schedule_grand_total": computed_all["grand_total"],
            "source_grand_total_discrepancies": grand_total_discrepancies,
            "approval_status": "ratified_capital_plan",
            "approval_source_id": approval["id"],
            "approval_date": approval["meeting_date"],
            "approval_url": approval["url"],
            "is_complete_capital_project_ledger": False,
            "is_spend_to_date": False,
            "is_accounts_payable_ledger": False,
            "is_commitment_ledger": False,
            "is_final_project_cost": False,
            "note": "Attachment 2 is the approved 2026/27 Capital Multi-Year Projects cashflow schedule. Exact project account IDs are retained for deterministic lifecycle linking. The source Grand Total row contains one preserved previous-years arithmetic defect; project rows and both source subtotals are not rewritten.",
        },
        "source_controls": {
            "discrete_projects": discrete_subtotal,
            "ongoing_programs": ongoing_subtotal,
            "source_grand_total_row": source_grand_total,
            "computed_all_projects": computed_all,
        },
        "records": records,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(
        f"Wrote {len(records)} current multi-year capital rows: "
        f"2026/27={computed_all['capital_budget_2026_27']} grand={computed_all['grand_total']} "
        f"source_discrepancies={len(grand_total_discrepancies)}"
    )


if __name__ == "__main__":
    main()
