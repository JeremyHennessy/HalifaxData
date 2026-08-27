#!/usr/bin/env python3
"""Extract source-backed Halifax Regional Council motion outcomes from approved minutes.

Build 016 deliberately treats approved minutes as decision evidence and keeps them
separate from agenda recommendations. Modern coverage follows every posted eSCRIBE
Regional Council minutes PDF in data/generated/council.json. A small, explicitly
incomplete legacy seed proves the pre-eSCRIBE historical path without claiming a
complete archive.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests

ROOT = Path(__file__).resolve().parents[1]
COUNCIL_PATH = ROOT / "data/generated/council.json"
REGISTRY_PATH = ROOT / "data/council_decision_sources.json"
DEFAULT_OUT = ROOT / "data/generated/council_decisions.json"
UA = "HalifaxData/0.16 (+https://github.com/JeremyHennessy/HalifaxData)"
PARSER_VERSION = "build016-council-decisions-v1"

RESULT_RE = re.compile(r"\bMOTION\s+PUT\s+AND\s+(.+?)(?:\s*)$", re.I)
MOVED_RE = re.compile(r"^MOVED\s+by\s+(.+?),\s+seconded\s+by\s+(.+?)(?:\s*$)", re.I)
ITEM_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,4})\s+(.+)$")
MONEY_RE = re.compile(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)")
PROCUREMENT_RE = re.compile(
    r"\b(?:RFP|RFQ|NRFP|RFSQ|TENDER|SOLICITATION|PO|CONTRACT)\s*(?:NO\.?|#|NUMBER)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9-]{2,})\b",
    re.I,
)
CASE_RE = re.compile(r"\b(?:CASE|PLPROJ|PLPPROJ)\s*(?:NO\.?|#)?\s*[:#-]?\s*([A-Z0-9-]{3,})\b", re.I)
CAPITAL_RE = re.compile(r"\b(?:CAPITAL\s+PROJECT|PROJECT\s+CODE|ACCOUNT)\s*(?:NO\.?|#)?\s*[:#-]?\s*([A-Z][A-Z0-9-]{2,})\b", re.I)
FISCAL_WORDS = re.compile(
    r"\b(budget|financial|funding|fund|reserve|grant|procurement|tender|contract|award|capital|debt|borrow|purchase|lease|cost|expenditure|revenue|tax|rate)\b",
    re.I,
)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm_line(value: str) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def source_date(value: str) -> str:
    raw = str(value or "")[:10].replace("/", "-")
    return raw if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", raw) else ""


def canonical_result(raw: str) -> str:
    value = norm_line(raw).rstrip(".").lower()
    if "passed unanimously" in value:
        return "passed_unanimously"
    if value.startswith("passed") or " passed" in value:
        return "passed"
    if "defeated" in value:
        return "defeated"
    if "tied" in value:
        return "tied"
    if "withdrawn" in value:
        return "withdrawn"
    return "other"


def clean_motion_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    for value in lines:
        line = norm_line(value)
        if not line:
            continue
        low = line.lower()
        if low in {"halifax regional council", "minutes"}:
            continue
        if re.fullmatch(r"\d{1,3}", line):
            continue
        if re.fullmatch(r"page\s+\d+(?:\s+of\s+\d+)?", line, re.I):
            continue
        result.append(line)
    return result


def extract_refs(text: str) -> dict[str, list[str]]:
    def unique(values):
        seen = set()
        out = []
        for value in values:
            token = norm_line(value).upper()
            if token and token not in seen:
                seen.add(token)
                out.append(token)
        return out

    return {
        "procurement_refs": unique(PROCUREMENT_RE.findall(text)),
        "case_refs": unique(CASE_RE.findall(text)),
        "capital_account_refs": unique(CAPITAL_RE.findall(text)),
    }


def extract_money(text: str) -> list[dict]:
    values = []
    seen = set()
    for match in MONEY_RE.finditer(text):
        raw = match.group(0)
        amount = float(match.group(1).replace(",", ""))
        key = (raw, amount)
        if key in seen:
            continue
        seen.add(key)
        values.append({"raw": raw, "amount_cad": amount})
    return values


def read_pdf_lines(content: bytes) -> tuple[list[dict], int]:
    rows: list[dict] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
            for line_number, value in enumerate(text.splitlines(), start=1):
                line = norm_line(value)
                if line:
                    rows.append({"text": line, "page": page_number, "line": line_number})
        return rows, len(pdf.pages)


def find_item(lines: list[dict], moved_index: int) -> tuple[str | None, str | None]:
    floor = max(0, moved_index - 300)
    for index in range(moved_index - 1, floor - 1, -1):
        match = ITEM_RE.match(lines[index]["text"])
        if not match:
            continue
        title = norm_line(match.group(2))
        if re.search(r"[A-Za-z]", title):
            return match.group(1), title
    return None, None


def parse_decisions(lines: list[dict], source: dict) -> tuple[list[dict], dict]:
    records: list[dict] = []
    unpaired_results = 0
    seen = set()
    last_result_index = -1

    for result_index, line in enumerate(lines):
        result_match = RESULT_RE.search(line["text"])
        if not result_match:
            continue
        raw_result = norm_line(result_match.group(1))
        result = canonical_result(raw_result)

        moved_index = None
        lower_bound = max(last_result_index + 1, result_index - 180)
        for index in range(result_index - 1, lower_bound - 1, -1):
            if MOVED_RE.match(lines[index]["text"]):
                moved_index = index
                break
        last_result_index = result_index
        if moved_index is None:
            unpaired_results += 1
            continue

        moved_line = lines[moved_index]["text"]
        moved_match = MOVED_RE.match(moved_line)
        if not moved_match:
            unpaired_results += 1
            continue
        mover = norm_line(moved_match.group(1))
        seconder = norm_line(moved_match.group(2))

        body_lines = clean_motion_lines([row["text"] for row in lines[moved_index + 1:result_index]])
        that_index = next((i for i, value in enumerate(body_lines) if re.match(r"^THAT\b", value, re.I)), None)
        if that_index is not None:
            body_lines = body_lines[that_index:]
        motion_text = norm_line(" ".join(body_lines))
        if len(motion_text) < 8:
            unpaired_results += 1
            continue

        item_ref, item_title = find_item(lines, moved_index)
        money_mentions = extract_money(motion_text)
        refs = extract_refs(f"{item_title or ''} {motion_text}")
        fiscal_relevant = bool(money_mentions or FISCAL_WORDS.search(f"{item_title or ''} {motion_text}"))
        decision_key = hashlib.sha256(
            "||".join([
                source["meeting_date"],
                item_ref or "",
                mover,
                motion_text,
                result,
            ]).encode("utf-8")
        ).hexdigest()[:24]
        if decision_key in seen:
            continue
        seen.add(decision_key)

        records.append({
            "decision_id": f"council-{source['meeting_date']}-{decision_key}",
            "meeting_id": source.get("meeting_id"),
            "meeting_date": source["meeting_date"],
            "meeting_name": source.get("meeting_name") or "Halifax Regional Council",
            "coverage_layer": source["coverage_layer"],
            "item_ref": item_ref,
            "item_title": item_title,
            "mover": mover,
            "seconder": seconder,
            "motion_text": motion_text,
            "result_source": raw_result,
            "decision_status": result,
            "motion_passed": result in {"passed", "passed_unanimously"},
            "fiscal_relevant": fiscal_relevant,
            "money_mentions": money_mentions,
            **refs,
            "source_id": source["source_id"],
            "source_url": source["minutes_url"],
            "source_page": line["page"],
            "source_locator": f"minutes p{line['page']} near result line {line['line']}",
            "source_sha256": source["source_sha256"],
            "parser_version": PARSER_VERSION,
            "validation_status": "parsed_from_approved_minutes",
        })

    return records, {"unpaired_result_lines": unpaired_results}


def fetch_pdf(session: requests.Session, url: str) -> tuple[bytes, str]:
    response = session.get(url, timeout=120, allow_redirects=True)
    response.raise_for_status()
    content = response.content
    if not content.startswith(b"%PDF"):
        raise RuntimeError(f"Expected PDF from {url}; received {response.headers.get('content-type')} ({len(content)} bytes)")
    return content, response.url


def modern_sources(council: dict) -> list[dict]:
    sources = []
    for row in council.get("records", []):
        name = str(row.get("meeting_name") or row.get("meeting_type") or "")
        url = row.get("minutes_pdf_url")
        if "halifax regional council" not in name.lower() or not url:
            continue
        date = source_date(row.get("start_date"))
        if not date:
            raise RuntimeError(f"Could not normalize Council meeting date for {row.get('meeting_id')}")
        sources.append({
            "source_id": "hrm-escribe",
            "meeting_id": row.get("meeting_id"),
            "meeting_date": date,
            "meeting_name": row.get("meeting_name") or "Halifax Regional Council",
            "minutes_url": url,
            "coverage_layer": "modern_escribe_complete_posted_minutes_window",
        })
    return sorted(sources, key=lambda row: (row["meeting_date"], str(row.get("meeting_id") or "")))


def legacy_sources(registry: dict) -> list[dict]:
    result = []
    for row in registry.get("legacy_sources", []):
        result.append({
            "source_id": row["source_id"],
            "meeting_id": None,
            "meeting_date": row["meeting_date"],
            "meeting_name": row.get("meeting_name") or "Halifax Regional Council",
            "minutes_url": row["minutes_url"],
            "coverage_layer": "legacy_seed_incomplete",
        })
    return sorted(result, key=lambda row: row["meeting_date"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    council = json.loads(COUNCIL_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    modern = modern_sources(council)
    legacy = legacy_sources(registry)
    if not modern:
        raise RuntimeError("No posted eSCRIBE Regional Council minutes found in council.json")
    if not legacy:
        raise RuntimeError("Legacy Council decision seed is empty")

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "application/pdf,text/html;q=0.8,*/*;q=0.5"})

    all_records: list[dict] = []
    source_status: list[dict] = []
    for source in [*legacy, *modern]:
        content, resolved_url = fetch_pdf(session, source["minutes_url"])
        sha = hashlib.sha256(content).hexdigest()
        source = {**source, "minutes_url": resolved_url, "source_sha256": sha}
        lines, page_count = read_pdf_lines(content)
        records, diagnostics = parse_decisions(lines, source)
        if not records:
            raise RuntimeError(f"No paired motion outcomes parsed from {source['meeting_date']} {resolved_url}")
        all_records.extend(records)
        source_status.append({
            "source_id": source["source_id"],
            "meeting_id": source.get("meeting_id"),
            "meeting_date": source["meeting_date"],
            "coverage_layer": source["coverage_layer"],
            "minutes_url": resolved_url,
            "source_sha256": sha,
            "pdf_pages": page_count,
            "decision_records": len(records),
            **diagnostics,
        })
        print(f"Council decisions {source['meeting_date']}: {len(records)} paired outcomes from {page_count} pages")

    ids = [row["decision_id"] for row in all_records]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate decision IDs produced")

    all_records.sort(key=lambda row: (
        row["meeting_date"],
        row.get("item_ref") or "zzzz",
        int(row.get("source_page") or 0),
        row["decision_id"],
    ))
    passed = sum(1 for row in all_records if row["motion_passed"])
    fiscal = sum(1 for row in all_records if row["fiscal_relevant"])
    money = sum(1 for row in all_records if row["money_mentions"])
    modern_records = sum(1 for row in all_records if row["coverage_layer"].startswith("modern_"))
    legacy_records = len(all_records) - modern_records

    payload = {
        "metadata": {
            "dataset_status": "approved_minutes_motion_outcome_extraction",
            "parser_version": PARSER_VERSION,
            "generated_at": now(),
            "source_registry": str(REGISTRY_PATH.relative_to(ROOT)),
            "modern_calendar_source": str(COUNCIL_PATH.relative_to(ROOT)),
            "modern_meetings_with_posted_minutes": len(modern),
            "legacy_seed_meetings": len(legacy),
            "legacy_seed_complete": False,
            "decision_records": len(all_records),
            "modern_decision_records": modern_records,
            "legacy_decision_records": legacy_records,
            "passed_motion_records": passed,
            "fiscal_relevant_records": fiscal,
            "money_mention_records": money,
            "is_payment_ledger": False,
            "scope": "Motion/result pairs extracted from official approved Regional Council minutes PDFs. Modern eSCRIBE posted-minutes coverage is complete for the checked current calendar window; the pre-2024 legacy set is an explicit incomplete seed.",
            "note": "A passed motion establishes that Council adopted that motion. Dollar mentions are source-text evidence only and are not invoices, payments, final project costs, proof that an amount was spent, or a finding of policy compliance or wrongdoing.",
        },
        "source_status": source_status,
        "records": all_records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print(f"Wrote {len(all_records)} Council decision records to {args.output}")


if __name__ == "__main__":
    main()
