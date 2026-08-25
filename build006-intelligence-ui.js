/* Build 006 intelligence UI integration.
 * Loaded after the approved Build 005 shell/integrations.
 * Goal: expose the evidence already checked into the repository without inventing
 * granularity or crosswalks the source data does not support.
 */

const BUILD006_EXTRA_FILES = {
  budgetHistory: './data/generated/budget_history.json',
  councilDocuments: './data/generated/council_documents.json',
  benchmarks: './data/generated/benchmarks.json',
  externalFunding: './data/generated/external_funding.json'
};

state.build006 = Object.fromEntries(Object.keys(BUILD006_EXTRA_FILES).map(key => [key, { status: 'loading', data: null }]));
state.budgetHistoryYear = 'all';
state.budgetHistoryQuery = '';
state.spendingYear = 'all';
state.spendingType = 'all';
state.spendingQuery = '';
state.vendorEntity = 'all';
state.vendorQuery = '';
state.capitalYear = 'all';
state.capitalCategory = 'all';
state.capitalQuery = '';
state.financialYear = 'all';
state.financialFamily = 'all';
state.financialQuery = '';
state.councilYear = 'all';
state.councilType = 'all';
state.councilFinanceOnly = true;
state.councilQuery = '';
state.benchmarkScope = 'hrm';
state.benchmarkDataset = 'all';
state.benchmarkQuery = '';

const BUILD006_NEW_ROUTES = [
  ['financials', 'Financial Statements', '▥', 'AUDIT & BALANCE'],
  ['council', 'Council & Decisions', '▦', 'APPROVAL CONTEXT'],
  ['benchmarks', 'Benchmarks & Funding', '≋', 'EXTERNAL CONTEXT']
];

function insertNavItem(afterId, item) {
  if (NAV.some(existing => existing[0] === item[0])) return;
  const index = NAV.findIndex(existing => existing[0] === afterId);
  NAV.splice(index >= 0 ? index + 1 : NAV.length, 0, item);
}
insertNavItem('budget', BUILD006_NEW_ROUTES[0]);
insertNavItem('projects', BUILD006_NEW_ROUTES[1]);
insertNavItem('council', BUILD006_NEW_ROUTES[2]);

const requestedBuild006Route = location.hash.slice(1);
if (BUILD006_NEW_ROUTES.some(route => route[0] === requestedBuild006Route)) state.view = requestedBuild006Route;

async function fetchBuild006File(key, url) {
  try {
    const response = await fetch(url, { cache: 'no-store' });
    if (response.status === 404) return [key, { status: 'missing', data: null, url }];
    if (!response.ok) return [key, { status: 'error', data: null, url, error: `HTTP ${response.status}` }];
    return [key, { status: 'ready', data: await response.json(), url }];
  } catch (error) {
    return [key, { status: 'error', data: null, url, error: error.message }];
  }
}

Promise.all(Object.entries(BUILD006_EXTRA_FILES).map(([key, url]) => fetchBuild006File(key, url))).then(entries => {
  state.build006 = Object.fromEntries(entries);
  if (state.compensation && typeof render === 'function') render();
});

function build006Dataset(key) { return state.build006?.[key] || { status: 'missing', data: null }; }
function build006Rows(key) { return getRows(build006Dataset(key).data); }
function build006Meta(key) { return build006Dataset(key).data?.metadata || {}; }
function humanize(value) { return String(value || '').replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase()); }
function dateOnly(value) { return value ? String(value).slice(0, 10).replaceAll('/', '-') : '—'; }
function numberValue(value) { const n = Number(value); return Number.isFinite(n) ? n : null; }
function sumNumeric(rows, getter) { return rows.reduce((sum, row) => sum + (numberValue(getter(row)) || 0), 0); }
function uniqueSorted(values, compare = (a, b) => String(a).localeCompare(String(b))) { return [...new Set(values.filter(value => value !== null && value !== undefined && value !== ''))].sort(compare); }
function textContains(row, query, fields) { return !query || normalize(fields.map(field => typeof field === 'function' ? field(row) : row?.[field]).join(' ')).includes(normalize(query)); }
function statusTone(status) {
  const value = normalize(status);
  if (value.includes('final') || value === 'ready' || value === 'ok') return 'good';
  if (value.includes('proposed') || value.includes('pre-covid') || value.includes('pending')) return 'warn';
  if (value.includes('context') || value.includes('historical')) return 'info';
  if (value.includes('error')) return 'bad';
  return 'muted';
}
function visibleLimitNote(total, visible, label = 'rows') {
  return total > visible ? `<span class="table-note">Showing ${numberFmt.format(visible)} of ${numberFmt.format(total)} ${escapeHtml(label)}. Narrow the filters to inspect more.</span>` : `<span class="table-note">${numberFmt.format(total)} ${escapeHtml(label)}</span>`;
}
function build006LoadingPanel(title, key) {
  const ds = build006Dataset(key);
  if (ds.status === 'loading') return panel(title, 'Loading checked-in Build 006 evidence.', emptyState('Loading data', 'Reading the checked-in artifact.'));
  if (ds.status === 'error') return panel(title, 'The checked-in artifact could not be loaded.', emptyState('Artifact error', ds.error || 'Unknown error'));
  if (ds.status === 'missing') return panel(title, 'The expected checked-in artifact is absent.', emptyState('Artifact missing', BUILD006_EXTRA_FILES[key] || 'Expected generated artifact'));
  return '';
}

function build006OverviewHtml() {
  const procurement = getRows(datasetStatus('procurement').data);
  const capital = getRows(datasetStatus('capital').data);
  const financials = getRows(datasetStatus('financials').data);
  const council = getRows(datasetStatus('council').data);
  const councilDocs = build006Rows('councilDocuments');
  const budgetMeta = datasetStatus('budget').data?.metadata || {};
  const budgetFlags = Number(budgetMeta.budget_source_arithmetic_discrepancy_rows || 0);
  const compFlags = compensationRows().filter(row => Array.isArray(row.validation_flags) && row.validation_flags.includes('reported_total_mismatch')).length;
  const expenseOverrun = numberValue(budgetMeta.audited_total_expenses_actual) != null && numberValue(budgetMeta.audited_total_expenses_budget) != null
    ? Number(budgetMeta.audited_total_expenses_actual) - Number(budgetMeta.audited_total_expenses_budget)
    : null;
  const financeDocs = councilDocs.filter(row => row.finance_relevant).length;
  const councilMeta = datasetStatus('council').data?.metadata || {};

  return `<section class="build006-section">
    <div class="metrics-grid compact">
      ${metricCard('Public-tender awards', numberFmt.format(procurement.length), 'Collected award rows; not an accounts-payable ledger', 'accent')}
      ${metricCard('Historical capital projects', numberFmt.format(capital.length), 'Official ArcGIS historical planned-project layer', 'neutral')}
      ${metricCard('Audited statement facts', numberFmt.format(financials.length), 'Comparative statement/schedule rows from two audited reports', 'neutral')}
      ${metricCard('Finance-tagged Council docs', numberFmt.format(financeDocs), `${numberFmt.format(council.length)} meetings in endpoint coverage`, financeDocs ? 'good' : 'neutral')}
    </div>
    <div class="split-grid wide-left">
      ${panel('Cross-domain review leads', 'Evidence-backed prompts that now deserve inspection; none is a finding of wrongdoing.', `<div class="rule-list build006-rule-list">
        <div><strong>${budgetFlags} budget source arithmetic flags</strong><span>Published change values that do not reconcile to the same source row's displayed endpoints. Preserve and review the source evidence.</span></div>
        <div><strong>${compFlags} compensation source-total mismatches</strong><span>Published disclosure components and source-reported totals differ; the original source values remain intact.</span></div>
        <div><strong>${expenseOverrun == null ? 'Audited expense variance unavailable' : `${compactMoney(expenseOverrun)} audited expense variance`}</strong><span>${expenseOverrun == null ? 'No current audited expense variance could be derived.' : '2024/25 audited expenses minus the budget presented in the audited statement. This is an accounting variance, not evidence of improper spending.'}</span></div>
        <div><strong>${numberFmt.format(financeDocs)} finance-tagged Council attachments</strong><span>Budget, procurement, capital, financial reporting, grants, debt/reserves, tax/revenue and related agenda-document titles are now searchable for authorization context.</span></div>
      </div>`)}
      ${panel('Coverage gaps that still matter', 'The next data work should target the gaps that most constrain municipal-money investigations.', `<div class="rule-list build006-rule-list">
        <div><strong>No transaction-level AP ledger yet</strong><span>Quarterly spending is summary-table evidence. It cannot identify individual vendor payments or duplicate invoices.</span></div>
        <div><strong>Capital layer is historical, not current cost control</strong><span>The ArcGIS layer identifies planned projects and geography but does not contain current budget, spend-to-date, amendments or completion status.</span></div>
        <div><strong>Public tenders do not equal all procurement</strong><span>Alternative procurement, every amendment and final paid value are not present in the awarded-tender dataset.</span></div>
        <div><strong>Council endpoint begins in ${escapeHtml(councilMeta.available_from_year || '2024')}</strong><span>Older Council history needs a separate archival source; the current eSCRIBE calendar must not be represented as complete before its available window.</span></div>
      </div>`)}
    </div>
  </section>`;
}

