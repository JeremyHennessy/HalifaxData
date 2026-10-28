"""Admit separately reviewed grant disclosures without recipient/payment joins."""
import hashlib,json
from review_receipts import validate_receipt
HASHES={'decision':('a259a520a95ff06fc5b765a3a5af17aa66e9f358e2c4df6981764e0cec0d1281','8dd4f8e8c6959c32144133a6a7abbb0518274d4d49339891c0b5c4203b82e4bb'),'paid':('4e2fcac3ab7323a0ff09bd75f9b3435d5ef82c3f9c377be3a7497f60589acea9','2debac715f6237ba3ce6044dc28ce862c9e63e2cf3f388540788b26913b094a0')}
def shelburne_files(root):
 out=[]
 for kind,(digest,receipt_digest) in HASHES.items():
  p=root/f'data/shelburne/{kind}.json';rp=root/f'data/shelburne/{kind}-review.json'
  if not p.exists():continue
  if hashlib.sha256(p.read_bytes()).hexdigest()!=digest or hashlib.sha256(rp.read_bytes()).hexdigest()!=receipt_digest:raise ValueError('Exact reviewed grant projection required')
  b=json.loads(p.read_text());r=json.loads(rp.read_text());pub=b['publication']
  if kind=='paid':validate_receipt(r,'foundation')
  else:
   if set(r)!={'status','bundleSha256','reviewer','reviewedOn','evidenceId','checks','limits'}:raise ValueError('Unexpected grant decision review fields')
   validate_receipt({**{k:v for k,v in r.items() if k!='limits'},'scope':'Source-attributed grant decision reconciliation','limitations':r['limits']},'foundation')
  if r['bundleSha256']!=digest or pub['reviewId']!=r['evidenceId'] or pub['reviewedOn']!=r['reviewedOn'] or pub['allowed'] is not True or pub['consequentialAllegation'] is not False:raise ValueError('Grant publication mismatch')
  out.extend([f'data/shelburne/{kind}.json',f'data/shelburne/{kind}-review.json'])
 return out
