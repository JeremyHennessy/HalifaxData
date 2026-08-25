/* Build 003 compensation UI integration.
 * Loaded after app.js so the approved Build 002 dashboard shell stays intact.
 * This layer adapts the UI to the full configured-statement compensation dataset.
 */

const COMP_PAGE_SIZE = 100;
const compMoneyExactFmt = new Intl.NumberFormat('en-CA', {
  style: 'currency', currency: 'CAD', minimumFractionDigits: 2, maximumFractionDigits: 2
});

state.entity = 'all';
state.peoplePage = 1;
state.signalPage = 1;

function compMoneyExact(value) {
  return value == null || Number.isNaN(Number(value)) ? '—' : compMoneyExactFmt.format(Number(value));
}
function compensationIdentity(row) { return `${row.entity || 'Unknown entity'}||${row.person_key || ''}`; }
function parseCompensationIdentity(identity) {
  const marker = String(identity || '').indexOf('||');
  return marker < 0 ? { entity: null, personKey: String(identity || '') } : { entity: identity.slice(0, marker), personKey: identity.slice(marker + 2) };
}
function compensationSignalKey(row) {
  return `${normalize(row.entity).replace(/[^a-z0-9]+/g, '-')}-${normalize(row.person_key).replace(/[^a-z0-9]+/g, '-')}`;
}
function rowHasSourceMismatch(row) {
  return Array.isArray(row?.validation_flags) && row.validation_flags.includes('reported_total_mismatch');
}
function compensationDatasetLabel() {
  const status = state.compensation?.metadata?.dataset_status;
  if (status === 'automated_full_extraction') return 'Validated configured-statement extraction';
  if (status === 'partial_verified_seed') return 'Partial verified seed';
  return 'Generated disclosure data';
}
function resetCompensationPages() { state.peoplePage = 1; state.signalPage = 1; }

filteredCompensationRows = function filteredCompensationRowsIntegrated() {
  return compensationRows().filter(row =>
    (state.year === 'all' || String(row.fiscal_year_end) === state.year) &&
    (state.entity === 'all' || row.entity === state.entity) &&
    (state.unit === 'all' || row.business_unit === state.unit)
  );
};

const build002InitializeChrome = initializeChrome;
initializeChrome = function initializeChromeIntegrated() {
  build002InitializeChrome();
  const entities = [...new Set(compensationRows().map(row => row.entity).filter(Boolean))].sort((a, b) => a.localeCompare(b));
  $('#global-entity').innerHTML = `<option value="all">All reporting entities</option>${entities.map(entity => `<option value="${escapeHtml(entity)}">${escapeHtml(entity)}</option>`).join('')}`;

  $('#global-year').addEventListener('change', resetCompensationPages, { capture: true });
  $('#global-unit').addEventListener('change', resetCompensationPages, { capture: true });
  $('#global-entity').addEventListener('change', event => {
    state.entity = event.target.value;
    resetCompensationPages();
    render();
  });
  $('#reset-filters').addEventListener('click', () => {
    state.entity = 'all';
    resetCompensationPages();
    $('#global-entity').value = 'all';
  }, { capture: true });

  const status = state.compensation.metadata?.dataset_status;
  $('#data-mode').textContent = status === 'automated_full_extraction' ? 'Validated disclosures' : status === 'partial_verified_seed' ? 'Partial verified data' : 'Generated data';
};

const build002Render = render;
render = function renderIntegrated() {
  build002Render();
  const entityFilter = $('#global-entity-wrap');
  if (entityFilter) entityFilter.hidden = !['overview', 'people', 'signals'].includes(state.view);
};

evidenceNotice = function evidenceNoticeIntegrated() {
  const status = state.compensation?.metadata?.dataset_status;
  const note = status === 'automated_full_extraction'
    ? 'Compensation is fully extracted from the currently configured $100k+ annual disclosure statements; it is not a full-workforce payroll ledger. Other analytical domains may still be incomplete.'
    : 'Checked-in records may be partial.';
  return `<div class="notice"><strong>Interpretation boundary</strong><span>${note} A review signal is a reproducible prompt for investigation, not a finding of waste, wrongdoing, illegality or policy breach.</span></div>`;
};

