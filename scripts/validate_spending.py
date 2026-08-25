#!/usr/bin/env python3
"""Independently validate conservative quarterly spending-summary extraction."""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'data/generated/spending.json'
REGISTRY = ROOT / 'data/sources.json'
EXPECTED_STATUS = 'conservative_quarterly_summary_extraction'
EXPECTED_PARSER = 'build005-spending-v2'
MAX_ABS_VALUE = 10_000_000_000
PERIOD_END = {
    'hrm-q2-2024-25': '2024-09-30',
    'hrm-q3-2024-25': '2024-12-31',
    'hrm-q1-2023-24': '2023-06-30',
    'hrm-q2-2023-24': '2023-09-30',
    'hrm-q3-2023-24': '2023-12-31',
}
MONEY_TOKEN_RE = re.compile(
    r'(?<![\w.])(?:'
    r'\(\s*\$?\s*\d[\d,]*(?:\.\d+)?\s*\)'
    r'|-?\s*\$?\s*\d[\d,]*(?:\.\d+)?'
    r')(?![\w.%])'
)
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def clean(value) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def parse_token(token: str) -> float:
    raw = clean(token)
    negative = raw.startswith('(') and raw.endswith(')')
    compact = raw.replace('$', '').replace(',', '').replace(' ', '')
    if negative:
        compact = compact[1:-1]
    number = float(compact)
    if negative:
        number = -number
    return round(number, 2)


def independent_values(cell: str) -> list[float]:
    text = clean(cell)
    values: list[float] = []
    for match in MONEY_TOKEN_RE.finditer(text):
        token = match.group(0)
        if not any(marker in token for marker in (',', '$', '(', ')', '-')) and text.strip() != token.strip():
            continue
        values.append(parse_token(token))
    return values


