"""Supplemental authorization evidence with separate fiscal-year totals."""
import hashlib,json,re,datetime
from review_receipts import validate_receipt
KEYS={'top': ['attribution', 'coverage', 'limits', 'orders', 'publication', 'schemaVersion'], 'coverage': ['appropriationClauses', 'orders', 'scheduleCells'], 'publication': ['allowed', 'consequentialAllegation', 'reviewId', 'reviewType', 'reviewedOn'], 'order': ['effectiveDate', 'fiscalYear', 'fiscalYearEnd', 'id', 'orderDate', 'orderNumber', 'pdfRetrievedAt', 'pdfSha256', 'pdfURL', 'recommendationDate', 'records', 'reportedSupplementalTotal', 'retrievedAt', 'sourceOwnedRecordId', 'sourceSha256', 'sourceURL', 'statutoryReferenceAsReported', 'totalReconciles'], 'row': ['appropriatedEntityAsReported', 'clause', 'columnIAsReported', 'currency', 'currencyBasis', 'currencyExplicitlySpecified', 'fiscalYear', 'id', 'measureType', 'multiplier', 'paymentEvidence', 'rawToken', 'rawValue', 'sourceColumn', 'sourceLocator', 'stage', 'unit'], 'columnI': ['meaning', 'rawToken', 'rawValue'], 'locator': ['htmlClause', 'pdfSchedulePage', 'schedule', 'scheduleRowLabel']}
def shape(v,key):
    if not isinstance(v,dict) or sorted(v)!=KEYS[key]:raise ValueError('Unexpected authorization fields')
def authorization_files(root):
    folder=root/'data/authorizations';path=folder/'records.json'
    if not path.exists():return []
    review=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'foundation')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=review['bundleSha256']:raise ValueError('Authorization review hash mismatch')
    b=json.loads(path.read_text());shape(b,'top');shape(b['coverage'],'coverage');shape(b['publication'],'publication');p=b['publication']
    if b['schemaVersion']!='supplemental-appropriations-v1' or p['allowed'] is not True or p['consequentialAllegation'] is not False or p['reviewType']!='source_attributed_supplemental_appropriation_facts' or p['reviewId']!=review['evidenceId'] or p['reviewedOn']!=review['reviewedOn']:raise ValueError('Unreviewed authorization scope')
    ids=set();orders=set()
    for order in b['orders']:
        shape(order,'order')
        if order['id'] in orders or order['id']!='oic-'+order['orderNumber']:raise ValueError('Duplicate or mismatched order')
        orders.add(order['id']);start=int(order['fiscalYear'][:4])
        if not re.fullmatch(r'\d{4}-\d{2}',order['fiscalYear']) or order['fiscalYear']!=f'{start}-{str(start+1)[-2:]}' or order['fiscalYearEnd']!=f'{start+1}-03-31':raise ValueError('Wrong authorization fiscal year')
        for key in ('orderDate','effectiveDate','recommendationDate','fiscalYearEnd'):datetime.date.fromisoformat(order[key])
        total=0;clauses=set()
        for row in order['records']:
            shape(row,'row');shape(row['sourceLocator'],'locator');shape(row['columnIAsReported'],'columnI')
            if row['columnIAsReported']['meaning']!='Source column I; its precise basis is not independently established here.' or row['sourceLocator']['schedule']!='A' or row['sourceLocator']['pdfSchedulePage']!=3 or row['id'] in ids or row['clause'] in clauses or row['id']!=order['id']+'-clause-'+row['clause'] or row['fiscalYear']!=order['fiscalYear'] or row['sourceLocator']['htmlClause']!=row['clause'] or row['sourceLocator']['scheduleRowLabel']!=row['appropriatedEntityAsReported']:raise ValueError('Authorization identity mismatch')
            ids.add(row['id']);clauses.add(row['clause'])
            if row['currency']!='CAD' or row['currencyExplicitlySpecified'] is not False or row['currencyBasis']!='context_inferred_from_official_nova_scotia_appropriation_order' or row['multiplier']!=1 or row['unit']!='source_dollars' or row['paymentEvidence'] is not False or row['stage']!='supplemental_appropriation_authorized' or row['measureType']!='authorization_flow' or row['sourceColumn']!='II':raise ValueError('Authorization is not payment')
            for value in (row,row['columnIAsReported']):
                if not isinstance(value['rawValue'],str) or not re.fullmatch(r'\d+',value['rawValue']) or value['rawToken'].replace(',','')!=value['rawValue']:raise ValueError('Authorization numeric token mismatch')
            total+=int(row['rawValue'])
        if str(total)!=order['reportedSupplementalTotal'] or order['totalReconciles'] is not True:raise ValueError('Separate order total mismatch')
    if len(orders)!=b['coverage']['orders'] or len(ids)!=b['coverage']['appropriationClauses'] or len(ids)*2!=b['coverage']['scheduleCells']:raise ValueError('Authorization coverage mismatch')
    return ['data/authorizations/records.json','data/authorizations/publication-review.json']
