#!/usr/bin/env python3
"""Build 010 adjustment refinement: parse Council adjustment tables structurally.

The May 27, 2025 staff report presents approved-capital changes in tables. This
wrapper keeps project identity fixes from v3, but replaces free-text monetary
segmentation with table-row parsing. A row is accepted only when exactly one
ordered monetary triple reconciles: approved_budget_before + adjustment =
approved_budget_after.
"""
from __future__ import annotations

import io
import re

import pdfplumber

import ingest_current_capital as base
import ingest_current_capital_v3  # noqa: F401  # applies authoritative project-code + continuation patches

ADJUSTMENT_CODE_RE = re.compile(r"\b[A-Z]{1,3}\d{6}\b")


def row_section(page_text: str, row_text: str, active_section: str | None) -> str | None:
    low = row_text.lower()
    for heading, section in base.SECTION_LABELS.items():
        if heading in low:
            return section
    code_match = ADJUSTMENT_CODE_RE.search(row_text)
    if code_match:
        code = code_match.group(0)
        position = page_text.find(code)
        if position >= 0:
            inferred = base.section_at(page_text, position)
            if inferred:
                return inferred
    return active_section


def reconciled_triplet(values: list[float]) -> tuple[float, float, float] | None:
    matches = []
    for index in range(max(0, len(values) - 2)):
        before, adjustment, after = values[index : index + 3]
        if round(before + adjustment - after, 2) == 0:
            matches.append((before, adjustment, after))
    unique = []
    for match in matches:
        if match not in unique:
            unique.append(match)
    return unique[0] if len(unique) == 1 else None


def project_name_from_cells(cells: list[str], code: str, code_index: int) -> str:
    parts = []
    same_cell = base.clean(cells[code_index])
    if code in same_cell:
        tail = base.clean(same_cell.split(code, 1)[1])
        if tail:
            parts.append(tail)
    for cell in cells[code_index + 1 :]:
        value = base.clean(cell)
        if not value:
            continue
        if value == "$":
            break
        if base.money(value) is not None:
            break
        if re.fullmatch(r"\$?\s*[-–—]", value):
            break
        parts.append(value)
    return base.clean(" ".join(parts)) or code


def row_money_values(cells: list[str], code_index: int) -> list[float]:
    values = []
    for cell in cells[code_index + 1 :]:
        text = base.clean(cell)
        if not text or text == "$":
            continue
        if re.fullmatch(r"\$?\s*[-–—]", text):
            values.append(0.0)
            continue
        parsed = base.money(text)
        if parsed is not None:
            values.append(parsed)
            continue
        # A merged table cell can contain multiple currency-formatted values.
        values.extend(base.money_tokens(text))
    return values


def collect_adjustments_table_first(session, report_url: str) -> list[dict]:
    blob = base.fetch_pdf(session, report_url)
    accepted = []
    active_section = None
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text() or ""
            page_low = page_text.lower()
            page_sections = [section for heading, section in base.SECTION_LABELS.items() if heading in page_low]
            if len(page_sections) == 1:
                active_section = page_sections[0]
            for table_num, table in enumerate(page.extract_tables() or [], 1):
                for row_num, raw_row in enumerate(table or [], 1):
                    cells = [base.clean(cell) for cell in (raw_row or [])]
                    if not any(cells):
                        continue
                    joined = base.clean(" | ".join(cells))
                    for heading, section in base.SECTION_LABELS.items():
                        if heading in joined.lower():
                            active_section = section
                    code_match = ADJUSTMENT_CODE_RE.search(joined)
                    if not code_match:
                        continue
                    section = row_section(page_text, joined, active_section)
                    if not section:
                        continue
                    code = code_match.group(0)
                    code_index = next((i for i, cell in enumerate(cells) if code in cell), None)
                    if code_index is None:
                        continue
                    values = row_money_values(cells, code_index)
                    triplet = reconciled_triplet(values)
                    if triplet is None:
                        continue
                    before, adjustment, after = triplet
                    accepted.append({
                        "adjustment_type": section,
                        "project_code": code,
                        "project_name": project_name_from_cells(cells, code, code_index),
                        "approved_budget_before": before,
                        "adjustment_amount": adjustment,
                        "approved_budget_after": after,
                        "source_id": "hrm-escribe",
                        "source_document_title": base.ADJUSTMENT_TITLE_TOKEN,
                        "source_document_url": report_url,
                        "source_page": page_num,
                        "source_table": table_num,
                        "source_row": row_num,
                        "provenance": base.provenance(
                            "hrm-escribe",
                            report_url,
                            page_num,
                            f"p{page_num}/t{table_num}/r{row_num}/{code}/{section}",
                            "council-report-table-row",
                        ),
                    })
    unique = {}
    for row in accepted:
        key = (
            row["adjustment_type"],
            row["project_code"],
            row["approved_budget_before"],
            row["adjustment_amount"],
            row["approved_budget_after"],
        )
        unique.setdefault(key, row)
    return sorted(unique.values(), key=lambda row: (row["adjustment_type"], row["project_code"]))


base.ADJUSTMENT_SOURCE_ID = "hrm-escribe"
base.collect_adjustments = collect_adjustments_table_first

if __name__ == "__main__":
    base.main()