function injectBuild006Overview() {
  const stack = document.querySelector('#content .page-stack');
  if (!stack || stack.querySelector('.build006-section')) return;
  const firstMetrics = stack.querySelector('.metrics-grid');
  if (firstMetrics) firstMetrics.insertAdjacentHTML('afterend', build006OverviewHtml());
  else stack.insertAdjacentHTML('afterbegin', build006OverviewHtml());
}

function filteredBudgetHistoryRows() {
  const rows = build006Rows('budgetHistory');
  return rows.filter(row =>
    (state.budgetHistoryYear === 'all' || String(row.fiscal_year) === state.budgetHistoryYear) &&
    textContains(row, state.budgetHistoryQuery, ['fiscal_year', 'business_unit', 'service_area', 'source_id', 'source_status'])
  );
}
function budgetHistoryPanelHtml() {
  const ds = build006Dataset('budgetHistory');
  if (ds.status !== 'ready') return build006LoadingPanel('Historical budget evidence', 'budgetHistory');
  const all = build006Rows('budgetHistory');
  const rows = filteredBudgetHistoryRows();
  const meta = build006Meta('budgetHistory');
  const years = uniqueSorted(all.map(row => row.fiscal_year), (a, b) => String(b).localeCompare(String(a)));
  const sources = uniqueSorted(all.map(row => row.source_id));
  const sourceStates = uniqueSorted(all.map(row => row.source_status));
  const visible = rows.slice(0, 250);

  return `<section class="panel build006-budget-history"><header class="panel-header"><div><h2>Historical budget evidence</h2><p>Validated older budget-book rows are shown exactly as their source state allows. Proposed/pre-COVID records are not silently promoted to final approved budgets, and historical business-unit labels are not force-crosswalked to the current organization.</p></div></header><div class="panel-body">
    <div class="metrics-grid compact">
      ${metricCard('Historical rows', numberFmt.format(all.length), `${sources.length} source documents`, 'accent')}
      ${metricCard('Fiscal-year labels', numberFmt.format(years.length), years.length ? `${years[years.length - 1]} → ${years[0]}` : '—', 'neutral')}
      ${metricCard('Rejected malformed rows', numberFmt.format(meta.rejected_invalid_numeric_rows || 0), 'Fail-closed PDF extraction', (meta.rejected_invalid_numeric_rows || 0) ? 'warn' : 'good')}
      ${metricCard('Extraction duplicates removed', numberFmt.format(meta.duplicates_removed || 0), `${sourceStates.length} explicit source state${sourceStates.length === 1 ? '' : 's'}`, 'neutral')}
    </div>
    <div class="local-toolbar build006-toolbar"><label class="local-search"><span>⌕</span><input id="budget-history-search" value="${escapeHtml(state.budgetHistoryQuery)}" placeholder="Search historical service area, unit or source" /></label><select id="budget-history-year"><option value="all">All historical fiscal years</option>${years.map(year => `<option value="${escapeHtml(year)}" ${year === state.budgetHistoryYear ? 'selected' : ''}>${escapeHtml(year)}</option>`).join('')}</select>${visibleLimitNote(rows.length, visible.length)}</div>
    <div class="table-wrap"><table><thead><tr><th>Fiscal year</th><th>Source state</th><th>Business unit</th><th>Service area</th><th class="numeric">Prior actual</th><th class="numeric">Prior budget</th><th class="numeric">Current budget</th></tr></thead><tbody>${visible.map(row => {
      const index = all.indexOf(row);
      return `<tr data-budget-history-index="${index}"><td>${escapeHtml(row.fiscal_year || '—')}</td><td>${badge(row.source_is_final ? 'Final source' : (row.source_status || 'Historical'), statusTone(row.source_status || (row.source_is_final ? 'final' : 'historical')))}</td><td>${escapeHtml(row.business_unit || '—')}</td><td><strong>${escapeHtml(row.service_area || '—')}</strong><small class="cell-sub">${escapeHtml(row.source_id || '')} · p${escapeHtml(row.source_page || '—')}</small></td><td class="numeric">${money(row.prior_actual)}</td><td class="numeric">${money(row.prior_budget)}</td><td class="numeric"><strong>${money(row.current_budget)}</strong></td></tr>`;
    }).join('')}</tbody></table></div>
  </div></section>`;
}
function injectBudgetHistoryPanel() {
  const stack = document.querySelector('#content .page-stack');
  if (!stack || stack.querySelector('.build006-budget-history')) return;
  stack.insertAdjacentHTML('beforeend', budgetHistoryPanelHtml());
}

