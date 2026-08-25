#!/usr/bin/env python3
"""Extract conservative HRM quarterly expense/expenditure summary rows.

The source PDFs often merge several monetary columns into one extracted cell.
This parser tokenizes those values individually instead of collapsing them into
one enormous number. Records remain summary-table facts, not transactions.
"""
from __future__ import annotations

import io
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests

from ingest_domains import clean, provenance

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'data/sources.json'
OUT = ROOT / 'data/generated/spending.json'
UA = 'HalifaxData/0.5 (+https://github.com/JeremyHennessy/HalifaxData)'
PARSER_VERSION = 'build005-spending-v2'
MAX_ABS_VALUE = 10_000_000_000
PERIOD_END = {
    'hrm-q2-2024-25': '2024-09-30',
    'hrm-q3-2024-25': '2024-12-31',
    'hrm-q1-2023-24': '2023-06-30',
    'hrm-q2-2023-24': '2023-09-30',
    'hrm-q3-2023-24': '2023-12-31',
}
KEYWORDS = (
    'expense', 'expenditure', 'district capital', 'district activity',
    'hospitality', 'area rate', 'operating results', 'capital projection', 'reserve',
)
MONEY_TOKEN_RE = re.compile(
    r'(?<![\w.])(?:'
    r'\(\s*\$?\s*\d[\d,]*(?:\.\d+)?\s*\)'
    r'|-?\s*\$?\s*\d[\d,]*(?:\.\d+)?'
    r')(?![\w.%])'
)


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def context_for(text):
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    for line in lines[:18]:
        low = line.lower()
        if any(keyword in low for keyword in KEYWORDS):
            return line[:200]
    return lines[0][:200] if lines else ''


def classify(context, header):
    value = f'{context} {header}'.lower()
    if 'hospitality' in value:
        return 'hospitality_expense'
    if 'district capital' in value:
        return 'district_capital_expenditure'
    if 'district activity' in value:
        return 'district_activity_expenditure'
    if 'recreation area' in value or 'area rate' in value:
        return 'area_rate_expenditure'
    if 'capital projection' in value or ('capital' in value and 'actual' in value):
        return 'capital_summary'
    if 'reserve' in value:
        return 'reserve_summary'
    if 'expense' in value or 'expenditure' in value:
        return 'operating_expense_summary'
    return None


def parse_money_token(token: str) -> float:
    raw = clean(token)
    negative = raw.startswith('(') and raw.endswith(')')
    compact = raw.replace('$', '').replace(',', '').replace(' ', '')
    if negative:
        compact = compact[1:-1]
    value = float(compact)
    if negative:
        value = -value
    value = round(value, 2)
    if not math.isfinite(value) or abs(value) > MAX_ABS_VALUE:
        raise ValueError(f'monetary token outside plausibility ceiling: {token!r} -> {value!r}')
    return value


def extract_cell_values(cell: str) -> list[float]:
    text = clean(cell)
    if not text:
        return []
    values: list[float] = []
    for match in MONEY_TOKEN_RE.finditer(text):
        token = match.group(0)
        # Plain integers embedded in descriptive text are not money. Exact
        # numeric cells are allowed; merged cells need currency-style evidence.
        if not any(marker in token for marker in (',', '$', '(', ')', '-')):
            if text.strip() != token.strip():
                continue
        values.append(parse_money_token(token))
    return values


def row_label(row: list[str]) -> tuple[int | None, str]:
    for index, cell in enumerate(row):
        value = clean(cell)
        if value and re.search(r'[A-Za-z]', value):
            return index, value
    return None, ''


def fiscal_year(source_id: str) -> str:
    return '2024/25' if '2024-25' in source_id else '2023/24'


