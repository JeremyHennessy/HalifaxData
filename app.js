const NAV = [
  ['overview', 'Command Center', '◈', 'PUBLIC MONEY'],
  ['budget', 'Budget & Actuals', '▤', 'FINANCIAL PLAN'],
  ['spending', 'Spend Explorer', '↳', 'MONEY FLOW'],
  ['vendors', 'Vendors & Contracts', '◇', 'PROCUREMENT'],
  ['people', 'People & Compensation', '◎', 'WORKFORCE'],
  ['projects', 'Capital Projects', '▱', 'CAPITAL'],
  ['signals', 'Signals Lab', '⚑', 'REVIEW QUEUE'],
  ['sources', 'Sources & Evidence', '⌗', 'PROVENANCE']
];

const OPTIONAL_FILES = {
  budget: './data/generated/budget.json',
  spending: './data/generated/spending.json',
  procurement: './data/generated/procurement.json',
  capital: './data/generated/capital.json',
  financials: './data/generated/financials.json',
  council: './data/generated/council.json',
  signals: './data/generated/signals.json'
};

const DOMAIN_META = {
  budget: { label: 'Budget & actuals', categories: ['Budgets & actuals'], sourceHint: 'Budget books, quarterly reporting and audited financial statements' },
  spending: { label: 'Spending detail', categories: ['Budgets & actuals', 'Council decisions'], sourceHint: 'Most-granular official expenditure records available' },
  procurement: { label: 'Procurement', categories: ['Procurement', 'Council decisions'], sourceHint: 'Tender notices, awards, amendments and Council/CAO reports' },
  capital: { label: 'Capital projects', categories: ['Capital', 'Council decisions'], sourceHint: 'Capital plan, mapped project records and approvals' },
  financials: { label: 'Audited financials', categories: ['Budgets & actuals'], sourceHint: 'Consolidated annual financial statements' },
  council: { label: 'Council decisions', categories: ['Council decisions'], sourceHint: 'Agendas, reports, minutes and decisions' }
};

const state = {
  view: validView(location.hash.slice(1)) || 'overview',
  compensation: null,
  sources: null,
  optional: {},
  year: 'all',
  unit: 'all',
  peopleQuery: '',
  sourceQuery: '',
  sourceCategory: 'all'
};

const moneyFmt = new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 });
const numberFmt = new Intl.NumberFormat('en-CA');
const decimalFmt = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 1 });

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

function validView(view) { return NAV.some(item => item[0] === view) ? view : null; }
function escapeHtml(value = '') { return String(value).replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char])); }
function money(value) { return value == null || Number.isNaN(Number(value)) ? '—' : moneyFmt.format(Number(value)); }
function compactMoney(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const n = Number(value); const a = Math.abs(n); const sign = n < 0 ? '-' : '';
  if (a >= 1e9) return `${sign}$${decimalFmt.format(a / 1e9)}B`;
  if (a >= 1e6) return `${sign}$${decimalFmt.format(a / 1e6)}M`;
  if (a >= 1e3) return `${sign}$${decimalFmt.format(a / 1e3)}K`;
  return money(n);
}
function pct(value, fraction = false) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const n = Number(value) * (fraction ? 100 : 1);
  return `${n >= 0 ? '+' : ''}${decimalFmt.format(n)}%`;
}
function normalize(value) { return String(value ?? '').trim().toLowerCase(); }
function safeUrl(value) { try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : null; } catch { return null; } }
function getRows(payload) {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  for (const key of ['records', 'rows', 'facts', 'items', 'projects', 'awards', 'transactions', 'signals']) if (Array.isArray(payload[key])) return payload[key];
  return [];
}
function first(row, keys, fallback = null) { for (const key of keys) if (row?.[key] !== undefined && row?.[key] !== null) return row[key]; return fallback; }
function sourceById(id) { return state.sources?.sources?.find(source => source.id === id) || null; }
function sourcesForCategories(categories) { return (state.sources?.sources || []).filter(source => categories.includes(source.category)); }
function compensationRows() { return state.compensation?.records || []; }
function filteredCompensationRows() {
  return compensationRows().filter(row => (state.year === 'all' || String(row.fiscal_year_end) === state.year) && (state.unit === 'all' || row.business_unit === state.unit));
}

