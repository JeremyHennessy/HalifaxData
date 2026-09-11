/* Build 017/020 — audited financial source expansion.
 * The established conservative financial statement parser remains unchanged for
 * 2019-2025. Build 020 adds one bounded exception: four 2018 primary audited
 * statements are released through the separately validated source-specific OCR layer.
 * Layout and existing financial-history interaction surfaces are preserved.
 */

state.build017FinancialSources = { status: 'loading', data: null, error: null };
state.build020AuditedFinancialSources = { status: 'loading', data: null, error: null };
let build017FinancialSourcesMerged = false;

function b17FetchRegistry(url) {
  return fetch(url, { cache: 'no-store' }).then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  });
}

Promise.all([
  b17FetchRegistry('./data/audited_financial_sources.json'),
  b17FetchRegistry('./data/audited_financial_sources_build020.json')
])
  .then(([build017, build020]) => {
    state.build017FinancialSources = { status: 'ready', data: build017, error: null };
    state.build020AuditedFinancialSources = { status: 'ready', data: build020, error: null };
    b17MergeFinancialSources();
    if (typeof render === 'function') render();
  })
  .catch(error => {
    state.build017FinancialSources = { status: 'error', data: null, error: error.message };
    state.build020AuditedFinancialSources = { status: 'error', data: null, error: error.message };
    if (typeof render === 'function') render();
  });

function b17Registry() { return state.build017FinancialSources?.data || null; }
function b20AuditedRegistry() { return state.build020AuditedFinancialSources?.data || null; }
function b17SupplementSources() { return Array.isArray(b17Registry()?.sources) ? b17Registry().sources : []; }
function b20AuditedSources() { return Array.isArray(b20AuditedRegistry()?.sources) ? b20AuditedRegistry().sources : []; }
function b20AuditedSource2018() { return b20AuditedSources().find(source => source.id === 'hrm-financials-2018') || null; }
function b17RuntimeSupplementSources() {
  const overlay2018 = b20AuditedSource2018();
  return b17SupplementSources().map(source => source.id === 'hrm-financials-2018' && overlay2018 ? overlay2018 : source);
}
function b17ExpectedYears() {
  const build020Years = b20AuditedRegistry()?.metadata?.released_source_years;
  if (Array.isArray(build020Years) && build020Years.length) return build020Years;
  return Array.isArray(b17Registry()?.metadata?.expected_source_years) ? b17Registry().metadata.expected_source_years : [];
}
function b17ParseGapIds() {
  const original = Array.isArray(b17Registry()?.metadata?.documented_parse_gap_source_ids) ? b17Registry().metadata.documented_parse_gap_source_ids : [];
  return b20AuditedSource2018() ? original.filter(id => id !== 'hrm-financials-2018') : original;
}
function b20PartialSourceYears() {
  const years = b20AuditedRegistry()?.metadata?.remaining_partial_source_years;
  return Array.isArray(years) ? years : [];
}

