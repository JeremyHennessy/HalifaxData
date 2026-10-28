import {searchRows} from './model.js';
// A directory of already-reviewed public material, not an entity graph or full-text record index.
export function evidenceDirectory(coverage,foundation){
 return [...coverage.collections.map(c=>({id:'collection:'+c.id,kind:'collection',title:c.title,summary:c.scope,context:`${c.count} ${c.countUnit}`,route:c.route})),...foundation.moneyFacts.map(f=>({id:'fact:'+f.id,kind:'fact',title:f.title,summary:`${f.entity} · ${f.period.label} · ${f.stage.replaceAll('_',' ')} · ${f.measureType}`,context:`Source units: ${f.unit.replaceAll('_',' ')}. Open the record for accounting definitions and provenance.`,route:`#/record/${encodeURIComponent(f.id)}`}))];
}
export function findEvidence(directory,query='',kind=''){
 const selected=['collection','fact'].includes(kind)?kind:'';
 return searchRows(directory,query,['title','summary','context']).filter(r=>!selected||r.kind===selected);
}
export const questions=[
 ['What spending was authorized?','authorizations','Inspect approved amounts without treating them as payments.'],
 ['Who appears in procurement records?','tenders','Search source observations; awards are not final bills.'],
 ['Do the published figures agree?','reporting','Review an unresolved municipal reporting question and its competing explanations.'],
 ['How does cash differ from an annual deficit?','cash-bridge','Follow the reviewed statement calculations, not an inferred bank ledger.'],
 ['Can a forecast be traced to a payment disclosure?','transfer-links','Inspect the explicit program/year mapping and what it cannot establish.'],
 ['Were audit recommendations completed?','audits','Read historical source-reported follow-up, not a claim about today’s status.']
];