async function fetchRequired(url, label) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${label} failed to load (${response.status})`);
  return response.json();
}
async function fetchOptional(key, url) {
  try {
    const response = await fetch(url, { cache: 'no-store' });
    if (response.status === 404) return [key, { status: 'missing', data: null, url }];
    if (!response.ok) return [key, { status: 'error', data: null, url, error: `HTTP ${response.status}` }];
    return [key, { status: 'ready', data: await response.json(), url }];
  } catch (error) {
    return [key, { status: 'error', data: null, url, error: error.message }];
  }
}

Promise.all([
  fetchRequired('./data/generated/compensation.json', 'Compensation data'),
  fetchRequired('./data/sources.json', 'Source registry'),
  Promise.all(Object.entries(OPTIONAL_FILES).map(([key, url]) => fetchOptional(key, url)))
]).then(([compensation, sources, optional]) => {
  state.compensation = compensation;
  state.sources = sources;
  state.optional = Object.fromEntries(optional);
  initializeChrome();
  render();
}).catch(error => {
  $('#content').innerHTML = `<div class="error-state"><strong>HalifaxData could not start</strong><p>${escapeHtml(error.message)}</p><p>The dashboard refuses to substitute invented or stale values when required checked-in data is unavailable.</p></div>`;
});

function initializeChrome() {
  $('#nav').innerHTML = NAV.map(([id, label, icon]) => `<a class="nav-item" href="#${id}" data-view="${id}"><span class="nav-icon">${icon}</span><span>${label}</span></a>`).join('');
  const years = [...new Set(compensationRows().map(row => Number(row.fiscal_year_end)).filter(Number.isFinite))].sort((a, b) => b - a);
  const units = [...new Set(compensationRows().map(row => row.business_unit).filter(Boolean))].sort((a, b) => a.localeCompare(b));
  $('#global-year').innerHTML = `<option value="all">All available years</option>${years.map(year => `<option value="${year}">${year}</option>`).join('')}`;
  $('#global-unit').innerHTML = `<option value="all">All business units</option>${units.map(unit => `<option value="${escapeHtml(unit)}">${escapeHtml(unit)}</option>`).join('')}`;
  $('#global-year').addEventListener('change', event => { state.year = event.target.value; render(); });
  $('#global-unit').addEventListener('change', event => { state.unit = event.target.value; render(); });
  $('#reset-filters').addEventListener('click', () => {
    state.year = 'all'; state.unit = 'all';
    $('#global-year').value = 'all'; $('#global-unit').value = 'all';
    render();
  });
  $('#global-search').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); runGlobalSearch(event.currentTarget.value); } });
  $('#evidence-standard').addEventListener('click', showEvidenceStandard);
  $('#drawer-close').addEventListener('click', () => $('#evidence-drawer').close());
  $('#menu-button').addEventListener('click', () => $('#sidebar').classList.toggle('open'));
  window.addEventListener('hashchange', () => { state.view = validView(location.hash.slice(1)) || 'overview'; $('#sidebar').classList.remove('open'); render(); });
  $('#snapshot-label').textContent = `Sources researched ${state.sources.metadata?.last_researched || 'date unknown'}`;
  $('#data-mode').textContent = state.compensation.metadata?.dataset_status === 'partial_verified_seed' ? 'Partial verified data' : 'Generated data';
}

function render() {
  const meta = NAV.find(item => item[0] === state.view) || NAV[0];
  $('#view-title').textContent = meta[1];
  $('#view-eyebrow').textContent = meta[3];
  $$('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.view === state.view));
  const views = { overview: renderOverview, budget: renderBudget, spending: renderSpending, vendors: renderVendors, people: renderPeople, projects: renderProjects, signals: renderSignals, sources: renderSources };
  $('#content').innerHTML = views[state.view]();
  bindViewEvents();
}

function metricCard(label, value, detail, tone = '') {
  return `<article class="metric-card ${tone}"><div class="metric-label">${escapeHtml(label)}</div><div class="metric-value">${value}</div><div class="metric-detail">${detail}</div></article>`;
}
function panel(title, subtitle, body, extraClass = '') {
  return `<section class="panel ${extraClass}"><header class="panel-header"><div><h2>${title}</h2>${subtitle ? `<p>${subtitle}</p>` : ''}</div></header><div class="panel-body">${body}</div></section>`;
}
function badge(text, tone = '') { return `<span class="badge ${tone}">${escapeHtml(text)}</span>`; }
function emptyState(title, text, action = '') { return `<div class="empty-state"><div class="empty-icon">⌁</div><strong>${title}</strong><p>${text}</p>${action}</div>`; }
function evidenceNotice() {
  return `<div class="notice"><strong>Interpretation boundary</strong><span>Checked-in records may be partial. A review signal is a reproducible prompt for investigation, not a finding of waste, wrongdoing, illegality or policy breach.</span></div>`;
}

function datasetStatus(key) { return state.optional[key] || { status: 'missing', data: null, url: OPTIONAL_FILES[key] }; }
function sourceStatusTone(status) { return status === 'ready' ? 'good' : status === 'ready-historical' ? 'info' : status === 'research' ? 'warn' : status === 'error' ? 'bad' : 'muted'; }
function generatedStatus(key) {
  const ds = datasetStatus(key);
  if (ds.status === 'ready') return { text: `${numberFmt.format(getRows(ds.data).length)} generated rows`, tone: 'good' };
  if (ds.status === 'error') return { text: 'Generated artifact error', tone: 'bad' };
  return { text: 'Awaiting generated artifact', tone: 'warn' };
}
function domainCoverageCard(key) {
  const meta = DOMAIN_META[key]; const sources = sourcesForCategories(meta.categories); const generated = generatedStatus(key);
  return `<button type="button" class="coverage-card" data-domain="${key}"><div class="coverage-top"><span>${escapeHtml(meta.label)}</span>${badge(generated.text, generated.tone)}</div><strong>${sources.length}</strong><p>registered source${sources.length === 1 ? '' : 's'} · ${escapeHtml(meta.sourceHint)}</p></button>`;
}

function renderOverview() {
  const sources = state.sources.sources || [];
  const compensation = filteredCompensationRows();
  const years = [...new Set(compensationRows().map(row => row.fiscal_year_end))];
  const readyGenerated = Object.entries(state.optional).filter(([key, value]) => key !== 'signals' && value.status === 'ready').length;
  const signals = computeCompSignals(compensation).slice(0, 6);
  const categories = [...new Set(sources.map(source => source.category))];
  return `<div class="page-stack">
    ${evidenceNotice()}
    <div class="metrics-grid">
      ${metricCard('Official sources mapped', numberFmt.format(sources.length), `${categories.length} evidence categories`, 'accent')}
      ${metricCard('Verified compensation rows', numberFmt.format(compensation.length), filterDetail('current seed rows'), 'neutral')}
      ${metricCard('Compensation history', years.length ? `${Math.min(...years)}–${Math.max(...years)}` : '—', '$100k+ disclosure history in checked-in seed', 'neutral')}
      ${metricCard('Additional generated domains', `${readyGenerated}/6`, 'Budget, spending, procurement, capital, financials, Council', readyGenerated ? 'good' : 'warn')}
    </div>
    <div class="split-grid wide-left">
      ${panel('Data coverage', 'Source discovery and generated analytical tables are deliberately tracked separately.', `<div class="coverage-grid">${['budget', 'spending', 'procurement', 'capital', 'financials', 'council'].map(domainCoverageCard).join('')}</div>`)}
      ${panel('Review queue', 'Highest-priority signals available under the current global filters.', signals.length ? `<div class="signal-list">${signals.map(signalCard).join('')}</div>` : emptyState('No signals under these filters', 'Change the fiscal year or business-unit filter to widen the current verified seed.'))}
    </div>
    <div class="split-grid">
      ${panel('Public-money reconciliation graph', 'The long-term inspection path is a connected evidence graph, not a collection of unrelated charts.', reconciliationGraph())}
      ${panel('Data integrity controls', 'Rules the UI and collection pipeline should preserve as coverage expands.', `<div class="rule-list"><div><strong>Missing ≠ zero</strong><span>Absent disclosure or uncollected rows never become numeric zero.</span></div><div><strong>Raw labels retained</strong><span>Historical business-unit and vendor/person names stay traceable.</span></div><div><strong>Derived values reproducible</strong><span>Every metric points back to source IDs and transforms.</span></div><div><strong>Coverage visible</strong><span>Parser/source gaps appear in the product instead of disappearing.</span></div></div>`)}
    </div>
  </div>`;
}

function filterDetail(label) {
  const parts = [];
  if (state.year !== 'all') parts.push(`FY ${state.year}`);
  if (state.unit !== 'all') parts.push(state.unit);
  return parts.length ? `${label} · ${escapeHtml(parts.join(' · '))}` : label;
}
function reconciliationGraph() {
  const nodes = ['SOURCE', 'APPROVAL', 'BUDGET', 'PROCUREMENT', 'VENDOR', 'PROJECT', 'AMENDMENT', 'ACTUAL', 'AUDIT'];
  return `<div class="flow">${nodes.map((node, index) => `${index ? '<span class="flow-arrow">→</span>' : ''}<span class="flow-node">${node}</span>`).join('')}</div><div class="flow secondary"><span class="flow-node">PERSON DISCLOSURE</span><span class="flow-arrow">→</span><span class="flow-node">FISCAL YEAR</span><span class="flow-arrow">→</span><span class="flow-node">UNIT / POSITION</span><span class="flow-arrow">→</span><span class="flow-node">WAGES + BENEFITS</span><span class="flow-arrow">→</span><span class="flow-node">SOURCE</span></div>`;
}

function domainIntro(key, questions) {
  const meta = DOMAIN_META[key]; const ds = datasetStatus(key); const registered = sourcesForCategories(meta.categories); const status = generatedStatus(key);
  return `<div class="metrics-grid compact">
    ${metricCard('Generated data', status.text, `Expected at ${escapeHtml(OPTIONAL_FILES[key])}`, status.tone)}
    ${metricCard('Registered sources', numberFmt.format(registered.length), meta.sourceHint, registered.length ? 'good' : 'warn')}
    ${metricCard('Primary questions', numberFmt.format(questions.length), questions.join(' · '), 'neutral')}
    ${metricCard('Evidence requirement', '100%', 'Every row and signal must retain provenance', 'accent')}
  </div>${ds.status === 'error' ? `<div class="notice danger"><strong>Artifact error</strong><span>${escapeHtml(ds.error || 'Unknown error')}</span></div>` : ''}`;
}
function domainSources(key) {
  const meta = DOMAIN_META[key]; const sources = sourcesForCategories(meta.categories);
  if (!sources.length) return emptyState('No registered sources in this category', 'Source research must be completed before the dashboard can claim coverage.');
  return `<div class="source-mini-list">${sources.map(source => `<button type="button" data-source-id="${escapeHtml(source.id)}"><span><strong>${escapeHtml(source.name)}</strong><small>${escapeHtml(source.publisher)}</small></span>${badge(source.status, sourceStatusTone(source.status))}</button>`).join('')}</div>`;
}
function genericRowsTable(rows, columns) {
  if (!rows.length) return '';
  return `<div class="table-wrap"><table><thead><tr>${columns.map(col => `<th class="${col.numeric ? 'numeric' : ''}">${escapeHtml(col.label)}</th>`).join('')}</tr></thead><tbody>${rows.slice(0, 500).map((row, index) => `<tr data-generic-row="${index}">${columns.map(col => `<td class="${col.numeric ? 'numeric' : ''}">${col.format ? col.format(col.get(row)) : escapeHtml(col.get(row) ?? '—')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function renderBudget() {
  const ds = datasetStatus('budget'); const rows = getRows(ds.data);
  const questions = ['variance', 'growth', 'mix', 'forecast accuracy'];
  const table = ds.status === 'ready' ? genericRowsTable(rows, [
    { label: 'Fiscal year', get: r => first(r, ['fiscal_year', 'fiscal_year_end', 'year']) },
    { label: 'Business unit', get: r => first(r, ['business_unit', 'unit']) },
    { label: 'Service / category', get: r => first(r, ['service_area', 'category', 'account_name']) },
    { label: 'Actual', get: r => first(r, ['actual', 'prior_actual']), format: money, numeric: true },
    { label: 'Budget', get: r => first(r, ['current_budget', 'budget']), format: money, numeric: true },
    { label: 'Projection', get: r => first(r, ['projection', 'forecast']), format: money, numeric: true }
  ]) : '';
  return `<div class="page-stack">${evidenceNotice()}${domainIntro('budget', questions)}<div class="split-grid wide-left">${panel('Budget line explorer', 'Trace plan → projection → actual while preserving organizational history.', table || emptyState('Budget fact table awaits ingestion', 'The official budget and audited-financial sources are registered. When the collector publishes budget.json, this view activates without a frontend rewrite.'))}${panel('Budget source coverage', 'Registered documents relevant to this analysis.', domainSources('budget'))}</div>${panel('Analysis lenses', 'Initial reproducible tests for the normalized budget fact table.', lensGrid([['Variance bridge', 'Prior budget → projection → actual with both amount and percentage variance.'], ['Year-over-year growth', 'Compare like categories while respecting organizational reorganizations.'], ['Cost mix', 'Compensation, services, supplies, transfers, debt and other published categories.'], ['Forecast accuracy', 'Measure projection error only after audited/final actuals exist.'], ['FTE context', 'Connect funded positions where business plans publish FTEs.'], ['Reallocations', 'Link Council-approved changes rather than treating all movement as unexplained.']]))}</div>`;
}

function renderSpending() {
  const ds = datasetStatus('spending'); const rows = getRows(ds.data); const questions = ['where money went', 'timing', 'account drift', 'duplicate-like candidates'];
  const table = ds.status === 'ready' ? genericRowsTable(rows, [
    { label: 'Date', get: r => first(r, ['posting_date', 'date']) }, { label: 'Vendor', get: r => first(r, ['vendor_name', 'vendor']) }, { label: 'Business unit', get: r => first(r, ['business_unit', 'unit']) }, { label: 'Account', get: r => first(r, ['account', 'category']) }, { label: 'Project', get: r => first(r, ['project_name', 'project']) }, { label: 'Amount', get: r => first(r, ['amount', 'value']), format: money, numeric: true }
  ]) : '';
  return `<div class="page-stack">${evidenceNotice()}${domainIntro('spending', questions)}<div class="split-grid wide-left">${panel('Spend explorer', 'The UI descends only to the granularity supported by official records.', table || emptyState('Transaction-level facts are not checked in yet', 'This is intentionally shown as a source gap—not as $0 spending. The collector can publish spending.json using the documented contract.'))}${panel('Source / authorization context', 'Spending facts should be connected to the records that authorize and explain them.', domainSources('spending'))}</div>${panel('Investigation path', 'Find the first layer where a value becomes unusual before changing presentation logic.', `<div class="investigation-path"><span>MUNICIPALITY</span><b>→</b><span>FUND</span><b>→</b><span>BUSINESS UNIT</span><b>→</b><span>SERVICE</span><b>→</b><span>ACCOUNT</span><b>→</b><span>VENDOR / PROJECT</span><b>→</b><span>SOURCE RECORD</span></div>`)}</div>`;
}

function renderVendors() {
  const ds = datasetStatus('procurement'); const rows = getRows(ds.data); const questions = ['award concentration', 'amendment growth', 'repeat awards', 'method context'];
  const table = ds.status === 'ready' ? genericRowsTable(rows, [
    { label: 'Vendor', get: r => first(r, ['vendor_name', 'vendor', 'canonical_name']) }, { label: 'Solicitation / PO', get: r => first(r, ['solicitation', 'solicitation_id', 'po_number', 'award_id']) }, { label: 'Business unit', get: r => first(r, ['business_unit', 'unit']) }, { label: 'Method', get: r => first(r, ['method', 'procurement_method']) }, { label: 'Original value', get: r => first(r, ['original_award_value', 'original_value', 'amount']), format: money, numeric: true }, { label: 'Current value', get: r => first(r, ['current_contract_value', 'current_value']), format: money, numeric: true }
  ]) : '';
  return `<div class="page-stack">${evidenceNotice()}${domainIntro('procurement', questions)}<div class="split-grid wide-left">${panel('Vendor & contract explorer', 'Canonical vendor identity should retain every raw source name and match confidence.', table || emptyState('Procurement fact table awaits ingestion', 'Tender sources are registered; award and amendment extraction can populate procurement.json without changing this page.'))}${panel('Procurement sources', 'Tender notices plus Council/CAO approval records.', domainSources('procurement'))}</div>${panel('Vendor intelligence model', 'Useful signals must include procurement context.', lensGrid([['Amendment growth', 'Original award → amendment sequence → cumulative contract value.'], ['Category concentration', 'Vendor share within comparable categories and time periods.'], ['Repeat awards', 'Frequency and value across solicitations, with raw award evidence.'], ['Submission count', 'Only display where an official record explicitly reports it.'], ['Threshold proximity', 'Only interpret against the applicable policy and date.'], ['Project linkage', 'Connect vendor activity to capital projects and funding accounts.']]))}</div>`;
}

function renderPeople() {
  const rows = filteredCompensationRows().filter(row => !state.peopleQuery || normalize(`${row.name} ${row.position} ${row.business_unit}`).includes(normalize(state.peopleQuery)));
  const totals = rows.map(row => Number(row.total)).filter(Number.isFinite);
  const uniquePeople = new Set(rows.map(row => row.person_key)).size;
  const largest = totals.length ? Math.max(...totals) : null;
  const signals = computeCompSignals(rows);
  const byYear = [...new Set(rows.map(row => row.fiscal_year_end))].sort((a, b) => a - b).map(year => ({ year, total: rows.filter(row => row.fiscal_year_end === year).reduce((sum, row) => sum + Number(row.total || 0), 0), count: rows.filter(row => row.fiscal_year_end === year).length }));
  return `<div class="page-stack">
    <div class="notice"><strong>Disclosure limitation</strong><span>${escapeHtml(state.compensation.metadata?.note || 'This dataset may be incomplete.')} Absence from a year is not evidence of departure or zero compensation.</span></div>
    <div class="metrics-grid">
      ${metricCard('Verified seed rows', numberFmt.format(rows.length), filterDetail('checked-in disclosure rows'), 'accent')}
      ${metricCard('People represented', numberFmt.format(uniquePeople), 'Not a workforce count', 'neutral')}
      ${metricCard('Largest row in filtered seed', compactMoney(largest), 'Not a municipality-wide ranking while seed is partial', 'neutral')}
      ${metricCard('Review signals', numberFmt.format(signals.length), 'Computed only from available rows', signals.length ? 'warn' : 'good')}
    </div>
    <div class="split-grid wide-left">
      ${panel('Disclosure history in current seed', 'Totals below are sums of checked-in verified rows, not population totals.', compensationBars(byYear))}
      ${panel('Interpretation guide', 'What the source-defined fields can include.', `<div class="rule-list"><div><strong>Wages</strong><span>Can include regular pay, overtime and acting pay.</span></div><div><strong>Benefits / other</strong><span>Can include severance, vacation payout, allowances and other disclosed items.</span></div><div><strong>Threshold</strong><span>${money(state.compensation.metadata?.disclosure_threshold_cad)} annual disclosure floor in current metadata.</span></div></div>`)}
    </div>
    ${panel('Employee compensation explorer', 'Search within the global fiscal-year and business-unit filters. Click any row for its evidence and available history.', `<div class="local-toolbar"><label class="local-search"><span>⌕</span><input id="people-search" value="${escapeHtml(state.peopleQuery)}" placeholder="Search employee, role or unit" /></label><span class="table-note">${numberFmt.format(rows.length)} rows</span></div>${compensationTable(rows)}`)}
  </div>`;
}
function compensationBars(items) {
  if (!items.length) return emptyState('No rows under the current filters', 'Reset the global filters to inspect the available seed.');
  const max = Math.max(...items.map(item => item.total), 1);
  return `<div class="bar-chart">${items.map(item => `<div class="bar-row"><span>${item.year}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(3, item.total / max * 100)}%"></div></div><strong>${compactMoney(item.total)}</strong><small>${item.count} rows</small></div>`).join('')}</div>`;
}
function compensationTable(rows) {
  if (!rows.length) return emptyState('No matching compensation rows', 'This may reflect the current filter/search or the deliberately partial seed.');
  const sorted = [...rows].sort((a, b) => Number(b.fiscal_year_end) - Number(a.fiscal_year_end) || Number(b.total) - Number(a.total));
  return `<div class="table-wrap"><table><thead><tr><th>Year</th><th>Employee</th><th>Business unit</th><th>Position</th><th class="numeric">Wages</th><th class="numeric">Benefits</th><th class="numeric">Total</th></tr></thead><tbody>${sorted.map(row => `<tr data-person-key="${escapeHtml(row.person_key)}" data-person-year="${row.fiscal_year_end}"><td>${row.fiscal_year_end}</td><td><strong>${escapeHtml(row.name)}</strong><small class="cell-sub">${escapeHtml(row.entity)}</small></td><td>${escapeHtml(row.business_unit || '—')}</td><td>${escapeHtml(row.position || '—')}</td><td class="numeric">${money(row.wages)}</td><td class="numeric">${money(row.benefits)}</td><td class="numeric"><strong>${money(row.total)}</strong></td></tr>`).join('')}</tbody></table></div>`;
}

function renderProjects() {
  const ds = datasetStatus('capital'); const rows = getRows(ds.data); const questions = ['budget escalation', 'spend-to-date', 'schedule change', 'contract linkage'];
  const table = ds.status === 'ready' ? genericRowsTable(rows, [
    { label: 'Project', get: r => first(r, ['project_name', 'name']) }, { label: 'Code', get: r => first(r, ['project_code', 'code']) }, { label: 'Business unit', get: r => first(r, ['business_unit', 'unit']) }, { label: 'Status', get: r => first(r, ['status']) }, { label: 'Current budget', get: r => first(r, ['current_budget', 'budget']), format: money, numeric: true }, { label: 'Actual spend', get: r => first(r, ['actual_spend', 'actual']), format: money, numeric: true }
  ]) : '';
  return `<div class="page-stack">${evidenceNotice()}${domainIntro('capital', questions)}<div class="split-grid wide-left">${panel('Capital project explorer', 'Project pages should join approvals, budgets, awards, amendments, actuals and geography.', table || emptyState('Capital fact table awaits ingestion', 'The current source registry already includes the 2025/26 Capital Plan and historical ArcGIS project service.'))}${panel('Capital sources', 'Current and historical project context.', domainSources('capital'))}</div>${panel('Lifecycle analysis', 'Preserve every approved change rather than comparing only two endpoints.', `<div class="lifecycle"><span>INITIAL APPROVAL</span><b>→</b><span>SCOPE / BUDGET CHANGE</span><b>→</b><span>AWARD</span><b>→</b><span>AMENDMENTS</span><b>→</b><span>SPEND</span><b>→</b><span>COMPLETION / AUDIT</span></div>`)}</div>`;
}

function computeCompSignals(inputRows = filteredCompensationRows()) {
  const rows = inputRows.length ? inputRows : [];
  const grouped = new Map();
  for (const row of rows) {
    if (!grouped.has(row.person_key)) grouped.set(row.person_key, []);
    grouped.get(row.person_key).push(row);
  }
  const signals = [];
  for (const [personKey, group] of grouped) {
    const ordered = [...group].sort((a, b) => Number(a.fiscal_year_end) - Number(b.fiscal_year_end));
    for (let i = 1; i < ordered.length; i++) {
      const prior = ordered[i - 1]; const current = ordered[i];
      if (Number(current.fiscal_year_end) - Number(prior.fiscal_year_end) === 1 && Number(prior.total) > 0) {
        const change = (Number(current.total) - Number(prior.total)) / Number(prior.total);
        if (Math.abs(change) >= 0.20) signals.push({ id: `comp-change-${personKey}-${current.fiscal_year_end}`, type: 'Year-over-year change', priority: Math.abs(change) >= 0.35 ? 'high' : 'review', score: Math.min(99, Math.round(Math.abs(change) * 100 + 50)), name: current.name, year: current.fiscal_year_end, source_id: current.source_id, detail: `Total disclosed compensation changed ${pct(change, true)} from ${money(prior.total)} to ${money(current.total)}.`, facts: [`Prior year: ${money(prior.total)}`, `Current year: ${money(current.total)}`, `Change: ${pct(change, true)}`], caveat: 'Compensation may change for overtime, acting pay, severance, vacation payout, allowances or other permitted source-defined components.' });
      }
      if (prior.position !== current.position || prior.business_unit !== current.business_unit) signals.push({ id: `comp-role-${personKey}-${current.fiscal_year_end}`, type: 'Role / unit change', priority: 'info', score: 35, name: current.name, year: current.fiscal_year_end, source_id: current.source_id, detail: `Disclosure label changed from ${prior.position || 'unknown role'} / ${prior.business_unit || 'unknown unit'} to ${current.position || 'unknown role'} / ${current.business_unit || 'unknown unit'}.`, facts: [`Prior: ${prior.position || 'unknown'} · ${prior.business_unit || 'unknown'}`, `Current: ${current.position || 'unknown'} · ${current.business_unit || 'unknown'}`], caveat: 'Organizational naming changes can occur without a substantive role change.' });
    }
    for (const row of ordered) {
      const total = Number(row.total); const benefits = Number(row.benefits);
      if (total > 0 && benefits / total >= 0.10) signals.push({ id: `comp-benefit-${personKey}-${row.fiscal_year_end}`, type: 'Benefits concentration', priority: 'review', score: Math.min(90, Math.round(50 + benefits / total * 100)), name: row.name, year: row.fiscal_year_end, source_id: row.source_id, detail: `Benefits were ${decimalFmt.format(benefits / total * 100)}% of disclosed total (${money(benefits)} of ${money(total)}).`, facts: [`Wages: ${money(row.wages)}`, `Benefits: ${money(row.benefits)}`, `Total: ${money(row.total)}`], caveat: 'The source definition can include retirement/severance, vacation payout, allowances and other permitted items.' });
    }
  }
  return signals.sort((a, b) => b.score - a.score || Number(b.year) - Number(a.year));
}
function signalCard(signal) {
  return `<button type="button" class="signal-card" data-signal-id="${escapeHtml(signal.id)}"><div class="signal-top"><span class="signal-type">⚑ ${escapeHtml(signal.type)}</span>${badge(signal.priority === 'high' ? 'priority review' : signal.priority === 'review' ? 'review' : 'context', signal.priority === 'high' ? 'bad' : signal.priority === 'review' ? 'warn' : 'info')}</div><strong>${escapeHtml(signal.name)} · ${signal.year}</strong><p>${escapeHtml(signal.detail)}</p><small>score ${signal.score} · source ${escapeHtml(signal.source_id || 'unresolved')}</small></button>`;
}
function allSignals() {
  const calculated = computeCompSignals(); const generated = datasetStatus('signals');
  if (generated.status !== 'ready') return calculated;
  const external = getRows(generated.data).map((signal, index) => ({ id: first(signal, ['signal_id', 'id'], `generated-${index}`), type: first(signal, ['signal_type', 'type'], 'Generated signal'), priority: first(signal, ['priority', 'severity'], 'review'), score: Number(first(signal, ['score'], 50)), name: first(signal, ['title', 'entity_name', 'name'], 'Generated review signal'), year: first(signal, ['fiscal_year', 'year'], ''), source_id: first(signal, ['source_id']), detail: first(signal, ['summary', 'detail', 'description'], ''), facts: first(signal, ['observed_facts'], []), caveat: first(signal, ['interpretation', 'caveat'], 'Generated signal requires source-level review.') }));
  return [...calculated, ...external].sort((a, b) => b.score - a.score);
}
function renderSignals() {
  const signals = allSignals();
  const high = signals.filter(signal => signal.priority === 'high').length; const review = signals.filter(signal => signal.priority === 'review').length;
  return `<div class="page-stack">${evidenceNotice()}<div class="metrics-grid">${metricCard('Open review signals', numberFmt.format(signals.length), filterDetail('calculated + generated'), 'accent')}${metricCard('Priority review', numberFmt.format(high), 'Higher-magnitude screening conditions', high ? 'warn' : 'good')}${metricCard('Standard review', numberFmt.format(review), 'Evidence-backed prompts', review ? 'neutral' : 'good')}${metricCard('Confirmed findings', '0 asserted', 'The dashboard never promotes a signal automatically', 'good')}</div><div class="split-grid wide-left">${panel('Ranked review queue', 'Click a signal to inspect facts, caveats and source evidence.', signals.length ? `<div class="signal-list">${signals.map(signalCard).join('')}</div>` : emptyState('No signals available', 'No generated signals and no qualifying conditions in the current compensation rows.'))}${panel('Signal standard', 'A score prioritizes review; it is not a probability of misconduct.', `<div class="rule-list"><div><strong>Observed fact</strong><span>Direct source value.</span></div><div><strong>Derived metric</strong><span>Reproducible calculation.</span></div><div><strong>Review signal</strong><span>Rule/threshold says investigate.</span></div><div><strong>Human interpretation</strong><span>Context added after source review.</span></div><div><strong>Confirmed finding</strong><span>Only after separate evidence supports it.</span></div></div>`)}</div></div>`;
}

function renderSources() {
  const sources = state.sources.sources || [];
  const categories = [...new Set(sources.map(source => source.category))].sort((a, b) => a.localeCompare(b));
  const filtered = sources.filter(source => (state.sourceCategory === 'all' || source.category === state.sourceCategory) && (!state.sourceQuery || normalize(`${source.name} ${source.publisher} ${source.category} ${source.coverage}`).includes(normalize(state.sourceQuery))));
  const statusCounts = sources.reduce((acc, source) => { acc[source.status] = (acc[source.status] || 0) + 1; return acc; }, {});
  return `<div class="page-stack"><div class="metrics-grid">${metricCard('Registered sources', numberFmt.format(sources.length), `${categories.length} categories`, 'accent')}${metricCard('Ready', numberFmt.format(statusCounts.ready || 0), 'Current ready source definitions', 'good')}${metricCard('Historical ready', numberFmt.format(statusCounts['ready-historical'] || 0), 'Useful but known-stale/historical coverage', 'neutral')}${metricCard('Research', numberFmt.format(statusCounts.research || 0), 'Manual/research source work', (statusCounts.research || 0) ? 'warn' : 'good')}</div>${panel('Source registry', 'Coverage and freshness are part of the analytical product. Click a source for its evidence record.', `<div class="local-toolbar"><label class="local-search"><span>⌕</span><input id="source-search" value="${escapeHtml(state.sourceQuery)}" placeholder="Search source registry" /></label><select id="source-category"><option value="all">All categories</option>${categories.map(category => `<option value="${escapeHtml(category)}" ${category === state.sourceCategory ? 'selected' : ''}>${escapeHtml(category)}</option>`).join('')}</select><span class="table-note">${filtered.length} sources</span></div><div class="source-grid">${filtered.map(sourceCard).join('')}</div>`)}</div>`;
}
function sourceCard(source) {
  return `<button type="button" class="source-card" data-source-id="${escapeHtml(source.id)}"><div class="source-card-top">${badge(source.category, 'muted')}${badge(source.status, sourceStatusTone(source.status))}</div><strong>${escapeHtml(source.name)}</strong><span>${escapeHtml(source.publisher)}</span><p>${escapeHtml(source.coverage || 'Coverage not documented')}</p><footer><span>${escapeHtml(source.ingestion || 'ingestion unspecified')}</span><span>${escapeHtml(source.id)}</span></footer></button>`;
}
function lensGrid(items) { return `<div class="lens-grid">${items.map(([title, text]) => `<div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(text)}</p></div>`).join('')}</div>`; }

function bindViewEvents() {
  $$('#content [data-source-id]').forEach(element => element.addEventListener('click', () => showSource(element.dataset.sourceId)));
  $$('#content [data-domain]').forEach(element => element.addEventListener('click', () => showDomainCoverage(element.dataset.domain)));
  $$('#content [data-signal-id]').forEach(element => element.addEventListener('click', () => showSignal(element.dataset.signalId)));
  $$('#content [data-person-key]').forEach(element => element.addEventListener('click', () => showPerson(element.dataset.personKey, Number(element.dataset.personYear))));
  const peopleSearch = $('#people-search'); if (peopleSearch) peopleSearch.addEventListener('input', event => { state.peopleQuery = event.target.value; render(); requestAnimationFrame(() => { const input = $('#people-search'); if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); } }); });
  const sourceSearch = $('#source-search'); if (sourceSearch) sourceSearch.addEventListener('input', event => { state.sourceQuery = event.target.value; render(); requestAnimationFrame(() => { const input = $('#source-search'); if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); } }); });
  const sourceCategory = $('#source-category'); if (sourceCategory) sourceCategory.addEventListener('change', event => { state.sourceCategory = event.target.value; render(); });
}

