/* Build 010 — Current Capital Cost Control
 * Derived presentation over validated current_capital.json.
 * Current plan estimates, approved budget adjustments, and exact-code plan changes
 * remain separate from actual spend, transactions, commitments, and final cost.
 */

state.build010Capital = { status: 'loading', data: null, error: null };
state.build010CapitalQuery = '';
state.build010CapitalCategory = 'all';

fetch('./data/generated/current_capital.json', { cache: 'no-store' })
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(data => {
    state.build010Capital = { status: 'ready', data, error: null };
    if (typeof render === 'function') render();
  })
  .catch(error => {
    state.build010Capital = { status: 'error', data: null, error: error.message };
    if (typeof render === 'function') render();
  });

function b10Data() { return state.build010Capital?.data || null; }
function b10Meta() { return b10Data()?.metadata || {}; }
function b10Rows(key) { return Array.isArray(b10Data()?.[key]) ? b10Data()[key] : []; }
function b10Number(value) { const n = Number(value); return Number.isFinite(n) ? n : null; }
function b10SignedMoney(value) {
  const n = b10Number(value);
  if (n == null) return '—';
  return `${n >= 0 ? '+' : '-'}${compactMoney(Math.abs(n))}`;
}
function b10Pct(value) {
  const n = b10Number(value);
  if (n == null) return '—';
  return `${n >= 0 ? '+' : ''}${decimalFmt.format(n * 100)}%`;
}
function b10MonthShift(value) {
  const n = b10Number(value);
  if (n == null) return '—';
  if (n === 0) return 'no schedule change';
  return `${n > 0 ? '+' : ''}${numberFmt.format(n)} month${Math.abs(n) === 1 ? '' : 's'}`;
}
function b10AnnualBudget(row, year = '2025/26') { return b10Number(row?.annual_budgets?.[year]); }

function b10AdjustmentGroups() {
  const rows = b10Rows('adjustments');
  return {
    increases: rows.filter(row => row.adjustment_type === 'capital_budget_increase'),
    transfers: rows.filter(row => row.adjustment_type === 'capital_budget_transfer'),
    external: rows.filter(row => row.adjustment_type === 'external_cost_sharing_award')
  };
}

function b10PlanMovements() {
  return b10Rows('plan_comparisons').filter(row => {
    const delta = b10Number(row.estimated_project_cost_change);
    const pct = b10Number(row.estimated_project_cost_change_pct);
    return delta != null && delta > 0 && (delta >= 1000000 || (pct != null && pct >= 0.15 && delta >= 250000));
  }).sort((a, b) => Number(b.estimated_project_cost_change || 0) - Number(a.estimated_project_cost_change || 0));
}

function b10ScheduleMovements() {
  return b10Rows('plan_comparisons').filter(row => {
    const execution = b10Number(row.execution_end_change_months);
    const operational = b10Number(row.operational_date_change_months);
    return (execution != null && execution >= 6) || (operational != null && operational >= 6);
  }).sort((a, b) => Math.max(Number(b.execution_end_change_months || 0), Number(b.operational_date_change_months || 0)) - Math.max(Number(a.execution_end_change_months || 0), Number(a.operational_date_change_months || 0)));
}

