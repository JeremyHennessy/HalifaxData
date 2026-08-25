#!/usr/bin/env python3
"""Extract HRM budget/service-area facts and audited PSAS actuals.

Build 004 deliberately keeps the two accounting views separate:
- 2025/26 Budget & Business Plan service-area tables use the budget-book basis.
- 2025 audited consolidated statement rows use PSAS presentation and are in $000s.

The collector is source-specific and guarded. It refuses to overwrite budget.json unless
both official PDFs download, expected page structures are present, all 18 configured
budget sections yield a Net Total, and independent published control totals reconcile.
Published budget-change arithmetic is preserved even when it disagrees with the source
row endpoints; those inconsistencies are explicitly flagged instead of silently repaired.
Source labels are retained verbatim. A very small alias map is used only where an official
HRM source independently establishes the complete label behind a truncated/typo table label.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
from pathlib import Path

import pdfplumber
import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'data' / 'sources.json'
OUTPUT = ROOT / 'data' / 'generated' / 'budget.json'
UA = 'HalifaxData/0.1 (+https://github.com/JeremyHennessy/HalifaxData)'
BUDGET_SOURCE_ID = 'hrm-budget-2025-26'
FINANCIAL_SOURCE_ID = 'hrm-financials-2025'

# PDF page numbers are physical pages (1-based), not printed section labels.
# The heading check makes these locators fail closed if HRM replaces/reorders the source PDF.
OVERVIEW_PAGES = {
    31: ('Halifax Regional Fire & Emergency', 'Halifax Regional Fire & Emergency'),
    52: ('Halifax Regional Police', 'BUDGET – HALIFAX REGIONAL POLICE'),
    78: ('Community Safety', 'Community Safety'),
    100: ('Halifax Transit', 'Halifax Transit'),
    119: ('Halifax Public Libraries', 'Halifax Public Libraries'),
    134: ('Major Projects Office', 'Major Projects Office'),
    147: ('Property, Fleet & Environment', 'Property, Fleet & Environment'),
    176: ('Parks & Recreation', 'Parks & Recreation'),
    223: ('Planning & Development', 'Planning & Development'),
    248: ('Public Works', 'Public Works'),
    271: ('Strategic Infrastructure & Transportation Planning', 'Strategic Infrastructure & Transportation Planning'),
    278: ('Office of the Auditor General', 'Office of the Auditor General'),
    286: ('CAO Business Unit', 'CAO Business Unit'),
    306: ('Finance & Asset Management', 'Finance & Asset Management'),
    324: ('Information Technology', 'Information Technology'),
    341: ('Human Resources', 'Human Resources'),
    357: ('Legal & Legislative Services', 'Legal & Legislative Services'),
    369: ('Fiscal Services', 'Fiscal Services'),
}

# Independent source controls used to detect silent column/page drift.
BUDGET_NET_CONTROLS = {
    'Halifax Regional Fire & Emergency': 98_189_400,
    'Halifax Regional Police': 101_255_700,
    'Halifax Transit': 63_462_600,
    'Halifax Public Libraries': 28_454_700,
    'Finance & Asset Management': 17_971_600,
    'Fiscal Services': -689_347_600,
}
AUDITED_CONTROLS = {
    ('revenue', 'Total revenue'): (1_347_173_000, 1_410_626_000),
    ('expense', 'Total expenses'): (1_338_192_000, 1_350_788_000),
    ('surplus', 'Annual surplus'): (8_981_000, 59_838_000),
}

# These are the only service-area label normalizations in Build 004. The raw table text
# remains in source_service_area_label. Two are established elsewhere in the SAME 2025/26
# budget book; the Libraries label is truncated throughout that table but is spelled out in
# prior official HRM budget books.
SERVICE_AREA_ALIASES = {
    'Infrastructure Maintenance & Operatons': {
        'canonical': 'Infrastructure Maintenance & Operations',
        'basis': 'same_source_section_heading',
        'evidence': '2025/26 Budget & Business Plan PDF page 253',
    },
    'Government Relations & Externa': {
        'canonical': 'Government Relations & External Affairs',
        'basis': 'same_source_section_heading',
        'evidence': '2025/26 Budget & Business Plan PDF page 295',
    },
    'Information Technology/Collecti': {
        'canonical': 'Information Technology/Collections',
        'basis': 'prior_official_budget_label',
        'evidence': 'Prior official HRM Budget & Business Plan service-area label',
    },
}


def clean(value: object) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def source_by_id(source_id: str) -> dict:
    registry = json.loads(SOURCES.read_text())
    for source in registry.get('sources', []):
        if source.get('id') == source_id:
            return source
    raise RuntimeError(f'missing source registry entry: {source_id}')


def download_pdf(source_id: str) -> tuple[bytes, str]:
    source = source_by_id(source_id)
    response = requests.get(source['url'], headers={'User-Agent': UA}, timeout=120)
    response.raise_for_status()
    blob = response.content
    if not blob.startswith(b'%PDF'):
        raise RuntimeError(f'{source_id}: response is not a PDF ({response.headers.get("content-type")})')
    return blob, hashlib.sha256(blob).hexdigest()


def visual_rows(page) -> list[list[dict]]:
    """Group PDF words into visual rows while preserving x coordinates."""
    words = page.extract_words(
        x_tolerance=1,
        y_tolerance=2,
        keep_blank_chars=False,
        use_text_flow=False,
    )
    rows: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (w['top'], w['x0'])):
        for row in rows:
            if abs(row[0]['top'] - word['top']) <= 2.2:
                row.append(word)
                break
        else:
            rows.append([word])
    return [sorted(row, key=lambda w: w['x0']) for row in sorted(rows, key=lambda r: r[0]['top'])]


def parse_numeric_words(words: list[dict], *, percent: bool = False) -> float | int | None:
    text = ''.join(str(word['text']) for word in words)
    text = text.replace('$', '').replace(',', '').replace(' ', '')
    if text in {'', '-', '–', '—'}:
        return None
    negative = text.startswith('(') and text.endswith(')')
    text = text.strip('()')
    if text in {'', '-'}:
        return None
    try:
        value = float(text) if (percent or '.' in text) else int(text)
    except ValueError as exc:
        raise RuntimeError(f'cannot parse numeric cell {text!r}') from exc
    return -value if negative else value


def budget_buckets(row: list[dict]) -> dict[str, list[dict]]:
    buckets = {key: [] for key in ('label', 'prior_actual', 'prior_budget', 'projection', 'current_budget', 'source_delta', 'source_delta_pct')}
    for word in row:
        x = float(word['x0'])
        if x < 215:
            key = 'label'
        elif x < 280:
            key = 'prior_actual'
        elif x < 340:
            key = 'prior_budget'
        elif x < 405:
            key = 'projection'
        elif x < 466:
            key = 'current_budget'
        elif x < 527:
            key = 'source_delta'
        else:
            key = 'source_delta_pct'
        buckets[key].append(word)
    return buckets


def annotate_budget_arithmetic(record: dict) -> None:
    """Add independently calculated change fields and tag source arithmetic mismatches."""
    prior_budget = record.get('prior_budget')
    current_budget = record.get('current_budget')
    if prior_budget is None or current_budget is None:
        return

    derived = current_budget - prior_budget
    record['derived_budget_change'] = derived
    derived_pct = None
    if prior_budget != 0:
        derived_pct = derived / prior_budget * 100
        record['derived_budget_change_pct'] = round(derived_pct, 4)

    flags: list[str] = []
    source_delta = record.get('source_reported_budget_change')
    if source_delta is not None and source_delta != derived:
        flags.append('reported_budget_change_mismatch')
        record['source_budget_change_delta'] = source_delta - derived

    source_pct = record.get('source_reported_budget_change_pct')
    # Source percentages are printed to one decimal place, so >0.11 percentage points
    # is safely outside normal source rounding.
    if source_pct is not None and derived_pct is not None and abs(source_pct - derived_pct) > 0.11:
        flags.append('reported_budget_change_pct_mismatch')
        record['source_budget_change_pct_delta'] = round(source_pct - derived_pct, 4)

    if flags:
        record['validation_flags'] = flags


def normalize_service_area(raw_label: str) -> tuple[str, dict | None]:
    alias = SERVICE_AREA_ALIASES.get(raw_label)
    if not alias:
        return raw_label, None
    return alias['canonical'], alias


def parse_budget_page(page, page_number: int, business_unit: str, required_heading: str) -> list[dict]:
    text = page.extract_text() or ''
    if required_heading not in text:
        raise RuntimeError(f'budget page {page_number}: expected heading {required_heading!r} not found')
    if 'SERVICE AREA BUDGET OVERVIEW' not in text and 'Service Area Budget Overview' not in text:
        raise RuntimeError(f'budget page {page_number}: service-area overview marker not found')

    rows = visual_rows(page)
    header_index = None
    for index, row in enumerate(rows):
        row_text = ' '.join(str(w['text']) for w in row)
        if 'Service Area' in row_text and 'Actual' in row_text and 'Projections' in row_text and 'Budget' in row_text:
            header_index = index
            break
    if header_index is None:
        raise RuntimeError(f'budget page {page_number}: column header not found')

    records: list[dict] = []
    pending_label: list[str] = []
    for row in rows[header_index + 1:]:
        buckets = budget_buckets(row)
        label = clean(' '.join(str(w['text']) for w in buckets['label']))
        values = {
            'prior_actual': parse_numeric_words(buckets['prior_actual']),
            'prior_budget': parse_numeric_words(buckets['prior_budget']),
            'projection': parse_numeric_words(buckets['projection']),
            'current_budget': parse_numeric_words(buckets['current_budget']),
            'source_delta': parse_numeric_words(buckets['source_delta']),
            'source_delta_pct': parse_numeric_words(buckets['source_delta_pct'], percent=True),
        }
        has_financial_value = any(values[key] is not None for key in ('prior_actual', 'prior_budget', 'projection', 'current_budget'))

        if not has_financial_value:
            if label and not any(marker in label for marker in ('SUMMARY OF', 'Expenditures', 'Revenues')):
                pending_label.append(label)
            continue

        raw_label = clean(' '.join([*pending_label, label]))
        pending_label = []
        if not raw_label:
            raise RuntimeError(f'budget page {page_number}: numeric row without service-area label')
        service_area, alias = normalize_service_area(raw_label)

        record = {
            'record_type': 'service_area_budget',
            'fiscal_year': '2025/26',
            'fiscal_year_end': 2026,
            'business_unit': business_unit,
            'service_area': service_area,
            'source_service_area_label': raw_label,
            'prior_actual': values['prior_actual'],
            'prior_actual_period': '2023/24',
            'prior_budget': values['prior_budget'],
            'prior_budget_period': '2024/25',
            'projection': values['projection'],
            'projection_period': '2024/25',
            'current_budget': values['current_budget'],
            'current_budget_period': '2025/26',
            'source_reported_budget_change': values['source_delta'],
            'source_reported_budget_change_pct': values['source_delta_pct'],
            'is_total': service_area == 'Net Total',
            'source_id': BUDGET_SOURCE_ID,
            'pdf_page': page_number,
        }
        if alias:
            record['label_normalization_basis'] = alias['basis']
            record['label_normalization_evidence'] = alias['evidence']
        annotate_budget_arithmetic(record)
        records.append(record)
        if record['is_total']:
            break

    totals = [row for row in records if row['is_total']]
    if len(totals) != 1:
        raise RuntimeError(f'budget page {page_number}: expected exactly one Net Total, found {len(totals)}')
    return records


def parse_budget_book(blob: bytes) -> tuple[list[dict], dict]:
    records: list[dict] = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        if len(pdf.pages) != 417:
            raise RuntimeError(f'{BUDGET_SOURCE_ID}: expected 417 PDF pages, found {len(pdf.pages)}')
        for page_number, (business_unit, required_heading) in OVERVIEW_PAGES.items():
            records.extend(parse_budget_page(pdf.pages[page_number - 1], page_number, business_unit, required_heading))

    total_rows = [row for row in records if row['is_total']]
    if len(total_rows) != len(OVERVIEW_PAGES):
        raise RuntimeError(f'{BUDGET_SOURCE_ID}: expected {len(OVERVIEW_PAGES)} business-unit totals, found {len(total_rows)}')
    if len(records) < 55:
        raise RuntimeError(f'{BUDGET_SOURCE_ID}: only {len(records)} service-area rows; refusing output')

    totals_by_unit = {row['business_unit']: row['current_budget'] for row in total_rows}
    for unit, expected in BUDGET_NET_CONTROLS.items():
        if totals_by_unit.get(unit) != expected:
            raise RuntimeError(f'{BUDGET_SOURCE_ID}: control total mismatch for {unit}: {totals_by_unit.get(unit)} != {expected}')

    delta_mismatches = sum('reported_budget_change_mismatch' in row.get('validation_flags', []) for row in records)
    pct_mismatches = sum('reported_budget_change_pct_mismatch' in row.get('validation_flags', []) for row in records)
    discrepancy_rows = sum(bool(row.get('validation_flags')) for row in records)
    normalized_labels = sum(row['service_area'] != row['source_service_area_label'] for row in records)
    return records, {
        'service_area_record_count': len(records),
        'service_area_detail_count': sum(not row['is_total'] for row in records),
        'business_unit_count': len(total_rows),
        'budget_source_arithmetic_discrepancy_rows': discrepancy_rows,
        'budget_source_delta_mismatches': delta_mismatches,
        'budget_source_pct_mismatches': pct_mismatches,
        'normalized_service_area_labels': normalized_labels,
    }


def financial_buckets(row: list[dict]) -> dict[str, list[dict]]:
    buckets = {key: [] for key in ('label', 'budget', 'actual', 'prior_actual')}
    for word in row:
        x = float(word['x0'])
        if x < 330:
            key = 'label'
        elif x < 415:
            key = 'budget'
        elif x < 490:
            key = 'actual'
        else:
            key = 'prior_actual'
        buckets[key].append(word)
    return buckets


def parse_audited_financials(blob: bytes) -> tuple[list[dict], dict]:
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        if len(pdf.pages) != 40:
            raise RuntimeError(f'{FINANCIAL_SOURCE_ID}: expected 40 PDF pages, found {len(pdf.pages)}')
        page_number = 8
        page = pdf.pages[page_number - 1]
        text = page.extract_text() or ''
        if 'Consolidated Statement of Operations and Accumulated Surplus' not in text or '(In thousands of dollars)' not in text:
            raise RuntimeError(f'{FINANCIAL_SOURCE_ID}: statement of operations structure not found on PDF page {page_number}')
        rows = visual_rows(page)

    records: list[dict] = []
    section: str | None = None
    pending_label: list[str] = []
    for row in rows:
        row_text = clean(' '.join(str(w['text']) for w in row))
        if row_text == 'Revenue':
            section = 'revenue'; pending_label = []; continue
        if row_text == 'Expenses':
            section = 'expense'; pending_label = []; continue
        if section is None:
            continue

        buckets = financial_buckets(row)
        label = clean(' '.join(str(w['text']) for w in buckets['label']))
        budget_thousands = parse_numeric_words(buckets['budget'])
        actual_thousands = parse_numeric_words(buckets['actual'])
        prior_thousands = parse_numeric_words(buckets['prior_actual'])
        has_value = any(value is not None for value in (budget_thousands, actual_thousands, prior_thousands))

        if not has_value:
            if label and label not in {'Budget 2 025 2024', '(Adjusted -', 'Note 2)'}:
                pending_label.append(label)
            continue

        category = clean(' '.join([*pending_label, label]))
        pending_label = []
        if not category:
            continue
        if category.startswith('Annual surplus'):
            section_for_row = 'surplus'
            category = 'Annual surplus'
        else:
            section_for_row = section

        def dollars(value):
            return None if value is None else int(round(float(value) * 1000))

        record = {
            'record_type': 'audited_psas',
            'fiscal_year': '2024/25',
            'fiscal_year_end': 2025,
            'statement_section': section_for_row,
            'category': category,
            'budget': dollars(budget_thousands),
            'actual': dollars(actual_thousands),
            'prior_actual': dollars(prior_thousands),
            'prior_actual_fiscal_year_end': 2024,
            'source_id': FINANCIAL_SOURCE_ID,
            'pdf_page': page_number,
            'printed_page': 4,
            'source_units': 'thousands_of_cad',
        }
        if record['budget'] is not None and record['actual'] is not None:
            record['variance'] = record['actual'] - record['budget']
        records.append(record)
        if section_for_row == 'surplus':
            break

    if len(records) != 20:
        raise RuntimeError(f'{FINANCIAL_SOURCE_ID}: expected 20 statement rows, found {len(records)}')
    by_key = {(row['statement_section'], row['category']): row for row in records}
    for key, (expected_budget, expected_actual) in AUDITED_CONTROLS.items():
        row = by_key.get(key)
        if not row:
            raise RuntimeError(f'{FINANCIAL_SOURCE_ID}: missing control row {key}')
        if (row['budget'], row['actual']) != (expected_budget, expected_actual):
            raise RuntimeError(f'{FINANCIAL_SOURCE_ID}: control mismatch for {key}: {(row["budget"], row["actual"])}')

    return records, {
        'audited_record_count': len(records),
        'audited_statement_pdf_page': 8,
        'audited_statement_printed_page': 4,
        'audited_total_revenue_budget': by_key[('revenue', 'Total revenue')]['budget'],
        'audited_total_revenue_actual': by_key[('revenue', 'Total revenue')]['actual'],
        'audited_total_expenses_budget': by_key[('expense', 'Total expenses')]['budget'],
        'audited_total_expenses_actual': by_key[('expense', 'Total expenses')]['actual'],
        'audited_annual_surplus_budget': by_key[('surplus', 'Annual surplus')]['budget'],
        'audited_annual_surplus_actual': by_key[('surplus', 'Annual surplus')]['actual'],
    }


def main() -> None:
    budget_blob, budget_sha = download_pdf(BUDGET_SOURCE_ID)
    financial_blob, financial_sha = download_pdf(FINANCIAL_SOURCE_ID)
    budget_rows, budget_stats = parse_budget_book(budget_blob)
    audited_rows, audited_stats = parse_audited_financials(financial_blob)

    payload = {
        'metadata': {
            'dataset_status': 'automated_structured_extraction',
            'budget_fiscal_year': '2025/26',
            'audited_fiscal_year_end': 2025,
            'source_ids': [BUDGET_SOURCE_ID, FINANCIAL_SOURCE_ID],
            'source_sha256': {BUDGET_SOURCE_ID: budget_sha, FINANCIAL_SOURCE_ID: financial_sha},
            **budget_stats,
            **audited_stats,
            'note': 'Service-area budget rows and audited PSAS rows are separate accounting views and are not force-joined. Budget-book rows retain raw source labels and source-reported change columns plus independently derived arithmetic; published inconsistencies are explicitly flagged. Three truncated/typo service-area labels are canonicalized only where official HRM budget evidence establishes the complete label. Audited statement amounts are converted from source $000s to CAD.',
        },
        'records': [*budget_rows, *audited_rows],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    tmp.replace(OUTPUT)
    print(
        f'Wrote {len(budget_rows)} budget-book rows and {len(audited_rows)} audited rows to {OUTPUT} '
        f'({budget_stats["budget_source_arithmetic_discrepancy_rows"]} budget source arithmetic discrepancy rows; '
        f'{budget_stats["normalized_service_area_labels"]} normalized labels)',
        file=sys.stderr,
    )


if __name__ == '__main__':
    main()