function openDrawer({ title, eyebrow = 'EVIDENCE', html }) {
  $('#drawer-title').textContent = title;
  $('#drawer-eyebrow').textContent = eyebrow;
  $('#drawer-body').innerHTML = html;
  const dialog = $('#evidence-drawer');
  if (!dialog.open) dialog.showModal();
}
function evidenceSteps(steps) { return `<div class="evidence-steps">${steps.map(([title, value]) => `<div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(value ?? '—')}</span></div>`).join('')}</div>`; }
function sourceLink(source) {
  const url = safeUrl(source?.url);
  return url ? `<a class="source-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Open official source ↗</a>` : '';
}
function showSource(id) {
  const source = sourceById(id); if (!source) return;
  openDrawer({ title: source.name, eyebrow: 'SOURCE RECORD', html: `${evidenceSteps([['Source ID', source.id], ['Publisher', source.publisher], ['Category', source.category], ['Coverage', source.coverage], ['Ingestion', source.ingestion], ['Registry status', source.status]])}<div class="drawer-callout"><strong>Provenance expectation</strong><p>Normalized facts derived from this source should also retain retrieval time, source date, page/row/record locator, raw hash, parser version and validation status.</p></div>${sourceLink(source)}` });
}
function showDomainCoverage(key) {
  const meta = DOMAIN_META[key]; if (!meta) return;
  const ds = datasetStatus(key); const sources = sourcesForCategories(meta.categories);
  openDrawer({ title: meta.label, eyebrow: 'COVERAGE', html: `${evidenceSteps([['Generated artifact', ds.status], ['Expected path', OPTIONAL_FILES[key]], ['Registered sources', String(sources.length)], ['Purpose', meta.sourceHint]])}<div class="drawer-section"><h3>Registered evidence</h3>${sources.length ? `<div class="drawer-source-list">${sources.map(source => `<button type="button" data-drawer-source="${escapeHtml(source.id)}"><strong>${escapeHtml(source.name)}</strong><span>${escapeHtml(source.status)}</span></button>`).join('')}</div>` : '<p>No source entries currently map to this domain.</p>'}</div>` });
  $$('#drawer-body [data-drawer-source]').forEach(button => button.addEventListener('click', () => showSource(button.dataset.drawerSource)));
}
function showPerson(personKey, selectedYear) {
  const history = compensationRows().filter(row => row.person_key === personKey).sort((a, b) => Number(a.fiscal_year_end) - Number(b.fiscal_year_end));
  if (!history.length) return;
  const selected = history.find(row => Number(row.fiscal_year_end) === Number(selectedYear)) || history[history.length - 1];
  const source = sourceById(selected.source_id);
  const max = Math.max(...history.map(row => Number(row.total || 0)), 1);
  const trend = `<div class="drawer-section"><h3>Available disclosure history</h3><div class="mini-history">${history.map(row => `<div><span>${row.fiscal_year_end}</span><div><i style="width:${Math.max(3, Number(row.total || 0) / max * 100)}%"></i></div><strong>${compactMoney(row.total)}</strong></div>`).join('')}</div><p class="drawer-note">Only checked-in verified rows are shown. Missing years are not interpreted as zero.</p></div>`;
  openDrawer({ title: selected.name, eyebrow: 'COMPENSATION EVIDENCE', html: `${evidenceSteps([['Fiscal year', selected.fiscal_year_end], ['Business unit', selected.business_unit], ['Position', selected.position], ['Wages', money(selected.wages)], ['Benefits / other', money(selected.benefits)], ['Total', money(selected.total)], ['Source ID', selected.source_id]])}${trend}${source ? sourceLink(source) : ''}` });
}
function showSignal(id) {
  const signal = allSignals().find(item => item.id === id); if (!signal) return;
  const source = sourceById(signal.source_id);
  openDrawer({ title: `${signal.name}${signal.year ? ` · ${signal.year}` : ''}`, eyebrow: 'REVIEW SIGNAL', html: `${evidenceSteps([['Signal type', signal.type], ['Priority state', signal.priority], ['Review score', signal.score], ['Source ID', signal.source_id || 'unresolved']])}<div class="drawer-section"><h3>Observed / derived facts</h3><ul>${(signal.facts || []).map(fact => `<li>${escapeHtml(fact)}</li>`).join('') || `<li>${escapeHtml(signal.detail)}</li>`}</ul></div><div class="drawer-callout"><strong>Interpretation boundary</strong><p>${escapeHtml(signal.caveat || 'This signal requires source-level review and is not a finding.')}</p></div>${source ? sourceLink(source) : ''}` });
}
function showEvidenceStandard() {
  openDrawer({ title: 'Evidence standard', eyebrow: 'METHODOLOGY', html: `${evidenceSteps([['1 · Source fact', 'Value copied or parsed from an official/public-body source.'], ['2 · Derived metric', 'Calculation reproducible from retained fact fields.'], ['3 · Review signal', 'Explainable rule or threshold identifies an item for review.'], ['4 · Interpretation', 'Human/contextual assessment after reading source evidence.'], ['5 · Confirmed finding', 'Only where separate evidence supports the conclusion.']])}<div class="drawer-callout"><strong>Required provenance</strong><p>source_id · source_url · source_title · source_date · retrieved_at · locator_type · locator_value · raw_hash · parser_version · transform_notes · validation_status</p></div>` });
}
function runGlobalSearch(rawQuery) {
  const query = normalize(rawQuery);
  if (query.length < 2) { showEvidenceStandard(); return; }
  const people = compensationRows().filter(row => normalize(`${row.name} ${row.position} ${row.business_unit}`).includes(query)).slice(0, 12);
  const sources = (state.sources.sources || []).filter(source => normalize(`${source.name} ${source.publisher} ${source.category} ${source.coverage}`).includes(query)).slice(0, 12);
  const signals = allSignals().filter(signal => normalize(`${signal.name} ${signal.type} ${signal.detail}`).includes(query)).slice(0, 12);
  const uniquePeople = [...new Map(people.map(row => [row.person_key, row])).values()];
  const html = `<div class="drawer-section"><h3>People</h3>${uniquePeople.length ? `<div class="search-results">${uniquePeople.map(row => `<button type="button" data-search-person="${escapeHtml(row.person_key)}"><strong>${escapeHtml(row.name)}</strong><span>${escapeHtml(row.position || '')} · ${escapeHtml(row.business_unit || '')}</span></button>`).join('')}</div>` : '<p>No matching checked-in compensation names.</p>'}</div><div class="drawer-section"><h3>Sources</h3>${sources.length ? `<div class="search-results">${sources.map(source => `<button type="button" data-search-source="${escapeHtml(source.id)}"><strong>${escapeHtml(source.name)}</strong><span>${escapeHtml(source.category)} · ${escapeHtml(source.publisher)}</span></button>`).join('')}</div>` : '<p>No matching registered sources.</p>'}</div><div class="drawer-section"><h3>Signals</h3>${signals.length ? `<div class="search-results">${signals.map(signal => `<button type="button" data-search-signal="${escapeHtml(signal.id)}"><strong>${escapeHtml(signal.name)}</strong><span>${escapeHtml(signal.type)} · ${escapeHtml(signal.detail)}</span></button>`).join('')}</div>` : '<p>No matching review signals.</p>'}</div>`;
  openDrawer({ title: `Search: ${rawQuery.trim()}`, eyebrow: 'GLOBAL SEARCH', html });
  $$('#drawer-body [data-search-person]').forEach(button => button.addEventListener('click', () => showPerson(button.dataset.searchPerson)));
  $$('#drawer-body [data-search-source]').forEach(button => button.addEventListener('click', () => showSource(button.dataset.searchSource)));
  $$('#drawer-body [data-search-signal]').forEach(button => button.addEventListener('click', () => showSignal(button.dataset.searchSignal)));
}
