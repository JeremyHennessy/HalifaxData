"""Fresh, offline evidence projection. No network and no legacy application imports."""
import argparse, hashlib, json, re
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parent
SCHEMA = 'halifaxdata-evidence-v1'

def load(path):
    return json.loads(Path(path).read_text(), parse_float=Decimal)

def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'

def require_url(url):
    if not isinstance(url,str) or not re.fullmatch(r'https://[^\s<>"\\]+',url):
        raise ValueError('Unsafe source URL')
    return url

def finite_decimal(value):
    if not isinstance(value,str):raise ValueError('Decimal value must be a string')
    try: result=Decimal(value)
    except Exception:raise ValueError('Invalid decimal')
    if not result.is_finite():raise ValueError('Non-finite decimal')
    return result

def compare(a,b):
    for key in ('metric','currency','unit','multiplier','accountingBasis','reportingPerimeter','measureType','entity'):
        if a.get(key) != b.get(key) or a.get(key) is None:
            raise ValueError('Incompatible financial dimension: '+key)
    if a['period'] != b['period'] or a['measureType'] != 'flow':
        raise ValueError('Incompatible period or non-flow')
    if a['rawValue'] is None or b['rawValue'] is None:
        raise ValueError('Missing is not zero')
    if a['unit'] not in ('CAD_thousands','CAD_millions') or type(a['multiplier']) is not int or a['multiplier'] != {'CAD_thousands':1000,'CAD_millions':1000000}[a['unit']]:raise ValueError('Unknown unit or multiplier')
    return str(finite_decimal(b['rawValue'])-finite_decimal(a['rawValue']))

def publish_case(case):
    p=case.get('publication',{})
    if case.get('status') != 'documented_comparison' or case.get('classification')!='calculated_source_comparison' or not p.get('reviewId') or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',p.get('reviewedOn','')) or not case.get('evidenceIds') or not case.get('moneyFactIds') or p.get('allowed') is not True or p.get('consequentialAllegation') is not False or p.get('reviewType')!='neutral_source_comparison':
        raise ValueError('Case has no public clearance')
    return case

