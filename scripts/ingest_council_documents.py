#!/usr/bin/env python3
"""Collect item-level eSCRIBE agenda attachment links for published HRM meetings.

This is a document-discovery layer, not a decision parser. It records the exact
meeting, attachment title, eSCRIBE DocumentId and direct URL. Keyword tags are
search aids only and do not imply that a document contains a finding or approved
expenditure.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests

ROOT = Path(__file__).resolve().parents[1]
COUNCIL = ROOT / 'data/generated/council.json'
OUT = ROOT / 'data/generated/council_documents.json'
BASE = 'https://pub-halifax.escribemeetings.com/'
UA = 'HalifaxData/0.3 (+https://github.com/JeremyHennessy/HalifaxData)'
SOURCE_ID = 'hrm-escribe'

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
            self.current = {'href': href, 'text_parts': [], 'title': amap.get('title'), 'aria_label': amap.get('aria-label')}

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
    tags = []
    for tag, tokens in FINANCE_KEYWORDS.items():
        if any(token in low for token in tokens):
            tags.append(tag)
    return tags


def sha256_text(text):
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


def main():
    council = json.loads(COUNCIL.read_text(encoding='utf-8'))
    meetings = council.get('records', [])
    session = requests.Session()
    session.headers['User-Agent'] = UA
    retrieved_at = now()
    records = []
    meeting_status = []

    for meeting in meetings:
        agenda_url = meeting.get('agenda_html_url')
        if not agenda_url:
            meeting_status.append({'meeting_id': meeting.get('meeting_id'), 'status': 'no_agenda_url', 'documents': 0})
            continue
        try:
            response = session.get(agenda_url, timeout=60)
            response.raise_for_status()
            parser = AnchorParser()
            parser.feed(response.text)
            seen = set()
            count = 0
            for link in parser.links:
                href = link.get('href') or ''
                if 'filestream.ashx' not in href.lower() or 'documentid=' not in href.lower():
                    continue
                url = urljoin(BASE, href)
                did = document_id(url)
                if not did:
                    continue
                title = link.get('text') or link.get('title') or link.get('aria_label') or f'eSCRIBE document {did}'
                key = (meeting.get('meeting_id'), did)
                if key in seen:
                    continue
                seen.add(key)
                tags = classify(title)
                records.append({
                    'document_id': did,
                    'meeting_id': meeting.get('meeting_id'),
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
                    'locator_value': f"{meeting.get('meeting_id')}:{did}",
                    'agenda_html_hash': sha256_text(response.text),
                    'validation_status': 'document_link',
                })
                count += 1
            meeting_status.append({'meeting_id': meeting.get('meeting_id'), 'status': 'ok', 'documents': count, 'http_status': response.status_code})
            print(f"{meeting.get('start_date')} {meeting.get('meeting_type')}: {count} attachment links")
        except Exception as exc:
            meeting_status.append({'meeting_id': meeting.get('meeting_id'), 'status': 'error', 'documents': 0, 'error': f'{type(exc).__name__}: {exc}'})
            print(f"ERROR {meeting.get('meeting_id')}: {type(exc).__name__}: {exc}")

    # A document may be referenced in more than one meeting. Preserve those
    # meeting-document edges, but provide unique-document counts separately.
    records.sort(key=lambda row: (str(row.get('meeting_start_date') or ''), str(row.get('meeting_id') or ''), int(row['document_id']) if str(row['document_id']).isdigit() else str(row['document_id'])))
    unique_documents = len({row['document_id'] for row in records})
    finance_records = sum(bool(row.get('finance_relevant')) for row in records)
    failed_meetings = sum(row.get('status') == 'error' for row in meeting_status)
    if len(records) < 100:
        raise RuntimeError(f'Only {len(records)} agenda attachment edges collected; refusing to replace document graph')

    payload = {
        'metadata': {
            'dataset_status': 'escribe_agenda_attachment_collection',
            'generated_at': retrieved_at,
            'meeting_records_scanned': len(meetings),
            'document_edges': len(records),
            'unique_documents': unique_documents,
            'finance_tagged_edges': finance_records,
            'meeting_errors': failed_meetings,
            'meeting_status': meeting_status,
            'note': 'Agenda attachment links and titles are source facts. finance_tags are deterministic title-keyword search aids only, not findings, approvals or semantic classifications of document contents.',
        },
        'records': records,
    }
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(OUT)
    print(f'Wrote {len(records)} meeting-document edges / {unique_documents} unique documents; finance-tagged={finance_records}; meeting_errors={failed_meetings}')


if __name__ == '__main__':
    main()
