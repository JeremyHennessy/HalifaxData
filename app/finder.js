import {searchRows} from './model.js';

// Editorial navigation groups only. Membership does not join or reconcile records.
export const topics=[
 {id:'budgets',label:'Budgets & accounts',collectionIds:['foundation','budget','authorizations','institution','cash-bridge','governance','nshealth','municipal','municipal-capital','hrm-capital']},
 {id:'contracts',label:'Contracts & suppliers',collectionIds:['tenders','suppliers','richmond-register','ambulance','housing-audit','hrm-winter']},
 {id:'municipal',label:'Municipal services',collectionIds:['hrm-winter','hrm-facilities','hrm-capital','hrm-audits','water-projects','richmond-register','shelburne-grants','municipal-capital','municipal','reporting']},
 {id:'health-housing',label:'Health & housing',collectionIds:['physician-categories','nshealth','ambulance','housing-audit']},
 {id:'oversight',label:'Audits & oversight',collectionIds:['audits','hrm-audits','hrm-capital','hrm-facilities','hrm-winter','ambulance','housing-audit','reporting','governance']},
 {id:'transfers-grants',label:'Transfers & grants',collectionIds:['transfers','transfer-links','shelburne-grants']}
];
export const validTopic=value=>topics.some(t=>t.id===value)?value:'';

// A directory of already-reviewed public material, not an entity graph or full-text record index.
export function evidenceDirectory(coverage,foundation){
 return [
  ...coverage.collections.map(c=>({id:'collection:'+c.id,kind:'collection',title:c.title,summary:c.scope,context:`${c.count} ${c.countUnit}`,route:c.route,topics:topics.filter(t=>t.collectionIds.includes(c.id)).map(t=>t.id),reviewedOn:c.reviewedOn,reviewPath:c.reviewPath})),
  ...foundation.moneyFacts.map(f=>({id:'fact:'+f.id,kind:'fact',title:f.title,summary:`${f.entity} · ${f.period.label} · ${f.stage.replaceAll('_',' ')} · ${f.measureType}`,context:`Source units: ${f.unit.replaceAll('_',' ')}. Open the record for accounting definitions and provenance.`,route:`#/record/${encodeURIComponent(f.id)}`,topics:['budgets'],reviewedOn:null,reviewPath:null}))
 ];
}
export function findEvidence(directory,query='',kind='',topic=''){
 const selected=['collection','fact'].includes(kind)?kind:'',selectedTopic=validTopic(topic);
 return searchRows(directory,query,['title','summary','context']).filter(r=>(!selected||r.kind===selected)&&(!selectedTopic||r.topics.includes(selectedTopic)));
}
export function collectionTopics(directory){
 return topics.map(t=>({id:t.id,label:t.label,count:directory.filter(r=>r.kind==='collection'&&r.topics.includes(t.id)).length})).filter(t=>t.count>0);
}
export const questions=[
 ['What spending was authorized?','authorizations','Inspect approved amounts without treating them as payments.'],
 ['Who appears in procurement records?','tenders','Search source observations; awards are not final bills.'],
 ['Do the published figures agree?','reporting','Review an unresolved municipal reporting question and its competing explanations.'],
 ['How does cash differ from an annual deficit?','cash-bridge','Follow the reviewed statement calculations, not an inferred bank ledger.'],
 ['Can a forecast be traced to a payment disclosure?','transfer-links','Inspect the explicit program/year mapping and what it cannot establish.'],
 ['Were audit recommendations completed?','audits','Read historical source-reported follow-up, not a claim about today’s status.'],
 ['What did the winter-operations audit measure?','hrm-winter','Keep historical contractor costs, unknown in-house costs and separate report samples distinct.'],
 ['What did the facility audit report about assessments?','hrm-facilities','Read two historical assessment groups, not a current building-safety finding.'],
 ['What did the capital-budget audit test?','hrm-capital','Inspect three tested business-unit aggregates, not the entire Capital Plan or payments.']
];