filterDetail = function filterDetailIntegrated(label) {
  const parts = [];
  if (state.year !== 'all') parts.push(`FY ${state.year}`);
  if (state.entity !== 'all') parts.push(state.entity);
  if (state.unit !== 'all') parts.push(state.unit);
  return parts.length ? `${label} · ${escapeHtml(parts.join(' · '))}` : label;
};

reconciliationGraph = function reconciliationGraphIntegrated() {
  const nodes = ['SOURCE', 'APPROVAL', 'BUDGET', 'PROCUREMENT', 'VENDOR', 'PROJECT', 'AMENDMENT', 'ACTUAL', 'AUDIT'];
  return `<div class="flow">${nodes.map((node, index) => `${index ? '<span class="flow-arrow">→</span>' : ''}<span class="flow-node">${node}</span>`).join('')}</div><div class="flow secondary"><span class="flow-node">PERSON DISCLOSURE</span><span class="flow-arrow">→</span><span class="flow-node">FISCAL YEAR</span><span class="flow-arrow">→</span><span class="flow-node">REPORTING ENTITY</span><span class="flow-arrow">→</span><span class="flow-node">UNIT / POSITION</span><span class="flow-arrow">→</span><span class="flow-node">WAGES + BENEFITS</span><span class="flow-arrow">→</span><span class="flow-node">SOURCE</span></div>`;
};

renderOverview = function renderOverviewIntegrated() {
  const sources = state.sources.sources || [];
  const compensation = filteredCompensationRows();
  const years = [...new Set(compensationRows().map(row => row.fiscal_year_end))];
  const entities = [...new Set(compensation.map(row => row.entity).filter(Boolean))];
  const discrepancies = compensation.filter(rowHasSourceMismatch).length;
  const signals = computeCompSignals(compensation).slice(0, 6);
  const categories = [...new Set(sources.map(source => source.category))];
  return `<div class="page-stack">
    ${evidenceNotice()}
    <div class="metrics-grid">
      ${metricCard('Official sources mapped', numberFmt.format(sources.length), `${categories.length} evidence categories`, 'accent')}
      ${metricCard('Compensation disclosures', numberFmt.format(compensation.length), filterDetail(`${compensationDatasetLabel()} · ${entities.length} reporting entities`), 'good')}
      ${metricCard('Compensation history', years.length ? `${Math.min(...years)}–${Math.max(...years)}` : '—', '$100k+ configured annual disclosure statements', 'neutral')}
      ${metricCard('Source arithmetic flags', numberFmt.format(discrepancies), 'Published values preserved; discrepancies are not silently corrected', discrepancies ? 'warn' : 'good')}
    </div>
    <div class="split-grid wide-left">
      ${panel('Data coverage', 'Source discovery and generated analytical tables are deliberately tracked separately.', `<div class="coverage-grid">${['budget', 'spending', 'procurement', 'capital', 'financials', 'council'].map(domainCoverageCard).join('')}</div>`)}
      ${panel('Review queue', 'Highest-priority signals available under the current compensation filters.', signals.length ? `<div class="signal-list">${signals.map(signalCard).join('')}</div>` : emptyState('No signals under these filters', 'Change the fiscal year, reporting entity or business-unit filter to widen the current disclosure set.'))}
    </div>
    <div class="split-grid">
      ${panel('Public-money reconciliation graph', 'The long-term inspection path is a connected evidence graph, not a collection of unrelated charts.', reconciliationGraph())}
      ${panel('Data integrity controls', 'Rules the UI and collection pipeline preserve as coverage expands.', `<div class="rule-list"><div><strong>Missing ≠ zero</strong><span>Absence from threshold disclosure is never converted to zero compensation.</span></div><div><strong>Reporting entities stay isolated</strong><span>Same-name people in HRM, Halifax Water and Halifax Public Libraries are not joined without evidence.</span></div><div><strong>Published discrepancies remain visible</strong><span>Source totals are retained with an explicit delta and validation flag.</span></div><div><strong>Coverage visible</strong><span>Parser/source gaps appear in the product instead of disappearing.</span></div></div>`)}
    </div>
  </div>`;
};

