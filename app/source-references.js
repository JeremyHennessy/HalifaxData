import {verifiedJSON} from './tenders.js';
import {searchRows} from './model.js';
export const CONTEXT={
 'source-references':{sha:'0b51f63c17d60ad1214fa53660a74b67423f4cecdb6b7aa819d81b1b4fa8d47e',receipt:'35f03ca1aac284128831862f34f7629a4245915e80de543255de0c2e9f03f80a',schema:'source-reference-coverage-v1'},
 'procurement-methodology':{sha:'96e6302b93413c98f54c2ea92f82f7a313a74144df5bb5a909f8b41ecae58f4c',receipt:'688c63710c2b743e25abb367ab0d24f248079f52241273274c5a8a8649c1ea6c',schema:'procurement-source-quality-annotation-v1'}
};
export const TENDER_TARGET='4118d8b43061fafc195c9b65504f7ef8589edd4cfec93ddc62e9a3126bbce062';
export function validateContext(bundle,review,kind){
 const c=CONTEXT[kind],p=bundle?.publication;
 if(!c||bundle.schemaVersion!==c.schema||review.status!=='accepted'||review.bundleSha256!==c.sha||p?.allowed!==true||p.consequentialAllegation!==false||p.reviewId!==review.evidenceId||p.reviewedOn!==review.reviewedOn)throw new Error('Source context review mismatch');
 if(kind==='source-references'){
 const refs=bundle.references;
 if(refs.length!==139||new Set(refs.map(r=>r.id)).size!==139||new Set(refs.map(r=>r.officialURL)).size!==121||new Set(refs.filter(r=>r.reviewedSubsetAvailable).map(r=>r.officialURL)).size!==4||refs.some(r=>r.completeSourceCoverageVerified!==false||r.ongoingRefreshVerified!==false)||bundle.evidenceCatalogCheckpointAt!=='2026-10-28T12:34:39Z')throw new Error('Reference checkpoint mismatch');
 }else if(bundle.target.tenderIndexSha256!==TENDER_TARGET||bundle.kind!=='source_methodology_annotation_not_investigation'||bundle.example.noRiskInference!==true)throw new Error('Methodology target mismatch');
 return bundle;
}
export async function getContext(kind,signal,fetcher=fetch){
 const c=CONTEXT[kind];if(!c)throw new Error('Unknown source context');
 const review=await verifiedJSON(`data/${kind}/publication-review.json`,c.receipt,null,signal,fetcher);
 const bundle=validateContext(await verifiedJSON(`data/${kind}/records.json`,c.sha,null,signal,fetcher),review,kind);
 if(kind==='procurement-methodology')await verifiedJSON('data/tenders/tender-index.json',TENDER_TARGET,null,signal,fetcher);
 return {bundle,review};
}
export function filterReferences(bundle,{q='',group='',stage=''}={}){
 let rows=searchRows(bundle.references,q,['id','titleAsInventory','group','jurisdiction','officialURL']);
 if(group)rows=rows.filter(r=>r.group===group);
 if(stage==='published')rows=rows.filter(r=>r.reviewedSubsetAvailable);
 if(stage==='reference')rows=rows.filter(r=>!r.reviewedSubsetAvailable);
 if(stage==='capture')rows=rows.filter(r=>r.retainedCaptureEvidenceVerified);
 return rows;
}
export const OPTIONAL_COLLECTION_ROUTES={
 'water-projects':'#/water-projects',
 'municipal-capital':'#/municipal-capital',
 'housing-audit':'#/audits?case=housing-contracts',
 ambulance:'#/audits?case=ambulance-contract',
 'shelburne-grants':'#/shelburne-grants'
};
