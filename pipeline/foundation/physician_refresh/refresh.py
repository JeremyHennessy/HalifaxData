"""Offline-only candidate preparation. No transport, scheduling or publication code."""
import csv,datetime,hashlib,io,json,pathlib,re
from decimal import Decimal
ROOT=pathlib.Path(__file__).resolve().parent
BASELINE_SHA='637075be4bdcfa7d12171898382db0d58b8f9f28e7f8b3833f146df239347768'
REVIEW_SHA='3f88039e57da939b94f4b810b0ee7887e60b3cd10661e7c6d2063092cbb8d7fc'
CSV_URL='https://data.novascotia.ca/api/views/xpt9-p9is/rows.csv?accessType=DOWNLOAD'
META_URL='https://data.novascotia.ca/api/views/xpt9-p9is.json'
FIELDS=['Year','Payment Type','Payment Type Subcategory','Amount']
API_FIELDS=['year','payment_type','payment_type_subcategory','amount']
MAX_BYTES=1024*1024
class Hold(ValueError):pass

def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,message):
 if not ok:raise Hold(message)
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def load_baseline(root=None):
 p=pathlib.Path(root) if root else ROOT/'baseline';b=(p/'records.json').read_bytes();r=(p/'publication-review.json').read_bytes()
 require(sha(b)==BASELINE_SHA and sha(r)==REVIEW_SHA,'Committed baseline or review drift; do not bootstrap from cache')
 x=json.loads(b);review=json.loads(r)
 require(review['status']=='accepted' and review['bundleSha256']==BASELINE_SHA,'Unreviewed baseline')
 return x

def validate_receipt(body,receipt,url,mime):
 require(type(body) is bytes and 0<len(body)<=MAX_BYTES,'Empty or oversized body')
 require(receipt.get('url')==url and receipt.get('status')==200 and receipt.get('complete') is True and receipt.get('disposition')=='received_for_semantic_review','Failed, incomplete or unexpected source response; hold without retry')
 require(receipt.get('bodyBytes')==len(body) and receipt.get('bodySha256')==sha(body),'Body provenance mismatch')
 require(receipt.get('headers',{}).get('content-type','').split(';',1)[0].strip().lower()==mime,'Unexpected source content type')
 require(receipt.get('headers',{}).get('content-encoding','identity')=='identity','Unexpected encoding')
 times=[datetime.datetime.fromisoformat(receipt[k].replace('Z','+00:00')) for k in ('attemptedAt','headersReceivedAt','completedAt')]
 require(all(t.tzinfo is not None for t in times) and times[0]<=times[1]<=times[2] and (times[2]-times[0]).total_seconds()<=40,'Invalid chronology or bounded-time limit')
 require(not re.search(rb'captcha|access.denied|request rejected|challenge-platform|cf-chl',body,re.I),'Access/challenge body; hold without retry')


def assess(csv_body,metadata_body,csv_receipt,metadata_receipt,baseline_root=None):
 baseline=load_baseline(baseline_root)
 validate_receipt(csv_body,csv_receipt,CSV_URL,'text/csv');validate_receipt(metadata_body,metadata_receipt,META_URL,'application/json')
 metadata=json.loads(metadata_body)
 require(metadata.get('id')=='xpt9-p9is' and metadata.get('provenance')=='official' and metadata.get('licenseId')=='OGL_NOVA_SCOTIA' and metadata.get('publicationStage')=='published' and metadata.get('assetType')=='dataset','Source identity, public stage or licence changed')
 owner=metadata.get('owner',{})
 require(owner.get('id')=='9pyy-md4w' and owner.get('displayName')=='Open Data Nova Scotia' and owner.get('screenName')=='Open Data Nova Scotia','Source owner identity changed')
 columns=metadata.get('columns',[])
 require([c.get('name') for c in columns]==FIELDS and [c.get('fieldName') for c in columns]==API_FIELDS and [c.get('dataTypeName') for c in columns]==['text','text','text','number'],'Schema changed; separate review required')
 old={ (r['reportingYearLabel'],r['paymentType'],r['paymentSubcategory']):r for r in baseline['records']}
 allowed={(k[1],k[2]) for k in old}
 reader=csv.DictReader(io.StringIO(csv_body.decode('utf-8',errors='strict'),newline=''))
 require(reader.fieldnames==FIELDS,'CSV columns changed')
 new={}
 for index,row in enumerate(reader,1):
  require(index<=2000 and set(row)==set(FIELDS) and all(isinstance(row[k],str) for k in FIELDS),'Row cap/schema exceeded')
  key=tuple(row[k] for k in FIELDS[:3]);year=key[0];match=re.fullmatch(r'(20\d{2})-(20\d{2})',year)
  require(match is not None and int(match[2])==int(match[1])+1,'Invalid reporting year')
  require((key[1],key[2]) in allowed,'New category label withheld: semantic/privacy review required before normalization')
  require(key not in new,'Duplicate category-year key; no deduplication')
  amount=row['Amount'];require(len(amount)<=32 and re.fullmatch(r'-?(?:0|[1-9]\d*)\.\d{2}',amount) is not None,'Malformed amount')
  require(abs(Decimal(amount))<=Decimal('10000000000'),'Amount outside reviewed numeric bound')
  new[key]={'key':list(key),'reportedAmount':amount,'sourceRecordNumber':index,'sourceRecordSha256':sha(canonical(row)),'unit':'source_amount_currency_unspecified','currency':None,'accountingBasis':'not_established','additiveStatus':'not_established_do_not_sum'}
 require(new,'Empty population held; not mass deletion')
 added=sorted(set(new)-set(old));removed=sorted(set(old)-set(new));changed=sorted(k for k in set(new)&set(old) if new[k]['reportedAmount']!=old[k]['reportedAmount'])
 return {'schemaVersion':'physician-refresh-candidate-v1','publicationAllowed':False,'status':'unreviewed_candidate','baselineSha256':BASELINE_SHA,'baselineReviewSha256':REVIEW_SHA,'source':{'datasetId':'xpt9-p9is','url':CSV_URL,'metadataUrl':META_URL,'csvSha256':sha(csv_body),'metadataSha256':sha(metadata_body),'csvReceiptSha256':sha(canonical(csv_receipt)),'metadataReceiptSha256':sha(canonical(metadata_receipt)),'receiptHashBasis':'canonical_json_object_not_original_file_bytes','retrievedAt':csv_receipt['completedAt'],'sourceRowsUpdatedAtUnix':metadata.get('rowsUpdatedAt'),'licenceId':'OGL_NOVA_SCOTIA','attribution':'Contains information licensed under the Open Government Licence – Nova Scotia.'},'diff':{'baselineRecords':len(old),'candidateRecords':len(new),'addedKeys':[list(k) for k in added],'removedKeys':[list(k) for k in removed],'changedAmounts':[{'key':list(k),'before':old[k]['reportedAmount'],'after':new[k]['reportedAmount']} for k in changed],'identicalSourceCsv':sha(csv_body)==baseline['source']['sourceBodySha256'],'metadataChanged':sha(metadata_body)!=baseline['source']['metadataBodySha256'],'financialSumComputed':False},'records':[new[k] for k in sorted(new)],'limitations':baseline['limitations']+['Unreviewed refresh candidate only. No accepted application data, source completeness, currency definition or publication status is changed.','New category labels stop normalization rather than exposing potentially sensitive or semantically changed text.','Metadata and CSV responses are not a transactionally atomic snapshot.']}
