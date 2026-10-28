"""Institutional recognition facts with stock/flow and consolidation boundaries."""
import hashlib,json,re
from review_receipts import validate_receipt
KEYS={'coverage': ['numericValues', 'rows', 'statementPagesNormalized', 'valueSlots'], 'publication': ['allowed', 'consequentialAllegation', 'reviewId', 'reviewType', 'reviewedOn'], 'recognitionContext': ['consolidationSourcePdfPage', 'policyPrintedPage', 'policySourcePdfPage', 'relatedPartySourcePdfPage', 'relatedPartySummary', 'summary'], 'top': ['attribution', 'auditReportDate', 'checks', 'coverage', 'financialYearEnd', 'limits', 'publication', 'publisher', 'recognitionContext', 'records', 'retrievedAt', 'schemaVersion', 'sourceSha256', 'sourceTitle', 'sourceURL'], 'row': ['aggregationRole', 'asOf', 'basis', 'columnAsReported', 'currency', 'currencyBasis', 'currencyExplicitlySpecified', 'fiscalYear', 'id', 'label', 'measureType', 'multiplier', 'paymentEvidence', 'perimeter', 'periodEnd', 'periodStart', 'presence', 'rawToken', 'rawValue', 'sourceLocator', 'stage', 'unit'], 'locator': ['columnIndex', 'pdfPage', 'printedPage', 'rowLabel'], 'check': ['accumulatedSurplusReconciles', 'columnIndex', 'expenseComponents', 'revenueComponents', 'revenueLessExpensesReconciles']}
ROLES={'Provincial operating grant': 'component', 'PNS - retirement health benefits': 'component', 'Other Provincial government funding': 'component', 'Tuition and fees': 'component', 'Contract training and service contracts': 'component', 'Other (Note 7)': 'component', 'Total revenue': 'reported_subtotal', 'Salaries and benefits': 'component', 'Operating supplies and services': 'component', 'Equipment, rentals and other administration': 'component', 'Utilities and maintenance': 'component', 'Amortization of tangible capital assets': 'component', 'Total expenditures': 'reported_subtotal', 'Annual (deficit) before the undernoted': 'reported_balance', 'Net revenue from Foundation operations': 'component', 'Annual (deficit) surplus': 'reported_balance', 'Accumulated surplus, beginning of year': 'opening_balance', 'Accumulated surplus, end of year': 'closing_balance'}
def shape(v,key):
    if not isinstance(v,dict) or sorted(v)!=KEYS[key]:raise ValueError('Unexpected institutional fields')
def institution_files(root):
    folder=root/'data/nscc';path=folder/'records.json'
    if not path.exists():return []
    review=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'foundation')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=review['bundleSha256']:raise ValueError('Institutional review hash mismatch')
    b=json.loads(path.read_text());shape(b,'top')
    for key in ('coverage','publication','recognitionContext'):shape(b[key],key)
    p=b['publication']
    if b['schemaVersion']!='nscc-recognized-financials-v1' or p['allowed'] is not True or p['consequentialAllegation'] is not False or p['reviewType']!='source_attributed_institutional_financial_facts' or p['reviewId']!=review['evidenceId'] or p['reviewedOn']!=review['reviewedOn']:raise ValueError('Unreviewed institutional scope')
    for check in b['checks']:
        shape(check,'check')
        for key in ('expenseComponents','revenueComponents'):
            if set(check[key])!={'status','value'}:raise ValueError('Unexpected component check')
    ids=set();labels=set();numeric=0
    columns={0:('institution_budget_as_reported','2025-26','Budget'),1:('audited_statement_actual','2025-26','2026'),2:('prior_year_comparative_as_presented','2024-25','2025')}
    for row in b['records']:
        shape(row,'row');shape(row['sourceLocator'],'locator')
        if ROLES.get(row['label'])!=row['aggregationRole'] or row['id'] in ids or (row['stage'],row['fiscalYear'],row['columnAsReported'])!=columns.get(row['sourceLocator']['columnIndex']) or row['sourceLocator']['pdfPage']!=8 or row['sourceLocator']['rowLabel']!=row['label']:raise ValueError('Institutional source identity mismatch')
        ids.add(row['id']);labels.add(row['label'])
        if row['currency']!='CAD' or row['currencyExplicitlySpecified'] is not False or row['currencyBasis']!='context_inferred_from_canadian_public_sector_financial_statement' or row['multiplier']!=1 or row['unit']!='source_dollars' or row['paymentEvidence'] is not False or row['perimeter']!='College and Foundation with inter-company eliminations':raise ValueError('Unverified accounting claim')
        start=int(row['fiscalYear'][:4]);end=start+1
        if row['aggregationRole'] in ('opening_balance','closing_balance'):
            expected=f"{start if row['aggregationRole']=='opening_balance' else end}-03-31"
            if row['measureType']!='stock' or row['asOf']!=expected or row['periodStart'] is not None or row['periodEnd'] is not None:raise ValueError('Stock date mismatch')
        elif row['measureType']!='flow' or row['asOf'] is not None or row['periodStart']!=f'{start}-04-01' or row['periodEnd']!=f'{end}-03-31':raise ValueError('Flow period mismatch')
        if row['presence']=='source_dash':
            if row['rawValue'] is not None or row['rawToken']!='-':raise ValueError('Dash is not zero')
        elif row['presence']=='present' and isinstance(row['rawValue'],str) and re.fullmatch(r'-?\d+',row['rawValue']):
            numeric+=1;token=row['rawToken'].replace(',','');token='-'+token[1:-1] if token.startswith('(') and token.endswith(')') else token
            if token!=row['rawValue']:raise ValueError('Institutional raw-token mismatch')
        else:raise ValueError('Invalid institutional value')
    if len(ids)!=b['coverage']['valueSlots'] or len(labels)!=b['coverage']['rows'] or numeric!=b['coverage']['numericValues']:raise ValueError('Institutional coverage mismatch')
    return ['data/nscc/records.json','data/nscc/publication-review.json']
