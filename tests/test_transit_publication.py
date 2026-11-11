"""Transit is one optional independently reviewed historical collection, not ingestion."""
import hashlib,json,pathlib,shutil,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from transit_publication import transit_files,HASH,REVIEW_HASH,SOURCE_HASH
from collection_coverage import build_collection_coverage
class TransitGate(unittest.TestCase):
 def test_exact_artifact_and_independent_receipt(self):
  self.assertEqual(transit_files(ROOT),['data/transit/records.json','data/transit/publication-review.json'])
  b=json.loads((ROOT/'data/transit/records.json').read_text());r=json.loads((ROOT/'data/transit/publication-review.json').read_text())
  self.assertEqual(len(b['records']),17);self.assertEqual(b['sourceSha256'],SOURCE_HASH);self.assertEqual(r['bundleSha256'],HASH)
  self.assertEqual(b['reliabilityContext']['currentYearTarget']['gapPercentagePoints'],14)
  self.assertFalse(b['accessContext']['unservedDemandRateEstablished']);self.assertFalse(b['currentStatusVerified'])
 def test_missing_corrupt_and_symlinked_inputs(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder);self.assertEqual(transit_files(root),[])
   dest=root/'data/transit';shutil.copytree(ROOT/'data/transit',dest)
   for name in ['records.json','publication-review.json']:
    path=dest/name;original=path.read_bytes();path.write_bytes(original+b' ')
    with self.assertRaisesRegex(ValueError,'Exact independently'):transit_files(root)
    path.unlink();path.symlink_to(ROOT/'data/transit'/name)
    with self.assertRaisesRegex(ValueError,'artifact and independent receipt'):transit_files(root)
    path.unlink();path.write_bytes(original)
   (dest/'publication-review.json').unlink()
   with self.assertRaises(ValueError):transit_files(root)
 def test_mutually_rehashed_data_and_review_do_not_self_authorize(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder);dest=root/'data/transit';shutil.copytree(ROOT/'data/transit',dest)
   path=dest/'records.json';b=json.loads(path.read_text());b['records'][0]['value']=99;path.write_text(json.dumps(b))
   path=dest/'publication-review.json';r=json.loads(path.read_text());r['bundleSha256']=hashlib.sha256((dest/'records.json').read_bytes()).hexdigest();path.write_text(json.dumps(r))
   with self.assertRaisesRegex(ValueError,'Exact independently'):transit_files(root)
 def test_directory_count_scope_and_absence(self):
  collection=next(c for c in build_collection_coverage(ROOT)['collections'] if c['id']=='transit')
  self.assertEqual(collection['count'],17);self.assertEqual(collection['route'],'#/transit');self.assertEqual(collection['dataSha256'],HASH)
  self.assertEqual(collection['sourceURLs'],['https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/250821tsc1312.pdf'])
  self.assertFalse(collection['completeSourceCoverage']);self.assertFalse(collection['scheduledRefreshConfigured'])
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder);(root/'data').mkdir();shutil.copyfile(ROOT/'data/foundation.json',root/'data/foundation.json');shutil.copyfile(ROOT/'data/publication-review.json',root/'data/publication-review.json')
   self.assertNotIn('transit',[c['id'] for c in build_collection_coverage(root)['collections']])
if __name__=='__main__':unittest.main()
