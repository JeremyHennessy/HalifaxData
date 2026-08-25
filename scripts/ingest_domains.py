#!/usr/bin/env python3
"""Build independent public-finance domain artifacts.

Each domain is isolated: procurement, capital, budget documents, financial
statements and council discovery report their own status. A failure in one domain
must not prevent successful domains from being written.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "sources.json"
OUT = ROOT / "data" / "generated"
UA = "HalifaxData/0.2 (+https://github.com/JeremyHennessy/HalifaxData)"
SODA_AWARDED = "https://data.novascotia.ca/resource/m6ps-8j6u.json"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def money(value):
    if value is None:
        return None
    s = clean(value).replace("$", "").replace(",", "").replace(" ", "")
    if s in {"", "-", "—", "–"}:
        return None
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    s = re.sub(r"[^0-9.\-]", "", s)
    if not s or s in {"-", "."}:
        return None
    try:
        n = float(s)
        return round(-n if negative else n, 2)
    except ValueError:
        return None


def source(registry: dict, source_id: str) -> dict:
    return next(item for item in registry["sources"] if item["id"] == source_id)


def write(name: str, payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def provenance(source_id: str, url: str, locator_type: str, locator_value: str, parser_version: str = "build003-v1") -> dict:
    return {
        "source_id": source_id,
        "source_url": url,
        "retrieved_at": now(),
        "locator_type": locator_type,
        "locator_value": locator_value,
        "parser_version": parser_version,
        "validation_status": "parsed",
    }


def fetch_pdf(session: requests.Session, src: dict) -> bytes:
    response = session.get(src["url"], timeout=120)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise RuntimeError(f"{src['id']} did not return a PDF ({response.headers.get('content-type')})")
    return response.content


# ----------------------------- Procurement -----------------------------

def ingest_procurement(session: requests.Session) -> dict:
    params = {
        "$limit": 50000,
        "$where": "upper(entity) like '%HALIFAX%'",
        "$order": "awarded_date DESC",
    }
    response = session.get(SODA_AWARDED, params=params, timeout=120)
    response.raise_for_status()
    raw_rows = response.json()
    rows = []
    for item in raw_rows:
        entity = clean(item.get("entity"))
        # Keep HRM/Halifax municipal bodies; do not silently mix unrelated Halifax-named organizations.
        entity_norm = entity.lower()
        if not any(token in entity_norm for token in ["halifax regional municipality", "halifax water", "halifax public libraries"]):
            continue
        tender_id = clean(item.get("tender_id"))
        vendor = clean(item.get("vendor"))
        amount = money(item.get("awarded_amount"))
        categories = [clean(item.get(k)) for k in ("goods", "service", "construction") if clean(item.get(k))]
        rows.append(
            {
                "award_id": tender_id,
                "solicitation": tender_id,
                "vendor_name": vendor,
                "entity": entity,
                "method": "Public tender",
                "category": " / ".join(categories) or None,
                "description": clean(item.get("tender_description")),
                "tender_start_date": item.get("tender_start_date"),
                "tender_close_date": item.get("tender_close_date"),
                "awarded_date": item.get("awarded_date"),
                "original_award_value": amount,
                "current_contract_value": amount,
                "source_id": "ns-awarded-tenders-socrata",
                "provenance": provenance("ns-awarded-tenders-socrata", SODA_AWARDED, "api-record", tender_id or vendor),
            }
        )
    return {
        "metadata": {
            "generated_at": now(),
            "dataset": "Nova Scotia Awarded Public Tenders filtered to HRM/Halifax municipal bodies",
            "source_dataset_id": "m6ps-8j6u",
            "records": len(rows),
            "note": "Public-tender awards are not a complete accounts-payable ledger and do not include every alternative procurement or later contract amendment.",
        },
        "records": rows,
    }


# ------------------------------- Capital -------------------------------

def ingest_capital(session: requests.Session, registry: dict) -> dict:
    src = source(registry, "hrm-open-capital")
    layer_url = src["url"]
    response = session.get(
        layer_url + "/query",
        params={
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        },
        timeout=120,
    )
    response.raise_for_status()
    geo = response.json()
    features = geo.get("features", [])
    rows = []
    for feature in features:
        attrs = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") if geometry.get("type") == "Point" else None
        rows.append(
            {
                "project_id": clean(attrs.get("GLOBALID")) or clean(attrs.get("OBJECTID")),
                "project_code": clean(attrs.get("PROJ_NO")),
                "project_name": clean(attrs.get("PROJ_NAME")),
                "category": clean(attrs.get("CATEGORY")),
                "asset_type": clean(attrs.get("ASSET_TYPE")),
                "fiscal_year": attrs.get("YEAR"),
                "location_id": clean(attrs.get("LOC_ID")),
                "location_description": clean(attrs.get("LOC_DESC")),
                "work_description": clean(attrs.get("WORK_DESC")),
                "source_link": clean(attrs.get("LINK")),
                "longitude": coords[0] if coords and len(coords) > 1 else None,
                "latitude": coords[1] if coords and len(coords) > 1 else None,
                "status": "historical planned project",
                "source_id": src["id"],
                "provenance": provenance(src["id"], layer_url, "api-record", str(attrs.get("OBJECTID", ""))),
            }
        )
    years = sorted({r["fiscal_year"] for r in rows if r["fiscal_year"] is not None})
    return {
        "metadata": {
            "generated_at": now(),
            "records": len(rows),
            "years": years,
            "historical": True,
            "note": "The ArcGIS service is an official historical project layer and must not be represented as the current capital universe.",
        },
        "records": rows,
    }


# ----------------------------- PDF indexing -----------------------------

def infer_page_context(text: str) -> str:
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    skip = {
        "halifax",
        "budget and business plan",
        "statement of compensation",
        "table of contents",
    }
    for line in lines[:12]:
        low = line.lower()
        if any(marker in low for marker in ["budget and business plan", "year ended march", "halifax regional municipality"]):
            continue
        if low not in skip and not re.fullmatch(r"[A-Z]\d+", line):
            return line[:180]
    return ""


def flatten_header(table: list[list[str]], max_rows: int = 3) -> list[str]:
    width = max((len(row or []) for row in table[:max_rows]), default=0)
    headers = []
    for col in range(width):
        parts = []
        for row in table[:max_rows]:
            if col < len(row or []):
                value = clean(row[col])
                if value and value not in parts:
                    parts.append(value)
        headers.append(" ".join(parts))
    return headers


def budget_records_from_table(table, page_num: int, context: str, source_id: str, url: str, fiscal_label: str) -> list[dict]:
    if not table or len(table) < 2:
        return []
    table = [[clean(cell) for cell in (row or [])] for row in table]
    header_rows = min(3, len(table))
    headers = flatten_header(table, header_rows)
    joined = " | ".join(headers).lower()
    if "actual" not in joined or "budget" not in joined:
        return []
    label_idx = 0
    actual_idx = next((i for i, h in enumerate(headers) if "actual" in h.lower()), None)
    projection_idx = next((i for i, h in enumerate(headers) if "project" in h.lower() or "forecast" in h.lower()), None)
    budget_candidates = [i for i, h in enumerate(headers) if "budget" in h.lower() and "Δ" not in h and "var" not in h.lower()]
    if actual_idx is None or not budget_candidates:
        return []
    current_budget_idx = budget_candidates[-1]
    prior_budget_idx = budget_candidates[-2] if len(budget_candidates) >= 2 else None
    rows = []
    for row_index, row in enumerate(table[header_rows:], start=header_rows):
        if len(row) <= max(filter(lambda x: x is not None, [label_idx, actual_idx, projection_idx, current_budget_idx, prior_budget_idx])):
            continue
        label = clean(row[label_idx])
        if not label or label.lower() in {"expenditures", "revenues"}:
            continue
        actual = money(row[actual_idx])
        current_budget = money(row[current_budget_idx])
        projection = money(row[projection_idx]) if projection_idx is not None and projection_idx < len(row) else None
        prior_budget = money(row[prior_budget_idx]) if prior_budget_idx is not None and prior_budget_idx < len(row) else None
        if all(value is None for value in [actual, prior_budget, projection, current_budget]):
            continue
        rows.append(
            {
                "fiscal_year": fiscal_label,
                "business_unit": context or None,
                "service_area": label,
                "prior_actual": actual,
                "prior_budget": prior_budget,
                "projection": projection,
                "current_budget": current_budget,
                "row_kind": "total" if "total" in label.lower() else "detail",
                "source_id": source_id,
                "source_page": page_num,
                "raw_cells": row,
                "provenance": provenance(source_id, url, "page/table/row", f"p{page_num}/r{row_index}"),
            }
        )
    return rows


def ingest_budget(session: requests.Session, registry: dict) -> tuple[dict, dict]:
    src = source(registry, "hrm-budget-2025-26")
    blob = fetch_pdf(session, src)
    records = []
    table_index = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            context = infer_page_context(text)
            tables = page.extract_tables() or []
            for table_num, table in enumerate(tables, 1):
                normalized = [[clean(cell) for cell in (row or [])] for row in (table or [])]
                if not normalized:
                    continue
                table_index.append(
                    {
                        "source_id": src["id"],
                        "page": page_num,
                        "table": table_num,
                        "context": context,
                        "rows": len(normalized),
                        "columns": max((len(r) for r in normalized), default=0),
                        "header": normalized[:3],
                    }
                )
                records.extend(budget_records_from_table(normalized, page_num, context, src["id"], src["url"], "2025/26"))
    budget = {
        "metadata": {
            "generated_at": now(),
            "source_id": src["id"],
            "records": len(records),
            "document_sha256": hashlib.sha256(blob).hexdigest(),
            "note": "Normalized only from tables whose headers explicitly expose actual and budget columns; all other tables remain visible in document_tables.json.",
        },
        "records": records,
    }
    index = {
        "metadata": {"generated_at": now(), "source_id": src["id"], "tables": len(table_index)},
        "records": table_index,
    }
    return budget, index


def ingest_financials(session: requests.Session, registry: dict) -> tuple[dict, dict]:
    src = source(registry, "hrm-financials-2025")
    blob = fetch_pdf(session, src)
    records = []
    table_index = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            context = infer_page_context(text)
            tables = page.extract_tables() or []
            for table_num, table in enumerate(tables, 1):
                normalized = [[clean(cell) for cell in (row or [])] for row in (table or [])]
                if not normalized:
                    continue
                table_index.append({"source_id": src["id"], "page": page_num, "table": table_num, "context": context, "rows": len(normalized), "header": normalized[:3]})
                for row_index, row in enumerate(normalized):
                    label = next((cell for cell in row if cell and money(cell) is None), "")
                    values = [money(cell) for cell in row]
                    numeric = [value for value in values if value is not None]
                    if not label or len(numeric) < 2:
                        continue
                    records.append(
                        {
                            "statement": context or None,
                            "line_item": label,
                            "current_year": numeric[-2],
                            "prior_year": numeric[-1],
                            "source_id": src["id"],
                            "source_page": page_num,
                            "raw_cells": row,
                            "provenance": provenance(src["id"], src["url"], "page/table/row", f"p{page_num}/t{table_num}/r{row_index}"),
                        }
                    )
    financials = {
        "metadata": {
            "generated_at": now(),
            "source_id": src["id"],
            "records": len(records),
            "document_sha256": hashlib.sha256(blob).hexdigest(),
            "note": "Generic audited-statement row extraction. Source page and raw cells are retained because statement layouts vary.",
        },
        "records": records,
    }
    index = {"metadata": {"generated_at": now(), "source_id": src["id"], "tables": len(table_index)}, "records": table_index}
    return financials, index


# ------------------------------ Council ------------------------------
class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_href = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.current_href = dict(attrs).get("href")
            self.current_text = []

    def handle_data(self, data):
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current_href is not None:
            self.links.append((self.current_href, clean(" ".join(self.current_text))))
            self.current_href = None
            self.current_text = []


def ingest_council(session: requests.Session, registry: dict) -> dict:
    src = source(registry, "hrm-escribe")
    candidates = [src["url"], urljoin(src["url"], "Meetings.aspx")]
    records = {}
    failures = []
    for url in candidates:
        try:
            response = session.get(url, timeout=90)
            response.raise_for_status()
            parser = LinkParser()
            parser.feed(response.text)
            for href, text in parser.links:
                if not href:
                    continue
                absolute = urljoin(response.url, href)
                if "Meeting.aspx?Id=" not in absolute:
                    continue
                match = re.search(r"[?&]Id=([^&]+)", absolute, re.I)
                meeting_id = match.group(1) if match else absolute
                records[meeting_id] = {
                    "meeting_id": meeting_id,
                    "title": text or None,
                    "url": absolute,
                    "source_id": src["id"],
                    "provenance": provenance(src["id"], response.url, "html-link", meeting_id),
                }
        except Exception as exc:
            failures.append(f"{url}: {type(exc).__name__}: {exc}")
    return {
        "metadata": {
            "generated_at": now(),
            "records": len(records),
            "discovery_urls": candidates,
            "failures": failures,
            "note": "This is an index discovery pass. Linked agenda/report PDFs require subsequent document-graph crawling and are not inferred when the eSCRIBE landing page does not expose them.",
        },
        "records": list(records.values()),
    }


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "application/json,text/html,application/pdf,*/*"})
    status = {}

    jobs = [
        ("procurement", lambda: write("procurement.json", ingest_procurement(session))),
        ("capital", lambda: write("capital.json", ingest_capital(session, registry))),
        (
            "budget",
            lambda: (
                lambda result: (write("budget.json", result[0]), write("budget_document_tables.json", result[1]))
            )(ingest_budget(session, registry)),
        ),
        (
            "financials",
            lambda: (
                lambda result: (write("financials.json", result[0]), write("financials_document_tables.json", result[1]))
            )(ingest_financials(session, registry)),
        ),
        ("council", lambda: write("council.json", ingest_council(session, registry))),
    ]

    for name, job in jobs:
        try:
            job()
            status[name] = {"status": "ok"}
            print(f"{name}: ok")
        except Exception as exc:
            status[name] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            print(f"{name}: ERROR {exc}")

    write(
        "domain_ingestion_status.json",
        {
            "metadata": {"generated_at": now(), "principle": "Independent domains; one parser failure does not block successful artifacts."},
            "records": [{"domain": key, **value} for key, value in status.items()],
        },
    )


if __name__ == "__main__":
    main()
