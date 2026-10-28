"""Allowlisted exact-schema adapters for already independently reviewed source fixtures."""
import json,pathlib,hashlib
ROOT=pathlib.Path(__file__).resolve().parent.parent/'fixtures'
SPECS={
 'shelburne':('shelburne/decision.json','a259a520a95ff06fc5b765a3a5af17aa66e9f358e2c4df6981764e0cec0d1281','shelburne/decision-review.json','shelburne-grant-decision-reconciliation-v1'),
 'annapolis':('capital-explanation/annotation.json','6e723fc4cef52be5d24c3245bf3cf58aaf2819cfc69237daae469d4c8738777c','capital-explanation/publication-review.json','explained-capital-movement-v1'),
 'municipal':('reporting-question/case.json','65a96a5960ea14b439d41823f55a317c181398664233551514b00ad1374bde82','reporting-question/publication-review.json','source-reporting-question-v1')}
RECEIPT_SHAS={'shelburne': '8dd4f8e8c6959c32144133a6a7abbb0518274d4d49339891c0b5c4203b82e4bb', 'annapolis': '934ff3a57d42ccf83c02232c599e4561feaf60246762501de7321ad02a3c74b5', 'municipal': '9caa8fe5787717962430b143b000864ce93e927bbe6271c7977c6d4d7d5c05f3'}
def load(name, input_path=None):
 root=pathlib.Path(input_path) if input_path is not None else ROOT
 path,sha,receipt,schema=SPECS[name];b=(root/path).read_bytes()
 if hashlib.sha256(b).hexdigest()!=sha:raise ValueError('Reviewed fixture drift')
 x=json.loads(b);rb=(root/receipt).read_bytes()
 if hashlib.sha256(rb).hexdigest()!=RECEIPT_SHAS[name]:raise ValueError('Review receipt drift')
 r=json.loads(rb)
 if r['status']!='accepted' or r['bundleSha256']!=sha or not r.get('reviewer') or x['schemaVersion']!=schema:raise ValueError('Unreviewed or unknown fixture schema')
 return x,sha

def fact(id,value,sourceid,loc,artifact,source,scope,unit,role='component',currency=None,available='reported'):
 if 'sourceRowId' in loc:native={'kind':'dataset_cell','rowId':loc['sourceRowId'],'field':loc['sourceField']}
 elif 'sourceColumn' in loc:native={'kind':'pdf_table_cell','page':loc['pdfPage'],'table':loc['table'],'row':loc['row'],'column':loc['sourceColumn']}
 else:native={'kind':'pdf_table_cell','page':loc.get('page',loc.get('pdfPage')),'table':'M24-212','row':loc.get('scheduleRowNumber','printed_total'),'column':'grant_amount'}
 return {'id':id,'value':value,'sourceFactId':sourceid,'sourceLocator':loc,'nativeCellLocator':native,'artifactSha256':artifact,'sourceSnapshotSha256':source,'scopeKey':scope,'unit':unit,'role':role,'currency':currency,'financialBasisVerified':False,'availability':available}
def term(id,sign=1):return {'factId':id,'coefficient':sign}
def rule(id,left,right,scope,unit,kind,confirmed,alternatives,missing):
 return {'id':id,'version':1,'operation':'linear_identity','mode':'source_native_arithmetic','left':left,'right':right,'basis':{'scopeKey':scope,'unit':unit,'nativeArithmeticDeclaration':kind,'mappingConfirmed':confirmed,'componentSetComplete':kind=='same_schedule_component_sum'},'alternatives':alternatives,'missingRecords':missing}

