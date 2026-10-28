"""Exact reviewed compensation and optional service projection; no raw captures."""
import hashlib,json
from review_receipts import validate_receipt
HASHES={'compensation':('b50fb2055dc53c46244a8aca3e6d523e76c5599180be0f6322f58c347b618e92','e9c61ef1169254e6666ae7b220d2e55de75cd2477ee64e2a81f107e249d63971'),'service':('dc4226a5232e68a489c9e094676d012499d8cfa5b89706f2ea0d34ffc23dfe12','6656b8643cd601b7dbe9cc2ca71c9b0a1e80e3f94a4a9d45a49871710553f8d8')}
def ambulance_files(root):
 folder=root/'data/ambulance';out=[]
 if not (folder/'compensation.json').exists():return out
 for name,(digest,receipt_digest) in HASHES.items():
  path=folder/(name+'.json');rp=folder/(name+'-review.json')
  if name=='service' and not path.exists():continue
  if hashlib.sha256(path.read_bytes()).hexdigest()!=digest or hashlib.sha256(rp.read_bytes()).hexdigest()!=receipt_digest:raise ValueError('Exact ambulance projection and review required')
  b=json.loads(path.read_text());r=validate_receipt(json.loads(rp.read_text()),'foundation');p=b['publication']
  if r['bundleSha256']!=digest or p['reviewId']!=r['evidenceId'] or p['reviewedOn']!=r['reviewedOn'] or p['allowed'] is not True or p['consequentialAllegation'] is not False:raise ValueError('Ambulance publication mismatch')
  if name=='compensation' and hashlib.sha256((root/'data/audits/records.json').read_bytes()).hexdigest()!=b['followUpSource']['acceptedBundleSha256']:raise ValueError('Exact follow-up required')
  if name=='service' and b['institutionalLink']['acceptedCompensationBundleSha256']!=HASHES['compensation'][0]:raise ValueError('Exact institutional context required')
  out.extend(['data/ambulance/'+name+'.json','data/ambulance/'+name+'-review.json'])
 return out