function compensationEntityCoverage(rows) {
  const counts = new Map();
  for (const row of rows) counts.set(row.entity || 'Unknown', (counts.get(row.entity || 'Unknown') || 0) + 1);
  if (!counts.size) return '';
  return `<div class="entity-summary">${[...counts.entries()].sort((a, b) => b[1] - a[1]).map(([entity, count]) => `<div><strong>${numberFmt.format(count)}</strong><span>${escapeHtml(entity)}</span></div>`).join('')}</div>`;
}
function sourceDiscrepancyList(rows) {
  return `<div class="quality-list">${rows.map(row => `<button type="button" class="quality-row" data-person-key="${escapeHtml(compensationIdentity(row))}" data-person-year="${row.fiscal_year_end}"><span><strong>${escapeHtml(row.name)} · ${row.fiscal_year_end}</strong><small>${escapeHtml(row.entity)} · ${escapeHtml(row.source_id)}</small></span><span class="quality-delta ${Number(row.source_total_delta) < 0 ? 'negative' : ''}">${Number(row.source_total_delta) >= 0 ? '+' : ''}${compMoneyExact(row.source_total_delta)}</span></button>`).join('')}</div>`;
}
function compensationPagination(totalRows, page, target) {
  const pages = Math.max(1, Math.ceil(totalRows / COMP_PAGE_SIZE));
  const current = Math.min(Math.max(1, page), pages);
  const start = totalRows ? (current - 1) * COMP_PAGE_SIZE + 1 : 0;
  const end = Math.min(current * COMP_PAGE_SIZE, totalRows);
  return `<div class="pagination"><span class="pagination-info">${numberFmt.format(start)}–${numberFmt.format(end)} of ${numberFmt.format(totalRows)} · page ${current}/${pages}</span><div><button type="button" class="button subtle" data-page-target="${target}" data-page-action="prev" ${current <= 1 ? 'disabled' : ''}>Previous</button><button type="button" class="button subtle" data-page-target="${target}" data-page-action="next" ${current >= pages ? 'disabled' : ''}>Next</button></div></div>`;
}

renderPeople = function renderPeopleIntegrated() {
  const rows = filteredCompensationRows().filter(row => !state.peopleQuery || normalize(`${row.name} ${row.position} ${row.business_unit} ${row.entity}`).includes(normalize(state.peopleQuery)));
  const totals = rows.map(row => Number(row.total)).filter(Number.isFinite);
  const uniquePeople = new Set(rows.map(compensationIdentity)).size;
  const entities = [...new Set(rows.map(row => row.entity).filter(Boolean))];
  const largest = totals.length ? Math.max(...totals) : null;
  const discrepancyRows = rows.filter(rowHasSourceMismatch);
  const byYear = [...new Set(rows.map(row => row.fiscal_year_end))].sort((a, b) => a - b).map(year => ({ year, total: rows.filter(row => row.fiscal_year_end === year).reduce((sum, row) => sum + Number(row.total || 0), 0), count: rows.filter(row => row.fiscal_year_end === year).length }));
  return `<div class="page-stack">
    <div class="notice"><strong>Disclosure limitation</strong><span>${escapeHtml(state.compensation.metadata?.note || 'This dataset may be incomplete.')} A missing person/year is not evidence of departure or zero compensation.</span></div>
    <div class="metrics-grid">
      ${metricCard('Disclosure rows', numberFmt.format(rows.length), filterDetail(`${compensationDatasetLabel()} · ${entities.length} reporting entit${entities.length === 1 ? 'y' : 'ies'}`), 'accent')}
      ${metricCard('People represented', numberFmt.format(uniquePeople), 'Entity-isolated disclosure identities; not a workforce count', 'neutral')}
      ${metricCard('Largest disclosed total', compactMoney(largest), 'Largest row under the current filters', 'neutral')}
      ${metricCard('Source arithmetic flags', numberFmt.format(discrepancyRows.length), 'Published component/total mismatches preserved as evidence', discrepancyRows.length ? 'warn' : 'good')}
    </div>
    <div class="split-grid wide-left">
      ${panel('Threshold-disclosure history', 'Totals are sums of extracted $100k+ statement rows, not full payroll.', compensationBars(byYear))}
      ${panel('Coverage & interpretation', 'Reporting entities and source-defined compensation fields.', `${compensationEntityCoverage(rows)}<div class="rule-list compact-rules"><div><strong>Wages</strong><span>Can include regular pay, overtime and acting pay.</span></div><div><strong>Benefits / other</strong><span>Can include severance, vacation payout, allowances and other disclosed items.</span></div><div><strong>Threshold</strong><span>${money(state.compensation.metadata?.disclosure_threshold_cad)} annual disclosure floor.</span></div></div>`)}
    </div>
    ${discrepancyRows.length ? panel('Published source discrepancies', 'These are arithmetic inconsistencies in the source statements, not inferred wrongdoing.', sourceDiscrepancyList(discrepancyRows)) : ''}
    ${panel('Employee compensation explorer', 'Search within the active disclosure filters. Results are paged to keep the 10k+ row dataset responsive; click a row for entity-isolated history and source evidence.', `<div class="local-toolbar"><label class="local-search"><span>⌕</span><input id="people-search" value="${escapeHtml(state.peopleQuery)}" placeholder="Search employee, role, unit or entity" /></label><span class="table-note">${numberFmt.format(rows.length)} matching rows</span></div>${compensationTable(rows)}`)}
  </div>`;
};

