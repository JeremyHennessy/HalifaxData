#!/usr/bin/env python3
"""Collect 2025/26 capital projection/actuals summaries from HRM quarterly reports.

These Attachment #8 tables are asset-category summaries. They are deliberately
not assigned to individual project codes; project-level payment/actual evidence
is not present in this source.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pdfplumber
import requests

from ingest_domains import clean, now, provenance, strict_money_cell

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/generated/capital_actuals_current.json"
PARSER_VERSION = "build008-capital-actuals-v1"

SOURCES = [
    {
        "source_id": "hrm-financial-q1-2025-26",
        "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250917afsc1313.pdf",
        "quarter": "Q1",
        "period_end": "2025-06-30",
        "expected_actual_expenditures": 60_200_000,
        "expected_projected_remaining_spend": 421_800_000,
        "expected_projected_year_end_wip": 198_700_000,
    },
    {
        "source_id": "hrm-financial-q2-2025-26",
        "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/boards-committees-commissions/251125afsc1326.pdf",
        "quarter": "Q2",
        "period_end": "2025-09-30",
        "expected_actual_expenditures": 147_800_000,
        "expected_projected_remaining_spend": 349_100_000,
        "expected_projected_year_end_wip": 219_900_000,
    },
    {
        "source_id": "hrm-financial-q3-2025-26",
        "url": "https://pub-halifax.escribemeetings.com/filestream.ashx?DocumentId=4479",
        "quarter": "Q3",
        "period_end": "2025-12-31",
        "expected_actual_expenditures": 255_400_000,
        "expected_projected_remaining_spend": 109_300_000,
        "expected_projected_year_end_wip": 343_100_000,
    },
]

VALUE_FIELDS = [
    "budget_remaining_at_prior_year_end",
    "commitments_at_prior_year_end",
    "budget_2025_26",
    "budget_increases_decreases",
    "budget_available_at_period_end",
    "ytd_expenditures",
    "ytd_commitments",
    "ytd_expenditures_and_commitments",
    "projected_spend_remaining_2025_26",
    "projected_work_in_progress_2026_27",
]


def fetch_pdf(session: requests.Session, url: str) -> bytes:
    response = session.get(url, timeout=180)
    response.raise_for_status()
    blob = response.content
    if not blob.startswith(b"%PDF"):
        raise RuntimeError(f"Expected PDF from {url}, received {response.headers.get('content-type')!r}")
    return blob


def money_tokens(row: list[str]) -> list[float | None]:
    values: list[float | None] = []
    for cell in row:
        cell = clean(cell)
        if not cell or cell == "$":
            continue
        value, valid = strict_money_cell(cell)
        if valid:
            values.append(value)
    return values


def row_label(row: list[str]) -> str:
    for cell in row:
        cell = clean(cell)
        if cell and any(ch.isalpha() for ch in cell):
            return cell
    return ""


def extract_source(source: dict, blob: bytes) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    table_status: list[dict] = []
    seen_labels: set[str] = set()
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if "Capital Projection Summary" not in text and "Budget Category" not in text:
                continue
            for table_num, table in enumerate(page.extract_tables() or [], 1):
                rows = [[clean(cell) for cell in (raw or [])] for raw in (table or [])]
                flattened = " ".join(cell for row in rows for cell in row)
                if "Budget Category" not in flattened or "Expenditures" not in flattened or "Projections" not in flattened:
                    continue
                parsed_in_table = 0
                for source_row, row in enumerate(rows, 1):
                    label = row_label(row)
                    if not label or "Budget Category" in label:
                        continue
                    values = money_tokens(row)
                    if len(values) != len(VALUE_FIELDS):
                        continue
                    normalized_label = " ".join(label.split())
                    key = normalized_label.casefold()
                    if key in seen_labels:
                        raise RuntimeError(f"Duplicate capital category {normalized_label!r} in {source['source_id']}")
                    seen_labels.add(key)
                    record = {
                        "fiscal_year": "2025/26",
                        "quarter": source["quarter"],
                        "period_end": source["period_end"],
                        "granularity": "capital_asset_category_summary",
                        "budget_category": normalized_label,
                        **dict(zip(VALUE_FIELDS, values, strict=True)),
                        "source_id": source["source_id"],
                        "source_page": page_num,
                        "source_table": table_num,
                        "source_row": source_row,
                        "provenance": provenance(
                            source["source_id"], source["url"], "page/table/row",
                            f"p{page_num}/t{table_num}/r{source_row}", PARSER_VERSION,
                        ),
                    }
                    records.append(record)
                    parsed_in_table += 1
                table_status.append({"page": page_num, "table": table_num, "parsed_rows": parsed_in_table})
    return records, table_status


def main() -> None:
    session = requests.Session()
    session.headers["User-Agent"] = "HalifaxData/0.8 (+https://github.com/JeremyHennessy/HalifaxData)"
    all_records = []
    source_status = []
    for source in SOURCES:
        blob = fetch_pdf(session, source["url"])
        rows, tables = extract_source(source, blob)
        if len(rows) < 5:
            raise RuntimeError(f"Only {len(rows)} capital summary rows parsed for {source['source_id']}")
        total_rows = [row for row in rows if "total" in row["budget_category"].casefold()]
        if len(total_rows) != 1:
            raise RuntimeError(f"Expected exactly one total capital row for {source['source_id']}, found {len(total_rows)}")
        total = total_rows[0]
        for field, expected_key in [
            ("ytd_expenditures", "expected_actual_expenditures"),
            ("projected_spend_remaining_2025_26", "expected_projected_remaining_spend"),
            ("projected_work_in_progress_2026_27", "expected_projected_year_end_wip"),
        ]:
            expected = float(source[expected_key])
            actual = float(total[field] or 0)
            # Narrative report values are rounded to $0.1M.
            if abs(actual - expected) > 100_000:
                raise RuntimeError(
                    f"{source['source_id']} {field} total {actual} does not reconcile to narrative {expected}"
                )
        source_status.append({
            "source_id": source["source_id"],
            "quarter": source["quarter"],
            "period_end": source["period_end"],
            "records": len(rows),
            "total_row": total["budget_category"],
            "narrative_actual_expenditures": source["expected_actual_expenditures"],
            "narrative_projected_remaining_spend": source["expected_projected_remaining_spend"],
            "narrative_projected_year_end_wip": source["expected_projected_year_end_wip"],
            "tables": tables,
        })
        all_records.extend(rows)

    payload = {
        "metadata": {
            "generated_at": now(),
            "dataset_status": "official_2025_26_capital_projection_summaries",
            "parser_version": PARSER_VERSION,
            "records": len(all_records),
            "source_count": len(SOURCES),
            "source_status": source_status,
            "granularity": "asset_category_summary_not_project_actuals",
            "project_level_actuals_available": False,
            "note": (
                "Quarterly Attachment #8 Capital Projection Summary rows. These provide current-year capital actuals, commitments and "
                "projections by published budget category, not by project code. They must not be joined to individual capital projects or "
                "interpreted as vendor payments."
            ),
        },
        "records": all_records,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Current capital actuals: {len(all_records)} category rows across {len(SOURCES)} quarters")


if __name__ == "__main__":
    main()
