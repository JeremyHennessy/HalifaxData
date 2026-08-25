#!/usr/bin/env python3
"""Collect eSCRIBE agenda attachments with fail-closed meeting completeness."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
COUNCIL = ROOT / 'data/generated/council.json'
OUT = ROOT / 'data/generated/council_documents.json'
BASE = 'https://pub-halifax.escribemeetings.com/'
UA = 'HalifaxData/0.5 (+https://github.com/JeremyHennessy/HalifaxData)'
SOURCE_ID = 'hrm-escribe'
PARSER_VERSION = 'build005-council-documents-v2'

FINANCE_KEYWORDS = {
    'budget': ('budget', 'business plan'),
    'capital': ('capital', 'project update', 'infrastructure'),
    'procurement': ('award of contract', 'award of contracts', 'procurement', 'tender', 'contract'),
    'financial_reporting': ('financial report', 'financial statement', 'financial position', 'quarterly report'),
    'grants': ('grant', 'funding program'),
    'reserves_debt': ('reserve', 'debt', 'borrowing'),
    'tax_revenue': ('tax', 'revenue', 'assessment', 'write off', 'write-off', 'uncollectible'),
    'investment': ('investment', 'cash management'),
    'compensation': ('compensation', 'salary', 'wage', 'payroll'),
    'audit_oversight': ('audit', 'auditor', 'accountability'),
    'expenditure': ('expenditure', 'expense', 'spending', 'cost'),
}


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'a':
            return
        amap = dict(attrs)
        href = amap.get('href')
        if href:
            self.current = {
                'href': href,
                'text_parts': [],
                'title': amap.get('title'),
                'aria_label': amap.get('aria-label'),
            }

    def handle_data(self, data):
        if self.current is not None:
            self.current['text_parts'].append(data)

    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self.current is not None:
            self.current['text'] = ' '.join(' '.join(self.current.pop('text_parts')).split())
            self.links.append(self.current)
            self.current = None


def document_id(url):
    try:
        query = parse_qs(urlparse(url).query)
        for key in ('DocumentId', 'documentId', 'documentid'):
            if query.get(key):
                return str(query[key][0])
    except Exception:
        pass
    match = re.search(r'DocumentId=([^&]+)', url or '', re.I)
    return match.group(1) if match else None


def classify(title):
    low = (title or '').lower()
    return [tag for tag, tokens in FINANCE_KEYWORDS.items() if any(token in low for token in tokens)]


def sha256_text(text):
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


def main():
    if not COUNCIL.exists():
        raise RuntimeError('council.json is missing; refusing to build a detached document graph')
    council_sha = sha256_file(COUNCIL)
    council = json.loads(COUNCIL.read_text(encoding='utf-8'))
    meetings = council.get('records')
    if not isinstance(meetings, list) or not meetings:
        raise RuntimeError('council.json has no meeting records')
    meeting_ids = [str(row.get('meeting_id') or '').strip() for row in meetings]
    if any(not meeting_id for meeting_id in meeting_ids) or len(meeting_ids) != len(set(meeting_ids)):
        raise RuntimeError('council.json meeting IDs are blank or non-unique')

    session = requests.Session()
    session.headers['User-Agent'] = UA
    retrieved_at = now()
    records: list[dict] = []
    meeting_status: list[dict] = []
    failures: list[str] = []
    global_edges: set[tuple[str, str]] = set()

    for meeting in meetings:
        meeting_id = str(meeting['meeting_id'])
        agenda_url = meeting.get('agenda_html_url')
        if not agenda_url:
            meeting_status.append({'meeting_id': meeting_id, 'status': 'no_agenda_url', 'documents': 0})
            continue
        try:
            response = session.get(agenda_url, timeout=60)
            response.raise_for_status()
            parser = AnchorParser()
            parser.feed(response.text)
            seen: set[str] = set()
            count = 0
            for link in parser.links:
                href = link.get('href') or ''
                if 'filestream.ashx' not in href.lower() or 'documentid=' not in href.lower():
                    continue
                url = urljoin(BASE, href)
                did = document_id(url)
                if not did or did in seen:
                    continue
                seen.add(did)
                edge = (meeting_id, did)
                if edge in global_edges:
                    raise RuntimeError(f'duplicate meeting/document edge {edge!r}')
                global_edges.add(edge)
                title = link.get('text') or link.get('title') or link.get('aria_label') or f'eSCRIBE document {did}'
                tags = classify(title)
                records.append({
                    'document_id': did,
                    'meeting_id': meeting_id,
                    'meeting_name': meeting.get('meeting_name'),
                    'meeting_type': meeting.get('meeting_type'),
                    'meeting_start_date': meeting.get('start_date'),
                    'title': title,
                    'url': url,
                    'agenda_url': agenda_url,
                    'finance_tags': tags,
                    'finance_relevant': bool(tags),
                    'source_id': SOURCE_ID,
                    'retrieved_at': retrieved_at,
                    'locator_type': 'escribe_agenda_attachment',
                    'locator_value': f'{meeting_id}:{did}',
                    'agenda_html_hash': sha256_text(response.text),
                    'validation_status': 'document_link',
                })
                count += 1
            meeting_status.append({
                'meeting_id': meeting_id,
                'status': 'ok',
                'documents': count,
                'http_status': response.status_code,
            })
            print(f"{meeting.get('start_date')} {meeting.get('meeting_type')}: {count} attachment links")
        except Exception as exc:
            failures.append(f'{meeting_id}: {type(exc).__name__}: {exc}')
            meeting_status.append({
                'meeting_id': meeting_id,
                'status': 'error',
                'documents': 0,
                'error': f'{type(exc).__name__}: {exc}',
            })

    if failures:
        raise RuntimeError('Council document refresh failed closed: ' + ' | '.join(failures))
    if len(meeting_status) != len(meetings):
        raise RuntimeError(f'meeting status count {len(meeting_status)} != meetings {len(meetings)}')
    if {row['meeting_id'] for row in meeting_status} != set(meeting_ids):
        raise RuntimeError('meeting status IDs do not exactly match council.json')

    records.sort(key=lambda row: (
        str(row.get('meeting_start_date') or ''),
        str(row.get('meeting_id') or ''),
        int(row['document_id']) if str(row['document_id']).isdigit() else str(row['document_id']),
    ))
    unique_documents = len({row['document_id'] for row in records})
    finance_records = sum(bool(row.get('finance_relevant')) for row in records)
    if len(records) < 100:
        raise RuntimeError(f'Only {len(records)} agenda attachment edges collected; refusing to replace document graph')

    payload = {
        'metadata': {
            'dataset_status': 'escribe_agenda_attachment_complete_scan',
            'parser_version': PARSER_VERSION,
            'generated_at': retrieved_at,
            'source_id': SOURCE_ID,
            'council_input_sha256': council_sha,
            'meeting_records_scanned': len(meetings),
            'meetings_with_agenda_url': sum(bool(row.get('agenda_html_url')) for row in meetings),
            'meetings_without_agenda_url': sum(not bool(row.get('agenda_html_url')) for row in meetings),
            'document_edges': len(records),
            'unique_documents': unique_documents,
            'finance_tagged_edges': finance_records,
            'meeting_errors': 0,
            'meeting_status': meeting_status,
            'note': (
                'Every council meeting is accounted for. Meetings with agenda HTML are fetched successfully or the '
                'refresh fails; meetings without an agenda URL remain explicit no_agenda_url coverage states. '
                'Finance tags are title-keyword search aids only, not findings or approvals.'
            ),
        },
        'records': records,
    }
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(OUT)
    print(f'Wrote {len(records)} meeting-document edges / {unique_documents} unique documents; meeting_errors=0')


if __name__ == '__main__':
    main()
