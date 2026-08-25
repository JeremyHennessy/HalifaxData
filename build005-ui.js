/* Build 005 dashboard integration.
 *
 * This layer loads after the Build 004 shell and budget integration. It does
 * not alter collector/model logic. New domains render analytical facts only
 * when data/domain_quality.json marks them ready.
 */

state.domainQuality = null;
state.domainQualityError = null;
state.procurementQuery = '';
state.procurementEntity = 'all';

const publicTenderNav = NAV.find(item => item[0] === 'vendors');
if (publicTenderNav) publicTenderNav[1] = 'Public Tender Awards';

if (window.HalifaxDataQualityPromise) {
  window.HalifaxDataQualityPromise
    .then(manifest => {
      state.domainQuality = manifest;
      if (state.compensation && state.sources && Object.keys(state.optional || {}).length) render();
    })
    .catch(error => {
      state.domainQualityError = error instanceof Error ? error.message : String(error);
      if (state.compensation && state.sources && Object.keys(state.optional || {}).length) render();
    });
}

function domainQualityEntry(key) {
  return state.domainQuality?.domains?.[key] || null;
}
function domainQualityLabel(status) {
  if (status === 'ready') return 'Validated for analysis';
  if (status === 'hold') return 'Data quality hold';
  if (status === 'review') return 'Validation review';
  if (status === 'missing') return 'Awaiting generated artifact';
  return 'Quality status unavailable';
}
function domainQualityTone(status) {
  if (status === 'ready') return 'good';
  if (status === 'hold') return 'bad';
  if (status === 'review') return 'warn';
  return 'muted';
}
function domainQualityPanel(key) {
  const entry = domainQualityEntry(key);
  if (!entry) {
    return `<div class="notice danger quality-gate-notice"><strong>Quality gate unavailable</strong><span>${escapeHtml(state.domainQualityError || 'The domain quality manifest is unavailable. HalifaxData is failing closed for this analytical domain.')}</span></div>`;
  }
  const status = domainQualityLabel(entry.status);
  return `<div class="quality-status-card ${escapeHtml(entry.status)}"><div class="quality-status-heading"><span>${badge(status, domainQualityTone(entry.status))}</span><strong>${escapeHtml(entry.label || DOMAIN_META[key]?.label || key)}</strong></div><p>${escapeHtml(entry.reason || 'No validation rationale recorded.')}</p><div><strong>Coverage boundary</strong><span>${escapeHtml(entry.boundary || 'No coverage boundary recorded.')}</span></div></div>`;
}

const build004GeneratedStatus = generatedStatus;
generatedStatus = function generatedStatusWithQualityGate(key) {
  const quality = domainQualityEntry(key);
  if (quality?.status === 'hold') return { text: 'Data quality hold', tone: 'bad' };
  if (quality?.status === 'review') return { text: 'Validation review', tone: 'warn' };
  if (quality?.status === 'missing') return { text: 'Awaiting generated artifact', tone: 'warn' };
  return build004GeneratedStatus(key);
};

const build004Render = render;
render = function renderWithBuild005DomainFilters() {
  build004Render();
  const filterbar = $('.filterbar');
  if (filterbar) filterbar.hidden = ['budget', 'vendors', 'spending', 'projects'].includes(state.view);
};

