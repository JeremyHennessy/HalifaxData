#!/usr/bin/env python3
"""Temporary Build 012 diagnostic for new contextual finance sources. Diagnostic revision 2."""
from __future__ import annotations
import io, json
from pathlib import Path
import requests, pdfplumber

UA = "HalifaxData/Build012 source validation (+https://github.com/JeremyHennessy/HalifaxData)"
GRANT_DOCS = [
    ("community_grants_2025", "https://pub-halifax.escribemeetings.com/filestream.ashx?DocumentId=2275"),
    ("community_grants_2026", "https://pub-halifax.escribemeetings.com/filestream.ashx?DocumentId=5670"),
]
AMENDMENT_REPORTS = [
    ("2023-05-17", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/boards-committees-commissions/revised230517afscinfo01.pdf"),
    ("2023-11-15", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/231115afscinfo1.pdf"),
    ("2024-01-17", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/boards-committees-commissions/240117afscinfo2.pdf"),
    ("2024-06-19", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/240619afscinfo3_0.pdf"),
    ("2024-12-11", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/241211afscinfo2.pdf"),
    ("2025-01-15", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250115afscinfo2.pdf"),
    ("2025-04-16", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250416afscinfo2.pdf"),
    ("2025-05-21", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250521afscinfo2.pdf"),
    ("2025-06-18", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250618afscinfo2.pdf"),
    ("2025-11-25", "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/251125afscinfo2.pdf"),
]

def clean(v):
    if v is None: return ""
    return " ".join(str(v).replace("\n", " ").split())

def inspect_pdf(session, name, url):
    r = session.get(url, timeout=120)
    result = {"name": name, "url": url, "status": r.status_code, "content_type": r.headers.get("content-type"), "bytes": len(r.content), "pages": []}
    if not (r.ok and r.content.startswith(b"%PDF")):
        result["error"] = clean(r.text[:300]) if r.text else "not a PDF"
        return result
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables() or []
            if not tables: continue
            page_item = {"page": pno, "tables": []}
            for tno, table in enumerate(tables, 1):
                rows = [[clean(c) for c in row] for row in table if row]
                page_item["tables"].append({"table": tno, "rows": rows[:12], "row_count": len(rows), "columns": max((len(r) for r in rows), default=0)})
            result["pages"].append(page_item)
    return result

def main():
    session = requests.Session(); session.headers["User-Agent"] = UA
    out = {"grants": [], "contract_amendments": []}
    for item in GRANT_DOCS: out["grants"].append(inspect_pdf(session, *item))
    for item in AMENDMENT_REPORTS: out["contract_amendments"].append(inspect_pdf(session, *item))
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/build012-source-diagnostic.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({
        "grant_status": [(x["name"], x["status"], len(x.get("pages", []))) for x in out["grants"]],
        "amendment_status": [(x["name"], x["status"], len(x.get("pages", []))) for x in out["contract_amendments"]]
    }, indent=2))

if __name__ == "__main__": main()
