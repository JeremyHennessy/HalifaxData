import {verifiedJSON} from './tenders.js';
export const AMBULANCE_SHA='b50fb2055dc53c46244a8aca3e6d523e76c5599180be0f6322f58c347b618e92';
export const AMBULANCE_REVIEW_SHA='e9c61ef1169254e6666ae7b220d2e55de75cd2477ee64e2a81f107e249d63971';
export const SERVICE_SHA='dc4226a5232e68a489c9e094676d012499d8cfa5b89706f2ea0d34ffc23dfe12';
export const SERVICE_REVIEW_SHA='6656b8643cd601b7dbe9cc2ca71c9b0a1e80e3f94a4a9d45a49871710553f8d8';
export const AMBULANCE_FOLLOWUP_ID='audit-status-b6a436efd9039f1ffe9c2666';
const FOLLOWUP_SHA='d0d9b05fe969ceec78cb87ff1a611f1650e878dc1501ded1ecaed01685402dbe';
const require=(ok,message)=>{if(!ok)throw Error(message);};
const published=(b,r,hash)=>require(r.status==='accepted'&&r.bundleSha256===hash&&b.publication.allowed===true&&b.publication.consequentialAllegation===false&&b.publication.reviewId===r.evidenceId&&b.publication.reviewedOn===r.reviewedOn,'Independent review mismatch');
export function validateAmbulance(b,review,audits,auditReview){
 published(b,review,AMBULANCE_SHA);require(b.schemaVersion==='ambulance-contract-compensation-v1'&&b.facts.length===24&&b.contractEvents.length===3&&b.recommendationLinks.length===2,'Ambulance subset mismatch');
 require(auditReview.bundleSha256===FOLLOWUP_SHA&&auditReview.status==='accepted'&&b.followUpSource.acceptedBundleSha256===FOLLOWUP_SHA&&b.followUpSource.recordId===AMBULANCE_FOLLOWUP_ID&&b.followUpSource.sha256===audits.sourceSha256&&b.followUpSource.statusAsOf===audits.limitedAssuranceAsOf&&audits.limitedAssuranceAsOf==='2025-10-10','Follow-up source mismatch');
 const row=audits.records.find(r=>r.id===AMBULANCE_FOLLOWUP_ID);require(row&&row.currentStatusVerified===false&&row.reportedNotCompleted===7,'Historical row mismatch');
 const raw=['$2.4','$4.1','$3.5','N/A*','N/A','$10.0','3%','3%','3%','3%','5%','','$3.7','$4.0','$3.7','$3.8','$6.5','$21.7','$6.1','$8.1','$7.2','$3.8','$6.5','$31.7'];
 b.facts.forEach((f,i)=>{const r=Math.floor(i/6)+1,c=i%6+1,rate=r===2,missing=['','N/A','N/A*'].includes(raw[i]);require(f.id===`ambulance-fees-r${r}-c${c}`&&f.rawValue===raw[i]&&f.sourceLocator.pdfPage===60&&f.sourceLocator.row===r&&f.sourceLocator.column===c&&f.periodStart===null&&f.periodEnd===null&&f.exactBankAmount===false&&f.columnRole===(c===6?'five_year_total':'fiscal_year')&&f.rowRole===(rate?'rate':r===4?'published_total':'component'),'Cell meaning mismatch');require(f.value===(missing?null:rate?raw[i].replace('%',''):String(BigInt(raw[i].replace(/[$.]/g,''))*100000n))&&f.stage===(rate?'reported_contract_fee_rate':'auditor_reported_compensation_paid')&&f.unitMultiplier===(rate?null:1000000)&&f.currency===(rate?null:'CAD')&&f.currencyExplicitlySpecified===false,'Money/rate/missing-value mismatch');});
 b.recommendationLinks.forEach((r,i)=>require(r.sourceRecommendationId===`1.${12+i}`&&r.followUpAcceptedBundleSha256===FOLLOWUP_SHA&&r.followUpRecordId===row.id&&r.statusAsOf==='2025-10-10'&&r.currentComplianceVerified===false&&r.historicalStatus==='reported_not_completed'&&r.assurance.startsWith('No assurance'),'Recommendation scope mismatch'));
 return {bundle:b,review,followUpRecord:row,auditReview};
}
export function validateService(b,review,compensation){
 published(b,review,SERVICE_SHA);const l=b.institutionalLink;require(b.schemaVersion==='ambulance-service-evidence-v1'&&l.acceptedCompensationBundleSha256===AMBULANCE_SHA&&l.acceptedCompensationId===compensation.id&&l.causalSpendingRelationshipEstablished===false&&l.contractOrTransactionId===null&&b.source.sha256===compensation.source.sha256,'Service link mismatch');
 require(b.responseStandards.length===6&&b.responseResults.length===2&&b.offloadResults.length===14&&b.offloadStandard.directiveRecipientAsReported==='Nova Scotia Health'&&b.offloadStandard.iwkDirectiveApplicabilityIndependentlyEstablished===false,'Service populations mismatch');
 b.responseStandards.forEach((r,i)=>require(r.withinMinutes===[9,15,30,15,20,40][i]&&r.targetPercent===80&&r.effectiveDatesEstablished===false,'Category threshold mismatch'));
 b.responseResults.forEach((r,i)=>require(r.reportedOnTimePercent===[69,64][i]&&r.targetPercent===90&&r.denominatorCount===null&&r.sourcePeriodLabel==='July 2022'&&r.sourceStage.includes('unaudited'),'Consolidated result mismatch'));
 require(b.offloadResults.filter(r=>r.role==='hospital').length===12&&b.offloadResults.filter(r=>r.role==='aggregate').length===2&&b.offloadResults[2].populationNote==='Patients aged 16 years and younger only','Offload population mismatch');
 return {bundle:b,review};
}
export async function getAmbulance(audits,auditReview,signal,fetcher=fetch){const review=await verifiedJSON('data/ambulance/compensation-review.json',AMBULANCE_REVIEW_SHA,null,signal,fetcher);const b=await verifiedJSON('data/ambulance/compensation.json',AMBULANCE_SHA,null,signal,fetcher);return validateAmbulance(b,review,audits,auditReview);}
export async function getAmbulanceService(compensation,signal,fetcher=fetch){const r=await verifiedJSON('data/ambulance/service-review.json',SERVICE_REVIEW_SHA,null,signal,fetcher);const b=await verifiedJSON('data/ambulance/service.json',SERVICE_SHA,null,signal,fetcher);return validateService(b,r,compensation);}
