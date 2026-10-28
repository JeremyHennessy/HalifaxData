"""Build an explicit public allowlist. Never recursively copy a research workspace."""
import hashlib,json,pathlib,shutil,os,re,subprocess
from public_schema import validate_public_shape
from tender_publication import tender_files
from supplier_publication import supplier_files
from municipal_publication import municipal_files
from reporting_publication import reporting_files
from audit_publication import audit_files
from housing_publication import housing_files
from ambulance_publication import ambulance_files
from shelburne_publication import shelburne_files
from budget_publication import budget_files
from transfer_publication import transfer_files
from governance_publication import governance_files
from institution_publication import institution_files
from authorization_publication import authorization_files
from cash_publication import cash_files
from purpose_publication import purpose_files
from capital_publication import capital_files
from capital_explanation_publication import capital_explanation_files
from collection_coverage import build_collection_coverage
from code_bundles import assemble,version_html,digest
from review_receipts import validate_receipt
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
FILES=['index.html','app/main.js','app/finder.js','app/model.js','app/tenders.js','app/suppliers.js','app/municipal.js','app/municipal-capital.js','app/capital-explanation.js','app/reporting.js','app/audits.js','app/housing-audit.js','app/ambulance.js','app/shelburne.js','app/budget-tables.js','app/transfers.js','app/governance.js','app/institution.js','app/authorizations.js','app/authorization-trace.js','app/authorization-purpose.js','app/cash-bridge.js','app/coverage.js','data/collection-coverage.json','app/styles.css','data/foundation.json','data/publication-review.json']
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
    review=validate_receipt(json.loads(review_path.read_text()),'foundation')
    assert review['status']=='accepted' and review['evidenceId'] and review['reviewer'] and review['reviewedOn']
    assert review['bundleSha256']==hashlib.sha256((ROOT/'data/foundation.json').read_bytes()).hexdigest(),'Review does not match bundle bytes'
    source_commit=os.environ.get('SOURCE_COMMIT_SHA') or subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert re.fullmatch('[0-9a-f]{40}',source_commit),'Exact source commit required'
    coverage=build_collection_coverage(ROOT)
    (ROOT/'data/collection-coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
    files=FILES+tender_files(ROOT)+supplier_files(ROOT)+municipal_files(ROOT)+reporting_files(ROOT)+audit_files(ROOT)+housing_files(ROOT)+ambulance_files(ROOT)+shelburne_files(ROOT)+budget_files(ROOT)+transfer_files(ROOT)+governance_files(ROOT)+institution_files(ROOT)+authorization_files(ROOT)+cash_files(ROOT)+purpose_files(ROOT)+capital_files(ROOT)+capital_explanation_files(ROOT)
    current_code,code_releases,code_assets=assemble(ROOT,files)
    OUT.mkdir(exist_ok=True)
    known=set(files+list(code_assets)+['release.json','.nojekyll'])
    for path in OUT.rglob('*'):
        if path.is_file() and path.relative_to(OUT).as_posix() not in known:
            relative=path.relative_to(OUT).as_posix()
            if re.fullmatch(r'code/[a-f0-9]{64}/app/[a-z0-9-]+\.(js|css)',relative):path.unlink()
            else:raise RuntimeError('Unexpected file in public output: '+str(path))
    hashes={}
    for name in files:
        source=ROOT/name
        assert source.is_file() and not source.is_symlink(),name
        dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True)
        body=source.read_bytes()
        if name=='index.html':body=version_html(body,current_code['id'])
        dest.write_bytes(body)
        hashes[name]=digest(body)
    for name,body in code_assets.items():
        dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(body);hashes[name]=digest(body)
    (OUT/'.nojekyll').write_text('')
    release={'schemaVersion':1,'release':'fresh-foundation-1','sourceCommitSha':source_commit,'codeReleases':code_releases,'codeRetentionPolicy':'Current plus up to six prior code-only bundles; older tabs can reload. No historical data copies.','evidenceAsOf':bundle['asOf'],'files':hashes,'scope':'Neutral reviewed evidence; not comprehensive government coverage'}
    (OUT/'release.json').write_text(json.dumps(release,indent=2)+'\n')
    print(json.dumps({'publicFiles':len(hashes)+2,'financialFacts':len(bundle['moneyFacts']),'guideReferences':139,'publishedComparisons':len(bundle['investigations']),'reviewedReportingQuestions':int((ROOT/'data/reporting-question/case.json').exists()),'reviewedGovernanceLinks':int((ROOT/'data/governance/case.json').exists())}))
if __name__=='__main__':build()
