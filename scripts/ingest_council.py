#!/usr/bin/env python3
"""Collect Halifax eSCRIBE meeting-calendar records into normalized Council facts.

The calendar API returns all published meeting types for a requested time window.
This collector keeps the meeting/document provenance and does not infer decisions
from calendar presence alone. Agenda/minutes item-level parsing is a later layer.
"""
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
UA = 'HalifaxData/0.3 (+https://github.com/JeremyHennessy/HalifaxData)'

# Start at 2016 to align with the compensation history and provide a useful
# governance history immediately. Extend one year beyond the current year to
# preserve scheduled future meetings already published by eSCRIBE.
START_YEAR = 2016
CURRENT_YEAR = datetime.now(timezone.utc).year
END_YEAR = CURRENT_YEAR + 1


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def absolute(url):
    if not url:
        return None
    return urljoin(BASE, url)


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


def first_document(documents, *types):
    wanted = {value.lower() for value in types}
    for doc in documents:
        if str(doc.get('type') or '').lower() in wanted:
            return doc.get('url')
    return None


def raw_hash(item):
    blob = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')
    return hashlib.sha256(blob).hexdigest()


def parse_year_window(session, year):
    # eSCRIBE accepts ISO-like offsets and returns JSON in body['d'].
    start = f'{year}-01-01T00:00:00-04:00'
    end = f'{year + 1}-01-01T00:00:00-04:00'
    payload = {'calendarStartDate': start, 'calendarEndDate': end}
    response = session.post(
        ENDPOINT,
        json=payload,
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
    record = {
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
    return record


def main():
    session = requests.Session()
    session.headers['User-Agent'] = UA
    landing = session.get(LANDING, timeout=60)
    landing.raise_for_status()

    retrieved_at = now()
    by_id = {}
    year_stats = []
    for year in range(START_YEAR, END_YEAR + 1):
        items = parse_year_window(session, year)
        kept = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            record = normalize_meeting(item, retrieved_at)
            if not record['meeting_id']:
                continue
            by_id[record['meeting_id']] = record
            kept += 1
        year_stats.append({'calendar_year': year, 'returned': len(items), 'normalized': kept})
        print(f'eSCRIBE {year}: returned={len(items)} normalized={kept}')

    records = sorted(by_id.values(), key=lambda row: (str(row.get('start_date') or ''), str(row.get('meeting_type') or ''), str(row.get('meeting_id') or '')))
    if len(records) < 50:
        raise RuntimeError(f'Only {len(records)} unique eSCRIBE meetings collected; refusing to replace Council artifact')

    meeting_types = {}
    with_agenda = 0
    with_minutes = 0
    for row in records:
        meeting_types[row.get('meeting_type') or 'Unknown'] = meeting_types.get(row.get('meeting_type') or 'Unknown', 0) + 1
        if row.get('agenda_html_url') or row.get('agenda_pdf_url'):
            with_agenda += 1
        if row.get('minutes_html_url') or row.get('minutes_pdf_url'):
            with_minutes += 1

    payload = {
        'metadata': {
            'dataset_status': 'escribe_calendar_collection',
            'generated_at': retrieved_at,
            'source_id': SOURCE_ID,
            'calendar_year_start': START_YEAR,
            'calendar_year_end': END_YEAR,
            'records': len(records),
            'with_agenda': with_agenda,
            'with_minutes': with_minutes,
            'meeting_types': dict(sorted(meeting_types.items())),
            'year_stats': year_stats,
            'note': 'Calendar/document facts only. A meeting or agenda is not itself evidence that a recommendation was approved; agenda/minutes item parsing and decision linkage are separate layers.',
        },
        'records': records,
    }
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(OUT)
    print(f'Wrote {len(records)} unique Council/committee meetings to {OUT}')


if __name__ == '__main__':
    main()