function b17MergeFinancialSources() {
  if (
    build017FinancialSourcesMerged ||
    state.build017FinancialSources?.status !== 'ready' ||
    state.build020AuditedFinancialSources?.status !== 'ready' ||
    !Array.isArray(state.sources?.sources)
  ) return false;

  const runtimeSources = b17RuntimeSupplementSources();
  for (const source of runtimeSources) {
    const index = state.sources.sources.findIndex(existing => existing.id === source.id);
    if (index === -1) {
      state.sources.sources.push(source);
    } else if (source.id === 'hrm-financials-2018' && b20AuditedSource2018()) {
      state.sources.sources[index] = { ...state.sources.sources[index], ...source };
    }
  }

  const researched = [
    b17Registry()?.metadata?.last_researched,
    b20AuditedRegistry()?.metadata?.last_researched
  ].filter(Boolean).sort().at(-1);
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
    const pageCount = Number(status.eligible_statement_pages || 0);
    const pageLabel = year === 2018 ? 'eligible primary statement pages' : 'eligible statement/schedule pages';
    return `<div><strong>${escapeHtml(String(year))} · ${numberFmt.format(status.records || rows.filter(row => Number(row.fiscal_year_end) === year).length)} facts</strong><span>${escapeHtml(source?.name || sourceId)} · ${numberFmt.format(pageCount)} ${pageLabel}</span></div>`;
  }).join('');
  const standardParser = escapeHtml(meta.parser_version || '—');
  const ocrAdapter = escapeHtml(meta.ocr_adapter_version || b20AuditedSource2018()?.ocr_adapter_version || '—');
  return `<section class="panel b17-financial-coverage"><header class="panel-header"><div><h2>Audited financial history coverage</h2><p>Build 020 extends released source-year coverage to 2018–2025. The 2019–2025 sources retain the same conservative heading-anchored parser; 2018 uses a separately validated source-specific OCR adapter for the four primary audited statements. Source-presented prior-year comparators remain attached to their annual statement rather than being silently collapsed into a synthetic time series.</p></div></header><div class="panel-body">
    <div class="metrics-grid compact">
      ${metricCard('Released audited sources', numberFmt.format(meta.source_count || years.length), expected.length ? `${expected[0]}–${expected[expected.length - 1]} source-year series` : years.join(' · '), 'accent')}
      ${metricCard('Normalized statement facts', numberFmt.format(rows.length), 'Conservative source-year statement facts', 'good')}
      ${metricCard('Statement families', numberFmt.format(new Set(rows.map(row => row.statement_family)).size), 'Financial position, operations, net financial assets, cash flows and schedules where released', 'neutral')}
      ${metricCard('Standard parser', standardParser, `2019–2025 unchanged · 2018 OCR ${ocrAdapter}`, 'neutral')}
    </div>
    <div class="rule-list">${yearCards}</div>
    <div class="notice"><strong>2018 partial source coverage</strong><span>HalifaxData releases 79 normalized primary-statement facts from four official image-backed statement pages. Raw OCR values are preserved; eight current-year OCR digit corrections are explicitly validated against the text-native 2019 audited statement's printed 2018 comparatives. Image-backed 2018 schedules remain unreleased.</span></div>
    <div class="notice"><strong>Longitudinal boundary</strong><span>Each annual statement can restate or reclassify its prior-year comparator. HalifaxData preserves the source-year context and does not treat repeated comparator values as independent additive facts or force audited PSAS lines onto operating-department budget categories.</span></div>
  </div></section>`;
}

function b17SourceCoverageHtml() {
  if (state.build017FinancialSources?.status !== 'ready' || state.build020AuditedFinancialSources?.status !== 'ready') return '';
  const expected = b17ExpectedYears();
  const runtimeSources = b17RuntimeSupplementSources();
  const ready = runtimeSources.filter(source => String(source.status || '').startsWith('ready'));
  const partialYears = b20PartialSourceYears();
  return `<section class="panel b17-financial-sources"><header class="panel-header"><div><h2>Build 020 audited financial sources</h2><p>The established 2019–2025 standard-parser source series is preserved unchanged. Build 020 adds the official 2018 Audit &amp; Finance attachment through a bounded OCR primary-statement layer; the image-backed 2018 schedules remain explicitly unreleased.</p></div></header><div class="panel-body">
    <div class="metrics-grid compact">
      ${metricCard('Released source years', numberFmt.format(expected.length), expected.length ? `${expected[0]}–${expected[expected.length - 1]}` : '—', 'accent')}
      ${metricCard('Supplemental released sources', numberFmt.format(ready.length), 'Existing 2023 and 2025 source definitions retained', 'neutral')}
      ${metricCard('Partial source years', numberFmt.format(partialYears.length), partialYears.length ? `${partialYears.join(' · ')} schedules not released` : 'None', partialYears.length ? 'warn' : 'good')}
    </div>
    <div class="source-mini-list">${runtimeSources.map(source => `<a class="build006-doc-link" href="${escapeHtml(safeUrl(source.url) || '#')}" target="_blank" rel="noreferrer"><span><strong>${escapeHtml(source.name)}</strong><small>${escapeHtml(source.coverage)} · ${escapeHtml(source.status)} · ${escapeHtml(source.ingestion)}</small></span><span>↗</span></a>`).join('')}</div>
    <div class="notice"><strong>Source-series boundary</strong><span>This registry expands audited PSAS source coverage only. It does not create an operating-budget crosswalk, payment ledger, transaction history or project-level actual-spend dataset. Aggregate audited statement facts are not invoices or accounts-payable transactions.</span></div>
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
