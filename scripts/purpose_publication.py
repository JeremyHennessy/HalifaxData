"""One immutable reviewed annotation; no modification of the authorization dataset."""
import hashlib,json
from review_receipts import validate_receipt
PURPOSE_SHA='79afb0f7c7d12af087f024db289caa6d6a0520c4d7ffc9100fdf5229d301a920'
TARGET_SHA='bca870a30c64807ef881d67d7c8680df748160bcd208b2f05bcdf4fc19f5c6c5'
def purpose_files(root):
    folder=root/'data/authorization-purpose';path=folder/'annotation.json'
    if not path.exists():return []
    review=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'foundation')
    if review['bundleSha256']!=PURPOSE_SHA or hashlib.sha256(path.read_bytes()).hexdigest()!=PURPOSE_SHA:raise ValueError('Purpose annotation exact reviewed bytes required')
    b=json.loads(path.read_text());p=b['publication'];t=b['target'];s=b['provenance']
    if p['allowed'] is not True or p['consequentialAllegation'] is not False or p['reviewId']!=review['evidenceId'] or p['reviewedOn']!=review['reviewedOn']:raise ValueError('Purpose annotation review mismatch')
    target=root/'data/authorizations/records.json'
    if hashlib.sha256(target.read_bytes()).hexdigest()!=TARGET_SHA or t['bundleSha256']!=TARGET_SHA:raise ValueError('Purpose annotation target bytes changed')
    orders=[o for o in json.loads(target.read_text())['orders'] if o['orderNumber']==t['orderNumber']]
    if len(orders)!=1:raise ValueError('Purpose order not uniquely identified')
    o=orders[0];rows=[r for r in o['records'] if r['id']==t['recordId'] and r['clause']==t['clause']]
    if len(rows)!=1 or rows[0]['rawValue']!='420632000' or rows[0]['paymentEvidence'] is not False or any(s[k]!=o[k] for k in ('sourceURL','sourceSha256','pdfURL','pdfSha256')):raise ValueError('Purpose source binding mismatch')
    return ['data/authorization-purpose/annotation.json','data/authorization-purpose/publication-review.json']