compensationBars = function compensationBarsIntegrated(items) {
  if (!items.length) return emptyState('No rows under the current filters', 'Reset the compensation filters to inspect the configured disclosure statements.');
  const max = Math.max(...items.map(item => item.total), 1);
  return `<div class="bar-chart">${items.map(item => `<div class="bar-row"><span>${item.year}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(3, item.total / max * 100)}%"></div></div><strong>${compactMoney(item.total)}</strong><small>${numberFmt.format(item.count)} rows</small></div>`).join('')}</div>`;
};

compensationTable = function compensationTableIntegrated(rows) {
  if (!rows.length) return emptyState('No matching compensation rows', 'This may reflect the current year, reporting-entity, business-unit or search filter.');
  const sorted = [...rows].sort((a, b) => Number(b.fiscal_year_end) - Number(a.fiscal_year_end) || Number(b.total) - Number(a.total));
  const pages = Math.max(1, Math.ceil(sorted.length / COMP_PAGE_SIZE));
  state.peoplePage = Math.min(Math.max(1, state.peoplePage), pages);
  const start = (state.peoplePage - 1) * COMP_PAGE_SIZE;
  const visible = sorted.slice(start, start + COMP_PAGE_SIZE);
  return `${compensationPagination(sorted.length, state.peoplePage, 'people')}<div class="table-wrap"><table><thead><tr><th>Year</th><th>Employee</th><th>Business unit</th><th>Position</th><th class="numeric">Wages</th><th class="numeric">Benefits</th><th class="numeric">Total</th></tr></thead><tbody>${visible.map(row => `<tr data-person-key="${escapeHtml(compensationIdentity(row))}" data-person-year="${row.fiscal_year_end}"><td>${row.fiscal_year_end}</td><td><strong>${escapeHtml(row.name)}</strong><small class="cell-sub">${escapeHtml(row.entity)}</small></td><td>${escapeHtml(row.business_unit || '—')}</td><td>${escapeHtml(row.position || '—')}</td><td class="numeric">${money(row.wages)}</td><td class="numeric">${money(row.benefits)}</td><td class="numeric"><strong>${money(row.total)}</strong>${rowHasSourceMismatch(row) ? '<small class="data-flag">source total mismatch</small>' : ''}</td></tr>`).join('')}</tbody></table></div>${compensationPagination(sorted.length, state.peoplePage, 'people')}`;
};

