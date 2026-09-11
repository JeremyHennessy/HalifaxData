#!/usr/bin/env python3
"""Promote a validated Build 020 Council archive candidate to checked-in release form."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "artifacts/build020-council-archive.json"
DEFAULT_OUT = ROOT / "data/generated/council_archive.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    meta = candidate.get("metadata") or {}
    if meta.get("dataset_status") != "official_halifax_regional_council_historical_meeting_inventory_candidate":
        raise RuntimeError(f"Unexpected candidate dataset_status: {meta.get('dataset_status')!r}")
    if meta.get("release_status") != "candidate_not_production":
        raise RuntimeError(f"Unexpected candidate release_status: {meta.get('release_status')!r}")
    if meta.get("advertised_result_count") != 249 or meta.get("records") != 249:
        raise RuntimeError("Candidate no longer has the proven 249-row archive shape")
    if meta.get("minutes_pdf_records") != 245 or meta.get("missing_minutes_records") != 4:
        raise RuntimeError("Candidate minutes coverage changed unexpectedly")
    if meta.get("min_meeting_date") != "2016-01-12" or meta.get("max_meeting_date") != "2024-11-05":
        raise RuntimeError("Candidate date range changed unexpectedly")

    released = copy.deepcopy(candidate)
    released["metadata"]["dataset_status"] = "official_halifax_regional_council_historical_meeting_inventory"
    released["metadata"]["release_status"] = "released_checked_in"
    released["metadata"]["note"] = (
        "This checked-in inventory records official Halifax historical meeting/minutes discovery evidence only. "
        "It does not expand council_decisions.json by itself, and it does not assert payment, spending or wrongdoing."
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(released, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("promoted Build 020 Council archive: 249 official Regional Council rows; 245 minutes PDFs")


if __name__ == "__main__":
    main()
