"""Admit only independently reviewed HRM status facts, never the source PDF or prose."""
import hashlib,json
from review_receipts import validate_receipt
HASH='f9171cfa466d09389976cb38172b735ea22488ac161db77463b726f1f7c893a4'
REVIEW_HASH='4ed640578877ab4e949ffaf75fc0c67a3db25df7847079f555be091cb27b166f'
SOURCE_HASH='c8ea434d59f1527e6804b11dbff512fb413c72e5c67434a9948b2999b921acb6'
def hrm_audit_files(root):
 p=root/'data/hrm-audits/records.json';r=root/'data/hrm-audits/publication-review.json'
 if not p.exists():return []
 if hashlib.sha256(p.read_bytes()).hexdigest()!=HASH or hashlib.sha256(r.read_bytes()).hexdigest()!=REVIEW_HASH:raise ValueError('Exact independently reviewed HRM bytes required')
 b=json.loads(p.read_text());review=validate_receipt(json.loads(r.read_text()),'audit');pub=b['publication']
 if review['bundleSha256']!=HASH or review['sourceSha256']!=SOURCE_HASH or pub['allowed'] is not True or pub['requiresMatchingIndependentReceipt'] is not True or pub['consequentialAllegation'] is not False or pub['reviewId']!=review['evidenceId'] or pub['reviewedOn']!=review['reviewedOn']:raise ValueError('HRM review mismatch')
 if b['sourceSha256']!=SOURCE_HASH or b['sourceBytes']!=599344 or b['statusObservationAsOf'] is not None or b['reportMonth']!='2026-10' or b['letterDate']!='2026-09-11' or b['summaryGraphicMonth']!='2026-09' or b['assurance']['level']!='limited assurance':raise ValueError('HRM source, date or assurance mismatch')
 if len(b['records'])!=32 or len(b['audits'])!=3 or sum(x['statusAsReported']=='Completed' for x in b['records'])!=14 or any(x['currentStatusVerified'] is not False for x in b['records']):raise ValueError('HRM historical count mismatch')
 return [p.relative_to(root).as_posix(),r.relative_to(root).as_posix()]
