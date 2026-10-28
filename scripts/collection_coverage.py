"""Build a separate receipt-bound collection layer without changing the reference inventory."""
import hashlib,json
COLLECTIONS=[
 ('municipal-capital','Historical municipal capital assets',[],'data/municipal-capital/records.json','data/municipal-capital/publication-review.json','records','source rows: 49 municipalities and 3 overlapping aggregates','#/municipal-capital','Historical 2021–22 capital assets, not operating expenses or cash payments. Currency and scale unknown; excluded placeholders and conflicting dates preserved.'),
 ('cash-bridge','NSCC cash/accrual explanation',[],'data/cash-bridge/case.json','data/cash-bridge/publication-review.json',None,'reviewed accounting explanation','#/cash-bridge','46 source observations and 14 explicit equations across two years. Internal statement arithmetic, not underlying bank verification.'),
 ('authorizations','Supplemental appropriation orders',[],'data/authorizations/records.json','data/authorizations/publication-review.json','orders','reviewed orders','#/authorizations','23 clauses in two separate fiscal years. Authorization, not payment; no combined fiscal-year total.'),
 ('foundation','Financial statement facts',['fiscal-document-01','fiscal-document-02','fiscal-document-03','fiscal-document-04'],'data/foundation.json','data/publication-review.json','moneyFacts','financial facts','#/money','Primary text reviewed; source binary was not retained for these facts.'),
 ('tenders','Procurement observations',['guide-024'],'data/tenders/tender-index.json','data/tenders/publication-review.json','recordCount','publisher observations','#/tenders','Bounded captured snapshot; not every tender, contract or payment.'),
 ('suppliers','Reviewed supplier-label associations',['guide-024'],'data/suppliers/labels.json','data/suppliers/publication-review.json','recordCount','reviewed label associations','#/tenders','71 exact reviewed labels only; not resolved legal owners or all suppliers.'),
 ('municipal','Historical municipal operating records',['guide-011'],'data/municipal/records.json','data/municipal/publication-review.json','records','municipality/type/year observations','#/municipal','2013–14 through 2023–24 only; not current financial reporting.'),
 ('reporting','Municipal reporting question',['guide-011'],'data/reporting-question/case.json','data/reporting-question/publication-review.json',None,'reviewed reporting question','#/reporting-question/municipal-operating-balance-reporting-2019-20','Two 2019–20 source observations and separately reviewed provincial profiles.'),
 ('audits','Historical audit follow-up',['guide-042'],'data/audits/records.json','data/audits/publication-review.json','records','organization/audit rows','#/audits','Assurance status date October 10, 2025; report published March 31, 2026. Not current completion status.'),
 ('budget','Captured budget summary tables',['fiscal-document-02'],'data/budget-tables/records.json','data/budget-tables/publication-review.json','records','source cells','#/budget-tables','Two tables of a 70-page addendum. Estimates and a historical forecast, not payments.'),
 ('transfers','Federal transfer factual projection',['guide-023'],'data/transfers/records.json','data/transfers/publication-review.json','records','source program/date cells','#/transfers','Nova Scotia only; April 2023 through October 2026. Latest fiscal year is partial.'),
 ('transfer-links','Budget-to-transfer program mappings',['guide-023','fiscal-document-02'],'data/transfers/links.json','data/transfers/links-review.json','links','reviewed program/year mappings','#/transfers','2025–26 only; not a shared transaction identifier or accounting reconciliation.'),
 ('governance','Government decision and presentation link',['fiscal-document-02'],'data/governance/case.json','data/governance/publication-review.json',None,'reviewed source-number connection','#/governance/oic-2025-366-nscc-budget-presentation','One official order and one budget footnote; no expenditure authority or payment linkage.'),
 ('institution','NSCC consolidated statement subset',[],'data/nscc/records.json','data/nscc/publication-review.json','records','institutional statement cells','#/institution','One consolidated statement page; College and Foundation, budget/actual/prior comparative columns.')]
def build_collection_coverage(root):
    foundation=json.loads((root/'data/foundation.json').read_text());source_ids={s['id'] for s in foundation['sources']};collections=[]
    for identity,title,related,path,receipt_path,count_key,unit,route,scope in COLLECTIONS:
        file=root/path
        if not file.exists():continue
        receipt=json.loads((root/receipt_path).read_text());digest=hashlib.sha256(file.read_bytes()).hexdigest()
        if receipt['status']!='accepted' or receipt.get('bundleSha256',receipt.get('indexSha256'))!=digest or not set(related)<=source_ids:raise ValueError('Collection coverage lacks matching accepted review')
        data=json.loads(file.read_text());value=data.get(count_key) if count_key else 1;count=len(value) if isinstance(value,list) else value
        if not isinstance(count,int) or count<1:raise ValueError('Invalid collection count')
        urls=set()
        def sources(v):
            if isinstance(v,dict):
                for k,item in v.items():
                    if k in ('sourceURL','url') and isinstance(item,str) and item.startswith('https://'):urls.add(item.split('#')[0])
                    elif k!='sources':sources(item)
            elif isinstance(v,list):
                for item in v:sources(item)
        sources(data)
        collections.append({'id':identity,'title':title,'relatedSourceIds':related,'dataPath':path,'dataSha256':digest,'reviewPath':receipt_path,'reviewId':receipt['evidenceId'],'reviewedOn':receipt['reviewedOn'],'count':count,'countUnit':unit,'route':route,'scope':scope,'completeSourceCoverage':False,'scheduledRefreshConfigured':False,'sourceURLs':sorted(urls)})
    return {'schemaVersion':'reviewed-collection-coverage-v1','guideReferenceCount':139,'supportingDocumentReferences':4,'countingNote':'Collections, documents, observations and source families are different units. Counts overlap and must not be added together.','refreshNote':'No source-ingestion refresh schedule is configured in this repository. Review dates do not make historical records current.','collections':collections}