computeCompSignals = function computeCompSignalsIntegrated(inputRows = filteredCompensationRows()) {
  const rows = inputRows.length ? inputRows : [];
  const grouped = new Map();
  for (const row of rows) {
    const key = compensationIdentity(row);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(row);
  }
  const signals = [];
  for (const group of grouped.values()) {
    const ordered = [...group].sort((a, b) => Number(a.fiscal_year_end) - Number(b.fiscal_year_end));
    const signalKey = compensationSignalKey(ordered[0] || {});
    for (let i = 1; i < ordered.length; i++) {
      const prior = ordered[i - 1]; const current = ordered[i];
      if (Number(current.fiscal_year_end) - Number(prior.fiscal_year_end) === 1 && Number(prior.total) > 0) {
        const change = (Number(current.total) - Number(prior.total)) / Number(prior.total);
        if (Math.abs(change) >= 0.20) signals.push({ id: `comp-change-${signalKey}-${current.fiscal_year_end}`, type: 'Year-over-year change', priority: Math.abs(change) >= 0.35 ? 'high' : 'review', score: Math.min(99, Math.round(Math.abs(change) * 100 + 50)), name: current.name, entity: current.entity, person_key: current.person_key, year: current.fiscal_year_end, source_id: current.source_id, detail: `Total disclosed compensation changed ${pct(change, true)} from ${money(prior.total)} to ${money(current.total)}.`, facts: [`Reporting entity: ${current.entity}`, `Prior year: ${money(prior.total)}`, `Current year: ${money(current.total)}`, `Change: ${pct(change, true)}`], caveat: 'Compensation may change for overtime, acting pay, severance, vacation payout, allowances or other permitted source-defined components.' });
      }
      if (prior.position !== current.position || prior.business_unit !== current.business_unit) signals.push({ id: `comp-role-${signalKey}-${current.fiscal_year_end}`, type: 'Role / unit change', priority: 'info', score: 35, name: current.name, entity: current.entity, person_key: current.person_key, year: current.fiscal_year_end, source_id: current.source_id, detail: `Disclosure label changed from ${prior.position || 'unknown role'} / ${prior.business_unit || 'unknown unit'} to ${current.position || 'unknown role'} / ${current.business_unit || 'unknown unit'}.`, facts: [`Reporting entity: ${current.entity}`, `Prior: ${prior.position || 'unknown'} · ${prior.business_unit || 'unknown'}`, `Current: ${current.position || 'unknown'} · ${current.business_unit || 'unknown'}`], caveat: 'Organizational naming changes can occur without a substantive role change.' });
    }
    for (const row of ordered) {
      const total = Number(row.total); const benefits = Number(row.benefits);
      if (total > 0 && benefits / total >= 0.10) signals.push({ id: `comp-benefit-${signalKey}-${row.fiscal_year_end}`, type: 'Benefits concentration', priority: 'review', score: Math.min(90, Math.round(50 + benefits / total * 100)), name: row.name, entity: row.entity, person_key: row.person_key, year: row.fiscal_year_end, source_id: row.source_id, detail: `Benefits were ${decimalFmt.format(benefits / total * 100)}% of disclosed total (${money(benefits)} of ${money(total)}).`, facts: [`Reporting entity: ${row.entity}`, `Wages: ${money(row.wages)}`, `Benefits: ${money(row.benefits)}`, `Total: ${money(row.total)}`], caveat: 'The source definition can include retirement/severance, vacation payout, allowances and other permitted items.' });
      if (rowHasSourceMismatch(row)) signals.push({ id: `comp-source-mismatch-${signalKey}-${row.fiscal_year_end}`, type: 'Source arithmetic mismatch', priority: 'review', score: 88, name: row.name, entity: row.entity, person_key: row.person_key, year: row.fiscal_year_end, source_id: row.source_id, detail: `The published total differs from published wages + benefits by ${Number(row.source_total_delta) >= 0 ? '+' : ''}${compMoneyExact(row.source_total_delta)}. HalifaxData preserves the published values.`, facts: [`Reporting entity: ${row.entity}`, `Published wages: ${compMoneyExact(row.wages)}`, `Published benefits: ${compMoneyExact(row.benefits)}`, `Published total: ${compMoneyExact(row.total)}`, `Published total delta: ${Number(row.source_total_delta) >= 0 ? '+' : ''}${compMoneyExact(row.source_total_delta)}`], caveat: 'This is a source-data arithmetic inconsistency detected by validation. It is not evidence of wrongdoing and HalifaxData does not silently correct the statement.' });
    }
  }
  return signals.sort((a, b) => b.score - a.score || Number(b.year) - Number(a.year) || String(a.name).localeCompare(String(b.name)));
};

