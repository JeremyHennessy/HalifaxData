import importlib.util,json,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from code_bundles import assemble,bundle_id,digest,validate_release,version_html
from retain_code import retain,BASE,NoRetentionRedirects
class CodeBundles(unittest.TestCase):
 def setup_root(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=pathlib.Path(temp.name);(root/'app').mkdir();(root/'app/main.js').write_text("import {marker} from './model.js';export default marker;");(root/'app/model.js').write_text("export const marker='old';");(root/'app/styles.css').write_text('body{color:navy}');return root
 def test_new_dependencies_change_complete_bundle_identity_and_old_import_paths_stay_isolated(self):
  root=self.setup_root();files=['app/main.js','app/model.js','app/styles.css'];old,_,assets=assemble(root,files);folder=root/'retained-code';folder.mkdir();(folder/'manifest.json').write_text(json.dumps([old]));
  for name,body in assets.items():target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
  (root/'app/model.js').write_text("export const marker='new';");new,releases,combined=assemble(root,files)
  self.assertNotEqual(old['id'],new['id']);self.assertEqual(len(releases),2)
  self.assertIn(b"marker='old'",combined[f"code/{old['id']}/app/model.js"]);self.assertIn(b"marker='new'",combined[f"code/{new['id']}/app/model.js"])
  self.assertIn(b"'./model.js'",combined[f"code/{old['id']}/app/main.js"])
 def test_entry_uses_relative_bundle_paths_and_reload_failure_state(self):
  root=self.setup_root();entry,_,_=assemble(root,['app/main.js','app/model.js','app/styles.css']);html=version_html((ROOT/'index.html').read_bytes(),entry['id']).decode()
  self.assertIn(f'./code/{entry["id"]}/app/main.js',html);self.assertIn(f'href="code/{entry["id"]}/app/styles.css"',html);self.assertIn('Reload latest app',html);self.assertNotIn('src="app/main.js"',html)
 def test_retention_downloads_only_verified_code_and_rejects_data_or_wrong_hash(self):
  root=self.setup_root();entry,_,assets=assemble(root,['app/main.js','app/model.js','app/styles.css']);release={'codeReleases':[entry],'files':{p:digest(v) for p,v in assets.items()}};calls=[]
  def fetch(url,limit):
   calls.append(url);return json.dumps(release).encode() if url.split('?')[0].endswith('release.json') else assets[url.removeprefix(BASE)]
  self.assertEqual(retain(root,fetch),1);self.assertTrue(all('/data/' not in u for u in calls))
  release['files'][next(iter(assets))]='0'*64
  with self.assertRaises(ValueError):retain(root,fetch)
  with self.assertRaises(ValueError):validate_release({'id':'a'*64,'files':{'data/private.json':'a'*64}})
 def test_retention_is_bounded_to_current_plus_six_prior_code_versions(self):
  root=self.setup_root();files=['app/main.js','app/model.js','app/styles.css'];folder=root/'retained-code';folder.mkdir();entries=[]
  for n in range(7):
   (root/'app/model.js').write_text(f'export const marker={n};');entry,_,assets=assemble(root,files);entries.append(entry)
   for name,body in assets.items():path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
  (folder/'manifest.json').write_text(json.dumps(entries));(root/'app/model.js').write_text("export const marker='current';");current,releases,assets=assemble(root,files)
  self.assertEqual(len(releases),7);self.assertEqual(releases[0]['id'],current['id']);self.assertNotIn(entries[-1]['id'],[r['id'] for r in releases]);self.assertTrue(all('/data/' not in p for p in assets))
 def test_unbundled_dependency_rejected(self):
  root=self.setup_root();(root/'app/main.js').write_text("import {secret} from '../outside.js';")
  with self.assertRaises(ValueError):assemble(root,['app/main.js','app/model.js','app/styles.css'])

 def test_retention_redirect_is_rejected_before_dispatch(self):
  handler=NoRetentionRedirects()
  for url in ['https://example.com/unrelated',BASE+'another-path']:
   with self.assertRaisesRegex(ValueError,'redirects are not allowed'):handler.redirect_request(None,None,302,'Found',{},url)
