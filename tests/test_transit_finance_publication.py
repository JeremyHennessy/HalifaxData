"""Optional finance context cannot substitute for accepted service evidence or self-authorize."""
import hashlib,json,pathlib,shutil,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from transit_finance_publication import transit_finance_files,HASH,REVIEW_HASH
from transit_publication import transit_files
from collection_coverage import build_collection_coverage
class TransitFinanceGate(unittest.TestCase):
 def copy(self,root):
  for folder in ['transit','transit-finance']:shutil.copytree(ROOT/'data'/folder,root/'data'/folder)
 def test_exact_independent_receipt_and_parent(self):
  self.assertEqual(transit_finance_files(ROOT),['data/transit-finance/context.json','data/transit-finance/publication-review.json'])
  b=json.loads((ROOT/'data/transit-finance/context.json').read_text());self.assertEqual(b['reconciliation']['componentSumMinusReportedTotal'],1)
  self.assertEqual(hashlib.sha256((ROOT/'data/transit-finance/publication-review.json').read_bytes()).hexdigest(),REVIEW_HASH)
  self.assertEqual(b['parentSha256'],hashlib.sha256((ROOT/'data/transit/records.json').read_bytes()).hexdigest())
 def test_missing_corrupt_and_symlinked_finance_inputs(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder);self.assertEqual(transit_finance_files(root),[]);self.copy(root)
   for name in ['context.json','publication-review.json']:
    path=root/'data/transit-finance'/name;original=path.read_bytes();path.write_bytes(original+b' ')
    with self.assertRaisesRegex(ValueError,'Exact independently'):transit_finance_files(root)
    path.unlink();path.symlink_to(ROOT/'data/transit-finance'/name)
    with self.assertRaisesRegex(ValueError,'artifact and independent receipt'):transit_finance_files(root)
    path.unlink()
    with self.assertRaises(ValueError):transit_finance_files(root)
    path.write_bytes(original)
 def test_parent_missing_or_modified_blocks_context(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder);self.copy(root)
   for name in ['records.json','publication-review.json']:
    path=root/'data/transit'/name;original=path.read_bytes();path.write_bytes(original+b' ')
    with self.assertRaises(ValueError):transit_finance_files(root)
    path.unlink()
    with self.assertRaises(ValueError):transit_finance_files(root)
    path.write_bytes(original)
 def test_mutually_rehashed_candidate_and_receipt_do_not_self_authorize(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder);self.copy(root);path=root/'data/transit-finance/context.json';b=json.loads(path.read_text());b['revenueRecords'][0]['actual']+=1;path.write_text(json.dumps(b))
   path=root/'data/transit-finance/publication-review.json';r=json.loads(path.read_text());r['bundleSha256']=hashlib.sha256((root/'data/transit-finance/context.json').read_bytes()).hexdigest();path.write_text(json.dumps(r))
   with self.assertRaisesRegex(ValueError,'Exact independently'):transit_finance_files(root)
 def test_context_is_not_a_new_collection_and_cannot_change_parent(self):
  before=(ROOT/'data/transit/records.json').read_bytes();coverage=build_collection_coverage(ROOT)
  self.assertEqual(len(coverage['collections']),26);self.assertEqual(next(c for c in coverage['collections'] if c['id']=='transit')['count'],17)
  self.assertNotIn('transit-finance',[c['id'] for c in coverage['collections']]);self.assertEqual((ROOT/'data/transit/records.json').read_bytes(),before)
  self.assertEqual(len(transit_files(ROOT)),2)
 def test_build_allowlist_admits_only_two_financial_files(self):
  import build
  self.assertIn('app/transit-finance.js',build.FILES);self.assertEqual(len(transit_finance_files(ROOT)),2)
if __name__=='__main__':unittest.main()
