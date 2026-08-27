/* Build 017 — audited financial source expansion.
 * The established conservative financial statement parser is unchanged. This layer
 * merges the additional official source definitions into the runtime registry and
 * makes the expanded source-year coverage explicit without changing financial facts.
 */

state.build017FinancialSources = { status: 'loading', data: null, error: null };
let build017FinancialSourcesMerged = false;

fetch('./data/audited_financial_sources.json', { cache: 'no-store' })
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(data => {
    state.build017FinancialSources = { status: 'ready', data, error: null };
    b17MergeFinancialSources();
    if (typeof render === 'function') render();
  })
  .catch(error => {
    state.build017FinancialSources = { status: 'error', data: null, error: error.message };
    if (typeof render === 'function') render();
  });

function b17Registry() { return state.build017FinancialSources?.data || null; }
function b17SupplementSources() { return Array.isArray(b17Registry()?.sources) ? b17Registry().sources : []; }
function b17ExpectedYears() { return Array.isArray(b17Registry()?.metadata?.expected_source_years) ? b17Registry().metadata.expected_source_years : []; }

function b17MergeFinancialSources() {
  if (build017FinancialSourcesMerged || state.build017FinancialSources?.status !== 'ready' || !Array.isArray(state.sources?.sources)) return false;
  const existing = new Set(state.sources.sources.map(source => source.id));
  for (const source of b17SupplementSources()) {
    if (!existing.has(source.id)) {
      state.sources.sources.push(source);
      existing.add(source.id);
    }
  }
  const researched = b17Registry()?.metadata?.last_researched;
  if (researched && (!state.sources.metadata?.last_researched || researched > state.sources.metadata.last_researched)) {
    state.sources.metadata = { ...(state.sources.metadata || {}), last_researched: researched };
  }
  build017FinancialSourcesMerged = true;
  const snapshot = $('#snapshot-label');
  if (snapshot) snapshot.textContent = `Sources researched ${state.sources.metadata?.last_researched || 'date unknown'}`;
  return true;
}

function b17FinancialCoverageHtml() {
  const ds = datasetStatus('financials');
  if (ds.status !== 'ready') return '';
  const rows = getRows(ds.data);
  const meta = ds.data?.metadata || {};
  const years = [...new Set(rows.map(row => Number(row.fiscal_year_end)).filter(Number.isFinite))].sort((a, b) => a - b);
  const expected = b17ExpectedYears();
  const statusBySource = new Map((meta.source_status || []).map(item => [item.source_id, item]));
  const yearCards = years.map(year => {
    const sourceId = `hrm-financials-${year}`;
    const status = statusBySource.get(sourceId) || {};
    const source = sourceById(sourceId);
    return `<div><strong>${escapeHtml(String(year))} · ${numberFmt.format(status.records || rows.filter(row => Number(row.fiscal_year_end) === year).length)} facts</strong><span>${escapeHtml(source?.name || sourceId)} · ${numberFmt.format(status.eligible_statement_pages || 0)} eligible statement/schedule page${Number(status.eligible_statement_pages || 0) === 1 ? '' : 's'}</span></div>`;
  }).join('');
  return `<section class="panel b17-financial-coverage"><header class="panel-header"><div><h2>Audited financial history coverage</h2><p>Build 017 expands the same conservative heading-anchored parser from two annual sources to a contiguous 2018–2025 source-year series. Source-presented prior-year comparators remain attached to their annual statement rather than being silently collapsed into a synthetic time series.</p></div></header><div class="panel-body">
    <div class="metrics-grid compact">
      ${metricCard('Annual audited sources', numberFmt.format(meta.source_count || years.length), expected.length ? `${expected[0]}–${expected[expected.length - 1]} source-year series` : years.join(' · '), 'accent')}
      ${metricCard('Normalized statement facts', numberFmt.format(rows.length), 'Same conservative statement/schedule parser', 'good')}
      ${metricCard('Statement families', numberFmt.format(new Set(rows.map(row => row.statement_family)).size), 'Financial position, operations, net financial assets, cash flows and schedules where published', 'neutral')}
      ${metricCard('Parser semantics', escapeHtml(meta.parser_version || '—'), 'Build 017 changes source coverage, not extraction rules', 'neutral')}
    </div>
    <div class="rule-list">${yearCards}</div>
    <div class="notice"><strong>Longitudinal boundary</strong><span>Each annual statement can restate or reclassify its prior-year comparator. HalifaxData preserves the source-year context and does not treat repeated comparator values as independent additive facts or force audited PSAS lines onto operating-department budget categories.</span></div>
  </div></section>`;
}

function b17SourceCoverageHtml() {
  if (state.build017FinancialSources?.status !== 'ready') return '';
  const expected = b17ExpectedYears();
  return `<section class="panel b17-financial-sources"><header class="panel-header"><div><h2>Build 017 audited financial sources</h2><p>Six additional official HRM annual audited-statement sources extend the existing 2023/2025 registry into a contiguous eight-source series.</p></div></header><div class="panel-body">
    <div class="metrics-grid compact">
      ${metricCard('Configured source years', numberFmt.format(expected.length), expected.length ? `${expected[0]}–${expected[expected.length - 1]}` : '—', 'accent')}
      ${metricCard('New source definitions', numberFmt.format(b17SupplementSources().length), 'Existing 2023 and 2025 source definitions retained', 'neutral')}
    </div>
    <div class="source-mini-list">${b17SupplementSources().map(source => `<a class="build006-doc-link" href="${escapeHtml(safeUrl(source.url) || '#')}" target="_blank" rel="noreferrer"><span><strong>${escapeHtml(source.name)}</strong><small>${escapeHtml(source.coverage)} · ${escapeHtml(source.ingestion)}</small></span><span>↗</span></a>`).join('')}</div>
    <div class="notice"><strong>Source-series boundary</strong><span>This registry expands audited source coverage only. It does not create an operating-budget crosswalk, payment ledger, transaction history or project-level actual-spend dataset.</span></div>
  </div></section>`;
}

function b17EnhanceFinancials() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b17-financial-coverage')) return;
  const metrics = stack.querySelector('.metrics-grid');
  if (metrics) metrics.insertAdjacentHTML('afterend', b17FinancialCoverageHtml());
  else stack.insertAdjacentHTML('afterbegin', b17FinancialCoverageHtml());
}
function b17EnhanceSources() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b17-financial-sources')) return;
  stack.insertAdjacentHTML('beforeend', b17SourceCoverageHtml());
}

const b17RenderBase = render;
render = function renderBuild017() {
  b17MergeFinancialSources();
  b17RenderBase();
  if (state.view === 'financials') b17EnhanceFinancials();
  if (state.view === 'sources') b17EnhanceSources();
};