function spendingLabel(row) {
  if (row.business_unit) return row.business_unit;
  const raw = Array.isArray(row.raw_cells) ? row.raw_cells.find(cell => /[A-Za-z]/.test(String(cell || '')) && String(cell).trim().length > 1) : null;
  return raw || row.category || row.account || humanize(row.record_type);
}
function filteredSpendingRows() {
  const rows = getRows(datasetStatus('spending').data);
  return rows.filter(row =>
    (state.spendingYear === 'all' || String(row.fiscal_year) === state.spendingYear) &&
    (state.spendingType === 'all' || String(row.record_type) === state.spendingType) &&
    textContains(row, state.spendingQuery, [spendingLabel, 'account', 'category', 'source_id', row => (row.raw_cells || []).join(' ')])
  );
}
renderSpending = function renderSpendingBuild006() {
  const ds = datasetStatus('spending');
  if (ds.status !== 'ready') return `<div class="page-stack">${evidenceNotice()}${domainIntro('spending', ['summary movement', 'quarterly context', 'source-row review'])}</div>`;
  const all = getRows(ds.data); const rows = filteredSpendingRows(); const meta = ds.data?.metadata || {};
  const years = uniqueSorted(all.map(row => row.fiscal_year), (a, b) => String(b).localeCompare(String(a)));
  const types = uniqueSorted(all.map(row => row.record_type));
  const sources = uniqueSorted(all.map(row => row.source_id));
  const visible = [...rows].sort((a, b) => String(b.posting_date || '').localeCompare(String(a.posting_date || '')) || Math.abs(Number(b.amount || 0)) - Math.abs(Number(a.amount || 0))).slice(0, 300);
  const largest = rows.reduce((best, row) => Math.abs(Number(row.amount || 0)) > Math.abs(Number(best?.amount || 0)) ? row : best, null);

  return `<div class="page-stack">
    <div class="notice"><strong>Granularity boundary</strong><span>This dataset contains official quarterly financial-summary table rows, not invoice or accounts-payable transactions. HalifaxData therefore does not display vendor/payment/project columns for these records and does not sum overlapping summary rows into a synthetic spending total.</span></div>
    <div class="metrics-grid">
      ${metricCard('Quarterly summary rows', numberFmt.format(all.length), `${sources.length} official quarterly reports`, 'accent')}
      ${metricCard('Fiscal-year coverage', numberFmt.format(years.length), years.join(' · ') || '—', 'neutral')}
      ${metricCard('Summary row types', numberFmt.format(types.length), types.map(humanize).join(' · '), 'neutral')}
      ${metricCard('Largest source-row amount', largest ? compactMoney(largest.amount) : '—', largest ? `${escapeHtml(spendingLabel(largest))} · ${escapeHtml(largest.fiscal_year || '')}` : 'No matching row', 'neutral')}
    </div>
    ${panel('Quarterly spending-summary explorer', 'Rows preserve the source table context, tokenized monetary values and page/table/row provenance.', `<div class="local-toolbar build006-toolbar"><label class="local-search"><span>⌕</span><input id="spending-search" value="${escapeHtml(state.spendingQuery)}" placeholder="Search row label, account, context or source" /></label><select id="spending-year"><option value="all">All fiscal years</option>${years.map(year => `<option value="${escapeHtml(year)}" ${year === state.spendingYear ? 'selected' : ''}>${escapeHtml(year)}</option>`).join('')}</select><select id="spending-type"><option value="all">All summary row types</option>${types.map(type => `<option value="${escapeHtml(type)}" ${type === state.spendingType ? 'selected' : ''}>${escapeHtml(humanize(type))}</option>`).join('')}</select>${visibleLimitNote(rows.length, visible.length)}</div><div class="table-wrap"><table><thead><tr><th>Period end</th><th>Fiscal year</th><th>Summary type</th><th>Source row label</th><th>Context</th><th class="numeric">Reported row amount</th><th>Source</th></tr></thead><tbody>${visible.map(row => {
      const index = all.indexOf(row);
      return `<tr data-spending-index="${index}"><td>${escapeHtml(row.posting_date || '—')}</td><td>${escapeHtml(row.fiscal_year || '—')}</td><td>${badge(humanize(row.record_type), 'info')}</td><td><strong>${escapeHtml(spendingLabel(row))}</strong></td><td>${escapeHtml(row.category || row.account || '—')}</td><td class="numeric"><strong>${money(row.amount)}</strong></td><td>${escapeHtml(row.source_id || '—')}<small class="cell-sub">p${escapeHtml(row.source_page || '—')} / t${escapeHtml(row.source_table || '—')}</small></td></tr>`;
    }).join('')}</tbody></table></div>`)}
    <div class="split-grid wide-left">${panel('What this can answer', 'Use these rows to inspect reported quarterly patterns without overstating granularity.', lensGrid([['Quarter-to-quarter source movement', 'Compare like summary labels and report periods when the source structure is comparable.'], ['Large source-row review', 'Inspect unusually large reported rows with the complete raw row and monetary tokens.'], ['Coverage differences', 'Identify report/table types that appear or disappear across quarters.'], ['Source reconciliation', 'Trace every displayed value back to PDF page/table/row evidence.']]))}${panel('What is still missing', 'These questions require more granular source data.', `<div class="rule-list"><div><strong>Vendor payments</strong><span>Requires transaction-level accounts-payable or cheque-register evidence.</span></div><div><strong>Duplicate invoices</strong><span>Cannot be tested from quarterly summary rows.</span></div><div><strong>Project-level actual spend</strong><span>Needs a project/payment or capital actuals source.</span></div></div>`)}
    </div>
  </div>`;
};

function filteredVendorRows() {
  const rows = getRows(datasetStatus('procurement').data);
  return rows.filter(row =>
    (state.vendorEntity === 'all' || row.entity === state.vendorEntity) &&
    textContains(row, state.vendorQuery, ['vendor_name', 'entity', 'award_id', 'description', 'category'])
  );
}
renderVendors = function renderVendorsBuild006() {
  const ds = datasetStatus('procurement');
  if (ds.status !== 'ready') return `<div class="page-stack">${evidenceNotice()}${domainIntro('procurement', ['award concentration', 'repeat awards', 'category mix'])}</div>`;
  const all = getRows(ds.data); const rows = filteredVendorRows(); const meta = ds.data?.metadata || {};
  const entities = uniqueSorted(all.map(row => row.entity));
  const uniqueVendors = new Set(rows.filter(row => row.vendor_name).map(row => `${normalize(row.entity)}||${normalize(row.vendor_name)}`)).size;
  const totalValue = sumNumeric(rows, row => row.original_award_value);
  const largest = rows.reduce((best, row) => Number(row.original_award_value || 0) > Number(best?.original_award_value || 0) ? row : best, null);
  const vendorTotals = new Map();
  rows.forEach(row => {
    const key = `${row.entity || 'Unknown'}||${row.vendor_name || 'Unknown vendor'}`;
    const current = vendorTotals.get(key) || { entity: row.entity || 'Unknown', vendor: row.vendor_name || 'Unknown vendor', count: 0, value: 0 };
    current.count += 1; current.value += Number(row.original_award_value || 0); vendorTotals.set(key, current);
  });
  const top = [...vendorTotals.values()].sort((a, b) => b.value - a.value).slice(0, 8);
  const visible = [...rows].sort((a, b) => String(b.awarded_date || '').localeCompare(String(a.awarded_date || '')) || Number(b.original_award_value || 0) - Number(a.original_award_value || 0)).slice(0, 300);

  return `<div class="page-stack">
    <div class="notice"><strong>Procurement coverage boundary</strong><span>These are official public-tender award rows for Halifax municipal bodies. They are not a complete procurement ledger, do not capture every alternative procurement, and do not establish later amendments or final paid value unless the source explicitly provides them.</span></div>
    <div class="metrics-grid">
      ${metricCard('Award rows', numberFmt.format(rows.length), `${numberFmt.format(all.length)} collected across all reporting entities`, 'accent')}
      ${metricCard('Published award value', compactMoney(totalValue), 'Sum of collected award-row values under the current filter', 'neutral')}
      ${metricCard('Vendor identities', numberFmt.format(uniqueVendors), 'Entity-scoped exact raw vendor names', 'neutral')}
      ${metricCard('Largest award row', largest ? compactMoney(largest.original_award_value) : '—', largest ? `${escapeHtml(largest.vendor_name || 'Unknown vendor')} · ${escapeHtml(largest.entity || '')}` : 'No matching row', 'neutral')}
    </div>
    <div class="split-grid wide-left">
      ${panel('Vendor & contract explorer', 'Search award date, municipal entity, vendor, tender ID, category and description.', `<div class="local-toolbar build006-toolbar"><label class="local-search"><span>⌕</span><input id="vendor-search" value="${escapeHtml(state.vendorQuery)}" placeholder="Search vendor, tender or description" /></label><select id="vendor-entity"><option value="all">All Halifax reporting entities</option>${entities.map(entity => `<option value="${escapeHtml(entity)}" ${entity === state.vendorEntity ? 'selected' : ''}>${escapeHtml(entity)}</option>`).join('')}</select>${visibleLimitNote(rows.length, visible.length, 'awards')}</div><div class="table-wrap"><table><thead><tr><th>Awarded</th><th>Entity</th><th>Vendor</th><th>Tender</th><th>Category</th><th>Description</th><th class="numeric">Award value</th></tr></thead><tbody>${visible.map(row => `<tr><td>${escapeHtml(dateOnly(row.awarded_date))}</td><td>${escapeHtml(row.entity || '—')}</td><td><strong>${escapeHtml(row.vendor_name || '—')}</strong></td><td>${escapeHtml(row.award_id || row.solicitation || '—')}</td><td>${escapeHtml(row.category || '—')}</td><td>${escapeHtml(row.description || '—')}</td><td class="numeric"><strong>${money(row.original_award_value)}</strong></td></tr>`).join('')}</tbody></table></div>`)}
      ${panel('Top collected award concentration', 'Ranking is based only on the public-tender award rows under the active entity/search filter.', top.length ? `<div class="rule-list">${top.map(item => `<div><strong>${escapeHtml(item.vendor)} · ${compactMoney(item.value)}</strong><span>${escapeHtml(item.entity)} · ${numberFmt.format(item.count)} award row${item.count === 1 ? '' : 's'} · ${totalValue ? decimalFmt.format(item.value / totalValue * 100) : '0'}% of filtered published award value</span></div>`).join('')}</div>` : emptyState('No vendor rows', 'Change the procurement filters.'))}
    </div>
    ${panel('Next procurement gaps', 'These are the highest-value additions for anomaly detection.', lensGrid([['Amendment history', 'Collect original award → amendment sequence → cumulative value from authoritative records.'], ['Alternative procurement', 'Add sole-source and other non-public-tender methods with applicable policy context.'], ['Submission / bidder counts', 'Use only where official tender records explicitly publish them.'], ['Final paid value', 'Connect awarded contracts to actual payment evidence when a transaction source becomes available.']]))}
  </div>`;
};