function b10CapitalInvestigations() {
  if (state.build010Capital?.status !== 'ready') return [];
  const { increases } = b10AdjustmentGroups();
  const movements = b10PlanMovements();
  const maxAdjustment = Math.max(1, ...increases.map(row => Math.abs(Number(row.adjustment_amount || 0))));
  const maxMovement = Math.max(1, ...movements.map(row => Math.abs(Number(row.estimated_project_cost_change || 0))));
  const items = [];

  for (const row of increases) {
    const delta = Number(row.adjustment_amount || 0);
    const before = Number(row.approved_budget_before || 0);
    const fraction = before ? delta / Math.abs(before) : null;
    const materiality = b8ScoreMateriality(delta, maxAdjustment);
    const deviation = fraction == null ? 60 : b8ScoreDeviation(fraction, 180);
    const persistence = 86;
    const evidence = 100;
    const score = Math.max(91, b8OverallScore({ materiality, deviation, persistence, evidence }));
    items.push({
      id: `b10-cap-adjust-${b8Slug(row.project_code)}`,
      domain: 'Capital', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${row.project_name} approved capital budget increase`,
      detail: `Council approved ${b10SignedMoney(delta)} · ${compactMoney(before)} → ${compactMoney(row.approved_budget_after)} on 2025-05-27`,
      materialityText: `${compactMoney(delta)} explicit approved budget increase`,
      scope: `${row.project_code} · Council-approved budget adjustment; not actual spend or final cost`,
      sourceIds: ['hrm-escribe'],
      evidenceRows: [
        ['Project code', row.project_code], ['Project', row.project_name],
        ['Approved budget before', money(row.approved_budget_before)],
        ['Approved increase', b10SignedMoney(row.adjustment_amount)],
        ['Approved budget after', money(row.approved_budget_after)],
        ['Council decision date', '2025-05-27'],
        ['Council result', b10Data()?.decision?.motion_result || 'Approved'],
        ['Source locator', `Council report p${row.source_page || '—'} / table ${row.source_table || '—'} / row ${row.source_row || '—'}`]
      ],
      caveat: 'This is a Council-approved capital-budget increase. It is not evidence that this amount has been spent, that invoices have been paid, that the project is over budget versus actuals, or that the increase is improper.'
    });
  }

  for (const row of movements.slice(0, 30)) {
    const delta = Number(row.estimated_project_cost_change || 0);
    const pct = b10Number(row.estimated_project_cost_change_pct);
    const scheduleMonths = Math.max(Number(row.execution_end_change_months || 0), Number(row.operational_date_change_months || 0));
    const materiality = b8ScoreMateriality(delta, maxMovement);
    const deviation = pct == null ? 25 : b8ScoreDeviation(pct, 180);
    const persistence = b8Clamp(30 + Math.max(0, scheduleMonths) * 1.2);
    const evidence = 96;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    items.push({
      id: `b10-cap-plan-${b8Slug(row.project_code)}`,
      domain: 'Capital', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${row.project_name_2025_26} plan estimate movement`,
      detail: `2024/25 → 2025/26 final plans · ${b10SignedMoney(delta)}${pct == null ? '' : ` (${b10Pct(pct)})`}${scheduleMonths >= 6 ? ` · schedule endpoint ${b10MonthShift(scheduleMonths)}` : ''}`,
      materialityText: `${compactMoney(delta)} higher total estimated project cost in the newer plan`,
      scope: `${row.project_code} · exact current project code in both final capital plans`,
      sourceIds: ['hrm-capital-2024-25', 'hrm-capital-2025-26'],
      evidenceRows: [
        ['Project code', row.project_code],
        ['2024/25 project name', row.project_name_2024_25],
        ['2025/26 project name', row.project_name_2025_26],
        ['2024/25 total estimated project cost', money(row.prior_total_estimated_project_cost)],
        ['2025/26 total estimated project cost', money(row.current_total_estimated_project_cost)],
        ['Plan estimate movement', b10SignedMoney(delta)],
        ['Relative movement', b10Pct(pct)],
        ['Execution-end change', b10MonthShift(row.execution_end_change_months)],
        ['Operational-date change', b10MonthShift(row.operational_date_change_months)],
        ['Comparison method', 'Exact Capital Project # in both final plans']
      ],
      caveat: 'This is a change in the total estimated project cost published in two successive final capital plans. It is not actual spend, a contract amendment, an invoice total, a final project cost, or by itself proof of a cost overrun.'
    });
  }
  return items.sort((a, b) => b.score - a.score);
}

const b10AllInvestigationsBase = b8AllInvestigations;
b8AllInvestigations = function b8AllInvestigationsBuild010() {
  const result = b10AllInvestigationsBase();
  const capital = b10CapitalInvestigations();
  if (!capital.length) return result;
  const fiscal = [...result.fiscal, ...capital].sort((a, b) => b.score - a.score);
  const all = [...fiscal, ...result.quality];
  build008InvestigationIndex = new Map(all.map(item => [item.id, item]));
  return { fiscal, quality: result.quality };
};

