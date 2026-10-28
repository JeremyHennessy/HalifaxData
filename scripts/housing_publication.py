"""Admit the exact independently reviewed institutional audit progression."""
import hashlib,json
from review_receipts import validate_receipt
HOUSING_SHA='55164a83769afa426568901932d863ccad8b16d87ebc988e3199ee6bf11e6a2e'
REVIEW_SHA='0fa3c28eba1ebfde07d8a9b047f5cdd48b65a0aaec28c232f846a46cfe2148e1'
def housing_files(root):
 folder=root/'data/housing-audit';path=folder/'progression.json'
 if not path.exists():return []
 if hashlib.sha256(path.read_bytes()).hexdigest()!=HOUSING_SHA or hashlib.sha256((folder/'publication-review.json').read_bytes()).hexdigest()!=REVIEW_SHA:raise ValueError('Exact housing audit release and receipt required')
 review=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'foundation');b=json.loads(path.read_text());p=b['publication']
 if review['bundleSha256']!=HOUSING_SHA or p['reviewId']!=review['evidenceId'] or p['reviewedOn']!=review['reviewedOn'] or p['allowed'] is not True or p['consequentialAllegation'] is not False:raise ValueError('Housing publication mismatch')
 if hashlib.sha256((root/'data/audits/records.json').read_bytes()).hexdigest()!=b['followUpSource']['acceptedBundleSha256']:raise ValueError('Follow-up source must match accepted linkage')
 return ['data/housing-audit/progression.json','data/housing-audit/publication-review.json']
