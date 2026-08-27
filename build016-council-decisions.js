/* Build 016 — approved-minutes Council decision evidence.
 * Additive presentation over council_decisions.json. No agenda recommendation is
 * promoted to an approval and no dollar mention is treated as a payment.
 */

state.build016CouncilDecisions = { status: 'loading', data: null, error: null };
state.build016CouncilSources = { status: 'loading', data: null, error: null };
state.build016DecisionYear = 'all';
state.build016DecisionStatus = 'all';
state.build016DecisionFiscalOnly = true;
state.build016DecisionQuery = '';

async function b16FetchJson(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

Promise.allSettled([
  b16FetchJson('./data/generated/council_decisions.json'),
  b16FetchJson('./data/council_decision_sources.json')
]).then(([decisionResult, sourceResult]) => {
  state.build016CouncilDecisions = decisionResult.status === 'fulfilled'
    ? { status: 'ready', data: decisionResult.value, error: null }
    : { status: 'error', data: null, error: decisionResult.reason?.message || 'Council decision artifact failed to load' };
  state.build016CouncilSources = sourceResult.status === 'fulfilled'
    ? { status: 'ready', data: sourceResult.value, error: null }
    : { status: 'error', data: null, error: sourceResult.reason?.message || 'Council decision source registry failed to load' };
  if (typeof render === 'function') render();
});

function b16Data() { return state.build016CouncilDecisions?.data || null; }
function b16Meta() { return b16Data()?.metadata || {}; }
function b16Rows() { return Array.isArray(b16Data()?.records) ? b16Data().records : []; }
function b16LegacySources() { return Array.isArray(state.build016CouncilSources?.data?.legacy_sources) ? state.build016CouncilSources.data.legacy_sources : []; }
function b16Year(row) { return String(row?.meeting_date || '').slice(0, 4); }
function b16ResultLabel(value) { return String(value || 'other').replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase()); }
function b16ResultTone(value) {
  return value === 'passed_unanimously' || value === 'passed' ? 'good'
    : value === 'defeated' ? 'warn'
      : value === 'tied' ? 'warn'
        : 'muted';
}
function b16MoneyText(row) {
  const mentions = Array.isArray(row?.money_mentions) ? row.money_mentions : [];
  return mentions.map(item => money(item.amount_cad)).join(' · ');
}
function b16RefText(row) {
  const refs = [
    ...(row?.procurement_refs || []).map(value => `Procurement ${value}`),
    ...(row?.case_refs || []).map(value => `Case ${value}`),
    ...(row?.capital_account_refs || []).map(value => `Project/account ${value}`)
  ];
  return [...new Set(refs)].join(' · ');
}
function b16Excerpt(value, max = 280) {
  const text = String(value || '');
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function b16FilteredRows() {
  const query = normalize(state.build016DecisionQuery);
  return b16Rows().filter(row =>
    (state.build016DecisionYear === 'all' || b16Year(row) === state.build016DecisionYear) &&
    (state.build016DecisionStatus === 'all' || row.decision_status === state.build016DecisionStatus) &&
    (!state.build016DecisionFiscalOnly || row.fiscal_relevant === true) &&
    (!query || normalize(`${row.item_ref || ''} ${row.item_title || ''} ${row.motion_text || ''} ${row.mover || ''} ${row.seconder || ''} ${b16MoneyText(row)} ${b16RefText(row)}`).includes(query))
  );
}

function b16DecisionTableHtml() {
  const all = b16Rows();
  const rows = b16FilteredRows();
  const years = [...new Set(all.map(b16Year).filter(Boolean))].sort((a, b) => b.localeCompare(a));
  const statuses = [...new Set(all.map(row => row.decision_status).filter(Boolean))].sort();
  const visible = [...rows].sort((a, b) => String(b.meeting_date || '').localeCompare(String(a.meeting_date || '')) || String(a.item_ref || '').localeCompare(String(b.item_ref || ''))).slice(0, 180);
  return `<div class="b16-decision-toolbar">
    <label class="local-search"><span>⌕</span><input id="b16-decision-search" value="${escapeHtml(state.build016DecisionQuery)}" placeholder="Search motion, item, mover or exact reference" /></label>
    <select id="b16-decision-year"><option value="all">All decision years</option>${years.map(year => `<option value="${escapeHtml(year)}" ${year === state.build016DecisionYear ? 'selected' : ''}>${escapeHtml(year)}</option>`).join('')}</select>
    <select id="b16-decision-status"><option value="all">All motion results</option>${statuses.map(status => `<option value="${escapeHtml(status)}" ${status === state.build016DecisionStatus ? 'selected' : ''}>${escapeHtml(b16ResultLabel(status))}</option>`).join('')}</select>
    <label class="build006-check"><input id="b16-decision-fiscal" type="checkbox" ${state.build016DecisionFiscalOnly ? 'checked' : ''}/><span>Fiscal-relevant only</span></label>
    ${visibleLimitNote(rows.length, visible.length, 'decisions')}
  </div>
  <div class="table-wrap"><table><thead><tr><th>Date</th><th>Item</th><th>Outcome</th><th>Motion adopted / considered</th><th class="numeric">Dollar mentions</th></tr></thead><tbody>${visible.map(row => `<tr data-build016-decision="${escapeHtml(row.decision_id)}">
    <td><strong>${escapeHtml(row.meeting_date || '—')}</strong><small class="cell-sub">${row.coverage_layer === 'legacy_seed_incomplete' ? 'legacy seed' : 'eSCRIBE minutes'}</small></td>
    <td><strong>${escapeHtml(row.item_ref || '—')}</strong><small class="cell-sub">${escapeHtml(row.item_title || 'Council motion')}</small></td>
    <td>${badge(b16ResultLabel(row.decision_status), b16ResultTone(row.decision_status))}</td>
    <td class="b16-motion-cell"><strong>${escapeHtml(row.mover || 'Mover not parsed')} · ${escapeHtml(row.seconder ? `seconded by ${row.seconder}` : 'seconder not parsed')}</strong><span>${escapeHtml(b16Excerpt(row.motion_text))}</span>${b16RefText(row) ? `<small>${escapeHtml(b16RefText(row))}</small>` : ''}</td>
    <td class="numeric">${(row.money_mentions || []).length ? `<div class="b16-money-list">${(row.money_mentions || []).map(item => `<span class="b16-money-token">${escapeHtml(money(item.amount_cad))}</span>`).join('')}</div>` : '—'}</td>
  </tr>`).join('')}</tbody></table></div>`;
}

function b16DecisionPanelHtml() {
  const status = state.build016CouncilDecisions?.status;
  if (status === 'loading') return panel('Council decision evidence', 'Loading approved-minutes motion outcomes.', emptyState('Loading Council decisions', 'Reading the Build 016 checked artifact.'), 'b16-decision-panel');
  if (status !== 'ready') return panel('Council decision evidence', 'Approved-minutes extraction is unavailable.', emptyState('Decision artifact unavailable', state.build016CouncilDecisions?.error || 'Unknown load error'), 'b16-decision-panel');
  const meta = b16Meta();
  const rows = b16Rows();
  const passed = rows.filter(row => row.motion_passed).length;
  const fiscal = rows.filter(row => row.fiscal_relevant).length;
  const moneyRows = rows.filter(row => (row.money_mentions || []).length).length;
  return `<section class="panel b16-decision-panel"><header class="panel-header"><div><h2>Approved-minutes decision evidence</h2><p>Motion text and recorded outcomes are extracted from official approved minutes. This closes the gap between an agenda recommendation and what Council actually adopted or defeated.</p></div></header><div class="panel-body">
    <div class="notice"><strong>Decision boundary</strong><span>A passed motion is evidence that Council adopted that motion. A dollar amount mentioned in the motion is not evidence that the amount was invoiced, paid, fully spent, or the final cost of a project or contract.</span></div>
    <div class="metrics-grid compact">
      ${metricCard('Motion outcomes', numberFmt.format(rows.length), `${numberFmt.format(meta.modern_decision_records || 0)} modern · ${numberFmt.format(meta.legacy_decision_records || 0)} legacy seed`, 'accent')}
      ${metricCard('Passed motions', numberFmt.format(passed), 'Passed / passed unanimously in approved minutes', 'good')}
      ${metricCard('Fiscal-relevant motions', numberFmt.format(fiscal), 'Keyword/dollar screening for review, not a finding', 'neutral')}
      ${metricCard('Motions with dollar text', numberFmt.format(moneyRows), 'Dollar mentions retained as source text only', 'neutral')}
    </div>
    ${b16DecisionTableHtml()}
  </div></section>`;
}

function b16SourceCoverageHtml() {
  if (state.build016CouncilDecisions?.status !== 'ready') return '';
  const meta = b16Meta();
  const legacy = b16LegacySources();
  return `<section class="panel b16-source-coverage"><header class="panel-header"><div><h2>Build 016 Council decision coverage</h2><p>Approved-minutes sources used for semantic motion/result extraction.</p></div></header><div class="panel-body">
    <div class="b16-source-summary">
      <div><strong>${numberFmt.format(meta.modern_meetings_with_posted_minutes || 0)}</strong><span>modern eSCRIBE Regional Council meetings with posted minutes</span></div>
      <div><strong>${numberFmt.format(meta.modern_decision_records || 0)}</strong><span>modern parsed motion outcomes</span></div>
      <div><strong>${numberFmt.format(meta.legacy_seed_meetings || legacy.length)}</strong><span>pre-2024 approved-minutes seed meetings</span></div>
      <div><strong>${numberFmt.format(meta.legacy_decision_records || 0)}</strong><span>legacy-seed parsed outcomes</span></div>
    </div>
    <div class="notice"><strong>Historical coverage boundary</strong><span>The eSCRIBE posted-minutes window is processed from the checked Council calendar. The pre-2024 records below are deliberately an incomplete seed, not a complete historical Council archive.</span></div>
    <div class="source-mini-list">${legacy.map(source => `<a class="build006-doc-link" href="${escapeHtml(safeUrl(source.minutes_url) || '#')}" target="_blank" rel="noreferrer"><span><strong>${escapeHtml(source.meeting_date)} · ${escapeHtml(source.meeting_name || 'Halifax Regional Council')}</strong><small>${escapeHtml(source.coverage_status || 'legacy seed')} · approved minutes PDF</small></span><span>↗</span></a>`).join('')}</div>
  </div></section>`;
}

function b16ShowDecision(id) {
  const row = b16Rows().find(item => item.decision_id === id);
  if (!row) return;
  const url = safeUrl(row.source_url);
  const moneyText = b16MoneyText(row) || 'None parsed';
  const refs = b16RefText(row) || 'None parsed';
  openDrawer({
    title: row.item_title || row.item_ref || 'Council motion',
    eyebrow: 'APPROVED MINUTES · COUNCIL DECISION',
    html: `${evidenceSteps([
      ['Meeting date', row.meeting_date],
      ['Agenda item', row.item_ref || 'Not parsed'],
      ['Recorded outcome', b16ResultLabel(row.decision_status)],
      ['Motion passed?', row.motion_passed ? 'Yes' : 'No'],
      ['Mover', row.mover || '—'],
      ['Seconder', row.seconder || '—'],
      ['Dollar mentions', moneyText],
      ['Exact reference tokens', refs],
      ['Coverage layer', row.coverage_layer === 'legacy_seed_incomplete' ? 'Pre-2024 legacy seed — incomplete historical coverage' : 'Modern eSCRIBE posted-minutes window'],
      ['Source locator', row.source_locator],
      ['Source ID', row.source_id]
    ])}<div class="drawer-section"><h3>Recorded motion text</h3><p>${escapeHtml(row.motion_text)}</p></div><div class="drawer-callout"><strong>Interpretation boundary</strong><p>This record establishes the motion and outcome printed in approved minutes. Any dollar amount is a mention in the adopted/considered motion, not payment evidence, an invoice, final paid value, final project cost, or proof of policy compliance.</p></div>${url ? `<div class="drawer-section"><h3>Official approved minutes</h3><div class="drawer-source-list"><a class="source-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Open source minutes ↗</a></div></div>` : ''}`
  });
}

function b16EnhanceCouncil() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b16-decision-panel')) return;
  const metrics = stack.querySelector('.metrics-grid');
  if (metrics) metrics.insertAdjacentHTML('afterend', b16DecisionPanelHtml());
  else stack.insertAdjacentHTML('afterbegin', b16DecisionPanelHtml());
}
function b16EnhanceSources() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b16-source-coverage')) return;
  stack.insertAdjacentHTML('beforeend', b16SourceCoverageHtml());
}
function b16BindEvents() {
  $$('#content [data-build016-decision]').forEach(element => element.addEventListener('click', () => b16ShowDecision(element.dataset.build016Decision)));
  const search = $('#b16-decision-search');
  if (search) search.addEventListener('input', event => { state.build016DecisionQuery = event.target.value; render(); });
  const year = $('#b16-decision-year');
  if (year) year.addEventListener('change', event => { state.build016DecisionYear = event.target.value; render(); });
  const status = $('#b16-decision-status');
  if (status) status.addEventListener('change', event => { state.build016DecisionStatus = event.target.value; render(); });
  const fiscal = $('#b16-decision-fiscal');
  if (fiscal) fiscal.addEventListener('change', event => { state.build016DecisionFiscalOnly = event.target.checked; render(); });
}

const b16RenderBase = render;
render = function renderBuild016() {
  b16RenderBase();
  if (state.view === 'council') b16EnhanceCouncil();
  if (state.view === 'sources') b16EnhanceSources();
  b16BindEvents();
};
