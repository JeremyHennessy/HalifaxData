#!/usr/bin/env python3
"""Collect 2025/26 capital projection/actuals summaries from HRM quarterly reports.

Attachment #8 is an asset-category summary, not a project-level ledger. The PDF
encodes its visual ten-value rows as a fourteen-column text grid with spacer
columns; this collector reconstructs only that explicit grid and never assigns
category actuals to individual project codes.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pdfplumber
import requests

from ingest_domains import clean, now, provenance, strict_money_cell

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/generated/capital_actuals_current.json"
PARSER_VERSION = "build008-capital-actuals-v2"

SOURCES = [
    {
        "source_id": "hrm-financial-q1-2025-26",
        "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250917afsc1313.pdf",
        "quarter": "Q1",
        "period_end": "2025-06-30",
        "required": True,
        "expected_actual_expenditures": 60_200_000,
        "expected_projected_remaining_spend": 421_800_000,
        "expected_projected_year_end_wip": 198_700_000,
    },
    {
        "source_id": "hrm-financial-q2-2025-26",
        "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/boards-committees-commissions/251125afsc1326.pdf",
        "quarter": "Q2",
        "period_end": "2025-09-30",
        "required": True,
        "expected_actual_expenditures": 147_800_000,
        "expected_projected_remaining_spend": 349_100_000,
        "expected_projected_year_end_wip": 219_900_000,
    },
    {
        "source_id": "hrm-financial-q3-2025-26",
        "url": "https://pub-halifax.escribemeetings.com/filestream.ashx?DocumentId=4479",
        "referer": "https://pub-halifax.escribemeetings.com/Meeting.aspx?Agenda=Agenda&Id=1338404b-b5af-4d13-996d-bb11be3fdcdb&lang=English",
        "quarter": "Q3",
        "period_end": "2025-12-31",
        # The official attachment is searchable/public but has returned HTTP 404
        # to GitHub Actions. Keep trying it, but never block Q1/Q2 publication or
        # fabricate Q3 rows from narrative/search-index text.
        "required": False,
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
# pdfplumber's text-grid extraction inserts spacer columns at 4, 7 and 9.
TEXT_GRID_VALUE_INDEXES = [1, 2, 3, 5, 6, 8, 10, 11, 12, 13]
TEXT_TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "intersection_tolerance": 8,
    "snap_tolerance": 4,
}


def fetch_pdf(session: requests.Session, source: dict) -> bytes:
    url = source["url"]
    attempts: list[str] = []
    if source.get("referer"):
        try:
            landing = session.get(source["referer"], timeout=60)
            attempts.append(f"referer_status={landing.status_code}")
        except requests.RequestException as exc:
            attempts.append(f"referer_error={type(exc).__name__}")
    headers = {
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        "Referer": source.get("referer") or url,
    }
    response = session.get(url, headers=headers, timeout=180)
    attempts.append(f"document_status={response.status_code}")
    response.raise_for_status()
    blob = response.content
    if not blob.startswith(b"%PDF"):
        raise RuntimeError(
            f"Expected PDF from {url}, received {response.headers.get('content-type')!r}; {' '.join(attempts)}"
        )
    return blob


def source_money(cell: str) -> float | None:
    """Parse one monetary cell while repairing PDF-internal digit spacing only."""
    compact = re.sub(r"\s+", "", clean(cell))
    value, valid = strict_money_cell(compact)
    if not valid:
        raise RuntimeError(f"Invalid single-value capital summary cell: {cell!r}")
    return value


def extract_source(source: dict, blob: bytes) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    table_status: list[dict] = []
    seen_labels: set[str] = set()
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if "Capital Projection Summary" not in text or "Budget Category" not in text or "GRAND TOTAL" not in text:
                continue
            for table_num, table in enumerate(page.extract_tables(table_settings=TEXT_TABLE_SETTINGS) or [], 1):
                rows = [[clean(cell) for cell in (raw or [])] for raw in (table or [])]
                if not any(row and clean(row[0]).casefold() == "grand total" for row in rows):
                    continue
                parsed_in_table = 0
                for source_row, row in enumerate(rows, 1):
                    if len(row) <= max(TEXT_GRID_VALUE_INDEXES):
                        continue
                    label = clean(row[0])
                    if not label or label.casefold() == "budget category" or not any(ch.isalpha() for ch in label):
                        continue
                    # Footer/header text can span the first grid column; only rows
                    # with ten independently parseable monetary columns qualify.
                    try:
                        values = [source_money(row[index]) for index in TEXT_GRID_VALUE_INDEXES]
                    except RuntimeError:
                        continue
                    normalized_label = " ".join(label.split())
                    key = normalized_label.casefold()
                    if key in seen_labels:
                        raise RuntimeError(f"Duplicate capital category {normalized_label!r} in {source['source_id']}")
                    seen_labels.add(key)
                    records.append(
                        {
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
                                source["source_id"], source["url"], "page/text-grid/row",
                                f"p{page_num}/t{table_num}/r{source_row}", PARSER_VERSION,
                            ),
                        }
                    )
                    parsed_in_table += 1
                table_status.append({"page": page_num, "table": table_num, "parsed_rows": parsed_in_table})
    return records, table_status


def validate_source_rows(source: dict, rows: list[dict]) -> dict:
    if len(rows) != 10:
        raise RuntimeError(f"Expected 9 categories + GRAND TOTAL for {source['source_id']}, parsed {len(rows)}")
    total_rows = [row for row in rows if row["budget_category"].casefold() == "grand total"]
    if len(total_rows) != 1:
        raise RuntimeError(f"Expected exactly one GRAND TOTAL for {source['source_id']}, found {len(total_rows)}")
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
            raise RuntimeError(f"{source['source_id']} {field} total {actual} does not reconcile to narrative {expected}")
    return total


def main() -> None:
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 HalifaxData/0.8 (+https://github.com/JeremyHennessy/HalifaxData)"
    all_records: list[dict] = []
    source_status: list[dict] = []
    materialized_quarters: list[str] = []

    for source in SOURCES:
        try:
            blob = fetch_pdf(session, source)
            rows, tables = extract_source(source, blob)
            total = validate_source_rows(source, rows)
        except Exception as exc:
            if source.get("required"):
                raise
            source_status.append(
                {
                    "source_id": source["source_id"],
                    "quarter": source["quarter"],
                    "period_end": source["period_end"],
                    "status": "source_access_error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "records": 0,
                    "narrative_actual_expenditures": source["expected_actual_expenditures"],
                    "narrative_projected_remaining_spend": source["expected_projected_remaining_spend"],
                    "narrative_projected_year_end_wip": source["expected_projected_year_end_wip"],
                    "note": "Official source is known/searchable but no rows are materialized when the attachment cannot be fetched by the collector.",
                }
            )
            continue

        source_status.append(
            {
                "source_id": source["source_id"],
                "quarter": source["quarter"],
                "period_end": source["period_end"],
                "status": "ok",
                "records": len(rows),
                "total_row": total["budget_category"],
                "narrative_actual_expenditures": source["expected_actual_expenditures"],
                "narrative_projected_remaining_spend": source["expected_projected_remaining_spend"],
                "narrative_projected_year_end_wip": source["expected_projected_year_end_wip"],
                "tables": tables,
            }
        )
        materialized_quarters.append(source["quarter"])
        all_records.extend(rows)

    if not {"Q1", "Q2"}.issubset(materialized_quarters):
        raise RuntimeError(f"Required Q1/Q2 current capital actuals were not materialized: {materialized_quarters}")

    payload = {
        "metadata": {
            "generated_at": now(),
            "dataset_status": "official_2025_26_capital_projection_summaries",
            "parser_version": PARSER_VERSION,
            "records": len(all_records),
            "source_count_configured": len(SOURCES),
            "source_count_materialized": len(materialized_quarters),
            "materialized_quarters": materialized_quarters,
            "source_status": source_status,
            "granularity": "asset_category_summary_not_project_actuals",
            "project_level_actuals_available": False,
            "note": (
                "Quarterly Attachment #8 Capital Projection Summary rows. These provide current-year capital actuals, commitments and "
                "projections by published budget category, not by project code. They must not be joined to individual capital projects or "
                "interpreted as vendor payments. A configured quarter with source_access_error remains unmaterialized rather than being "
                "backfilled from narrative or search-index text."
            ),
        },
        "records": all_records,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Current capital actuals: {len(all_records)} category rows; materialized={materialized_quarters}")


if __name__ == "__main__":
    main()
