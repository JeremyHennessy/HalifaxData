"""Admit only the independently accepted historical capital projection, unchanged."""
import hashlib,json
from review_receipts import validate_receipt
CAPITAL_SHA='4136b3b3cd3f48c8d6ebf044f5657f5a8825169b6af9983461ff044e8189109f'
def capital_files(root):
    folder=root/'data/municipal-capital';path=folder/'records.json'
    if not path.exists():return []
    review=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'foundation')
    if review['bundleSha256']!=CAPITAL_SHA or hashlib.sha256(path.read_bytes()).hexdigest()!=CAPITAL_SHA:raise ValueError('Capital snapshot exact accepted bytes required')
    b=json.loads(path.read_text());p=b['publication']
    if b['schemaVersion']!='municipal-capital-assets-v1' or p['allowed'] is not True or p['consequentialAllegation'] is not False or p['reviewId']!=review['evidenceId'] or p['reviewedOn']!=review['reviewedOn']:raise ValueError('Capital publication scope mismatch')
    return ['data/municipal-capital/records.json','data/municipal-capital/publication-review.json']
