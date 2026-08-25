#!/usr/bin/env python3
"""Collect Halifax eSCRIBE meetings with explicit source-coverage completeness."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/generated/council.json'
BASE = 'https://pub-halifax.escribemeetings.com/'
LANDING = urljoin(BASE, 'MeetingsCalendarView.aspx')
ENDPOINT = urljoin(BASE, 'MeetingsCalendarView.aspx/GetCalendarMeetings')
SOURCE_ID = 'hrm-escribe'
UA = 'HalifaxData/0.5 (+https://github.com/JeremyHennessy/HalifaxData)'
PARSER_VERSION = 'build005-council-v2'
START_YEAR = 2016
CURRENT_YEAR = datetime.now(timezone.utc).year
END_YEAR = CURRENT_YEAR + 1


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def absolute(url):
    return urljoin(BASE, url) if url else None


def document_id(url):
    if not url:
        return None
    match = re.search(r'(?:DocumentId=|[?&]Id=)([^&]+)', url, re.I)
    return match.group(1) if match else None


def normalize_document(doc):
    return {
        'type': doc.get('Type'),
        'title': doc.get('Title'),
        'format': doc.get('Format'),
        'url': absolute(doc.get('Url')),
        'document_id': document_id(doc.get('Url')),
        'language_id': doc.get('LanguageId'),
        'aria_label': doc.get('AriaLabel'),
        'sequence': doc.get('Sequence'),
    }


def raw_hash(item):
    blob = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')
    return hashlib.sha256(blob).hexdigest()


def parse_year_window(session, year):
    start = f'{year}-01-01T00:00:00-04:00'
    end = f'{year + 1}-01-01T00:00:00-04:00'
    response = session.post(
        ENDPOINT,
        json={'calendarStartDate': start, 'calendarEndDate': end},
        timeout=90,
        headers={'Referer': LANDING, 'X-Requested-With': 'XMLHttpRequest'},
    )
    response.raise_for_status()
    body = response.json()
    items = body.get('d', []) if isinstance(body, dict) else []
    if isinstance(items, str):
        items = json.loads(items)
    if not isinstance(items, list):
        raise RuntimeError(f'{year}: expected list in eSCRIBE d payload, got {type(items).__name__}')
    return items


def normalize_meeting(item, retrieved_at):
    documents = [normalize_document(doc) for doc in (item.get('MeetingDocumentLink') or []) if isinstance(doc, dict)]
    agenda_html = next((doc['url'] for doc in documents if doc.get('type') == 'Agenda' and str(doc.get('format')).upper() == 'HTML'), None)
    agenda_pdf = next((doc['url'] for doc in documents if doc.get('type') in {'Agenda', 'AgendaCover'} and str(doc.get('format')).lower() == '.pdf'), None)
    minutes_html = next((doc['url'] for doc in documents if doc.get('type') == 'PostMinutes' and str(doc.get('format')).upper() == 'HTML'), None)
    minutes_pdf = next((doc['url'] for doc in documents if doc.get('type') == 'PostMinutes' and str(doc.get('format')).lower() == '.pdf'), None)
    meeting_id = item.get('ID') or item.get('Id') or item.get('id')
    return {
        'meeting_id': meeting_id,
        'meeting_name': item.get('MeetingName'),
        'meeting_type': item.get('MeetingType'),
        'start_date': item.get('StartDate'),
        'formatted_start': item.get('FormattedStart'),
        'end_date': item.get('EndDate'),
        'location': item.get('Location'),
        'description': item.get('Description'),
        'has_agenda': bool(item.get('HasAgenda')),
        'has_video': bool(item.get('HasVideo')),
        'has_live_video': bool(item.get('HasLiveVideo')),
        'meeting_passed': bool(item.get('MeetingPassed')),
        'meeting_url': absolute(item.get('Url')) or (urljoin(BASE, f'Meeting.aspx?Id={meeting_id}') if meeting_id else None),
        'agenda_html_url': agenda_html,
        'agenda_pdf_url': agenda_pdf,
        'minutes_html_url': minutes_html,
        'minutes_pdf_url': minutes_pdf,
        'documents': documents,
        'source_id': SOURCE_ID,
        'source_url': ENDPOINT,
        'retrieved_at': retrieved_at,
        'locator_type': 'escribe_calendar_meeting',
        'locator_value': meeting_id,
        'raw_hash': raw_hash(item),
        'validation_status': 'calendar_record',
    }


def main():
    session = requests.Session()
    session.headers['User-Agent'] = UA
    landing = session.get(LANDING, timeout=60)
    landing.raise_for_status()

    retrieved_at = now()
    by_id: dict[str, dict] = {}
    meeting_year: dict[str, int] = {}
    year_stats: list[dict] = []

    for year in range(START_YEAR, END_YEAR + 1):
        items = parse_year_window(session, year)
        invalid = 0
        normalized = 0
        for item_index, item in enumerate(items):
            if not isinstance(item, dict):
                invalid += 1
                continue
            record = normalize_meeting(item, retrieved_at)
            meeting_id = str(record.get('meeting_id') or '').strip()
            if not meeting_id:
                invalid += 1
                continue
            if meeting_id in by_id:
                raise RuntimeError(
                    f'duplicate eSCRIBE meeting_id {meeting_id!r} returned in years '
                    f'{meeting_year[meeting_id]} and {year}'
                )
            by_id[meeting_id] = record
            meeting_year[meeting_id] = year
            normalized += 1
        if invalid:
            raise RuntimeError(f'{year}: {invalid}/{len(items)} eSCRIBE items were non-object or missing meeting IDs')
        if normalized != len(items):
            raise RuntimeError(f'{year}: normalized {normalized} rows from {len(items)} returned items')
        year_stats.append({'calendar_year': year, 'returned': len(items), 'normalized': normalized})
        print(f'eSCRIBE {year}: returned={len(items)} normalized={normalized}')

    present_years = [item['calendar_year'] for item in year_stats if item['calendar_year'] <= CURRENT_YEAR and item['returned'] > 0]
    if not present_years:
        raise RuntimeError('eSCRIBE returned no meetings in any requested year through the current year')
    available_from_year = min(present_years)
    by_year = {item['calendar_year']: item for item in year_stats}
    coverage_gaps = [year for year in range(available_from_year, CURRENT_YEAR + 1) if by_year[year]['returned'] == 0]
    if coverage_gaps:
        raise RuntimeError(f'eSCRIBE coverage has unexplained empty years after archive availability begins: {coverage_gaps}')
    if by_year[CURRENT_YEAR]['returned'] == 0:
        raise RuntimeError(f'eSCRIBE returned zero records for current calendar year {CURRENT_YEAR}')

    records = sorted(by_id.values(), key=lambda row: (
        str(row.get('start_date') or ''), str(row.get('meeting_type') or ''), str(row.get('meeting_id') or '')
    ))
    if len(records) < 50:
        raise RuntimeError(f'Only {len(records)} unique eSCRIBE meetings collected; refusing to replace Council artifact')

    meeting_types: dict[str, int] = {}
    with_agenda = 0
    with_minutes = 0
    for row in records:
        meeting_type = row.get('meeting_type') or 'Unknown'
        meeting_types[meeting_type] = meeting_types.get(meeting_type, 0) + 1
        if row.get('agenda_html_url') or row.get('agenda_pdf_url'):
            with_agenda += 1
        if row.get('minutes_html_url') or row.get('minutes_pdf_url'):
            with_minutes += 1

    payload = {
        'metadata': {
            'dataset_status': 'escribe_calendar_complete_available_window',
            'parser_version': PARSER_VERSION,
            'generated_at': retrieved_at,
            'source_id': SOURCE_ID,
            'requested_calendar_year_start': START_YEAR,
            'requested_calendar_year_end': END_YEAR,
            'available_from_year': available_from_year,
            'complete_through_year': CURRENT_YEAR,
            'pre_availability_empty_years': [
                year for year in range(START_YEAR, available_from_year) if by_year[year]['returned'] == 0
            ],
            'coverage_gaps_after_availability': coverage_gaps,
            'records': len(records),
            'with_agenda': with_agenda,
            'with_minutes': with_minutes,
            'meeting_types': dict(sorted(meeting_types.items())),
            'year_stats': year_stats,
            'note': (
                'Calendar/document facts only. Empty years before available_from_year are explicit endpoint coverage limits. '
                'Any empty year after availability begins through the current year fails publication. A meeting or agenda '
                'is not itself evidence that a recommendation was approved.'
            ),
        },
        'records': records,
    }
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(OUT)
    print(f'Wrote {len(records)} unique Council/committee meetings; archive available from {available_from_year}')


if __name__ == '__main__':
    main()
