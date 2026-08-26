#!/usr/bin/env python3
"""Temporary Build 011 diagnostic for the replaced Apr-Jun 2026 report attachment."""
from __future__ import annotations

import argparse
import io
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests

from ingest_procurement_quarterly_reports import clean, fetch_pdf, report_documents

DIAGNOSTIC_VERSION = "build011-layout-v5"


class AnchorCollector(HTMLParser):
    def __init__(self):
        super().__init__(); self.current = None; self.anchors = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a": self.current = {"href": dict(attrs).get("href") or "", "text": []}
    def handle_data(self, data):
        if self.current is not None: self.current["text"].append(data)
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current is not None:
            self.anchors.append({"href": self.current["href"], "text": clean(" ".join(self.current["text"]))}); self.current = None


def resolve(session, report):
    try:
        return report["url"], fetch_pdf(session, report["url"]), "graph"
    except Exception:
        response = session.get(report["agenda_url"], timeout=120); response.raise_for_status()
        parser = AnchorCollector(); parser.feed(response.text)
        urls = []
        for anchor in parser.anchors:
            if clean(anchor["text"]) != clean(report["title"]): continue
            absolute = urljoin(report["agenda_url"], anchor["href"])
            if "filestream.ashx" in absolute.lower(): urls.append(absolute)
        urls = list(dict.fromkeys(urls))
        if len(urls) != 1: raise RuntimeError(f"expected one exact-title replacement, got {urls}")
        return urls[0], fetch_pdf(session, urls[0]), "exact-title-agenda"


def clip(value, limit=700):
    value = clean(value)
    return value if len(value) <= limit else value[:limit-1] + "…"


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    report = next(r for r in report_documents() if r["document_id"] == "5716")
    session = requests.Session(); session.headers["User-Agent"] = "HalifaxData/0.11 diagnostic"
    resolved_url, blob, resolution = resolve(session, report)
    pages = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            tables = []
            for table_num, raw in enumerate(page.extract_tables() or [], 1):
                table = [[clean(cell) for cell in (row or [])] for row in (raw or [])]
                tables.append({"table_num": table_num, "rows": [[clip(cell, 300) for cell in row] for row in table[:60]]})
            pages.append({"page": page_num, "text": clip(text, 6000), "tables": tables})
    payload = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "graph_url": report["url"],
        "resolved_url": resolved_url,
        "resolution": resolution,
        "title": report["title"],
        "pages": pages,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(f"captured {len(pages)} pages from {resolved_url}")


if __name__ == "__main__": main()
