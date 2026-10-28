"""Admission for one independently reviewed, minimum-field tender snapshot."""
import hashlib,json,re,datetime
from review_receipts import validate_receipt
ROW_KEYS={'id','sourceRowId','tenderId','publisherEntityLabel','dateFields','reportedAmount','categories'}
def tender_files(root):
    folder=root/'data/tenders';index_path=folder/'tender-index.json'
    if not index_path.exists():return []
    index=json.loads(index_path.read_text());receipt=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'tender')
    if receipt.get('status')!='accepted' or not receipt.get('reviewer') or not receipt.get('evidenceId'):raise ValueError('Tender publication not accepted')
    if receipt['indexSha256']!=hashlib.sha256(index_path.read_bytes()).hexdigest():raise ValueError('Tender index changed after review')
    if index['schemaVersion']!='tender-minimum-index-v1' or index['amountSemantics']['currency'] is not None or index['amountSemantics']['aggregationAllowed'] is not False or index['amountSemantics']['paymentEvidence'] is not False:raise ValueError('Unsupported amount semantics')
    if receipt['fieldNames']!=index['fieldNames']:raise ValueError('Review field scope does not match index')
    if set(index['fieldNames'])!=ROW_KEYS:raise ValueError('Unreviewed public fields')
    files=['data/tenders/tender-index.json','data/tenders/publication-review.json'];ids=set();paths=set();count=0
    for shard in index['shards']:
        name=shard['path']
        if not re.fullmatch(r'tenders-\d{3}\.json',name) or name in paths:raise ValueError('Unsafe or duplicate shard path')
        paths.add(name);path=folder/name
        if path.is_symlink() or not path.is_file():raise ValueError('Missing or linked shard')
        body=path.read_bytes()
        if len(body)!=shard['bytes'] or hashlib.sha256(body).hexdigest()!=shard['sha256']:raise ValueError('Shard no longer matches accepted index')
        payload=json.loads(body)
        if set(payload)!={'schemaVersion','records'} or payload['schemaVersion']!='tender-minimum-v1' or len(payload['records'])!=shard['records']:raise ValueError('Wrong public shard shape')
        for row in payload['records']:
            if set(row)!=ROW_KEYS or set(row['categories'])!={'construction','goods','service'} or set(row['dateFields'])!={'awarded_date','tender_close_date','tender_start_date'}:raise ValueError('Unexpected public fields')
            for key in ('id','sourceRowId','tenderId','publisherEntityLabel'):
                if not isinstance(row[key],str) or not row[key]:raise ValueError('Invalid source identity/label')
            if any(v not in ('Y','N') for v in row['categories'].values()):raise ValueError('Invalid source category')
            for value in row['dateFields'].values():
                if value is not None:
                    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('Invalid source calendar date')
                    datetime.date.fromisoformat(value)
            if row['reportedAmount'] is not None and (not isinstance(row['reportedAmount'],str) or not re.fullmatch(r'-?\d+(\.\d+)?',row['reportedAmount'])):raise ValueError('Invalid original monetary string')
            if row['id'] in ids:raise ValueError('Duplicate observation')
            ids.add(row['id']);count+=1
        files.append('data/tenders/'+name)
    if count!=index['recordCount']:raise ValueError('Incomplete public population')
    return files
