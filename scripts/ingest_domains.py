#!/usr/bin/env python3
"""Shared parsing helpers for HalifaxData domain collectors.

This module intentionally has no executable ``main``. Build 005 split the old
monolithic domain collector into dedicated scripts so running a helper module
cannot overwrite the authoritative Build 004 budget artifact.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import requests


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


def provenance(source_id: str, url: str, locator_type: str, locator_value: str, parser_version: str = "build005-v1") -> dict:
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


def infer_page_context(text: str) -> str:
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    skip = {"halifax", "budget and business plan", "statement of compensation", "table of contents"}
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
    indexes = [i for i in [label_idx, actual_idx, projection_idx, current_budget_idx, prior_budget_idx] if i is not None]
    rows = []
    for row_index, row in enumerate(table[header_rows:], start=header_rows):
        if not indexes or len(row) <= max(indexes):
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
        rows.append({
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
            "provenance": provenance(source_id, url, "page/table/row", f"p{page_num}/r{row_index}", "build005-budget-history-v1"),
        })
    return rows