signalCard = function signalCardIntegrated(signal) {
  return `<button type="button" class="signal-card" data-signal-id="${escapeHtml(signal.id)}"><div class="signal-top"><span class="signal-type">⚑ ${escapeHtml(signal.type)}</span>${badge(signal.priority === 'high' ? 'priority review' : signal.priority === 'review' ? 'review' : 'context', signal.priority === 'high' ? 'bad' : signal.priority === 'review' ? 'warn' : 'info')}</div><strong>${escapeHtml(signal.name)}${signal.year ? ` · ${signal.year}` : ''}</strong><p>${escapeHtml(signal.detail)}</p><small>${signal.entity ? `${escapeHtml(signal.entity)} · ` : ''}score ${signal.score} · source ${escapeHtml(signal.source_id || 'unresolved')}</small></button>`;
};

allSignals = function allSignalsIntegrated() {
  const calculated = computeCompSignals(); const generated = datasetStatus('signals');
  if (generated.status !== 'ready') return calculated;
  const external = getRows(generated.data).map((signal, index) => ({
    id: first(signal, ['signal_id', 'id'], `generated-${index}`), type: first(signal, ['signal_type', 'type'], 'Generated signal'), priority: first(signal, ['priority', 'severity'], 'review'), score: Number(first(signal, ['score'], 50)), name: first(signal, ['title', 'entity_name', 'name'], 'Generated review signal'), entity: first(signal, ['entity', 'reporting_entity']), year: first(signal, ['fiscal_year', 'year'], ''), source_id: first(signal, ['source_id']), detail: first(signal, ['summary', 'detail', 'description'], ''), facts: first(signal, ['observed_facts'], []), caveat: first(signal, ['interpretation', 'caveat'], 'Generated signal requires source-level review.')
  }));
  return [...calculated, ...external].sort((a, b) => b.score - a.score);
};

renderSignals = function renderSignalsIntegrated() {
  const signals = allSignals();
  const high = signals.filter(signal => signal.priority === 'high').length;
  const sourceMismatches = signals.filter(signal => signal.type === 'Source arithmetic mismatch').length;
  const pages = Math.max(1, Math.ceil(signals.length / COMP_PAGE_SIZE));
  state.signalPage = Math.min(Math.max(1, state.signalPage), pages);
  const start = (state.signalPage - 1) * COMP_PAGE_SIZE;
  const visible = signals.slice(start, start + COMP_PAGE_SIZE);
  return `<div class="page-stack">${evidenceNotice()}<div class="metrics-grid">${metricCard('Open review signals', numberFmt.format(signals.length), filterDetail('calculated + generated'), 'accent')}${metricCard('Priority review', numberFmt.format(high), 'Higher-magnitude screening conditions', high ? 'warn' : 'good')}${metricCard('Source arithmetic flags', numberFmt.format(sourceMismatches), 'Published mismatches retained and explicitly flagged', sourceMismatches ? 'warn' : 'good')}${metricCard('Confirmed findings', '0 asserted', 'The dashboard never promotes a signal automatically', 'good')}</div><div class="split-grid wide-left">${panel('Ranked review queue', 'Click a signal to inspect facts, caveats and source evidence. The queue is paged for the full disclosure dataset.', signals.length ? `${compensationPagination(signals.length, state.signalPage, 'signals')}<div class="signal-list">${visible.map(signalCard).join('')}</div>${compensationPagination(signals.length, state.signalPage, 'signals')}` : emptyState('No signals available', 'No generated signals and no qualifying conditions under the current filters.'))}${panel('Signal standard', 'A score prioritizes review; it is not a probability of misconduct.', `<div class="rule-list"><div><strong>Observed fact</strong><span>Direct source value.</span></div><div><strong>Derived metric</strong><span>Reproducible calculation.</span></div><div><strong>Review signal</strong><span>Rule/threshold says investigate.</span></div><div><strong>Human interpretation</strong><span>Context added after source review.</span></div><div><strong>Confirmed finding</strong><span>Only after separate evidence supports it.</span></div></div>`)}</div></div>`;
};