function b10FilteredProjects() {
  const query = normalize(state.build010CapitalQuery);
  return b10Rows('current_projects').filter(row =>
    (state.build010CapitalCategory === 'all' || row.asset_category === state.build010CapitalCategory) &&
    (!query || normalize(`${row.project_code} ${row.project_name} ${row.previous_code || ''} ${row.asset_category || ''} ${row.service_area || ''} ${row.project_type || ''} ${row.executive_director || ''}`).includes(query))
  );
}

function b10AdjustmentHtml() {
  const { increases, transfers, external } = b10AdjustmentGroups();
  const increaseTotal = increases.reduce((sum, row) => sum + Number(row.adjustment_amount || 0), 0);
  const transferNet = transfers.reduce((sum, row) => sum + Number(row.adjustment_amount || 0), 0);
  const externalTotal = external.reduce((sum, row) => sum + Number(row.adjustment_amount || 0), 0);
  return `<div class="b10-adjustment-stack">
    <div class="b10-adjustment-summary">
      <div><strong>${compactMoney(increaseTotal)}</strong><span>explicit capital-budget increases</span></div>
      <div><strong>${compactMoney(transferNet)}</strong><span>net effect of eight budget transfers</span></div>
      <div><strong>${compactMoney(externalTotal)}</strong><span>new external cost-sharing awards</span></div>
    </div>
    <div class="b10-adjustment-columns">
      <section><h3>Budget increases</h3>${increases.map(row => `<button type="button" class="b10-row-button" data-build008-investigation-id="b10-cap-adjust-${escapeHtml(b8Slug(row.project_code))}"><strong>${escapeHtml(row.project_name)}</strong><span>${escapeHtml(row.project_code)} · ${b10SignedMoney(row.adjustment_amount)} · ${money(row.approved_budget_before)} → ${money(row.approved_budget_after)}</span></button>`).join('')}</section>
      <section><h3>Net-zero transfers</h3>${transfers.map(row => `<div class="b10-static-row"><strong>${escapeHtml(row.project_name)}</strong><span>${escapeHtml(row.project_code)} · ${b10SignedMoney(row.adjustment_amount)}</span></div>`).join('')}</section>
      <section><h3>External cost sharing</h3>${external.map(row => `<div class="b10-static-row"><strong>${escapeHtml(row.project_name)}</strong><span>${escapeHtml(row.project_code)} · ${b10SignedMoney(row.adjustment_amount)}</span></div>`).join('')}</section>
    </div>
    <p class="table-note">Council approved the adjustment package on 2025-05-27. External cost-sharing changes are source-described as having no net increase from HRM funding; the eight transfer rows net to $0. Neither set is treated as overspending.</p>
  </div>`;
}

function b10PlanMovementHtml() {
  const movements = b10PlanMovements().slice(0, 12);
  return movements.length ? `<div class="b8-investigation-grid">${movements.map(row => {
    const item = b10CapitalInvestigations().find(candidate => candidate.id === `b10-cap-plan-${b8Slug(row.project_code)}`);
    return item ? b8InvestigationCard(item) : '';
  }).join('')}</div>` : emptyState('No qualifying plan movements', 'No exact-code project comparisons meet the current materiality screen.');
}

function b10ScheduleHtml() {
  const rows = b10ScheduleMovements().slice(0, 10);
  if (!rows.length) return emptyState('No schedule movements', 'No exact-code comparison moved an execution/operational endpoint by at least six months.');
  return `<div class="rule-list">${rows.map(row => {
    const maxShift = Math.max(Number(row.execution_end_change_months || 0), Number(row.operational_date_change_months || 0));
    return `<div><strong>${escapeHtml(row.project_name_2025_26)} · ${b10MonthShift(maxShift)}</strong><span>${escapeHtml(row.project_code)} · execution ${escapeHtml(row.prior_execution_end || '—')} → ${escapeHtml(row.current_execution_end || '—')} · operational ${escapeHtml(row.prior_operational_date || '—')} → ${escapeHtml(row.current_operational_date || '—')}</span></div>`;
  }).join('')}</div>`;
}

