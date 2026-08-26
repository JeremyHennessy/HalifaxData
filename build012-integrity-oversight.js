/* Build 012 — Integrity / oversight evidence layer.
 * Loaded after Build 011. This layer keeps official oversight findings separate
 * from derived anomaly scores and does not alter the approved app shell.
 */

state.build012Integrity = { status: 'loading', data: null, error: null };
state.build012Sources = { status: 'loading', data: null, error: null };
let build012SourcesMerged = false;

async function b12FetchJson(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

Promise.allSettled([
  b12FetchJson('./data/generated/integrity_oversight.json'),
  b12FetchJson('./data/integrity_sources.json')
]).then(([integrityResult, sourceResult]) => {
  state.build012Integrity = integrityResult.status === 'fulfilled'
    ? { status: 'ready', data: integrityResult.value, error: null }
    : { status: 'error', data: null, error: integrityResult.reason?.message || 'Integrity artifact failed to load' };
  state.build012Sources = sourceResult.status === 'fulfilled'
    ? { status: 'ready', data: sourceResult.value, error: null }
    : { status: 'error', data: null, error: sourceResult.reason?.message || 'Integrity source registry failed to load' };
  b12MergeSources();
  if (typeof render === 'function') render();
});

const b12ExactMoneyFmt = new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 2, maximumFractionDigits: 2 });
function b12ExactMoney(value) { return value == null || !Number.isFinite(Number(value)) ? '—' : b12ExactMoneyFmt.format(Number(value)); }
function b12SignedExactMoney(value) { const n = Number(value); return Number.isFinite(n) ? `${n >= 0 ? '+' : '-'}${b12ExactMoneyFmt.format(Math.abs(n))}` : '—'; }

function b12Data() { return state.build012Integrity?.data || null; }
function b12Meta() { return b12Data()?.metadata || {}; }
function b12AuthorityFindings() { return Array.isArray(b12Data()?.authority_findings) ? b12Data().authority_findings : []; }
function b12Amendments() { return Array.isArray(b12Data()?.contract_amendments) ? b12Data().contract_amendments : []; }
function b12PlannedAudits() { return Array.isArray(b12Data()?.planned_audits) ? b12Data().planned_audits : []; }
function b12Taxonomy() { return Array.isArray(b12Data()?.status_taxonomy) ? b12Data().status_taxonomy : []; }
function b12SupplementSources() { return Array.isArray(state.build012Sources?.data?.sources) ? state.build012Sources.data.sources : []; }
function b12SourcesMergedStatus() { return build012SourcesMerged; }

function b12MergeSources() {
  if (build012SourcesMerged || state.build012Sources?.status !== 'ready' || !Array.isArray(state.sources?.sources)) return false;
  const existing = new Set(state.sources.sources.map(source => source.id));
  for (const source of b12SupplementSources()) {
    if (!existing.has(source.id)) {
      state.sources.sources.push(source);
      existing.add(source.id);
    }
  }
  const researched = state.build012Sources?.data?.metadata?.last_researched;
  if (researched && (!state.sources.metadata?.last_researched || researched > state.sources.metadata.last_researched)) {
    state.sources.metadata = { ...(state.sources.metadata || {}), last_researched: researched };
  }
  build012SourcesMerged = true;
  const snapshot = $('#snapshot-label');
  if (snapshot) snapshot.textContent = `Sources researched ${state.sources.metadata?.last_researched || 'date unknown'}`;
  return true;
}

function b12SourceById(id) {
  return sourceById(id) || b12SupplementSources().find(source => source.id === id) || null;
}

function b12StatusTone(status) {
  return status === 'policy_noncompliance' ? 'bad'
    : status === 'control_weakness' ? 'warn'
      : status === 'referred_for_investigation' ? 'warn'
        : status === 'substantiated_wrongdoing' ? 'bad'
          : 'info';
}

function b12StatusLabel(status) {
  return b12Taxonomy().find(item => item.id === status)?.label || String(status || 'Unclassified').replace(/_/g, ' ');
}

function b12StatusCounts() {
  const counts = Object.fromEntries(b12Taxonomy().map(item => [item.id, 0]));
  for (const item of [...b12AuthorityFindings(), ...b12Amendments()]) {
    counts[item.status] = (counts[item.status] || 0) + 1;
  }
  return counts;
}

function b12FactLabel(value) {
  return String(value || '').replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
}

function b12FactValue(key, value) {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (value == null) return '—';
  if (/pct|percent/i.test(key) && Number.isFinite(Number(value))) return `${decimalFmt.format(Number(value))}%`;
  if (/amount|overstatement|estimate/i.test(key) && Number.isFinite(Number(value))) return money(Number(value));
  return String(value);
}

