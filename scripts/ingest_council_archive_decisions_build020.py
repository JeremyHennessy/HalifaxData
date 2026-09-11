#!/usr/bin/env python3
"""Build 020 full candidate extraction for historical Regional Council decisions.

This collector reads the released 249-row Council archive inventory and attempts the
unchanged Build 016 approved-minutes parser against every minutes-bearing, non-status
Regional Council row. It never silently drops a source: every eligible meeting receives
an explicit parsed, parse_gap, or error source status in the candidate artifact.

No production council_decisions.json file is modified by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

import ingest_council_decisions as base

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_PATH = ROOT / "data/generated/council_archive.json"
DEFAULT_OUT = ROOT / "artifacts/build020-council-archive-decisions.json"
SOURCE_ID = "hrm-historical-council-table"
COVERAGE_LAYER = "historical_halifax_meeting_table"
REQUEST_DELAY_SECONDS = 0.25
NO_MOTION_PATH = ROOT / "data/council_no_motion_sources_build020.json"


def reviewed_no_motion(source: dict, lines: list[dict], page_count: int,
                       records: list[dict], diagnostics: dict) -> dict | None:
    """Accept only an exact reviewed document; unknown empty parses stay gaps."""
    if records or diagnostics.get("unpaired_result_lines") != 0:
        return None
    text = " ".join(line["text"] for line in lines)
    if re.search(r"\b(MOTION|MOVED|SECONDED)\b", text, re.I):
        return None
    registry = json.loads(NO_MOTION_PATH.read_text(encoding="utf-8"))
    for review in registry["sources"]:
        if (all(source.get(key) == review[key] for key in
                ("meeting_date", "minutes_url", "source_sha256"))
                and page_count == review["pdf_pages"] and len(lines) >= 20):
            return review
    return None


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def eligible(row: dict) -> bool:
    return bool(
        row.get("minutes_url")
        and row.get("has_minutes_pdf") is True
        and not row.get("meeting_date_note_source")
        and row.get("meeting_type") == "Regional Council"
    )


def source_from_archive(row: dict) -> dict:
    return {
        "source_id": SOURCE_ID,
        "meeting_id": row["archive_meeting_id"],
        "meeting_date": row["meeting_date"],
        "meeting_name": "Halifax Regional Council",
        "minutes_url": row["minutes_url"],
        "coverage_layer": COVERAGE_LAYER,
        "archive_agenda_url": row.get("agenda_url"),
        "archive_source_search_url": row.get("source_search_url"),
    }


def status_base(source: dict, archive_row: dict) -> dict:
    return {
        "source_id": SOURCE_ID,
        "meeting_id": source["meeting_id"],
        "meeting_date": source["meeting_date"],
        "coverage_layer": COVERAGE_LAYER,
        "archive_minutes_url": archive_row.get("minutes_url"),
        "archive_agenda_url": archive_row.get("agenda_url"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    archive_meta = archive.get("metadata") or {}
    if archive_meta.get("dataset_status") != "official_halifax_regional_council_historical_meeting_inventory":
        raise RuntimeError("Historical Council archive is not the released Build 020 inventory")
    if archive_meta.get("records") != 249 or archive_meta.get("minutes_pdf_records") != 245:
        raise RuntimeError("Historical Council archive shape changed from the proven 249/245 release")

    archive_rows = list(archive.get("records") or [])
    selected = sorted([row for row in archive_rows if eligible(row)], key=lambda row: (row["meeting_date"], row["archive_meeting_id"]))
    if len(selected) != archive_meta.get("minutes_pdf_records"):
        raise RuntimeError(
            f"Eligible historical minutes count {len(selected)} != released minutes count {archive_meta.get('minutes_pdf_records')}"
        )

    session = requests.Session()
    session.headers.update({"User-Agent": base.UA, "Accept": "application/pdf,text/html;q=0.8,*/*;q=0.5"})

    all_records: list[dict] = []
    source_status: list[dict] = []
    for index, archive_row in enumerate(selected, start=1):
        source = source_from_archive(archive_row)
        base_status = status_base(source, archive_row)
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            content, resolved_url = base.fetch_pdf(session, source["minutes_url"])
            sha = hashlib.sha256(content).hexdigest()
            source = {**source, "minutes_url": resolved_url, "source_sha256": sha}
            lines, page_count = base.read_pdf_lines(content)
            records, diagnostics = base.parse_decisions(lines, source)
            if not records:
                review = reviewed_no_motion(source, lines, page_count, records, diagnostics)
                if review:
                    source_status.append({
                        **base_status,
                        "status": "verified_no_motion_outcomes",
                        "minutes_url": resolved_url,
                        "source_sha256": sha,
                        "pdf_pages": page_count,
                        "pdf_text_lines": len(lines),
                        "decision_records": 0,
                        **diagnostics,
                        "review_registry": NO_MOTION_PATH.relative_to(ROOT).as_posix(),
                        "review_note": review["review_note"],
                    })
                    print(f"[{index}/{len(selected)}] {source['meeting_date']}: VERIFIED_NO_MOTION_OUTCOMES")
                    continue
                source_status.append({
                    **base_status,
                    "status": "parse_gap",
                    "minutes_url": resolved_url,
                    "source_sha256": sha,
                    "pdf_pages": page_count,
                    "pdf_text_lines": len(lines),
                    "decision_records": 0,
                    **diagnostics,
                    "error": "Build 016 parser produced zero paired motion/result decisions from the approved minutes.",
                })
                print(f"[{index}/{len(selected)}] {source['meeting_date']}: PARSE_GAP pages={page_count} lines={len(lines)}")
                continue

            all_records.extend(records)
            source_status.append({
                **base_status,
                "status": "parsed",
                "minutes_url": resolved_url,
                "source_sha256": sha,
                "pdf_pages": page_count,
                "pdf_text_lines": len(lines),
                "decision_records": len(records),
                **diagnostics,
            })
            print(
                f"[{index}/{len(selected)}] {source['meeting_date']}: parsed={len(records)} "
                f"pages={page_count} unpaired={diagnostics.get('unpaired_result_lines', 0)}"
            )
        except Exception as exc:
            source_status.append({
                **base_status,
                "status": "error",
                "decision_records": 0,
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            print(f"[{index}/{len(selected)}] {source['meeting_date']}: ERROR {type(exc).__name__}: {exc}")

    decision_ids = [row["decision_id"] for row in all_records]
    duplicate_ids = len(decision_ids) - len(set(decision_ids))
    if duplicate_ids:
        raise RuntimeError(f"Historical archive candidate produced {duplicate_ids} duplicate decision IDs")

    all_records.sort(key=lambda row: (
        row["meeting_date"],
        row.get("item_ref") or "zzzz",
        int(row.get("source_page") or 0),
        row["decision_id"],
    ))
    status_counts = Counter(item["status"] for item in source_status)
    decisions_by_year: dict[str, int] = {}
    parsed_meetings_by_year: dict[str, int] = {}
    for row in all_records:
        year = row["meeting_date"][:4]
        decisions_by_year[year] = decisions_by_year.get(year, 0) + 1
    for item in source_status:
        if item["status"] == "parsed":
            year = item["meeting_date"][:4]
            parsed_meetings_by_year[year] = parsed_meetings_by_year.get(year, 0) + 1

    payload = {
        "metadata": {
            "build": "020",
            "dataset_status": "historical_council_decision_archive_candidate",
            "generated_at": now(),
            "parser_version": base.PARSER_VERSION,
            "archive_source": str(ARCHIVE_PATH.relative_to(ROOT)),
            "archive_records": archive_meta.get("records"),
            "eligible_minutes_sources": len(selected),
            "source_status_counts": dict(sorted(status_counts.items())),
            "decision_records": len(all_records),
            "decisions_by_year": dict(sorted(decisions_by_year.items())),
            "parsed_meetings_by_year": dict(sorted(parsed_meetings_by_year.items())),
            "fiscal_relevant_records": sum(1 for row in all_records if row.get("fiscal_relevant")),
            "money_mention_records": sum(1 for row in all_records if row.get("money_mentions")),
            "source_status": source_status,
            "is_payment_ledger": False,
            "payment_facts": 0,
            "scope": "Candidate-only application of the unchanged Build 016 approved-minutes motion/result parser to every minutes-bearing, non-status Regional Council row in the released Build 020 historical archive inventory.",
            "note": "Every eligible historical source is accounted for as parsed, exact-document verified_no_motion_outcomes, parse_gap or error. Only four SHA-pinned, visually reviewed ceremony minutes qualify for the no-motion status; missing or failed sources remain unverified. Dollar mentions are Council source text, not invoices, vendor payments, final paid values or findings of wrongdoing.",
            "release_status": "candidate_not_production",
        },
        "records": all_records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["metadata"], indent=2))


if __name__ == "__main__":
    main()
