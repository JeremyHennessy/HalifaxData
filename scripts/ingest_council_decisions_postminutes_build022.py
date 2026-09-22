#!/usr/bin/env python3
"""Incrementally append newly posted eSCRIBE PostMinutes decisions.

The checked PDF-derived decision artifact remains immutable input. This adapter:
1) proves one checked meeting is semantically equivalent through PostMinutes HTML;
2) preserves every checked record/status row unchanged;
3) parses only newly posted approved Regional Council PostMinutes meetings;
4) never treats agendas, draft minutes, or a merely reachable PostMinutes URL as approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import requests

import ingest_council_decisions as base
from diagnose_council_postminutes_html_build022 import (
    PostMinutesParser,
    html_to_lines,
    semantic_fingerprint,
    title_compatible,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COUNCIL = ROOT / "data/generated/council.json"
DEFAULT_CHECKED = ROOT / "data/generated/council_decisions.json"
DEFAULT_OUTPUT = ROOT / "data/generated/council_decisions.json"
ADAPTER_VERSION = "build022-postminutes-html-v1"
CONTROL_DATE = "2026-06-23"
UA = "HalifaxData Build022 PostMinutes incremental adapter (+https://github.com/JeremyHennessy/HalifaxData)"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_html(session: requests.Session, url: str) -> tuple[bytes, str]:
    response = session.get(url, timeout=120, allow_redirects=True)
    response.raise_for_status()
    content_type = str(response.headers.get("content-type") or "").lower()
    if "text/html" not in content_type:
        raise RuntimeError(f"Expected PostMinutes HTML from {url}; got {content_type!r}")
    content = response.content
    if b"AgendaItemMinutes" not in content or b"MINUTES" not in content.upper():
        raise RuntimeError(f"PostMinutes HTML did not contain the expected minutes structure: {response.url}")
    return content, response.url


def meeting_date(row: dict) -> str:
    return base.source_date(row.get("start_date"))


def regional_postminutes(council: dict) -> list[dict]:
    rows = []
    for row in council.get("records") or []:
        name = str(row.get("meeting_name") or row.get("meeting_type") or "")
        if "halifax regional council" not in name.lower():
            continue
        if row.get("meeting_passed") is not True:
            continue
        if not row.get("minutes_html_url"):
            continue
        date = meeting_date(row)
        if not date:
            raise RuntimeError(f"Could not normalize meeting date for {row.get('meeting_id')}")
        rows.append({**row, "_meeting_date": date})
    return sorted(rows, key=lambda row: (row["_meeting_date"], str(row.get("meeting_id") or "")))


def parse_html_meeting(session: requests.Session, meeting: dict) -> tuple[list[dict], dict]:
    content, resolved_url = fetch_html(session, meeting["minutes_html_url"])
    parser = PostMinutesParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    lines = html_to_lines(content)
    source = {
        "source_id": "hrm-escribe",
        "meeting_id": meeting.get("meeting_id"),
        "meeting_date": meeting["_meeting_date"],
        "meeting_name": meeting.get("meeting_name") or "Halifax Regional Council",
        "minutes_url": resolved_url,
        "coverage_layer": "modern_escribe_complete_posted_minutes_window",
        "source_sha256": hashlib.sha256(content).hexdigest(),
    }
    records, diagnostics = base.parse_decisions(lines, source)
    if not records:
        raise RuntimeError(f"No decisions parsed from approved PostMinutes HTML for {meeting['_meeting_date']}")
    if diagnostics.get("unpaired_result_lines") != 0:
        raise RuntimeError(
            f"PostMinutes HTML for {meeting['_meeting_date']} has "
            f"{diagnostics.get('unpaired_result_lines')} unpaired result line(s)"
        )

    for row in records:
        item_position = int(row.get("source_page") or 0)
        row["source_format"] = "postminutes_html"
        row["source_item_position"] = item_position
        row["source_locator"] = (
            f"PostMinutes HTML agenda item {row.get('item_ref') or item_position} "
            f"(synthetic parser position {item_position})"
        )
        row["validation_status"] = "parsed_from_approved_postminutes_html"
        row["html_adapter_version"] = ADAPTER_VERSION

    status = {
        "source_id": "hrm-escribe",
        "meeting_id": meeting.get("meeting_id"),
        "meeting_date": meeting["_meeting_date"],
        "coverage_layer": "modern_escribe_complete_posted_minutes_window",
        "minutes_url": resolved_url,
        "source_sha256": source["source_sha256"],
        "source_format": "postminutes_html",
        "html_agenda_items": len(parser.items),
        "decision_records": len(records),
        **diagnostics,
    }
    return records, status


def prove_control(session: requests.Session, council: dict, checked: dict) -> dict:
    meeting = next(
        (row for row in regional_postminutes(council) if row["_meeting_date"] == CONTROL_DATE),
        None,
    )
    if not meeting:
        raise RuntimeError(f"Control meeting {CONTROL_DATE} is not present with approved PostMinutes HTML")
    expected = [
        row for row in checked.get("records") or []
        if row.get("meeting_date") == CONTROL_DATE
        and row.get("coverage_layer") == "modern_escribe_complete_posted_minutes_window"
    ]
    if not expected:
        raise RuntimeError(f"Checked decision control set is missing for {CONTROL_DATE}")

    content, resolved_url = fetch_html(session, meeting["minutes_html_url"])
    source = {
        "source_id": "hrm-escribe",
        "meeting_id": meeting.get("meeting_id"),
        "meeting_date": CONTROL_DATE,
        "meeting_name": meeting.get("meeting_name") or "Halifax Regional Council",
        "minutes_url": resolved_url,
        "coverage_layer": "modern_escribe_complete_posted_minutes_window",
        "source_sha256": hashlib.sha256(content).hexdigest(),
    }
    parsed, diagnostics = base.parse_decisions(html_to_lines(content), source)
    expected_by = {semantic_fingerprint(row): row for row in expected}
    parsed_by = {semantic_fingerprint(row): row for row in parsed}
    missing = set(expected_by) - set(parsed_by)
    new = set(parsed_by) - set(expected_by)
    title_mismatches = [
        fingerprint
        for fingerprint in set(expected_by) & set(parsed_by)
        if not title_compatible(expected_by[fingerprint], parsed_by[fingerprint])
    ]
    if missing or new or title_mismatches or len(parsed) != len(expected) or diagnostics.get("unpaired_result_lines") != 0:
        raise RuntimeError(
            "PostMinutes HTML control no longer matches checked PDF-derived decision semantics: "
            f"missing={len(missing)} new={len(new)} title_mismatches={len(title_mismatches)} "
            f"parsed={len(parsed)} expected={len(expected)} diagnostics={diagnostics}"
        )
    return {
        "meeting_date": CONTROL_DATE,
        "checked_decisions": len(expected),
        "html_decisions": len(parsed),
        "semantic_equivalence": True,
        "source_url": resolved_url,
    }


def recalc_metadata(payload: dict) -> None:
    rows = payload.get("records") or []
    statuses = payload.get("source_status") or []
    meta = payload.setdefault("metadata", {})
    modern_rows = sum(1 for row in rows if str(row.get("coverage_layer") or "").startswith("modern_"))
    legacy_rows = len(rows) - modern_rows
    meta["generated_at"] = base.now()
    meta["decision_records"] = len(rows)
    meta["modern_decision_records"] = modern_rows
    meta["legacy_decision_records"] = legacy_rows
    meta["passed_motion_records"] = sum(1 for row in rows if row.get("motion_passed"))
    meta["fiscal_relevant_records"] = sum(1 for row in rows if row.get("fiscal_relevant"))
    meta["money_mention_records"] = sum(1 for row in rows if row.get("money_mentions"))
    meta["modern_meetings_with_posted_minutes"] = sum(
        1 for row in statuses if row.get("coverage_layer") == "modern_escribe_complete_posted_minutes_window"
    )
    meta["incremental_adapter_version"] = ADAPTER_VERSION
    meta["incremental_transport"] = "official eSCRIBE PostMinutes HTML; checked PDF-derived rows remain preserved"
    meta["incremental_approval_rule"] = (
        "Only refreshed Regional Council calendar rows with meeting_passed=true and an explicit minutes_html_url "
        "are eligible. Reachability of a guessed PostMinutes URL is not approval evidence."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--council", type=Path, default=DEFAULT_COUNCIL)
    parser.add_argument("--checked", type=Path, default=DEFAULT_CHECKED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()

    council = load(args.council)
    checked = load(args.checked)
    payload = json.loads(json.dumps(checked))
    existing_status = payload.get("source_status") or []
    existing_meeting_ids = {
        str(row.get("meeting_id"))
        for row in existing_status
        if row.get("coverage_layer") == "modern_escribe_complete_posted_minutes_window" and row.get("meeting_id")
    }

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
    control = prove_control(session, council, checked)

    candidates = [
        row for row in regional_postminutes(council)
        if str(row.get("meeting_id") or "") not in existing_meeting_ids
    ]
    appended_records: list[dict] = []
    appended_status: list[dict] = []
    for meeting in candidates:
        records, status = parse_html_meeting(session, meeting)
        appended_records.extend(records)
        appended_status.append(status)
        print(
            f"PostMinutes decisions {meeting['_meeting_date']}: "
            f"{len(records)} paired outcomes from {status['html_agenda_items']} agenda item(s)"
        )

    if not candidates:
        print("No newly posted approved Regional Council PostMinutes meetings to append.")
        if args.output != args.checked:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(args.checked.read_bytes())
        summary = {
            "control": control,
            "candidate_meetings": 0,
            "appended_decisions": 0,
            "decision_records": len(payload.get("records") or []),
            "changed": False,
        }
    else:
        payload.setdefault("records", []).extend(appended_records)
        payload.setdefault("source_status", []).extend(appended_status)
        ids = [row.get("decision_id") for row in payload["records"]]
        if any(not value for value in ids) or len(ids) != len(set(ids)):
            raise RuntimeError("Incremental PostMinutes adapter produced missing or duplicate decision IDs")
        payload["records"].sort(key=lambda row: (
            str(row.get("meeting_date") or ""),
            str(row.get("item_ref") or "zzzz"),
            int(row.get("source_item_position") or row.get("source_page") or 0),
            str(row.get("decision_id") or ""),
        ))
        payload["source_status"].sort(key=lambda row: (
            str(row.get("meeting_date") or ""),
            str(row.get("meeting_id") or ""),
            str(row.get("source_id") or ""),
        ))
        recalc_metadata(payload)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.output.with_suffix(args.output.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(args.output)
        summary = {
            "control": control,
            "candidate_meetings": len(candidates),
            "candidate_dates": [row["_meeting_date"] for row in candidates],
            "appended_decisions": len(appended_records),
            "decision_records": len(payload["records"]),
            "changed": True,
        }

    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
