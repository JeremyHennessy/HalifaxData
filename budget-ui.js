/* Build 004 budget/actuals UI integration.
 * Loaded after app.js and compensation-ui.js so the approved Build 002/003 shell stays intact.
 * Budget-book service-area rows and audited PSAS rows remain separate accounting views.
 */

state.budgetUnit = 'all';
state.budgetQuery = '';

function budgetDataRows() { return getRows(datasetStatus('budget').data); }
function budgetServiceRows() { return budgetDataRows().filter(row => row.record_type === 'service_area_budget'); }
function budgetAuditedRows() { return budgetDataRows().filter(row => row.record_type === 'audited_psas'); }
function budgetWarning(row) { return Array.isArray(row?.validation_flags) && row.validation_flags.length > 0; }
function budgetSourceMismatchCount() { return budgetServiceRows().filter(budgetWarning).length; }
function budgetUnitOptions() { return [...new Set(budgetServiceRows().map(row => row.business_unit).filter(Boolean))].sort((a,b) => a.localeCompare(b)); }
function budgetRowKey(row) { return `${row.business_unit}||${row.source_service_area_label || row.service_area}`; }
function findBudgetRow(key) { return budgetServiceRows().find(row => budgetRowKey(row) === key) || null; }
function findAuditedRow(key) { return budgetAuditedRows().find(row => `${row.statement_section}||${row.category}` === key) || null; }

