/* Build 022 — usability hierarchy + separate provincial/freshness context.
 * Presentation changes only: no investigation scores, joins, accounting totals,
 * source facts or approved evidence boundaries are rewritten here.
 */
state.build022Province={status:'loading',data:null,error:null};
state.build022Tax={status:'loading',data:null,error:null};
state.build022Freshness={status:'loading',data:null,error:null};
let build022SourcesMerged=false;

async function b22FetchJson(url){
  const response=await fetch(url,{cache:'no-store'});
  if(!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
Promise.allSettled([
  b22FetchJson('./data/generated/province_context.json'),
  b22FetchJson('./data/tax_transparency_2026.json'),
  b22FetchJson('./data/current_source_refresh_status.json')
]).then(([provinceResult,taxResult,freshnessResult])=>{
  state.build022Province=provinceResult.status==='fulfilled'?{status:'ready',data:provinceResult.value,error:null}:{status:'error',data:null,error:provinceResult.reason?.message||'Provincial context failed to load'};
  state.build022Tax=taxResult.status==='fulfilled'?{status:'ready',data:taxResult.value,error:null}:{status:'error',data:null,error:taxResult.reason?.message||'Tax context failed to load'};
  state.build022Freshness=freshnessResult.status==='fulfilled'?{status:'ready',data:freshnessResult.value,error:null}:{status:'error',data:null,error:freshnessResult.reason?.message||'Freshness status failed to load'};
  b22MergeSources();
  if(state.compensation&&state.sources&&typeof render==='function') render();
});

function b22Province(){return state.build022Province?.data||null;}
function b22Tax(){return state.build022Tax?.data||null;}
function b22Freshness(){return state.build022Freshness?.data||null;}
function b22ProvinceSources(){return Array.isArray(b22Province()?.sources)?b22Province().sources:[];}
function b22TaxSources(){return Array.isArray(b22Tax()?.sources)?b22Tax().sources:[];}

function b22MergeSources(){
  if(build022SourcesMerged||!Array.isArray(state.sources?.sources)) return false;
  const candidates=[...b22ProvinceSources(),...b22TaxSources()];
  if(!candidates.length) return false;
  const existing=new Set(state.sources.sources.map(source=>source.id));
  for(const source of candidates){
    if(!source?.id||existing.has(source.id)) continue;
    state.sources.sources.push({
      id:source.id,
      name:source.title,
      publisher:source.publisher||source.authority||'Official public source',
      category:b22ProvinceSources().some(item=>item.id===source.id)?'Provincial context':'Tax & fiscal context',
      coverage:source.fiscal_year||source.supports?.join(', ')||'Current registered context',
      ingestion:'Registered authoritative context; kept outside HRM transaction/payment facts unless explicitly HRM-scoped.',
      status:'ready',
      url:source.url
    });
    existing.add(source.id);
  }
  build022SourcesMerged=true;
  return true;
}
function b22AllContextSources(){return [...b22ProvinceSources(),...b22TaxSources()];}
function b22Source(id){return b22AllContextSources().find(source=>source.id===id)||sourceById(id)||null;}
function b22SourceLink(id,label='Open official source'){
  const source=b22Source(id),href=safeUrl(source?.url);
  return source&&href?`<a class="source-link" href="${escapeHtml(href)}" target="_blank" rel="noreferrer">${escapeHtml(label)} ↗</a>`:'';
}
function b22SectionLabel(value){
  return {grants_and_contributions:'Grants and contributions',other:'Other payments',external_secondments:'External secondments'}[value]||humanize(value||'Unknown');
}
function b22StatusLabel(value){
  return {
    verified_current:'Verified current',
    verified_new_source:'Verified newer source',
    current_source_research:'Current source monitored',
    not_yet_verified:'Newer source not yet verified'
  }[value]||humanize(value||'Unknown');
}
function b22StatusTone(value){
  if(value==='verified_current'||value==='current_source_research') return 'good';
  if(value==='verified_new_source') return 'warn';
  return 'muted';
}

function b22StartHere(){
  return `<section class="panel b22-start-here" data-build022-start>
    <header class="panel-header"><div><h2>Start here</h2><p>The shortest path from a review lead to the underlying source evidence.</p></div></header>
    <div class="panel-body"><div class="b22-action-grid">
      <a href="#signals"><strong>1 · Review prioritized investigations</strong><span>Begin with evidence-backed leads. A review score is ordering, not a finding.</span></a>
      <a href="#budget"><strong>2 · Trace the financial context</strong><span>Check budget pressure, historical rows, capital and published spending summaries.</span></a>
      <a href="#sources"><strong>3 · Check freshness and gaps</strong><span>Confirm what is current, what is blocked, and what is still unverified before drawing a conclusion.</span></a>
    </div></div>
  </section>`;
}

function b22ProvincePanel(){
  if(state.build022Province?.status==='loading') return `<section class="panel b22-province" data-build022-province="loading"><header class="panel-header"><div><h2>Province → Halifax funding context</h2><p>Loading source-backed provincial context.</p></div></header></section>`;
  if(state.build022Province?.status!=='ready') return `<section class="panel b22-province" data-build022-province="error"><header class="panel-header"><div><h2>Province → Halifax funding context</h2><p>Provincial context is unavailable.</p></div></header></section>`;
  const data=b22Province(),summary=data.summary||{},departments=Array.isArray(data.department_totals)?data.department_totals:[],payments=Array.isArray(data.payments)?data.payments:[];
  const departmentRows=departments.slice(0,6).map(row=>`<tr><td><strong>${escapeHtml(row.department)}</strong></td><td class="numeric">${numberFmt.format(row.row_count)}</td><td class="numeric"><strong>${money(row.amount)}</strong></td></tr>`).join('');
  const paymentRows=payments.map(row=>`<tr data-build022-province-row="${escapeHtml(row.id)}"><td><strong>${escapeHtml(row.department)}</strong></td><td>${escapeHtml(row.recipient)}</td><td>${escapeHtml(b22SectionLabel(row.source_section))}</td><td class="numeric"><strong>${money(row.amount)}</strong></td><td>Volume 3 p${numberFmt.format(row.source_page)}</td></tr>`).join('');
  return `<section class="panel b22-province" data-build022-province="ready">
    <header class="panel-header"><div><h2>Province → Halifax funding context</h2><p>Exact-payee 2024/25 Nova Scotia Public Accounts rows, kept separate from HRM accounting.</p></div></header>
    <div class="panel-body">
      <div class="notice b22-scope-note"><strong>Separate accounting scope</strong><span>These are Province of Nova Scotia General Revenue Fund cash-basis accumulated payee disclosures. They are inbound provincial evidence, not HRM expenses, not an HRM accounts-payable ledger, and not invoice-level transactions.</span></div>
      <div class="metrics-grid compact">
        ${metricCard('HRM exact-payee total',compactMoney(summary.hrm_amount),`${numberFmt.format(summary.hrm_rows||0)} Public Accounts rows`,'accent')}
        ${metricCard('Halifax Water exact-payee total',compactMoney(summary.halifax_water_amount),`${numberFmt.format(summary.halifax_water_rows||0)} Public Accounts rows`,'neutral')}
        ${metricCard('Combined exact-payee subset',compactMoney(summary.combined_exact_payee_amount),`${numberFmt.format(summary.payment_rows||0)} rows · not a net-transfer measure`,'good')}
        ${metricCard('Provincial departments',numberFmt.format(summary.departments||0),'2024/25 source year','neutral')}
      </div>
      <div class="b22-summary-grid">
        <div><h3>Largest department flows in this subset</h3><p>Department totals only within the exact HRM/Halifax Water rows.</p><div class="table-wrap"><table><thead><tr><th>Department</th><th class="numeric">Rows</th><th class="numeric">Amount</th></tr></thead><tbody>${departmentRows}</tbody></table></div></div>
        <div class="b22-boundary-card"><h3>What this adds</h3><ul><li>Provincial cash-payment context to named Halifax public bodies.</li><li>A distinct source type from procurement awards and HRM spending summaries.</li><li>No new HRM payment facts or investigation score changes.</li></ul>${b22SourceLink('ns-public-accounts-2024-25-volume3')}</div>
      </div>
      <details class="b22-detail-block" data-build022-province-details>
        <summary>View all ${numberFmt.format(payments.length)} published Halifax payee rows</summary>
        <div class="b22-detail-body"><div class="table-wrap"><table data-build022-province-table><thead><tr><th>Provincial department</th><th>Published payee</th><th>Section</th><th class="numeric">Cash-basis amount</th><th>Evidence</th></tr></thead><tbody>${paymentRows}</tbody></table></div>
        <p class="table-note">Volume 3 generally reports accumulated annual other payments of $5,000 or more, with separate salary and travel thresholds. HalifaxData does not infer undisclosed smaller payments, invoices, payment dates or HRM use of funds.</p></div>
      </details>
    </div>
  </section>`;
}

function b22TaxContextPanel(){
  if(state.build022Tax?.status!=='ready') return '';
  const tax=b22Tax(),fed=tax.federal_spending_allocation||{},ns=tax.nova_scotia_spending_allocation||{},hrm=tax.halifax_property_tax||{};
  const fedTop=[...(fed.categories||[])].sort((a,b)=>Number(b.amount_billion)-Number(a.amount_billion)).slice(0,4);
  const nsTop=[...(ns.categories||[])].sort((a,b)=>Number(b.share_pct)-Number(a.share_pct)).slice(0,5);
  return `<section class="panel b22-tax-context" data-build022-tax>
    <header class="panel-header"><div><h2>Where my taxes go — scope-correct context</h2><p>Three government layers are shown separately. No personal remittance is transaction-traced to a program.</p></div></header>
    <div class="panel-body">
      <div class="b22-government-grid">
        <article><span>FEDERAL · 2026/27</span><strong>${money(Number(fed.denominator_billion||0)*1e9)}</strong><p>${escapeHtml(fed.denominator_label||'Planned federal expenses')}</p><ol>${fedTop.map(row=>`<li><b>${escapeHtml(row.category)}</b><em>${compactMoney(Number(row.amount_billion||0)*1e9)}</em></li>`).join('')}</ol>${b22SourceLink('canada-spring-update-2026')}</article>
        <article><span>NOVA SCOTIA · 2026/27</span><strong>${nsTop.length?decimalFmt.format(nsTop[0].share_pct)+'%':'—'}</strong><p>Largest published planned-expense share: ${escapeHtml(nsTop[0]?.category||'—')}</p><ol>${nsTop.map(row=>`<li><b>${escapeHtml(row.category)}</b><em>${decimalFmt.format(row.share_pct)}%</em></li>`).join('')}</ol>${b22SourceLink('ns-budget-2026-27-expense-shares')}</article>
        <article><span>HALIFAX · PROPERTY TAX</span><strong>${money(hrm.average_urban_example?.municipal_tax||0)}</strong><p>Illustrative municipal amount on a ${money(hrm.average_urban_example?.assessment||0)} urban assessment using the explicitly selected components.</p><dl><div><dt>Urban general rate</dt><dd>${decimalFmt.format(hrm.general_rates?.urban||0)} / $100</dd></div><div><dt>Local transit</dt><dd>${decimalFmt.format(hrm.optional_or_area_components?.local_transit||0)} / $100</dd></div><div><dt>Infrastructure & climate</dt><dd>${decimalFmt.format(hrm.optional_or_area_components?.strategic_infrastructure_and_climate||0)} / $100</dd></div></dl>${b22SourceLink('hrm-budget-ratification-2026-03-31')}</article>
      </div>
      <p class="table-note">Federal and provincial values are proportional spending-plan context. Halifax does not levy municipal personal income tax. The municipal example is not a complete property-tax bill and may exclude other mandatory or area-specific charges.</p>
    </div>
  </section>`;
}

function b22FreshnessPanel(){
  const payload=b22Freshness();
  if(state.build022Freshness?.status!=='ready'||!Array.isArray(payload?.domains)) return '';
  const rows=payload.domains;
  const verified=rows.filter(row=>row.status==='verified_current'||row.status==='current_source_research').length;
  const newer=rows.filter(row=>row.status==='verified_new_source').length;
  const unresolved=rows.filter(row=>row.status==='not_yet_verified').length;
  const blocked=rows.filter(row=>String(row.source_transport_status||'').includes('blocked')).length;
  return `<section class="panel b22-freshness" data-build022-freshness>
    <header class="panel-header"><div><h2>Source freshness & unresolved gaps</h2><p>Publication status is kept separate from data values so an unavailable source never becomes an inferred zero.</p></div></header>
    <div class="panel-body">
      <div class="b8-inline-metrics"><div><strong>${numberFmt.format(verified)}</strong><span>verified/currently monitored domains</span></div><div><strong>${numberFmt.format(newer)}</strong><span>verified newer source pending controlled publication</span></div><div><strong>${numberFmt.format(unresolved)}</strong><span>newer source not yet verified</span></div><div><strong>${numberFmt.format(blocked)}</strong><span>current transport blocks</span></div></div>
      <details class="b22-detail-block"><summary>Review domain-by-domain freshness status</summary><div class="b22-detail-body"><div class="b22-freshness-list">${rows.map(row=>`<article><div><strong>${escapeHtml(humanize(row.domain))}</strong>${badge(b22StatusLabel(row.status),b22StatusTone(row.status))}</div><p>${escapeHtml(row.latest_check||row.research_result||'No check detail recorded.')}</p>${row.known_gap?`<small><b>Known gap:</b> ${escapeHtml(row.known_gap)}</small>`:''}${row.next_action?`<small><b>Next:</b> ${escapeHtml(row.next_action)}</small>`:''}</article>`).join('')}</div></div></details>
    </div>
  </section>`;
}

function b22ProvinceSourcesPanel(){
  const sources=b22ProvinceSources();
  if(!sources.length) return '';
  return `<section class="panel b22-context-sources" data-build022-context-sources><header class="panel-header"><div><h2>Additional provincial context sources</h2><p>Registered as a separate evidence layer so provincial cash payments cannot be mistaken for HRM expenditures.</p></div></header><div class="panel-body"><div class="rule-list">${sources.map(source=>`<div><strong>${escapeHtml(source.title)}</strong><span>${escapeHtml(source.fiscal_year||'')} · ${escapeHtml(source.evidence_type||'official fiscal context')}</span>${b22SourceLink(source.id)}</div>`).join('')}</div></div></section>`;
}

function b22WrapBenchmarkExplorer(){
  const stack=$('#content .page-stack');
  if(!stack||stack.querySelector('[data-build022-benchmark-details]')) return;
  const explorer=[...stack.querySelectorAll(':scope > .panel')].find(el=>normalize(el.querySelector('h2')?.textContent)==='municipal benchmark & funding explorer');
  if(!explorer) return;
  const details=document.createElement('details');
  details.className='b22-detail-block b22-benchmark-details';
  details.dataset.build022BenchmarkDetails='true';
  const summary=document.createElement('summary');
  summary.innerHTML='<strong>Explore detailed benchmark & funding table</strong><span>Raw official fields remain available on demand.</span>';
  explorer.parentNode.insertBefore(details,explorer);
  details.append(summary,explorer);
}

function b22EnhanceOverview(){
  const stack=$('#content .page-stack');
  if(!stack) return;
  if(!stack.querySelector('[data-build022-start]')){
    const metrics=stack.querySelector(':scope > .metrics-grid');
    if(metrics) metrics.insertAdjacentHTML('afterend',b22StartHere());
    else stack.insertAdjacentHTML('afterbegin',b22StartHere());
  }
  const start=stack.querySelector('[data-build022-start]');
  const attention=[...stack.querySelectorAll(':scope > .panel')].find(el=>normalize(el.querySelector('h2')?.textContent)==='what deserves attention?');
  if(start&&attention&&attention.previousElementSibling!==start) start.insertAdjacentElement('afterend',attention);
  const authority=stack.querySelector(':scope > .b12-overview-authority, :scope > [data-build012-overview]');
  const pattern=stack.querySelector(':scope > .b9-pattern-summary');
  if(attention&&authority) attention.insertAdjacentElement('afterend',authority);
  if(authority&&pattern) authority.insertAdjacentElement('afterend',pattern);
}

function b22EnhanceBenchmarks(){
  const stack=$('#content .page-stack');
  if(!stack) return;
  const metrics=stack.querySelector(':scope > .metrics-grid');
  if(!stack.querySelector('[data-build022-province]')){
    if(metrics) metrics.insertAdjacentHTML('afterend',b22ProvincePanel()+b22TaxContextPanel());
    else stack.insertAdjacentHTML('beforeend',b22ProvincePanel()+b22TaxContextPanel());
  }
  b22WrapBenchmarkExplorer();
}
function b22EnhanceSources(){
  const stack=$('#content .page-stack');
  if(!stack) return;
  if(!stack.querySelector('[data-build022-freshness]')){
    const metrics=stack.querySelector(':scope > .metrics-grid');
    if(metrics) metrics.insertAdjacentHTML('afterend',b22FreshnessPanel());
    else stack.insertAdjacentHTML('afterbegin',b22FreshnessPanel());
  }
  if(!stack.querySelector('[data-build022-context-sources]')) stack.insertAdjacentHTML('beforeend',b22ProvinceSourcesPanel());
}

const b22RenderBase=render;
render=function renderBuild022(){
  b22MergeSources();
  b22RenderBase();
  if(state.view==='overview') b22EnhanceOverview();
  if(state.view==='benchmarks') b22EnhanceBenchmarks();
  if(state.view==='sources') b22EnhanceSources();
};