bindViewEvents = function bindViewEventsIntegrated() {
  $$('#content [data-source-id]').forEach(element => element.addEventListener('click', () => showSource(element.dataset.sourceId)));
  $$('#content [data-domain]').forEach(element => element.addEventListener('click', () => showDomainCoverage(element.dataset.domain)));
  $$('#content [data-signal-id]').forEach(element => element.addEventListener('click', () => showSignal(element.dataset.signalId)));
  $$('#content [data-person-key]').forEach(element => element.addEventListener('click', () => showPerson(element.dataset.personKey, Number(element.dataset.personYear))));
  $$('#content [data-page-action]').forEach(button => button.addEventListener('click', () => {
    const delta = button.dataset.pageAction === 'next' ? 1 : -1;
    if (button.dataset.pageTarget === 'people') state.peoplePage = Math.max(1, state.peoplePage + delta);
    if (button.dataset.pageTarget === 'signals') state.signalPage = Math.max(1, state.signalPage + delta);
    render();
  }));
  const peopleSearch = $('#people-search');
  if (peopleSearch) peopleSearch.addEventListener('input', event => {
    state.peopleQuery = event.target.value; state.peoplePage = 1; render();
    requestAnimationFrame(() => { const input = $('#people-search'); if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); } });
  });
  const sourceSearch = $('#source-search');
  if (sourceSearch) sourceSearch.addEventListener('input', event => {
    state.sourceQuery = event.target.value; render();
    requestAnimationFrame(() => { const input = $('#source-search'); if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); } });
  });
  const sourceCategory = $('#source-category');
  if (sourceCategory) sourceCategory.addEventListener('change', event => { state.sourceCategory = event.target.value; render(); });
};

showPerson = function showPersonIntegrated(identity, selectedYear) {
  const { entity, personKey } = parseCompensationIdentity(identity);
  const history = compensationRows().filter(row => (!entity || row.entity === entity) && row.person_key === personKey).sort((a, b) => Number(a.fiscal_year_end) - Number(b.fiscal_year_end));
  if (!history.length) return;
  const selected = history.find(row => Number(row.fiscal_year_end) === Number(selectedYear)) || history[history.length - 1];
  const source = sourceById(selected.source_id);
  const max = Math.max(...history.map(row => Number(row.total || 0)), 1);
  const trend = `<div class="drawer-section"><h3>Available disclosure history</h3><div class="mini-history">${history.map(row => `<div><span>${row.fiscal_year_end}</span><div><i style="width:${Math.max(3, Number(row.total || 0) / max * 100)}%"></i></div><strong>${compactMoney(row.total)}</strong></div>`).join('')}</div><p class="drawer-note">History is isolated to ${escapeHtml(selected.entity)}. Missing years are not interpreted as zero because the statements use a disclosure threshold.</p></div>`;
  const quality = rowHasSourceMismatch(selected) ? `<div class="drawer-callout"><strong>Source arithmetic mismatch</strong><p>The statement publishes wages + benefits that differ from the published total by ${Number(selected.source_total_delta) >= 0 ? '+' : ''}${compMoneyExact(selected.source_total_delta)}. HalifaxData preserves all source-published values and flags the discrepancy instead of correcting it.</p></div>` : '';
  const extraction = selected.extraction_method ? [['Extraction method', selected.extraction_method]] : [];
  openDrawer({ title: selected.name, eyebrow: 'COMPENSATION EVIDENCE', html: `${evidenceSteps([['Fiscal year', selected.fiscal_year_end], ['Reporting entity', selected.entity], ['Business unit', selected.business_unit], ['Position', selected.position], ['Wages', compMoneyExact(selected.wages)], ['Benefits / other', compMoneyExact(selected.benefits)], ['Published total', compMoneyExact(selected.total)], ...extraction, ['Source ID', selected.source_id]])}${quality}${trend}${source ? sourceLink(source) : ''}` });
};

