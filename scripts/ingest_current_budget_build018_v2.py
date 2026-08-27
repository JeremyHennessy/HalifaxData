#!/usr/bin/env python3
"""Build 018 source-layout specialization for the final 2026/27 budget package.

The Build 004 table buckets remain untouched. Live-source diagnostics established that
the final 2026/27 package shifts service-area table geometry between business units.
A single fixed x-coordinate cannot safely separate the change amount from the percent
column, and on the RCMP page the first currency marker begins left of the legacy label
boundary.

This wrapper therefore derives two boundaries independently for every service-area page:

- label/value boundary: the first value token on that page's source `Net Total` row,
  capped at the legacy x=215 boundary;
- change/percent boundary: the x-position of the source header's second `Δ`, which marks
  the percent column on the final package.

Rows containing no numeric token remain text rows. All other Build 018 collection,
validation, provenance and arithmetic logic remains in `ingest_current_budget_build018`.
"""
from __future__ import annotations

import re

import ingest_current_budget_build018 as current

DEFAULT_LABEL_BOUNDARY = 215.0
DEFAULT_PERCENT_BOUNDARY = 527.0
page_label_boundary = DEFAULT_LABEL_BOUNDARY
page_percent_boundary = DEFAULT_PERCENT_BOUNDARY
original_parse_service_area_page = current.parse_service_area_page


def row_text(row: list[dict]) -> str:
    return " ".join(str(word.get("text") or "") for word in row)


def configure_page_boundaries(page) -> None:
    global page_label_boundary, page_percent_boundary

    visual = current.base.visual_rows(page)
    header_index = None
    header_row = None
    for index, row in enumerate(visual):
        text = row_text(row).lower()
        if "service area" in text and "actual" in text and "budget" in text and ("projection" in text or "projections" in text):
            header_index = index
            header_row = row
            break
    if header_row is None or header_index is None:
        raise RuntimeError("Build 018 source-layout header row not found")

    delta_positions = [
        float(word["x0"])
        for word in header_row
        if str(word.get("text") or "").strip() in {"Δ", "∆"}
    ]
    if len(delta_positions) < 2:
        raise RuntimeError(
            f"Build 018 source-layout header expected two delta markers; found {delta_positions}"
        )
    page_percent_boundary = delta_positions[-1]

    net_total_row = None
    for row in visual[header_index + 1:]:
        text = row_text(row).strip().lower()
        if text.startswith("net total"):
            net_total_row = row
            break
    if net_total_row is None:
        raise RuntimeError("Build 018 source-layout Net Total row not found")

    first_value_x = None
    for word in net_total_row:
        text = str(word.get("text") or "").strip()
        x = float(word["x0"])
        if x <= 150:
            continue
        if text == "$" or re.search(r"\d", text) or text in {"(", "-", "–", "—"}:
            first_value_x = x
            break
    if first_value_x is None:
        raise RuntimeError("Build 018 source-layout first Net Total value token not found")

    page_label_boundary = min(DEFAULT_LABEL_BOUNDARY, max(150.0, first_value_x - 0.5))
    if not (page_label_boundary < 280 and 466 < page_percent_boundary < 560):
        raise RuntimeError(
            f"Build 018 source-layout boundaries out of range: label={page_label_boundary}, percent={page_percent_boundary}"
        )


def budget_buckets_2026_27(row: list[dict]) -> dict[str, list[dict]]:
    buckets = {
        key: []
        for key in (
            "label",
            "prior_actual",
            "prior_budget",
            "projection",
            "current_budget",
            "source_delta",
            "source_delta_pct",
        )
    }

    # Source-observed text headings can extend beyond the numeric label boundary.
    # A row with no digit anywhere cannot be a service-area amount row.
    if not any(re.search(r"\d", str(word.get("text") or "")) for word in row):
        buckets["label"].extend(row)
        return buckets

    for word in row:
        x = float(word["x0"])
        if x < page_label_boundary:
            key = "label"
        elif x < 280:
            key = "prior_actual"
        elif x < 340:
            key = "prior_budget"
        elif x < 405:
            key = "projection"
        elif x < 466:
            key = "current_budget"
        elif x < page_percent_boundary:
            key = "source_delta"
        else:
            key = "source_delta_pct"
        buckets[key].append(word)
    return buckets


def parse_service_area_page_2026_27(page, page_number: int, heading: str, stable_retrieved_at: str):
    configure_page_boundaries(page)
    return original_parse_service_area_page(page, page_number, heading, stable_retrieved_at)


current.PARSER_VERSION = "build018-current-budget-v2"
current.base.budget_buckets = budget_buckets_2026_27
current.parse_service_area_page = parse_service_area_page_2026_27

if __name__ == "__main__":
    current.main()
