#!/usr/bin/env python3
"""Collect HRM quarterly Award of Contracts report alternative-procurement evidence.

Build 011 treats these quarterly reports as a procurement-evidence layer separate
from the Nova Scotia public-tender award dataset. Rows are included because HRM
places them in the report's controlled Alternative Awards / Alternative Procurement
appendix section; the row's literal procurement-type field is preserved separately.

The report wording describes Alternative Procurement awards exceeding $50,000.
Some source appendices include rows at exactly $50,000; those rows are retained so
that extracted rows reconcile to the municipality's published report controls.

This is not an accounts-payable ledger and is not a complete procurement ledger.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests

ROOT = Path(__file__).resolve().parents[1]
COUNCIL_DOCS = ROOT / "data" / "generated" / "council_documents.json"
DEFAULT_OUT = ROOT / "data" / "generated" / "procurement_quarterly.json"
UA = "HalifaxData/0.11 (+https://github.com/JeremyHennessy/HalifaxData)"
PARSER_VERSION = "build011-procurement-quarterly-v2"
REPORT_TITLE_RE = re.compile(r"Award of Contracts\s*[-–—]\s*Quarterly Report", re.I)
MONEY_RE = re.compile(r"\(?\$?\s*-?\s*\d[\d,]*(?:\.\d+)?\)?")
SOLICITATION_RE = re.compile(r"\b(?:HRM-)?((?:20)?\d{2})-\s*(\d{3,5})\b", re.I)
ALT_MARKER_RE = re.compile(r"^Alternative Awards$", re.I)
NET_TOTAL_RE = re.compile(r"^Net Total\b", re.I)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()


def money(value):
    text = clean(value).replace("**", "").replace("*", "")
    if not text or text in {"-", "$ -", "$-", "—"}:
        return None
    match = MONEY_RE.search(text)
    if not match:
        return None
    raw = clean(match.group())
    negative = raw.startswith("(") and raw.endswith(")")
    compact = raw.replace("$", "").replace(",", "").replace(" ", "")
    if negative:
        compact = compact[1:-1]
    try:
        value = float(compact)
    except ValueError:
        return None
    return round(-value if negative else value, 2)


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()


def report_documents() -> list[dict]:
    payload = json.loads(COUNCIL_DOCS.read_text(encoding="utf-8"))
    rows = []
    for row in payload.get("records") or []:
        title = clean(row.get("title"))
        if not REPORT_TITLE_RE.search(title):
            continue
        rows.append({
            "document_id": str(row.get("document_id") or ""),
            "meeting_id": row.get("meeting_id"),
            "meeting_start_date": row.get("meeting_start_date"),
            "title": title,
            "url": row.get("url"),
            "agenda_url": row.get("agenda_url"),
            "source_id": row.get("source_id") or "hrm-escribe",
        })
    rows.sort(key=lambda row: str(row.get("meeting_start_date") or ""))
    return rows


def fetch_pdf(session: requests.Session, url: str) -> bytes:
    last_error = None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=180)
            response.raise_for_status()
            if not response.content.startswith(b"%PDF"):
                raise RuntimeError(f"Expected PDF from {url}; got {response.headers.get('content-type')!r}")
            return response.content
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Unable to reproduce quarterly report PDF after 3 attempts: {url}: {last_error}")


def summary_controls(text: str) -> dict:
    normalized = clean(text)
    count_patterns = [
        re.compile(r"Total number of Alternative Procurement Awards exceeding \$50,000\s*[:=]\s*(\d+)", re.I),
        re.compile(r"Alternative procurements\s*[-–—]\s*(\d+)\s+or\s+\d+%", re.I),
    ]
    value_patterns = [
        re.compile(r"Value of Alternative Procurement Awards exceeding \$50,000\s*[:=]\s*\$?\s*\$?\s*([\d,]+(?:\.\d+)?)", re.I),
    ]
    count = None
    value = None
    for pattern in count_patterns:
        match = pattern.search(normalized)
        if match:
            count = int(match.group(1))
            break
    for pattern in value_patterns:
        match = pattern.search(normalized)
        if match:
            value = float(match.group(1).replace(",", ""))
            break
    return {"alternative_count": count, "alternative_value": value}


def period_from_title(title: str) -> str:
    match = re.search(r"Quarterly Report\s+(.+?)\.pdf$", title, re.I)
    return clean(match.group(1)) if match else title


def solicitation_from_text(value: str) -> str | None:
    match = SOLICITATION_RE.search(clean(value))
    if not match:
        return None
    year, number = match.groups()
    if len(year) == 2:
        year = f"20{year}"
    return f"{year}-{number}"


def provenance(report: dict, page_num: int, table_num: int, row_num: int, schema: str) -> dict:
    return {
        "source_id": "hrm-escribe",
        "source_url": report["url"],
        "retrieved_at": now(),
        "locator_type": "quarterly-award-report-table-row",
        "locator_value": f"doc{report['document_id']}/p{page_num}/t{table_num}/r{row_num}",
        "parser_version": PARSER_VERSION,
        "validation_status": "parsed",
        "source_schema": schema,
    }


def base_record(report: dict, page_num: int, table_num: int, row_num: int) -> dict:
    return {
        "report_document_id": report["document_id"],
        "report_meeting_id": report["meeting_id"],
        "report_meeting_start_date": report["meeting_start_date"],
        "report_title": report["title"],
        "report_period": period_from_title(report["title"]),
        "source_id": "hrm-escribe",
        "source_url": report["url"],
        "source_page": page_num,
        "source_table": table_num,
        "source_row": row_num,
        "procurement_class": "reported_alternative_procurement_section",
        "source_report_section": "alternative_procurement_over_50000",
    }


def nearest_vendor(cells: list[str], title_index: int, amount_index: int) -> str:
    for index in range(amount_index - 1, title_index, -1):
        candidate = clean(cells[index]).rstrip("*").strip()
        if not candidate:
            continue
        if re.fullmatch(r"Alternative (?:Procurement|Award)", candidate, re.I):
            continue
        return candidate
    return ""


def nearest_reference(cells: list[str], amount_index: int) -> str:
    for index in range(amount_index + 1, len(cells)):
        candidate = clean(cells[index])
        if not candidate or money(candidate) is not None:
            continue
        if re.search(r"Alternative (?:Procurement|Award)", candidate, re.I):
            continue
        return candidate
    return ""


def old_section_rows(pdf, report: dict) -> list[dict]:
    rows = []
    in_section = False
    for page_num, page in enumerate(pdf.pages, 1):
        for table_num, raw_table in enumerate(page.extract_tables() or [], 1):
            table = [[clean(cell) for cell in (row or [])] for row in (raw_table or [])]
            for row_num, cells in enumerate(table, 1):
                nonempty = [cell for cell in cells if cell]
                joined = clean(" ".join(nonempty))
                if any(ALT_MARKER_RE.fullmatch(cell) for cell in nonempty):
                    in_section = True
                    continue
                if in_section and (NET_TOTAL_RE.match(joined) or any(NET_TOTAL_RE.match(cell) for cell in nonempty)):
                    in_section = False
                    continue
                if not in_section or not nonempty:
                    continue
                title_index = next((i for i, cell_value in enumerate(cells) if cell_value), None)
                if title_index is None:
                    continue
                amount_index = next((i for i, cell_value in enumerate(cells) if i > title_index and money(cell_value) is not None), None)
                if amount_index is None:
                    continue
                award_value = money(cells[amount_index])
                if award_value is None or award_value < 50_000:
                    continue
                title = clean(cells[title_index]).lstrip("").strip()
                vendor = nearest_vendor(cells, title_index, amount_index)
                reference = nearest_reference(cells, amount_index)
                source_type = next((clean(cell_value) for cell_value in cells if re.search(r"Alternative (?:Procurement|Award)", clean(cell_value), re.I)), "Alternative report section")
                record = {
                    **base_record(report, page_num, table_num, row_num),
                    "source_schema": "legacy_alternative_awards_table",
                    "solicitation": solicitation_from_text(title),
                    "project_number": None,
                    "award_title": title,
                    "vendor_name": vendor,
                    "supplier_source_text": vendor,
                    "award_value": award_value,
                    "budget_cost_estimate": None,
                    "account_project_codes": reference,
                    "department": None,
                    "procurement_type_source": source_type,
                    "source_details": clean(" | ".join(cell_value for cell_value in cells[amount_index + 1 :] if cell_value)),
                    "raw_cells": cells,
                    "provenance": provenance(report, page_num, table_num, row_num, "legacy_alternative_awards_table"),
                }
                rows.append(record)
    return rows


def find_modern_alt_header(table: list[list[str]]) -> tuple[int, dict] | None:
    for index, row in enumerate(table[:6]):
        headers = [normalize_header(cell) for cell in row]
        if any("source published" in h or "actual award amount" in h or "completed submissions" in h for h in headers):
            continue
        mapping = {}
        for col, header in enumerate(headers):
            if header == "project number":
                mapping["project_number"] = col
            elif header == "project name":
                mapping["project_name"] = col
            elif header == "procurement type":
                mapping["procurement_type"] = col
            elif header in {"awarded summary", "supplier", "awarded supplier"}:
                mapping["supplier"] = col
            elif header in {"award total project value", "project value"}:
                mapping["value"] = col
            elif header in {"internal reference", "cost centre project number", "cost center project number"}:
                mapping["reference"] = col
            elif header == "department":
                mapping["department"] = col
        if {"project_number", "project_name", "procurement_type", "supplier", "value"}.issubset(mapping):
            return index, mapping
    return None


def mapped(cells: list[str], mapping: dict, key: str) -> str:
    index = mapping.get(key)
    return clean(cells[index]) if index is not None and index < len(cells) else ""


def supplier_from_summary(value: str) -> str:
    text = clean(value)
    if not text:
        return ""
    patterns = [
        re.compile(r"^Awarded to\s+(.+?)(?:\s+on\s+[A-Za-z]+\s+\d|\s+on\s+\d|\s+for\s+\$|\s+\$[\d,]|$)", re.I),
        re.compile(r"^Awarded\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}\s+to\s+(.+?)(?:\s+for\s+\$|\s+\$[\d,]|$)", re.I),
        re.compile(r"^Awarded\s+to\s+(.+)$", re.I),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return clean(match.group(1)).rstrip(".,")
    return text


def modern_section_rows(pdf, report: dict) -> list[dict]:
    rows = []
    for page_num, page in enumerate(pdf.pages, 1):
        for table_num, raw_table in enumerate(page.extract_tables() or [], 1):
            table = [[clean(cell) for cell in (row or [])] for row in (raw_table or [])]
            header = find_modern_alt_header(table)
            if not header:
                continue
            header_index, mapping = header
            for row_num, cells in enumerate(table[header_index + 1 :], header_index + 2):
                project_number = mapped(cells, mapping, "project_number")
                project_name = mapped(cells, mapping, "project_name")
                if not project_number or not project_name:
                    continue
                source_summary = mapped(cells, mapping, "supplier")
                value_text = mapped(cells, mapping, "value")
                award_value = money(value_text)
                if award_value is None:
                    award_value = money(source_summary)
                if award_value is None or award_value < 50_000:
                    continue
                procurement_type = mapped(cells, mapping, "procurement_type")
                reference = mapped(cells, mapping, "reference")
                department = mapped(cells, mapping, "department")
                record = {
                    **base_record(report, page_num, table_num, row_num),
                    "source_schema": "modern_dedicated_alternative_table",
                    "solicitation": solicitation_from_text(project_number),
                    "project_number": project_number,
                    "award_title": project_name,
                    "vendor_name": supplier_from_summary(source_summary),
                    "supplier_source_text": source_summary,
                    "award_value": award_value,
                    "budget_cost_estimate": None,
                    "account_project_codes": reference,
                    "department": department,
                    "procurement_type_source": procurement_type,
                    "source_details": source_summary,
                    "raw_cells": cells,
                    "provenance": provenance(report, page_num, table_num, row_num, "modern_dedicated_alternative_table"),
                }
                rows.append(record)
    return rows


def parse_report(session: requests.Session, report: dict) -> tuple[dict, list[dict]]:
    blob = fetch_pdf(session, report["url"])
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        controls = summary_controls(text)
        modern = modern_section_rows(pdf, report)
        alternatives = modern if modern else old_section_rows(pdf, report)

    unique = {}
    for row in alternatives:
        key = (row["report_document_id"], row["source_page"], row["source_table"], row["source_row"])
        if key in unique:
            raise RuntimeError(f"Duplicate source locator in {report['title']}: {key}")
        unique[key] = row
    alternatives = list(unique.values())
    parsed_value = round(sum(row["award_value"] for row in alternatives), 2)
    control_count = controls.get("alternative_count")
    control_value = controls.get("alternative_value")
    if control_count is None:
        raise RuntimeError(f"No published alternative-procurement count control found in {report['title']}")
    if len(alternatives) != control_count:
        raise RuntimeError(
            f"Alternative-procurement count mismatch in {report['title']}: parsed={len(alternatives)} published={control_count}"
        )
    if control_value is not None and abs(parsed_value - control_value) > 0.02:
        raise RuntimeError(
            f"Alternative-procurement value mismatch in {report['title']}: parsed={parsed_value:.2f} published={control_value:.2f}"
        )
    report_meta = {
        **report,
        "report_period": period_from_title(report["title"]),
        **controls,
        "source_schema": alternatives[0]["source_schema"] if alternatives else None,
        "parsed_alternative_rows": len(alternatives),
        "parsed_alternative_value": parsed_value,
        "control_count_reconciled": True,
        "control_value_reconciled": control_value is None or abs(parsed_value - control_value) <= 0.02,
    }
    return report_meta, alternatives


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    reports = report_documents()
    if len(reports) < 8:
        raise RuntimeError(f"Only {len(reports)} recurring quarterly Award of Contracts reports discovered")

    session = requests.Session()
    session.headers["User-Agent"] = UA
    report_status = []
    alternatives = []
    for report in reports:
        meta, alt_rows = parse_report(session, report)
        report_status.append(meta)
        alternatives.extend(alt_rows)
        print(
            f"{report['document_id']} {meta['report_period']}: alternatives={len(alt_rows)} "
            f"value={meta['parsed_alternative_value']:.2f} published_count={meta['alternative_count']} "
            f"published_value={meta['alternative_value']} schema={meta['source_schema']}"
        )

    keys = set()
    for row in alternatives:
        key = (row["report_document_id"], row["source_page"], row["source_table"], row["source_row"])
        if key in keys:
            raise RuntimeError(f"Duplicate source locator across final artifact: {key}")
        keys.add(key)

    exact_threshold_rows = sum(1 for row in alternatives if abs(row["award_value"] - 50_000) <= 0.005)
    payload = {
        "metadata": {
            "dataset_status": "official_quarterly_alternative_procurement_report_sections",
            "parser_version": PARSER_VERSION,
            "generated_at": now(),
            "report_count": len(report_status),
            "alternative_procurement_rows": len(alternatives),
            "alternative_procurement_value": round(sum(row["award_value"] for row in alternatives), 2),
            "alternative_reporting_threshold_wording": "awards exceeding $50,000",
            "source_rows_at_exact_threshold": exact_threshold_rows,
            "threshold_handling": (
                "Rows at exactly $50,000 are retained when HRM includes them inside the report-controlled "
                "Alternative Procurement appendix; this preserves exact reconciliation to the source report."
            ),
            "is_accounts_payable_ledger": False,
            "is_complete_procurement_ledger": False,
            "is_final_paid_value": False,
            "note": (
                "HRM quarterly Award of Contracts report evidence. Records are the rows placed by HRM inside "
                "the controlled Alternative Awards / Alternative Procurement appendix section. The literal "
                "source procurement type is retained separately because report-section membership and the row's "
                "procurement-type field are not always identical. This is not an accounts-payable ledger, does "
                "not contain every purchase or payment, and must not be combined with public-tender award values "
                "without preserving source and classification boundaries."
            ),
        },
        "reports": report_status,
        "alternative_procurement": alternatives,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print(f"Wrote {len(alternatives)} report-controlled alternative-procurement rows across {len(report_status)} reports")


if __name__ == "__main__":
    main()