function filteredCapitalRows() {
  const rows = getRows(datasetStatus('capital').data);
  return rows.filter(row =>
    (state.capitalYear === 'all' || String(row.fiscal_year) === state.capitalYear) &&
    (state.capitalCategory === 'all' || String(row.category) === state.capitalCategory) &&
    textContains(row, state.capitalQuery, ['project_code', 'project_name', 'category', 'asset_type', 'location_description', 'work_description'])
  );
}
renderProjects = function renderProjectsBuild006() {
  const ds = datasetStatus('capital');
  if (ds.status !== 'ready') return `<div class="page-stack">${evidenceNotice()}${domainIntro('capital', ['historical project inventory', 'location', 'category'])}</div>`;
  const all = getRows(ds.data); const rows = filteredCapitalRows(); const meta = ds.data?.metadata || {};
  const years = uniqueSorted(all.map(row => row.fiscal_year), (a, b) => Number(b) - Number(a));
  const categories = uniqueSorted(all.map(row => row.category));
  const assetTypes = uniqueSorted(all.map(row => row.asset_type));
  const geocoded = rows.filter(row => numberValue(row.latitude) != null && numberValue(row.longitude) != null).length;
  const visible = [...rows].sort((a, b) => Number(b.fiscal_year || 0) - Number(a.fiscal_year || 0) || String(a.project_name || '').localeCompare(String(b.project_name || ''))).slice(0, 300);

  return `<div class="page-stack">
    <div class="notice"><strong>Historical-project boundary</strong><span>${escapeHtml(meta.note || 'This is the official historical project layer.')} The source does not provide current project budget, spend-to-date or amendment history, so HalifaxData no longer displays blank “current budget / actual spend” columns as if those fields existed.</span></div>
    <div class="metrics-grid">
      ${metricCard('Historical project rows', numberFmt.format(all.length), meta.collection_complete ? 'ArcGIS advertised count fully collected' : 'Collection status unavailable', 'accent')}
      ${metricCard('Year values', numberFmt.format(years.length), years.length ? `${years[years.length - 1]} → ${years[0]}` : '—', 'neutral')}
      ${metricCard('Project categories', numberFmt.format(categories.length), `${assetTypes.length} asset-type labels`, 'neutral')}
      ${metricCard('Geocoded filtered rows', numberFmt.format(geocoded), `${numberFmt.format(rows.length)} rows under current filter`, 'neutral')}
    </div>
    ${panel('Historical capital project explorer', 'Use project code, category, asset type, location and work description to inspect the historical planned-project universe.', `<div class="local-toolbar build006-toolbar"><label class="local-search"><span>⌕</span><input id="capital-search" value="${escapeHtml(state.capitalQuery)}" placeholder="Search project, code, location or work" /></label><select id="capital-year"><option value="all">All source years</option>${years.map(year => `<option value="${escapeHtml(year)}" ${String(year) === state.capitalYear ? 'selected' : ''}>${escapeHtml(year)}</option>`).join('')}</select><select id="capital-category"><option value="all">All categories</option>${categories.map(category => `<option value="${escapeHtml(category)}" ${category === state.capitalCategory ? 'selected' : ''}>${escapeHtml(category)}</option>`).join('')}</select>${visibleLimitNote(rows.length, visible.length, 'projects')}</div><div class="table-wrap"><table><thead><tr><th>Year</th><th>Project code</th><th>Project</th><th>Category</th><th>Asset type</th><th>Location</th><th>Work description</th></tr></thead><tbody>${visible.map(row => `<tr><td>${escapeHtml(row.fiscal_year || '—')}</td><td>${escapeHtml(row.project_code || '—')}</td><td><strong>${escapeHtml(row.project_name || '—')}</strong>${safeUrl(row.source_link) ? `<small class="cell-sub"><a href="${escapeHtml(safeUrl(row.source_link))}" target="_blank" rel="noreferrer">official project link ↗</a></small>` : ''}</td><td>${escapeHtml(row.category || '—')}</td><td>${escapeHtml(row.asset_type || '—')}</td><td>${escapeHtml(row.location_description || '—')}</td><td>${escapeHtml(row.work_description || '—')}</td></tr>`).join('')}</tbody></table></div>`)}
    <div class="split-grid">${panel('What this layer supports', 'Historical project discovery and source linkage.', `<div class="rule-list"><div><strong>Project identity</strong><span>Official project code/OBJECTID and raw project name are retained.</span></div><div><strong>Geographic context</strong><span>Location descriptions and coordinates are available where published.</span></div><div><strong>Historical category mix</strong><span>Project/category/asset-type distributions can be compared within this historical source.</span></div></div>`)}${panel('What still needs a current source', 'Do not infer these fields from the historical ArcGIS layer.', `<div class="rule-list"><div><strong>Current budget</strong><span>Requires normalized current capital-plan amounts.</span></div><div><strong>Spend-to-date / completion</strong><span>Requires actuals and authoritative status evidence.</span></div><div><strong>Contract amendments</strong><span>Requires procurement/Council linkage to exact project identifiers.</span></div></div>`)}</div>
  </div>`;
};

