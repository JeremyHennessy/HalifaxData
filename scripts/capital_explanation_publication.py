"""An optional reviewed explanation, not another dataset or source count."""
import hashlib,json
from review_receipts import validate_receipt
from capital_publication import CAPITAL_SHA
EXPLANATION_SHA='6e723fc4cef52be5d24c3245bf3cf58aaf2819cfc69237daae469d4c8738777c'
def capital_explanation_files(root):
    folder=root/'data/capital-explanation';path=folder/'annotation.json'
    if not path.exists():return []
    if hashlib.sha256((folder/'publication-review.json').read_bytes()).hexdigest()!='934ff3a57d42ccf83c02232c599e4561feaf60246762501de7321ad02a3c74b5':raise ValueError('Exact independent explanation receipt required')
    review=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'foundation')
    if review['bundleSha256']!=EXPLANATION_SHA or hashlib.sha256(path.read_bytes()).hexdigest()!=EXPLANATION_SHA:raise ValueError('Exact reviewed capital explanation required')
    capital=root/'data/municipal-capital/records.json'
    if hashlib.sha256(capital.read_bytes()).hexdigest()!=CAPITAL_SHA:raise ValueError('Capital target snapshot mismatch')
    b=json.loads(path.read_text());p=b['publication']
    if not p['allowed'] or p['consequentialAllegation'] or p['reviewId']!=review['evidenceId'] or p['reviewedOn']!=review['reviewedOn']:raise ValueError('Explanation review mismatch')
    return ['data/capital-explanation/annotation.json','data/capital-explanation/publication-review.json']
