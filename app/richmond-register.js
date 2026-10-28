import {verifiedJSON} from './tenders.js';
export const RICHMOND_HASH='90cf613e0e8054e47dab52d29b8a90bfea359745c96bfbe9cfc30e8d488cc4ca';
export const RICHMOND_REVIEW_HASH='7511e32f7a23e444a140de61eeca2c800ffcbf0a6adc50672ed8006e8cdcc16d';
export const RICHMOND_SECTIONS=['GENERAL','ONLINE UTILITY','WATER','ONLINE PAYMENTS'];
const need=(ok,message)=>{if(!ok)throw Error(message);};
export function sourceCents(text){need(typeof text==='string'&&/^\d+\.\d{2}$/.test(text),'Expected source decimal amount');return BigInt(text.replace('.',''));}
export function faceSum(rows){const cents=rows.reduce((n,r)=>n+sourceCents(r.reportedAmount),0n);return `${cents/100n}.${String(cents%100n).padStart(2,'0')}`;}
export function validateRichmond(b,r){
 const p=b.publication,c=b.filterCoverage,s=b.source;
 need(b.schemaVersion==='richmond-organization-cheque-register-v1'&&b.kind==='reviewed_organization_cheque_register'&&b.publicationAuthorized===true&&p.allowed===true&&p.consequentialAllegation===false&&p.requiresMatchingIndependentReceipt===true&&r.status==='accepted'&&r.bundleSha256===RICHMOND_HASH&&p.reviewId===r.evidenceId&&p.reviewedOn===r.reviewedOn,'Richmond independent review mismatch');
 need(s.sourceId==='richmond-county-cheques-issued-2026-01'&&s.publisher==='County of Richmond'&&s.retrievalIsChequeDate===false&&b.scope.geography==='not_Halifax'&&b.scope.sourcePeriodStart==='2026-01-01'&&b.scope.sourcePeriodEnd==='2026-01-31'&&s.rights.reuseLicence==='not_established','Richmond source scope mismatch');
 need(c.completeSourceRows===241&&c.publishedRows===85&&c.excludedRows===156&&c.exactAllowedVendorLabelKeys===54&&c.fullSourceTotalsPublished===false&&b.records.length===85,'Richmond bounded subset mismatch');
 const fields='accountingBasis,chequeDate,chequeDateSourceText,clearanceVerified,currency,decisionId,id,identifierBasis,multiplier,officialChequeNumber,officialContractId,officialVendorId,reportedAmount,sourceAmountText,sourceAuditTrailCode,sourceChequebookId,sourceCurrencySymbol,sourceLocator,sourceRecordSha256,stage,unit,vendorIdentityStatus,vendorSourceLabel,voidStatus'.split(',').sort().join('|');
 const ids=new Set(),keys=new Set(),vendors=new Set();
 for(const x of b.records){
  need(Object.keys(x).sort().join('|')===fields&&!ids.has(x.id)&&!keys.has(x.sourceChequebookId+'|'+x.officialChequeNumber)&&/^richmond-register-[a-f0-9]{64}$/.test(x.id),'Richmond row shape or uniqueness mismatch');
  need(x.stage==='source_reported_issued_cheque_or_online_register_entry'&&x.currency===null&&x.sourceCurrencySymbol==='$'&&x.unit==='source_dollars_currency_unspecified'&&x.multiplier===1&&x.clearanceVerified===false&&x.accountingBasis==='not_established'&&x.officialContractId===null&&x.decisionId===null&&x.voidStatus==='not_marked_void_in_source'&&x.vendorIdentityStatus==='explicit_organization_or_public_body_source_label_not_verified_legal_entity','Richmond financial or identity boundary mismatch');
  need(RICHMOND_SECTIONS.includes(x.sourceChequebookId)&&/^2026-01-\d{2}$/.test(x.chequeDate)&&x.chequeDate>='2026-01-01'&&x.chequeDate<='2026-01-31'&&Number.isInteger(x.sourceLocator.pdfPage)&&x.sourceLocator.pdfPage>=1&&x.sourceLocator.pdfPage<=7&&Number.isInteger(x.sourceLocator.dataRowOnPage)&&x.sourceLocator.dataRowOnPage>0&&x.sourceAmountText.replaceAll(',','')===x.reportedAmount,'Richmond date, locator or amount mismatch');
  sourceCents(x.reportedAmount);ids.add(x.id);keys.add(x.sourceChequebookId+'|'+x.officialChequeNumber);vendors.add(x.officialVendorId+'|'+x.vendorSourceLabel);
 }
 need(vendors.size===54&&faceSum(b.records)==='482855.06'&&b.filteredAmountSummary.amount==='482855.06'&&b.filteredAmountSummary.currency===null&&b.filteredAmountSummary.records===85&&b.filteredAmountSummary.voidMarkedRows===0&&b.filteredAmountSummary.scope==='filtered_displayed_subset_only_not_full_register_or_cleared_expenditure','Richmond exact-decimal subset mismatch');
 for(const [section,count] of [['GENERAL',65],['ONLINE UTILITY',2],['WATER',14],['ONLINE PAYMENTS',4]])need(b.records.filter(r=>r.sourceChequebookId===section).length===count&&c.rowsBySection.find(r=>r.sourceChequebookId===section)?.publishedRows===count,'Richmond section mismatch');
 return b;
}
export function filterRichmond(b,{q='',section='',from='',to=''}={}){
 need(!section||RICHMOND_SECTIONS.includes(section),'Unknown register section');for(const date of [from,to])need(!date||/^2026-01-(0[1-9]|[12]\d|3[01])$/.test(date),'Dates must be within January 2026');need(!from||!to||from<=to,'Date range is reversed');
 const query=q.trim().toLocaleLowerCase('en-CA');return b.records.filter(r=>(!section||r.sourceChequebookId===section)&&(!from||r.chequeDate>=from)&&(!to||r.chequeDate<=to)&&(!query||[r.id,r.vendorSourceLabel,r.officialVendorId,r.officialChequeNumber].some(v=>v.toLocaleLowerCase('en-CA').includes(query))));
}
export async function getRichmond(signal,fetcher=fetch){const review=await verifiedJSON('data/richmond-register/publication-review.json',RICHMOND_REVIEW_HASH,null,signal,fetcher);const bundle=validateRichmond(await verifiedJSON('data/richmond-register/records.json',RICHMOND_HASH,null,signal,fetcher),review);return{bundle,review};}
