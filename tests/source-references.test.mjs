import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {webcrypto} from 'node:crypto';
import {getContext,filterReferences,validateContext,CONTEXT,OPTIONAL_COLLECTION_ROUTES} from '../app/source-references.js';
globalThis.crypto??=webcrypto;
const read=async path=>fs.readFile(new URL('../'+path,import.meta.url));
const fetcher=async path=>new Response(await read(path));
test('exact reviewed reference checkpoint and receipt load without source network calls',async()=>{
 const {bundle:b}=await getContext('source-references',null,fetcher);
 assert.equal(b.references.length,139);assert.equal(filterReferences(b,{stage:'published'}).length,4);
 assert.deepEqual(filterReferences(b,{stage:'published'}).map(r=>r.id),['SI006','SI011','SI023','SI024']);
 assert.equal(filterReferences(b,{stage:'capture'}).length,3);
 assert.equal(filterReferences(b,{stage:'reference'}).length,135);
 assert.equal(filterReferences(b,{q:'SI003'})[0].reviewedSubsetAvailable,false);
 assert.equal(filterReferences(b,{q:'nonexistent-zzzz'}).length,0);
 assert.equal(filterReferences(b,{q:'SI006',stage:'capture'}).length,0);
 assert.equal(b.evidenceCatalogCheckpointAt,'2026-10-28T12:34:39Z');
});
test('metadata search and groups preserve exact identities and do not make publisher joins',async()=>{
 const {bundle:b}=await getContext('source-references',null,fetcher);
 for(const group of new Set(b.references.map(r=>r.group)))assert.ok(filterReferences(b,{group}).every(r=>r.group===group));
 assert.ok(filterReferences(b,{q:'public accounts'}).every(r=>!r.reviewedSubsetAvailable));
 assert.equal(b.references.find(r=>r.id==='SI006').retainedCaptureEvidenceVerified,false);
});
test('methodology is tied to exact accepted tender index, not a new collection',async()=>{
 const {bundle:b}=await getContext('procurement-methodology',null,fetcher);
 assert.equal(b.snapshotFacts.observationCount,33670);assert.equal(b.snapshotFacts.distinctTenderStrings,32002);
 assert.equal(b.example.sourceRowId,'row-rzyy_crj2-ah2f');assert.equal(b.kind,'source_methodology_annotation_not_investigation');
 assert.match(b.amountCaveat,/Do not sum/);
 const coverage=JSON.parse(await read('data/collection-coverage.json'));
 assert.equal(coverage.collections.length,21);
 assert.ok(!coverage.collections.some(c=>Object.keys(CONTEXT).includes(c.id)));
});
for(const kind of Object.keys(CONTEXT)){
 test(kind+' rejects changed artifact and changed receipt bytes',async()=>{
  for(const file of ['records.json','publication-review.json'])await assert.rejects(getContext(kind,null,async path=>new Response(Buffer.concat([await read(path),Buffer.from(path===`data/${kind}/${file}`?' ':'')]))),/checksum/);
 });
 test(kind+' does not continue past missing or unaccepted receipt',async()=>{
  await assert.rejects(getContext(kind,null,async()=>new Response('',{status:404})),/unavailable/);
  const b=JSON.parse(await read(`data/${kind}/records.json`)),r=JSON.parse(await read(`data/${kind}/publication-review.json`));
  assert.throws(()=>validateContext(b,{...r,status:'pending'},kind),/review mismatch/);
 });
}
test('methodology target drift fails closed',async()=>{
 await assert.rejects(getContext('procurement-methodology',null,async path=>new Response(Buffer.concat([await read(path),Buffer.from(path==='data/tenders/tender-index.json'?' ':'')]))),/checksum/);
});
test('aborted request cannot publish checkpoint',async()=>{
 const controller=new AbortController();controller.abort();await assert.rejects(getContext('source-references',controller.signal,fetcher),/Cancelled/);
});

test('unavailable optional collections link to their exact explorer or story',()=>{
 assert.equal(OPTIONAL_COLLECTION_ROUTES['municipal-capital'],'#/municipal-capital');
 assert.equal(OPTIONAL_COLLECTION_ROUTES['housing-audit'],'#/audits?case=housing-contracts');
 assert.equal(OPTIONAL_COLLECTION_ROUTES.ambulance,'#/audits?case=ambulance-contract');
 assert.equal(OPTIONAL_COLLECTION_ROUTES['shelburne-grants'],'#/shelburne-grants');
});
