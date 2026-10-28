import {validateAuthorizations} from './authorizations.js';
import {purposeFor,validatePurpose} from './authorization-purpose.js';
export const AUTHORIZATION_SHA='bca870a30c64807ef881d67d7c8680df748160bcd208b2f05bcdf4fc19f5c6c5';
export function buildAuthorizationTrace(bundle,review,id,purpose=null,purposeReview=null){
 if(review.bundleSha256!==AUTHORIZATION_SHA)throw Error('The admitted authorization snapshot is required');
 validateAuthorizations(bundle,review);
 const matches=bundle.orders.flatMap(order=>order.records.filter(record=>record.id===id).map(record=>({order,record})));
 if(matches.length!==1)throw Error('That exact authorization record is not available');
 const {order,record}=matches[0];let context=null;
 if(purpose&&purposeReview){validatePurpose(purpose,purposeReview,bundle,review);if(purposeFor(purpose,order,record))context={annotation:purpose,review:purposeReview};}
 const target={recordId:record.id,orderNumber:order.orderNumber,clause:record.clause,fiscalYear:record.fiscalYear,entityAsReported:record.appropriatedEntityAsReported};
 const stages=[
  {id:'budget',title:'Budget origin',status:'not_linked',explanation:'No exact budget-line link has been established for this clause.'},
  {id:'authorization',title:'Recorded authorization',status:'source_record',explanation:`Order ${order.orderNumber}, clause ${record.clause}, Schedule A Column II.`,recordIds:[record.id]},
  {id:'contract',title:'Contract or other spending route',status:'not_linked',explanation:'No linked procurement, grant, transfer or internal-spending record is established.'},
  {id:'payment',title:'Payment',status:'not_linked',explanation:'No transaction-level payment link is established for this clause.'},
  {id:'delivery',title:'Delivery and results',status:'not_linked',explanation:'No linked acceptance, completion or outcome record is established.'}
 ];
 const nextRecords=[
  {id:'budget',question:'Which budget line or initiative does this clause adjust?',recordsNeeded:'The appropriation account and supporting budget or initiative breakdown.',matchRequired:'An explicit account, program or initiative identifier connecting the breakdown to this order and clause—not a similar amount.'},
  {id:'decision',question:'What decision and authority support this authorization?',recordsNeeded:'Supporting decision record and applicable statutory or policy provisions in force for the relevant dates.',matchRequired:'An exact order reference and dated provision. The order alone does not establish an elected vote or an independent legal interpretation.'},
  {id:'contract',question:'How was the authorized amount used?',recordsNeeded:'A documented breakdown of procurement, grants, transfers or internal spending, then the relevant agreement or account records.',matchRequired:'An explicit link from the authorized initiative/account to a contract, grant or other spending identifier. Not every authorization requires a contract.'},
  {id:'payment',question:'What was actually paid, to whom and when?',recordsNeeded:'Payment transactions or a reconciled ledger with transaction IDs, dates, payees, amounts and accounting basis.',matchRequired:'A documented account/initiative/agreement link and compatible period and gross/net definitions. Do not subtract unlinked amounts to infer a loss.'},
  {id:'delivery',question:'What was delivered or achieved?',recordsNeeded:'Acceptance records, completion reports, grant results or relevant service measures.',matchRequired:'An explicit project/agreement/program identifier and reporting period connecting results to the expenditure.'}
 ];
 return {schemaVersion:'authorization-evidence-trace-v1',kind:'investigative_workbench_not_finding',target,stages,nextRecords,scope:'This is a trail through currently linked evidence, not a finding that money was misspent. Not linked means unknown here, not that a record, payment or activity does not exist.',sourceScope:'One selected clause from an independently reviewed 23-clause projection. The source review does not establish the missing links in this workbench.',authorization:{record,order:{id:order.id,orderNumber:order.orderNumber,fiscalYear:order.fiscalYear,fiscalYearEnd:order.fiscalYearEnd,orderDate:order.orderDate,effectiveDate:order.effectiveDate,recommendationDate:order.recommendationDate,statutoryReferenceAsReported:order.statutoryReferenceAsReported,sourceURL:order.sourceURL,pdfURL:order.pdfURL,sourceSha256:order.sourceSha256,pdfSha256:order.pdfSha256,sourceOwnedRecordId:order.sourceOwnedRecordId,retrievedAt:order.retrievedAt,pdfRetrievedAt:order.pdfRetrievedAt},sourceBundleSha256:review.bundleSha256,review},purposeContext:context};
}
