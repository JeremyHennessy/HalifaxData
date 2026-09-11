#!/usr/bin/env python3
"""Build 020 source-specific OCR adapter for HRM's 2018 audited statements.

The 2018 official attachment is a mixed text/image PDF. The established Build 005
parser correctly refuses to treat narrative bundle pages as statements, but the actual
statement/schedule pages have no usable PDF text layer. This adapter OCRs only the
known audited statement/schedule pages, then reuses the established conservative text
row parser unchanged. It does not alter parsing semantics for any other source year.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests

import ingest_financial_history as base
from ingest_domains import fetch_pdf

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "artifacts/build020-financials-2018-ocr.json"
SOURCE = {
    "id": "hrm-financials-2018",
    "name": "Audited Consolidated Financial Statements — 2018 Audit & Finance attachment",
    "publisher": "Halifax Regional Municipality",
    "category": "Budgets & actuals",
    "status": "ocr-adapter-candidate",
    "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/180718afsc1211.pdf",
}
# PDF page numbers. Pages 8-11 are statement pages 3-6. Pages 35-38 are the
# consolidated long-term-debt and segment-disclosure schedules (statement pages 30-33).
OCR_PAGES = [8, 9, 10, 11, 35, 36, 37, 38]
OCR_DPI = 200
OCR_PSM = 6
ADAPTER_VERSION = "build020-financials-2018-ocr-v1"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required OCR binary not found: {name}")
    return path


def ocr_page(pdf_path: Path, page_num: int, workdir: Path) -> str:
    prefix = workdir / f"page-{page_num:03d}"
    subprocess.run(
        [
            require_binary("pdftoppm"),
            "-f", str(page_num),
            "-l", str(page_num),
            "-r", str(OCR_DPI),
            "-singlefile",
            "-png",
            str(pdf_path),
            str(prefix),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    image_path = prefix.with_suffix(".png")
    result = subprocess.run(
        [require_binary("tesseract"), str(image_path), "stdout", "--psm", str(OCR_PSM)],
        check=True,
        capture_output=True,
        text=True,
    )
    text = result.stdout.replace("\x0c", "").strip()
    if not text:
        raise RuntimeError(f"OCR returned no text for PDF page {page_num}")
    return text


def dedupe(rows: list[dict]) -> list[dict]:
    unique: dict[tuple, dict] = {}
    for row in rows:
        key = (
            row["source_id"],
            row["source_page"],
            row["statement_family"],
            " ".join(str(row["line_item"]).lower().split()),
            row["current_year"],
            row["prior_year"],
        )
        unique.setdefault(key, row)
    return sorted(
        unique.values(),
        key=lambda row: (
            row.get("source_page") or 0,
            row.get("statement_family") or "",
            row.get("line_item") or "",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    require_binary("pdftoppm")
    require_binary("tesseract")
    session = requests.Session()
    session.headers["User-Agent"] = base.UA
    blob = fetch_pdf(session, SOURCE)
    source_sha = hashlib.sha256(blob).hexdigest()

    rows: list[dict] = []
    page_status: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="halifaxdata-2018-ocr-") as tmp:
        tmpdir = Path(tmp)
        pdf_path = tmpdir / "source.pdf"
        pdf_path.write_bytes(blob)
        # Structural check: these pages must exist in the authoritative attachment.
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            if len(pdf.pages) < max(OCR_PAGES):
                raise RuntimeError(f"2018 source unexpectedly has only {len(pdf.pages)} pages")

        for page_num in OCR_PAGES:
            text = ocr_page(pdf_path, page_num, tmpdir)
            family, title = base.statement_context(text)
            if not family:
                page_status.append({
                    "source_page": page_num,
                    "status": "no_statement_heading",
                    "ocr_chars": len(text),
                    "ocr_first_lines": [line.strip() for line in text.splitlines()[:5]],
                })
                continue
            multiplier = base.unit_multiplier(text)
            parsed = base.parse_text_rows(
                SOURCE,
                2018,
                page_num,
                family,
                title,
                text,
                multiplier,
            )
            for row in parsed:
                row["extraction_method"] = "ocr_text_line"
                row["ocr_adapter_version"] = ADAPTER_VERSION
                row["source_sha256"] = source_sha
                prov = dict(row.get("provenance") or {})
                prov["parser_version"] = base.PARSER_VERSION
                prov["ocr_adapter_version"] = ADAPTER_VERSION
                prov["source_sha256"] = source_sha
                prov["locator"] = f"p{page_num}/ocr/{prov.get('locator') or ''}".rstrip("/")
                row["provenance"] = prov
            rows.extend(parsed)
            page_status.append({
                "source_page": page_num,
                "status": "parsed",
                "statement_family": family,
                "statement_title": title,
                "source_unit_multiplier": multiplier,
                "ocr_chars": len(text),
                "records": len(parsed),
            })

    rows = dedupe(rows)
    families: dict[str, int] = {}
    for row in rows:
        families[row["statement_family"]] = families.get(row["statement_family"], 0) + 1

    payload = {
        "metadata": {
            "build": "020",
            "dataset_status": "candidate_2018_source_specific_ocr_extraction",
            "generated_at": now(),
            "fiscal_year_end": 2018,
            "source_id": SOURCE["id"],
            "source_url": SOURCE["url"],
            "source_sha256": source_sha,
            "base_parser_version": base.PARSER_VERSION,
            "ocr_adapter_version": ADAPTER_VERSION,
            "ocr_engine": "tesseract",
            "ocr_dpi": OCR_DPI,
            "ocr_psm": OCR_PSM,
            "ocr_pages": OCR_PAGES,
            "records": len(rows),
            "families": families,
            "page_status": page_status,
            "scope": "2018-only OCR of authoritative image-backed statement/schedule pages, followed by the established conservative Build 005 text-row parser. Narrative notes are not normalized.",
            "release_status": "candidate_not_production_until_validated_and_integrated",
        },
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["metadata"], indent=2))


if __name__ == "__main__":
    main()
