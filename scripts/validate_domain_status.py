#!/usr/bin/env python3
"""Validate the UI lifecycle manifest against checked-in analytical artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'data/generated/domain_ingestion_status.json'
GENERATED = ROOT / 'data/generated'
RELEASED = {
    'budget': 'budget.json',
    'spending': 'spending.json',
    'procurement': 'procurement.json',
    'capital': 'capital.json',
    'financials': 'financials.json',
    'council': 'council.json',
}
ALLOWED = {'ready', 'pending_release', 'validation_pending', 'missing', 'error'}


def main() -> None:
    payload = json.loads(MANIFEST.read_text(encoding='utf-8'))
    records = payload.get('records')
    if not isinstance(records, list):
        raise SystemExit('domain lifecycle records must be a list')
    by_domain = {}
    errors = []
    for row in records:
        domain = row.get('domain')
        status = row.get('status')
        if not domain or domain in by_domain:
            errors.append(f'domain is blank or duplicated: {domain!r}')
            continue
        by_domain[domain] = row
        if status not in ALLOWED:
            errors.append(f'{domain}: unsupported lifecycle state {status!r}')
    for domain, filename in RELEASED.items():
        row = by_domain.get(domain)
        if not row:
            errors.append(f'{domain}: missing lifecycle record')
            continue
        if row.get('status') != 'ready':
            errors.append(f'{domain}: Build 005 release domain must be ready, got {row.get("status")!r}')
        path = GENERATED / filename
        if not path.exists():
            errors.append(f'{domain}: ready manifest points to missing {filename}')
        else:
            artifact = json.loads(path.read_text(encoding='utf-8'))
            rows = artifact.get('records')
            if not isinstance(rows, list) or not rows:
                errors.append(f'{domain}: ready artifact has no records')
    signals = by_domain.get('signals')
    if signals and signals.get('status') == 'ready' and not (GENERATED / 'signals.json').exists():
        errors.append('signals: ready state cannot be published without signals.json')
    if errors:
        print('DOMAIN LIFECYCLE VALIDATION FAILED', file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)
    print('validated lifecycle manifest: 6/6 Build 005 analytical domains ready')


if __name__ == '__main__':
    main()
