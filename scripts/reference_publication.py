"""Admit exact reviewed source context only; neither artifact adds a collection."""
import hashlib,json
CONTEXT = {
 'source-references': ('0b51f63c17d60ad1214fa53660a74b67423f4cecdb6b7aa819d81b1b4fa8d47e','35f03ca1aac284128831862f34f7629a4245915e80de543255de0c2e9f03f80a'),
 'procurement-methodology': ('96e6302b93413c98f54c2ea92f82f7a313a74144df5bb5a909f8b41ecae58f4c','688c63710c2b743e25abb367ab0d24f248079f52241273274c5a8a8649c1ea6c')}
TARGET='4118d8b43061fafc195c9b65504f7ef8589edd4cfec93ddc62e9a3126bbce062'
def reference_files(root):
 files=[]
 for folder,(digest,receipt_digest) in CONTEXT.items():
  path=root/'data'/folder/'records.json'
  if not path.exists():continue
  receipt=path.with_name('publication-review.json')
  if hashlib.sha256(path.read_bytes()).hexdigest()!=digest or hashlib.sha256(receipt.read_bytes()).hexdigest()!=receipt_digest:raise ValueError('Source context requires exact reviewed artifact and receipt bytes')
  b=json.loads(path.read_text());r=json.loads(receipt.read_text());p=b['publication']
  if r['status']!='accepted' or r['bundleSha256']!=digest or p['reviewId']!=r['evidenceId'] or p['reviewedOn']!=r['reviewedOn'] or p['allowed'] is not True or p['consequentialAllegation'] is not False:raise ValueError('Source context review mismatch')
  if folder=='procurement-methodology' and (b['target']['tenderIndexSha256']!=TARGET or hashlib.sha256((root/'data/tenders/tender-index.json').read_bytes()).hexdigest()!=TARGET):raise ValueError('Procurement context target mismatch')
  files.extend([f'data/{folder}/records.json',f'data/{folder}/publication-review.json'])
 return files
