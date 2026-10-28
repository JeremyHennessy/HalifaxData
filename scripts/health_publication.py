"""Separate exact public health projections; optional same-source Note21 is not a collection."""
import hashlib,json
PINS={
 'physician-categories/records':('637075be4bdcfa7d12171898382db0d58b8f9f28e7f8b3833f146df239347768','3f88039e57da939b94f4b810b0ee7887e60b3cd10661e7c6d2063092cbb8d7fc','physician-categories/publication-review'),
 'nshealth/records':('9ec619b70614e8696fa920b7c040e269c749f4c0e2029d9b1e8993ae0b7da8ac','b8030aec1948b53cdc5ba2ee778495f432b04fe1d9df9ffc809257af17006b86','nshealth/publication-review'),
 'nshealth/funding-bridge':('948a879fe1dce70cff7aff8c83829d8e23d578a93d6296f49a8c9af75b9a0613','a8f483e9df0ba42b37dded416364fa597dc804930219c74ee04ec80f5ec6f110','nshealth/funding-bridge-review')}
def health_files(root):
 out=[];parent=None
 for name,(sha,receipt_sha,rname) in PINS.items():
  p=root/f'data/{name}.json';rp=root/f'data/{rname}.json'
  if not p.exists():continue
  if hashlib.sha256(p.read_bytes()).hexdigest()!=sha or hashlib.sha256(rp.read_bytes()).hexdigest()!=receipt_sha:raise ValueError('Exact reviewed health artifact/receipt required')
  b=json.loads(p.read_text());r=json.loads(rp.read_text());pub=b['publication']
  if r['status']!='accepted' or r['bundleSha256']!=sha or pub['allowed'] is not True or pub['consequentialAllegation'] is not False or pub['reviewId']!=r['evidenceId'] or pub['reviewedOn']!=r['reviewedOn']:raise ValueError('Health independent review mismatch')
  if name=='physician-categories/records':
   if len(b['records'])!=435 or b['coverage']['financialTotalProvided'] is not False or any(x['currency'] is not None or x['periodStart'] is not None or x['periodEnd'] is not None or x['additiveStatus']!='not_established_do_not_sum' for x in b['records']):raise ValueError('Physician source boundaries required')
  if name=='nshealth/records':
   parent=b
   if len(b['facts'])!=78 or any(f['unit']!='thousands_of_Canadian_dollars' or f['currency']!='CAD' or f['multiplier']!=1000 for f in b['facts']):raise ValueError('NS Health explicit CAD thousands required')
  if name=='nshealth/funding-bridge':
   if parent is None or b['target']['expenseBundleSha256']!=PINS['nshealth/records'][0] or b['target']['expenseBundleId']!=parent['id'] or b['source']['sha256']!=parent['source']['sha256'] or b['legalContext']['applicableLawVersionVerified'] is not False:raise ValueError('Funding context exact parent required')
   facts={f['id']:f for f in b['facts']}
   if facts['nshealth-note21-r7-2026']['value'] is not None or facts['nshealth-note21-r6-2025']['value'] is not None or b['calculations'][0]['sourceReportedValue'] is not None or b['calculations'][1]['calculatedResult'] is not None:raise ValueError('Funding missingness cannot become zero')
  out.extend([p.relative_to(root).as_posix(),rp.relative_to(root).as_posix()])
 return out
