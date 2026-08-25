#!/usr/bin/env python3
"""Independently validate Council calendar coverage and document-graph completeness."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNCIL = ROOT / 'data/generated/council.json'
DOCUMENTS = ROOT / 'data/generated/council_documents.json'
COUNCIL_STATUS = 'escribe_calendar_complete_available_window'
COUNCIL_PARSER = 'build005-council-v2'
DOC_STATUS = 'escribe_agenda_attachment_complete_scan'
DOC_PARSER = 'build005-council-documents-v2'
CURRENT_YEAR = datetime.now(timezone.utc).year
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f'Missing Council artifact: {path.relative_to(ROOT)}')
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> None:
    council = load(COUNCIL)
    documents = load(DOCUMENTS)
    cmeta = council.get('metadata') or {}
    dmeta = documents.get('metadata') or {}
    meetings = council.get('records')
    docs = documents.get('records')
    if not isinstance(meetings, list) or not meetings:
        raise SystemExit('council.json records must be a non-empty list')
    if not isinstance(docs, list):
        raise SystemExit('council_documents.json records must be a list')

    if cmeta.get('dataset_status') != COUNCIL_STATUS:
        fail(f"council dataset_status {cmeta.get('dataset_status')!r} != {COUNCIL_STATUS!r}")
    if cmeta.get('parser_version') != COUNCIL_PARSER:
        fail(f"council parser_version {cmeta.get('parser_version')!r} != {COUNCIL_PARSER!r}")
    if cmeta.get('records') != len(meetings):
        fail('council metadata record count mismatch')
    if cmeta.get('complete_through_year') != CURRENT_YEAR:
        fail(f"council complete_through_year {cmeta.get('complete_through_year')!r} != current year {CURRENT_YEAR}")
    available_from = cmeta.get('available_from_year')
    if not isinstance(available_from, int) or available_from < cmeta.get('requested_calendar_year_start', 0) or available_from > CURRENT_YEAR:
        fail(f'council invalid available_from_year {available_from!r}')

    year_stats = cmeta.get('year_stats')
    if not isinstance(year_stats, list):
        fail('council year_stats must be a list')
        year_stats = []
    year_ids = [item.get('calendar_year') for item in year_stats]
    start = cmeta.get('requested_calendar_year_start')
    end = cmeta.get('requested_calendar_year_end')
    if isinstance(start, int) and isinstance(end, int):
        if year_ids != list(range(start, end + 1)):
            fail('council year_stats do not exactly cover requested calendar-year window')
    by_year = {item.get('calendar_year'): item for item in year_stats}
    for year in range(available_from or CURRENT_YEAR, CURRENT_YEAR + 1):
        item = by_year.get(year) or {}
        returned = item.get('returned')
        normalized = item.get('normalized')
        if not isinstance(returned, int) or returned < 1:
            fail(f'council year {year}: coverage is empty after archive availability begins')
        if normalized != returned:
            fail(f'council year {year}: normalized {normalized!r} != returned {returned!r}')
    gaps = cmeta.get('coverage_gaps_after_availability')
    if gaps != []:
        fail(f'council coverage_gaps_after_availability must be empty, got {gaps!r}')

    meeting_by_id: dict[str, dict] = {}
    meeting_counts: Counter[int] = Counter()
    agenda_count = 0
    minutes_count = 0
    for index, row in enumerate(meetings):
        meeting_id = str(row.get('meeting_id') or '').strip()
        if not meeting_id:
            fail(f'council row {index}: blank meeting_id')
            continue
        if meeting_id in meeting_by_id:
            fail(f'council row {index}: duplicate meeting_id {meeting_id!r}')
        meeting_by_id[meeting_id] = row
        if row.get('source_id') != 'hrm-escribe' or row.get('validation_status') != 'calendar_record':
            fail(f'council row {index}: source/validation metadata invalid')
        if row.get('locator_value') != meeting_id:
            fail(f'council row {index}: locator_value does not equal meeting_id')
        raw_hash = row.get('raw_hash')
        if not isinstance(raw_hash, str) or len(raw_hash) != 64:
            fail(f'council row {index}: raw_hash missing/invalid')
        start_date = str(row.get('start_date') or '')
        try:
            year = int(start_date[:4])
            meeting_counts[year] += 1
        except Exception:
            fail(f'council row {index}: invalid start_date {start_date!r}')
        if row.get('agenda_html_url') or row.get('agenda_pdf_url'):
            agenda_count += 1
        if row.get('minutes_html_url') or row.get('minutes_pdf_url'):
            minutes_count += 1
    for year in range(available_from or CURRENT_YEAR, CURRENT_YEAR + 1):
        if meeting_counts[year] != (by_year.get(year) or {}).get('normalized'):
            fail(f'council year {year}: record dates do not reconcile to year_stats')
    if cmeta.get('with_agenda') != agenda_count or cmeta.get('with_minutes') != minutes_count:
        fail('council agenda/minutes metadata counts do not match meeting rows')

    if dmeta.get('dataset_status') != DOC_STATUS:
        fail(f"documents dataset_status {dmeta.get('dataset_status')!r} != {DOC_STATUS!r}")
    if dmeta.get('parser_version') != DOC_PARSER:
        fail(f"documents parser_version {dmeta.get('parser_version')!r} != {DOC_PARSER!r}")
    if dmeta.get('council_input_sha256') != sha256_file(COUNCIL):
        fail('documents council_input_sha256 is stale')
    if dmeta.get('meeting_records_scanned') != len(meetings):
        fail('documents meeting_records_scanned does not match council records')
    if dmeta.get('meeting_errors') != 0:
        fail(f"documents meeting_errors must be zero, got {dmeta.get('meeting_errors')!r}")
    if dmeta.get('document_edges') != len(docs):
        fail('documents metadata edge count mismatch')

    statuses = dmeta.get('meeting_status')
    if not isinstance(statuses, list):
        fail('documents meeting_status must be a list')
        statuses = []
    status_ids = [str(item.get('meeting_id') or '') for item in statuses]
    if set(status_ids) != set(meeting_by_id) or len(status_ids) != len(meeting_by_id):
        fail('documents meeting_status must contain each Council meeting exactly once')
    status_by_id = {str(item.get('meeting_id') or ''): item for item in statuses}
    for meeting_id, meeting in meeting_by_id.items():
        status = status_by_id.get(meeting_id) or {}
        if meeting.get('agenda_html_url'):
            if status.get('status') != 'ok' or status.get('http_status') != 200:
                fail(f'documents meeting {meeting_id}: agenda URL was not successfully scanned')
        elif status.get('status') != 'no_agenda_url':
            fail(f'documents meeting {meeting_id}: expected explicit no_agenda_url status')

    seen_edges: set[tuple[str, str]] = set()
    unique_docs: set[str] = set()
    doc_counts: Counter[str] = Counter()
    finance_count = 0
    for index, row in enumerate(docs):
        meeting_id = str(row.get('meeting_id') or '')
        document_id = str(row.get('document_id') or '')
        if meeting_id not in meeting_by_id:
            fail(f'document row {index}: unknown meeting_id {meeting_id!r}')
        if not document_id:
            fail(f'document row {index}: blank document_id')
        edge = (meeting_id, document_id)
        if edge in seen_edges:
            fail(f'document row {index}: duplicate meeting/document edge {edge!r}')
        seen_edges.add(edge)
        unique_docs.add(document_id)
        doc_counts[meeting_id] += 1
        if row.get('source_id') != 'hrm-escribe' or row.get('validation_status') != 'document_link':
            fail(f'document row {index}: source/validation metadata invalid')
        if row.get('locator_value') != f'{meeting_id}:{document_id}':
            fail(f'document row {index}: invalid locator_value')
        if row.get('agenda_url') != (meeting_by_id.get(meeting_id) or {}).get('agenda_html_url'):
            fail(f'document row {index}: agenda_url does not match Council meeting')
        tags = row.get('finance_tags')
        if not isinstance(tags, list):
            fail(f'document row {index}: finance_tags must be a list')
        if bool(tags) != bool(row.get('finance_relevant')):
            fail(f'document row {index}: finance_relevant does not match tags')
        finance_count += bool(row.get('finance_relevant'))
    for meeting_id, count in doc_counts.items():
        if (status_by_id.get(meeting_id) or {}).get('documents') != count:
            fail(f'documents meeting {meeting_id}: status document count mismatch')
    if dmeta.get('unique_documents') != len(unique_docs):
        fail('documents unique_documents metadata mismatch')
    if dmeta.get('finance_tagged_edges') != finance_count:
        fail('documents finance_tagged_edges metadata mismatch')

    if errors:
        print('COUNCIL VALIDATION FAILED', file=sys.stderr)
        for message in errors[:100]:
            print(message, file=sys.stderr)
        raise SystemExit(1)

    print(
        f'validated Council: {len(meetings)} meetings from {available_from}-{CURRENT_YEAR}; '
        f'{len(docs)} document edges; zero agenda-fetch errors'
    )


if __name__ == '__main__':
    main()