function b12AuthorityCard(item, compact = false) {
  const amount = item.amount == null ? '' : `<div class="b12-card-amount">${money(item.amount)}</div>`;
  return `<button type="button" class="b12-authority-card ${compact ? 'compact' : ''}" data-build012-finding="${escapeHtml(item.id)}">
    <div class="b12-authority-top"><span>${badge(b12StatusLabel(item.status), b12StatusTone(item.status))}${badge(item.group, 'muted')}</span></div>
    <h3>${escapeHtml(item.title)}</h3>
    <p>${escapeHtml(item.detail)}</p>
    ${amount}
    <small>${escapeHtml(item.authority || 'Official oversight authority')}</small>
  </button>`;
}

function b12StatusLadderHtml() {
  const counts = b12StatusCounts();
  return `<div class="b12-status-ladder">${b12Taxonomy().map(item => `<article class="b12-status-step" data-status="${escapeHtml(item.id)}">
    <div><span>${escapeHtml(String(item.rank))}</span><strong>${escapeHtml(item.label)}</strong></div>
    <b>${numberFmt.format(counts[item.id] || 0)}</b>
    <p>${escapeHtml(item.definition)}</p>
  </article>`).join('')}</div>`;
}

function b12AuthorityPanelHtml(limit = null) {
  const findings = limit == null ? b12AuthorityFindings() : b12AuthorityFindings().slice(0, limit);
  if (!findings.length) return emptyState('No authority-backed findings loaded', 'The Build 012 authority artifact is not available or contains no findings.');
  return `<div class="b12-authority-grid">${findings.map(item => b12AuthorityCard(item)).join('')}</div>`;
}

function b12PlannedAuditsHtml() {
  const audits = b12PlannedAudits();
  if (!audits.length) return emptyState('No planned audits in this artifact', 'No future Auditor General work is currently registered.');
  return `<div class="rule-list">${audits.map(item => `<div><strong>${escapeHtml(item.subject)}</strong><span>${escapeHtml(item.business_unit)} · ${escapeHtml(item.note)}</span></div>`).join('')}</div>`;
}

function b12OverviewSection() {
  const counts = b12StatusCounts();
  return `<section class="panel b12-overview-authority"><header class="panel-header"><div><h2>Authority-backed oversight</h2><p>Official oversight conclusions are shown separately from anomaly scores. They outrank statistical screening for review purposes, but they are not automatically criminal findings.</p></div></header><div class="panel-body">
    <div class="b12-inline-summary">
      <div><strong>${numberFmt.format(counts.policy_noncompliance || 0)}</strong><span>policy-noncompliance findings</span></div>
      <div><strong>${numberFmt.format(counts.control_weakness || 0)}</strong><span>control-weakness findings</span></div>
      <div><strong>${numberFmt.format(counts.referred_for_investigation || 0)}</strong><span>official referral records in this artifact</span></div>
      <div><strong>${numberFmt.format(counts.substantiated_wrongdoing || 0)}</strong><span>substantiated-wrongdoing findings</span></div>
    </div>
    ${b12AuthorityPanelHtml(6)}
  </div></section>`;
}

function b12InvestigationsSection() {
  const meta = b12Meta();
  return `<section class="b12-investigation-evidence page-stack">
    ${panel('Evidence status ladder', 'The app now distinguishes a derived anomaly from an independent control finding, policy noncompliance, formal referral and substantiated wrongdoing. Empty higher tiers remain visible rather than being inferred.', b12StatusLadderHtml())}
    ${panel('Authority-backed findings', `${numberFmt.format(meta.authority_finding_records || 0)} records extracted from HRM Auditor General reports. These findings are not assigned anomaly scores.`, b12AuthorityPanelHtml())}
    <div class="split-grid wide-left">
      ${panel('Planned independent audits', 'Future oversight work registered from the Auditor General’s 2026/27 priorities. A planned audit is context only until findings are issued.', b12PlannedAuditsHtml())}
      ${panel('Integrity interpretation boundary', 'Authority and anomaly layers remain deliberately separate.', `<div class="rule-list"><div><strong>Anomaly</strong><span>Pattern says inspect the underlying evidence.</span></div><div><strong>Control weakness</strong><span>Independent authority found a process or documentation weakness.</span></div><div><strong>Policy noncompliance</strong><span>Independent authority concluded a policy requirement was not followed.</span></div><div><strong>Referral</strong><span>Must be explicitly sourced; this artifact contains no referral record.</span></div><div><strong>Substantiated wrongdoing</strong><span>Never inferred from scores, amendments, political contributions or policy noncompliance.</span></div></div>`)}
    </div>
  </section>`;
}

