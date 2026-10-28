"""Exact source-number governance link, not expenditure authority."""
import hashlib,json,datetime,re
from review_receipts import validate_receipt
KEYS={'budget': ['departmentAsReported', 'destinationDepartmentAsReported', 'footnote', 'observations', 'paymentEvidence', 'pdfPage', 'presentationChangeDateAsReported', 'printedPage', 'program', 'sourceSha256', 'sourceURL'], 'decision': ['assignedMinisterialPortfolio', 'decisionType', 'effectiveDateAsReported', 'financialAmountAuthorized', 'orderDate', 'orderNumber', 'paymentEvidence', 'program', 'recommendationDateAsReported', 'responsibleInstitutionAsReported', 'retrievedAt', 'sourceOwnedRecordId', 'sourceSha256', 'sourceURL', 'summary'], 'publication': ['allowed', 'consequentialAllegation', 'reason', 'reviewId', 'reviewType', 'reviewedOn'], 'top': ['attribution', 'budget', 'connectionMethod', 'decision', 'explanation', 'id', 'limits', 'nextEvidence', 'publication', 'schemaVersion', 'sharedSourceIdentifier', 'status', 'title'], 'observation': ['fiscalYear', 'multiplier', 'presence', 'rawToken', 'rawValue', 'stage', 'unit']}
def shape(v,key):
    if not isinstance(v,dict) or sorted(v)!=KEYS[key]:raise ValueError('Unexpected governance fields')
def governance_files(root):
    folder=root/'data/governance';path=folder/'case.json'
    if not path.exists():return []
    review=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'foundation')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=review['bundleSha256']:raise ValueError('Governance review mismatch')
    b=json.loads(path.read_text());shape(b,'top')
    for key in ('budget','decision','publication'):shape(b[key],key)
    p=b['publication'];d=b['decision'];budget=b['budget']
    if b['schemaVersion']!='oic-budget-link-v1' or b['status']!='documented_governance_and_presentation_link' or p['allowed'] is not True or p['consequentialAllegation'] is not False or p['reviewType']!='neutral_documented_governance_presentation_link' or p['reviewId']!=review['evidenceId'] or p['reviewedOn']!=review['reviewedOn']:raise ValueError('Unreviewed governance case')
    if b['sharedSourceIdentifier']!=d['orderNumber'] or d['decisionType']!='ministerial_responsibility_assignment' or d['financialAmountAuthorized'] is not None or d['paymentEvidence'] is not False or budget['paymentEvidence'] is not False or budget['program']!=d['program'] or budget['destinationDepartmentAsReported']!=d['assignedMinisterialPortfolio']:raise ValueError('Unsupported decision or payment claim')
    for value in (d['effectiveDateAsReported'],d['orderDate'],d['recommendationDateAsReported'],budget['presentationChangeDateAsReported']):datetime.date.fromisoformat(value)
    columns=[('2025-26','estimate_as_printed','present'),('2025-26','forecast_as_printed','present'),('2026-27','amended_estimate_as_printed','source_dash')]
    if len(budget['observations'])!=len(columns):raise ValueError('Incomplete budget cells')
    for observation,expected in zip(budget['observations'],columns):
        shape(observation,'observation')
        if (observation['fiscalYear'],observation['stage'],observation['presence'])!=expected or observation['unit']!='CAD_thousands' or observation['multiplier']!=1000:raise ValueError('Governance budget column mismatch')
        if observation['presence']=='source_dash':
            if observation['rawValue'] is not None or observation['rawToken']!='--- (A)':raise ValueError('Dash cannot imply zero')
        elif not isinstance(observation['rawValue'],str) or not re.fullmatch(r'\d+',observation['rawValue']) or observation['rawToken'].replace(',','')!=observation['rawValue']:raise ValueError('Budget token mismatch')
    pdf=json.loads((root/'data/budget-tables/records.json').read_text())['sourcePdfSha256']
    if budget['sourceSha256']!=pdf:raise ValueError('Different budget document')
    return ['data/governance/case.json','data/governance/publication-review.json']
