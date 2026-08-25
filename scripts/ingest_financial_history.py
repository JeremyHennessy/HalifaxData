#!/usr/bin/env python3
"""Extract conservative audited HRM comparative financial-statement rows.

The source PDFs contain many non-financial numbers (dates, page ranges, phone
numbers and narrative note references). Only pages that explicitly identify a
consolidated statement or consolidated schedule are eligible. Candidate rows
must also carry financial-number formatting or a detected thousands-of-dollars
unit before they can become facts.
"""
from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests

from ingest_domains import clean, money, fetch_pdf, provenance

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'data/sources.json'
OUT = ROOT / 'data/generated'
UA = 'HalifaxData/0.5 (+https://github.com/JeremyHennessy/HalifaxData)'
PARSER_VERSION = 'build005-financials-v3'

VALUE_RE = re.compile(r'\(?\$?\s*\d[\d,]*(?:\.\d+)?\)?')
STATEMENT_PATTERNS = [
    ('financial_position', re.compile(r'\bconsolidated statement of financial position\b', re.I)),
    ('operations', re.compile(r'\bconsolidated statement of operations(?: and accumulated surplus)?\b', re.I)),
    ('net_financial_assets', re.compile(r'\bconsolidated statement of change(?:s)? in net financial assets(?: \(debt\))?\b', re.I)),
    ('cash_flows', re.compile(r'\bconsolidated statement of cash flows\b', re.I)),
    ('schedule', re.compile(r'\bconsolidated schedules? of\b', re.I)),
]
REJECT_LABEL_PATTERNS = [
    re.compile(r'^page\s+\d+', re.I),
    re.compile(r'^notes? to consolidated financial statements$', re.I),
    re.compile(r'^year ended march\b', re.I),
    re.compile(r'\btelephone\s*\(?\d{3}\)?', re.I),
    re.compile(r'\bfax\s*\(?\d{3}\)?', re.I),
    re.compile(r'^halifax nova scotia\s+[A-Z]\d[A-Z]', re.I),
]


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def year_from(src):
    match = re.search(r'(20\d{2})', src['id'])
    return int(match.group(1)) if match else None


def unit_multiplier(text):
    low = (text or '').lower()
    if any(token in low for token in ['in thousands of dollars', 'in thousands', '$000', '$ 000', "000's"]):
        return 1000
    return 1


def statement_context(text):
    """Return an explicit audited statement/schedule heading or None."""
    lines = [clean(line) for line in (text or '').splitlines() if clean(line)]
    for line in lines:
        for family, pattern in STATEMENT_PATTERNS:
            match = pattern.search(line)
            if match:
                # Auditor narrative can mention the statements. Keep the page
                # eligible, but downstream row formatting still has to prove a
                # monetary comparative row before anything is emitted.
                return family, line[:220]
    return None, None


def has_financial_format(raw_value, multiplier):
    text = clean(raw_value)
    if multiplier == 1000:
        return True
    return any(marker in text for marker in ('$', ',', '(', ')'))


def valid_label(label):
    text = clean(label)
    if len(text) < 3 or not re.search(r'[A-Za-z]', text):
        return False
    return not any(pattern.search(text) for pattern in REJECT_LABEL_PATTERNS)


def normalized_record(src, fiscal_year, page_num, statement_family, statement_title, label, current_raw, prior_raw, multiplier, raw_cells, method, locator):
    return {
        'fiscal_year_end': fiscal_year,
        'statement_family': statement_family,
        'statement': statement_title,
        'line_item': clean(label),
        'current_year': round(current_raw * multiplier, 2),
        'prior_year': round(prior_raw * multiplier, 2),
        'source_presented_current_year': current_raw,
        'source_presented_prior_year': prior_raw,
        'source_unit_multiplier': multiplier,
        'currency': 'CAD',
        'source_id': src['id'],
        'source_page': page_num,
        'raw_cells': raw_cells,
        'extraction_method': method,
        'provenance': provenance(src['id'], src['url'], method, locator, PARSER_VERSION),
    }


def parse_table_rows(src, fiscal_year, page_num, statement_family, statement_title, tables, multiplier):
    records = []
    index_rows = []
    for table_num, table in enumerate(tables or [], 1):
        normalized = [[clean(c) for c in (row or [])] for row in (table or [])]
        if not normalized:
            continue
        index_rows.append({
            'source_id': src['id'], 'fiscal_year_end': fiscal_year, 'page': page_num,
            'table': table_num, 'statement_family': statement_family,
            'context': statement_title, 'rows': len(normalized), 'header': normalized[:3],
        })
        for row_num, row in enumerate(normalized):
            numeric_positions = [(idx, money(cell), cell) for idx, cell in enumerate(row) if money(cell) is not None]
            if len(numeric_positions) < 2:
                continue
            current_idx, current_raw, current_cell = numeric_positions[-2]
            _, prior_raw, prior_cell = numeric_positions[-1]
            if not (has_financial_format(current_cell, multiplier) or has_financial_format(prior_cell, multiplier)):
                continue
            label_candidates = [cell for cell in row[:current_idx] if cell and re.search(r'[A-Za-z]', cell)]
            label = label_candidates[0] if label_candidates else ''
            if not valid_label(label):
                continue
            records.append(normalized_record(
                src, fiscal_year, page_num, statement_family, statement_title, label,
                current_raw, prior_raw, multiplier, row, 'pdf_table_row',
                f'p{page_num}/t{table_num}/r{row_num}',
            ))
    return records, index_rows


