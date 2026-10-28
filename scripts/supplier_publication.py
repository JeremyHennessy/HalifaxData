"""Validate the exact reviewed supplier extension and same-capture joins."""
import hashlib,json
from review_receipts import validate_receipt
KEYS={'aliasesMerged','attribution','beneficialOwnershipResolved','captureManifestSha256','coverage','descriptionsPublished','legalIdentityVerified','licenceURL','limitations','orderedSourceDigest','recordCount','records','reviewedLabelCount','role','schemaVersion','sourceId','sourceURL'}
def supplier_files(root):
    folder=root/'data/suppliers';path=folder/'labels.json'
    if not path.exists():return []
    receipt=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'supplier')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=receipt['bundleSha256']:raise ValueError('Supplier bundle changed after review')
    bundle=json.loads(path.read_text());tender=json.loads((root/'data/tenders/publication-review.json').read_text())
    if set(bundle)!=KEYS or bundle['schemaVersion']!='reviewed-supplier-labels-v1' or bundle['role']!='supplier_as_reported_by_publisher':raise ValueError('Unreviewed supplier schema')
    for key in ('aliasesMerged','beneficialOwnershipResolved','legalIdentityVerified','descriptionsPublished'):
        if bundle[key] is not False:raise ValueError('Unsupported supplier identity claim')
    for key in ('captureManifestSha256','orderedSourceDigest'):
        if bundle[key]!=receipt[key] or bundle[key]!=tender[key]:raise ValueError('Supplier capture mismatch')
    observations={}
    index=json.loads((root/'data/tenders/tender-index.json').read_text())
    for shard in index['shards']:
        for row in json.loads((root/'data/tenders'/shard['path']).read_text())['records']:observations[row['id']]=row['sourceRowId']
    ids=set();labels=set()
    for record in bundle['records']:
        if set(record)!={'observationId','sourceRowId','supplierLabel'} or not all(isinstance(v,str) and v for v in record.values()):raise ValueError('Invalid supplier association')
        if record['observationId'] in ids or observations.get(record['observationId'])!=record['sourceRowId']:raise ValueError('Unverified supplier link')
        ids.add(record['observationId']);labels.add(record['supplierLabel'])
    if len(ids)!=bundle['recordCount'] or len(labels)!=bundle['reviewedLabelCount']:raise ValueError('Incomplete supplier subset')
    return ['data/suppliers/labels.json','data/suppliers/publication-review.json']
