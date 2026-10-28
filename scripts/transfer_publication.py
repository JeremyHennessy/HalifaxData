"""Exact program/jurisdiction/year mappings, not transaction or cash-to-accrual joins."""
import hashlib,json,datetime
from collections import Counter
from review_receipts import validate_receipt
KEYS={'top': ['attribution', 'coverage', 'limits', 'publication', 'publisher', 'records', 'retrievedAt', 'rightsLimit', 'rightsReviewURL', 'schemaVersion', 'sourceId', 'sourceSha256', 'sourceTitle', 'sourceURL', 'summaries'], 'row': ['basis', 'currency', 'currencyBasis', 'currencyExplicitlySpecified', 'fiscalYear', 'futurePayment', 'id', 'multiplier', 'paymentDate', 'presence', 'programCode', 'programLabel', 'rawToken', 'rawValue', 'recipient', 'recipientJurisdictionCode', 'sourceLocator', 'sourceUnit', 'stage'], 'locator': ['bodyRowIndexZeroBased', 'caption', 'cellIndexZeroBased', 'tableId', 'tableIndexZeroBased'], 'coverage': ['firstPaymentDate', 'lastPaymentDate', 'monthlyTables', 'numericSlots', 'paymentDates', 'valueSlots'], 'publication': ['allowed', 'consequentialAllegation', 'reason', 'reviewId', 'reviewType', 'reviewedOn'], 'summary': ['currency', 'currencyBasis', 'currencyExplicitlySpecified', 'fiscalYear', 'fullFiscalYearDatesPresent', 'paymentDateCount', 'programCode', 'sourceReportedSum', 'sourceUnit', 'sumScope'], 'linksTop': ['limits', 'links', 'nextEvidence', 'publication', 'rightsLimit', 'schemaVersion', 'title'], 'link': ['budget', 'comparison', 'fiscalYear', 'id', 'payments', 'programCode', 'programMapping', 'recipientJurisdictionCode'], 'budget': ['currency', 'financialBasis', 'multiplier', 'observationId', 'paymentEvidence', 'rawValue', 'reportingPerimeter', 'sourceLocator', 'sourceSha256', 'sourceURL', 'stage'], 'comparison': ['accountingReconciliationEstablished', 'differenceAsLossOrWaste', 'equalNumericValues', 'reportedPrimaryPaymentSum', 'rule', 'scaledBudgetNumber'], 'payments': ['currency', 'currencyBasis', 'currencyExplicitlySpecified', 'financialBasis', 'firstPaymentDate', 'lastPaymentDate', 'observationIds', 'paymentDateCount', 'primaryColumnSum', 'sourceSha256', 'sourceURL', 'sourceUnit'], 'programMapping': ['federalSourceLabel', 'method', 'provincialSourceLabel', 'sourceOwnedSharedTransactionId']}
def same(v,key):
    if not isinstance(v,dict) or sorted(v)!=KEYS[key]:raise ValueError('Unexpected transfer fields: '+key)
def reviewed(path,receipt):
    review=validate_receipt(json.loads(receipt.read_text()),'foundation')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=review['bundleSha256']:raise ValueError('Transfer publication bytes changed')
    return json.loads(path.read_text()),review
def publication(b,review,kind):
    p=b['publication'];same(p,'publication')
    if p['allowed'] is not True or p['consequentialAllegation'] is not False or p['reviewId']!=review['evidenceId'] or p['reviewedOn']!=review['reviewedOn'] or p['reviewType']!=kind:raise ValueError('Transfer review scope mismatch')
def full_year(rows):
    months=Counter(r['paymentDate'][:7] for r in rows)
    return len({r['paymentDate'] for r in rows})==24 and len(months)==12 and all(n==2 for n in months.values())
def currency(r):
    if r['currency']!='CAD' or r['currencyExplicitlySpecified'] is not False or r['currencyBasis']!='context_inferred_from_official_canadian_federal_transfer_program':raise ValueError('Unverified source currency claim')
