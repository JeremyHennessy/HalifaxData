"""Bounded summary-table facts, never payments or a current forecast."""
import hashlib,json,re
from review_receipts import validate_receipt
TOP={'records', 'visualReview', 'sourceId', 'sourcePdfSha256', 'checks', 'coverage', 'limitations', 'schemaVersion', 'sourceURL'}
ROW={'latestForecastClaim', 'fiscalYearLabel', 'provenance', 'stage', 'sourceLocator', 'section', 'unit', 'table', 'financialBasis', 'presence', 'id', 'reportingPerimeter', 'label', 'rawValue', 'multiplier', 'currency', 'paymentEvidence', 'sourceURL', 'rawToken'}
PROVENANCE={'printedPage', 'pdfPage', 'transform', 'columnIndex', 'lineInExtractedPage', 'sourcePdfSha256'}
COVERAGE={'rows', 'tables', 'present', 'completeDocument', 'slots', 'publicationDateVerified', 'announcementDate'}
def budget_files(root):
    folder=root/'data/budget-tables';path=folder/'records.json'
    if not path.exists():return []
    review=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'budget')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=review['bundleSha256']:raise ValueError('Budget table bytes changed after review')
    b=json.loads(path.read_text())
    if set(b)!=TOP or set(b['coverage'])!=COVERAGE or b['schemaVersion']!='budget-addendum-tables-v1' or b['sourcePdfSha256']!=review['sourcePdfSha256'] or b['coverage']['completeDocument'] is not False or b['coverage']['publicationDateVerified'] is not False:raise ValueError('Unverified budget coverage')
    if set(b['visualReview'])!={'pages','reviewScope','reviewedOn'}:raise ValueError('Unexpected review fields')
    for check in b['checks']:
        if set(check)!={'columnIndex','expenseComponents','expensesReconcile','revenueSourcesReconcile'}:raise ValueError('Unexpected reconciliation field')
    ids=set();rows=set();present=0
    for row in b['records']:
        if set(row)!=ROW or set(row['provenance'])!=PROVENANCE or row['id'] in ids:raise ValueError('Invalid budget identity or fields')
        columns={0:('2025-26','estimate_as_presented_in_addendum'),1:('2025-26','forecast_as_presented_in_addendum'),2:('2026-27','amended_estimate')}
        if (row['fiscalYearLabel'],row['stage'])!=columns.get(row['provenance']['columnIndex']) or row['provenance']['pdfPage']!={'2.1':2,'2.2':3}.get(row['table']):raise ValueError('Budget column or page mismatch')
        ids.add(row['id']);rows.add((row['table'],row['section'],row['label']))
        if row['currency']!='CAD' or row['multiplier']!=1000 or row['unit']!='CAD_thousands' or row['paymentEvidence'] is not False or row['latestForecastClaim'] is not False or row['stage'] not in ('amended_estimate','estimate_as_presented_in_addendum','forecast_as_presented_in_addendum') or row['provenance']['sourcePdfSha256']!=b['sourcePdfSha256']:raise ValueError('Unverified financial meaning')
        if row['presence']=='source_dash':
            if row['rawValue'] is not None or row['rawToken']!='---':raise ValueError('Source dash is not zero')
        elif row['presence']=='present' and isinstance(row['rawValue'],str) and re.fullmatch(r'-?\d+',row['rawValue']):
            present+=1
            token=row['rawToken'].replace(',','');token='-'+token[1:-1] if token.startswith('(') and token.endswith(')') else token
            if token!=row['rawValue']:raise ValueError('Original token mismatch')
        else:raise ValueError('Invalid budget value')
    if len(ids)!=b['coverage']['slots'] or present!=b['coverage']['present'] or len(rows)!=b['coverage']['rows']:raise ValueError('Budget coverage mismatch')
    return ['data/budget-tables/records.json','data/budget-tables/publication-review.json']