def main() -> None:
    if not PATH.exists():
        raise SystemExit(f'Missing spending artifact: {PATH.relative_to(ROOT)}')
    payload = json.loads(PATH.read_text(encoding='utf-8'))
    metadata = payload.get('metadata') or {}
    rows = payload.get('records')
    if not isinstance(rows, list):
        raise SystemExit('spending.json records must be a list')

    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    registry_ids = {row.get('id') for row in registry.get('sources', [])}
    for source_id in PERIOD_END:
        if source_id not in registry_ids:
            fail(f'configured quarterly source {source_id!r} is missing from registry')

    if metadata.get('dataset_status') != EXPECTED_STATUS:
        fail(f"dataset_status {metadata.get('dataset_status')!r} != {EXPECTED_STATUS!r}")
    if metadata.get('parser_version') != EXPECTED_PARSER:
        fail(f"parser_version {metadata.get('parser_version')!r} != {EXPECTED_PARSER!r}")
    if metadata.get('records') != len(rows):
        fail(f"metadata records {metadata.get('records')!r} != actual {len(rows)}")
    if metadata.get('is_transaction_ledger') is not False:
        fail('spending artifact must explicitly state is_transaction_ledger=false')
    if metadata.get('granularity') != 'quarterly financial summary tables':
        fail(f"unexpected granularity {metadata.get('granularity')!r}")

    statuses = metadata.get('source_status') or []
    if not isinstance(statuses, list):
        fail('source_status must be a list')
        statuses = []
    status_ids = [item.get('source_id') for item in statuses]
    if set(status_ids) != set(PERIOD_END) or len(status_ids) != len(PERIOD_END):
        fail('source_status must contain each configured quarterly source exactly once')
    status_by_id = {item.get('source_id'): item for item in statuses}
    for source_id in PERIOD_END:
        item = status_by_id.get(source_id) or {}
        if item.get('status') != 'ok':
            fail(f'{source_id}: source status is not ok')
        if not isinstance(item.get('records'), int) or item.get('records', 0) < 1:
            fail(f'{source_id}: source status has no positive record count')
        rejected = item.get('rejected_rows_without_monetary_values')
        if not isinstance(rejected, int) or rejected < 0:
            fail(f'{source_id}: rejected row count must be a non-negative integer')

    counts: Counter[str] = Counter()
    seen_locators: set[tuple[str, str]] = set()
    allowed_types = {
        'hospitality_expense', 'district_capital_expenditure',
        'district_activity_expenditure', 'area_rate_expenditure',
        'capital_summary', 'reserve_summary', 'operating_expense_summary',
    }
    for index, row in enumerate(rows):
        source_id = row.get('source_id')
        if source_id not in PERIOD_END:
            fail(f'row {index}: unknown source_id {source_id!r}')
            continue
        counts[source_id] += 1
        if row.get('posting_date') != PERIOD_END[source_id]:
            fail(f'row {index}: posting_date does not match configured period end')
        expected_fy = '2024/25' if '2024-25' in source_id else '2023/24'
        if row.get('fiscal_year') != expected_fy:
            fail(f'row {index}: fiscal_year {row.get("fiscal_year")!r} != {expected_fy!r}')
        if row.get('record_type') not in allowed_types:
            fail(f'row {index}: unsupported record_type {row.get("record_type")!r}')
        if row.get('granularity') != 'official_summary_table_row':
            fail(f'row {index}: invalid granularity')
        if row.get('amount_semantics') != 'last_monetary_value_in_source_row':
            fail(f'row {index}: unexpected amount_semantics')
        if not clean(row.get('account')) or not clean(row.get('category')):
            fail(f'row {index}: blank account/category context')

        raw_cells = row.get('raw_cells')
        label_index = row.get('label_cell_index')
        if not isinstance(raw_cells, list) or not isinstance(label_index, int) or label_index < 0 or label_index >= len(raw_cells):
            fail(f'row {index}: invalid raw_cells/label_cell_index')
            continue
        expected_values: list[float] = []
        for cell in raw_cells[label_index + 1:]:
            try:
                expected_values.extend(independent_values(cell))
            except Exception as exc:
                fail(f'row {index}: independent token parse failed: {type(exc).__name__}: {exc}')
        actual_values = row.get('values')
        if not isinstance(actual_values, list) or not actual_values:
            fail(f'row {index}: values must be a non-empty list')
            actual_values = []
        if actual_values != expected_values:
            fail(f'row {index}: values do not match independently tokenized raw cells')
        for value in actual_values:
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                fail(f'row {index}: non-finite/non-numeric monetary value {value!r}')
            elif abs(value) > MAX_ABS_VALUE:
                fail(f'row {index}: value {value!r} exceeds plausibility ceiling')
        amount = row.get('amount')
        if not actual_values or amount != actual_values[-1]:
            fail(f'row {index}: amount must equal final independently tokenized monetary value')

        page, table, source_row = row.get('source_page'), row.get('source_table'), row.get('source_row')
        if not isinstance(page, int) or page < 1 or not isinstance(table, int) or table < 1 or not isinstance(source_row, int) or source_row < 1:
            fail(f'row {index}: invalid source page/table/row coordinates')
        provenance = row.get('provenance') or {}
        if provenance.get('source_id') != source_id:
            fail(f'row {index}: provenance source_id mismatch')
        if provenance.get('parser_version') != EXPECTED_PARSER:
            fail(f'row {index}: stale provenance parser_version')
        if provenance.get('validation_status') != 'parsed':
            fail(f'row {index}: provenance validation_status must be parsed')
        locator = provenance.get('locator_value')
        expected_locator = f'p{page}/t{table}/r{source_row}'
        if locator != expected_locator:
            fail(f'row {index}: locator {locator!r} != {expected_locator!r}')
        locator_key = (source_id, str(locator))
        if locator_key in seen_locators:
            fail(f'row {index}: duplicate source locator {locator_key!r}')
        seen_locators.add(locator_key)
        if not provenance.get('source_url'):
            fail(f'row {index}: missing provenance source_url')

    for source_id in PERIOD_END:
        status_count = (status_by_id.get(source_id) or {}).get('records')
        if status_count != counts[source_id]:
            fail(f'{source_id}: metadata count {status_count!r} != actual {counts[source_id]}')

    if errors:
        print('SPENDING VALIDATION FAILED', file=sys.stderr)
        for message in errors[:100]:
            print(message, file=sys.stderr)
        raise SystemExit(1)

    print(f'validated {len(rows)} conservative quarterly spending-summary rows across {len(PERIOD_END)} sources')
    for source_id in sorted(PERIOD_END):
        print(f'{source_id}: rows={counts[source_id]}')


if __name__ == '__main__':
    main()
