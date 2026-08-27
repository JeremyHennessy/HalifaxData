/* Build 014 — longitudinal public CAO contract-amendment series.
 * Expands the single Build 013 historical table into 12 identified public reports.
 * Exact identifiers only: no fuzzy contract or vendor linking.
 */

state.build014Amendments = { status: 'loading', data: null, error: null };
state.build014Sources = { status: 'loading', data: null, error: null };
state.build014Query = '';
state.build014Report = 'all';
let build014SourcesMerged = false;

async function b14FetchJson(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

Promise.allSettled([
  b14FetchJson('./data/generated/contract_amendments.json'),
  b14FetchJson('./data/contract_amendment_sources.json')
]).then(([dataResult, sourceResult]) => {
  state.build014Amendments = dataResult.status === 'fulfilled'
    ? { status: 'ready', data: dataResult.value, error: null }
    : { status: 'error', data: null, error: dataResult.reason?.message || 'Contract-amendment series failed to load' };
  state.build014Sources = sourceResult.status === 'fulfilled'
    ? { status: 'ready', data: sourceResult.value, error: null }
    : { status: 'error', data: null, error: sourceResult.reason?.message || 'Contract-amendment sources failed to load' };
  b14MergeSources();
  if (typeof render === 'function') render();
});

function b14Data() { return state.build014Amendments?.data || null; }
function b14Meta() { return b14Data()?.metadata || {}; }
function b14Summary() { return b14Data()?.summary || {}; }
function b14Reports() { return Array.isArray(b14Data()?.reports) ? b14Data().reports : []; }
function b14Observations() { return Array.isArray(b14Data()?.observations) ? b14Data().observations : []; }
function b14Trajectories() { return Array.isArray(b14Data()?.trajectories) ? b14Data().trajectories : []; }
function b14SupplementSources() { return Array.isArray(state.build014Sources?.data?.sources) ? state.build014Sources.data.sources : []; }

function b14MergeSources() {
  if (build014SourcesMerged || state.build014Sources?.status !== 'ready' || !Array.isArray(state.sources?.sources)) return false;
  const existing = new Set(state.sources.sources.map(source => source.id));
  for (const source of b14SupplementSources()) {
    if (!existing.has(source.id)) {
      state.sources.sources.push(source);
      existing.add(source.id);
    }
  }
  const researched = state.build014Sources?.data?.metadata?.last_researched;
  if (researched && (!state.sources.metadata?.last_researched || researched > state.sources.metadata.last_researched)) {
    state.sources.metadata = { ...(state.sources.metadata || {}), last_researched: researched };
  }
  build014SourcesMerged = true;
  return true;
}

function b14SourceById(id) {
  return sourceById(id) || b14SupplementSources().find(source => source.id === id) || null;
}
function b14SourceLink(sourceId, label = null) {
  const source = b14SourceById(sourceId);
  const url = safeUrl(source?.url);
  return source && url ? `<a class="source-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(label || source.name)} ↗</a>` : '';
}

const b14DateFormatter = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
function b14Date(value) {
  const parts = String(value || '').split('-').map(Number);
  if (parts.length !== 3 || parts.some(part => !Number.isFinite(part))) return value || '—';
  return b14DateFormatter.format(new Date(Date.UTC(parts[0], parts[1] - 1, parts[2], 12)));
}
function b14Pct(value) {
  const n = Number(value);
  return Number.isFinite(n) ? `${decimalFmt.format(n)}%` : '—';
}
function b14SignedMoney(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return `${n > 0 ? '+' : n < 0 ? '-' : ''}${money(Math.abs(n))}`;
}
function b14SchemaLabel(schema) {
  if (schema === 'original_updated_total_to_date') return 'Legacy total-to-date';
  if (schema === 'original_cumulative_amendment') return 'Cumulative amendment · updated derived';
  return 'Published amendment + updated value';
}
function b14Identifier(row) {
  return row.po || (Array.isArray(row.procurement_refs) && row.procurement_refs.length ? row.procurement_refs.join(' · ') : 'No exact contract identifier');
}
function b14UpdatedValue(row) {
  const value = row.updated_value_source ?? row.derived_updated_value;
  return Number.isFinite(Number(value)) ? Number(value) : null;
}
function b14AmendmentValue(row) {
  const value = row.effective_cumulative_amendment_value;
  return Number.isFinite(Number(value)) ? Number(value) : null;
}
function b14DisplayName(row) {
  return String(row.name_source || 'Contract amendment')
    .replace(/^\s*\d+\.\s*/, '')
    .replace(/^CAO\s+Award\s*[-–—:]?\s*/i, '')
    .replace(/^CAO\s+Contract\s+Amendment\s+Report\s*[-–—:]?\s*/i, '')
    .replace(/^CAO\s+Contract\s+Amendment\s*[-–—:]?\s*/i, '')
    .trim();
}

function b14FilteredObservations() {
  const query = normalize(state.build014Query);
  return b14Observations().filter(row => {
    if (state.build014Report !== 'all' && row.report_date !== state.build014Report) return false;
    if (!query) return true;
    return normalize(`${row.report_date} ${row.name_source} ${row.reason_source} ${row.po || ''} ${(row.procurement_refs || []).join(' ')} ${row.contract_key || ''}`).includes(query);
  });
}

function b14ReportTimelineHtml() {
  return `<div class="b14-timeline">${b14Reports().map(report => `<button type="button" class="b14-timeline-card ${state.build014Report === report.report_date ? 'active' : ''}" data-build014-report="${escapeHtml(report.report_date)}"><strong>${escapeHtml(b14Date(report.report_date))}</strong><span>${numberFmt.format(report.observation_count)} observations</span><small>${escapeHtml((report.schemas || []).map(b14SchemaLabel).join(' · '))}</small></button>`).join('')}</div>`;
}

function b14TrajectoryHtml() {
  const rows = b14Trajectories();
  if (!rows.length) return `<p class="table-note">No recurring exact contract identifier appears in more than one identified public report.</p>`;
  return `<div class="b14-trajectory-grid">${rows.map(row => {
    const step = row.steps?.[row.steps.length - 1];
    return `<button type="button" class="b14-trajectory-card" data-build014-trajectory="${escapeHtml(row.contract_key)}"><span>${badge('EXACT IDENTIFIER', 'info')}${badge(`${row.report_count} reports`, 'muted')}</span><h3>${escapeHtml(row.contract_key.replace(/^contract:/, 'Contract ').replace(/^po:/, 'PO '))}</h3><p>${escapeHtml(b14Date(row.first_report_date))} → ${escapeHtml(b14Date(row.last_report_date))} · ${money(row.first_original_value)} original → ${money(row.latest_total_value)} latest published/derived total</p><span class="b14-movement">${step?.published_cumulative_amendment_delta == null ? 'No comparable cumulative movement' : `${b14SignedMoney(step.published_cumulative_amendment_delta)} published cumulative-amendment movement`}</span><small class="cell-sub">${escapeHtml(row.contract_key_basis || row.caveat)}</small></button>`;
  }).join('')}</div>`;
}

function b14QualityFlagsHtml() {
  const flags = b14Observations().filter(row => row.source_arithmetic_consistent === false);
  if (!flags.length) return `<p class="table-note">No source arithmetic differences are recorded in the normalized public series.</p>`;
  return `<div class="b14-quality-grid">${flags.map(row => `<button type="button" class="b14-quality-card" data-build014-amendment="${escapeHtml(row.id)}"><strong>${escapeHtml(b14Identifier(row))} · ${escapeHtml(b14Date(row.report_date))}</strong><span>${b14SignedMoney(row.source_arithmetic_delta)} source arithmetic delta</span><small>${escapeHtml(b14DisplayName(row))}</small></button>`).join('')}</div>`;
}

function b14AmountCell(row) {
  const amount = b14AmendmentValue(row);
  if (amount == null) return '—';
  const derived = row.amendment_value_source == null;
  return `<strong>${money(amount)}</strong><small class="b14-semantic ${derived ? 'derived' : ''}">${derived ? 'derived from source total-to-date' : 'source-published cumulative amendment'}</small>`;
}
function b14UpdatedCell(row) {
  const value = b14UpdatedValue(row);
  if (value == null) return '—';
  const derived = row.updated_value_source == null;
  const flag = row.source_arithmetic_consistent === false ? `<small class="cell-sub b14-source-flag">source math ${b14SignedMoney(row.source_arithmetic_delta)}</small>` : '';
  return `${money(value)}<small class="b14-semantic ${derived ? 'derived' : ''}">${derived ? 'derived original + cumulative amendment' : 'source-published updated value'}</small>${flag}`;
}

function b14ObservationTableHtml() {
  const rows = b14FilteredObservations();
  const reports = b14Reports();
  return `<div class="b14-toolbar"><label class="local-search"><span>⌕</span><input id="b14-amendment-search" value="${escapeHtml(state.build014Query)}" placeholder="Search PO, contract, project or reason" /></label><select id="b14-report-filter"><option value="all">All 12 public reports</option>${reports.map(report => `<option value="${escapeHtml(report.report_date)}" ${state.build014Report === report.report_date ? 'selected' : ''}>${escapeHtml(b14Date(report.report_date))} · ${numberFmt.format(report.observation_count)} rows</option>`).join('')}</select><button type="button" class="button subtle" id="b14-reset">Reset</button><span class="table-note">${numberFmt.format(rows.length)} matched observations</span></div>
    <div class="table-wrap"><table class="b14-table"><thead><tr><th>Report</th><th>PO / contract</th><th>Context</th><th class="numeric">Original</th><th class="numeric">Cumulative amendment</th><th class="numeric">Updated total</th><th class="numeric">Increase</th></tr></thead><tbody>${rows.map(row => `<tr data-build014-amendment="${escapeHtml(row.id)}"><td><strong>${escapeHtml(b14Date(row.report_date))}</strong><small class="cell-sub">${escapeHtml(b14SchemaLabel(row.source_schema))}</small></td><td><strong>${escapeHtml(b14Identifier(row))}</strong><small class="cell-sub">${escapeHtml(row.contract_key_basis || 'No exact cross-report key created')}</small></td><td><strong>${escapeHtml(b14DisplayName(row))}</strong>${row.reason_source ? `<small class="cell-sub">${escapeHtml(row.reason_source)}</small>` : ''}</td><td class="numeric">${money(row.original_value)}</td><td class="numeric">${b14AmountCell(row)}</td><td class="numeric">${b14UpdatedCell(row)}</td><td class="numeric"><strong>${b14Pct(row.increase_pct_source ?? row.derived_increase_pct)}</strong></td></tr>`).join('')}</tbody></table></div>`;
}

function b14AmendmentSeriesHtml() {
  if (state.build014Amendments?.status === 'loading') return `<section class="panel b14-amendment-series"><header class="panel-header"><div><h2>Historical CAO amendment context — public series</h2><p>Loading the Build 014 amendment series.</p></div></header></section>`;
  if (state.build014Amendments?.status !== 'ready') return `<section class="panel b14-amendment-series"><header class="panel-header"><div><h2>Historical CAO amendment context — public series</h2><p>Build 014 amendment evidence is unavailable.</p></div></header><div class="panel-body">${emptyState('Amendment series unavailable', state.build014Amendments?.error || 'Unknown load error')}</div></section>`;
  const summary = b14Summary();
  return `<section class="panel b14-amendment-series"><header class="panel-header"><div><h2>Historical CAO amendment context — full public series</h2><p>Expands the complete public Nov. 15, 2023 baseline into 12 identified public HRM reports from May 2023 through Nov. 25, 2025, while keeping source amount semantics explicit.</p></div></header><div class="panel-body">
    <div class="notice b14-boundary"><strong>Amendment-report evidence, not payment evidence</strong><span>${escapeHtml(b14Meta().scope)} These are not invoices, accounts-payable transactions or final paid values. A large amendment can reflect legitimate scope, schedule, site-condition, utility, market, safety or operational changes and is not a finding of corruption, waste, illegality or policy breach. Private/confidential amendment reports may be excluded from the public sources.</span></div>
    <div class="metrics-grid compact b14-metrics">
      ${metricCard('Public reports', numberFmt.format(summary.report_count), `${escapeHtml(b14Date(b14Meta().coverage_start))} → ${escapeHtml(b14Date(b14Meta().coverage_end))}`, 'accent')}
      ${metricCard('Amendment observations', numberFmt.format(summary.observation_count), `${numberFmt.format(summary.unique_contract_keys)} exact contract identifiers`, 'neutral')}
      ${metricCard('Recurring exact trajectories', numberFmt.format(summary.recurring_exact_contract_keys), 'Exact PO / source contract reference only · no fuzzy linking', 'neutral')}
      ${metricCard('Source arithmetic flags', numberFmt.format(summary.source_arithmetic_flags), 'Source values preserved without silent correction', 'warn')}
    </div>
    ${b14ReportTimelineHtml()}
    ${panel('Exact-identifier longitudinal trajectories', 'Only the same source PO or procurement/contract reference is linked across reports. Vendor/project-name similarity is not used.', b14TrajectoryHtml())}
    ${panel('Source arithmetic controls', 'Differences between source-published original + amendment and source-published updated value remain visible as data-quality evidence.', b14QualityFlagsHtml())}
    ${panel('Public amendment observations', 'Source-published and derived fields are labelled separately because report schemas changed over time.', b14ObservationTableHtml())}
    <p class="b14-baseline-note">Build 013 baseline retained for regression: the Nov. 15, 2023 table remains the historical control. Build 014 broadens that evidence but is still not a complete historical amendment ledger or complete contract history.</p>
  </div></section>`;
}

function b14ShowObservation(id) {
  const row = b14Observations().find(item => item.id === id);
  if (!row) return;
  const location = row.source_locations?.[0] || {};
  const amendmentLabel = row.amendment_value_source == null ? 'Derived cumulative amendment' : 'Source-published cumulative amendment';
  const updatedLabel = row.updated_value_source == null ? 'Derived updated value' : 'Source-published updated value';
  openDrawer({
    title: b14DisplayName(row),
    eyebrow: 'LONGITUDINAL CONTRACT AMENDMENT EVIDENCE',
    html: `${evidenceSteps([
      ['Report date', b14Date(row.report_date)],
      ['PO / contract', b14Identifier(row)],
      ['Exact cross-report key', row.contract_key || 'None created'],
      ['Link basis', row.contract_key_basis || 'No exact identifier available'],
      ['Source schema', b14SchemaLabel(row.source_schema)],
      ['Original value', money(row.original_value)],
      [amendmentLabel, money(b14AmendmentValue(row))],
      [updatedLabel, money(b14UpdatedValue(row))],
      ['Source-published increase', b14Pct(row.increase_pct_source)],
      ['Derived increase', b14Pct(row.derived_increase_pct)],
      ['Source arithmetic delta', row.source_arithmetic_delta == null ? 'Not applicable to this source schema' : b14SignedMoney(row.source_arithmetic_delta)],
      ['Source arithmetic consistent?', row.source_arithmetic_consistent == null ? 'Not testable from published columns' : row.source_arithmetic_consistent ? 'Yes' : 'No — source values preserved without correction'],
      ['Source location', `Page ${location.page || '—'} · table ${location.table || '—'} · row ${location.row || '—'}`],
      ['Source-stated reason', row.reason_source || 'Not published in this aggregate row']
    ])}<div class="drawer-callout"><strong>Source amount semantics</strong><p>${escapeHtml(row.source_amount_semantics)}</p></div><div class="drawer-callout"><strong>Interpretation boundary</strong><p>This is public CAO amendment-report evidence, not an invoice or payment, not an accounts-payable transaction, not a final paid value, not a complete contract history, and not a wrongdoing finding. Public reports may exclude Private & Confidential amendments.</p></div>${row.source_cells?.length ? `<div class="drawer-section"><h3>Extracted source row</h3><div class="b14-source-cells">${escapeHtml(row.source_cells.join(' | '))}</div></div>` : ''}<div class="drawer-section"><h3>Sources</h3><div class="drawer-source-list">${b14SourceLink(row.source_id)}${b14SourceLink('hrm-procurement-policy-2022-012-adm', 'Procurement policy')}</div></div>`
  });
}

function b14ShowTrajectory(contractKey) {
  const row = b14Trajectories().find(item => item.contract_key === contractKey);
  if (!row) return;
  const observations = row.observation_ids.map(id => b14Observations().find(item => item.id === id)).filter(Boolean);
  const step = row.steps?.[0];
  openDrawer({
    title: row.contract_key.replace(/^contract:/, 'Contract ').replace(/^po:/, 'PO '),
    eyebrow: 'EXACT-IDENTIFIER AMENDMENT TRAJECTORY',
    html: `${evidenceSteps([
      ['Exact link basis', row.contract_key_basis],
      ['First public report', b14Date(row.first_report_date)],
      ['Latest public report', b14Date(row.last_report_date)],
      ['Public report count', numberFmt.format(row.report_count)],
      ['First original value', money(row.first_original_value)],
      ['Latest published / derived total', money(row.latest_total_value)],
      ['Latest cumulative amendment', money(row.latest_effective_cumulative_amendment_value)],
      ['Latest source increase', b14Pct(row.latest_increase_pct_source)],
      ['Published cumulative-amendment movement', step?.published_cumulative_amendment_delta == null ? 'Not comparable' : b14SignedMoney(step.published_cumulative_amendment_delta)]
    ])}<div class="drawer-section"><h3>Public report observations</h3><div class="rule-list">${observations.map(item => `<div><strong>${escapeHtml(b14Date(item.report_date))} · ${escapeHtml(b14Identifier(item))}</strong><span>${money(item.original_value)} original · ${money(b14AmendmentValue(item))} cumulative amendment · ${money(b14UpdatedValue(item))} updated · ${b14Pct(item.increase_pct_source)}</span></div>`).join('')}</div></div><div class="drawer-callout"><strong>Interpretation boundary</strong><p>${escapeHtml(step?.interpretation || row.caveat)} ${escapeHtml(row.caveat)} This trajectory is not an invoice/payment history, final paid value, complete contract history or wrongdoing finding.</p></div><div class="drawer-section"><h3>Sources</h3><div class="drawer-source-list">${observations.map(item => b14SourceLink(item.source_id)).join('')}</div></div>`
  });
}

function b14AmendmentInvestigations() {
  if (state.build014Amendments?.status !== 'ready') return [];
  const recurring = new Set(b14Trajectories().map(row => row.contract_key));
  const rows = b14Observations().filter(row => {
    const pct = Number(row.increase_pct_source ?? row.derived_increase_pct ?? 0);
    const amount = Math.abs(Number(b14AmendmentValue(row) || 0));
    return pct >= 75 || amount >= 250000 || row.source_arithmetic_consistent === false || recurring.has(row.contract_key);
  });
  const maxAmount = Math.max(1, ...rows.map(row => Math.abs(Number(b14AmendmentValue(row) || 0))));
  return rows.map(row => {
    const pct = Number(row.increase_pct_source ?? row.derived_increase_pct ?? 0);
    const amount = Math.abs(Number(b14AmendmentValue(row) || 0));
    const trajectory = b14Trajectories().find(item => item.contract_key && item.contract_key === row.contract_key);
    const materiality = b8ScoreMateriality(amount, maxAmount);
    const deviation = b8ScoreDeviation(pct / 100, 100);
    const persistence = trajectory ? 85 : 32;
    const evidence = row.source_arithmetic_consistent === false ? 92 : 98;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    const updated = b14UpdatedValue(row);
    return {
      id: `b14-amend-${b8Slug(row.id)}`,
      domain: 'Contract amendments', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${b14DisplayName(row)} — public amendment review`,
      detail: `${b14Date(row.report_date)} · ${b14Identifier(row)} · ${money(row.original_value)} → ${money(updated)} · ${b14Pct(pct)} published/derived increase`,
      materialityText: `${money(amount)} cumulative amendment value${row.amendment_value_source == null ? ' (derived from published total-to-date)' : ' in public report'}`,
      scope: `12 identified public CAO amendment reports, May 2023–Nov. 2025 · ${row.contract_key ? 'exact identifier available' : 'no cross-report key created'}`,
      sourceIds: [row.source_id, 'hrm-procurement-policy-2022-012-adm'],
      evidenceRows: [
        ['Report date', b14Date(row.report_date)],
        ['PO / contract', b14Identifier(row)],
        ['Exact cross-report key', row.contract_key || 'None created'],
        ['Original value', money(row.original_value)],
        ['Cumulative amendment', money(amount)],
        ['Updated total', money(updated)],
        ['Published increase', b14Pct(row.increase_pct_source)],
        ['Exact trajectory', trajectory ? `${trajectory.report_count} reports · ${b14Date(trajectory.first_report_date)} → ${b14Date(trajectory.last_report_date)}` : 'No recurring exact identifier'],
        ['Source arithmetic', row.source_arithmetic_consistent == null ? 'Not testable from published columns' : row.source_arithmetic_consistent ? 'Reconciles' : `${b14SignedMoney(row.source_arithmetic_delta)} mismatch preserved`],
        ['Source-stated reason', row.reason_source || 'Not published in this aggregate row']
      ],
      caveat: 'This ranking orders public amendment records for inspection. It is not a probability of corruption, fraud, waste, illegality or policy breach. Published cumulative amendments may include prior changes and are not necessarily one current change order; records are not invoices, AP transactions or final paid values.'
    };
  }).sort((a, b) => b.score - a.score);
}

const b14AllInvestigationsBase = b8AllInvestigations;
b8AllInvestigations = function b8AllInvestigationsBuild014() {
  const result = b14AllInvestigationsBase();
  if (state.build014Amendments?.status !== 'ready') return result;
  const fiscalWithoutBuild013Amendments = result.fiscal.filter(item => !String(item.id || '').startsWith('b13-amend-'));
  const fiscal = [...fiscalWithoutBuild013Amendments, ...b14AmendmentInvestigations()].sort((a, b) => b.score - a.score);
  const all = [...fiscal, ...result.quality];
  build008InvestigationIndex = new Map(all.map(item => [item.id, item]));
  return { fiscal, quality: result.quality };
};

function b14SourceCoverageHtml() {
  if (state.build014Sources?.status !== 'ready') return '';
  const sources = b14SupplementSources();
  return `<section class="panel b14-source-coverage"><header class="panel-header"><div><h2>Build 014 CAO amendment source series</h2><p>12 identified official public HRM amendment-report PDFs spanning May 2023 through November 2025.</p></div></header><div class="panel-body"><div class="b14-source-grid">${sources.map(source => `<div class="b14-source-card"><strong>${escapeHtml(source.name)}</strong><span>${escapeHtml(source.coverage)}</span><small>${escapeHtml(source.ingestion)}</small>${badge(source.status, sourceStatusTone(source.status))}${b14SourceLink(source.id, 'Open source')}</div>`).join('')}</div><div class="notice b14-boundary"><strong>Coverage boundary</strong><span>This is a longitudinal public-report series, not a complete contract-amendment ledger, accounts-payable ledger or payment history. Private/confidential reports may be excluded and no vendor aliases or fuzzy contract links are created.</span></div></div></section>`;
}

function b14EnhanceVendors() {
  const stack = $('#content .page-stack');
  if (!stack) return;
  const existing = stack.querySelector('.b14-amendment-series');
  if (existing) return;
  const build013 = stack.querySelector('.b13-amendment-history');
  if (build013) {
    build013.insertAdjacentHTML('beforebegin', b14AmendmentSeriesHtml());
    build013.remove();
    return;
  }
  const anchor = stack.querySelector('.b12-amendment-section') || stack.querySelector('.b11-procurement') || stack.lastElementChild;
  if (anchor) anchor.insertAdjacentHTML('afterend', b14AmendmentSeriesHtml());
}
function b14EnhanceSources() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b14-source-coverage')) return;
  stack.insertAdjacentHTML('beforeend', b14SourceCoverageHtml());
}

function b14BindEvents() {
  $$('#content [data-build014-amendment]').forEach(element => element.addEventListener('click', () => b14ShowObservation(element.dataset.build014Amendment)));
  $$('#content [data-build014-trajectory]').forEach(element => element.addEventListener('click', () => b14ShowTrajectory(element.dataset.build014Trajectory)));
  $$('#content [data-build014-report]').forEach(element => element.addEventListener('click', () => { state.build014Report = element.dataset.build014Report; render(); }));
  const query = $('#b14-amendment-search');
  if (query) query.addEventListener('input', event => { state.build014Query = event.target.value; render(); });
  const report = $('#b14-report-filter');
  if (report) report.addEventListener('change', event => { state.build014Report = event.target.value; render(); });
  const reset = $('#b14-reset');
  if (reset) reset.addEventListener('click', () => { state.build014Query = ''; state.build014Report = 'all'; render(); });
}

const b14RenderBase = render;
render = function renderBuild014() {
  b14MergeSources();
  b14RenderBase();
  if (state.view === 'vendors') b14EnhanceVendors();
  if (state.view === 'sources') b14EnhanceSources();
  b14BindEvents();
};
