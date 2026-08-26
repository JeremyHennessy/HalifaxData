#!/usr/bin/env python3
"""Emit compact diagnostics for Build 011 quarterly procurement PDF layouts.

This does not publish procurement data. It records table/header structure and the
source text lines from explicit alternative-award sections so parser changes can
be based on source layout rather than guesses. Fetch failures are recorded explicitly
rather than causing the diagnostic to hide layouts from other available reports.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path

import pdfplumber
import requests

from ingest_procurement_quarterly_reports import clean, fetch_pdf, find_header_map, report_documents

DIAGNOSTIC_VERSION = "build011-layout-v3"


def clip(value: str, limit: int = 240) -> str:
    text = clean(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def page_snippets(text: str) -> list[str]:
    flat = clean(text)
    out = []
    for match in re.finditer(r"alternative\s+procurement", flat, re.I):
        start = max(0, match.start() - 180)
        end = min(len(flat), match.end() + 260)
        snippet = clip(flat[start:end], 520)
        if snippet not in out:
            out.append(snippet)
    return out[:8]


def relevant_lines(text: str) -> list[str]:
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    if not lines:
        return []
    start = next((i for i, line in enumerate(lines) if re.search(r"\balternative awards\b|\balternative procurement awards over\b", line, re.I)), None)
    if start is None and any(re.search(r"\balternative procurement\b", line, re.I) for line in lines):
        start = max(0, next(i for i, line in enumerate(lines) if re.search(r"\balternative procurement\b", line, re.I)) - 2)
    if start is None:
        return []
    selected = lines[start : start + 80]
    return [clip(line, 520) for line in selected]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = "HalifaxData/0.11 layout diagnostic"
    reports_out = []

    for report in report_documents():
        report_out = {
            "document_id": report["document_id"],
            "title": report["title"],
            "url": report["url"],
            "status": "ok",
            "pages": [],
        }
        try:
            blob = fetch_pdf(session, report["url"])
        except Exception as exc:
            report_out["status"] = "fetch_error"
            report_out["error"] = f"{type(exc).__name__}: {exc}"
            reports_out.append(report_out)
            continue
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                snippets = page_snippets(text)
                section_lines = relevant_lines(text)
                tables_out = []
                for table_num, raw_table in enumerate(page.extract_tables() or [], 1):
                    table = [[clean(cell) for cell in (row or [])] for row in (raw_table or [])]
                    flat = " | ".join(" | ".join(row) for row in table)
                    header = find_header_map(table)
                    interesting = bool(section_lines) or bool(re.search(r"alternative\s+procurement", flat, re.I)) or header is not None
                    if not interesting:
                        continue
                    header_map = None
                    if header:
                        header_map = {"row_index": header[0], "mapping": header[1]}
                    tables_out.append({
                        "table_num": table_num,
                        "row_count": len(table),
                        "header": header_map,
                        "rows": [[clip(cell, 180) for cell in row] for row in table[:30]],
                    })
                if snippets or section_lines or tables_out:
                    report_out["pages"].append({
                        "page": page_num,
                        "alternative_snippets": snippets,
                        "alternative_section_lines": section_lines,
                        "tables": tables_out,
                    })
        reports_out.append(report_out)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"diagnostic_version": DIAGNOSTIC_VERSION, "reports": reports_out}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote layout diagnostics for {len(reports_out)} reports")


if __name__ == "__main__":
    main()
