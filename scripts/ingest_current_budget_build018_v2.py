#!/usr/bin/env python3
"""Build 018 source-layout specialization for the final 2026/27 budget package.

The Build 004 table buckets remain untouched. Live-source diagnostics established that
the final 2026/27 package shifts service-area table geometry between business units.
Two source-specific protections are therefore required:

- label/value boundary: derive the first value position independently from each page's
  source `Net Total` row, capped at the legacy x=215 boundary. This keeps the RCMP
  page's currency marker (x≈206) out of the source label without changing older data;
- change/percent boundary: use the verified source-wide gap measured across all 20
  service-area overview pages and 105 amount rows. The furthest-right change token is
  x=513.6580 and the earliest percent token is x=518.9849, so x=516.32 is inside a
  proven empty gap rather than inferred from any one page's header typography.

Rows containing no numeric token remain text rows. All other Build 018 collection,
validation, provenance and arithmetic logic remains in `ingest_current_budget_build018`.
"""
from __future__ import annotations

import re

import ingest_current_budget_build018 as current

DEFAULT_LABEL_BOUNDARY = 215.0
SOURCE_PERCENT_BOUNDARY = 516.32
SOURCE_MAX_DELTA_TOKEN_X0 = 513.65801625
SOURCE_MIN_PERCENT_TOKEN_X0 = 518.98489600
page_label_boundary = DEFAULT_LABEL_BOUNDARY
original_parse_service_area_page = current.parse_service_area_page


def row_text(row: list[dict]) -> str:
    return " ".join(str(word.get("text") or "") for word in row)


def configure_page_label_boundary(page) -> None:
    global page_label_boundary

    visual = current.base.visual_rows(page)
    header_index = None
    for index, row in enumerate(visual):
        text = row_text(row).lower()
        if "service area" in text and "actual" in text and "budget" in text and ("projection" in text or "projections" in text):
            header_index = index
            break
    if header_index is None:
        raise RuntimeError("Build 018 source-layout header row not found")

    net_total_row = None
    for row in visual[header_index + 1:]:
        if row_text(row).strip().lower().startswith("net total"):
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
    if not (150.0 <= page_label_boundary < 280.0):
        raise RuntimeError(f"Build 018 source-layout label boundary out of range: {page_label_boundary}")


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
        elif x < SOURCE_PERCENT_BOUNDARY:
            key = "source_delta"
        else:
            key = "source_delta_pct"
        buckets[key].append(word)
    return buckets


def parse_service_area_page_2026_27(page, page_number: int, heading: str, stable_retrieved_at: str):
    configure_page_label_boundary(page)
    return original_parse_service_area_page(page, page_number, heading, stable_retrieved_at)


if not (SOURCE_MAX_DELTA_TOKEN_X0 < SOURCE_PERCENT_BOUNDARY < SOURCE_MIN_PERCENT_TOKEN_X0):
    raise RuntimeError("Build 018 configured percent boundary is outside the verified source-wide gap")

current.PARSER_VERSION = "build018-current-budget-v2"
current.base.budget_buckets = budget_buckets_2026_27
current.parse_service_area_page = parse_service_area_page_2026_27

if __name__ == "__main__":
    current.main()