function budgetVarianceText(actual, budget) {
  if (actual == null || budget == null) return '—';
  const delta = Number(actual) - Number(budget);
  return `${delta >= 0 ? '+' : ''}${compactMoney(delta)} vs budget`;
}
function budgetDelta(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const n = Number(value);
  return `${n >= 0 ? '+' : ''}${money(n)}`;
}
function budgetPctPlain(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Number(value) >= 0 ? '+' : ''}${decimalFmt.format(Number(value))}%`;
}

const build003Render = render;
render = function renderWithBudgetIntegration() {
  build003Render();
  const budgetRoute = state.view === 'budget';
  const filterbar = $('.filterbar');
  const yearLabel = $('#global-year')?.closest('label');
  const unitLabel = $('#global-unit')?.closest('label');
  if (filterbar) filterbar.hidden = budgetRoute;
  if (yearLabel) yearLabel.hidden = budgetRoute;
  if (unitLabel) unitLabel.hidden = budgetRoute;
};

renderBudget = function renderBudgetIntegrated() {
  const ds = datasetStatus('budget');
  if (ds.status !== 'ready') {
    return `<div class="page-stack">${evidenceNotice()}${domainIntro('budget', ['variance','growth','mix','forecast accuracy'])}<div class="split-grid wide-left">${panel('Budget line explorer', 'Trace plan → projection → actual while preserving accounting basis.', emptyState('Budget fact table awaits ingestion', 'The official budget and audited-financial sources are registered, but the generated artifact is not available.'))}${panel('Budget source coverage', 'Registered documents relevant to this analysis.', domainSources('budget'))}</div></div>`;
  }

  const allService = budgetServiceRows();
  const audited = budgetAuditedRows();
  const query = normalize(state.budgetQuery);
  const service = allService.filter(row =>
    (state.budgetUnit === 'all' || row.business_unit === state.budgetUnit) &&
    (!query || normalize(`${row.business_unit} ${row.service_area} ${row.source_service_area_label || ''}`).includes(query))
  );
  const details = allService.filter(row => !row.is_total);
  const units = new Set(allService.map(row => row.business_unit)).size;
  const sourceWarnings = budgetSourceMismatchCount();
  const auditedByKey = new Map(audited.map(row => [`${row.statement_section}||${row.category}`, row]));
  const revenue = auditedByKey.get('revenue||Total revenue');
  const expenses = auditedByKey.get('expense||Total expenses');
  const surplus = auditedByKey.get('surplus||Annual surplus');

  return `<div class="page-stack">
    <div class="notice"><strong>Accounting basis boundary</strong><span>The 2025/26 Budget & Business Plan service-area tables and the March 31, 2025 audited PSAS statement are separate accounting views. HalifaxData does not force audited PSAS categories onto departmental/service-area budgets where the source classifications do not match.</span></div>
    <div class="metrics-grid">
      ${metricCard('2025/26 service areas', numberFmt.format(details.length), `${units} business units · 2023/24 actual → 2025/26 budget`, 'accent')}
      ${metricCard('Audited revenue', compactMoney(revenue?.actual), budgetVarianceText(revenue?.actual, revenue?.budget), 'good')}
      ${metricCard('Audited expenses', compactMoney(expenses?.actual), budgetVarianceText(expenses?.actual, expenses?.budget), Number(expenses?.actual) > Number(expenses?.budget) ? 'warn' : 'good')}
      ${metricCard('Audited annual surplus', compactMoney(surplus?.actual), budgetVarianceText(surplus?.actual, surplus?.budget), 'good')}
    </div>
    ${sourceWarnings ? `<div class="notice"><strong>${sourceWarnings} source arithmetic flags</strong><span>The budget book contains published change/percentage values that do not always reconcile to the same row's published budget endpoints. HalifaxData retains both the published and independently derived values and flags the difference; these are source-data review items, not findings of wrongdoing.</span></div>` : ''}
    ${panel('2025/26 service-area budget explorer', 'Source-published service-area history. Use the local filter because compensation business-unit labels are a different source-defined dimension.', `<div class="local-toolbar budget-toolbar"><label class="local-search"><span>⌕</span><input id="budget-search" value="${escapeHtml(state.budgetQuery)}" placeholder="Search service area or business unit" /></label><select id="budget-unit"><option value="all">All budget business units</option>${budgetUnitOptions().map(unit => `<option value="${escapeHtml(unit)}" ${unit === state.budgetUnit ? 'selected' : ''}>${escapeHtml(unit)}</option>`).join('')}</select><span class="table-note">${numberFmt.format(service.length)} rows</span></div>${budgetServiceTable(service)}`)}
    <div class="split-grid wide-left">
      ${panel('Audited 2024/25 operating results', 'Consolidated Statement of Operations and Accumulated Surplus. Source amounts were published in $000s and are stored/displayed as CAD.', budgetAuditedTable(audited))}
      ${panel('Evidence & interpretation', 'How to read the two accounting views.', `<div class="rule-list"><div><strong>Budget-book service areas</strong><span>2023/24 actual, 2024/25 budget/projection and 2025/26 budget from the Budget & Business Plan.</span></div><div><strong>Audited PSAS</strong><span>2025 budget, 2025 actual and 2024 actual from the audited consolidated statement.</span></div><div><strong>Published Δ vs derived Δ</strong><span>Published change columns remain source facts. Derived change is independently calculated from the displayed budget endpoints.</span></div><div><strong>No forced crosswalk</strong><span>PSAS categories and departmental service areas are not assumed equivalent without explicit reconciliation evidence.</span></div></div>${domainSources('budget')}`)}
    </div>
  </div>`;
};

function budgetServiceTable(rows) {
  if (!rows.length) return emptyState('No matching budget rows', 'Change the local budget business-unit or text filter.');
  return `<div class="table-wrap"><table class="budget-table"><thead><tr><th>Business unit</th><th>Service area</th><th class="numeric">2023/24 actual</th><th class="numeric">2024/25 budget</th><th class="numeric">2024/25 projection</th><th class="numeric">2025/26 budget</th><th class="numeric">Published Δ</th><th class="numeric">Derived Δ</th></tr></thead><tbody>${rows.map(row => `<tr class="${budgetWarning(row) ? 'budget-source-warning' : ''}" data-budget-row="${escapeHtml(budgetRowKey(row))}"><td>${escapeHtml(row.business_unit)}</td><td><strong>${escapeHtml(row.service_area)}</strong>${row.service_area !== row.source_service_area_label ? `<small class="cell-sub">source label: ${escapeHtml(row.source_service_area_label)}</small>` : ''}${budgetWarning(row) ? '<small class="data-flag">source arithmetic flag</small>' : ''}</td><td class="numeric">${money(row.prior_actual)}</td><td class="numeric">${money(row.prior_budget)}</td><td class="numeric">${money(row.projection)}</td><td class="numeric"><strong>${money(row.current_budget)}</strong></td><td class="numeric">${budgetDelta(row.source_reported_budget_change)}<small class="cell-sub">${budgetPctPlain(row.source_reported_budget_change_pct)}</small></td><td class="numeric">${budgetDelta(row.derived_budget_change)}<small class="cell-sub">${budgetPctPlain(row.derived_budget_change_pct)}</small></td></tr>`).join('')}</tbody></table></div>`;
}

function budgetAuditedTable(rows) {
  if (!rows.length) return emptyState('No audited rows', 'The audited statement artifact is missing its operations rows.');
  return `<div class="table-wrap"><table><thead><tr><th>Section</th><th>Category</th><th class="numeric">2025 budget</th><th class="numeric">2025 actual</th><th class="numeric">Variance</th></tr></thead><tbody>${rows.map(row => `<tr data-audited-row="${escapeHtml(`${row.statement_section}||${row.category}`)}"><td>${badge(row.statement_section, row.statement_section === 'revenue' ? 'good' : row.statement_section === 'expense' ? 'warn' : 'info')}</td><td><strong>${escapeHtml(row.category)}</strong></td><td class="numeric">${money(row.budget)}</td><td class="numeric"><strong>${money(row.actual)}</strong></td><td class="numeric">${budgetDelta(row.variance)}</td></tr>`).join('')}</tbody></table></div>`;
}

function showBudgetRow(key) {
  const row = findBudgetRow(key); if (!row) return;
  const source = sourceById(row.source_id);
  const flagList = row.validation_flags || [];
  const rawLabel = row.source_service_area_label || row.service_area;
  const normalization = row.service_area !== rawLabel ? `<div class="drawer-section"><h3>Label normalization</h3>${evidenceSteps([['Raw source label', rawLabel], ['Canonical display label', row.service_area], ['Basis', row.label_normalization_basis], ['Evidence', row.label_normalization_evidence]])}</div>` : '';
  const arithmetic = flagList.length ? `<div class="drawer-callout"><strong>Published source arithmetic flag</strong><p>${escapeHtml(flagList.join(' · '))}. Published change: ${escapeHtml(budgetDelta(row.source_reported_budget_change))} (${escapeHtml(budgetPctPlain(row.source_reported_budget_change_pct))}); independently derived change: ${escapeHtml(budgetDelta(row.derived_budget_change))} (${escapeHtml(budgetPctPlain(row.derived_budget_change_pct))}). HalifaxData preserves the source values and does not reinterpret this as wrongdoing.</p></div>` : '';
  openDrawer({ title: row.service_area, eyebrow: 'BUDGET EVIDENCE', html: `${evidenceSteps([['Business unit', row.business_unit], ['Fiscal year', row.fiscal_year], ['2023/24 actual', money(row.prior_actual)], ['2024/25 budget', money(row.prior_budget)], ['2024/25 projection', money(row.projection)], ['2025/26 budget', money(row.current_budget)], ['Published budget change', budgetDelta(row.source_reported_budget_change)], ['Derived budget change', budgetDelta(row.derived_budget_change)], ['PDF page', row.pdf_page], ['Source ID', row.source_id]])}${arithmetic}${normalization}${source ? sourceLink(source) : ''}` });
}

function showAuditedBudgetRow(key) {
  const row = findAuditedRow(key); if (!row) return;
  const source = sourceById(row.source_id);
  openDrawer({ title: row.category, eyebrow: 'AUDITED PSAS EVIDENCE', html: `${evidenceSteps([['Statement section', row.statement_section], ['Fiscal year', row.fiscal_year], ['Budget', money(row.budget)], ['Actual', money(row.actual)], ['Variance', budgetDelta(row.variance)], ['Prior actual (2024)', money(row.prior_actual)], ['Source units', 'Source published in $000s; stored as CAD'], ['PDF / printed page', `${row.pdf_page} / ${row.printed_page}`], ['Source ID', row.source_id]])}<div class="drawer-callout"><strong>Accounting-basis boundary</strong><p>This audited PSAS row is not automatically mapped onto a Budget & Business Plan department or service area.</p></div>${source ? sourceLink(source) : ''}` });
}

const build003BindViewEvents = bindViewEvents;
bindViewEvents = function bindViewEventsWithBudget() {
  build003BindViewEvents();
  $$('#content [data-budget-row]').forEach(element => element.addEventListener('click', () => showBudgetRow(element.dataset.budgetRow)));
  $$('#content [data-audited-row]').forEach(element => element.addEventListener('click', () => showAuditedBudgetRow(element.dataset.auditedRow)));
  const budgetSearch = $('#budget-search');
  if (budgetSearch) budgetSearch.addEventListener('input', event => {
    state.budgetQuery = event.target.value; render();
    requestAnimationFrame(() => { const input = $('#budget-search'); if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); } });
  });
  const budgetUnit = $('#budget-unit');
  if (budgetUnit) budgetUnit.addEventListener('change', event => { state.budgetUnit = event.target.value; render(); });
};
