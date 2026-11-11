import {verifiedJSON} from './tenders.js';
export const CAPITAL_HASH='a33e4b93da00253b70125f4a34163cffa996a2cad8dacfb514ed6a150b6def7e';
export const CAPITAL_REVIEW_HASH='0dd2938884f98373ffa68aecd5c15a5fe71fa29e90ef653b07ae811c06453b0b';
export const CAPITAL_SOURCE_HASH='c18a7243e04556e25f9e99ae5c5fdfde8bc509663ed3ddfdd726e7c6481912af';
export const CAPITAL_SCOPE='Three business-unit aggregates representing 12 tested projects, not 12 identified project rows or the entire Capital Plan. Budget and workplan amounts, not payments or losses. Documentation tests overlap; management acceptance is not implementation. No cross-collection totals.';
export const CAPITAL_UNIT='business-unit aggregates of tested projects';
const need=(ok,message)=>{if(!ok)throw Error(message);};
export function validateCapital(b,r){
 need(r.status==='accepted'&&r.bundleSha256===CAPITAL_HASH&&r.sourceSha256===CAPITAL_SOURCE_HASH&&b.publication.allowed===true&&b.publication.reviewId===r.evidenceId&&b.publication.reviewedOn===r.reviewedOn,'Capital independent review mismatch');
 need(b.sourceSha256===CAPITAL_SOURCE_HASH&&b.sourceBytes===868537&&b.records.length===3&&b.amountUnit.currencyCode===null&&b.amountUnit.scale===1&&b.reportMonth==='2026-06'&&b.letterDate==='2026-06-10'&&b.auditPeriod.start==='2024-04-01'&&b.auditPeriod.end==='2025-03-31','Capital source, units or dates mismatch');
 const expected=[[5,30199000,68395000,98594000],[5,9097000,37235000,46332000],[2,1995000,2000000,3995000]];
 b.records.forEach((row,i)=>need(JSON.stringify(['projectsTested','carryForwardBudget','capitalBudget','totalWorkplan'].map(k=>row[k]))===JSON.stringify(expected[i])&&row.printedPage===10&&row.pdfPage===11,'Capital bounded aggregate mismatch'));
 for(const key of ['projectsTested','carryForwardBudget','capitalBudget','totalWorkplan'])need(b.reportedTotal[key]===b.records.reduce((n,r)=>n+r[key],0),'Capital reported total mismatch');
 need(b.documentationTests.length===2&&b.documentationTests[0].totalProjects===12&&b.documentationTests[1].totalProjects===9&&b.documentationTests.every(t=>t.insufficientInformation===6)&&b.managementResponses.every(m=>m.implementationVerified===false),'Capital test or implementation boundary mismatch');return b;
}
export function filterCapital(b,q=''){const query=q.trim().toLocaleLowerCase('en-CA');return b.records.filter(r=>[r.id,r.businessUnitAsReported].some(v=>v.toLocaleLowerCase('en-CA').includes(query)));}
export function capitalExport(bundle,review,q=''){return{bundle,review,filters:{q},matchingRecordIds:filterCapital(bundle,q).map(r=>r.id),scope:CAPITAL_SCOPE};}
export async function getCapital(signal,fetcher=fetch){const review=await verifiedJSON('data/hrm-capital/publication-review.json',CAPITAL_REVIEW_HASH,null,signal,fetcher);return{review,bundle:validateCapital(await verifiedJSON('data/hrm-capital/records.json',CAPITAL_HASH,null,signal,fetcher),review)};}
export function validateCapitalCoverage(c,{bundle:b,review:r}){need(c.id==='hrm-capital'&&c.title===b.title&&c.relatedSourceIds.length===0&&c.dataPath==='data/hrm-capital/records.json'&&c.reviewPath==='data/hrm-capital/publication-review.json'&&c.dataSha256===CAPITAL_HASH&&c.reviewId===r.evidenceId&&c.reviewedOn===r.reviewedOn&&c.count===3&&c.countUnit===CAPITAL_UNIT&&c.route==='#/hrm-capital'&&c.scope===CAPITAL_SCOPE&&c.completeSourceCoverage===false&&c.scheduledRefreshConfigured===false&&JSON.stringify(c.sourceURLs)===JSON.stringify([b.sourceURL]),'Capital directory metadata mismatch');return c;}