function b10ProjectExplorerHtml() {
  const all = b10Rows('current_projects');
  const rows = b10FilteredProjects();
  const categories = [...new Set(all.map(row => row.asset_category).filter(Boolean))].sort((a, b) => a.localeCompare(b));
  const visible = [...rows].sort((a, b) => Number(b10AnnualBudget(b) || 0) - Number(b10AnnualBudget(a) || 0) || String(a.project_name).localeCompare(String(b.project_name))).slice(0, 150);
  return `<div class="local-toolbar build006-toolbar"><label class="local-search"><span>⌕</span><input id="b10-capital-search" value="${escapeHtml(state.build010CapitalQuery)}" placeholder="Search current project, code, service area" /></label><select id="b10-capital-category"><option value="all">All current asset categories</option>${categories.map(category => `<option value="${escapeHtml(category)}" ${category === state.build010CapitalCategory ? 'selected' : ''}>${escapeHtml(category)}</option>`).join('')}</select><span class="table-note">Showing ${numberFmt.format(visible.length)} of ${numberFmt.format(rows.length)} matching current projects</span></div>
    <div class="table-wrap"><table><thead><tr><th>Project code</th><th>Current project</th><th>Asset category</th><th>Service area</th><th>Type</th><th class="numeric">2025/26 planned budget</th><th class="numeric">Total estimated project cost</th><th>Execution end</th><th>Operational</th></tr></thead><tbody>${visible.map(row => `<tr data-build010-project="${escapeHtml(row.project_code)}"><td><strong>${escapeHtml(row.project_code)}</strong>${row.previous_code ? `<small class="cell-sub">previous ${escapeHtml(row.previous_code)}</small>` : ''}</td><td>${escapeHtml(row.project_name)}</td><td>${escapeHtml(row.asset_category || '—')}</td><td>${escapeHtml(row.service_area || '—')}</td><td>${escapeHtml(row.project_type || '—')}</td><td class="numeric">${money(b10AnnualBudget(row))}</td><td class="numeric">${money(row.total_estimated_project_cost)}</td><td>${escapeHtml(row.execution_end || '—')}</td><td>${escapeHtml(row.operational_date || '—')}</td></tr>`).join('')}</tbody></table></div>`;
}

function b10CurrentCapitalSection() {
  if (state.build010Capital?.status === 'loading') return `<section class="panel b10-current-capital"><header class="panel-header"><div><h2>Current capital control</h2><p>Loading validated 2025/26 plan evidence.</p></div></header><div class="panel-body">${emptyState('Loading current capital evidence', 'Reading the checked-in Build 010 artifact.')}</div></section>`;
  if (state.build010Capital?.status === 'error') return `<section class="panel b10-current-capital"><header class="panel-header"><div><h2>Current capital control</h2><p>Validated artifact could not be loaded.</p></div></header><div class="panel-body">${emptyState('Current-capital artifact error', state.build010Capital.error || 'Unknown error')}</div></section>`;
  const meta = b10Meta();
  const { increases } = b10AdjustmentGroups();
  const increaseTotal = increases.reduce((sum, row) => sum + Number(row.adjustment_amount || 0), 0);
  const current = b10Rows('current_projects');
  const comparisons = b10Rows('plan_comparisons');
  const adjustments = b10Rows('adjustments');
  const costFacts = current.filter(row => b10Number(row.total_estimated_project_cost) != null).length;
  return `<section class="b10-current-capital page-stack">
    <div class="notice"><strong>Current-capital boundary</strong><span>Build 010 uses final 2024/25 and 2025/26 capital-plan project sheets plus Council-approved 2025/26 budget adjustments. These are plan/budget facts—not transaction-level spend, invoices, commitments, final project costs, or proof of an overrun.</span></div>
    <div class="metrics-grid">
      ${metricCard('Current 2025/26 projects', numberFmt.format(current.length), `${numberFmt.format(costFacts)} publish a total estimated project cost`, 'accent')}
      ${metricCard('Exact-code plan comparisons', numberFmt.format(comparisons.length), 'Same authoritative Capital Project # in both final plans', 'neutral')}
      ${metricCard('Approved adjustment rows', numberFmt.format(adjustments.length), '4 external awards · 8 transfers · 2 budget increases', 'neutral')}
      ${metricCard('Explicit budget increases', compactMoney(increaseTotal), 'Two Council-approved debt-financed project increases', 'warn')}
    </div>
    ${panel('Approved 2025/26 capital budget adjustments', 'Council-approved changes are separated into true budget increases, net-zero transfers and external cost-sharing awards.', b10AdjustmentHtml())}
    ${panel('Plan-over-plan estimated project cost movement', 'Exact project-code comparison between the final 2024/25 and 2025/26 capital plans. A higher plan estimate is not labeled an overrun.', b10PlanMovementHtml())}
    <div class="split-grid wide-left">${panel('Current capital project explorer', 'Current project-sheet fields from the final 2025/26 plan. Planned budget is not spend-to-date.', b10ProjectExplorerHtml())}${panel('Schedule movement context', 'Largest exact-code shifts of at least six months between published plan endpoints.', b10ScheduleHtml())}</div>
    <div class="notice subtle"><strong>Historical archive remains below</strong><span>The existing ArcGIS project layer is still preserved as historical evidence. Build 010 does not force current plan projects onto that historical geography or treat old rows as current cost-control facts.</span></div>
  </section>`;
}

