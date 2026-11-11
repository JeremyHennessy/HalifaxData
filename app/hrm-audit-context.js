import {verifiedJSON} from './tenders.js';
import {HRM_HASH} from './hrm-audits.js';
export const ANNUAL_HASH='76f5e0bc8beabc514c352b51569871b2f108020cbf7de173184c0166e44359a9';
export const ANNUAL_REVIEW_HASH='b71e6b1a61c2b47d7589b0dc4a62e35a5d020d783363909d67f9b27f34296a34';
export const ANNUAL_SOURCE_HASH='f0f22cddff14327f72c5af379172c7ef46a5e90041f16e179b7d1949746a3f4d';
const need=(ok,message)=>{if(!ok)throw Error(message);};
const shape=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join('|')===keys.split(' ').sort().join('|');
export function validateAnnualContext(b,r,parent){
 need(shape(b,'schemaVersion title source measure parent explanation limits sourceRights publication'),'Annual context public field allowlist mismatch');
 need(shape(r,'status reviewer reviewedOn evidenceId scope limitations bundleSha256 sourceSha256 checks')&&r.status==='accepted'&&r.bundleSha256===ANNUAL_HASH&&r.sourceSha256===ANNUAL_SOURCE_HASH&&typeof r.reviewer==='string'&&r.reviewer.length>0&&Array.isArray(r.checks)&&Array.isArray(r.limitations),'Annual context independent review unavailable');
 const p=b.publication,s=b.source,m=b.measure;
 need(shape(p,'allowed requiresMatchingIndependentReceipt consequentialAllegation reviewType reviewId reviewedOn')&&p.allowed===true&&p.requiresMatchingIndependentReceipt===true&&p.consequentialAllegation===false&&p.reviewType==='source_attributed_historical_performance_context'&&p.reviewId===r.evidenceId&&p.reviewedOn===r.reviewedOn,'Annual context publication mismatch');
 need(b.schemaVersion==='hrm-annual-audit-context-v1'&&shape(s,'publisher title url sha256 bytes retrievedOn printedPage pdfPage')&&s.publisher==='Office of the Auditor General, Halifax Regional Municipality'&&s.title==='2025-26 Annual Report and 2026-27 Audit Priorities'&&s.url==='https://hrmauditorgeneral.ca/themes/user/site/default/asset/img/common/2025-26_Annual_Report_and_2026-27_Audit_Priorities.pdf'&&s.sha256===ANNUAL_SOURCE_HASH&&s.bytes===222532&&s.retrievedOn==='2026-11-11'&&s.printedPage===3&&s.pdfPage===4,'Annual context source mismatch');
 need(shape(m,'periodAsReported description resultPercent targetPercent recommendationDenominator statusObservationAsOf currentStatusVerified')&&m.periodAsReported==='2025-26'&&m.description==='Recommendations implemented after 18 months'&&m.resultPercent===70&&m.targetPercent===80&&m.recommendationDenominator===null&&m.statusObservationAsOf===null&&m.currentStatusVerified===false,'Annual measure or uncertainty mismatch');
 need(shape(b.parent,'path sha256 relationship')&&b.parent.path==='data/hrm-audits/records.json'&&b.parent.sha256===HRM_HASH&&parent?.review.bundleSha256===HRM_HASH&&parent?.bundle.reportMonth==='2026-10'&&parent?.bundle.reportedSummary.completionPercent===44,'Annual context parent mismatch');
 need(shape(b.sourceRights,'reuseLicence projection')&&b.sourceRights.reuseLicence==='not_established'&&typeof b.sourceRights.projection==='string'&&typeof b.explanation==='string'&&Array.isArray(b.limits)&&b.limits.length===3&&b.limits.every(v=>typeof v==='string'),'Annual context interpretation scope mismatch');
 return b;
}
export async function getAnnualContext(parent,signal,fetcher=fetch){
 const review=await verifiedJSON('data/hrm-audit-context/publication-review.json',ANNUAL_REVIEW_HASH,null,signal,fetcher);
 const bundle=validateAnnualContext(await verifiedJSON('data/hrm-audit-context/context.json',ANNUAL_HASH,null,signal,fetcher),review,parent);
 return{bundle,review};
}
