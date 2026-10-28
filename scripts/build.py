"""Build an explicit public allowlist. Never recursively copy a research workspace."""
import hashlib,json,pathlib,shutil,os,re,subprocess
from public_schema import validate_public_shape
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
FILES=['index.html','app/main.js','app/model.js','app/styles.css','data/foundation.json','data/publication-review.json']
def build():
    bundle=json.loads((ROOT/'data/foundation.json').read_text())
    assert bundle['schemaVersion']=='halifaxdata-evidence-v1'
    assert len([s for s in bundle['sources'] if s['inventoryId']])==139
    for record in bundle['investigations']:
        p=record['publication']
        assert p['allowed'] is True and p['consequentialAllegation'] is False
        assert p['reviewType']=='neutral_source_comparison' and p['reviewId'] and p['reviewedOn']
        assert record['status']=='documented_comparison'
    validate_public_shape(bundle)
    review_path=ROOT/'data/publication-review.json'
    if not review_path.is_file():raise RuntimeError('Independent publication review receipt is required.')
    review=json.loads(review_path.read_text())
    assert review['status']=='accepted' and review['evidenceId'] and review['reviewer'] and review['reviewedOn']
    assert review['bundleSha256']==hashlib.sha256((ROOT/'data/foundation.json').read_bytes()).hexdigest(),'Review does not match bundle bytes'
    source_commit=os.environ.get('SOURCE_COMMIT_SHA') or subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert re.fullmatch('[0-9a-f]{40}',source_commit),'Exact source commit required'
    OUT.mkdir(exist_ok=True)
    known=set(FILES+['release.json','.nojekyll'])
    for path in OUT.rglob('*'):
        if path.is_file() and path.relative_to(OUT).as_posix() not in known:
            raise RuntimeError('Unexpected file in public output: '+str(path))
    hashes={}
    for name in FILES:
        source=ROOT/name
        assert source.is_file() and not source.is_symlink(),name
        dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,dest)
        hashes[name]=hashlib.sha256(dest.read_bytes()).hexdigest()
    (OUT/'.nojekyll').write_text('')
    release={'schemaVersion':1,'release':'fresh-foundation-1','sourceCommitSha':source_commit,'evidenceAsOf':bundle['asOf'],'files':hashes,'scope':'Neutral reviewed evidence; not comprehensive government coverage'}
    (OUT/'release.json').write_text(json.dumps(release,indent=2)+'\n')
    print(json.dumps({'publicFiles':len(FILES)+2,'financialFacts':len(bundle['moneyFacts']),'guideReferences':139,'publishedComparisons':len(bundle['investigations'])}))
if __name__=='__main__':build()
