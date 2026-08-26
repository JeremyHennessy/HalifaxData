#!/usr/bin/env python3
"""Build 010 adjustment scope refinement: accept only the three headed tables.

The staff report is followed by a multi-year capital schedule. Project rows in
that attachment can also reconcile arithmetically, so section state must not be
carried forward. An approved adjustment row is eligible only when the same
extracted table contains exactly one of the report's three adjustment headings.
"""
from __future__ import annotations

import io

import pdfplumber

import ingest_current_capital as base
import ingest_current_capital_v3  # noqa: F401  # authoritative project identity patches
import ingest_current_capital_v4 as structural


def table_section(table) -> str | None:
    text = base.clean(" ".join(base.clean(cell) for row in (table or []) for cell in (row or []) if base.clean(cell))).lower()
    matches = [section for heading, section in base.SECTION_LABELS.items() if heading in text]
    unique = list(dict.fromkeys(matches))
    return unique[0] if len(unique) == 1 else None


def collect_adjustments_scoped(session, report_url: str) -> list[dict]:
    blob = base.fetch_pdf(session, report_url)
    accepted = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            for table_num, table in enumerate(page.extract_tables() or [], 1):
                section = table_section(table)
                if not section:
                    continue
                for row_num, raw_row in enumerate(table or [], 1):
                    cells = [base.clean(cell) for cell in (raw_row or [])]
                    if not any(cells):
                        continue
                    joined = base.clean(" | ".join(cells))
                    code_match = structural.ADJUSTMENT_CODE_RE.search(joined)
                    if not code_match:
                        continue
                    code = code_match.group(0)
                    code_index = next((i for i, cell in enumerate(cells) if code in cell), None)
                    if code_index is None:
                        continue
                    values = structural.row_money_values(cells, code_index)
                    triplet = structural.reconciled_triplet(values)
                    if triplet is None:
                        continue
                    before, adjustment, after = triplet
                    accepted.append({
                        "adjustment_type": section,
                        "project_code": code,
                        "project_name": structural.project_name_from_cells(cells, code, code_index),
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
                            "council-report-adjustment-table-row",
                        ),
                    })
    unique = {}
    for row in accepted:
        key = (
            row["adjustment_type"], row["project_code"], row["approved_budget_before"],
            row["adjustment_amount"], row["approved_budget_after"],
        )
        unique.setdefault(key, row)
    return sorted(unique.values(), key=lambda row: (row["adjustment_type"], row["project_code"]))


base.PARSER_VERSION = "build010-current-capital-v5"
base.ADJUSTMENT_SOURCE_ID = "hrm-escribe"
base.collect_adjustments = collect_adjustments_scoped

if __name__ == "__main__":
    base.main()
