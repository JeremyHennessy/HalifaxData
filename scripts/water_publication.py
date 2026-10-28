"""Allow only exact public project facts and an optional, exact-parent-bound decision."""
import hashlib,json
HASHES={'records':('57eac399c2d4438ef38089422730852c5e244502680d1a645e21317aa10f17cb','263cbf59aaae8d65d5f0cc3bc52e84ed9ec76783f6ebbabf58e9fa13510ee2c6'),'m10687-v1':('d58bbf98772baa5b3ba9400d08c6799d1fe2565b27234c1c12f0ff23329d3a78','7186aaf06bb04e6e407b5ecc915f05f38bd255557a3bb737f02cc66d96f8b8b7')}
HASHES['m10687']=('f2c81193e22ebb8a0da58ebf0ed0ce4faa2cdd6b04943212f4bcbf2df4a6c2d8','230d305dd10cc8ce6f052e1f75d645d57440297ecedd223fd654eadd93f0bdd4')
def water_files(root):
 folder=root/'data/water-projects';out=[];parent=None
 for name,(sha,receipt_sha) in HASHES.items():
  p=folder/(name+'.json');receipt=folder/('publication-review.json' if name=='records' else name+'-review.json')
  if not p.exists():continue
  if hashlib.sha256(p.read_bytes()).hexdigest()!=sha or hashlib.sha256(receipt.read_bytes()).hexdigest()!=receipt_sha:raise ValueError('Water exact reviewed bytes required')
  b=json.loads(p.read_text());r=json.loads(receipt.read_text());pub=b['publication']
  if r['status']!='accepted' or r['bundleSha256']!=sha or pub['allowed'] is not True or pub['consequentialAllegation'] is not False or pub['reviewId']!=r['evidenceId'] or pub['reviewedOn']!=r['reviewedOn']:raise ValueError('Water review mismatch')
  if name=='records':parent=b
  else:
   i=b['integration']
   if parent is None or i['parentBundleSha256']!=HASHES['records'][0] or i['parentCollectionId']!=parent['id'] or i['addsCollectionCount'] is not False or i['addsProjectCount'] is not False or i['addsMatterReferenceCount'] is not False:raise ValueError('Water context requires exact parent')
   records=[r for r in parent['records'] if r['id']==i['parentRecordId']]
   if len(records)!=1 or records[0]['projectNumberAsReported']!='300003121' or records[0]['regulatoryMatterIdsAsReported']!=['M10687'] or records[0]['regulatoryApprovalDateTextAsReported']!='Aug 22/22':raise ValueError('Water context exact record mismatch')
  if name=='m10687':
   prior=folder/'m10687-v1.json'
   if not prior.exists() or hashlib.sha256(prior.read_bytes()).hexdigest()!=HASHES['m10687-v1'][0] or b['versionHistory']['supersedesSha256']!=HASHES['m10687-v1'][0]:raise ValueError('Water clarification requires preserved original context')
  out.extend([p.relative_to(root).as_posix(),receipt.relative_to(root).as_posix()])
 return out
