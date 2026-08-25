/* Build 003 dashboard integration fixes.
 * Loaded after app.js so these function declarations replace the initial
 * Build 002 dashboard implementations without rewriting the dashboard shell.
 */

function personScopeKey(row) {
  return `${row.entity || 'unknown'}::${row.person_key || ''}`;
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
      ${metricCard('Verified compensation rows', numberFmt.format(compensation.length), filterDetail('configured disclosure rows'), 'neutral')}
      ${metricCard('Compensation history', years.length ? `${Math.min(...years)}–${Math.max(...years)}` : '—', '$100k+ threshold disclosures from configured annual statements', 'neutral')}
      ${metricCard('Additional generated domains', `${readyGenerated}/6`, 'Budget, spending, procurement, capital, financials, Council', readyGenerated ? 'good' : 'warn')}
    </div>
    <div class="split-grid wide-left">
      ${panel('Data coverage', 'Source discovery and generated analytical tables are deliberately tracked separately.', `<div class="coverage-grid">${['budget', 'spending', 'procurement', 'capital', 'financials', 'council'].map(domainCoverageCard).join('')}</div>`)}
      ${panel('Review queue', 'Highest-priority signals available under the current global filters.', signals.length ? `<div class="signal-list">${signals.map(signalCard).join('')}</div>` : emptyState('No signals under these filters', 'Change the fiscal year or business-unit filter to widen the current disclosure set.'))}
    </div>
    <div class="split-grid">
      ${panel('Public-money reconciliation graph', 'The long-term inspection path is a connected evidence graph, not a collection of unrelated charts.', reconciliationGraph())}
      ${panel('Data integrity controls', 'Rules the UI and collection pipeline preserve as coverage expands.', `<div class="rule-list"><div><strong>Missing ≠ zero</strong><span>Absent disclosure or uncollected rows never become numeric zero.</span></div><div><strong>Raw labels retained</strong><span>Historical business-unit and vendor/person names stay traceable.</span></div><div><strong>Derived values reproducible</strong><span>Every metric points back to source IDs and transforms.</span></div><div><strong>Coverage visible</strong><span>Parser/source gaps appear in the product instead of disappearing.</span></div></div>`)}
    </div>
  </div>`;
}

function renderPeople() {
  const rows = filteredCompensationRows().filter(row => !state.peopleQuery || normalize(`${row.name} ${row.position} ${row.business_unit} ${row.entity}`).includes(normalize(state.peopleQuery)));
  const totals = rows.map(row => Number(row.total)).filter(Number.isFinite);
  const uniquePeople = new Set(rows.map(personScopeKey)).size;
  const largest = totals.length ? Math.max(...totals) : null;
  const signals = computeCompSignals(rows);
  const byYear = [...new Set(rows.map(row => row.fiscal_year_end))].sort((a, b) => a - b).map(year => ({
    year,
    total: rows.filter(row => row.fiscal_year_end === year).reduce((sum, row) => sum + Number(row.total || 0), 0),
    count: rows.filter(row => row.fiscal_year_end === year).length
  }));
  return `<div class="page-stack">
    <div class="notice"><strong>Disclosure limitation</strong><span>${escapeHtml(state.compensation.metadata?.note || 'This is a threshold-disclosure dataset.')} Absence from a year is not evidence of departure or zero compensation.</span></div>
    <div class="metrics-grid">
      ${metricCard('Verified disclosure rows', numberFmt.format(rows.length), filterDetail('checked-in source rows'), 'accent')}
      ${metricCard('People represented', numberFmt.format(uniquePeople), 'Entity-scoped disclosed people; not a workforce count', 'neutral')}
      ${metricCard('Largest filtered disclosure', compactMoney(largest), 'Largest row under the current filters', 'neutral')}
      ${metricCard('Review signals', numberFmt.format(signals.length), 'Screening prompts; not findings', signals.length ? 'warn' : 'good')}
    </div>
    <div class="split-grid wide-left">
      ${panel('Disclosure history', 'Totals below sum the configured $100k+ disclosure rows; they are not total municipal payroll.', compensationBars(byYear))}
      ${panel('Interpretation guide', 'What the source-defined fields can include.', `<div class="rule-list"><div><strong>Wages</strong><span>Can include regular pay, overtime and acting pay.</span></div><div><strong>Benefits / other</strong><span>Can include severance, vacation payout, allowances and other disclosed items.</span></div><div><strong>Threshold</strong><span>${money(state.compensation.metadata?.disclosure_threshold_cad)} annual disclosure floor in current metadata.</span></div></div>`)}
    </div>
    ${panel('Employee compensation explorer', 'Search within global fiscal-year and business-unit filters. Click a row for entity-scoped history and source evidence.', `<div class="local-toolbar"><label class="local-search"><span>⌕</span><input id="people-search" value="${escapeHtml(state.peopleQuery)}" placeholder="Search employee, role, unit or entity" /></label><span class="table-note">${numberFmt.format(rows.length)} rows</span></div>${compensationTable(rows)}`)}
  </div>`;
}

function compensationBars(items) {
  if (!items.length) return emptyState('No rows under the current filters', 'Reset the global filters to inspect the configured disclosures.');
  const max = Math.max(...items.map(item => item.total), 1);
  return `<div class="bar-chart">${items.map(item => `<div class="bar-row"><span>${item.year}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(3, item.total / max * 100)}%"></div></div><strong>${compactMoney(item.total)}</strong><small>${item.count} rows</small></div>`).join('')}</div>`;
}

function compensationTable(rows) {
  if (!rows.length) return emptyState('No matching compensation rows', 'This may reflect the current filter/search or threshold disclosure coverage.');
  const sorted = [...rows].sort((a, b) => Number(b.fiscal_year_end) - Number(a.fiscal_year_end) || Number(b.total) - Number(a.total));
  return `<div class="table-wrap"><table><thead><tr><th>Year</th><th>Employee</th><th>Business unit</th><th>Position</th><th class="numeric">Wages</th><th class="numeric">Benefits</th><th class="numeric">Total</th></tr></thead><tbody>${sorted.map(row => `<tr data-person-key="${escapeHtml(row.person_key)}" data-person-entity="${escapeHtml(row.entity || '')}" data-person-year="${row.fiscal_year_end}"><td>${row.fiscal_year_end}</td><td><strong>${escapeHtml(row.name)}</strong><small class="cell-sub">${escapeHtml(row.entity)}</small></td><td>${escapeHtml(row.business_unit || '—')}</td><td>${escapeHtml(row.position || '—')}</td><td class="numeric">${money(row.wages)}</td><td class="numeric">${money(row.benefits)}</td><td class="numeric"><strong>${money(row.total)}</strong></td></tr>`).join('')}</tbody></table></div>`;
}

function computeCompSignals(inputRows = filteredCompensationRows()) {
  const rows = inputRows.length ? inputRows : [];
  const grouped = new Map();
  for (const row of rows) {
    const scopeKey = personScopeKey(row);
    if (!grouped.has(scopeKey)) grouped.set(scopeKey, []);
    grouped.get(scopeKey).push(row);
  }
  const signals = [];
  for (const [scopeKey, group] of grouped) {
    const ordered = [...group].sort((a, b) => Number(a.fiscal_year_end) - Number(b.fiscal_year_end));
    const signalKey = scopeKey.replace(/[^a-z0-9_-]+/gi, '-');
    for (let i = 1; i < ordered.length; i++) {
      const prior = ordered[i - 1]; const current = ordered[i];
      if (Number(current.fiscal_year_end) - Number(prior.fiscal_year_end) === 1 && Number(prior.total) > 0) {
        const change = (Number(current.total) - Number(prior.total)) / Number(prior.total);
        if (Math.abs(change) >= 0.20) signals.push({
          id: `comp-change-${signalKey}-${current.fiscal_year_end}`,
          type: 'Year-over-year change',
          priority: Math.abs(change) >= 0.35 ? 'high' : 'review',
          score: Math.min(99, Math.round(Math.abs(change) * 100 + 50)),
          name: current.name,
          year: current.fiscal_year_end,
          source_id: current.source_id,
          detail: `Total disclosed compensation changed ${pct(change, true)} from ${money(prior.total)} to ${money(current.total)}.`,
          facts: [`Entity: ${current.entity}`, `Prior year: ${money(prior.total)}`, `Current year: ${money(current.total)}`, `Change: ${pct(change, true)}`],
          caveat: 'Compensation may change for overtime, acting pay, severance, vacation payout, allowances or other permitted source-defined components.'
        });
      }
      if (prior.position !== current.position || prior.business_unit !== current.business_unit) signals.push({
        id: `comp-role-${signalKey}-${current.fiscal_year_end}`,
        type: 'Role / unit change', priority: 'info', score: 35, name: current.name, year: current.fiscal_year_end, source_id: current.source_id,
        detail: `Disclosure label changed from ${prior.position || 'unknown role'} / ${prior.business_unit || 'unknown unit'} to ${current.position || 'unknown role'} / ${current.business_unit || 'unknown unit'}.`,
        facts: [`Entity: ${current.entity}`, `Prior: ${prior.position || 'unknown'} · ${prior.business_unit || 'unknown'}`, `Current: ${current.position || 'unknown'} · ${current.business_unit || 'unknown'}`],
        caveat: 'Organizational naming changes can occur without a substantive role change.'
      });
    }
    for (const row of ordered) {
      const total = Number(row.total); const benefits = Number(row.benefits);
      if (total > 0 && benefits / total >= 0.10) signals.push({
        id: `comp-benefit-${signalKey}-${row.fiscal_year_end}`,
        type: 'Benefits concentration', priority: 'review', score: Math.min(90, Math.round(50 + benefits / total * 100)), name: row.name, year: row.fiscal_year_end, source_id: row.source_id,
        detail: `Benefits were ${decimalFmt.format(benefits / total * 100)}% of disclosed total (${money(benefits)} of ${money(total)}).`,
        facts: [`Entity: ${row.entity}`, `Wages: ${money(row.wages)}`, `Benefits: ${money(row.benefits)}`, `Total: ${money(row.total)}`],
        caveat: 'The source definition can include retirement/severance, vacation payout, allowances and other permitted items.'
      });
    }
  }
  return signals.sort((a, b) => b.score - a.score || Number(b.year) - Number(a.year));
}

function bindViewEvents() {
  $$('#content [data-source-id]').forEach(element => element.addEventListener('click', () => showSource(element.dataset.sourceId)));
  $$('#content [data-domain]').forEach(element => element.addEventListener('click', () => showDomainCoverage(element.dataset.domain)));
  $$('#content [data-signal-id]').forEach(element => element.addEventListener('click', () => showSignal(element.dataset.signalId)));
  $$('#content [data-person-key]').forEach(element => element.addEventListener('click', () => showPerson(element.dataset.personKey, Number(element.dataset.personYear), element.dataset.personEntity)));
  const peopleSearch = $('#people-search'); if (peopleSearch) peopleSearch.addEventListener('input', event => { state.peopleQuery = event.target.value; render(); requestAnimationFrame(() => { const input = $('#people-search'); if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); } }); });
  const sourceSearch = $('#source-search'); if (sourceSearch) sourceSearch.addEventListener('input', event => { state.sourceQuery = event.target.value; render(); requestAnimationFrame(() => { const input = $('#source-search'); if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); } }); });
  const sourceCategory = $('#source-category'); if (sourceCategory) sourceCategory.addEventListener('change', event => { state.sourceCategory = event.target.value; render(); });
}

function showPerson(personKey, selectedYear, entity = null) {
  const history = compensationRows().filter(row => row.person_key === personKey && (!entity || row.entity === entity)).sort((a, b) => Number(a.fiscal_year_end) - Number(b.fiscal_year_end));
  if (!history.length) return;
  const selected = history.find(row => Number(row.fiscal_year_end) === Number(selectedYear)) || history[history.length - 1];
  const source = sourceById(selected.source_id);
  const max = Math.max(...history.map(row => Number(row.total || 0)), 1);
  const trend = `<div class="drawer-section"><h3>Available disclosure history</h3><div class="mini-history">${history.map(row => `<div><span>${row.fiscal_year_end}</span><div><i style="width:${Math.max(3, Number(row.total || 0) / max * 100)}%"></i></div><strong>${compactMoney(row.total)}</strong></div>`).join('')}</div><p class="drawer-note">Entity-scoped checked-in disclosure rows are shown. Missing years are not interpreted as zero.</p></div>`;
  openDrawer({ title: selected.name, eyebrow: 'COMPENSATION EVIDENCE', html: `${evidenceSteps([['Reporting entity', selected.entity], ['Fiscal year', selected.fiscal_year_end], ['Business unit', selected.business_unit], ['Position', selected.position], ['Wages', money(selected.wages)], ['Benefits / other', money(selected.benefits)], ['Total', money(selected.total)], ['Source ID', selected.source_id]])}${trend}${source ? sourceLink(source) : ''}` });
}

function runGlobalSearch(rawQuery) {
  const query = normalize(rawQuery);
  if (query.length < 2) { showEvidenceStandard(); return; }
  const people = compensationRows().filter(row => normalize(`${row.name} ${row.position} ${row.business_unit} ${row.entity}`).includes(query)).slice(0, 30);
  const sources = (state.sources.sources || []).filter(source => normalize(`${source.name} ${source.publisher} ${source.category} ${source.coverage}`).includes(query)).slice(0, 12);
  const signals = allSignals().filter(signal => normalize(`${signal.name} ${signal.type} ${signal.detail}`).includes(query)).slice(0, 12);
  const uniquePeople = [...new Map(people.map(row => [personScopeKey(row), row])).values()].slice(0, 12);
  const html = `<div class="drawer-section"><h3>People</h3>${uniquePeople.length ? `<div class="search-results">${uniquePeople.map(row => `<button type="button" data-search-person="${escapeHtml(row.person_key)}" data-search-entity="${escapeHtml(row.entity || '')}"><strong>${escapeHtml(row.name)}</strong><span>${escapeHtml(row.entity || '')} · ${escapeHtml(row.position || '')} · ${escapeHtml(row.business_unit || '')}</span></button>`).join('')}</div>` : '<p>No matching checked-in compensation names.</p>'}</div><div class="drawer-section"><h3>Sources</h3>${sources.length ? `<div class="search-results">${sources.map(source => `<button type="button" data-search-source="${escapeHtml(source.id)}"><strong>${escapeHtml(source.name)}</strong><span>${escapeHtml(source.category)} · ${escapeHtml(source.publisher)}</span></button>`).join('')}</div>` : '<p>No matching registered sources.</p>'}</div><div class="drawer-section"><h3>Signals</h3>${signals.length ? `<div class="search-results">${signals.map(signal => `<button type="button" data-search-signal="${escapeHtml(signal.id)}"><strong>${escapeHtml(signal.name)}</strong><span>${escapeHtml(signal.type)} · ${escapeHtml(signal.detail)}</span></button>`).join('')}</div>` : '<p>No matching review signals.</p>'}</div>`;
  openDrawer({ title: `Search: ${rawQuery.trim()}`, eyebrow: 'GLOBAL SEARCH', html });
  $$('#drawer-body [data-search-person]').forEach(button => button.addEventListener('click', () => showPerson(button.dataset.searchPerson, null, button.dataset.searchEntity)));
  $$('#drawer-body [data-search-source]').forEach(button => button.addEventListener('click', () => showSource(button.dataset.searchSource)));
  $$('#drawer-body [data-search-signal]').forEach(button => button.addEventListener('click', () => showSignal(button.dataset.searchSignal)));
}
