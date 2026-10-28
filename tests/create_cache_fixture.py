"""Write code-isolation fixtures into the test host, never the public artifact."""
import json,pathlib,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from code_bundles import assemble
out=pathlib.Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
 root=pathlib.Path(tmp);(root/'app').mkdir();(root/'app/main.js').write_text("import {marker} from './helper.js';export default marker;");(root/'app/helper.js').write_text("export const marker='old';")
 files=['app/main.js','app/helper.js'];old,_,assets=assemble(root,files)
 (root/'app/helper.js').write_text("export const marker='new';");new,_,newassets=assemble(root,files);assets.update(newassets)
 for name,body in assets.items():path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
 (out/'fixture.json').write_text(json.dumps({'old':f"code/{old['id']}/app/main.js",'new':f"code/{new['id']}/app/main.js"}))
