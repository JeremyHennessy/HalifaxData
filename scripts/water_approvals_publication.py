"""Independent optional approvals; parent records and collection counts stay unchanged."""
import hashlib,json
from water_publication import HASHES
CONTEXTS={'cowie':('034bf64dafc13d6243b02f8d3a67f0739f82912b426ec2387b4039ef161adcbc','f8a85c3a6df29f96790943c804df07a04c8e598146d7d7d1850a72115f60c0ba','300002718',['M09997','M10305'],'Apr 8/21 & Nov 24/21'),'akerley':('58bdbf5f4dd51874cc4dd6b18764207af5149b83d3ab6dca2336588b859db91b','912c0189304ddf10a294d3266cf65f4cbb6493c4ba1fc7029f40d406f497ecd7','300003356',['M10446'],'Mar 4/22')}
def water_approval_files(root):
 out=[]
 for name,(sha,receipt_sha,number,matters,dates) in CONTEXTS.items():
  path=root/f'data/water-approvals/{name}.json';rp=root/f'data/water-approvals/{name}-review.json'
  if not path.exists():continue
  parent=root/'data/water-projects/records.json'
  if not parent.exists() or hashlib.sha256(parent.read_bytes()).hexdigest()!=HASHES['records'][0]:raise ValueError('Additional approval needs exact project report')
  if hashlib.sha256(path.read_bytes()).hexdigest()!=sha or hashlib.sha256(rp.read_bytes()).hexdigest()!=receipt_sha:raise ValueError('Additional approval needs exact artifact and receipt')
  b=json.loads(path.read_text());r=json.loads(rp.read_text());p=b['publication'];i=b['integration'];report=json.loads(parent.read_text())
  if r['status']!='accepted' or r['bundleSha256']!=sha or p['allowed'] is not True or p['consequentialAllegation'] is not False or p['reviewId']!=r['evidenceId'] or p['reviewedOn']!=r['reviewedOn']:raise ValueError('Additional approval review mismatch')
  if i['parentBundleSha256']!=HASHES['records'][0] or i['parentCollectionId']!=report['id'] or any(i[k] is not False for k in ['addsCollectionCount','addsProjectCount','addsMatterReferenceCount']):raise ValueError('Additional approval parent/count mismatch')
  rows=[r for r in report['records'] if r['id']==i['parentRecordId']]
  if len(rows)!=1 or rows[0]['projectNumberAsReported']!=number or rows[0]['regulatoryMatterIdsAsReported']!=matters or rows[0]['regulatoryApprovalDateTextAsReported']!=dates:raise ValueError('Additional approval exact row mismatch')
  out.extend([path.relative_to(root).as_posix(),rp.relative_to(root).as_posix()])
 return out
