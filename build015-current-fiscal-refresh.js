/* Build 015 — current fiscal quarterly reporting refresh.
 * Adds 2025/26 Q1-Q3 source coverage and exposes the stronger longitudinal
 * quarterly series without changing the underlying summary-row semantics.
 */

state.build015QuarterlySources = { status: 'loading', data: null, error: null };
let build015SourcesMerged = false;

async function b15FetchJson(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

b15FetchJson('./data/quarterly_financial_sources.json').then(data => {
  state.build015QuarterlySources = { status: 'ready', data, error: null };
  b15MergeSources();
  if (typeof render === 'function') render();
}).catch(error => {
  state.build015QuarterlySources = { status: 'error', data: null, error: error.message || 'Quarterly source registry failed to load' };
  if (typeof render === 'function') render();
});

function b15Sources() {
  return Array.isArray(state.build015QuarterlySources?.data?.sources) ? state.build015QuarterlySources.data.sources : [];
}
function b15MergeSources() {
  if (build015SourcesMerged || state.build015QuarterlySources?.status !== 'ready' || !Array.isArray(state.sources?.sources)) return false;
  const existing = new Set(state.sources.sources.map(source => source.id));
  for (const source of b15Sources()) {
    if (!existing.has(source.id)) {
      state.sources.sources.push({
        ...source,
        category: 'Budgets & actuals'
      });
      existing.add(source.id);
    }
  }
  const researched = state.build015QuarterlySources?.data?.metadata?.last_researched;
  if (researched && (!state.sources.metadata?.last_researched || researched > state.sources.metadata.last_researched)) {
    state.sources.metadata = { ...(state.sources.metadata || {}), last_researched: researched };
  }
  build015SourcesMerged = true;
  return true;
}

function b15SpendingData() { return datasetStatus('spending').data || null; }
function b15Rows() { return getRows(b15SpendingData()); }
function b15Meta() { return b15SpendingData()?.metadata || {}; }
function b15Date(value) {
  const parts = String(value || '').split('-').map(Number);
  if (parts.length !== 3 || parts.some(part => !Number.isFinite(part))) return value || '—';
  return new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' })
    .format(new Date(Date.UTC(parts[0], parts[1] - 1, parts[2], 12)));
}

function b15TrajectoryStats() {
  const rows = b15Rows();
  const grouped = typeof b9SpendingSeries === 'function' ? b9SpendingSeries(rows) : { series: [], ambiguousDates: 0 };
  let yoyPairs = 0;
  let currentFiscalSeries = 0;
  for (const series of grouped.series || []) {
    const dates = new Set((series.points || []).map(point => point.date));
    let hasCurrent = false;
    for (const point of series.points || []) {
      if (point.row?.fiscal_year === '2025/26') hasCurrent = true;
      const year = Number(String(point.date || '').slice(0, 4));
      if (!Number.isFinite(year)) continue;
      if (dates.has(`${year - 1}${String(point.date).slice(4)}`)) yoyPairs += 1;
    }
    if (hasCurrent) currentFiscalSeries += 1;
  }
  return {
    matchedSeries: (grouped.series || []).length,
    ambiguousDates: grouped.ambiguousDates || 0,
    yoyPairs,
    currentFiscalSeries
  };
}

function b15Stats() {
  const rows = b15Rows();
  const sources = b15Sources();
  const statuses = Array.isArray(b15Meta().source_status) ? b15Meta().source_status : [];
  const currentSources = sources.filter(source => source.fiscal_year === '2025/26');
  const currentRows = rows.filter(row => row.fiscal_year === '2025/26');
  return {
    reportCount: Number(b15Meta().report_count || sources.length || statuses.length || 0),
    latestPeriodEnd: b15Meta().latest_period_end || statuses.map(item => item.period_end).filter(Boolean).sort().at(-1) || null,
    currentReportCount: currentSources.length,
    currentRows: currentRows.length,
    totalRows: rows.length,
    currentSources,
    ...b15TrajectoryStats()
  };
}

function b15SourceLink(source) {
  const url = safeUrl(source?.url);
  return url ? `<a class="source-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Open report ↗</a>` : '';
}

function b15TimelineHtml() {
  const statuses = new Map((b15Meta().source_status || []).map(item => [item.source_id, item]));
  return `<div class="b15-timeline">${b15Sources().map(source => {
    const status = statuses.get(source.id) || {};
    return `<button type="button" class="b15-quarter-card ${source.fiscal_year === '2025/26' ? 'current' : ''}" data-source-id="${escapeHtml(source.id)}"><span>${badge(`${source.fiscal_year} · Q${source.quarter}`, source.fiscal_year === '2025/26' ? 'info' : 'muted')}</span><strong>${escapeHtml(b15Date(source.period_end))}</strong><small>${status.records == null ? 'Source registered' : `${numberFmt.format(status.records)} extracted summary rows`}</small></button>`;
  }).join('')}</div>`;
}

function b15CurrentReportsHtml() {
  const current = b15Sources().filter(source => source.fiscal_year === '2025/26');
  return `<div class="b15-current-grid">${current.map(source => `<div class="b15-current-card"><div><span>${badge(`Q${source.quarter}`, 'info')}</span><strong>${escapeHtml(source.name)}</strong><p>${escapeHtml(source.coverage)}</p></div>${b15SourceLink(source)}</div>`).join('')}</div>`;
}

function b15QuarterlyPanel() {
  if (state.build015QuarterlySources?.status === 'loading') {
    return `<section class="panel b15-current-fiscal"><header class="panel-header"><div><h2>Current quarterly financial series</h2><p>Loading Build 015 source coverage.</p></div></header></section>`;
  }
  if (state.build015QuarterlySources?.status !== 'ready') {
    return `<section class="panel b15-current-fiscal"><header class="panel-header"><div><h2>Current quarterly financial series</h2><p>Build 015 source registry is unavailable.</p></div></header><div class="panel-body">${emptyState('Quarterly source coverage unavailable', state.build015QuarterlySources?.error || 'Unknown load error')}</div></section>`;
  }
  const stats = b15Stats();
  const refreshed = b15Meta().parser_version === 'build015-quarterly-financial-v1';
  return `<section class="panel b15-current-fiscal"><header class="panel-header"><div><h2>Current quarterly financial series</h2><p>Build 015 extends the checked quarterly reporting series through Q3 2025/26 and feeds the existing trajectory and cross-domain pattern engine with newer like-for-like source rows.</p></div></header><div class="panel-body">
    <div class="notice b15-boundary"><strong>Financial-summary evidence, not transaction evidence</strong><span>These records come from official HRM quarterly financial-report tables. They are not invoices, accounts-payable transactions, vendor payments or final paid values. Source wording such as “spent or committed” remains source context and is not converted into cash-payment evidence.</span></div>
    <div class="metrics-grid compact b15-metrics">
      ${metricCard('Public quarterly reports', numberFmt.format(stats.reportCount), refreshed ? `${numberFmt.format(stats.totalRows)} conservative summary rows` : 'Refresh artifact pending', 'accent')}
      ${metricCard('2025/26 reports', numberFmt.format(stats.currentReportCount), 'Q1 · Q2 · Q3 identified official reports', 'good')}
      ${metricCard('Latest period', stats.latestPeriodEnd ? escapeHtml(b15Date(stats.latestPeriodEnd)) : '—', 'Period end represented in checked series', 'neutral')}
      ${metricCard('Same-period YoY pairs', numberFmt.format(stats.yoyPairs), `${numberFmt.format(stats.matchedSeries)} unambiguous like-for-like series`, 'neutral')}
    </div>
    ${b15TimelineHtml()}
    ${panel('2025/26 official reporting set', 'Each report remains separately traceable; missing periods are not imputed.', b15CurrentReportsHtml())}
    <div class="b15-method-grid">
      <div><strong>${numberFmt.format(stats.currentRows)}</strong><span>2025/26 extracted summary rows</span></div>
      <div><strong>${numberFmt.format(stats.currentFiscalSeries)}</strong><span>matched trajectories touching 2025/26</span></div>
      <div><strong>${numberFmt.format(stats.ambiguousDates)}</strong><span>ambiguous key/date combinations excluded</span></div>
      <div><strong>Explicit gap</strong><span>2024/25 Q1 is not in the current checked source set; absence is not treated as zero.</span></div>
    </div>
    <p class="table-note">The existing Build 009 trajectory engine automatically re-evaluates persistence, reversals, acceleration and exact same-period year-over-year comparisons using this refreshed source-backed series. Dollar values from different accounting scopes are never added together for cross-domain corroboration.</p>
  </div></section>`;
}

function b15SourcePanel() {
  if (state.build015QuarterlySources?.status !== 'ready') return '';
  return `<section class="panel b15-source-panel"><header class="panel-header"><div><h2>Build 015 quarterly financial sources</h2><p>${numberFmt.format(b15Sources().length)} official HRM reports in the checked longitudinal source set, including Q1-Q3 2025/26.</p></div></header><div class="panel-body">${b15TimelineHtml()}<div class="notice b15-boundary"><strong>Coverage boundary</strong><span>This source set supports quarterly financial-summary analysis only. It does not close the public accounts-payable/payment-ledger gap, and absent quarters are not fabricated or inferred.</span></div></div></section>`;
}

function b15EnhanceSpending() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b15-current-fiscal')) return;
  const anchor = stack.querySelector('.b9-spending-trajectories');
  if (anchor) anchor.insertAdjacentHTML('beforebegin', b15QuarterlyPanel());
  else {
    const firstPanel = stack.querySelector('.panel');
    if (firstPanel) firstPanel.insertAdjacentHTML('beforebegin', b15QuarterlyPanel());
    else stack.insertAdjacentHTML('beforeend', b15QuarterlyPanel());
  }
}
function b15EnhanceSources() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b15-source-panel')) return;
  stack.insertAdjacentHTML('beforeend', b15SourcePanel());
}
function b15BindEvents() {
  $$('#content .b15-current-fiscal [data-source-id], #content .b15-source-panel [data-source-id]').forEach(element => {
    element.addEventListener('click', () => showSource(element.dataset.sourceId));
  });
}

window.b15Stats = b15Stats;
window.b15Sources = b15Sources;

const b15RenderBase = render;
render = function renderBuild015() {
  b15MergeSources();
  b15RenderBase();
  if (state.view === 'spending') b15EnhanceSpending();
  if (state.view === 'sources') b15EnhanceSources();
  b15BindEvents();
};
