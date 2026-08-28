/* Build 018 — current-source refresh.
 * Adds ratified-current 2026/27 operating-budget authority and the approved-current
 * capital multi-year cashflow schedule without replacing the proven 2025/26 views.
 */

state.build018CurrentBudget = { status: 'loading', data: null, error: null };
state.build018CurrentCapital = { status: 'loading', data: null, error: null };
state.build018BudgetSources = { status: 'loading', data: null, error: null };
state.build018CapitalSources = { status: 'loading', data: null, error: null };
state.build018BudgetQuery = '';
state.build018BudgetUnit = 'all';
state.build018CapitalQuery = '';
state.build018CapitalClass = 'all';
let build018SourcesMerged = false;

async function b18FetchJson(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function b18SafeRender() {
  if (typeof render === 'function' && state.compensation && state.sources) render();
}

Promise.all([
  b18FetchJson('./data/generated/current_budget_2026_27.json'),
  b18FetchJson('./data/generated/current_capital_2026_27_multiyear.json'),
  b18FetchJson('./data/current_budget_sources.json'),
  b18FetchJson('./data/current_capital_sources.json')
]).then(([budget, capital, budgetSources, capitalSources]) => {
  state.build018CurrentBudget = { status: 'ready', data: budget, error: null };
  state.build018CurrentCapital = { status: 'ready', data: capital, error: null };
  state.build018BudgetSources = { status: 'ready', data: budgetSources, error: null };
  state.build018CapitalSources = { status: 'ready', data: capitalSources, error: null };
  b18MergeSources();
  b18SafeRender();
}).catch(error => {
  const message = error.message || 'Build 018 source refresh failed to load';
  for (const key of ['build018CurrentBudget', 'build018CurrentCapital', 'build018BudgetSources', 'build018CapitalSources']) {
    if (state[key]?.status === 'loading') state[key] = { status: 'error', data: null, error: message };
  }
  b18SafeRender();
});

function b18BudgetData() { return state.build018CurrentBudget?.data || null; }
function b18BudgetMeta() { return b18BudgetData()?.metadata || {}; }
function b18BudgetRows() { return Array.isArray(b18BudgetData()?.records) ? b18BudgetData().records : []; }
function b18CapitalData() { return state.build018CurrentCapital?.data || null; }
function b18CapitalMeta() { return b18CapitalData()?.metadata || {}; }
function b18CapitalRows() { return Array.isArray(b18CapitalData()?.records) ? b18CapitalData().records : []; }
function b18BudgetConfig() { return state.build018BudgetSources?.data || null; }
function b18CapitalConfig() { return state.build018CapitalSources?.data || null; }

function b18MergeSources() {
  if (build018SourcesMerged || !Array.isArray(state.sources?.sources)) return false;
  if (state.build018BudgetSources?.status !== 'ready' || state.build018CapitalSources?.status !== 'ready') return false;

  const budgetConfig = b18BudgetConfig();
  const capitalConfig = b18CapitalConfig();
  const budgetSource = budgetConfig?.budget_source;
  const approval = budgetConfig?.approval_source;
  const capitalSource = capitalConfig?.schedule_source;
  if (!budgetSource || !approval || !capitalSource) return false;

  const additions = [
    budgetSource,
    {
      id: capitalSource.id,
      name: capitalSource.name,
      publisher: capitalSource.publisher,
      category: 'Capital',
      coverage: '2026/27 Capital Multi-Year Projects schedule; 52 identified discrete projects and ongoing programs with fiscal-year cashflow columns.',
      ingestion: 'Official eSCRIBE PDF Attachment 2; exact-title live attachment resolution',
      status: capitalSource.status,
      url: capitalSource.known_live_attachment_url
    },
    {
      ...approval,
      coverage: 'March 31, 2026 Regional Council ratification of 2026/27 operating budgets, Capital Plan and tax rates.',
      ingestion: 'Official eSCRIBE Council agenda / decision record'
    }
  ];

  const existing = new Set(state.sources.sources.map(source => source.id));
  for (const source of additions) {
    if (!source?.id || existing.has(source.id)) continue;
    state.sources.sources.push(source);
    existing.add(source.id);
  }
  const researched = budgetConfig?.metadata?.last_researched || capitalConfig?.metadata?.last_researched;
  if (researched && (!state.sources.metadata?.last_researched || researched > state.sources.metadata.last_researched)) {
    state.sources.metadata = { ...(state.sources.metadata || {}), last_researched: researched };
  }
  build018SourcesMerged = true;
  return true;
}

function b18BudgetUnits() {
  return [...new Set(b18BudgetRows().map(row => row.business_unit_source_heading).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}
function b18BudgetKey(row) {
  return `${row.source_page}||${row.business_unit_source_heading}||${row.source_service_area_label}`;
}
function b18BudgetFilteredRows() {
  const query = normalize(state.build018BudgetQuery);
  return b18BudgetRows().filter(row =>
    (state.build018BudgetUnit === 'all' || row.business_unit_source_heading === state.build018BudgetUnit) &&
    (!query || normalize(`${row.business_unit_source_heading} ${row.service_area} ${row.source_service_area_label || ''}`).includes(query))
  );
}
function b18BudgetWarning(row) { return Array.isArray(row?.validation_flags) && row.validation_flags.length > 0; }
function b18SignedMoney(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return `${n >= 0 ? '+' : '-'}${money(Math.abs(n))}`;
}
function b18PlainPct(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return `${n >= 0 ? '+' : ''}${decimalFmt.format(n)}%`;
}
function b18SourceEvidence(label, source) {
  if (!source) return '';
  return `<div class="drawer-section"><h3>${escapeHtml(label)}</h3>${evidenceSteps([
    ['Source', source.name],
    ['Publisher', source.publisher],
    ['Source ID', source.id]
  ])}${sourceLink(source)}</div>`;
}

function b18BudgetTable() {
  const rows = b18BudgetFilteredRows();
  if (!rows.length) return emptyState('No matching 2026/27 budget rows', 'Change the Build 018 service-area filter or search text.');
  return `<div class="local-toolbar budget-toolbar"><label class="local-search"><span>⌕</span><input id="b18-budget-search" value="${escapeHtml(state.build018BudgetQuery)}" placeholder="Search 2026/27 service area or business unit" /></label><select id="b18-budget-unit"><option value="all">All 2026/27 budget business units</option>${b18BudgetUnits().map(unit => `<option value="${escapeHtml(unit)}" ${unit === state.build018BudgetUnit ? 'selected' : ''}>${escapeHtml(unit)}</option>`).join('')}</select><span class="table-note">${numberFmt.format(rows.length)} rows</span></div>
  <div class="table-wrap"><table class="budget-table"><thead><tr><th>Business unit</th><th>Service area</th><th class="numeric">2024/25 actual</th><th class="numeric">2025/26 budget</th><th class="numeric">2025/26 projection</th><th class="numeric">2026/27 budget</th><th class="numeric">Published Δ</th><th class="numeric">Derived Δ</th></tr></thead><tbody>${rows.map(row => `<tr class="${b18BudgetWarning(row) ? 'budget-source-warning' : ''}" data-build018-budget-row="${escapeHtml(b18BudgetKey(row))}"><td>${escapeHtml(row.business_unit_source_heading)}</td><td><strong>${escapeHtml(row.service_area)}</strong>${row.service_area !== row.source_service_area_label ? `<small class="cell-sub">source label: ${escapeHtml(row.source_service_area_label)}</small>` : ''}${b18BudgetWarning(row) ? '<small class="data-flag">source arithmetic flag</small>' : ''}</td><td class="numeric">${money(row.prior_actual)}</td><td class="numeric">${money(row.prior_budget)}</td><td class="numeric">${money(row.projection)}</td><td class="numeric"><strong>${money(row.current_budget)}</strong></td><td class="numeric">${b18SignedMoney(row.source_reported_budget_change)}<small class="cell-sub">${b18PlainPct(row.source_reported_budget_change_pct)}</small></td><td class="numeric">${b18SignedMoney(row.derived_budget_change)}<small class="cell-sub">${b18PlainPct(row.derived_budget_change_pct)}</small></td></tr>`).join('')}</tbody></table></div>`;
}

function b18CurrentBudgetPanel() {
  if (state.build018CurrentBudget?.status === 'loading') return `<section class="panel b18-current-budget"><header class="panel-header"><div><h2>Ratified-current 2026/27 budget</h2><p>Loading Build 018 source-backed budget authority.</p></div></header></section>`;
  if (state.build018CurrentBudget?.status !== 'ready') return `<section class="panel b18-current-budget"><header class="panel-header"><div><h2>Ratified-current 2026/27 budget</h2><p>Build 018 current-budget artifact is unavailable.</p></div></header><div class="panel-body">${emptyState('Current budget unavailable', state.build018CurrentBudget?.error || 'Unknown load error')}</div></section>`;

  const meta = b18BudgetMeta();
  const details = b18BudgetRows().filter(row => !row.is_total).length;
  const flags = b18BudgetRows().filter(b18BudgetWarning);
  const controls = meta.published_controls || {};
  return `<section class="panel b18-current-budget"><header class="panel-header"><div><h2>Ratified-current 2026/27 budget</h2><p>Final March 25 post-BAL service-area tables, linked separately to Regional Council's March 31 ratification.</p></div></header><div class="panel-body">
    <div class="notice"><strong>Budget authority — not spending</strong><span>These are 2026/27 budget facts. They are not invoices, accounts-payable transactions, commitments, cash payments or final costs. The proven 2025/26 budget and audited-history views remain unchanged below.</span></div>
    <div class="metrics-grid compact">
      ${metricCard('Municipal expenditures', compactMoney(controls.municipal_expenditures), 'Final March 25 package control', 'accent')}
      ${metricCard('2026/27 service areas', numberFmt.format(details), `${numberFmt.format(meta.overview_page_count || 0)} source overview pages`, 'good')}
      ${metricCard('HRP net budget', compactMoney(102182400), 'Independent source-table control', 'neutral')}
      ${metricCard('Source review rows', numberFmt.format(flags.length), 'Published values preserved; not wrongdoing findings', flags.length ? 'warn' : 'good')}
    </div>
    ${flags.length ? `<div class="notice"><strong>One published percentage does not reconcile to its row endpoints</strong><span>Parks & Recreation → Strategic Planning and Design publishes an 8.9% change; the same source row's $3.9221M → $4.2559M endpoints derive to 8.5107%. HalifaxData retains both values and flags the discrepancy.</span></div>` : ''}
    ${panel('2026/27 service-area budget explorer', 'Source-published 2024/25 actual, 2025/26 budget/projection and ratified-current 2026/27 budget. Current organization headings are retained as published rather than force-mapped onto prior-year taxonomy.', b18BudgetTable())}
    <p class="table-note">Amount source: final March 25, 2026 post-Budget-Adjustment-List staff package. Approval evidence: March 31, 2026 Regional Council ratification of the operating budgets, Capital Plan and tax rates.</p>
  </div></section>`;
}

function b18CapitalFilteredRows() {
  const query = normalize(state.build018CapitalQuery);
  return b18CapitalRows().filter(row =>
    (state.build018CapitalClass === 'all' || row.schedule_class === state.build018CapitalClass) &&
    (!query || normalize(`${row.project_account_id} ${row.project_name} ${row.schedule_class}`).includes(query))
  );
}
function b18CapitalClassLabel(value) { return value === 'discrete_project' ? 'Discrete project' : 'Ongoing program'; }

function b18CapitalTable() {
  const rows = b18CapitalFilteredRows();
  if (!rows.length) return emptyState('No matching 2026/27 capital rows', 'Change the Build 018 project/program filter or search text.');
  const visible = [...rows].sort((a, b) => Number(b.capital_budget_2026_27 || 0) - Number(a.capital_budget_2026_27 || 0) || String(a.project_name).localeCompare(String(b.project_name)));
  return `<div class="local-toolbar build006-toolbar"><label class="local-search"><span>⌕</span><input id="b18-capital-search" value="${escapeHtml(state.build018CapitalQuery)}" placeholder="Search current account ID or project/program" /></label><select id="b18-capital-class"><option value="all">All multi-year rows</option><option value="discrete_project" ${state.build018CapitalClass === 'discrete_project' ? 'selected' : ''}>Discrete projects</option><option value="ongoing_program" ${state.build018CapitalClass === 'ongoing_program' ? 'selected' : ''}>Ongoing programs</option></select><span class="table-note">${numberFmt.format(visible.length)} rows</span></div>
  <div class="table-wrap"><table><thead><tr><th>Account ID</th><th>Project / program</th><th>Class</th><th class="numeric">Previous years</th><th class="numeric">2025/26</th><th class="numeric">2026/27</th><th class="numeric">2027/28</th><th class="numeric">Row Grand Total</th></tr></thead><tbody>${visible.map(row => `<tr data-build018-capital-row="${escapeHtml(row.project_account_id)}"><td><strong>${escapeHtml(row.project_account_id)}</strong></td><td>${escapeHtml(row.project_name)}</td><td>${badge(b18CapitalClassLabel(row.schedule_class), row.schedule_class === 'discrete_project' ? 'info' : 'muted')}</td><td class="numeric">${money(row.total_previous_years_gross_budget)}</td><td class="numeric">${money(row.capital_budget_2025_26)}</td><td class="numeric"><strong>${money(row.capital_budget_2026_27)}</strong></td><td class="numeric">${money(row.capital_budget_2027_28)}</td><td class="numeric">${money(row.grand_total)}</td></tr>`).join('')}</tbody></table></div>`;
}

function b18CurrentCapitalPanel() {
  if (state.build018CurrentCapital?.status === 'loading') return `<section class="panel b18-current-capital"><header class="panel-header"><div><h2>Approved-current 2026/27 multi-year capital schedule</h2><p>Loading Build 018 capital cashflow evidence.</p></div></header></section>`;
  if (state.build018CurrentCapital?.status !== 'ready') return `<section class="panel b18-current-capital"><header class="panel-header"><div><h2>Approved-current 2026/27 multi-year capital schedule</h2><p>Build 018 current-capital artifact is unavailable.</p></div></header><div class="panel-body">${emptyState('Current capital schedule unavailable', state.build018CurrentCapital?.error || 'Unknown load error')}</div></section>`;

  const meta = b18CapitalMeta();
  return `<section class="panel b18-current-capital"><header class="panel-header"><div><h2>Approved-current 2026/27 multi-year capital schedule</h2><p>Revised March 3 Attachment 2 with exact project account IDs, linked to March 31 Capital Plan ratification.</p></div></header><div class="panel-body">
    <div class="notice"><strong>Schedule boundary</strong><span>This is a multi-year capital budget/cashflow schedule, not a complete capital-project ledger. It does not establish spend-to-date, commitments, invoices, payments, final project cost or an overrun. The richer 2025/26 project-sheet and adjustment evidence remains unchanged below.</span></div>
    <div class="metrics-grid compact">
      ${metricCard('Multi-year rows', numberFmt.format(meta.project_rows || 0), `${numberFmt.format(meta.discrete_project_rows || 0)} discrete · ${numberFmt.format(meta.ongoing_program_rows || 0)} ongoing`, 'accent')}
      ${metricCard('2026/27 cashflow', compactMoney(meta.current_2026_27_multiyear_budget), 'Across the 52 identified schedule rows', 'good')}
      ${metricCard('Row-computed schedule', compactMoney(meta.computed_schedule_grand_total), 'Every project/program row reconciles internally', 'neutral')}
      ${metricCard('Source control flags', numberFmt.format((meta.source_control_discrepancies || []).length), 'Four fields · two underlying source defects', 'warn')}
    </div>
    <div class="notice"><strong>Published control-table defects preserved</strong><span>The 29 discrete project rows sum $1 above HRM's printed discrete subtotal, and that $1 carries into the printed schedule Grand Total. The final previous-years control also omits the ongoing-program previous-years subtotal. Project rows are not rewritten to force the source totals.</span></div>
    ${panel('2026/27 capital multi-year project/program explorer', 'Exact source account IDs and fiscal-year budget columns. Sorting emphasizes the current 2026/27 scheduled amount, not actual spend.', b18CapitalTable())}
    <p class="table-note">The previously indexed attachment URL now returns 404. Build 018 re-resolves the March 3 agenda by exact visible attachment title and requires one unique live URL before parsing.</p>
  </div></section>`;
}

function b18ShowBudgetRow(key) {
  const row = b18BudgetRows().find(item => b18BudgetKey(item) === key);
  if (!row) return;
  const source = sourceById(row.source_id);
  const approval = sourceById(row.approval_source_id);
  const flags = row.validation_flags || [];
  openDrawer({
    title: row.service_area,
    eyebrow: 'RATIFIED-CURRENT BUDGET EVIDENCE',
    html: `${evidenceSteps([
      ['Business unit source heading', row.business_unit_source_heading],
      ['Fiscal year', row.fiscal_year],
      ['2024/25 actual', money(row.prior_actual)],
      ['2025/26 budget', money(row.prior_budget)],
      ['2025/26 projection', money(row.projection)],
      ['2026/27 budget', money(row.current_budget)],
      ['Published change', b18SignedMoney(row.source_reported_budget_change)],
      ['Published change %', b18PlainPct(row.source_reported_budget_change_pct)],
      ['Derived change', b18SignedMoney(row.derived_budget_change)],
      ['Derived change %', b18PlainPct(row.derived_budget_change_pct)],
      ['Source PDF page', row.source_page],
      ['Approval date', b18BudgetMeta().approval_date]
    ])}${flags.length ? `<div class="drawer-callout"><strong>Published source arithmetic flag</strong><p>${escapeHtml(flags.join(' · '))}. HalifaxData retains the printed value and the independently derived arithmetic; this is a source-data review item, not a finding of wrongdoing.</p></div>` : ''}<div class="drawer-callout"><strong>Interpretation boundary</strong><p>Budget authority is not evidence of a payment, invoice, commitment or final cost.</p></div>${b18SourceEvidence('Amount source', source)}${b18SourceEvidence('Approval source', approval)}`
  });
}

function b18ShowCapitalRow(projectAccountId) {
  const row = b18CapitalRows().find(item => item.project_account_id === projectAccountId);
  if (!row) return;
  const source = sourceById(row.source_id);
  const approval = sourceById(row.approval_source_id);
  openDrawer({
    title: row.project_name,
    eyebrow: 'APPROVED-CURRENT CAPITAL SCHEDULE EVIDENCE',
    html: `${evidenceSteps([
      ['Project account ID', row.project_account_id],
      ['Schedule class', b18CapitalClassLabel(row.schedule_class)],
      ['Previous years gross budget', money(row.total_previous_years_gross_budget)],
      ['2025/26 capital budget', money(row.capital_budget_2025_26)],
      ['2026/27 capital budget', money(row.capital_budget_2026_27)],
      ['2027/28 capital budget', money(row.capital_budget_2027_28)],
      ['2028/29 capital budget', money(row.capital_budget_2028_29)],
      ['2029/30 capital budget', money(row.capital_budget_2029_30)],
      ['2030/31–2035/36 capital budget', money(row.capital_budget_2030_31_to_2035_36)],
      ['Row Grand Total', money(row.grand_total)],
      ['Source PDF / table / row', `${row.source_page} / ${row.source_table} / ${row.source_row}`],
      ['Approval date', b18CapitalMeta().approval_date]
    ])}<div class="drawer-callout"><strong>Interpretation boundary</strong><p>This row is scheduled capital budget authority/cashflow. It is not spend-to-date, a payment, commitment, invoice, final cost or evidence of an overrun.</p></div>${b18SourceEvidence('Schedule source', source)}${b18SourceEvidence('Approval source', approval)}`
  });
}

function b18EnhanceBudget() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b18-current-budget')) return;
  stack.insertAdjacentHTML('afterbegin', b18CurrentBudgetPanel());
}
function b18EnhanceProjects() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b18-current-capital')) return;
  const current = stack.querySelector('.b10-current-capital');
  if (current) current.insertAdjacentHTML('beforebegin', b18CurrentCapitalPanel());
  else stack.insertAdjacentHTML('afterbegin', b18CurrentCapitalPanel());
}

function b18BindEvents() {
  const budgetSearch = $('#b18-budget-search');
  if (budgetSearch) budgetSearch.addEventListener('input', event => {
    state.build018BudgetQuery = event.target.value;
    render();
    requestAnimationFrame(() => { const input = $('#b18-budget-search'); if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); } });
  });
  const budgetUnit = $('#b18-budget-unit');
  if (budgetUnit) budgetUnit.addEventListener('change', event => { state.build018BudgetUnit = event.target.value; render(); });
  const capitalSearch = $('#b18-capital-search');
  if (capitalSearch) capitalSearch.addEventListener('input', event => {
    state.build018CapitalQuery = event.target.value;
    render();
    requestAnimationFrame(() => { const input = $('#b18-capital-search'); if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); } });
  });
  const capitalClass = $('#b18-capital-class');
  if (capitalClass) capitalClass.addEventListener('change', event => { state.build018CapitalClass = event.target.value; render(); });
  $$('#content [data-build018-budget-row]').forEach(row => row.addEventListener('click', () => b18ShowBudgetRow(row.dataset.build018BudgetRow)));
  $$('#content [data-build018-capital-row]').forEach(row => row.addEventListener('click', () => b18ShowCapitalRow(row.dataset.build018CapitalRow)));
}

window.b18BudgetRows = b18BudgetRows;
window.b18CapitalRows = b18CapitalRows;
window.b18BudgetMeta = b18BudgetMeta;
window.b18CapitalMeta = b18CapitalMeta;

const b18RenderBase = render;
render = function renderBuild018() {
  b18MergeSources();
  b18RenderBase();
  if (state.view === 'budget') b18EnhanceBudget();
  if (state.view === 'projects') b18EnhanceProjects();
  b18BindEvents();
};
