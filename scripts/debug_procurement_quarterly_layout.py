#!/usr/bin/env python3
"""Temporary Build 011 source/layout diagnostic.

Never publishes data. It records source table structure and, when an attachment URL
fails, re-reads the owning eSCRIBE agenda page and captures current attachment links
whose text references Award of Contracts.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests

from ingest_procurement_quarterly_reports import clean, fetch_pdf, find_modern_alt_header, report_documents

DIAGNOSTIC_VERSION = "build011-layout-v4"


class AnchorCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        self.current = {"href": href or "", "text": []}

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"].append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current is not None:
            self.anchors.append({"href": self.current["href"], "text": clean(" ".join(self.current["text"]))})
            self.current = None


def clip(value: str, limit: int = 520) -> str:
    text = clean(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def agenda_candidates(session: requests.Session, report: dict) -> dict:
    url = report.get("agenda_url")
    result = {"agenda_url": url, "status": "not_checked", "candidates": []}
    if not url:
        return result
    try:
        response = session.get(url, timeout=90)
        result["http_status"] = response.status_code
        response.raise_for_status()
        parser = AnchorCollector()
        parser.feed(response.text)
        candidates = []
        for anchor in parser.anchors:
            href = anchor["href"]
            text = anchor["text"]
            if not href:
                continue
            if re.search(r"award of contracts", text, re.I) or ("filestream.ashx" in href.lower() and re.search(r"quarterly report", text, re.I)):
                candidates.append({"text": clip(text), "href": urljoin(url, href)})
        result["status"] = "ok"
        result["candidates"] = candidates
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def relevant_lines(text: str) -> list[str]:
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    start = next((i for i, line in enumerate(lines) if re.search(r"\balternative awards\b|\balternative procurement awards over\b", line, re.I)), None)
    if start is None:
        return []
    return [clip(line) for line in lines[start : start + 80]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = "HalifaxData/0.11 source diagnostic"
    reports_out = []

    for report in report_documents():
        out = {
            "document_id": report["document_id"],
            "meeting_id": report.get("meeting_id"),
            "title": report["title"],
            "url": report["url"],
            "agenda_url": report.get("agenda_url"),
            "status": "ok",
            "pages": [],
        }
        try:
            blob = fetch_pdf(session, report["url"])
        except Exception as exc:
            out["status"] = "fetch_error"
            out["error"] = f"{type(exc).__name__}: {exc}"
            out["agenda_resolution"] = agenda_candidates(session, report)
            reports_out.append(out)
            continue
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                lines = relevant_lines(text)
                tables = []
                for table_num, raw in enumerate(page.extract_tables() or [], 1):
                    table = [[clean(cell) for cell in (row or [])] for row in (raw or [])]
                    modern = find_modern_alt_header(table)
                    has_alt = any(re.search(r"alternative (?:procurement|awards?)", clean(" ".join(row)), re.I) for row in table)
                    if not lines and not modern and not has_alt:
                        continue
                    tables.append({
                        "table_num": table_num,
                        "row_count": len(table),
                        "modern_alt_header": modern,
                        "rows": [[clip(cell, 180) for cell in row] for row in table[:30]],
                    })
                if lines or tables:
                    out["pages"].append({"page": page_num, "alternative_section_lines": lines, "tables": tables})
        reports_out.append(out)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"diagnostic_version": DIAGNOSTIC_VERSION, "reports": reports_out}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote source diagnostics for {len(reports_out)} reports")


if __name__ == "__main__":
    main()
