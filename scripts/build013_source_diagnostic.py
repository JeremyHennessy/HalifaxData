#!/usr/bin/env python3
"""Temporary source-layout diagnostic for Build 013.

This is intentionally not a production parser. It records compact table samples so
new HRM amendment/grant sources can be mapped to explicit schemas before ingestion.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pdfplumber
import requests

UA = "HalifaxData/Build013 source diagnostic (+https://github.com/JeremyHennessy/HalifaxData)"

AMENDMENT_REPORTS = [
    ("2023-05-17", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/boards-committees-commissions/revised230517afscinfo01.pdf"),
    ("2023-09-20", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/230920afscinfo1.pdf"),
    ("2023-11-15", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/231115afscinfo1.pdf"),
    ("2024-01-17", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/boards-committees-commissions/240117afscinfo2.pdf"),
    ("2024-06-19", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/240619afscinfo3_0.pdf"),
    ("2024-10-09", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/241009afscinfo2.pdf"),
    ("2024-12-11", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/241211afscinfo2.pdf"),
    ("2025-01-15", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250115afscinfo2.pdf"),
    ("2025-04-16", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250416afscinfo2.pdf"),
    ("2025-05-21", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250521afscinfo2.pdf"),
    ("2025-06-18", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250618afscinfo2.pdf"),
    ("2025-11-25", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/251125afscinfo2.pdf"),
]

GRANT_REPORTS = [
    ("community-grants-2025", "https://pub-halifax.escribemeetings.com/filestream.ashx?DocumentId=2275"),
    ("community-grants-2026-27", "https://pub-halifax.escribemeetings.com/filestream.ashx?DocumentId=5670"),
    ("community-grants-2025-supplement", "https://pub-halifax.escribemeetings.com/filestream.ashx?DocumentId=5242"),
]


def clean(value):
    if value is None:
        return ""
    return " ".join(str(value).replace("\n", " ").split())


def inspect(session, name, url):
    item = {"name": name, "url": url, "status": None, "bytes": 0, "pages": []}
    try:
        response = session.get(url, timeout=120)
        item["status"] = response.status_code
        item["bytes"] = len(response.content)
        item["content_type"] = response.headers.get("content-type")
        if not response.ok or not response.content.startswith(b"%PDF"):
            item["error"] = "source did not return a PDF"
            return item
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            item["page_count"] = len(pdf.pages)
            for page_no, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables() or []
                if not tables:
                    continue
                page_item = {"page": page_no, "tables": []}
                for table_no, table in enumerate(tables, 1):
                    rows = [[clean(cell) for cell in row] for row in table if row]
                    page_item["tables"].append({
                        "table": table_no,
                        "row_count": len(rows),
                        "column_count": max((len(row) for row in rows), default=0),
                        "sample": rows[:18],
                    })
                item["pages"].append(page_item)
    except Exception as exc:
        item["error"] = f"{type(exc).__name__}: {exc}"
    return item


def main():
    session = requests.Session()
    session.headers["User-Agent"] = UA
    output = {
        "amendment_reports": [inspect(session, *source) for source in AMENDMENT_REPORTS],
        "grant_reports": [inspect(session, *source) for source in GRANT_REPORTS],
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/build013-source-diagnostic.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({
        "amendments": [{"name": x["name"], "status": x.get("status"), "pages_with_tables": len(x.get("pages", [])), "error": x.get("error")} for x in output["amendment_reports"]],
        "grants": [{"name": x["name"], "status": x.get("status"), "pages_with_tables": len(x.get("pages", [])), "error": x.get("error")} for x in output["grant_reports"]],
    }, indent=2))

if __name__ == "__main__":
    main()
