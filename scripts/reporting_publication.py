"""Admit only the independently accepted neutral reporting question."""
import hashlib,json,re
from decimal import Decimal
from urllib.parse import urlparse
from review_receipts import validate_receipt
SHAPE={'attribution': None, 'confirmedFacts': None, 'consequentialAllegation': None, 'hypotheses': None, 'id': None, 'nextRecords': None, 'notEstablished': None, 'publication': ['allowed', 'consequentialAllegation', 'reason', 'reviewId', 'reviewType', 'reviewedOn'], 'responses': None, 'rule': ['expression', 'id', 'scope'], 'schemaVersion': None, 'sourceLicenceURL': None, 'status': None, 'summary': None, 'title': None}
EVIDENCE=['fiscalYear', 'municipality', 'municipalityType', 'portal', 'profile']
PORTAL=['calculatedBalance', 'currency', 'equationResidual', 'exactAccountingPolicyVerified', 'financingAndTransfers', 'operatingBalance', 'rawSha256', 'reportedAnnualBalance', 'retrievedAt', 'sourceRowId', 'sourceURL', 'unit']
PROFILE=['basis', 'currency', 'label', 'multiplier', 'pdfPage', 'precision', 'printedPage', 'rawSha256', 'rawValue', 'reportedDisplay', 'retrievedAt', 'sourceURL', 'unit']
def reporting_files(root):
    folder=root/'data/reporting-question';path=folder/'case.json'
    if not path.exists():return []
    review=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'reporting')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=review['bundleSha256']:raise ValueError('Reporting question review mismatch')
    b=json.loads(path.read_text())
    if set(b)!=set(SHAPE)|{'evidence'} or b['schemaVersion']!='source-reporting-question-v1' or b['status']!='documented_source_reporting_difference' or b['consequentialAllegation'] is not False:raise ValueError('Unsupported public case')
    for key,keys in SHAPE.items():
        if keys is not None and sorted(b[key])!=keys:raise ValueError('Unexpected nested case fields')
    p=b['publication']
    if p['allowed'] is not True or p['consequentialAllegation'] is not False or p['reviewId']!=review['evidenceId'] or p['reviewType']!='neutral_source_reporting_question' or p['reviewedOn']!=review['reviewedOn']:raise ValueError('Case review does not apply')
    if b['responses']!=[]:raise ValueError('New responses need their own review')
    source=json.loads((root/'data/municipal/records.json').read_text());rows={r['sourceRowId']:r for r in source['records']};seen=set()
    for item in b['evidence']:
        if sorted(item)!=EVIDENCE or sorted(item['portal'])!=PORTAL or sorted(item['profile'])!=PROFILE:raise ValueError('Unexpected case evidence fields')
        v=item['portal'];profile=item['profile'];row=rows.get(v['sourceRowId'])
        if not row or v['sourceRowId'] in seen or (item['municipality'],item['municipalityType'],item['fiscalYear'])!=(row['municipalityLabel'],row['municipalityType'],row['fiscalYearLabel']):raise ValueError('Invalid municipal case identity')
        seen.add(v['sourceRowId'])
        for target,field in [('operatingBalance','operating_surplus_deficit_before_financing_and_transfers'),('financingAndTransfers','total_financing_and_transfers'),('reportedAnnualBalance','annual_surplus_deficit_')]:
            if v[target]!=row['measures'][field]['rawValue']:raise ValueError('Calculation input differs from original observation')
        if Decimal(v['operatingBalance'])+Decimal(v['financingAndTransfers'])!=Decimal(v['calculatedBalance']) or Decimal(v['calculatedBalance'])-Decimal(v['reportedAnnualBalance'])!=Decimal(v['equationResidual']):raise ValueError('Non-reproducible calculation')
        if v['currency'] is not None or profile['currency'] is not None or v['exactAccountingPolicyVerified'] is not False or profile['precision']!='rounded display; exact underlying value not independently obtained':raise ValueError('Unsupported financial meaning')
        for evidence in (v,profile):
            u=urlparse(evidence['sourceURL'])
            if u.scheme!='https' or not u.netloc or u.username or u.password:raise ValueError('Unsafe source URL')
    return ['data/reporting-question/case.json','data/reporting-question/publication-review.json']
