#!/usr/bin/env python3
"""Build 020 source-specific OCR adapter for HRM's 2018 audited statements.

The 2018 official attachment is a mixed text/image PDF. The established Build 005
parser correctly refuses to treat narrative bundle pages as statements, but the actual
statement pages have no usable PDF text layer. This adapter OCRs only the four primary
audited statement pages and applies the established conservative numeric/normalization
rules with one source-specific correction: on three-column Budget/2018/2017 lines, the
label ends before the first numeric column rather than before the 2018 column.

Eight OCR digit errors that are deterministically contradicted by the next year's
text-native audited statement are corrected explicitly. Every correction preserves the
raw OCR value and records the independent 2019 comparative source used to validate the
replacement. It does not alter parsing semantics for any other source year. Image-backed
schedules remain explicitly out of scope until separately validated.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests

import ingest_financial_history as base
from ingest_domains import clean, fetch_pdf, money

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
COMPARATOR_SOURCE = {
    "id": "hrm-financials-2019",
    "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/budget-finances/FS-March-31-2019-V7-Signed.pdf",
    "role": "text-native next-year audited statement containing source-presented 2018 comparative values",
}
OCR_PAGES = [8, 9, 10, 11]
OCR_DPI = 200
OCR_PSM = 6
ADAPTER_VERSION = "build020-financials-2018-ocr-v4"
NOTE_RE = re.compile(r"\s*\(?notes?\s+\d+[a-z]?(?:\([a-z0-9]+\))?\)?", re.I)
NONWORD_RE = re.compile(r"[^a-z0-9]+")

CORRECTIONS = {
    ("financial_position", "accounts payable and accrued liabilities"): 106_700_000.0,
    ("financial_position", "accumulated surplus"): 2_040_260_000.0,
    ("financial_position", "investment in the halifax regional water commission"): 167_660_000.0,
    ("financial_position", "loans deposits and advances"): 490_000.0,
    ("financial_position", "net financial assets"): 163_419_000.0,
    ("cash_flows", "annual surplus"): 83_815_000.0,
    ("cash_flows", "increase decrease in accounts payable and accrued liabilities"): -67_000.0,
    ("cash_flows", "before remeasurement gain loss"): -21_781_000.0,
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm_label(value: str) -> str:
    text = NOTE_RE.sub(" ", str(value or "").lower())
    return " ".join(NONWORD_RE.sub(" ", text).split())


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required OCR binary not found: {name}")
    return path


def ocr_page(pdf_path: Path, page_num: int, workdir: Path) -> str:
    prefix = workdir / f"page-{page_num:03d}"
    subprocess.run(
        [require_binary("pdftoppm"), "-f", str(page_num), "-l", str(page_num), "-r", str(OCR_DPI), "-singlefile", "-png", str(pdf_path), str(prefix)],
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


def parse_ocr_text_rows(src: dict, fiscal_year: int, page_num: int, statement_family: str, statement_title: str, text: str, multiplier: int) -> list[dict]:
    records: list[dict] = []
    for line_num, raw_line in enumerate((text or "").splitlines(), 1):
        line = clean(raw_line)
        if not line or not base.valid_label(line):
            continue
        masked_line = base.mask_label_numbers(line)
        matches = list(base.VALUE_RE.finditer(masked_line))
        if len(matches) < 2:
            continue
        current_match, prior_match = matches[-2], matches[-1]
        if not (base.has_financial_format(current_match.group(), multiplier) or base.has_financial_format(prior_match.group(), multiplier)):
            continue
        label_end = matches[0].start() if len(matches) >= 3 else current_match.start()
        label = clean(line[:label_end]).rstrip("$ ")
        if not base.valid_label(label):
            continue
        current_raw = money(current_match.group())
        prior_raw = money(prior_match.group())
        if current_raw is None or prior_raw is None:
            continue
        records.append(base.normalized_record(
            src, fiscal_year, page_num, statement_family, statement_title, label,
            current_raw, prior_raw, multiplier, [line], "ocr_text_line", f"p{page_num}/ocr-line{line_num}",
        ))
    return records


def apply_validated_corrections(rows: list[dict]) -> int:
    applied = 0
    seen_keys: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("statement_family") or ""), norm_label(row.get("line_item")))
        target = CORRECTIONS.get(key)
        if target is None:
            continue
        if key in seen_keys:
            raise RuntimeError(f"Correction key matched multiple OCR rows: {key!r}")
        seen_keys.add(key)
        raw_normalized = float(row["current_year"])
        raw_presented = float(row["source_presented_current_year"])
        if raw_normalized == target:
            raise RuntimeError(f"Correction no longer required for {key!r}; remove stale correction rule")
        row["ocr_current_year"] = raw_normalized
        row["ocr_source_presented_current_year"] = raw_presented
        row["current_year"] = target
        row["ocr_correction"] = {
            "status": "validated_against_next_year_audited_comparative",
            "raw_ocr_current_year": raw_normalized,
            "validated_current_year": target,
            "validation_source_id": COMPARATOR_SOURCE["id"],
            "validation_source_url": COMPARATOR_SOURCE["url"],
            "validation_source_role": COMPARATOR_SOURCE["role"],
            "basis": "Same statement family and normalized line item; 2019 audited statement presents the 2018 amount as its comparative column.",
        }
        prov = dict(row.get("provenance") or {})
        prov["validation_source_id"] = COMPARATOR_SOURCE["id"]
        prov["validation_source_url"] = COMPARATOR_SOURCE["url"]
        prov["ocr_correction_applied"] = True
        row["provenance"] = prov
        applied += 1
    missing = set(CORRECTIONS) - seen_keys
    if missing:
        diagnostics = [
            {
                "family": row.get("statement_family"),
                "label": row.get("line_item"),
                "normalized_label": norm_label(row.get("line_item")),
                "current_year": row.get("current_year"),
                "prior_year": row.get("prior_year"),
                "raw_cells": row.get("raw_cells"),
            }
            for row in rows
            if row.get("statement_family") == "financial_position"
        ]
        raise RuntimeError(
            f"Configured OCR corrections did not match candidate rows: {sorted(missing)!r}; "
            f"financial_position_rows={diagnostics!r}"
        )
    return applied


def dedupe(rows: list[dict]) -> list[dict]:
    unique: dict[tuple, dict] = {}
    for row in rows:
        key = (row["source_id"], row["source_page"], row["statement_family"], " ".join(str(row["line_item"]).lower().split()), row["current_year"], row["prior_year"])
        unique.setdefault(key, row)
    return sorted(unique.values(), key=lambda row: (row.get("source_page") or 0, row.get("statement_family") or "", row.get("line_item") or ""))


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
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            if len(pdf.pages) < max(OCR_PAGES):
                raise RuntimeError(f"2018 source unexpectedly has only {len(pdf.pages)} pages")
        for page_num in OCR_PAGES:
            text = ocr_page(pdf_path, page_num, tmpdir)
            family, title = base.statement_context(text)
            if not family:
                raise RuntimeError(f"No audited statement heading recovered by OCR on PDF page {page_num}")
            multiplier = base.unit_multiplier(text)
            parsed = parse_ocr_text_rows(SOURCE, 2018, page_num, family, title, text, multiplier)
            for row in parsed:
                row["ocr_adapter_version"] = ADAPTER_VERSION
                row["source_sha256"] = source_sha
                prov = dict(row.get("provenance") or {})
                prov["locator_type"] = "ocr_text_line"
                prov["parser_version"] = base.PARSER_VERSION
                prov["ocr_adapter_version"] = ADAPTER_VERSION
                prov["source_sha256"] = source_sha
                row["provenance"] = prov
            rows.extend(parsed)
            page_status.append({"source_page": page_num, "status": "parsed", "statement_family": family, "statement_title": title, "source_unit_multiplier": multiplier, "ocr_chars": len(text), "records": len(parsed)})
    correction_count = apply_validated_corrections(rows)
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
            "validated_ocr_corrections": correction_count,
            "correction_validation_source": COMPARATOR_SOURCE,
            "scope": "2018-only OCR of the four authoritative primary statement pages, followed by Build 005 conservative numeric/normalization rules with a source-specific three-column label-boundary correction. Eight raw OCR digit errors are explicitly preserved and corrected only where the text-native 2019 audited statement independently prints the same 2018 comparative line item. Image-backed schedules and narrative notes remain out of scope.",
            "schedule_coverage": "not_released_from_ocr_candidate",
            "release_status": "candidate_not_production_until_validated_and_integrated",
        },
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["metadata"], indent=2))


if __name__ == "__main__":
    main()