def main():
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    by_id = {source['id']: source for source in registry['sources']}
    session = requests.Session()
    session.headers['User-Agent'] = UA
    records: list[dict] = []
    source_status: list[dict] = []
    failures: list[str] = []

    for source_id, period_end in PERIOD_END.items():
        source = by_id.get(source_id)
        if not source:
            failures.append(f'{source_id}: missing registry entry')
            continue
        try:
            response = session.get(source['url'], timeout=120)
            response.raise_for_status()
            if not response.content.startswith(b'%PDF'):
                raise RuntimeError('response is not PDF')
            source_rows = 0
            rejected_rows = 0
            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ''
                    page_context = context_for(text)
                    for table_num, table in enumerate(page.extract_tables() or [], 1):
                        normalized = [[clean(cell) for cell in (row or [])] for row in (table or [])]
                        if len(normalized) < 2:
                            continue
                        header = ' | '.join(' '.join(row) for row in normalized[:3])
                        record_type = classify(page_context, header)
                        if not record_type:
                            continue
                        for row_num, row in enumerate(normalized[1:], 1):
                            label_index, label = row_label(row)
                            if label_index is None or not label:
                                continue
                            low_label = label.lower()
                            if low_label.startswith(('page ', 'halifax regional municipality', 'statement of')):
                                continue
                            values: list[float] = []
                            for cell in row[label_index + 1:]:
                                values.extend(extract_cell_values(cell))
                            if not values:
                                rejected_rows += 1
                                continue
                            amount = values[-1]
                            locator = f'p{page_num}/t{table_num}/r{row_num}'
                            record = {
                                'record_type': record_type,
                                'posting_date': period_end,
                                'fiscal_year': fiscal_year(source_id),
                                'business_unit': label if record_type == 'operating_expense_summary' else None,
                                'account': page_context or record_type.replace('_', ' '),
                                'category': page_context or record_type.replace('_', ' '),
                                'amount': amount,
                                'amount_semantics': 'last_monetary_value_in_source_row',
                                'values': values,
                                'label_cell_index': label_index,
                                'raw_cells': row,
                                'source_page': page_num,
                                'source_table': table_num,
                                'source_row': row_num,
                                'source_id': source_id,
                                'granularity': 'official_summary_table_row',
                                'provenance': provenance(
                                    source_id,
                                    source['url'],
                                    'page/table/row',
                                    locator,
                                    PARSER_VERSION,
                                ),
                            }
                            records.append(record)
                            source_rows += 1
            if source_rows < 1:
                raise RuntimeError('no conservative spending summary rows extracted')
            source_status.append({
                'source_id': source_id,
                'status': 'ok',
                'records': source_rows,
                'rejected_rows_without_monetary_values': rejected_rows,
            })
            print(f'{source_id}: records={source_rows} rejected_without_values={rejected_rows}')
        except Exception as exc:
            failures.append(f'{source_id}: {type(exc).__name__}: {exc}')

    if failures:
        raise RuntimeError('Quarterly spending refresh failed closed: ' + ' | '.join(failures))
    if len(source_status) != len(PERIOD_END):
        raise RuntimeError(f'Only {len(source_status)}/{len(PERIOD_END)} quarterly sources completed')
    if len(records) < 50:
        raise RuntimeError(f'Only {len(records)} conservative spending rows extracted; refusing to replace artifact')

    records.sort(key=lambda row: (
        row['source_id'], row['source_page'], row['source_table'], row['source_row']
    ))
    payload = {
        'metadata': {
            'dataset_status': 'conservative_quarterly_summary_extraction',
            'parser_version': PARSER_VERSION,
            'generated_at': now(),
            'records': len(records),
            'source_status': source_status,
            'granularity': 'quarterly financial summary tables',
            'is_transaction_ledger': False,
            'amount_semantics': 'last monetary value in the extracted source row; all independently tokenized monetary values are retained in values',
            'note': (
                'Official HRM quarterly report summary rows. This is not a transaction-level accounts-payable ledger. '
                'Merged PDF cells are tokenized into separate values and revenue-only tables are not relabeled as spending.'
            ),
        },
        'records': records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(OUT)
    print(f'quarterly spending summaries: {len(records)} conservative rows')


if __name__ == '__main__':
    main()
