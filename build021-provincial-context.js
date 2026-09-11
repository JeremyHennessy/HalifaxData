/* Build 021 — Nova Scotia Provincial Context
 * Separate provincial evidence. No HRM accounting totals, payment-fact counts,
 * investigation scores, navigation or approved shell are changed.
 */
state.build021Province={status:'loading',data:null,error:null};
state.build021TaxContext={status:'loading',data:null,error:null};
let build021SourcesMerged=false;

async function b21FetchJson(url){
  const response=await fetch(url,{cache:'no-store'});
  if(!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
Promise.allSettled([
  b21FetchJson('./data/generated/province_context.json'),
  b21FetchJson('./data/tax_transparency_2026.json')
]).then(([provinceResult,taxResult])=>{
  state.build021Province=provinceResult.status==='fulfilled'?{status:'ready',data:provinceResult.value,error:null}:{status:'error',data:null,error:provinceResult.reason?.message||'Provincial context failed to load'};
  state.build021TaxContext=taxResult.status==='fulfilled'?{status:'ready',data:taxResult.value,error:null}:{status:'error',data:null,error:taxResult.reason?.message||'Provincial budget context failed to load'};
  b21MergeSources();
  if(state.compensation&&state.sources&&typeof render==='function') render();
});

function b21Data(){return state.build021Province?.data||null;}
function b21Summary(){return b21Data()?.summary||{};}
function b21Payments(){return Array.isArray(b21Data()?.payments)?b21Data().payments:[];}
function b21Departments(){return Array.isArray(b21Data()?.department_totals)?b21Data().department_totals:[];}
function b21Sources(){return Array.isArray(b21Data()?.sources)?b21Data().sources:[];}
function b21TaxData(){return state.build021TaxContext?.data||null;}

function b21MergeSources(){
  if(build021SourcesMerged||state.build021Province?.status!=='ready'||!Array.isArray(state.sources?.sources)) return false;
  const existing=new Set(state.sources.sources.map(source=>source.id));
  for(const source of b21Sources()){
    if(existing.has(source.id)) continue;
    state.sources.sources.push({
      id:source.id,
      name:source.title,
      publisher:source.publisher,
      category:'Provincial context',
      coverage:source.fiscal_year==='2026-27'?'2026/27 planned provincial expense context':'2024/25 General Revenue Fund cash-basis accumulated payee disclosures',
      ingestion:source.fiscal_year==='2026-27'?'Authoritative budget table already normalized in tax_transparency_2026.json':'Exact source-row transcription + deterministic validation',
      status:'ready',
      url:source.url
    });
    existing.add(source.id);
  }
  if(!state.sources.metadata?.last_researched||state.sources.metadata.last_researched<'2026-09-11'){
    state.sources.metadata={...(state.sources.metadata||{}),last_researched:'2026-09-11'};
    const snapshot=$('#snapshot-label');
    if(snapshot) snapshot.textContent='Sources researched 2026-09-11';
  }
  build021SourcesMerged=true;
  return true;
}
function b21SourceById(id){return sourceById(id)||b21Sources().find(source=>source.id===id)||null;}
function b21SourceLink(id,label=null){
  const source=b21SourceById(id),href=safeUrl(source?.url);
  return source&&href?`<a class="source-link" href="${escapeHtml(href)}" target="_blank" rel="noreferrer">${escapeHtml(label||source.name||source.title)} ↗</a>`:'';
}
function b21SectionLabel(value){
  return {grants_and_contributions:'Grants and contributions',other:'Other payments',external_secondments:'External secondments'}[value]||String(value||'Unknown').replaceAll('_',' ');
}
function b21ProvincePaymentTable(){
  return `<div class="table-wrap"><table data-build021-payments-table><thead><tr><th>Provincial department</th><th>Published payee</th><th>Source section</th><th class="numeric">Cash-basis amount</th><th>Evidence</th></tr></thead><tbody>${b21Payments().map(row=>`<tr data-build021-payment-row="${escapeHtml(row.id)}"><td><strong>${escapeHtml(row.department)}</strong></td><td>${escapeHtml(row.recipient)}</td><td>${escapeHtml(b21SectionLabel(row.source_section))}</td><td class="numeric"><strong>${money(row.amount)}</strong></td><td>Volume 3 p${numberFmt.format(row.source_page)}</td></tr>`).join('')}</tbody></table></div>`;
}
function b21DepartmentTable(){
  return `<div class="table-wrap"><table data-build021-departments-table><thead><tr><th>Provincial department</th><th class="numeric">Rows</th><th class="numeric">Exact-payee amount</th></tr></thead><tbody>${b21Departments().slice(0,6).map(row=>`<tr><td><strong>${escapeHtml(row.department)}</strong></td><td class="numeric">${numberFmt.format(row.row_count)}</td><td class="numeric"><strong>${money(row.amount)}</strong></td></tr>`).join('')}</tbody></table></div>`;
}
function b21ProvincePaymentPanel(){
  if(state.build021Province?.status==='loading') return `<section class="panel" data-build021-province="loading"><header class="panel-header"><div><h2>Province → Halifax cash payments</h2><p>Loading source-backed Nova Scotia Public Accounts context.</p></div></header></section>`;
  if(state.build021Province?.status!=='ready') return `<section class="panel" data-build021-province="error"><header class="panel-header"><div><h2>Province → Halifax cash payments</h2><p>Provincial context is unavailable.</p></div></header><div class="panel-body">${emptyState('Provincial context unavailable',state.build021Province?.error||'Unknown load error')}</div></section>`;
  const summary=b21Summary();
  return `<section class="panel" data-build021-province="ready"><header class="panel-header"><div><h2>Province → Halifax cash payments</h2><p>2024/25 Nova Scotia Public Accounts exact-payee rows for Halifax Regional Municipality and Halifax Regional Water Commission.</p></div></header><div class="panel-body">
    <div class="notice"><strong>Separate provincial accounting scope</strong><span>These are Province of Nova Scotia General Revenue Fund cash-basis accumulated annual payee disclosures. They are inbound provincial payment/context evidence, not HRM expenses, not an HRM spending total, not HRM accounts payable and not invoice-level transactions.</span></div>
    <div class="metrics-grid compact">
      ${metricCard('HRM published payee total',compactMoney(summary.hrm_amount),`${numberFmt.format(summary.hrm_rows)} exact Public Accounts rows`,'accent')}
      ${metricCard('Halifax Water payee total',compactMoney(summary.halifax_water_amount),`${numberFmt.format(summary.halifax_water_rows)} exact Public Accounts rows`,'neutral')}
      ${metricCard('Combined exact-payee subset',compactMoney(summary.combined_exact_payee_amount),`${numberFmt.format(summary.payment_rows)} rows · not a net-transfer measure`,'good')}
      ${metricCard('Provincial departments',numberFmt.format(summary.departments),'2024/25 source year','neutral')}
    </div>
    ${panel('Largest provincial department flows','Department totals within the exact HRM/Halifax Water payee subset only. They do not represent total provincial spending in Halifax.',b21DepartmentTable())}
    ${panel('Published Halifax payee rows','Each row preserves the Public Accounts department, section and PDF page. Grant, secondment and other-payment semantics remain distinct.',b21ProvincePaymentTable())}
    <p class="table-note">Volume 3 generally discloses accumulated annual other payments of $5,000 or more, with different thresholds for salary and travel. Build 021 does not infer undisclosed smaller payments, invoices, payment dates or HRM use of funds.</p>
    <div class="b13-source-inline">${b21SourceLink('ns-public-accounts-2024-25-volume3')}</div>
  </div></section>`;
}
function b21ProvincialBudgetPanel(){
  if(state.build021TaxContext?.status!=='ready') return `<section class="panel" data-build021-budget="${state.build021TaxContext?.status||'loading'}"><header class="panel-header"><div><h2>Nova Scotia expense-plan context</h2><p>Current provincial budget context is unavailable.</p></div></header></section>`;
  const allocation=b21TaxData()?.nova_scotia_spending_allocation;
  if(!allocation||!Array.isArray(allocation.categories)) return `<section class="panel" data-build021-budget="error"><header class="panel-header"><div><h2>Nova Scotia expense-plan context</h2><p>The authoritative provincial budget allocation contract is missing.</p></div></header></section>`;
  const rows=[...allocation.categories].sort((a,b)=>Number(b.share_pct)-Number(a.share_pct));
  return `<section class="panel" data-build021-budget="ready"><header class="panel-header"><div><h2>Nova Scotia 2026/27 expense-plan context</h2><p>Provincial planned expense shares shown beside, but never merged into, HRM budget or actual totals.</p></div></header><div class="panel-body">
    <div class="notice"><strong>Different government, different denominator</strong><span>These percentages describe the Province of Nova Scotia's 2026/27 planned expenses. They provide fiscal context only and are never added to HRM service-area budgets, quarterly spending summaries, capital schedules or audited results.</span></div>
    <div class="table-wrap"><table data-build021-budget-table><thead><tr><th>Provincial expense area</th><th class="numeric">Share of planned expenses</th></tr></thead><tbody>${rows.map(row=>`<tr><td><strong>${escapeHtml(row.category)}</strong></td><td class="numeric">${decimalFmt.format(row.share_pct)}%</td></tr>`).join('')}</tbody></table></div>
    <p class="table-note">${escapeHtml(allocation.source_rounding_note||'Source-reported shares may reflect rounding.')}</p>
    <div class="b13-source-inline">${b21SourceLink('ns-budget-2026-27-expense-shares')}</div>
  </div></section>`;
}
function b21ProvinceSourcesPanel(){
  const sources=b21Sources();
  if(!sources.length) return '';
  return `<section class="panel" data-build021-sources><header class="panel-header"><div><h2>Provincial context sources</h2><p>Province-wide evidence is registered separately so it cannot be mistaken for municipal accounting data.</p></div></header><div class="panel-body"><div class="rule-list">${sources.map(source=>`<div><strong>${escapeHtml(source.title)}</strong><span>${escapeHtml(source.fiscal_year||'')} · separate provincial evidence type</span>${b21SourceLink(source.id,'Open source')}</div>`).join('')}</div><p class="table-note">Nova Scotia awarded-tender records remain procurement evidence. Public Accounts cash payments are a separate provincial evidence type and do not convert a tender award into an HRM payment fact.</p></div></section>`;
}
function b21EnhanceOverview(){
  const stack=$('#content .page-stack');
  if(!stack||stack.querySelector('[data-build021-province]')) return;
  const metrics=stack.querySelector(':scope > .metrics-grid');
  if(metrics) metrics.insertAdjacentHTML('afterend',b21ProvincePaymentPanel()); else stack.insertAdjacentHTML('beforeend',b21ProvincePaymentPanel());
}
function b21EnhanceBudget(){
  const stack=$('#content .page-stack');
  if(stack&&!stack.querySelector('[data-build021-budget]')) stack.insertAdjacentHTML('beforeend',b21ProvincialBudgetPanel());
}
function b21EnhanceSources(){
  const stack=$('#content .page-stack');
  if(stack&&!stack.querySelector('[data-build021-sources]')) stack.insertAdjacentHTML('beforeend',b21ProvinceSourcesPanel());
}
window.b21Payments=b21Payments;
window.b21Summary=b21Summary;
window.b21Departments=b21Departments;

const b21RenderBase=render;
render=function renderBuild021(){
  b21MergeSources();
  b21RenderBase();
  if(state.view==='overview') b21EnhanceOverview();
  if(state.view==='budget') b21EnhanceBudget();
  if(state.view==='sources') b21EnhanceSources();
};