showSignal = function showSignalIntegrated(id) {
  const signal = allSignals().find(item => item.id === id); if (!signal) return;
  const source = sourceById(signal.source_id);
  openDrawer({ title: `${signal.name}${signal.year ? ` · ${signal.year}` : ''}`, eyebrow: 'REVIEW SIGNAL', html: `${evidenceSteps([['Signal type', signal.type], ['Reporting entity', signal.entity || '—'], ['Priority state', signal.priority], ['Review score', signal.score], ['Source ID', signal.source_id || 'unresolved']])}<div class="drawer-section"><h3>Observed / derived facts</h3><ul>${(signal.facts || []).map(fact => `<li>${escapeHtml(fact)}</li>`).join('') || `<li>${escapeHtml(signal.detail)}</li>`}</ul></div><div class="drawer-callout"><strong>Interpretation boundary</strong><p>${escapeHtml(signal.caveat || 'This signal requires source-level review and is not a finding.')}</p></div>${source ? sourceLink(source) : ''}` });
};

runGlobalSearch = function runGlobalSearchIntegrated(rawQuery) {
  const query = normalize(rawQuery);
  if (query.length < 2) { showEvidenceStandard(); return; }
  const peopleMatches = compensationRows().filter(row => normalize(`${row.name} ${row.position} ${row.business_unit} ${row.entity}`).includes(query));
  const uniquePeople = [...new Map(peopleMatches.map(row => [compensationIdentity(row), row])).values()].slice(0, 12);
  const sources = (state.sources.sources || []).filter(source => normalize(`${source.name} ${source.publisher} ${source.category} ${source.coverage}`).includes(query)).slice(0, 12);
  const signals = allSignals().filter(signal => normalize(`${signal.name} ${signal.entity || ''} ${signal.type} ${signal.detail}`).includes(query)).slice(0, 12);
  const html = `<div class="drawer-section"><h3>People</h3>${uniquePeople.length ? `<div class="search-results">${uniquePeople.map(row => `<button type="button" data-search-person="${escapeHtml(compensationIdentity(row))}"><strong>${escapeHtml(row.name)}</strong><span>${escapeHtml(row.entity)} · ${escapeHtml(row.position || '')} · ${escapeHtml(row.business_unit || '')}</span></button>`).join('')}</div>` : '<p>No matching disclosed-compensation names.</p>'}</div><div class="drawer-section"><h3>Sources</h3>${sources.length ? `<div class="search-results">${sources.map(source => `<button type="button" data-search-source="${escapeHtml(source.id)}"><strong>${escapeHtml(source.name)}</strong><span>${escapeHtml(source.category)} · ${escapeHtml(source.publisher)}</span></button>`).join('')}</div>` : '<p>No matching registered sources.</p>'}</div><div class="drawer-section"><h3>Signals</h3>${signals.length ? `<div class="search-results">${signals.map(signal => `<button type="button" data-search-signal="${escapeHtml(signal.id)}"><strong>${escapeHtml(signal.name)}</strong><span>${escapeHtml(signal.entity || '')} · ${escapeHtml(signal.type)} · ${escapeHtml(signal.detail)}</span></button>`).join('')}</div>` : '<p>No matching review signals.</p>'}</div>`;
  openDrawer({ title: `Search: ${rawQuery.trim()}`, eyebrow: 'GLOBAL SEARCH', html });
  $$('#drawer-body [data-search-person]').forEach(button => button.addEventListener('click', () => showPerson(button.dataset.searchPerson)));
  $$('#drawer-body [data-search-source]').forEach(button => button.addEventListener('click', () => showSource(button.dataset.searchSource)));
  $$('#drawer-body [data-search-signal]').forEach(button => button.addEventListener('click', () => showSignal(button.dataset.searchSignal)));
};
