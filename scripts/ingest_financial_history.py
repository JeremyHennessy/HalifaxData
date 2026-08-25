#!/usr/bin/env python3
"""Extract audited HRM financial-statement rows across registered years.

Audited statements are visually tabular but do not always expose reliable PDF
cell boundaries. The collector therefore uses table extraction when it yields
usable rows and a conservative text-line fallback otherwise. Source-presented
values and the detected unit multiplier are retained so normalized CAD values
remain auditable.
"""
from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests

from ingest_domains import clean, money, fetch_pdf, infer_page_context, provenance

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'data/sources.json'
OUT = ROOT / 'data/generated'
UA = 'HalifaxData/0.3 (+https://github.com/JeremyHennessy/HalifaxData)'

# Source statements commonly use values such as 562,328, $ 1,410,626 or
# (12,345). We only use the final two numeric tokens on a labelled line as the
# current/prior comparative columns.
VALUE_RE = re.compile(r'\(?\$?\s*\d[\d,]*(?:\.\d+)?\)?')


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


def normalized_record(src, fiscal_year, page_num, context, label, current_raw, prior_raw, multiplier, raw_cells, method, locator):
    return {
        'fiscal_year_end': fiscal_year,
        'statement': context or None,
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
        'provenance': provenance(src['id'], src['url'], method, locator, 'build003-financials-v2'),
    }


def parse_table_rows(src, fiscal_year, page_num, context, tables, multiplier):
    records = []
    index_rows = []
    for table_num, table in enumerate(tables or [], 1):
        normalized = [[clean(c) for c in (row or [])] for row in (table or [])]
        if not normalized:
            continue
        index_rows.append({
            'source_id': src['id'], 'fiscal_year_end': fiscal_year, 'page': page_num,
            'table': table_num, 'context': context, 'rows': len(normalized), 'header': normalized[:3],
        })
        for row_num, row in enumerate(normalized):
            numeric_positions = [(idx, money(cell)) for idx, cell in enumerate(row) if money(cell) is not None]
            if len(numeric_positions) < 2:
                continue
            current_raw = numeric_positions[-2][1]
            prior_raw = numeric_positions[-1][1]
            first_numeric_index = numeric_positions[-2][0]
            label_candidates = [cell for cell in row[:first_numeric_index] if cell and re.search(r'[A-Za-z]', cell)]
            label = label_candidates[0] if label_candidates else ''
            if len(label) < 3:
                continue
            records.append(normalized_record(
                src, fiscal_year, page_num, context, label, current_raw, prior_raw,
                multiplier, row, 'pdf_table_row', f'p{page_num}/t{table_num}/r{row_num}',
            ))
    return records, index_rows


def parse_text_rows(src, fiscal_year, page_num, context, text, multiplier):
    records = []
    for line_num, raw_line in enumerate((text or '').splitlines(), 1):
        line = clean(raw_line)
        if not line or not re.search(r'[A-Za-z]', line):
            continue
        matches = list(VALUE_RE.finditer(line))
        if len(matches) < 2:
            continue
        # Comparative statements put the current/prior values at the end. Any
        # note number before those values remains in the label/raw line and is
        # not interpreted as money.
        current_match, prior_match = matches[-2], matches[-1]
        label = clean(line[:current_match.start()])
        if len(label) < 3 or not re.search(r'[A-Za-z]', label):
            continue
        low = label.lower()
        if low.startswith(('page ', 'note ')) or low in {'2025', '2024', '2023', '2022'}:
            continue
        current_raw = money(current_match.group())
        prior_raw = money(prior_match.group())
        if current_raw is None or prior_raw is None:
            continue
        records.append(normalized_record(
            src, fiscal_year, page_num, context, label, current_raw, prior_raw,
            multiplier, [line], 'pdf_text_line', f'p{page_num}/line{line_num}',
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
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text(layout=True) or page.extract_text() or ''
                    context = infer_page_context(text)
                    multiplier = unit_multiplier(text)
                    table_records, table_index = parse_table_rows(
                        src, fiscal_year, page_num, context, page.extract_tables() or [], multiplier
                    )
                    source_tables.extend(table_index)
                    # Text extraction is intentionally run as well because some
                    # statement pages expose partial/merged table geometry.
                    text_records = parse_text_rows(src, fiscal_year, page_num, context, text, multiplier)
                    source_records.extend(table_records)
                    source_records.extend(text_records)

            # Deduplicate exact comparative facts emitted by both paths while
            # preferring table extraction when both produce the same fact.
            priority = {'pdf_table_row': 0, 'pdf_text_line': 1}
            source_records.sort(key=lambda row: priority.get(row['extraction_method'], 9))
            unique = {}
            for row in source_records:
                key = (
                    row['source_id'], row['source_page'], re.sub(r'\s+', ' ', row['line_item']).strip().lower(),
                    row['current_year'], row['prior_year'],
                )
                unique.setdefault(key, row)
            source_records = list(unique.values())

            if len(source_records) < 10:
                source_status.append({
                    'source_id': src['id'], 'status': 'parse_gap', 'records': len(source_records),
                    'note': 'Source downloaded but fewer than 10 comparative financial rows were normalized.',
                })
            else:
                source_status.append({'source_id': src['id'], 'status': 'ok', 'records': len(source_records)})
            records.extend(source_records)
            tables.extend(source_tables)
        except Exception as exc:
            source_status.append({'source_id': src['id'], 'status': 'error', 'error': f'{type(exc).__name__}: {exc}'})

    records.sort(key=lambda row: (row.get('fiscal_year_end') or 0, row.get('source_page') or 0, row.get('line_item') or ''))
    payload = {
        'metadata': {
            'generated_at': now(),
            'records': len(records),
            'source_count': len(sources),
            'source_status': source_status,
            'note': 'Audited financial-statement comparative rows retain raw source values, detected unit scale, source page and extraction method. Normalized current_year/prior_year values are CAD after applying source_unit_multiplier.',
        },
        'records': records,
    }
    index = {
        'metadata': {'generated_at': now(), 'tables': len(tables), 'source_count': len(sources)},
        'records': tables,
    }
    (OUT / 'financials.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (OUT / 'financials_document_tables.json').write_text(json.dumps(index, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'financial history: {len(records)} rows from {len(sources)} audited sources')
    print(json.dumps(source_status, indent=2))
    if not records:
        raise RuntimeError('No audited financial rows parsed from configured sources')


if __name__ == '__main__':
    main()
