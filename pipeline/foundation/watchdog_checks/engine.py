"""Deterministic private arithmetic checks. No eval, currency inference or publication."""
from decimal import Decimal,localcontext
import json,hashlib,re,pathlib
class InvalidDeclaration(ValueError):pass

def number(v):
 if not isinstance(v,str) or not re.fullmatch(r'-?\d+(?:\.\d+)?',v) or len(v)>80:raise InvalidDeclaration('Expected bounded exact decimal string')
 d=Decimal(v)
 if not d.is_finite():raise InvalidDeclaration('Nonfinite number')
 return d

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def cell_key(f):
 loc=f['nativeCellLocator'];kind=loc.get('kind')
 expected={'pdf_table_cell':{'kind','page','table','row','column'},'dataset_cell':{'kind','rowId','field'}}
 if kind not in expected or set(loc)!=expected[kind]:raise InvalidDeclaration('Noncanonical native cell locator')
 if any(v is None or v=='' or isinstance(v,(dict,list,bool)) for v in loc.values()):raise InvalidDeclaration('Invalid native locator value')
 return (f['sourceSnapshotSha256'],json.dumps(loc,sort_keys=True))

def evaluate(rule,facts):
 if rule['operation']!='linear_identity' or (type(rule['version']) is not int or rule['version']!=1):raise InvalidDeclaration('Unsupported rule operation/version')
 if rule['mode'] not in ('source_native_arithmetic','monetary_comparison'):raise InvalidDeclaration('Unknown measurement mode')
 terms=rule['left']+rule['right'];ids=[t['factId'] for t in terms]
 if len(ids)!=len(set(ids)):raise InvalidDeclaration('Repeated fact would double count/cancel')
 if not terms or not rule['left'] or not rule['right'] or len(terms)>100:raise InvalidDeclaration('Invalid expression size')
 for t in terms:
  if set(t)!= {'factId','coefficient'} or type(t['coefficient']) is not int or t['coefficient'] not in (-1,1):raise InvalidDeclaration('Only explicit signed terms allowed')
 base={'ruleId':rule['id'],'ruleVersion':rule['version'],'ruleDeclarationSha256':digest(rule),'publicationAllowed':False,'consequentialAllegation':False,'statusScope':'Arithmetic result only; not fraud, legality, payment correctness or delivery verification.','mode':rule['mode'],'inputFactIds':ids,'alternatives':rule['alternatives'],'missingRecords':rule['missingRecords'],'snapshotBindings':[],'calculation':None,'currency':None,'monetaryAmountEstablished':False}
 reasons=[]
 if any(i not in facts for i in ids):reasons.append('Missing input fact')
 if reasons:return dict(base,status='insufficient_evidence',reasons=reasons)
 selected=[facts[i] for i in ids]
 for lookup,f in zip(ids,selected):
  if f.get('id')!=lookup:raise InvalidDeclaration('Fact lookup identity mismatch')
  if not f.get('artifactSha256') or not f.get('sourceSnapshotSha256') or not f.get('sourceLocator') or not f.get('sourceFactId') or not f.get('nativeCellLocator'):raise InvalidDeclaration('Missing source provenance')
  if not re.fullmatch('[a-f0-9]{64}',f['artifactSha256']) or not re.fullmatch('[a-f0-9]{64}',f['sourceSnapshotSha256']):raise InvalidDeclaration('Malformed evidence digest')
  if f['availability']!='reported' or f['value'] is None:reasons.append('Missing or nonnumeric source observation')
 provenance_keys=[cell_key(f) for f in selected]
 if len(set(provenance_keys))!=len(provenance_keys):raise InvalidDeclaration('Same source cell selected more than once')
 base['snapshotBindings']=[{'factId':f['id'],'sourceFactId':f['sourceFactId'],'sourceSnapshotSha256':f['sourceSnapshotSha256'],'artifactSha256':f['artifactSha256'],'sourceLocator':f['sourceLocator'],'nativeCellLocator':f['nativeCellLocator']} for f in selected]
 if rule['basis']['mappingConfirmed'] is not True:reasons.append('Accounting/field mapping not established')
 if any(not isinstance(f['scopeKey'],str) or not f['scopeKey'] for f in selected):reasons.append('Unknown entity/period/schedule scope')
 if len({f['scopeKey'] for f in selected})!=1 or selected[0]['scopeKey']!=rule['basis']['scopeKey']:reasons.append('Mismatched entity/period/schedule scope')
 if any(not isinstance(f['unit'],str) or not f['unit'] for f in selected):reasons.append('Unknown unit declaration')
 if len({f['unit'] for f in selected})!=1 or selected[0]['unit']!=rule['basis']['unit']:reasons.append('Unknown or incompatible unit basis')
 sources={f['sourceSnapshotSha256'] for f in selected}
 if len(sources)!=1:reasons.append('Cross-source arithmetic not authorized by this runner version')
 if rule['mode']=='monetary_comparison':
  currencies={f.get('currency') for f in selected}
  if None in currencies or len(currencies)!=1 or not all(isinstance(c,str) and re.fullmatch('[A-Z]{3}',c) for c in currencies):reasons.append('Unknown or incompatible currency')
  if not rule['basis'].get('financialBasisId') or any(f.get('financialBasisId')!=rule['basis'].get('financialBasisId') for f in selected):reasons.append('Undeclared financial basis identity')
  if not all(f.get('financialBasisVerified') is True for f in selected):reasons.append('Financial accounting basis not verified')
  if not reasons:base.update(currency=selected[0]['currency'],monetaryAmountEstablished=True)
 else:
  if rule['basis'].get('nativeArithmeticDeclaration') not in ('same_schedule_component_sum','same_table_documented_asset_identity'):reasons.append('Source-native arithmetic not explicitly supported')
 if rule['basis'].get('nativeArithmeticDeclaration')=='same_schedule_component_sum':
  if rule['basis'].get('componentSetComplete') is not True:reasons.append('Incomplete component population')
  if any(facts[t['factId']]['role']!='component' for t in rule['left']) or len(rule['right'])!=1 or facts[rule['right'][0]['factId']]['role']!='printed_total':raise InvalidDeclaration('Aggregate/component double count or invalid schedule comparison')
 if reasons:return dict(base,status='insufficient_evidence',reasons=sorted(set(reasons)))
 with localcontext() as ctx:
  ctx.prec=200
  def side(terms):return sum((number(facts[t['factId']]['value'])*t['coefficient'] for t in terms),Decimal(0))
  left=side(rule['left']);right=side(rule['right']);residual=left-right
  calc={'operation':'sum(coefficient × exact input) on each side; residual = left − right','left':format(left,'f'),'right':format(right,'f'),'residual':format(residual,'f'),'tolerance':'0','exactEquality':residual==0,'unit':rule['basis']['unit'],'meaning':'Source-native numeric identity only; not a verified currency amount' if rule['mode']=='source_native_arithmetic' else 'Declared monetary comparison'}
 return dict(base,status='explained' if residual==0 else 'flagged_unreviewed',reasons=[],calculation=calc)