function filteredFinancialRows() {
  const rows = getRows(datasetStatus('financials').data);
  return rows.filter(row =>
    (state.financialYear === 'all' || String(row.fiscal_year_end) === state.financialYear) &&
    (state.financialFamily === 'all' || String(row.statement_family) === state.financialFamily) &&
    textContains(row, state.financialQuery, ['statement_family', 'statement', 'line_item', 'source_id'])
  );
}
function renderFinancialsBuild006() {
  const ds = datasetStatus('financials');
  if (ds.status !== 'ready') return `<div class="page-stack">${evidenceNotice()}${domainIntro('financials', ['audited position', 'operations', 'cash flow', 'comparative movements'])}</div>`;
  const all = getRows(ds.data); const rows = filteredFinancialRows(); const meta = ds.data?.metadata || {};
  const years = uniqueSorted(all.map(row => row.fiscal_year_end), (a, b) => Number(b) - Number(a));
  const families = uniqueSorted(all.map(row => row.statement_family));
  const latestYear = years[0];
  const movementBase = rows.filter(row => numberValue(row.current_year) != null && numberValue(row.prior_year) != null);
  const movements = [...movementBase].sort((a, b) => Math.abs(Number(b.current_year) - Number(b.prior_year)) - Math.abs(Number(a.current_year) - Number(a.prior_year))).slice(0, 8);
  const visible = [...rows].sort((a, b) => Number(b.fiscal_year_end || 0) - Number(a.fiscal_year_end || 0) || String(a.statement_family || '').localeCompare(String(b.statement_family || '')) || String(a.line_item || '').localeCompare(String(b.line_item || ''))).slice(0, 300);

  return `<div class="page-stack">
    <div class="notice"><strong>Audited-statement boundary</strong><span>${escapeHtml(meta.scope || '')} Comparative values are source-presented statement facts converted to CAD where the source publishes $000s. HalifaxData does not force PSAS statement categories onto operational departments.</span></div>
    <div class="metrics-grid">
      ${metricCard('Audited statement facts', numberFmt.format(all.length), `${meta.source_count || years.length} source statements`, 'accent')}
      ${metricCard('Source fiscal-year ends', numberFmt.format(years.length), years.join(' · ') || '—', 'neutral')}
      ${metricCard('Statement families', numberFmt.format(families.length), families.map(humanize).join(' · '), 'neutral')}
      ${metricCard('Latest extracted source year', latestYear || '—', 'Each row also retains the source-presented prior-year comparator', 'neutral')}
    </div>
    <div class="split-grid wide-left">
      ${panel('Audited statement explorer', 'Filter audited line items and compare the source-presented current/prior-year values.', `<div class="local-toolbar build006-toolbar"><label class="local-search"><span>⌕</span><input id="financial-search" value="${escapeHtml(state.financialQuery)}" placeholder="Search statement or line item" /></label><select id="financial-year"><option value="all">All source fiscal years</option>${years.map(year => `<option value="${escapeHtml(year)}" ${String(year) === state.financialYear ? 'selected' : ''}>${escapeHtml(year)}</option>`).join('')}</select><select id="financial-family"><option value="all">All statement families</option>${families.map(family => `<option value="${escapeHtml(family)}" ${family === state.financialFamily ? 'selected' : ''}>${escapeHtml(humanize(family))}</option>`).join('')}</select>${visibleLimitNote(rows.length, visible.length, 'statement rows')}</div><div class="table-wrap"><table><thead><tr><th>FY end</th><th>Family</th><th>Statement</th><th>Line item</th><th class="numeric">Current year</th><th class="numeric">Prior year</th><th class="numeric">Movement</th></tr></thead><tbody>${visible.map(row => {
        const index = all.indexOf(row); const delta = numberValue(row.current_year) != null && numberValue(row.prior_year) != null ? Number(row.current_year) - Number(row.prior_year) : null;
        return `<tr data-financial-index="${index}"><td>${escapeHtml(row.fiscal_year_end || '—')}</td><td>${badge(humanize(row.statement_family), 'info')}</td><td>${escapeHtml(row.statement || '—')}</td><td><strong>${escapeHtml(row.line_item || '—')}</strong><small class="cell-sub">${escapeHtml(row.source_id || '')} · p${escapeHtml(row.source_page || '—')}</small></td><td class="numeric">${money(row.current_year)}</td><td class="numeric">${money(row.prior_year)}</td><td class="numeric">${delta == null ? '—' : `${delta >= 0 ? '+' : ''}${compactMoney(delta)}`}</td></tr>`;
      }).join('')}</tbody></table></div>`)}
      ${panel('Largest comparative source-row movements', 'Absolute current-versus-prior movement among the active filtered rows. Totals and detail rows may coexist, so these are review prompts—not additive amounts.', movements.length ? `<div class="rule-list">${movements.map(row => {
        const delta = Number(row.current_year) - Number(row.prior_year);
        return `<div><strong>${escapeHtml(row.line_item || row.statement)} · ${delta >= 0 ? '+' : ''}${compactMoney(delta)}</strong><span>${escapeHtml(row.statement || '')} · source FY ${escapeHtml(row.fiscal_year_end || '')}</span></div>`;
      }).join('')}</div>` : emptyState('No comparative rows', 'Change the statement filters.'))}
    </div>
  </div>`;
}