def transfer_files(root):
    folder=root/'data/transfers'
    if not (folder/'records.json').exists():return []
    b,review=reviewed(folder/'records.json',folder/'publication-review.json');same(b,'top');same(b['coverage'],'coverage');publication(b,review,'source_attributed_federal_transfer_facts')
    if b['schemaVersion']!='federal-transfer-observations-v1':raise ValueError('Unknown transfer schema')
    rows={};dates=set();numeric=0;months=set();identities=set()
    for row in b['records']:
        same(row,'row');same(row['sourceLocator'],'locator');currency(row)
        identity=(row['recipientJurisdictionCode'],row['programCode'],row['paymentDate'])
        if identity in identities or row['id'] in rows or row['recipientJurisdictionCode']!='CA-NS' or row['recipient']!='Nova Scotia' or row['multiplier']!=1 or row['stage']!='source_reported_payment' or row['sourceUnit']!='dollars' or row['futurePayment'] is not False:raise ValueError('Unverified payment scope')
        date=datetime.date.fromisoformat(row['paymentDate']);start=date.year if date.month>=4 else date.year-1
        if row['fiscalYear']!=f'{start}-{str(start+1)[-2:]}' or date.isoformat()>b['retrievedAt'][:10]:raise ValueError('Payment period mismatch')
        if row['presence']=='blank':
            if row['rawValue'] is not None or row['rawToken']!='':raise ValueError('Blank is not zero')
        elif row['presence']=='present':
            if str(int(row['rawValue']))!=row['rawValue'] or row['rawToken'].replace(',','')!=row['rawValue']:raise ValueError('Invalid exact payment value')
            numeric+=1
        else:raise ValueError('Unknown payment presence')
        identities.add(identity);rows[row['id']]=row;dates.add(row['paymentDate']);months.add(row['sourceLocator']['tableIndexZeroBased'])
    c=b['coverage']
    if len(rows)!=c['valueSlots'] or len(dates)!=c['paymentDates'] or len(months)!=c['monthlyTables'] or numeric!=c['numericSlots'] or min(dates)!=c['firstPaymentDate'] or max(dates)!=c['lastPaymentDate']:raise ValueError('Payment coverage mismatch')
    for summary in b['summaries']:
        same(summary,'summary');currency(summary);population=[r for r in rows.values() if r['programCode']==summary['programCode'] and r['fiscalYear']==summary['fiscalYear']]
        if any(r['presence']!='present' for r in population) or len(population)!=summary['paymentDateCount'] or sum(int(r['rawValue']) for r in population)!=int(summary['sourceReportedSum']) or summary['fullFiscalYearDatesPresent']!=full_year(population):raise ValueError('Primary-column summary mismatch')
    links,linkReview=reviewed(folder/'links.json',folder/'links-review.json');same(links,'linksTop');publication(links,linkReview,'neutral_program_budget_payment_links')
    if links['schemaVersion']!='program-budget-payment-links-v1':raise ValueError('Unknown link schema')
    budget={r['id']:r for r in json.loads((root/'data/budget-tables/records.json').read_text())['records']};seen=set()
    for link in links['links']:
        same(link,'link')
        for key in ('budget','comparison','payments','programMapping'):same(link[key],key)
        v=link['budget'];p=link['payments'];cmp=link['comparison'];currency(p)
        if link['id'] in seen or link['recipientJurisdictionCode']!='CA-NS' or link['programMapping']['sourceOwnedSharedTransactionId'] is not None or cmp['accountingReconciliationEstablished'] is not False or cmp['differenceAsLossOrWaste'] is not None:raise ValueError('Unsupported transaction/accounting claim')
        seen.add(link['id']);original=budget.get(v['observationId'])
        if not original or any(original[k]!=v[k] for k in ('currency','financialBasis','reportingPerimeter','paymentEvidence')) or original['rawValue']!=v['rawValue'] or original['multiplier']!=v['multiplier'] or original['stage']!=v['stage'] or original['fiscalYearLabel']!=link['fiscalYear'] or original['label']!=link['programMapping']['provincialSourceLabel'] or original['provenance']!=v['sourceLocator']:raise ValueError('Budget link does not match original cell')
        population=[r for r in rows.values() if r['programCode']==link['programCode'] and r['fiscalYear']==link['fiscalYear']]
        if set(p['observationIds'])!={r['id'] for r in population} or len(p['observationIds'])!=len(population) or len(population)!=p['paymentDateCount'] or not full_year(population) or min(r['paymentDate'] for r in population)!=p['firstPaymentDate'] or max(r['paymentDate'] for r in population)!=p['lastPaymentDate'] or any(r['presence']!='present' or r['programLabel']!=link['programMapping']['federalSourceLabel'] for r in population):raise ValueError('Payment population mismatch')
        total=sum(int(r['rawValue']) for r in population);scaled=int(v['rawValue'])*v['multiplier']
        if str(total)!=p['primaryColumnSum'] or str(total)!=cmp['reportedPrimaryPaymentSum'] or str(scaled)!=cmp['scaledBudgetNumber'] or cmp['equalNumericValues']!=(total==scaled) or p['sourceSha256']!=b['sourceSha256'] or v['sourceSha256']!=original['provenance']['sourcePdfSha256']:raise ValueError('Program trace values do not reproduce')
    return ['data/transfers/'+name for name in ('records.json','publication-review.json','links.json','links-review.json')]