def run(fixture):
 if fixture['schemaVersion']!='arithmetic-fixtures-v1':raise InvalidDeclaration('Unsupported fixture schema')
 if len({f['id'] for f in fixture['facts']})!=len(fixture['facts']):raise InvalidDeclaration('Duplicate fact ID')
 if len({r['id'] for r in fixture['rules']})!=len(fixture['rules']):raise InvalidDeclaration('Duplicate rule ID')
 facts={f['id']:f for f in fixture['facts']};results=[evaluate(r,facts) for r in fixture['rules']]
 return {'schemaVersion':'private-arithmetic-run-v1','engineVersion':'1','engineSourceSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'fixtureSha256':digest(fixture),'publicationAllowed':False,'operation':'Offline deterministic arithmetic evaluation of declared reviewed fixtures; not a scheduled service or novel-discovery claim','results':results,'counts':{s:sum(r['status']==s for r in results) for s in ['flagged_unreviewed','explained','insufficient_evidence']},'limits':['No source changes, data deduplication, keyword accusations, vendor scores or automatic publication.','A nonzero residual is a reconciliation question. A zero residual only explains the declared arithmetic.','Unknown monetary currency/basis fails closed; explicitly declared same-source native arithmetic does not infer currency or missing money.','No cross-source subtraction is enabled in this version.']}
