#!/usr/bin/env python3
"""Collect HRM quarterly Award of Contracts reports from the checked-in Council graph.

Build 011 treats the quarterly reports as a separate procurement-evidence layer.
Alternative Procurement rows are source-declared non-competitive/alternative awards;
we do not infer alternative procurement from the public-tender dataset.

Report coverage begins with the first recurring report present in the checked-in
Council/eSCRIBE document graph. The published reporting threshold is preserved:
Alternative Procurement awards reported by this series are those exceeding $50,000.
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
COUNCIL_DOCS = ROOT / "data" / "generated" / "council_documents.json"
DEFAULT_OUT = ROOT / "data" / "generated" / "procurement_quarterly.json"
UA = "HalifaxData/0.11 (+https://github.com/JeremyHennessy/HalifaxData)"
PARSER_VERSION = "build011-procurement-quarterly-v1"
REPORT_TITLE_RE = re.compile(r"Award of Contracts\s*[-–—]\s*Quarterly Report", re.I)
ALT_TITLE_RE = re.compile(r"\bAward\s*[-–—]?\s*Alternative Procurement\b", re.I)
SOLICITATION_RE = re.compile(r"\b(20\d{2}-\d{2,5})\b")
MONEY_RE = re.compile(r"\(?\$?\s*-?\s*\d[\d,]*(?:\.\d+)?\)?")


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
            "source_id": row.get("source_id") or "hrm-escribe",
        })
    rows.sort(key=lambda row: str(row.get("meeting_start_date") or ""))
    return rows


def fetch_pdf(session: requests.Session, url: str) -> bytes:
    response = session.get(url, timeout=180)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise RuntimeError(f"Expected PDF from {url}; got {response.headers.get('content-type')!r}")
    return response.content


def summary_controls(text: str) -> dict:
    normalized = clean(text)
    count_patterns = [
        re.compile(r"Total number of Alternative Procurement Awards exceeding \$50,000\s*=\s*(\d+)", re.I),
        re.compile(r"Alternative procurements\s*[-–—]\s*(\d+)\s+or\s+\d+%", re.I),
        re.compile(r"Alternative Procurement Awards[^\n]{0,120}?=\s*(\d+)\b", re.I),
    ]
    value_patterns = [
        re.compile(r"Value of Alternative Procurement Awards exceeding \$50,000\s*=\s*\$?([\d,]+(?:\.\d+)?)", re.I),
        re.compile(r"Value of Alternative Procurement Awards[^\n]{0,100}?\$([\d,]+(?:\.\d+)?)", re.I),
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


def find_header_map(table: list[list[str]]) -> tuple[int, dict] | None:
    for index, row in enumerate(table[:8]):
        headers = [normalize_header(cell) for cell in row]
        mapping = {}
        for col, header in enumerate(headers):
            if "title of report" in header or header in {"title", "report"}:
                mapping.setdefault("title", col)
            elif "name of company" in header or "successful supplier" in header or "company" == header:
                mapping.setdefault("vendor", col)
            elif "bid price" in header or "contract amount" in header or "award amount" in header:
                mapping.setdefault("award", col)
            elif "budget cost estimate" in header or "budgetary estimate" in header or ("budget" in header and "estimate" in header):
                mapping.setdefault("budget", col)
            elif "account" in header:
                mapping.setdefault("account", col)
            elif "details" in header or "cost share" in header or "reason" in header:
                mapping.setdefault("details", col)
        if {"title", "vendor", "award"}.issubset(mapping):
            return index, mapping
    return None


def table_rows(page) -> list[tuple[int, int, list[str], dict]]:
    results = []
    for table_num, raw_table in enumerate(page.extract_tables() or [], 1):
        table = [[clean(cell) for cell in (row or [])] for row in (raw_table or [])]
        header = find_header_map(table)
        if not header:
            continue
        header_index, mapping = header
        for row_num, cells in enumerate(table[header_index + 1 :], header_index + 2):
            results.append((table_num, row_num, cells, mapping))
    return results


def cell(cells: list[str], mapping: dict, key: str) -> str:
    index = mapping.get(key)
    return clean(cells[index]) if index is not None and index < len(cells) else ""


def period_from_title(title: str) -> str:
    match = re.search(r"Quarterly Report\s+(.+?)\.pdf$", title, re.I)
    return clean(match.group(1)) if match else title


def parse_report(session: requests.Session, report: dict) -> tuple[dict, list[dict], list[dict]]:
    blob = fetch_pdf(session, report["url"])
    alternatives = []
    competitive = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        page_texts = []
        for page_num, page in enumerate(pdf.pages, 1):
            page_texts.append(page.extract_text() or "")
            for table_num, row_num, cells, mapping in table_rows(page):
                title = cell(cells, mapping, "title")
                vendor = cell(cells, mapping, "vendor")
                award_raw = cell(cells, mapping, "award")
                if not title or not vendor or money(award_raw) is None:
                    continue
                award_value = money(award_raw)
                budget_value = money(cell(cells, mapping, "budget"))
                details = cell(cells, mapping, "details")
                account = cell(cells, mapping, "account")
                solicitation_match = SOLICITATION_RE.search(title)
                record = {
                    "report_document_id": report["document_id"],
                    "report_meeting_id": report["meeting_id"],
                    "report_meeting_start_date": report["meeting_start_date"],
                    "report_title": report["title"],
                    "report_period": period_from_title(report["title"]),
                    "award_title": title,
                    "solicitation": solicitation_match.group(1) if solicitation_match else None,
                    "vendor_name": clean(vendor).rstrip("*").strip(),
                    "award_value": award_value,
                    "budget_cost_estimate": budget_value,
                    "account_project_codes": account,
                    "source_details": details,
                    "source_id": "hrm-escribe",
                    "source_url": report["url"],
                    "source_page": page_num,
                    "source_table": table_num,
                    "source_row": row_num,
                    "provenance": {
                        "source_id": "hrm-escribe",
                        "source_url": report["url"],
                        "retrieved_at": now(),
                        "locator_type": "quarterly-award-report-table-row",
                        "locator_value": f"doc{report['document_id']}/p{page_num}/t{table_num}/r{row_num}",
                        "parser_version": PARSER_VERSION,
                        "validation_status": "parsed",
                    },
                }
                if ALT_TITLE_RE.search(title):
                    record["procurement_class"] = "alternative_procurement"
                    alternatives.append(record)
                else:
                    record["procurement_class"] = "competitive_or_other_reported_award"
                    competitive.append(record)
        text = "\n".join(page_texts)
    controls = summary_controls(text)
    report_meta = {
        **report,
        "report_period": period_from_title(report["title"]),
        **controls,
        "parsed_alternative_rows": len(alternatives),
        "parsed_alternative_value": round(sum(row["award_value"] for row in alternatives), 2),
        "parsed_competitive_or_other_rows": len(competitive),
    }
    return report_meta, alternatives, competitive


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
    competitive = []
    for report in reports:
        meta, alt_rows, other_rows = parse_report(session, report)
        report_status.append(meta)
        alternatives.extend(alt_rows)
        competitive.extend(other_rows)
        print(
            f"{report['document_id']} {meta['report_period']}: alternatives={len(alt_rows)} "
            f"value={meta['parsed_alternative_value']:.2f} control_count={meta['alternative_count']} "
            f"control_value={meta['alternative_value']} other={len(other_rows)}"
        )

    unique = {}
    for row in alternatives:
        key = (row["report_document_id"], row["award_title"], row["vendor_name"], row["award_value"])
        unique.setdefault(key, row)
    alternatives = list(unique.values())

    payload = {
        "metadata": {
            "dataset_status": "official_quarterly_award_reports",
            "parser_version": PARSER_VERSION,
            "generated_at": now(),
            "report_count": len(report_status),
            "alternative_procurement_rows": len(alternatives),
            "alternative_procurement_value": round(sum(row["award_value"] for row in alternatives), 2),
            "alternative_reporting_threshold": 50000,
            "is_accounts_payable_ledger": False,
            "is_complete_procurement_ledger": False,
            "note": (
                "HRM quarterly Award of Contracts report evidence. Alternative Procurement rows are source-declared "
                "awards exceeding the report's $50,000 reporting threshold. This is not an accounts-payable ledger, "
                "does not contain every purchase or payment, and must not be combined with public-tender awards "
                "without preserving source/classification boundaries."
            ),
        },
        "reports": report_status,
        "alternative_procurement": alternatives,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print(f"Wrote {len(alternatives)} alternative-procurement rows across {len(report_status)} reports")


if __name__ == "__main__":
    main()
