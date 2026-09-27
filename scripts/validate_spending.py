#!/usr/bin/env python3
"""Validate typed financial facts against independent controls and PDF fixtures."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(payload):
    registry = json.loads((ROOT / 'data/quarterly_financial_sources.json').read_text())['sources']
    sources = {s['id']: s for s in registry}
    rows = payload['records']
    meta = payload['metadata']
    assert meta['parser_version'] == 'build023-quarterly-geometry-v1'
    assert meta['is_transaction_ledger'] is False
    assert meta['records'] == len(rows) and len(rows) >= 1000
    assert meta['report_count'] == len(sources)
    assert meta['latest_period_end'] == max(s['period_end'] for s in registry)
    assert len({r['record_id'] for r in rows}) == len(rows)
    assert set(r['source_id'] for r in rows) == set(sources)
    for status in meta['source_status']:
        assert status['status'] == 'ok'
        blob = (ROOT / status['source_snapshot']).read_bytes()
        assert blob.startswith(b'%PDF')
        assert hashlib.sha256(blob).hexdigest() == status['source_sha256']
        assert status['records'] == sum(r['source_id'] == status['source_id'] for r in rows)
    for row in rows:
        source = sources[row['source_id']]
        assert row['posting_date'] == row['period_end'] == source['period_end']
        assert row['fiscal_year'] == source['fiscal_year'] and row['quarter'] == source['quarter']
        assert row['period_months'] == source['quarter'] * 3
        assert row['period_start'] == source['fiscal_year'][:4] + '-04-01'
        assert row['currency'] == 'CAD'
        assert row['provenance']['source_url'] == source['url']
        assert row['provenance']['parser_version'] == meta['parser_version']
        assert all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and abs(v) <= 1e10 for v in row['values'])
        assert not {'vendor','invoice_id','payment_id','cheque_number'}.intersection(row)
        if row['comparison_eligible']:
            f = row['financial_fields']
            assert row['measure'] == row['amount_semantics'] == 'current_ytd_actual'
            assert row['amount'] == f['current_ytd_actual']
            assert row['record_type'] == 'operating_expense_summary' and not row['quality_flags']
            assert abs(f['budget'] - f['forecast'] - f['forecast_variance']) <= 2
            assert abs(f['forecast'] - f['current_ytd_actual'] - f['forecast_available']) <= 2
            if f['forecast']:
                assert abs(100 * f['current_ytd_actual'] / f['forecast'] - f['actual_percent_of_forecast']) <= .16
        else:
            assert row['amount'] is None and row['measure'] is None and row['quality_flags']
    # Independently transcribed from rendered official PDF page 8, not generated
    # from collector tokens. The historical defect is required to fail here.
    transit = [r for r in rows if r['source_id'] == 'hrm-q3-2024-25' and r['source_page'] == 8 and r['business_unit'] == 'Halifax Transit']
    assert len(transit) == 1 and transit[0]['comparison_eligible']
    assert transit[0]['financial_fields'] == {
        'budget':145515500, 'forecast':147481900, 'forecast_variance':-1966400,
        'current_ytd_actual':111079932, 'actual_percent_of_forecast':75.3,
        'forecast_available':36401968, 'prior_ytd_actual':91100148}
    total = [r for r in rows if r['source_id'] == 'hrm-q3-2024-25' and r['source_page'] == 8 and r['source_table'] == 1 and r['business_unit'] == 'Total']
    assert len(total) == 1
    assert total[0]['financial_fields']['current_ytd_actual'] == 594874920
    assert total[0]['financial_fields']['prior_ytd_actual'] == 530832739
    for source_id in sources:
        assert sum(r['source_id'] == source_id and r['comparison_eligible'] for r in rows) >= 10, source_id
    return {'rows':len(rows), 'reports':len(sources), 'comparable':sum(r['comparison_eligible'] for r in rows), 'payment_facts':0}


if __name__ == '__main__':
    import sys
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data/generated/spending.json'
    print(json.dumps(validate(json.loads(p.read_text())), indent=2))