function councilYear(row) { const match = String(row.start_date || row.meeting_start_date || '').match(/^(\d{4})/); return match ? match[1] : ''; }
function councilFinanceDocsByMeeting() {
  const map = new Map();
  build006Rows('councilDocuments').filter(row => row.finance_relevant).forEach(row => {
    if (!map.has(row.meeting_id)) map.set(row.meeting_id, []);
    map.get(row.meeting_id).push(row);
  });
  return map;
}
function filteredCouncilMeetings() {
  const meetings = getRows(datasetStatus('council').data); const financeMap = councilFinanceDocsByMeeting();
  return meetings.filter(row =>
    (state.councilYear === 'all' || councilYear(row) === state.councilYear) &&
    (state.councilType === 'all' || row.meeting_type === state.councilType) &&
    (!state.councilFinanceOnly || (financeMap.get(String(row.meeting_id)) || []).length > 0) &&
    (!state.councilQuery || normalize(`${row.meeting_name} ${row.meeting_type} ${(financeMap.get(String(row.meeting_id)) || []).map(doc => `${doc.title} ${(doc.finance_tags || []).join(' ')}`).join(' ')}`).includes(normalize(state.councilQuery)))
  );
}
function renderCouncilBuild006() {
  const councilDs = datasetStatus('council'); const docsDs = build006Dataset('councilDocuments');
  if (councilDs.status !== 'ready' || docsDs.status !== 'ready') return `<div class="page-stack">${evidenceNotice()}${councilDs.status !== 'ready' ? emptyState('Council calendar unavailable', 'council.json is not ready.') : ''}${docsDs.status !== 'ready' ? build006LoadingPanel('Council document graph', 'councilDocuments') : ''}</div>`;
  const all = getRows(councilDs.data); const rows = filteredCouncilMeetings(); const docs = build006Rows('councilDocuments'); const financeDocs = docs.filter(row => row.finance_relevant); const meta = councilDs.data?.metadata || {}; const docMeta = docsDs.data?.metadata || {};
  const years = uniqueSorted(all.map(councilYear), (a, b) => Number(b) - Number(a)); const types = uniqueSorted(all.map(row => row.meeting_type)); const financeMap = councilFinanceDocsByMeeting();
  const tagCounts = new Map(); financeDocs.forEach(doc => (doc.finance_tags || []).forEach(tag => tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1)));
  const visibleMeetings = [...rows].sort((a, b) => String(b.start_date || '').localeCompare(String(a.start_date || ''))).slice(0, 160);
  const filteredFinanceDocs = financeDocs.filter(doc =>
    (state.councilYear === 'all' || councilYear(doc) === state.councilYear) &&
    (state.councilType === 'all' || doc.meeting_type === state.councilType) &&
    (!state.councilQuery || normalize(`${doc.title} ${(doc.finance_tags || []).join(' ')} ${doc.meeting_name}`).includes(normalize(state.councilQuery)))
  ).sort((a, b) => String(b.meeting_start_date || '').localeCompare(String(a.meeting_start_date || ''))).slice(0, 180);

  return `<div class="page-stack">
    <div class="notice"><strong>Decision-evidence boundary</strong><span>Meeting, agenda and attachment presence are calendar/document facts. Finance tags are title-keyword search aids. Neither proves that a recommendation was approved, that money was spent, or that a policy breach occurred.</span></div>
    <div class="metrics-grid">
      ${metricCard('Council / budget meetings', numberFmt.format(all.length), `Endpoint available from ${escapeHtml(meta.available_from_year || '2024')}`, 'accent')}
      ${metricCard('Meetings with minutes', numberFmt.format(meta.with_minutes || 0), `${numberFmt.format(meta.with_agenda || 0)} with agenda evidence`, 'neutral')}
      ${metricCard('Agenda document edges', numberFmt.format(docMeta.document_edges || docs.length), `${numberFmt.format(docMeta.unique_documents || docs.length)} unique documents`, 'neutral')}
      ${metricCard('Finance-tagged documents', numberFmt.format(financeDocs.length), `${tagCounts.size} finance tag categories`, financeDocs.length ? 'good' : 'neutral')}
    </div>
    ${panel('Meeting & finance-document explorer', 'Default view keeps meetings with at least one finance-tagged attachment. Search reaches meeting names, attachment titles and finance tags.', `<div class="local-toolbar build006-toolbar"><label class="local-search"><span>⌕</span><input id="council-search" value="${escapeHtml(state.councilQuery)}" placeholder="Search Council finance topics or document titles" /></label><select id="council-year"><option value="all">All available Council years</option>${years.map(year => `<option value="${escapeHtml(year)}" ${year === state.councilYear ? 'selected' : ''}>${escapeHtml(year)}</option>`).join('')}</select><select id="council-type"><option value="all">All meeting types</option>${types.map(type => `<option value="${escapeHtml(type)}" ${type === state.councilType ? 'selected' : ''}>${escapeHtml(type)}</option>`).join('')}</select><label class="build006-check"><input id="council-finance-only" type="checkbox" ${state.councilFinanceOnly ? 'checked' : ''}/><span>Finance-tagged meetings only</span></label>${visibleLimitNote(rows.length, visibleMeetings.length, 'meetings')}</div><div class="table-wrap"><table><thead><tr><th>Date</th><th>Meeting</th><th>Type</th><th>Agenda</th><th>Minutes</th><th class="numeric">Finance docs</th></tr></thead><tbody>${visibleMeetings.map(row => `<tr data-council-id="${escapeHtml(row.meeting_id)}"><td>${escapeHtml(dateOnly(row.start_date))}</td><td><strong>${escapeHtml(row.meeting_name || '—')}</strong></td><td>${escapeHtml(row.meeting_type || '—')}</td><td>${row.agenda_html_url || row.agenda_pdf_url ? badge('Available', 'good') : badge('Missing', 'muted')}</td><td>${row.minutes_html_url || row.minutes_pdf_url ? badge('Available', 'good') : badge('Not posted', 'muted')}</td><td class="numeric"><strong>${numberFmt.format((financeMap.get(String(row.meeting_id)) || []).length)}</strong></td></tr>`).join('')}</tbody></table></div>`)}
    <div class="split-grid wide-left">
      ${panel('Finance-tagged agenda attachments', 'Open the official attachment; tags only describe title-keyword matches.', filteredFinanceDocs.length ? `<div class="source-mini-list">${filteredFinanceDocs.map(doc => `<a class="build006-doc-link" href="${escapeHtml(safeUrl(doc.url) || '#')}" target="_blank" rel="noreferrer"><span><strong>${escapeHtml(doc.title)}</strong><small>${escapeHtml(dateOnly(doc.meeting_start_date))} · ${escapeHtml(doc.meeting_type || '')} · ${(doc.finance_tags || []).map(tag => humanize(tag)).join(' · ')}</small></span><span>↗</span></a>`).join('')}</div>` : emptyState('No finance-tagged attachments under these filters', 'Widen the year/type/search filters.'))}
      ${panel('Finance tag coverage', 'Useful discovery categories in the current document graph.', `<div class="rule-list">${[...tagCounts.entries()].sort((a, b) => b[1] - a[1]).map(([tag, count]) => `<div><strong>${escapeHtml(humanize(tag))}</strong><span>${numberFmt.format(count)} tagged attachment${count === 1 ? '' : 's'}</span></div>`).join('')}</div>`)}
    </div>
  </div>`;
}