def build(seed):
    sources=[]
    for i,row in enumerate(seed['inventory'],1):
        v=row['values']; sid=f'guide-{i:03}'
        if len(v)!=12: raise ValueError('Workbook schema drift')
        sources.append(dict(id=sid,inventoryId=f'SI{i:03}',inventoryRow=row['row'],title=v[2],url=require_url(v[3]),publisher=None,group=v[0],jurisdiction=v[1],geography=v[6],priority=v[8],format=v[4],status=dict(registered=True,acquired=False,normalized=False,published=False,monitored=False),limitations=[v[9],'Research inventory entry, not a working integration.'],investigationUse=v[5],accessClass=v[7],suggestedCadence=v[11],provenance=dict(type='reference_inventory',workbookSha256=seed['workbookSha256'],originalVerificationClaim=v[10],claimIndependentlyRechecked=False)))
    if len(sources)!=139:raise ValueError('139 guide entries required')
    # Corrections retain original reference title and make ambiguity explicit.
    for s in sources:
        if s['inventoryId']=='SI049':s['limitations'].append('Reference title is ambiguous: this source is not verified as provincial MLA electoral boundaries.')
        if s['inventoryId']=='SI011':s['limitations'].append('The official dataset is titled Operating Fund Total Revenues and Expenditures by Municipality; its metadata also lists service-category fields. Definitions and category changes require validation before comparisons.')
        if s['url']=='https://www.novascotia.ca/public-accounts':s['limitations'].append('Exact index has an unresolved access hold; no retry or full-volume ingestion claimed.')
    docs={}
    for d in seed['documents']:
        if d['originalResearchId'] in docs or any(x['id']==d['id'] for x in sources):raise ValueError('Duplicate source ID')
        doc=dict(d); doc['url']=require_url(doc['url']); docs[doc['originalResearchId']]=doc
        sources.append(dict(id=doc['id'],title=doc['title'],url=doc['url'],publisher=doc['publisher'],inventoryId=None,inventoryRow=None,group='Primary fiscal documents',jurisdiction='Nova Scotia',geography='Province',priority='P0',format='Primary document table',status=dict(registered=True,acquired=False,normalized=True,published=True,monitored=False),limitations=['Bounded independent primary-text review; source binary not retained.','Not a full automated importer.',doc['accessNote']],provenance=dict(type='independent_primary_research',reviewedOn='2026-10-28',sourceSnapshotHash=None)))
    facts=[]; evidence=[]; seen_facts=set()
    for n,v in enumerate(seed['verifiedFacts'],1):
        if v['status']!='independently_verified_primary_text':raise ValueError('Unverified value')
        rid=v['candidate_id']
        if rid in seen_facts:raise ValueError('Duplicate research fact')
        seen_facts.add(rid)
        if v['source_id'] not in docs:raise ValueError('Missing source')
        if v['unit'] not in ('CAD_thousands','CAD_millions'):raise ValueError('Unknown unit')
        finite_decimal(str(v['verified_value']))
        doc=docs[v['source_id']]
        year='2026-27' if '2026-27' in rid else '2025-26'
        match=re.match(r'(.+?)-(202[56]-2[67])-(.+)',rid)
        if not match:raise ValueError('Unexpected research observation')
        raw_stage,_,metric=match.groups()
        stage={'original':'original_estimate','amended':'amended_estimate','capital':'capital_plan','actual':'audited_actual'}.get(raw_stage,raw_stage)
        if stage not in ('original_estimate','amended_estimate','capital_plan','adjusted_estimate','audited_actual'):raise ValueError('Unknown stage')
        stock=metric=='net-debt'; metric=metric.replace('-','_')
        fiscal=int(year[:4]); eid=f'evidence-{n:03}'; fid=f'finance-{n:03}'
        evidence.append(dict(id=eid,sourceId=doc['id'],title=doc['title']+' — '+metric.replace('_',' '),url=doc['url'],sourceLocator=v['source_locator'],reviewedOn='2026-10-28',verification='independently_reviewed_primary_text',sourceSnapshotHash=None,limitations=['No retained source binary/hash or visual PDF verification.','Source observations are not payment records.']))
        basis='consolidated_statement_accrual' if year=='2025-26' else ('capital_funding_plan' if stage=='capital_plan' else 'budget_estimates_including_non_cash_expenses')
        perimeter='government_reporting_entity' if year=='2025-26' else ('capital_plan_program' if stage=='capital_plan' else 'general_revenue_fund_with_separate_consolidation_adjustment')
        facts.append(dict(id=fid,title=metric.replace('_',' ').capitalize(),entity='Province of Nova Scotia',jurisdiction='CA-NS',metric=metric,period=dict(start=f'{fiscal}-04-01',end=f'{fiscal+1}-03-31',label=year,asOf=f'{fiscal+1}-03-31' if stock else None),stage=stage,accountingBasis=basis,reportingPerimeter=perimeter,measureType='stock' if stock else 'flow',rawValue=str(v['verified_value']),unit=v['unit'],currency='CAD',multiplier=1000000 if v['unit']=='CAD_millions' else 1000,evidenceId=eid,sourceId=doc['id'],sourceLocator=v['source_locator'],interpretation='Not an invoice, payment or final project cost. '+('Stock at period end; do not add to annual flows.' if stock else 'Compare only compatible metric, fiscal period and reporting perimeter.')))
    if len(facts)!=29:raise ValueError('Expected 29 independently reviewed numbers')
    idx={(f['stage'],f['metric']):f for f in facts}
    a=idx['original_estimate','departmental_expenses']; b=idx['amended_estimate','departmental_expenses']; diff=compare(a,b)
    if diff!='53592':raise ValueError('Budget revision changed')
    case=dict(id='budget-revision-2026-27',title='What changed between the original budget and its addendum?',question='How did the reported spending plan change, and can those plans be followed through to payments and delivery?',status='documented_comparison',classification='calculated_source_comparison',publication=dict(allowed=True,reviewType='neutral_source_comparison',reviewedOn='2026-10-28',reviewId='primary-text-review-20261028-budget-rows',consequentialAllegation=False),summary='The 2026–27 addendum increased planned departmental expenses by CAD 53.592 million. This is a change to estimates, not evidence of money paid, waste or wrongdoing.',whyFlagged='An explicit comparison of the same fiscal-year departmental-expense row in two separately identified budget versions.',calculation=dict(operation='second_minus_first',inputIds=[a['id'],b['id']],resultRaw=diff,unit=a['unit'],multiplier=a['multiplier']),moneyFactIds=[a['id'],b['id']],evidenceIds=[a['evidenceId'],b['evidenceId']],confirmedFacts=['Both inputs are estimates for fiscal 2026–27 in the same budget presentation.','17,823,982 minus 17,770,390 equals 53,592 in CAD thousands.','The reported plan changed; this does not establish actual expenditure.'],alternativeExplanations=['The addendum attributes the announced CAD 53.6 million increase to restored support for disability, senior and education programs (printed page 1).','A budget addendum is a documented revision, not by itself an unexplained overrun.'],missingEvidence=['No linked appropriation or legislative-vote record has been validated in this workflow.','No contract, invoice, cash payment or delivered outcome is joined to this change.','The later September forecast tables are not integrated.'],responses=[dict(type='published_official_explanation',sourceId=b['sourceId'],sourceLocator='Addendum printed page 1, introductory paragraphs',summary='The government describes reinstated and re-established support for disability, senior and education programs; the introduction rounds the change to CAD 53.6 million.',contactedByProject=False)],nextSteps=['Reconcile addendum program detail to the precise summary difference.','Link the exact approval record and subsequent actuals using compatible accounting definitions.'],chronology=[dict(label='Original budget table',sourceId=a['sourceId'],date='2026-02-23'),dict(label='Budget revisions announced',sourceId=b['sourceId'],date='2026-03-10',dateType='announcement_not_verified_publication_date')],limitations=['Not the latest forecast.','Original budget URL has an unresolved access hold; values were independently checked before that hold.','Source text was reviewed, but raw document binaries were not retained.'])
    symbols=[dict(id='symbol-001',metric='contingency_expense',period='2025-26',stage='audited_actual',rawValue=None,sourceSymbol='—',sourceId=docs['ns-public-accounts-2025-26-sec']['id'],sourceLocator='Statement 2, printed page 76, Actual 2026 column',interpretation='The source dash is not a numeric spending zero.')]
    return dict(schemaVersion=SCHEMA,asOf='2026-10-28',coverage=dict(guideSourceCount=139,uniqueGuideURLs=len(set(s['url'] for s in sources[:139])),fiscalFactCount=29,paymentFacts=0,complete=False,notes=['139 reference entries are not 139 integrations.','Document text review and source-binary acquisition are separate states.','No personal or private investigative material is included.']),sources=sources,evidenceRecords=evidence,moneyFacts=facts,reportedSymbols=symbols,investigations=[publish_case(case)],relationships=[dict(id='relation-001',type='same_metric_budget_version_comparison',fromFactId=a['id'],toFactId=b['id'],method='same_metric_period_basis_perimeter',evidenceIds=[a['evidenceId'],b['evidenceId']],confidence='verified_comparable_dimensions',inferredPaymentLink=False)])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=Path,default=ROOT/'research-seed.json');p.add_argument('--out',type=Path,default=ROOT/'foundation.json');args=p.parse_args()
    result=build(load(args.seed));args.out.write_text(dump(result));print(json.dumps({'sources':len(result['sources']),'facts':len(result['moneyFacts']),'sha256':hashlib.sha256(args.out.read_bytes()).hexdigest()}))