function b12AmendmentTableHtml() {
  const rows = b12Amendments();
  if (!rows.length) return emptyState('No contract-amendment examples loaded', 'The Build 012 amendment artifact is unavailable or empty.');
  return `<div class="table-wrap"><table class="b12-amendment-table"><thead><tr><th>Supplier / contract</th><th>Context</th><th class="numeric">Original</th><th class="numeric">Cumulative change</th><th class="numeric">New value</th></tr></thead><tbody>${rows.map(row => `<tr data-build012-amendment="${escapeHtml(row.id)}">
    <td><strong>${escapeHtml(row.vendor)}</strong><small class="cell-sub">${escapeHtml(row.contract ? `Contract ${row.contract}` : `PO ${row.po || '—'}`)}</small></td>
    <td><strong>${escapeHtml(row.title)}${row.source_arithmetic_consistent === false ? ` ${badge('source arithmetic mismatch', 'warn')}` : ''}</strong><small class="cell-sub">${escapeHtml(row.context)}</small></td>
    <td class="numeric">${money(row.original_contract_value)}</td>
    <td class="numeric"><strong>${money(row.cumulative_increase)}</strong><small class="cell-sub">${decimalFmt.format(row.cumulative_increase_pct)}%</small></td>
    <td class="numeric">${money(row.new_contract_value)}</td>
  </tr>`).join('')}</tbody></table></div>`;
}

function b12AmendmentSection() {
  const rows = b12Amendments();
  const largestPct = rows.length ? Math.max(...rows.map(row => Number(row.cumulative_increase_pct || 0))) : 0;
  const largestDollar = rows.length ? Math.max(...rows.map(row => Number(row.cumulative_increase || 0))) : 0;
  return `<section class="panel b12-amendment-section"><header class="panel-header"><div><h2>Contract amendment oversight</h2><p>Selected source-backed CAO amendment records are shown as amendment-review evidence, not as a complete contract ledger and not as findings of improper spending.</p></div></header><div class="panel-body">
    <div class="b12-inline-summary">
      <div><strong>${numberFmt.format(rows.length)}</strong><span>selected published amendment records</span></div>
      <div><strong>${decimalFmt.format(largestPct)}%</strong><span>largest cumulative percentage in this seed</span></div>
      <div><strong>${compactMoney(largestDollar)}</strong><span>largest cumulative dollar increase in this seed</span></div>
      <div><strong>Incomplete denominator</strong><span>do not infer whole-procurement rates</span></div>
    </div>
    ${b12AmendmentTableHtml()}
  </div></section>`;
}

function b12SourcesSection() {
  const sources = b12SupplementSources();
  const categories = new Map();
  for (const source of sources) categories.set(source.category, (categories.get(source.category) || 0) + 1);
  const meta = b12Meta();
  return `<section class="panel b12-source-coverage"><header class="panel-header"><div><h2>Integrity source coverage</h2><p>Build 012 adds official oversight, contract-amendment and campaign-finance source definitions to the existing registry at runtime without changing prior source semantics.</p></div></header><div class="panel-body">
    <div class="b12-source-stats">${[...categories.entries()].map(([category, count]) => `<div><strong>${numberFmt.format(count)}</strong><span>${escapeHtml(category)}</span></div>`).join('')}<div><strong>${numberFmt.format(meta.campaign_relationship_records || 0)}</strong><span>campaign-to-vendor relationships asserted</span></div></div>
    <div class="notice b12-campaign-boundary"><strong>Campaign-finance boundary</strong><span>Campaign disclosures are registered as relationship evidence only. A contribution or name match does not imply favoritism, conflict, corruption or improper procurement.</span></div>
    <div class="b12-source-list">${sources.map(source => `<div><strong>${escapeHtml(source.name)}</strong><span>${escapeHtml(source.coverage)}</span>${badge(source.status, sourceStatusTone(source.status))}</div>`).join('')}</div>
  </div></section>`;
}

function b12FindFinding(id) { return b12AuthorityFindings().find(item => item.id === id) || null; }
function b12FindAmendment(id) { return b12Amendments().find(item => item.id === id) || null; }

function b12SourceLinksHtml(sourceId) {
  const source = b12SourceById(sourceId);
  const url = safeUrl(source?.url);
  return source && url ? `<div class="drawer-section"><h3>Official source record</h3><div class="drawer-source-list"><a class="source-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(source.name)} ↗</a></div></div>` : '';
}

