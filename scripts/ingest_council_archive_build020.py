#!/usr/bin/env python3
"""Collect the official Halifax pre-eSCRIBE Regional Council meeting inventory.

Halifax's agendas/meetings/reports page exposes a paginated historical table for
Regional Council (category 931). This collector inventories that table only; it does
not parse minutes into decisions and does not alter the modern eSCRIBE calendar.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "artifacts/build020-council-archive.json"
BASE_URL = "https://www.halifax.ca/city-hall/agendas-meetings-reports"
CATEGORY = "931"
UA = "HalifaxData/0.20 (+https://github.com/JeremyHennessy/HalifaxData)"
EXPECTED_HEADER = ["Date", "Type", "Agenda", "Minutes (PDF)", "Video"]
DATE_FORMAT = "%B %d, %Y"
DATE_PREFIX_RE = re.compile(r"^([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})(?:\s+(.*))?$")
RETRYABLE = {429, 500, 502, 503, 504}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value: str) -> str:
    return " ".join(html.unescape(str(value or "")).replace("\u00a0", " ").split())


class TableParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.tables: list[list[list[dict]]] = []
        self._table_depth = 0
        self._table: list[list[dict]] | None = None
        self._row: list[dict] | None = None
        self._cell: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._table = []
        elif tag == "tr" and self._table_depth == 1:
            self._row = []
        elif tag in {"td", "th"} and self._table_depth == 1 and self._row is not None:
            self._cell = {"tag": tag, "text": [], "links": []}
        elif tag == "a" and self._cell is not None:
            href = attrs_map.get("href")
            if href:
                self._cell["links"].append(urljoin(self.base_url, html.unescape(href)))

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None:
            self._cell["text"] = clean(" ".join(self._cell["text"]))
            if self._row is not None:
                self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._table is not None and self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table_depth:
            if self._table_depth == 1 and self._table is not None:
                self.tables.append(self._table)
                self._table = None
            self._table_depth -= 1


def fetch_html(session: requests.Session, page_index: int) -> tuple[str, str, int]:
    params = {"category": CATEGORY, "page": str(page_index)}
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            response = session.get(BASE_URL, params=params, timeout=90, allow_redirects=True)
            if response.status_code in RETRYABLE:
                raise requests.HTTPError(f"retryable HTTP {response.status_code}", response=response)
            response.raise_for_status()
            if "text/html" not in str(response.headers.get("content-type") or "").lower():
                raise RuntimeError(f"Expected HTML from {response.url}; received {response.headers.get('content-type')!r}")
            return response.text, response.url, response.status_code
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt == 5:
                break
            retry_after = None
            response = getattr(exc, "response", None)
            if response is not None:
                raw = response.headers.get("Retry-After")
                if raw and raw.isdigit():
                    retry_after = min(int(raw), 20)
            time.sleep(retry_after if retry_after is not None else min(1.5 * attempt, 7.5))
    raise RuntimeError(f"Historical Council archive page {page_index} failed after retries: {last_error}")


def result_count(text: str) -> int:
    match = re.search(r"<h3[^>]*>\s*([\d,]+)\s+Results\s*</h3>", text, re.I)
    if not match:
        raise RuntimeError("Could not locate advertised historical meeting result count")
    return int(match.group(1).replace(",", ""))


def find_meeting_table(text: str, source_url: str) -> list[list[dict]]:
    parser = TableParser(source_url)
    parser.feed(text)
    matches = []
    for table in parser.tables:
        if not table:
            continue
        header = [clean(cell.get("text")) for cell in table[0]]
        if header == EXPECTED_HEADER:
            matches.append(table)
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one historical meetings table; found {len(matches)}")
    return matches[0]


def first_link(cell: dict) -> str | None:
    links = [str(value) for value in cell.get("links") or [] if str(value).startswith(("http://", "https://"))]
    return links[0] if links else None


def normalize_minutes_identity(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.path.lower().rstrip("/")


def parse_source_date(date_text: str, page_index: int, row_index: int) -> tuple[str, str | None]:
    match = DATE_PREFIX_RE.fullmatch(date_text)
    if not match:
        raise RuntimeError(f"Page {page_index} row {row_index}: invalid meeting date/status cell {date_text!r}")
    date_part = match.group(1)
    note = clean(match.group(2)) if match.group(2) else None
    try:
        meeting_date = datetime.strptime(date_part, DATE_FORMAT).date().isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Page {page_index} row {row_index}: invalid meeting date {date_part!r}") from exc
    return meeting_date, note


def parse_row(row: list[dict], page_index: int, row_index: int, search_url: str) -> dict:
    if len(row) != len(EXPECTED_HEADER):
        raise RuntimeError(f"Page {page_index} row {row_index}: expected 5 cells, found {len(row)}")
    values = [clean(cell.get("text")) for cell in row]
    date_text, meeting_type = values[0], values[1]
    if meeting_type != "Regional Council":
        raise RuntimeError(f"Page {page_index} row {row_index}: unexpected meeting type {meeting_type!r}")
    meeting_date, date_note = parse_source_date(date_text, page_index, row_index)

    agenda_url = first_link(row[2])
    minutes_url = first_link(row[3])
    video_url = first_link(row[4])
    if not agenda_url:
        raise RuntimeError(f"Page {page_index} row {row_index}: meeting has no agenda/details URL")
    identity = hashlib.sha256(f"{meeting_date}|{date_note or ''}|{agenda_url}|{minutes_url or ''}".encode("utf-8")).hexdigest()[:20]
    return {
        "archive_meeting_id": f"hrm-regional-council-archive-{identity}",
        "meeting_date": meeting_date,
        "meeting_date_source": date_text,
        "meeting_date_note_source": date_note,
        "meeting_type": meeting_type,
        "agenda_url": agenda_url,
        "minutes_url": minutes_url,
        "minutes_identity": normalize_minutes_identity(minutes_url),
        "video_url": video_url,
        "has_minutes_pdf": bool(minutes_url),
        "source_page_index": page_index,
        "source_row_index": row_index,
        "source_search_url": search_url,
        "source_category": CATEGORY,
        "publisher": "Halifax Regional Municipality",
        "source_kind": "official_historical_meeting_table",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})

    first_text, first_url, _ = fetch_html(session, 0)
    advertised = result_count(first_text)
    first_table = find_meeting_table(first_text, first_url)
    first_rows = first_table[1:]
    if not first_rows:
        raise RuntimeError("Historical Regional Council table returned no meeting rows")
    page_size = len(first_rows)
    total_pages = math.ceil(advertised / page_size)
    if total_pages < 1 or total_pages > 100:
        raise RuntimeError(f"Implausible historical archive page count: {total_pages}")

    records: list[dict] = []
    page_status: list[dict] = []
    for page_index in range(total_pages):
        if page_index == 0:
            text, source_url = first_text, first_url
            table = first_table
        else:
            text, source_url, _ = fetch_html(session, page_index)
            page_advertised = result_count(text)
            if page_advertised != advertised:
                raise RuntimeError(f"Historical result count drifted while crawling: page0={advertised}, page{page_index}={page_advertised}")
            table = find_meeting_table(text, source_url)
            time.sleep(0.20)
        rows = table[1:]
        if page_index < total_pages - 1 and len(rows) != page_size:
            raise RuntimeError(f"Historical page {page_index} returned {len(rows)} rows; expected page size {page_size}")
        page_status.append({"page_index": page_index, "url": source_url, "rows": len(rows)})
        for row_index, row in enumerate(rows, start=1):
            records.append(parse_row(row, page_index, row_index, source_url))

    keys = [record["archive_meeting_id"] for record in records]
    if len(keys) != len(set(keys)):
        raise RuntimeError("Historical archive produced duplicate stable meeting identities")
    if len(records) != advertised:
        raise RuntimeError(f"Harvested {len(records)} Regional Council rows but Halifax advertised {advertised}")

    records.sort(key=lambda row: (row["meeting_date"], row["archive_meeting_id"]), reverse=True)
    dates = [row["meeting_date"] for row in records]
    by_year: dict[str, int] = {}
    date_notes: dict[str, int] = {}
    for row in records:
        year = row["meeting_date"][:4]
        by_year[year] = by_year.get(year, 0) + 1
        note = row.get("meeting_date_note_source")
        if note:
            date_notes[note] = date_notes.get(note, 0) + 1
    minutes_count = sum(1 for row in records if row["minutes_url"])

    payload = {
        "metadata": {
            "build": "020",
            "dataset_status": "official_halifax_regional_council_historical_meeting_inventory_candidate",
            "generated_at": now(),
            "source_url": BASE_URL,
            "source_category": CATEGORY,
            "advertised_result_count": advertised,
            "records": len(records),
            "page_size": page_size,
            "pages_fetched": total_pages,
            "min_meeting_date": min(dates),
            "max_meeting_date": max(dates),
            "records_by_year": dict(sorted(by_year.items())),
            "date_status_notes": dict(sorted(date_notes.items())),
            "minutes_pdf_records": minutes_count,
            "missing_minutes_records": len(records) - minutes_count,
            "page_status": page_status,
            "scope": "Official Halifax Regional Council historical meeting-table inventory exposed by the pre-eSCRIBE agendas/meetings/reports search. Date-cell status text such as Rescheduled is preserved separately. This is meeting/minutes discovery evidence only; it is not Council decision extraction and not payment evidence.",
            "pre_2017_boundary": "Halifax directs users seeking meetings prior to 2017 to the separate legacy archive / Municipal Clerk path; this candidate does not assert pre-2017 completeness.",
            "release_status": "candidate_not_production",
        },
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["metadata"], indent=2))


if __name__ == "__main__":
    main()
