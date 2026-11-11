import {verifiedJSON} from './tenders.js';
export const HRM_HASH='f9171cfa466d09389976cb38172b735ea22488ac161db77463b726f1f7c893a4';
// Independent review binds the exact public artifact and source bytes.
export const HRM_REVIEW_HASH='4ed640578877ab4e949ffaf75fc0c67a3db25df7847079f555be091cb27b166f';
export const HRM_SOURCE_HASH='c8ea434d59f1527e6804b11dbff512fb413c72e5c67434a9948b2999b921acb6';
const need=(ok,message)=>{if(!ok)throw Error(message);};
const shape=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join('|')===keys.split(' ').sort().join('|');
const groups=[['diversity-inclusion','Diversity and Inclusion','2024-12','The Office of Diversity & Inclusion',8,7,88,[1,3,4,5,6,7,8]],['enterprise-risk','Enterprise Risk Management','2024-07','Legal, Risk & Insurance Services',14,4,29,[8,10,11,12]],['business-continuity','Management of Business Continuity','2024-07','Community Safety',10,3,30,[2,8,9]]];
export function validateHRMAudits(b,r){
 need(shape(b,'schemaVersion title publisher sourceURL landingURL sourceSha256 sourceBytes retrievedOn reportMonth letterDate summaryGraphicMonth statusObservationAsOf scope reportedSummary assurance limits audits records publication sourceRights'),'HRM public field allowlist mismatch');
 need(shape(r,'status reviewer reviewedOn evidenceId scope limitations bundleSha256 sourceSha256 checks')&&r.status==='accepted'&&r.bundleSha256===HRM_HASH&&r.sourceSha256===HRM_SOURCE_HASH&&typeof r.reviewer==='string'&&r.reviewer.length>0&&Array.isArray(r.checks)&&Array.isArray(r.limitations),'HRM independent receipt unavailable');
 const p=b.publication;
 need(shape(p,'allowed requiresMatchingIndependentReceipt consequentialAllegation reviewType reviewId reviewedOn')&&p.allowed===true&&p.requiresMatchingIndependentReceipt===true&&p.consequentialAllegation===false&&p.reviewType==='source_attributed_historical_hrm_recommendation_status'&&p.reviewId===r.evidenceId&&p.reviewedOn===r.reviewedOn,'HRM independent publication review mismatch');
 need(b.schemaVersion==='hrm-audit-followup-status-v1'&&b.sourceSha256===HRM_SOURCE_HASH&&b.sourceBytes===599344&&b.sourceURL==='https://hrmauditorgeneral.ca/themes/user/site/default/asset/img/common/Follow-up_Review_2024_Audits.pdf'&&b.landingURL==='https://hrmauditorgeneral.ca/follow-up'&&b.publisher==='Office of the Auditor General, Halifax Regional Municipality','HRM source identity mismatch');
 need(b.reportMonth==='2026-10'&&b.letterDate==='2026-09-11'&&b.summaryGraphicMonth==='2026-09'&&b.statusObservationAsOf===null&&b.retrievedOn==='2026-11-11','HRM date meanings must remain separate');
 need(shape(b.assurance,'level methodologyPrintedPage methodologyPdfPage summary')&&b.assurance.level==='limited assurance'&&b.assurance.methodologyPrintedPage===10&&b.assurance.methodologyPdfPage===11&&b.assurance.summary==='Review-level assurance based on discussions and limited testing, lower than an audit.','HRM assurance boundary mismatch');
 need(shape(b.sourceRights,'reuseLicence projection')&&b.sourceRights.reuseLicence==='not_established'&&typeof b.sourceRights.projection==='string'&&Array.isArray(b.limits)&&b.limits.length===6&&b.limits.every(x=>typeof x==='string'),'HRM publication scope mismatch');
 const s=b.reportedSummary;
 need(shape(s,'recommendations completed completionPercent printedPage pdfPage')&&s.recommendations===32&&s.completed===14&&s.completionPercent===44&&s.printedPage===3&&s.pdfPage===4&&b.audits.length===3&&b.records.length===32,'HRM bounded summary mismatch');
 const ids=new Set();
 for(const [id,title,month,unit,total,completed,percent,numbers]of groups){
  const a=b.audits.find(a=>a.id===id),rows=b.records.filter(row=>row.auditId===id);
  need(shape(a,'id auditTitle originalAuditMonth businessUnitAsReported reportedTotal reportedCompleted reportedCompletionPercent summaryPrintedPage summaryPdfPage completedRecommendationNumbers')&&a.auditTitle===title&&a.originalAuditMonth===month&&a.businessUnitAsReported===unit&&a.reportedTotal===total&&a.reportedCompleted===completed&&a.reportedCompletionPercent===percent&&a.summaryPrintedPage===3&&a.summaryPdfPage===4&&JSON.stringify(a.completedRecommendationNumbers)===JSON.stringify(numbers)&&rows.length===total,'HRM audit identity or reported count mismatch');
  const seen=new Set();
  for(const row of rows){
   const n=row.recommendationNumber,printed=id==='diversity-inclusion'?(n<=7?4:5):id==='enterprise-risk'?(n<=8?6:7):(n<=7?8:9);
   need(shape(row,'id auditId recommendationNumber statusAsReported printedPage pdfPage currentStatusVerified')&&Number.isSafeInteger(n)&&n>=1&&n<=total&&!seen.has(n)&&!ids.has(row.id)&&row.id===`hrm-2024-${id}-${String(n).padStart(2,'0')}`&&row.currentStatusVerified===false&&row.statusAsReported===(numbers.includes(n)?'Completed':'Incomplete')&&row.printedPage===printed&&row.pdfPage===printed+1,'HRM recommendation identity, status or locator mismatch');
   seen.add(n);ids.add(row.id);
  }
 }
 need(ids.size===32,'HRM recommendation coverage mismatch');return b;
}
export function filterHRMAudits(b,{q='',audit='',status=''}={}){
 need(!audit||b.audits.some(a=>a.id===audit),'Unknown HRM audit');need(!status||['Completed','Incomplete'].includes(status),'Unknown historical HRM status');
 const query=q.trim().toLocaleLowerCase('en-CA');return b.records.filter(r=>{const a=b.audits.find(a=>a.id===r.auditId);return(!audit||r.auditId===audit)&&(!status||r.statusAsReported===status)&&(!query||[r.id,String(r.recommendationNumber),a.auditTitle,a.businessUnitAsReported].some(value=>value.toLocaleLowerCase('en-CA').includes(query)));});
}
export function hrmEvidenceExport(bundle,review,filters){return{bundle,review,filters,matchingRecordIds:filterHRMAudits(bundle,filters).map(r=>r.id),scope:'32 historical recommendation statuses from three named 2024 HRM audits only. Full reviewed bundle retained; matchingRecordIds identifies the filtered subset. No combined provincial recommendation total or current completion verification.'};}
export async function getHRMAudits(signal,fetcher=fetch){const review=await verifiedJSON('data/hrm-audits/publication-review.json',HRM_REVIEW_HASH,null,signal,fetcher);const bundle=validateHRMAudits(await verifiedJSON('data/hrm-audits/records.json',HRM_HASH,null,signal,fetcher),review);return{bundle,review};}

// The directory itself is not an approval receipt. Validate this new entry against
// the actual admitted bytes before counting or displaying its descriptive metadata.
export function validateHRMCoverage(c,{bundle:b,review:r}){
 const scope='32 historical recommendation statuses in the October 2026 HRM follow-up: 14 reported completed, 44% as printed. Status-as-of is unknown; September letter/graphic dates are distinct. Limited assurance, lower than an audit. Separate from provincial organization/audit rows; no combined recommendation total.';
 need(c.id==='hrm-audits'&&c.title===b.title&&c.relatedSourceIds.length===0&&c.dataPath==='data/hrm-audits/records.json'&&c.reviewPath==='data/hrm-audits/publication-review.json'&&c.dataSha256===HRM_HASH&&c.reviewId===r.evidenceId&&c.reviewedOn===r.reviewedOn&&c.count===b.records.length&&c.countUnit==='historical recommendation-status rows from three named HRM audits'&&c.route==='#/audits?view=hrm'&&c.scope===scope&&c.completeSourceCoverage===false&&c.scheduledRefreshConfigured===false&&JSON.stringify(c.sourceURLs)===JSON.stringify([b.sourceURL]),'HRM directory entry does not match its verified evidence');return c;
}
