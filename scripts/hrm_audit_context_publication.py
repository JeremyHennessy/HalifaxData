"""Optional annual-report context is separate from the HRM follow-up collection."""
import hashlib,json
from review_receipts import validate_receipt
from hrm_audit_publication import hrm_audit_files,HASH as PARENT_HASH
HASH='76f5e0bc8beabc514c352b51569871b2f108020cbf7de173184c0166e44359a9'
REVIEW_HASH='b71e6b1a61c2b47d7589b0dc4a62e35a5d020d783363909d67f9b27f34296a34'
SOURCE_HASH='f0f22cddff14327f72c5af379172c7ef46a5e90041f16e179b7d1949746a3f4d'
def hrm_audit_context_files(root):
 p=root/'data/hrm-audit-context/context.json';r=root/'data/hrm-audit-context/publication-review.json'
 if not p.exists():return []
 if hashlib.sha256(p.read_bytes()).hexdigest()!=HASH or hashlib.sha256(r.read_bytes()).hexdigest()!=REVIEW_HASH:raise ValueError('Exact independently reviewed annual context bytes required')
 b=json.loads(p.read_text());review=validate_receipt(json.loads(r.read_text()),'audit');pub=b['publication']
 if review['bundleSha256']!=HASH or review['sourceSha256']!=SOURCE_HASH or pub['allowed'] is not True or pub['requiresMatchingIndependentReceipt'] is not True or pub['consequentialAllegation'] is not False or pub['reviewId']!=review['evidenceId'] or pub['reviewedOn']!=review['reviewedOn']:raise ValueError('Annual context review mismatch')
 if not hrm_audit_files(root) or b['parent']['sha256']!=PARENT_HASH:raise ValueError('Annual context parent not verified')
 if b['source']['sha256']!=SOURCE_HASH or b['source']['bytes']!=222532 or b['measure']['resultPercent']!=70 or b['measure']['targetPercent']!=80 or b['measure']['recommendationDenominator'] is not None or b['measure']['statusObservationAsOf'] is not None or b['measure']['currentStatusVerified'] is not False:raise ValueError('Annual context source or measure mismatch')
 return [p.relative_to(root).as_posix(),r.relative_to(root).as_posix()]