def parse_text_rows(src, fiscal_year, page_num, statement_family, statement_title, text, multiplier):
    records = []
    for line_num, raw_line in enumerate((text or '').splitlines(), 1):
        line = clean(raw_line)
        if not line or not re.search(r'[A-Za-z]', line):
            continue
        matches = list(VALUE_RE.finditer(line))
        if len(matches) < 2:
            continue
        current_match, prior_match = matches[-2], matches[-1]
        if not (
            has_financial_format(current_match.group(), multiplier)
            or has_financial_format(prior_match.group(), multiplier)
        ):
            continue
        label = clean(line[:current_match.start()])
        if not valid_label(label):
            continue
        current_raw = money(current_match.group())
        prior_raw = money(prior_match.group())
        if current_raw is None or prior_raw is None:
            continue
        records.append(normalized_record(
            src, fiscal_year, page_num, statement_family, statement_title, label,
            current_raw, prior_raw, multiplier, [line], 'pdf_text_line',
            f'p{page_num}/line{line_num}',
        ))
    return records


def main():
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    sources = [
        source for source in registry['sources']
        if source['id'].startswith('hrm-financials-') and str(source.get('status', '')).startswith('ready')
    ]
    session = requests.Session()
    session.headers['User-Agent'] = UA
    records = []
    tables = []
    source_status = []

    for src in sources:
        fiscal_year = year_from(src)
        try:
            blob = fetch_pdf(session, src)
            source_records = []
            source_tables = []
            eligible_pages = 0
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text(layout=True) or page.extract_text() or ''
                    statement_family, statement_title = statement_context(text)
                    if not statement_family:
                        continue
                    eligible_pages += 1
                    multiplier = unit_multiplier(text)
                    table_records, table_index = parse_table_rows(
                        src, fiscal_year, page_num, statement_family, statement_title,
                        page.extract_tables() or [], multiplier,
                    )
                    source_tables.extend(table_index)
                    text_records = parse_text_rows(
                        src, fiscal_year, page_num, statement_family, statement_title,
                        text, multiplier,
                    )
                    source_records.extend(table_records)
                    source_records.extend(text_records)

            priority = {'pdf_table_row': 0, 'pdf_text_line': 1}
            source_records.sort(key=lambda row: priority.get(row['extraction_method'], 9))
            unique = {}
            for row in source_records:
                key = (
                    row['source_id'], row['source_page'], row['statement_family'],
                    re.sub(r'\s+', ' ', row['line_item']).strip().lower(),
                    row['current_year'], row['prior_year'],
                )
                unique.setdefault(key, row)
            source_records = list(unique.values())

            if len(source_records) < 10:
                source_status.append({
                    'source_id': src['id'], 'status': 'parse_gap', 'records': len(source_records),
                    'eligible_statement_pages': eligible_pages,
                    'note': 'Source downloaded but fewer than 10 conservative comparative financial rows were normalized.',
                })
            else:
                source_status.append({
                    'source_id': src['id'], 'status': 'ok', 'records': len(source_records),
                    'eligible_statement_pages': eligible_pages,
                })
            records.extend(source_records)
            tables.extend(source_tables)
        except Exception as exc:
            source_status.append({'source_id': src['id'], 'status': 'error', 'error': f'{type(exc).__name__}: {exc}'})

    records.sort(key=lambda row: (
        row.get('fiscal_year_end') or 0,
        row.get('source_page') or 0,
        row.get('statement_family') or '',
        row.get('line_item') or '',
    ))
    payload = {
        'metadata': {
            'generated_at': now(),
            'dataset_status': 'conservative_audited_statement_extraction',
            'parser_version': PARSER_VERSION,
            'records': len(records),
            'source_count': len(sources),
            'source_status': source_status,
            'scope': 'Explicit consolidated statement/schedule pages only; narrative notes are not normalized by this collector.',
            'note': 'Source-presented comparative values, detected unit scale, source page and extraction method are retained. Normalized current_year/prior_year values are CAD after applying source_unit_multiplier.',
        },
        'records': records,
    }
    index = {
        'metadata': {
            'generated_at': now(),
            'parser_version': PARSER_VERSION,
            'tables': len(tables),
            'source_count': len(sources),
            'scope': 'Tables found only on pages with an explicit consolidated statement/schedule heading.',
        },
        'records': tables,
    }
    (OUT / 'financials.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (OUT / 'financials_document_tables.json').write_text(json.dumps(index, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'financial history: {len(records)} conservative rows from {len(sources)} audited sources')
    print(json.dumps(source_status, indent=2))
    if not records:
        raise RuntimeError('No conservative audited financial rows parsed from configured sources')
    if any(item.get('status') != 'ok' for item in source_status):
        raise RuntimeError(f'One or more audited financial sources failed conservative extraction: {source_status!r}')


if __name__ == '__main__':
    main()
