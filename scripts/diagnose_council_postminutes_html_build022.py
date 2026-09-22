#!/usr/bin/env python3
"""Prove that official eSCRIBE PostMinutes HTML reproduces checked Council decisions.

This is a diagnostic equivalence test only. It does not update production artifacts.
The established PDF-derived decision IDs are the control surface.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

import requests

import ingest_council_decisions as decisions

ROOT = Path(__file__).resolve().parents[1]
COUNCIL = ROOT / "data/generated/council.json"
CHECKED = ROOT / "data/generated/council_decisions.json"
DEFAULT_DATE = "2026-06-23"
UA = "HalifaxData Build022 PostMinutes equivalence (+https://github.com/JeremyHennessy/HalifaxData)"


class PostMinutesParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict] = []
        self.item_stack: list[dict] = []
        self.counter_stack: list[dict] = []
        self.title_stack: list[dict] = []
        self.minutes_stack: list[dict] = []
        self.tag_stack: list[tuple[str, dict]] = []
        self.sequence = 0

    @staticmethod
    def _classes(attrs) -> set[str]:
        values = dict(attrs).get("class", "")
        return {value for value in str(values).split() if value}

    @staticmethod
    def _break(item: dict) -> None:
        minutes = item["minutes"]
        if minutes and minutes[-1] != "\n":
            minutes.append("\n")

    def handle_starttag(self, tag: str, attrs) -> None:
        classes = self._classes(attrs)
        frame: dict = {}

        if self.minutes_stack and tag in {"p", "br", "li"}:
            self._break(self.minutes_stack[-1])

        if "AgendaItemContainer" in classes:
            self.sequence += 1
            item = {"counter": [], "title": [], "minutes": [], "sequence": self.sequence}
            self.item_stack.append(item)
            frame["container"] = item

        if self.item_stack:
            current = self.item_stack[-1]
            if "AgendaItemCounter" in classes:
                self.counter_stack.append(current)
                frame["counter"] = current
            if "AgendaItemTitle" in classes:
                self.title_stack.append(current)
                frame["title"] = current
            if "AgendaItemMinutes" in classes:
                self.minutes_stack.append(current)
                frame["minutes"] = current

        if tag not in self.VOID_TAGS:
            self.tag_stack.append((tag, frame))

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self.counter_stack:
            self.counter_stack[-1]["counter"].append(data)
        if self.title_stack:
            self.title_stack[-1]["title"].append(data)
        if self.minutes_stack:
            self.minutes_stack[-1]["minutes"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.minutes_stack and tag in {"p", "li"}:
            self._break(self.minutes_stack[-1])
        if not self.tag_stack:
            return

        frame = None
        while self.tag_stack:
            open_tag, candidate = self.tag_stack.pop()
            if open_tag == tag:
                frame = candidate
                break
        if frame is None:
            return

        if frame.get("counter") is not None:
            item = frame["counter"]
            if self.counter_stack and self.counter_stack[-1] is item:
                self.counter_stack.pop()
        if frame.get("title") is not None:
            item = frame["title"]
            if self.title_stack and self.title_stack[-1] is item:
                self.title_stack.pop()
        if frame.get("minutes") is not None:
            item = frame["minutes"]
            if self.minutes_stack and self.minutes_stack[-1] is item:
                self.minutes_stack.pop()
        if frame.get("container") is not None:
            item = frame["container"]
            if self.item_stack and self.item_stack[-1] is item:
                self.item_stack.pop()
            counter = decisions.norm_line("".join(item["counter"]))
            title = decisions.norm_line("".join(item["title"]))
            raw_minutes = "".join(item["minutes"])
            minute_lines = [
                decisions.norm_line(line)
                for line in raw_minutes.splitlines()
                if decisions.norm_line(line)
            ]
            if counter or title or minute_lines:
                self.items.append({
                    "counter": counter,
                    "title": title,
                    "minute_lines": minute_lines,
                    "sequence": item["sequence"],
                })



def html_to_lines(content: bytes) -> list[dict]:
    parser = PostMinutesParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    output: list[dict] = []
    line_number = 0
    for item_index, item in enumerate(sorted(parser.items, key=lambda row: row['sequence']), start=1):
        header = decisions.norm_line(f"{item['counter']} {item['title']}")
        if header:
            line_number += 1
            output.append({"text": header, "page": item_index, "line": line_number})
        for value in item["minute_lines"]:
            line_number += 1
            output.append({"text": value, "page": item_index, "line": line_number})
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--meeting-date", default=DEFAULT_DATE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    council = json.loads(COUNCIL.read_text(encoding="utf-8"))
    checked = json.loads(CHECKED.read_text(encoding="utf-8"))
    meeting = next(
        (
            row for row in council.get("records", [])
            if decisions.source_date(row.get("start_date")) == args.meeting_date
            and "halifax regional council" in str(row.get("meeting_name") or row.get("meeting_type") or "").lower()
            and row.get("minutes_html_url")
        ),
        None,
    )
    if not meeting:
        raise SystemExit(f"No checked Regional Council meeting with PostMinutes HTML for {args.meeting_date}")

    expected = [
        row for row in checked.get("records", [])
        if row.get("meeting_date") == args.meeting_date
        and row.get("coverage_layer") == "modern_escribe_complete_posted_minutes_window"
    ]
    if not expected:
        raise SystemExit(f"No checked PDF-derived decision controls for {args.meeting_date}")

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
    response = session.get(meeting["minutes_html_url"], timeout=120, allow_redirects=True)
    response.raise_for_status()
    if "text/html" not in str(response.headers.get("content-type") or "").lower():
        raise SystemExit(f"PostMinutes source is not HTML: {response.headers.get('content-type')!r}")

    content = response.content
    source = {
        "source_id": "hrm-escribe",
        "meeting_id": meeting.get("meeting_id"),
        "meeting_date": args.meeting_date,
        "meeting_name": meeting.get("meeting_name") or "Halifax Regional Council",
        "minutes_url": response.url,
        "coverage_layer": "modern_escribe_complete_posted_minutes_window",
        "source_sha256": hashlib.sha256(content).hexdigest(),
    }
    lines = html_to_lines(content)
    parsed, diagnostics = decisions.parse_decisions(lines, source)

    expected_ids = {row["decision_id"] for row in expected}
    parsed_ids = {row["decision_id"] for row in parsed}
    result = {
        "meeting_date": args.meeting_date,
        "meeting_id": meeting.get("meeting_id"),
        "source_url": response.url,
        "html_bytes": len(content),
        "synthetic_lines": len(lines),
        "expected_pdf_decisions": len(expected_ids),
        "parsed_html_decisions": len(parsed_ids),
        "missing_from_html": sorted(expected_ids - parsed_ids),
        "new_from_html": sorted(parsed_ids - expected_ids),
        "diagnostics": diagnostics,
        "equivalent_decision_ids": parsed_ids == expected_ids,
        "principle": "HTML fallback is acceptable only if the established checked PDF-derived decision IDs are reproduced exactly.",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if parsed_ids != expected_ids:
        raise SystemExit("PostMinutes HTML did not reproduce the checked PDF-derived decision ID set exactly")


if __name__ == "__main__":
    main()