function b10ShowProject(code) {
  const row = b10Rows('current_projects').find(item => item.project_code === code);
  if (!row) return;
  const source = sourceById(row.source_id);
  openDrawer({
    title: row.project_name,
    eyebrow: 'CURRENT CAPITAL PLAN EVIDENCE',
    html: `${evidenceSteps([
      ['Capital Project #', row.project_code], ['Previous #', row.previous_code || '—'],
      ['Asset category', row.asset_category || '—'], ['Service area', row.service_area || '—'],
      ['Project type', row.project_type || '—'], ['Executive Director / Chief', row.executive_director || '—'],
      ['2025/26 planned budget', money(b10AnnualBudget(row))],
      ['Unspent previous budget', money(row.unspent_previous_budget)],
      ['Previously approved budget', money(row.previously_approved_budget)],
      ['Estimated remaining budget required', money(row.estimated_remaining_budget_required)],
      ['Total estimated project cost', money(row.total_estimated_project_cost)],
      ['Execution timing', `${row.execution_start || '—'} → ${row.execution_end || '—'}`],
      ['Estimated asset operational date', row.operational_date || '—'],
      ['Source page(s)', (row.source_pages || [row.source_page]).filter(Boolean).join(', ') || '—'],
      ['Source ID', row.source_id]
    ])}<div class="drawer-callout"><strong>Interpretation boundary</strong><p>This is a final capital-plan project sheet. Planned budget and total estimated project cost are not actual spend, invoices, commitments, or final cost.</p></div>${source ? `<div class="drawer-section"><h3>Official source</h3><a class="source-link" href="${escapeHtml(safeUrl(source.url) || '#')}" target="_blank" rel="noreferrer">${escapeHtml(source.name)} ↗</a></div>` : ''}`
  });
}

function b10BindEvents() {
  const search = $('#b10-capital-search');
  if (search) search.addEventListener('input', event => { state.build010CapitalQuery = event.target.value; render(); });
  const category = $('#b10-capital-category');
  if (category) category.addEventListener('change', event => { state.build010CapitalCategory = event.target.value; render(); });
  $$('#content [data-build010-project]').forEach(row => row.addEventListener('click', () => b10ShowProject(row.dataset.build010Project)));
  $$('#content [data-build008-investigation-id]').forEach(element => {
    if (element.dataset.b10Bound === '1') return;
    element.dataset.b10Bound = '1';
    element.addEventListener('click', () => b8ShowInvestigation(element.dataset.build008InvestigationId));
  });
}

function b10EnhanceProjects() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b10-current-capital')) return;
  stack.insertAdjacentHTML('afterbegin', b10CurrentCapitalSection());
}

const build009Render = render;
render = function renderBuild010() {
  build009Render();
  if (state.view === 'projects') b10EnhanceProjects();
  b10BindEvents();
};
