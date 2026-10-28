"""Historical source-attributed status only, never a current allegation."""
import hashlib,json,datetime
from review_receipts import validate_receipt
TOP={'retrievedAt', 'limits', 'reportPublishedOn', 'sourceId', 'schemaVersion', 'limitedAssuranceAsOf', 'records', 'cohorts', 'sourceSha256', 'conclusionDate', 'sourceURL', 'coverage', 'landingURL', 'publication', 'attribution'}
ROW={'assuranceNotCompleted', 'reportedCompleted', 'auditYear', 'pdfPage', 'assuranceCompleted', 'currentStatusVerified', 'basis', 'reportedCompletionPercent', 'reportedNotCompleted', 'completedRecommendationNumbersAsReported', 'reportedTotal', 'organizationAsReported', 'auditTitleAsReported', 'id', 'printedPage'}
COVERAGE={'additional2024SharedRecommendationCount', 'mainReportedCompleted', 'mainRows', 'organizationAuditRows', 'mainReportedTotal', 'mainReportedNotCompleted', 'additional2024Rows'}
PUBLICATION={'reviewType', 'reviewId', 'allowed', 'reason', 'consequentialAllegation', 'reviewedOn'}
def audit_files(root):
    folder=root/'data/audits';path=folder/'records.json'
    if not path.exists():return []
    review=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'audit')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=review['bundleSha256']:raise ValueError('Audit publication bytes changed')
    b=json.loads(path.read_text())
    if set(b)!=TOP or set(b['coverage'])!=COVERAGE or set(b['publication'])!=PUBLICATION or b['schemaVersion']!='audit-followup-status-v1' or b['sourceSha256']!=review['sourceSha256']:raise ValueError('Unexpected audit projection')
    p=b['publication']
    if p['allowed'] is not True or p['consequentialAllegation'] is not False or p['reviewId']!=review['evidenceId'] or p['reviewedOn']!=review['reviewedOn'] or p['reviewType']!='source_attributed_historical_audit_status':raise ValueError('Audit review scope mismatch')
    for key in ('limitedAssuranceAsOf','conclusionDate','reportPublishedOn'):datetime.date.fromisoformat(b[key])
    ids=set()
    for row in b['records']:
        if set(row)!=ROW or row['currentStatusVerified'] is not False or row['id'] in ids:raise ValueError('Unreviewed audit record')
        ids.add(row['id'])
        for key in ('reportedCompleted','reportedNotCompleted','reportedTotal','reportedCompletionPercent','auditYear','pdfPage'):
            if type(row[key]) is not int or row[key]<0:raise ValueError('Invalid audit count')
        if row['reportedCompleted']+row['reportedNotCompleted']!=row['reportedTotal'] or row['reportedCompletionPercent']>100 or row['reportedTotal']==0 or abs(row['reportedCompletionPercent']*row['reportedTotal']-100*row['reportedCompleted'])*2>row['reportedTotal']:raise ValueError('Audit counts do not reconcile')
    main=[r for r in b['records'] if r['auditYear'] in (2021,2022,2023)];additional=[r for r in b['records'] if r['auditYear']==2024];c=b['coverage']
    if len(main)!=c['mainRows'] or len(additional)!=c['additional2024Rows'] or len(ids)!=c['organizationAuditRows'] or c['additional2024SharedRecommendationCount']!=1:raise ValueError('Mixed audit scopes')
    for source,target in [('reportedTotal','mainReportedTotal'),('reportedCompleted','mainReportedCompleted'),('reportedNotCompleted','mainReportedNotCompleted')]:
        if sum(r[source] for r in main)!=c[target]:raise ValueError('Main audit counts changed')
    for cohort in b['cohorts']:
        if set(cohort)!={'auditYear','reportedCompleted','reportedTotal'}:raise ValueError('Unexpected cohort field')
        rows=[r for r in main if r['auditYear']==cohort['auditYear']]
        if sum(r['reportedTotal'] for r in rows)!=cohort['reportedTotal'] or sum(r['reportedCompleted'] for r in rows)!=cohort['reportedCompleted']:raise ValueError('Cohort mismatch')
    return ['data/audits/records.json','data/audits/publication-review.json']