const RAW_ID_KEYS = new Set(['year', 'municipality', 'municipality_name', 'municipal_unit', 'region', 'region_name', 'region_type', 'entity', 'area_name', 'community', 'name', 'funding_program', 'area']);
function rawYear(raw) { return raw?.year || raw?.fiscal_year || raw?.fiscal_year_end || '—'; }
function rawIdentity(raw) { return raw?.municipality_name || raw?.municipality || raw?.municipal_unit || raw?.region_name || raw?.region || raw?.entity || raw?.funding_program || raw?.region_type || raw?.area_name || raw?.community || raw?.name || raw?.area || '—'; }
function rawMetricPreview(raw, max = 4) {
  if (!raw || typeof raw !== 'object') return '—';
  const entries = Object.entries(raw).filter(([key, value]) => !RAW_ID_KEYS.has(key) && value !== '' && value !== null && value !== undefined).slice(0, max);
  return entries.map(([key, value]) => `${humanize(key)}: ${escapeHtml(formatRawValue(value))}`).join(' · ') || '—';
}
function formatRawValue(value) {
  const n = Number(String(value).replaceAll(',', ''));
  if (Number.isFinite(n) && String(value).trim() !== '') return numberFmt.format(n);
  return String(value ?? '—');
}
function benchmarkCombinedRows() {
  const benchmark = build006Rows('benchmarks').map((row, index) => ({ origin: 'benchmarks', index, ...row }));
  const funding = build006Rows('externalFunding').map((row, index) => ({ origin: 'externalFunding', index, ...row }));
  return [...benchmark, ...funding];
}
function filteredBenchmarkRows() {
  return benchmarkCombinedRows().filter(row => {
    const isHrm = row.scope === 'hrm';
    const scopeMatch = state.benchmarkScope === 'all' || (state.benchmarkScope === 'hrm' ? isHrm : !isHrm);
    return scopeMatch && (state.benchmarkDataset === 'all' || row.dataset_type === state.benchmarkDataset) && (!state.benchmarkQuery || normalize(`${row.dataset_type} ${row.scope} ${JSON.stringify(row.raw || {})}`).includes(normalize(state.benchmarkQuery)));
  });
}
function renderBenchmarksBuild006() {
  const benchmarksDs = build006Dataset('benchmarks'); const fundingDs = build006Dataset('externalFunding');
  if (benchmarksDs.status !== 'ready' || fundingDs.status !== 'ready') return `<div class="page-stack">${evidenceNotice()}${benchmarksDs.status !== 'ready' ? build006LoadingPanel('Municipal benchmarks', 'benchmarks') : ''}${fundingDs.status !== 'ready' ? build006LoadingPanel('External funding', 'externalFunding') : ''}</div>`;
  const all = benchmarkCombinedRows(); const rows = filteredBenchmarkRows(); const bMeta = build006Meta('benchmarks'); const fMeta = build006Meta('externalFunding'); const types = uniqueSorted(all.map(row => row.dataset_type));
  const visible = rows.slice(0, 260);

  return `<div class="page-stack">
    <div class="notice"><strong>Scope boundary</strong><span>Only rows explicitly marked <b>scope=hrm</b> are Halifax recipient/entity facts. Regional-type comparator aggregates and province-program funding totals are context only and must never be described as Halifax expenses, revenues or funding received.</span></div>
    <div class="metrics-grid">
      ${metricCard('HRM benchmark facts', numberFmt.format(bMeta.hrm_records || 0), `${numberFmt.format(bMeta.comparator_records || 0)} comparator rows kept separate`, 'accent')}
      ${metricCard('HRM funding facts', numberFmt.format(fMeta.hrm_records || 0), 'Explicit Halifax recipient/entity scope only', 'good')}
      ${metricCard('Province program context', numberFmt.format(fMeta.context_records || 0), 'Never attributed to Halifax', 'neutral')}
      ${metricCard('Dataset families', numberFmt.format(types.length), 'Operating, consolidated, financial-condition, assessment and funding context', 'neutral')}
    </div>
    ${panel('Municipal benchmark & funding explorer', 'Inspect raw official fields while preserving HRM versus context scope.', `<div class="local-toolbar build006-toolbar"><label class="local-search"><span>⌕</span><input id="benchmark-search" value="${escapeHtml(state.benchmarkQuery)}" placeholder="Search dataset, year, municipality or program" /></label><select id="benchmark-scope"><option value="hrm" ${state.benchmarkScope === 'hrm' ? 'selected' : ''}>HRM-specific facts</option><option value="context" ${state.benchmarkScope === 'context' ? 'selected' : ''}>Comparator / province context</option><option value="all" ${state.benchmarkScope === 'all' ? 'selected' : ''}>All with scope labels</option></select><select id="benchmark-dataset"><option value="all">All dataset families</option>${types.map(type => `<option value="${escapeHtml(type)}" ${type === state.benchmarkDataset ? 'selected' : ''}>${escapeHtml(humanize(type))}</option>`).join('')}</select>${visibleLimitNote(rows.length, visible.length)}</div><div class="table-wrap"><table><thead><tr><th>Year</th><th>Dataset</th><th>Scope</th><th>Entity / comparator / program</th><th>Published fields</th><th>Source</th></tr></thead><tbody>${visible.map(row => `<tr data-benchmark-origin="${escapeHtml(row.origin)}" data-benchmark-index="${row.index}"><td>${escapeHtml(rawYear(row.raw))}</td><td><strong>${escapeHtml(humanize(row.dataset_type))}</strong></td><td>${badge(row.scope === 'hrm' ? 'HRM fact' : 'Context only', row.scope === 'hrm' ? 'good' : 'info')}</td><td>${escapeHtml(rawIdentity(row.raw))}</td><td>${rawMetricPreview(row.raw)}</td><td>${escapeHtml(row.source_id || '—')}</td></tr>`).join('')}</tbody></table></div>`)}
    <div class="split-grid">${panel('What this enables', 'Useful external context without inventing equivalence.', `<div class="rule-list"><div><strong>HRM financial-condition context</strong><span>Inspect source-published HRM indicators and consolidated municipal rows over the years provided.</span></div><div><strong>Municipality-type context</strong><span>Compare broad operating categories to regional-type aggregates only as contextual benchmarks.</span></div><div><strong>Assessment context</strong><span>Track official uniform-assessment records where Halifax is explicitly identified.</span></div><div><strong>Funding discovery</strong><span>Distinguish explicit HRM capacity-grant rows from province-wide program totals.</span></div></div>`)}${panel('Critical interpretation rules', 'These constraints prevent false municipal claims.', `<div class="rule-list"><div><strong>Context ≠ Halifax</strong><span>Province-program totals are not funding received by HRM.</span></div><div><strong>Aggregate ≠ peer municipality</strong><span>Regional-type expense/revenue rows are type aggregates, not individual peer-municipality facts.</span></div><div><strong>No synthetic normalization</strong><span>Raw official fields stay visible until a defensible metric definition and unit reconciliation are implemented.</span></div></div>`)}</div>
  </div>`;
}

function showBudgetHistoryRow(index) {
  const row = build006Rows('budgetHistory')[Number(index)]; if (!row) return;
  const source = sourceById(row.source_id); const provenance = row.provenance || {};
  openDrawer({ title: row.service_area || 'Historical budget row', eyebrow: 'HISTORICAL BUDGET EVIDENCE', html: `${evidenceSteps([['Fiscal year', row.fiscal_year], ['Source state', row.source_status], ['Final source?', row.source_is_final ? 'Yes' : 'No'], ['Business unit', row.business_unit], ['Service area', row.service_area], ['Prior actual', money(row.prior_actual)], ['Prior budget', money(row.prior_budget)], ['Projection', money(row.projection)], ['Current budget', money(row.current_budget)], ['Source locator', provenance.locator_value || `p${row.source_page}/t${row.source_table}/r${row.source_row}`], ['Source ID', row.source_id]])}<div class="drawer-callout"><strong>Historical identity boundary</strong><p>This historical label is not automatically mapped to a current business unit. Proposed/pre-COVID records remain in their source state.</p></div>${source ? sourceLink(source) : ''}` });
}
function showSpendingRow(index) {
  const row = getRows(datasetStatus('spending').data)[Number(index)]; if (!row) return;
  const source = sourceById(row.source_id); const values = Array.isArray(row.values) ? row.values.map(money).join(' · ') : '—';
  openDrawer({ title: spendingLabel(row), eyebrow: 'QUARTERLY SPENDING-SUMMARY EVIDENCE', html: `${evidenceSteps([['Period end', row.posting_date], ['Fiscal year', row.fiscal_year], ['Record type', humanize(row.record_type)], ['Context', row.category || row.account], ['Selected amount', money(row.amount)], ['Amount semantics', row.amount_semantics], ['All tokenized monetary values', values], ['Raw source row', (row.raw_cells || []).join(' | ')], ['Source page / table / row', `${row.source_page} / ${row.source_table} / ${row.source_row}`], ['Source ID', row.source_id]])}<div class="drawer-callout"><strong>Not a transaction</strong><p>This row is an official quarterly summary-table row. It does not identify an invoice, payment or vendor.</p></div>${source ? sourceLink(source) : ''}` });
}
function showFinancialRow(index) {
  const row = getRows(datasetStatus('financials').data)[Number(index)]; if (!row) return;
  const source = sourceById(row.source_id); const delta = numberValue(row.current_year) != null && numberValue(row.prior_year) != null ? Number(row.current_year) - Number(row.prior_year) : null;
  openDrawer({ title: row.line_item || row.statement, eyebrow: 'AUDITED FINANCIAL EVIDENCE', html: `${evidenceSteps([['Fiscal year end', row.fiscal_year_end], ['Statement family', humanize(row.statement_family)], ['Statement', row.statement], ['Line item', row.line_item], ['Current year', money(row.current_year)], ['Prior year', money(row.prior_year)], ['Comparative movement', delta == null ? '—' : `${delta >= 0 ? '+' : ''}${money(delta)}`], ['Source unit multiplier', row.source_unit_multiplier], ['Source page', row.source_page], ['Extraction method', row.extraction_method], ['Source ID', row.source_id]])}<div class="drawer-callout"><strong>Accounting-basis boundary</strong><p>This audited PSAS statement line is not automatically assigned to an operational department or budget-book service area.</p></div>${source ? sourceLink(source) : ''}` });
}
function showCouncilMeeting(meetingId) {
  const meeting = getRows(datasetStatus('council').data).find(row => String(row.meeting_id) === String(meetingId)); if (!meeting) return;
  const docs = (councilFinanceDocsByMeeting().get(String(meetingId)) || []).sort((a, b) => String(a.title || '').localeCompare(String(b.title || '')));
  const docHtml = docs.length ? `<div class="drawer-section"><h3>Finance-tagged attachments</h3><div class="drawer-source-list">${docs.slice(0, 40).map(doc => `<a class="source-link" href="${escapeHtml(safeUrl(doc.url) || '#')}" target="_blank" rel="noreferrer">${escapeHtml(doc.title)} ↗</a>`).join('')}</div></div>` : '<div class="drawer-section"><p>No finance-tagged attachment titles were found for this meeting.</p></div>';
  const links = [meeting.agenda_html_url || meeting.agenda_pdf_url, meeting.minutes_html_url || meeting.minutes_pdf_url].filter(Boolean).map((url, index) => `<a class="source-link" href="${escapeHtml(safeUrl(url) || '#')}" target="_blank" rel="noreferrer">Open official ${index === 0 ? 'agenda' : 'minutes'} ↗</a>`).join('');
  openDrawer({ title: meeting.meeting_name || 'Council meeting', eyebrow: 'COUNCIL DOCUMENT EVIDENCE', html: `${evidenceSteps([['Date', meeting.start_date], ['Meeting type', meeting.meeting_type], ['Location', meeting.location], ['Finance-tagged attachments', docs.length], ['Meeting ID', meeting.meeting_id]])}<div class="drawer-callout"><strong>Not an approval finding</strong><p>Agenda/document presence and title tags do not establish that a recommendation was approved or a payment occurred.</p></div>${docHtml}${links}` });
}
function showBenchmarkRecord(origin, index) {
  const sourceRows = origin === 'benchmarks' ? build006Rows('benchmarks') : build006Rows('externalFunding'); const row = sourceRows[Number(index)]; if (!row) return;
  const raw = row.raw || {}; const source = sourceById(row.source_id);
  const rawHtml = `<div class="drawer-section"><h3>Published source fields</h3><div class="rule-list">${Object.entries(raw).map(([key, value]) => `<div><strong>${escapeHtml(humanize(key))}</strong><span>${escapeHtml(formatRawValue(value))}</span></div>`).join('')}</div></div>`;
  openDrawer({ title: rawIdentity(raw), eyebrow: row.scope === 'hrm' ? 'HRM MUNICIPAL CONTEXT' : 'CONTEXT-ONLY EVIDENCE', html: `${evidenceSteps([['Dataset', humanize(row.dataset_type)], ['Scope', row.scope === 'hrm' ? 'Explicit HRM fact' : 'Comparator / province context only'], ['Year', rawYear(raw)], ['Source ID', row.source_id], ['Source row index', row.source_row_index]])}${row.scope !== 'hrm' ? '<div class="drawer-callout"><strong>Do not attribute to Halifax</strong><p>This row is external context and is intentionally not joined to HRM in the normalized entity index.</p></div>' : ''}${rawHtml}${source ? sourceLink(source) : ''}` });
}

