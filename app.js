const state = { compensation: null, sources: null, view: 'overview', selectedName: null };
const fmtMoney = new Intl.NumberFormat('en-CA', { style:'currency', currency:'CAD', maximumFractionDigits:0 });
const fmtNum = new Intl.NumberFormat('en-CA');
const content = document.querySelector('#content');
const title = document.querySelector('#view-title');

Promise.all([
  fetch('./data/generated/compensation.json').then(r => { if(!r.ok) throw new Error('compensation data'); return r.json(); }),
  fetch('./data/sources.json').then(r => { if(!r.ok) throw new Error('source registry'); return r.json(); })
]).then(([compensation, sources]) => {
  state.compensation = compensation; state.sources = sources;
  document.querySelector('#coverage-label').textContent = `${compensation.metadata.min_year}–${compensation.metadata.max_year} disclosure seed`;
  render();
}).catch(err => { content.innerHTML = `<div class="panel"><h2>Data load failed</h2><p class="panel-sub">${escapeHtml(err.message)}</p></div>`; });

document.querySelector('#nav').addEventListener('click', e => {
  const btn = e.target.closest('[data-view]'); if(!btn) return;
  state.view = btn.dataset.view;
  document.querySelectorAll('.nav-item').forEach(x => x.classList.toggle('active', x === btn));
  render();
});