def build(input_path=None):
 facts=[];rules=[];s,sha=load('shelburne',input_path);src=s['sources'][0];scope='Shelburne|M24-212|approved-schedule-pages7-8';unit='source_dollar_symbols_same_schedule_currency_unspecified'
 if s['decision']['officialMotionId']!='M24-212' or len(s['records'])!=35 or s['decision']['scheduleRows']!=35:raise ValueError('Schedule scope drift')
 for i,r in enumerate(s['records']):
  if r['stage']!='approved_grant_schedule_not_payment' or r['officialMotionId']!='M24-212':raise ValueError('Mixed schedule basis')
  facts.append(fact(r['id'],r['reportedAmount'],r['id'],{'jsonPointer':f'/records/{i}/reportedAmount',**r['sourceLocator'],'sourceField':'grant_amount'},sha,src['sourceBodySha256'],scope,unit))
 total='shelburne:M24-212:printed-schedule-total'
 facts.append(fact(total,s['approvedScheduleReconciliation']['printedTotal'],total,{'jsonPointer':'/approvedScheduleReconciliation/printedTotal','pdfPage':8,'motion':'M24-212','sourceField':'printed_schedule_total','identifierBasis':'adapter_local_locator_not_official_transaction_id'},sha,src['sourceBodySha256'],scope,unit,role='printed_total'))
 rules.append(rule('shelburne-schedule-total-v1',[term(r['id']) for r in s['records']],[term(total)],scope,unit,'same_schedule_component_sum',True,s['possibleExplanationsNotEstablished'],s['missingEvidence']))
 a,sha=load('annapolis',input_path);src=a['source'];scope='Annapolis|table3.6.1|row5|2021-2022';unit='unlabelled_source_native_numbers_same_asset_table';bymeasure={}
 for i,r in enumerate(a['facts']):
  if r['sourceLocator']['pdfPage']!=46:continue
  if r['sourceLocator']['row']!=5 or r['sourceMunicipalityLabel']!='Municipality of the County of Annapolis':raise ValueError('Asset entity scope drift')
  bymeasure[r['measure']]=r['id'];facts.append(fact(r['id'],r['value'],r['id'],{'jsonPointer':f'/facts/{i}/value',**r['sourceLocator'],'sourceColumn':r['sourceColumn']},sha,src['sha256'],scope,unit,role=r['measureType'],available=r['availability']))
 specs=[('gross-cost-roll-forward',[('gross_cost_opening',1),('additions',1),('disposals_write_downs',1)],'gross_cost_closing'),('accumulated-amortization-roll-forward',[('accumulated_amortization_opening',1),('annual_amortization',1),('amortization_adjustments_disposals',1)],'accumulated_amortization_second_column'),('closing-net-book-value',[('gross_cost_closing',1),('accumulated_amortization_second_column',-1)],'net_book_value')]
 accepted={e['id'] for e in a['equations']}
 for rid,lhs,rhs in specs:
  if rid not in accepted:raise ValueError('Identity not in reviewed explanation')
  rules.append(rule('annapolis-'+rid+'-v1',[term(bymeasure[n],c) for n,c in lhs],[term(bymeasure[rhs])],scope,unit,'same_table_documented_asset_identity',True,['Numerical agreement does not establish the purpose or legitimacy of disposal/write-down entries.'],['Asset/disposal schedules, decisions and transaction records before interpreting underlying causes or cash effects.']))
 m,sha=load('municipal',input_path)
 for i,e in enumerate(m['evidence']):
  p=e['portal'];scope=p['sourceRowId']+'|'+e['fiscalYear']+'|'+e['municipalityType'];unit='source_native_portal_number_mapping_unverified';ids={}
  for field in ['operatingBalance','financingAndTransfers','reportedAnnualBalance']:
   ident=p['sourceRowId']+':'+field;ids[field]=ident;facts.append(fact(ident,p[field],ident,{'jsonPointer':f'/evidence/{i}/portal/{field}','sourceRowId':p['sourceRowId'],'sourceField':{'operatingBalance':'operating_surplus_deficit_before_financing_and_transfers','financingAndTransfers':'total_financing_and_transfers','reportedAnnualBalance':'annual_surplus_deficit_'}[field]},sha,p['rawSha256'],scope,unit))
  rules.append(rule('municipal-'+p['sourceRowId']+'-balance-v1',[term(ids['operatingBalance']),term(ids['financingAndTransfers'])],[term(ids['reportedAnnualBalance'])],scope,unit,'unverified_portal_balance_mapping',p['exactAccountingPolicyVerified'],m['hypotheses'],m['nextRecords']))
 return {'schemaVersion':'arithmetic-fixtures-v1','scope':'Three known reviewed fixtures, not new findings or a broad coverage claim','facts':facts,'rules':rules,'fixtureReviewReceiptHashes':RECEIPT_SHAS,'fixtureArtifactHashes':{name:spec[1] for name,spec in SPECS.items()},'notes':['Shelburne and Annapolis are explicitly declared same-source native-number identities. Currency code is not inferred.','Municipal formula mapping remains unverified; runner must emit insufficient evidence rather than financial discrepancy.','Paid-disclosure totals, profile amounts, unrelated source totals and fund/consolidated duplicate totals are not selected.']}