function rerenderSearch(id, stateKey, event) {
  state[stateKey] = event.target.value; render();
  requestAnimationFrame(() => { const input = document.getElementById(id); if (input) { input.focus(); if (typeof input.setSelectionRange === 'function') input.setSelectionRange(input.value.length, input.value.length); } });
}
function bindBuild006Events() {
  const listeners = [
    ['budget-history-search', 'input', event => rerenderSearch('budget-history-search', 'budgetHistoryQuery', event)],
    ['budget-history-year', 'change', event => { state.budgetHistoryYear = event.target.value; render(); }],
    ['spending-search', 'input', event => rerenderSearch('spending-search', 'spendingQuery', event)],
    ['spending-year', 'change', event => { state.spendingYear = event.target.value; render(); }],
    ['spending-type', 'change', event => { state.spendingType = event.target.value; render(); }],
    ['vendor-search', 'input', event => rerenderSearch('vendor-search', 'vendorQuery', event)],
    ['vendor-entity', 'change', event => { state.vendorEntity = event.target.value; render(); }],
    ['capital-search', 'input', event => rerenderSearch('capital-search', 'capitalQuery', event)],
    ['capital-year', 'change', event => { state.capitalYear = event.target.value; render(); }],
    ['capital-category', 'change', event => { state.capitalCategory = event.target.value; render(); }],
    ['financial-search', 'input', event => rerenderSearch('financial-search', 'financialQuery', event)],
    ['financial-year', 'change', event => { state.financialYear = event.target.value; render(); }],
    ['financial-family', 'change', event => { state.financialFamily = event.target.value; render(); }],
    ['council-search', 'input', event => rerenderSearch('council-search', 'councilQuery', event)],
    ['council-year', 'change', event => { state.councilYear = event.target.value; render(); }],
    ['council-type', 'change', event => { state.councilType = event.target.value; render(); }],
    ['council-finance-only', 'change', event => { state.councilFinanceOnly = event.target.checked; render(); }],
    ['benchmark-search', 'input', event => rerenderSearch('benchmark-search', 'benchmarkQuery', event)],
    ['benchmark-scope', 'change', event => { state.benchmarkScope = event.target.value; render(); }],
    ['benchmark-dataset', 'change', event => { state.benchmarkDataset = event.target.value; render(); }]
  ];
  listeners.forEach(([id, type, handler]) => { const element = document.getElementById(id); if (element) element.addEventListener(type, handler); });
  document.querySelectorAll('[data-budget-history-index]').forEach(row => row.addEventListener('click', () => showBudgetHistoryRow(row.dataset.budgetHistoryIndex)));
  document.querySelectorAll('[data-spending-index]').forEach(row => row.addEventListener('click', () => showSpendingRow(row.dataset.spendingIndex)));
  document.querySelectorAll('[data-financial-index]').forEach(row => row.addEventListener('click', () => showFinancialRow(row.dataset.financialIndex)));
  document.querySelectorAll('[data-council-id]').forEach(row => row.addEventListener('click', () => showCouncilMeeting(row.dataset.councilId)));
  document.querySelectorAll('[data-benchmark-origin]').forEach(row => row.addEventListener('click', () => showBenchmarkRecord(row.dataset.benchmarkOrigin, row.dataset.benchmarkIndex)));
}

function renderBuild006Route(route, html) {
  const meta = NAV.find(item => item[0] === route) || [route, humanize(route), '', 'HALIFAX REGIONAL MUNICIPALITY'];
  $('#view-title').textContent = meta[1];
  $('#view-eyebrow').textContent = meta[3];
  $$('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.view === route));
  $('#content').innerHTML = html;
  const filterbar = $('.filterbar'); if (filterbar) filterbar.hidden = true;
  const entityFilter = $('#global-entity-wrap'); if (entityFilter) entityFilter.hidden = true;
  bindViewEvents();
  bindBuild006Events();
}

const build005Render = render;
render = function renderBuild006() {
  if (state.view === 'financials') return renderBuild006Route('financials', renderFinancialsBuild006());
  if (state.view === 'council') return renderBuild006Route('council', renderCouncilBuild006());
  if (state.view === 'benchmarks') return renderBuild006Route('benchmarks', renderBenchmarksBuild006());
  build005Render();
  if (state.view === 'overview') injectBuild006Overview();
  if (state.view === 'budget') injectBudgetHistoryPanel();
  bindBuild006Events();
};