function render(){
  if(!state.compensation || !state.sources) return;
  ({overview:renderOverview, compensation:renderCompensation, flags:renderFlags, sources:renderSources}[state.view] || renderOverview)();
}
function setTitle(t){ title.textContent=t; }
function groupBy(rows, keyFn){ const grouped=new Map(); for(const row of rows){ const key=keyFn(row); if(!grouped.has(key)) grouped.set(key,[]); grouped.get(key).push(row); } return grouped; }
function money(v){ return v == null ? '—' : fmtMoney.format(v); }
function pct(v){ return `${(v*100).toFixed(1)}%`; }
function escapeHtml(s=''){ return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function records(){ return state.compensation.records; }
function latestYear(){ return Math.max(...records().map(r=>r.fiscal_year_end)); }
function latestRecords(){ const y=latestYear(); return records().filter(r=>r.fiscal_year_end===y); }

function computeSignals(){
  const byName = groupBy(records(), r => r.person_key);
  const signals=[];
  for(const [key, rows0] of byName){
    const rows=[...rows0].sort((a,b)=>a.fiscal_year_end-b.fiscal_year_end);
    for(let i=1;i<rows.length;i++){
      const a=rows[i-1], b=rows[i];
      if(b.fiscal_year_end-a.fiscal_year_end===1 && a.total>0){
        const change=(b.total-a.total)/a.total;
        if(Math.abs(change)>=.20) signals.push({type:'Year-over-year change',severity:Math.abs(change)>=.35?'high':'review',name:b.name,year:b.fiscal_year_end,detail:`Total disclosed compensation changed ${change>=0?'+':''}${pct(change)} from ${money(a.total)} to ${money(b.total)}.`,source:b.source_id});
      }
      if(a.position!==b.position || a.business_unit!==b.business_unit){
        signals.push({type:'Role/unit change',severity:'info',name:b.name,year:b.fiscal_year_end,detail:`Disclosure changed from ${a.position || 'unknown role'} / ${a.business_unit || 'unknown unit'} to ${b.position || 'unknown role'} / ${b.business_unit || 'unknown unit'}.`,source:b.source_id});
      }
    }
    rows.forEach(r=>{
      if(r.total>0 && r.benefits/r.total>=.10) signals.push({type:'Benefits concentration',severity:'review',name:r.name,year:r.fiscal_year_end,detail:`Benefits were ${pct(r.benefits/r.total)} of disclosed total (${money(r.benefits)}). This may reflect severance, allowances or other permitted items and requires source review.`,source:r.source_id});
    });
  }
  return signals.sort((a,b)=>b.year-a.year || (a.severity==='high'?-1:1));
}

function renderOverview(){
  setTitle('Financial intelligence overview');
  const src=state.sources.sources; const comp=records(); const signals=computeSignals(); const yr=latestYear();
  const units=new Set(comp.filter(r=>r.fiscal_year_end===yr).map(r=>r.business_unit).filter(Boolean));
  content.innerHTML=`
    <div class="banner"><strong>Current data state:</strong> ${escapeHtml(state.compensation.metadata.note)} The UI never treats this seed as a complete population.</div>
    <div class="grid metrics">
      <div class="metric"><div class="label">Official sources mapped</div><div class="value">${fmtNum.format(src.length)}</div><div class="sub">HRM, Province, Halifax Water & regulators</div></div>
      <div class="metric"><div class="label">Verified compensation rows</div><div class="value">${fmtNum.format(comp.length)}</div><div class="sub">Partial seed pending automated full extraction</div></div>
      <div class="metric"><div class="label">Compensation history</div><div class="value">${state.compensation.metadata.min_year}–${state.compensation.metadata.max_year}</div><div class="sub">$100k+ disclosure threshold</div></div>
      <div class="metric"><div class="label">Latest units represented</div><div class="value">${units.size}</div><div class="sub">Seed only; not a workforce count</div></div>
    </div>
    <div class="grid two-col">
      <div class="panel"><h2>What HalifaxData will reconcile</h2><p class="panel-sub">Every signal should be traceable back to an official document or machine-readable endpoint.</p>${reconciliationHtml()}</div>
      <div class="panel"><h2>Recent review signals</h2><p class="panel-sub">Neutral screening signals, not findings of wrongdoing.</p><div class="signal-list">${signals.slice(0,6).map(signalHtml).join('') || '<div class="empty">No signals in seed.</div>'}</div></div>
    </div>`;
}
function reconciliationHtml(){
  const items=[
    ['Budget → actual','Approved operating/capital plans versus quarterly and audited actuals.'],
    ['Project → amendments','Original capital authorization versus carry-forwards, Council increases and final spend.'],
    ['Tender → vendor','Competition method, award, vendor, amount and subsequent contract amendments.'],
    ['Payroll → history','Annual disclosed compensation, role/unit changes and unusual benefit concentrations.'],
    ['Reserve → withdrawal','Reserve balances, transfers, Council authorizations and stated purpose.'],
    ['External funding → delivery','Federal/provincial commitments versus municipal project execution.']
  ];
  return `<div class="signal-list">${items.map(([a,b])=>`<div class="signal"><div><strong>${a}</strong><p>${b}</p></div><span class="badge">planned</span></div>`).join('')}</div>`;
}
function signalHtml(s){return `<div class="signal"><div><strong>${escapeHtml(s.name)} · ${s.year}</strong><p>${escapeHtml(s.type)} — ${escapeHtml(s.detail)}</p></div><span class="badge ${s.severity==='high'?'high':s.severity==='review'?'review':''}">${s.severity==='high'?'high review':s.severity==='review'?'review':'context'}</span></div>`}

function renderCompensation(){
  setTitle('Employee compensation history');
  const years=[...new Set(records().map(r=>r.fiscal_year_end))].sort((a,b)=>b-a); const units=[...new Set(records().map(r=>r.business_unit).filter(Boolean))].sort();
  content.innerHTML=`<div class="banner"><strong>Disclosure limitation:</strong> HRM's statement covers people receiving $100,000 or more in the fiscal year. Absence from a year cannot be interpreted as departure from employment or zero compensation.</div>
  <div class="panel"><div class="section-title"><div><h2>Disclosed compensation</h2><p class="panel-sub">Click a row to inspect the available history.</p></div><span class="count" id="row-count"></span></div>
    <div class="toolbar"><input id="comp-search" placeholder="Search employee, position or business unit" aria-label="Search compensation"/><select id="year-filter"><option value="all">All years</option>${years.map(y=>`<option value="${y}" ${y===latestYear()?'selected':''}>${y}</option>`).join('')}</select><select id="unit-filter"><option value="all">All business units</option>${units.map(u=>`<option>${escapeHtml(u)}</option>`).join('')}</select></div>
    <div id="comp-table"></div><div id="person-detail" class="detail"></div>
  </div>`;
  const update=()=>renderCompTable(document.querySelector('#comp-search').value,document.querySelector('#year-filter').value,document.querySelector('#unit-filter').value);
  ['#comp-search','#year-filter','#unit-filter'].forEach(sel=>document.querySelector(sel).addEventListener(sel==='#comp-search'?'input':'change',update)); update();
}
function renderCompTable(q,year,unit){
  q=q.toLowerCase().trim(); let rows=records().filter(r=>(year==='all'||String(r.fiscal_year_end)===year)&&(unit==='all'||r.business_unit===unit)&&(!q||`${r.name} ${r.position} ${r.business_unit}`.toLowerCase().includes(q))).sort((a,b)=>b.fiscal_year_end-a.fiscal_year_end||b.total-a.total);
  document.querySelector('#row-count').textContent=`${rows.length} verified seed rows`;
  document.querySelector('#comp-table').innerHTML=rows.length?`<div class="table-wrap"><table><thead><tr><th>Year</th><th>Employee</th><th>Business unit</th><th>Position</th><th class="money">Wages</th><th class="money">Benefits</th><th class="money">Total</th></tr></thead><tbody>${rows.map(r=>`<tr data-name="${escapeHtml(r.person_key)}"><td>${r.fiscal_year_end}</td><td class="name-cell"><strong>${escapeHtml(r.name)}</strong><span>${escapeHtml(r.entity)}</span></td><td>${escapeHtml(r.business_unit||'—')}</td><td>${escapeHtml(r.position||'—')}</td><td class="money">${money(r.wages)}</td><td class="money">${money(r.benefits)}</td><td class="money"><strong>${money(r.total)}</strong></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">No matching seed rows.</div>';
  document.querySelector('#comp-table').querySelectorAll('[data-name]').forEach(tr=>tr.addEventListener('click',()=>renderPerson(tr.dataset.name)));
  if(state.selectedName && rows.some(r=>r.person_key===state.selectedName)) renderPerson(state.selectedName); else document.querySelector('#person-detail').innerHTML='';
}
function renderPerson(key){
  state.selectedName=key; const rows=records().filter(r=>r.person_key===key).sort((a,b)=>a.fiscal_year_end-b.fiscal_year_end); const latest=rows.at(-1); const vals=rows.map(r=>r.total); const min=Math.min(...vals),max=Math.max(...vals); const w=600,h=130,pad=15; const pts=rows.map((r,i)=>{const x=pad+(i*(w-pad*2)/Math.max(rows.length-1,1));const y=h-pad-((r.total-min)/(Math.max(max-min,1))*(h-pad*2));return [x,y]}).map(p=>p.join(',')).join(' ');
  document.querySelector('#person-detail').innerHTML=`<div class="panel"><div class="detail-head"><div><h3>${escapeHtml(latest.name)}</h3><p>${escapeHtml(latest.position||'')} · ${escapeHtml(latest.business_unit||'')}</p></div><span class="badge">${rows.length} disclosed years in seed</span></div><div class="trend"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Compensation history"><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="3" style="color:#0d6d73"/>${rows.map((r,i)=>{const [x,y]=pts.split(' ')[i].split(',');return `<circle cx="${x}" cy="${y}" r="4" fill="#0d6d73"><title>${r.fiscal_year_end}: ${money(r.total)}</title></circle>`}).join('')}</svg><div class="trend-meta"><span>${rows[0].fiscal_year_end}: ${money(rows[0].total)}</span><span>${latest.fiscal_year_end}: ${money(latest.total)}</span></div></div><div class="provenance">Only years included in the current verified seed are plotted. The automated extractor is intended to replace this seed with the complete annual statements.</div></div>`;
}

function renderFlags(){
  setTitle('Review signals'); const sig=computeSignals();
  content.innerHTML=`<div class="banner"><strong>Interpretation rule:</strong> these are screening conditions only. Compensation can change because of overtime, acting pay, retirement/severance, vacation payouts and other permitted items explicitly included in HRM's disclosure definition.</div><div class="panel"><div class="section-title"><h2>Signals generated from available rows</h2><span class="count">${sig.length} signals</span></div><div class="signal-list">${sig.map(signalHtml).join('')||'<div class="empty">No current signals.</div>'}</div></div>`;
}

function renderSources(){
  setTitle('Official source registry'); const sources=state.sources.sources; const cats=groupBy(sources,s=>s.category);
  content.innerHTML=`<div class="category-summary">${[...cats].map(([c,rows])=>`<div class="category-chip"><strong>${rows.length}</strong><span>${escapeHtml(c)}</span></div>`).join('')}</div><div class="panel"><div class="section-title"><div><h2>Source map</h2><p class="panel-sub">Registry records what is verified, how it can be ingested, and known limitations.</p></div><span class="count">${sources.length} sources</span></div><div class="source-list">${sources.map(s=>`<div class="source-row"><div><strong>${escapeHtml(s.name)}</strong><small>${escapeHtml(s.publisher)}</small></div><div><strong>${escapeHtml(s.category)}</strong><small>${escapeHtml(s.coverage||'')}</small></div><div><strong>${escapeHtml(s.ingestion)}</strong><small>ingestion</small></div><div><span class="badge ${s.status==='ready'?'':'review'}">${escapeHtml(s.status)}</span></div><div><a href="${escapeHtml(s.url)}" target="_blank" rel="noreferrer">Open ↗</a></div></div>`).join('')}</div></div>`;
}
