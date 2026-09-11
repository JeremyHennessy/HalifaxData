#!/usr/bin/env python3
"""Validate Build 020 audited-source overlay and its 2018 evidence boundary."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data/audited_financial_sources_build020.json"
OFFICIAL_HOSTS = {"cdn.halifax.ca", "www.halifax.ca"}


def main() -> None:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    meta = payload.get("metadata") or {}
    sources = payload.get("sources") or []
    assert meta.get("build") == "020", meta
    assert meta.get("released_source_years") == list(range(2018, 2026)), meta
    assert meta.get("standard_parser_source_years") == list(range(2019, 2026)), meta
    assert meta.get("ocr_primary_statement_source_years") == [2018], meta
    assert meta.get("remaining_partial_source_years") == [2018], meta
    assert "schedules" in str(meta.get("remaining_gap") or "").lower(), meta
    assert "not invoices" in str(meta.get("payment_boundary") or "").lower(), meta

    by_id = {source.get("id"): source for source in sources}
    assert {"hrm-financials-2018", "hrm-financials-2019"}.issubset(by_id), sorted(by_id)
    source = by_id["hrm-financials-2018"]
    assert source.get("status") == "ready-ocr-primary-statements-partial-schedules", source
    assert source.get("released_records") == 79, source
    assert source.get("validated_ocr_corrections") == 8, source
    assert source.get("deterministic_2019_comparative_overlaps") == 41, source
    assert source.get("deterministic_2019_comparative_matches") == 41, source
    assert source.get("schedule_coverage") == "not_released", source
    assert set(source.get("released_statement_families") or []) == {
        "financial_position", "operations", "net_financial_assets", "cash_flows"
    }, source
    assert source.get("ocr_adapter_version") == "build020-financials-2018-ocr-v4", source
    assert source.get("source_sha256") == "8ddb997b3deaf2985b0fe6901f76ef36a8dd8c6633b434c68b903149651821fe", source
    assert (urlparse(source.get("url") or "").hostname or "").lower() in OFFICIAL_HOSTS, source

    comparator = by_id["hrm-financials-2019"]
    assert comparator.get("role") == "independent validation source for 2018 current-year OCR values", comparator
    assert (urlparse(comparator.get("url") or "").hostname or "").lower() in OFFICIAL_HOSTS, comparator
    assert "not relabelled" in str(comparator.get("finding") or "").lower(), comparator

    print("validated Build 020 audited-source overlay: 2018 primary statements released through proven OCR adapter; 2018 schedules remain explicit gap")


if __name__ == "__main__":
    main()