function b12ShowFinding(id) {
  const item = b12FindFinding(id);
  if (!item) return;
  const factRows = Object.entries(item.facts || {}).map(([key, value]) => [b12FactLabel(key), b12FactValue(key, value)]);
  openDrawer({
    title: item.title,
    eyebrow: 'AUTHORITY FINDING',
    html: `${evidenceSteps([
      ['Evidence status', b12StatusLabel(item.status)],
      ['Authority', item.authority],
      ['Audit / finding group', item.group],
      ['Amount semantics', b12FactLabel(item.amount_semantics)],
      ['Amount', item.amount == null ? '—' : money(item.amount)],
      ...(item.approximate_amended_value == null ? [] : [['Approximate amended value', `${money(item.approximate_amended_value)} (${b12FactLabel(item.approximate_amended_value_semantics)})`]]),
      ['Source locator', item.source_locator],
      ...factRows
    ])}<div class="drawer-section"><h3>Authority summary</h3><p>${escapeHtml(item.detail)}</p></div><div class="drawer-callout"><strong>Interpretation boundary</strong><p>${escapeHtml(item.caveat)}</p></div>${b12SourceLinksHtml(item.source_id)}`
  });
}

function b12ShowAmendment(id) {
  const row = b12FindAmendment(id);
  if (!row) return;
  openDrawer({
    title: row.title,
    eyebrow: 'CONTRACT AMENDMENT REVIEW',
    html: `${evidenceSteps([
      ['Evidence status', b12StatusLabel(row.status)],
      ['Supplier', row.vendor],
      ['Contract', row.contract || '—'],
      ['Purchase order', row.po || '—'],
      ['Original value', money(row.original_contract_value)],
      ['Cumulative increase', money(row.cumulative_increase)],
      ['Cumulative increase %', `${decimalFmt.format(row.cumulative_increase_pct)}%`],
      ['Published new value', money(row.new_contract_value)],
      ['Derived original + cumulative increase', money(row.derived_new_contract_value)],
      ['Published arithmetic delta', b12SignedExactMoney(row.source_arithmetic_delta)],
      ['Source arithmetic consistent', row.source_arithmetic_consistent ? 'Yes' : 'No — published values retained'],
      ['Change requested in source report', money(row.request_in_report)],
      ['Source locator', row.source_locator]
    ])}<div class="drawer-section"><h3>Published context</h3><p>${escapeHtml(row.context)}</p></div><div class="drawer-callout"><strong>Interpretation boundary</strong><p>${escapeHtml(row.caveat)}</p></div>${b12SourceLinksHtml(row.source_id)}`
  });
}

function b12BindEvents() {
  $$('#content [data-build012-finding]').forEach(element => element.addEventListener('click', () => b12ShowFinding(element.dataset.build012Finding)));
  $$('#content [data-build012-amendment]').forEach(element => element.addEventListener('click', () => b12ShowAmendment(element.dataset.build012Amendment)));
}

function b12EnhanceOverview() {
  if (state.build012Integrity?.status !== 'ready') return;
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b12-overview-authority')) return;
  const metrics = stack.querySelector('.metrics-grid');
  if (metrics) metrics.insertAdjacentHTML('afterend', b12OverviewSection());
  else stack.insertAdjacentHTML('afterbegin', b12OverviewSection());
}

function b12EnhanceInvestigations() {
  if (state.build012Integrity?.status !== 'ready') return;
  const stack = $('#content .b8-investigations-page');
  if (!stack || stack.querySelector('.b12-investigation-evidence')) return;
  const metrics = stack.querySelector('.metrics-grid');
  if (metrics) metrics.insertAdjacentHTML('afterend', b12InvestigationsSection());
  else stack.insertAdjacentHTML('afterbegin', b12InvestigationsSection());
}

function b12EnhanceVendors() {
  if (state.build012Integrity?.status !== 'ready') return;
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b12-amendment-section')) return;
  const anchor = stack.querySelector('.b11-procurement') || stack.querySelector('.b8-procurement-analysis') || stack.querySelector('.metrics-grid');
  if (anchor) anchor.insertAdjacentHTML('afterend', b12AmendmentSection());
  else stack.insertAdjacentHTML('afterbegin', b12AmendmentSection());
}

function b12EnhanceSources() {
  if (state.build012Sources?.status !== 'ready') return;
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b12-source-coverage')) return;
  const metrics = stack.querySelector('.metrics-grid');
  if (metrics) metrics.insertAdjacentHTML('afterend', b12SourcesSection());
  else stack.insertAdjacentHTML('afterbegin', b12SourcesSection());
}

const b12RenderBase = render;
render = function renderBuild012() {
  b12MergeSources();
  b12RenderBase();
  if (state.view === 'overview') b12EnhanceOverview();
  if (state.view === 'signals') b12EnhanceInvestigations();
  if (state.view === 'vendors') b12EnhanceVendors();
  if (state.view === 'sources') b12EnhanceSources();
  b12BindEvents();
};
