#!/usr/bin/env python3
"""Run the established conservative audited-financial parser over Build 017 sources.

Build 017 changes only the configured official-source set. It deliberately reuses
scripts/ingest_financial_history.py unchanged so the previously validated parsing
semantics remain the control while released source-year coverage expands from two
to seven (2019–2025). The official 2018 source remains an explicit parse gap.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import ingest_financial_history as base

ROOT = Path(__file__).resolve().parents[1]
BASE_REGISTRY = ROOT / "data/sources.json"
SUPPLEMENTAL_REGISTRY = ROOT / "data/audited_financial_sources.json"


def main() -> None:
    base_registry = json.loads(BASE_REGISTRY.read_text(encoding="utf-8"))
    supplemental = json.loads(SUPPLEMENTAL_REGISTRY.read_text(encoding="utf-8"))

    sources = list(base_registry.get("sources") or [])
    by_id = {source.get("id"): source for source in sources if source.get("id")}
    for source in supplemental.get("sources") or []:
        source_id = source.get("id")
        if not source_id:
            raise RuntimeError("Build 017 supplemental financial source is missing an ID")
        if source_id in by_id and by_id[source_id] != source:
            raise RuntimeError(f"Build 017 source ID conflicts with base registry: {source_id}")
        if source_id not in by_id:
            sources.append(source)
            by_id[source_id] = source

    expected_years = list(supplemental.get("metadata", {}).get("expected_source_years") or [])
    financial_sources = [
        source for source in sources
        if str(source.get("id") or "").startswith("hrm-financials-")
        and str(source.get("status") or "").startswith("ready")
    ]
    actual_years = sorted(int(str(source["id"]).rsplit("-", 1)[1]) for source in financial_sources)
    if actual_years != expected_years:
        raise RuntimeError(f"Configured audited source years {actual_years} != expected Build 017 years {expected_years}")

    combined = {
        "metadata": {
            **(base_registry.get("metadata") or {}),
            "build017_audited_source_expansion": supplemental.get("metadata") or {},
        },
        "sources": sources,
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        json.dump(combined, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        combined_path = Path(handle.name)

    original_registry = base.REGISTRY
    try:
        base.REGISTRY = combined_path
        base.main()
    finally:
        base.REGISTRY = original_registry
        combined_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
