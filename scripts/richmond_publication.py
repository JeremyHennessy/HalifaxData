"""Publish only the exact reviewed organization-role projection, never private extracts."""
import hashlib,json
from decimal import Decimal
HASH='90cf613e0e8054e47dab52d29b8a90bfea359745c96bfbe9cfc30e8d488cc4ca'
REVIEW_HASH='7511e32f7a23e444a140de61eeca2c800ffcbf0a6adc50672ed8006e8cdcc16d'
def richmond_files(root):
 p=root/'data/richmond-register/records.json';r=root/'data/richmond-register/publication-review.json'
 if not p.exists():return []
 if hashlib.sha256(p.read_bytes()).hexdigest()!=HASH or hashlib.sha256(r.read_bytes()).hexdigest()!=REVIEW_HASH:raise ValueError('Exact reviewed Richmond bytes required')
 b=json.loads(p.read_text());review=json.loads(r.read_text());pub=b['publication']
 if review['status']!='accepted' or review['bundleSha256']!=HASH or pub['allowed'] is not True or pub['consequentialAllegation'] is not False or pub['reviewId']!=review['evidenceId'] or pub['reviewedOn']!=review['reviewedOn']:raise ValueError('Richmond review mismatch')
 if len(b['records'])!=85 or sum((Decimal(x['reportedAmount']) for x in b['records']),Decimal(0))!=Decimal('482855.06') or b['scope']['geography']!='not_Halifax':raise ValueError('Richmond bounded subset mismatch')
 if any(x['clearanceVerified'] is not False or x['currency'] is not None or x['officialContractId'] is not None or x['decisionId'] is not None for x in b['records']):raise ValueError('Richmond unsupported payment connection')
 return [p.relative_to(root).as_posix(),r.relative_to(root).as_posix()]
