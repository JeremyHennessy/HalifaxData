/* Personal review state stays in this browser. Export/import is the backup path. */
const b23StorageKey = 'halifaxdata.workspace.v1';
const b23Filters = ['year','unit','spendingYear','spendingType','spendingQuery','vendorQuery','build019LifecyclePriority','build019LifecycleTrack'];
let b23Store = {version:1, items:[]}, b23StorageError = '', b23Context = null, b23Current = null;
let b23Release = 'build023-development', b23OpenedLink = false;
try { const saved = JSON.parse(localStorage.getItem(b23StorageKey) || 'null'); if (saved?.version === 1 && Array.isArray(saved.items)) b23Store = saved; }
catch { b23StorageError = 'Saved data could not be read. Export any visible work before clearing browser storage.'; }
fetch('./release-manifest.json').then(r => r.ok ? r.json() : null).then(r => { if (r?.commit) b23Release = r.commit; }).catch(() => {});
const b23InitialParams = new URLSearchParams(location.search);
try { const f = JSON.parse(b23InitialParams.get('filters') || '{}'); for (const key of b23Filters) if (typeof f[key] === 'string' && f[key].length < 500) state[key] = f[key]; } catch { /* Invalid filters leave defaults intact. */ }
function b23SaveStore() {
  try { localStorage.setItem(b23StorageKey, JSON.stringify(b23Store)); b23StorageError = ''; return true; }
  catch { b23StorageError = 'Browser storage is unavailable or full. Export a backup now; changes are only in memory.'; return false; }
}
function b23Url(kind, id) {
  const u = new URL(location.href); u.search = ''; u.hash = kind === 'spending' ? 'spending' : 'signals';
  if (kind && id) { u.searchParams.set('evidence',kind); u.searchParams.set('id',id); }
  return u.href;
}
function b23Fingerprint(value) { return JSON.stringify(value); }
function b23CurrentFact(item) {
  if (item.kind === 'lifecycle') return b19InvestigationRows().find(r => r.investigation_id === item.id);
  if (item.kind === 'spending') return getRows(datasetStatus('spending').data).find(r => r.record_id === item.id);
  return null;
}
function b23Changed(item) {
  if (!item.watch || !['lifecycle','spending'].includes(item.kind)) return '';
  const ready = item.kind === 'lifecycle' ? state.build019LifecycleInvestigations?.status === 'ready' : datasetStatus('spending').status === 'ready';
  if (!ready) return 'Waiting for current evidence';
  const current = b23CurrentFact(item);
  if (!current) return 'Evidence no longer present in this release';
  return b23Fingerprint(current) !== item.fingerprint ? 'Evidence changed since saved review — open to compare' : 'No evidence change since saved review';
}
function b23Download(name, text, type='application/json') {
  const url = URL.createObjectURL(new Blob([text],{type})); const a = document.createElement('a');
  a.href=url; a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function b23Csv(value) { const s=String(value ?? ''); return '"'+(/^[=+\-@\t\r]/.test(s) ? "'" : '')+s.replaceAll('"','""')+'"'; }
function b23Export(item, format) {
  const packet={release:b23Release,exported_at:new Date().toISOString(),...item};
  if (format==='csv') {
    const rows=[['field','value'],...Object.entries(packet).map(([k,v])=>[k,typeof v==='object'?JSON.stringify(v):v])];
    b23Download('halifaxdata-evidence.csv',rows.map(r=>r.map(b23Csv).join(',')).join('\r\n'),'text/csv');
  } else if (format==='brief') {
    b23Download('halifaxdata-evidence-brief.md',`# ${item.title}\n\nRelease: ${b23Release}\nExported: ${packet.exported_at}\nEvidence: ${item.url}\nReviewer: ${item.reviewer || 'Unassigned'}\nStatus: ${item.status}\n\n## Notes\n${item.notes || ''}\n\n## Source evidence and limitations\n${item.text}\n\n${(item.sources || []).map(s=>`${s.label}: ${s.url}`).join('\n')}\n`,'text/markdown');
  } else b23Download('halifaxdata-evidence.json',JSON.stringify(packet,null,2));
}
const b23OriginalDrawer = openDrawer;
openDrawer = function(args) {
  b23OriginalDrawer(args);
  const body=$('#drawer-body'); const context=b23Context;
  const id=context?.id || `${state.view}:${args.title}`;
  const kind=context?.kind || 'snapshot';
  const prior=b23Store.items.find(i=>i.kind===kind&&i.id===id);
  b23Current={kind,id,title:args.title,url:context?b23Url(kind,id):location.href,
    text:body.innerText,sources:[...body.querySelectorAll('a[href]')].map(a=>({label:a.textContent,url:a.href})),
    fact:context?.fact || null,fingerprint:context?b23Fingerprint(context.fact):null,release:b23Release,
    notes:prior?.notes||'',reviewer:prior?.reviewer||'',status:prior?.status||'needs-evidence',watch:prior?.watch||false};
  body.insertAdjacentHTML('beforeend', `<section class="drawer-section b23-review"><h3>Save this investigation</h3><p>Notes are saved in this browser. Export a backup to keep or move your work.</p>
    <label>Review status <select id="b23-status">${['needs-evidence','reviewed','dismissed'].map(v=>`<option ${b23Current.status===v?'selected':''}>${v}</option>`).join('')}</select></label>
    <label>Reviewer <input id="b23-reviewer" maxlength="120" value="${escapeHtml(b23Current.reviewer)}"></label>
    <label>Notes <textarea id="b23-notes" maxlength="20000" rows="4">${escapeHtml(b23Current.notes)}</textarea></label>
    ${context?`<label><input type="checkbox" id="b23-watch" ${b23Current.watch?'checked':''}> Watch for changes when I next visit</label>`:''}
    <div class="b23-actions"><button id="b23-save">Save review</button><button data-b23-export="json">Export JSON</button><button data-b23-export="csv">Export CSV</button><button data-b23-export="brief">Evidence brief</button>${context?'<button id="b23-share-evidence">Copy evidence link</button>':''}</div><p id="b23-save-result" role="status"></p></section>`);
  function edited() { return {...b23Current,notes:$('#b23-notes').value,reviewer:$('#b23-reviewer').value,status:$('#b23-status').value,watch:!!$('#b23-watch')?.checked,updated_at:new Date().toISOString()}; }
  $('#b23-save').onclick=()=>{const item=edited();b23Store.items=b23Store.items.filter(i=>!(i.kind===item.kind&&i.id===item.id));b23Store.items.push(item);$('#b23-save-result').textContent=b23SaveStore()?'Review saved in this browser.':b23StorageError;};
  body.querySelectorAll('[data-b23-export]').forEach(b=>b.onclick=()=>b23Export(edited(),b.dataset.b23Export));
  if ($('#b23-share-evidence')) $('#b23-share-evidence').onclick=async()=>{try{await navigator.clipboard.writeText(b23Current.url);$('#b23-save-result').textContent='Evidence link copied. Private notes are not included.';}catch{$('#b23-save-result').textContent=b23Current.url;}};
};
const b23OriginalLifecycle=b19ShowInvestigation;
b19ShowInvestigation=function(id){const fact=b19InvestigationRows().find(r=>r.investigation_id===id);if(!fact)return;b23Context={kind:'lifecycle',id,fact};try{b23OriginalLifecycle(id);}finally{b23Context=null;}};
const b23OriginalSpending=showSpendingRow;
showSpendingRow=function(index){const fact=getRows(datasetStatus('spending').data)[index];if(!fact)return;b23Context={kind:'spending',id:fact.record_id,fact};try{b23OriginalSpending(index);}finally{b23Context=null;}};
function b23OpenSaved(index) {
 const item=b23Store.items[index];if(!item)return;
 if(item.kind==='lifecycle'&&b23CurrentFact(item))return b19ShowInvestigation(item.id);
 if(item.kind==='spending'&&b23CurrentFact(item))return showSpendingRow(getRows(datasetStatus('spending').data).findIndex(r=>r.record_id===item.id));
 openDrawer({title:item.title,eyebrow:'SAVED EVIDENCE SNAPSHOT',html:`<p>Saved ${escapeHtml(item.updated_at)}. This is the saved snapshot; current evidence is unavailable here.</p><pre class="b23-snapshot">${escapeHtml(item.text)}</pre>`});
}
async function b23Import(file) {
 if(!file||file.size>5000000)throw Error('Choose a workspace JSON backup smaller than 5 MB.');
 const data=JSON.parse(await file.text());
 if(data.version!==1||!Array.isArray(data.items)||data.items.length>1000)throw Error('Unsupported workspace backup.');
 const items=data.items.map(i=>{
  if(!['snapshot','lifecycle','spending'].includes(i.kind)||typeof i.id!=='string'||typeof i.title!=='string'||typeof i.text!=='string'||!['needs-evidence','reviewed','dismissed'].includes(i.status))throw Error('Invalid review record.');
  const clean={};for(const key of ['id','title','text','notes','reviewer','updated_at','release','fingerprint'])clean[key]=typeof i[key]==='string'?i[key].slice(0,key==='fingerprint'?500000:100000):'';
  return {...clean,kind:i.kind,status:i.status,watch:i.watch===true,url:b23Url(i.kind,i.id),sources:(Array.isArray(i.sources)?i.sources:[]).filter(s=>typeof s.label==='string'&&typeof s.url==='string'&&/^https?:\/\//.test(s.url)).slice(0,200)};
 });
 for(const item of items){if(!b23Store.items.some(i=>i.kind===item.kind&&i.id===item.id))b23Store.items.push(item);}
 b23SaveStore();render();
}
function b23Enhance() {
 document.querySelectorAll('[data-b23-page]').forEach(b=>b.onclick=()=>{state.b23SpendingPage=Number(b.dataset.b23Page);render();});
 // Existing evidence rows retain their mouse behavior and gain keyboard access.
 document.querySelectorAll('#content tr[data-spending-index], #content tr[data-vendor-index], #content tr[data-financial-index]').forEach(row=>{row.tabIndex=0;row.setAttribute('role','button');row.setAttribute('aria-label','Open evidence: '+row.textContent.trim().slice(0,150));row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();row.click();}};});
 if(state.view==='signals'&&!$('#b23-workspace')) {
  const host=$('#content .page-stack')||$('#content');
  host.insertAdjacentHTML('afterbegin',`<section id="b23-workspace" class="panel"><header class="panel-header"><div><h2>Saved investigations</h2><p>Private to this browser. Watchlist changes are checked on each visit; no background alerts are sent.</p></div></header><div class="panel-body"><div class="b23-actions"><button id="b23-backup">Export workspace backup</button><label>Import backup <input id="b23-import" type="file" accept="application/json,.json"></label><button id="b23-share-view">Copy filtered view link</button></div><p id="b23-workspace-status" role="status">${escapeHtml(b23StorageError)}</p>${b23Store.items.length?b23Store.items.map((item,i)=>`<div class="drawer-callout"><button data-b23-open="${i}">${escapeHtml(item.title)}</button><p>${escapeHtml(item.status)} · ${escapeHtml(item.reviewer||'Unassigned')} · ${escapeHtml(item.updated_at||'')}</p><p>${escapeHtml(b23Changed(item))}</p><p>${escapeHtml(item.notes||'')}</p></div>`).join(''):'<p>Open any evidence drawer and select Save review to begin.</p>'}</div></section>`);
  $('#b23-backup').onclick=()=>b23Download('halifaxdata-workspace.json',JSON.stringify(b23Store,null,2));
  $('#b23-import').onchange=async e=>{try{await b23Import(e.target.files[0]);}catch(error){$('#b23-workspace-status').textContent=error.message;}};
  $('#b23-share-view').onclick=async()=>{const u=new URL(location.href);u.search='';u.searchParams.set('filters',JSON.stringify(Object.fromEntries(b23Filters.filter(k=>typeof state[k]==='string').map(k=>[k,state[k]]))));try{await navigator.clipboard.writeText(u.href);$('#b23-workspace-status').textContent='Filtered view link copied.';}catch{$('#b23-workspace-status').textContent=u.href;}};
  document.querySelectorAll('[data-b23-open]').forEach(b=>b.onclick=()=>b23OpenSaved(Number(b.dataset.b23Open)));
 }
 if(!b23OpenedLink&&b23InitialParams.has('id')) {
  const kind=b23InitialParams.get('evidence'),id=b23InitialParams.get('id');
  if(kind==='lifecycle'&&state.build019LifecycleInvestigations?.status==='ready'){b23OpenedLink=true;b19ShowInvestigation(id);}
  if(kind==='spending'&&datasetStatus('spending').status==='ready'){b23OpenedLink=true;const index=getRows(datasetStatus('spending').data).findIndex(r=>r.record_id===id);if(index>=0)showSpendingRow(index);}
 }
}
const b23PreviousRender=render;
render=function(){b23PreviousRender();b23Enhance();};