function procurementRows() {
  return getRows(datasetStatus('procurement').data);
}
function procurementRowKey(row) {
  return [row?.award_id, row?.vendor_name, row?.awarded_date, row?.original_award_value].map(value => String(value ?? '')).join('||');
}
function findProcurementRow(key) {
  return procurementRows().find(row => procurementRowKey(row) === key) || null;
}
function procurementPublishedAmount(row) {
  const value = first(row, ['original_award_value', 'current_contract_value']);
  return value == null || Number.isNaN(Number(value)) ? null : Number(value);
}
function procurementCategoryLabel(row) {
  const raw = String(row?.category || '').trim();
  if (!raw) return '—';
  const flags = raw.split('/').map(value => value.trim().toUpperCase());
  if (flags.length === 3 && flags.every(value => value === 'Y' || value === 'N')) {
    const labels = ['Goods', 'Service', 'Construction'];
    const active = labels.filter((_, index) => flags[index] === 'Y');
    return active.length ? active.join(' + ') : 'Unspecified';
  }
  return raw;
}
function procurementDate(value) {
  const raw = String(value || '').trim();
  return raw ? raw.slice(0, 10) : '—';
}
function procurementEntityOptions() {
  return [...new Set(procurementRows().map(row => row.entity).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}
function filteredProcurementRows() {
  const query = normalize(state.procurementQuery);
  return procurementRows().filter(row =>
    (state.procurementEntity === 'all' || row.entity === state.procurementEntity) &&
    (!query || normalize(`${row.award_id || ''} ${row.vendor_name || ''} ${row.entity || ''} ${row.description || ''} ${procurementCategoryLabel(row)}`).includes(query))
  );
}
function procurementTable(rows) {
  if (!rows.length) return emptyState('No matching tender awards', 'Change the local entity or text filter.');
  const sorted = [...rows].sort((a, b) => String(b.awarded_date || '').localeCompare(String(a.awarded_date || '')) || String(a.award_id || '').localeCompare(String(b.award_id || '')));
  return `<div class="table-wrap"><table class="procurement-table"><thead><tr><th>Awarded</th><th>Tender</th><th>Vendor</th><th>Entity</th><th>Category</th><th class="numeric">Published award amount</th></tr></thead><tbody>${sorted.slice(0, 500).map(row => {
    const amount = procurementPublishedAmount(row);
    return `<tr data-procurement-row="${escapeHtml(procurementRowKey(row))}"><td>${escapeHtml(procurementDate(row.awarded_date))}</td><td><strong>${escapeHtml(row.award_id || '—')}</strong><small class="cell-sub procurement-description">${escapeHtml(row.description || 'No description published')}</small></td><td>${escapeHtml(row.vendor_name || '—')}</td><td>${escapeHtml(row.entity || '—')}</td><td>${escapeHtml(procurementCategoryLabel(row))}</td><td class="numeric"><strong>${money(amount)}</strong>${amount != null && amount < 0 ? '<small class="cell-sub signed-source-value">signed source value</small>' : ''}</td></tr>`;
  }).join('')}</tbody></table></div>`;
}

renderVendors = function renderPublicTenderAwards() {
  const quality = domainQualityEntry('procurement');
  const ds = datasetStatus('procurement');
  if (quality?.status !== 'ready' || ds.status !== 'ready') {
    return `<div class="page-stack">${evidenceNotice()}${domainIntro('procurement', ['award history', 'vendor frequency', 'entity mix', 'published award amounts'])}${domainQualityPanel('procurement')}${panel('Public tender awards', 'HalifaxData will not render procurement facts unless the domain quality gate and checked-in artifact are both ready.', emptyState('Procurement analysis is unavailable', 'Review the quality status and source coverage before enabling analytical rows.'))}${panel('Procurement sources', 'Official tender and procurement evidence registered for this domain.', domainSources('procurement'))}</div>`;
  }

  const allRows = procurementRows();
  const rows = filteredProcurementRows();
  const vendors = new Set(allRows.map(row => row.vendor_name).filter(Boolean));
  const entities = new Set(allRows.map(row => row.entity).filter(Boolean));
  const withAmount = allRows.filter(row => {
    const amount = procurementPublishedAmount(row);
    return amount != null && amount !== 0;
  }).length;
  const dates = allRows.map(row => procurementDate(row.awarded_date)).filter(value => value !== '—').sort();
  const dateRange = dates.length ? `${dates[0].slice(0, 4)}–${dates[dates.length - 1].slice(0, 4)}` : '—';

  return `<div class="page-stack procurement-page">
    <div class="notice"><strong>Public tender coverage boundary</strong><span>This view contains Nova Scotia public-tender award records filtered to Halifax municipal bodies. It is not a complete accounts-payable ledger, does not include every alternative procurement or later amendment, and preserves signed published award amounts without automatically treating them as municipal spending.</span></div>
    <div class="metrics-grid">
      ${metricCard('Tender award rows', numberFmt.format(allRows.length), `${dateRange} source-published award history`, 'accent')}
      ${metricCard('Vendor labels', numberFmt.format(vendors.size), 'Raw source vendor labels; not yet canonical identities', 'neutral')}
      ${metricCard('Reporting entities', numberFmt.format(entities.size), 'HRM / Halifax municipal bodies in source filter', 'neutral')}
      ${metricCard('Rows with published amount', numberFmt.format(withAmount), 'Signed source field; not an AP spend total', 'good')}
    </div>
    ${panel('Public tender award explorer', 'Search official award records. Click a row for source provenance and the exact interpretation boundary.', `<div class="local-toolbar procurement-toolbar"><label class="local-search"><span>⌕</span><input id="procurement-search" value="${escapeHtml(state.procurementQuery)}" placeholder="Search tender, vendor, entity or description" /></label><select id="procurement-entity"><option value="all">All reporting entities</option>${procurementEntityOptions().map(entity => `<option value="${escapeHtml(entity)}" ${entity === state.procurementEntity ? 'selected' : ''}>${escapeHtml(entity)}</option>`).join('')}</select><span class="table-note">${numberFmt.format(rows.length)} matching rows · first 500 displayed</span></div>${procurementTable(rows)}`)}
    <div class="split-grid wide-left">
      ${panel('Evidence & quality status', 'The analytical contract is explicit and source-bounded.', `${domainQualityPanel('procurement')}${domainSources('procurement')}`)}
      ${panel('Supported analysis lenses', 'Use only questions supported by the current award dataset.', lensGrid([['Award frequency', 'Count source-published awards by vendor label, entity, category or time period.'], ['Published amount distribution', 'Inspect source-published signed award amounts without relabeling them as accounts-payable spend.'], ['Entity mix', 'Compare award activity across the Halifax municipal bodies represented in this source extract.'], ['Category mix', 'Use the source Goods / Service / Construction flags while retaining their raw values.'], ['Timeline', 'Inspect tender start, close and award dates for source-published records.'], ['Evidence drilldown', 'Every displayed row retains source ID, API locator and official source link.']]))}
    </div>
  </div>`;
};

renderSpending = function renderSpendingQualityHold() {
  return `<div class="page-stack">${evidenceNotice()}${domainIntro('spending', ['quarterly variance', 'service-level movement', 'source-table reconciliation'])}${domainQualityPanel('spending')}<div class="split-grid wide-left">${panel('Spend explorer blocked by quality gate', 'The checked-in quarterly artifact is not transaction-level accounts payable and currently contains a verified merged-cell parsing defect.', emptyState('Data quality hold', 'HalifaxData is deliberately not loading or rendering the invalid spending amounts. The parser must be corrected and the artifact regenerated before this view can become analytical.'))}${panel('Source / authorization context', 'Registered records remain available for source research while the generated fact table is held.', domainSources('spending'))}</div>${panel('Investigation path', 'When valid granular facts exist, trace the first layer where a value becomes unusual before interpreting it.', `<div class="investigation-path"><span>MUNICIPALITY</span><b>→</b><span>FUND</span><b>→</b><span>BUSINESS UNIT</span><b>→</b><span>SERVICE</span><b>→</b><span>ACCOUNT</span><b>→</b><span>VENDOR / PROJECT</span><b>→</b><span>SOURCE RECORD</span></div>`)}</div>`;
};

renderProjects = function renderCapitalQualityHold() {
  return `<div class="page-stack">${evidenceNotice()}${domainIntro('capital', ['project identity', 'approved budget', 'award linkage', 'schedule and scope changes'])}${domainQualityPanel('capital')}<div class="split-grid wide-left">${panel('Capital project explorer blocked by quality gate', 'The current mixed historical/capital-plan artifact contains a verified project-code parsing defect.', emptyState('Data quality hold', 'HalifaxData is deliberately not rendering malformed capital-plan project identities. The artifact must be regenerated against the corrected collector and revalidated first.'))}${panel('Capital sources', 'The underlying official plan and historical ArcGIS sources remain registered for evidence review.', domainSources('capital'))}</div>${panel('Lifecycle analysis', 'Once project identity is stable, preserve every approved change rather than comparing only two endpoints.', `<div class="lifecycle"><span>INITIAL APPROVAL</span><b>→</b><span>SCOPE / BUDGET CHANGE</span><b>→</b><span>AWARD</span><b>→</b><span>AMENDMENTS</span><b>→</b><span>SPEND</span><b>→</b><span>COMPLETION / AUDIT</span></div>`)}</div>`;
};

function showProcurementRow(key) {
  const row = findProcurementRow(key);
  if (!row) return;
  const source = sourceById(row.source_id);
  const provenance = row.provenance || {};
  const amount = procurementPublishedAmount(row);
  openDrawer({
    title: row.award_id || row.vendor_name || 'Tender award',
    eyebrow: 'PUBLIC TENDER EVIDENCE',
    html: `${evidenceSteps([
      ['Tender / award ID', row.award_id || '—'],
      ['Vendor label', row.vendor_name || '—'],
      ['Reporting entity', row.entity || '—'],
      ['Description', row.description || '—'],
      ['Category', procurementCategoryLabel(row)],
      ['Raw category flags', row.category || '—'],
      ['Procurement method', row.method || '—'],
      ['Tender start', procurementDate(row.tender_start_date)],
      ['Tender close', procurementDate(row.tender_close_date)],
      ['Awarded date', procurementDate(row.awarded_date)],
      ['Published award amount', money(amount)],
      ['Source locator', provenance.locator_value || row.award_id || '—'],
      ['Source ID', row.source_id || '—']
    ])}<div class="drawer-callout"><strong>Signed source-value boundary</strong><p>This amount is reproduced from the official awarded-tender source. HalifaxData preserves the published sign, including negative source values, and does not infer whether the value represents expenditure, disposal proceeds, a credit, amendment, or another accounting treatment without separate evidence.</p></div>${source ? sourceLink(source) : ''}`
  });
}

const build004BindViewEvents = bindViewEvents;
bindViewEvents = function bindViewEventsWithBuild005() {
  build004BindViewEvents();
  $$('#content [data-procurement-row]').forEach(element => element.addEventListener('click', () => showProcurementRow(element.dataset.procurementRow)));

  const procurementSearch = $('#procurement-search');
  if (procurementSearch) procurementSearch.addEventListener('input', event => {
    state.procurementQuery = event.target.value;
    render();
    requestAnimationFrame(() => {
      const input = $('#procurement-search');
      if (input) {
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
      }
    });
  });

  const procurementEntity = $('#procurement-entity');
  if (procurementEntity) procurementEntity.addEventListener('change', event => {
    state.procurementEntity = event.target.value;
    render();
  });
};
