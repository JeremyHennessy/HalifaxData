/* Build 019 — deterministic lifecycle investigations.
 * Additive over the proven Build 008 investigations page. The existing investigation
 * models remain intact below this source-backed lifecycle queue.
 */

state.build019LifecycleInvestigations = { status: 'loading', data: null, error: null };
state.build019LifecyclePriority = 'attention';
state.build019LifecycleTrack = 'all';

fetch('./data/generated/lifecycle_investigations.json', { cache: 'no-store' })
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(data => {
    state.build019LifecycleInvestigations = { status: 'ready', data, error: null };
    if (typeof render === 'function' && state.compensation && state.sources) render();
  })
  .catch(error => {
    state.build019LifecycleInvestigations = { status: 'error', data: null, error: error.message };
    if (typeof render === 'function' && state.compensation && state.sources) render();
  });

function b19InvestigationsData() { return state.build019LifecycleInvestigations?.data || null; }
function b19InvestigationRows() { return Array.isArray(b19InvestigationsData()?.investigations) ? b19InvestigationsData().investigations : []; }
function b19InvestigationSummary() { return b19InvestigationsData()?.summary || {}; }
function b19ReasonLabel(value) {
  const labels = {
    capital_account_linked_to_procurement_award_evidence: 'capital ↔ award',
    multiple_procurement_references_linked_to_same_capital_component: 'multiple procurement refs',
    approved_council_motion_in_lifecycle_evidence: 'Council motion',
    procurement_reference_linked_to_public_cao_amendment_evidence: 'procurement ↔ amendment',
    multiple_purchase_orders_linked_to_same_procurement_reference: 'multiple POs'
  };
  return labels[value] || value.replace(/_/g, ' ');
}
function b19PriorityLabel(value) {
  return value === 'priority_review' ? 'priority review' : value === 'review' ? 'review' : 'context';
}
function b19PriorityTone(value) { return value === 'priority_review' ? 'warn' : value === 'review' ? 'info' : 'muted'; }
function b19Track(row) { return row.capital_project_accounts?.length ? 'capital_procurement' : 'procurement_amendment'; }
function b19PriorityMatches(row) {
  if (state.build019LifecyclePriority === 'all') return true;
  if (state.build019LifecyclePriority === 'attention') return row.priority === 'priority_review' || row.priority === 'review';
  return row.priority === state.build019LifecyclePriority;
}
function b19FilteredInvestigations() {
  return b19InvestigationRows().filter(row =>
    b19PriorityMatches(row) &&
    (state.build019LifecycleTrack === 'all' || b19Track(row) === state.build019LifecycleTrack)
  );
}
function b19InvestigationDetail(row) {
  const parts = [];
  if (row.capital_project_accounts?.length) parts.push(`capital ${row.capital_project_accounts.join(', ')}`);
  if (row.procurement_references?.length) parts.push(`procurement ${row.procurement_references.join(', ')}`);
  if (row.purchase_orders?.length) parts.push(`PO ${row.purchase_orders.join(', ')}`);
  return parts.join(' · ');
}
function b19InvestigationCard(row) {
  const reasonBadges = (row.review_reasons || []).slice(0, 3).map(reason => badge(b19ReasonLabel(reason), 'muted')).join('');
  return `<button type="button" class="b8-investigation-card" data-build019-investigation-id="${escapeHtml(row.investigation_id)}">
    <div class="b8-investigation-top"><span>${badge(b19Track(row) === 'capital_procurement' ? 'capital lifecycle' : 'amendment lifecycle', 'muted')}${badge(b19PriorityLabel(row.priority), b19PriorityTone(row.priority))}</span><strong>${numberFmt.format(row.review_priority_score)}</strong></div>
    <h3>${escapeHtml(row.title)}</h3>
    <p>${escapeHtml(b19InvestigationDetail(row))}</p>
    <div class="b8-materiality">${numberFmt.format(row.evidence_record_count || 0)} evidence records · ${numberFmt.format((row.domains || []).length)} evidence domains</div>
    <div class="b8-investigation-top" style="margin-top:7px"><span>${reasonBadges}</span></div>
    <small>Evidence-depth review score · not misconduct probability</small>
  </button>`;
}
function b19InvestigationPanel() {
  if (state.build019LifecycleInvestigations?.status === 'loading') {
    return panel('Deterministic lifecycle investigations', 'Build 019 exact-identifier reconciliation.', '<div class="loading-card"><div class="spinner" aria-hidden="true"></div><div><strong>Loading lifecycle evidence</strong><span>Reading the checked-in deterministic review queue.</span></div></div>', 'b19-lifecycle-investigations');
  }
  if (state.build019LifecycleInvestigations?.status !== 'ready') {
    return panel('Deterministic lifecycle investigations', 'Build 019 exact-identifier reconciliation.', emptyState('Lifecycle queue unavailable', state.build019LifecycleInvestigations?.error || 'Unknown load error'), 'b19-lifecycle-investigations');
  }
  const summary = b19InvestigationSummary();
  const rows = b19FilteredInvestigations();
  return `<section class="panel b19-lifecycle-investigations"><header class="panel-header"><div><h2>Deterministic lifecycle investigations</h2><p>Exact identifiers connect capital projects, procurement awards, CAO amendments and approved Council evidence. Existing analytical investigations remain below.</p></div></header><div class="panel-body">
    <div class="notice"><strong>Review priority ≠ misconduct risk</strong><span>The Build 019 score ranks evidence depth and lifecycle complexity. It does not estimate corruption, waste, illegality, overpayment or final paid value. No payment/AP source, service-area budget bridge or audited-PSAS crosswalk is asserted.</span></div>
    <div class="metrics-grid compact">
      ${metricCard('Lifecycle review targets', numberFmt.format(summary.investigations || 0), 'Verified multi-domain components', 'accent')}
      ${metricCard('Capital ↔ procurement', numberFmt.format(summary.capital_procurement || 0), 'Same structured award/project identifiers', 'good')}
      ${metricCard('Procurement ↔ amendment', numberFmt.format(summary.procurement_amendment || 0), 'Exact tender/contract refs and PO evidence', 'neutral')}
      ${metricCard('Payment evidence', '0', 'Transaction analyses remain disabled', 'warn')}
    </div>
    <div class="local-toolbar"><select id="b19-lifecycle-priority"><option value="attention" ${state.build019LifecyclePriority === 'attention' ? 'selected' : ''}>Priority + review</option><option value="all" ${state.build019LifecyclePriority === 'all' ? 'selected' : ''}>All 29 targets</option><option value="priority_review" ${state.build019LifecyclePriority === 'priority_review' ? 'selected' : ''}>Priority review</option><option value="review" ${state.build019LifecyclePriority === 'review' ? 'selected' : ''}>Review</option><option value="context" ${state.build019LifecyclePriority === 'context' ? 'selected' : ''}>Context</option></select><select id="b19-lifecycle-track"><option value="all">All lifecycle tracks</option><option value="capital_procurement" ${state.build019LifecycleTrack === 'capital_procurement' ? 'selected' : ''}>Capital ↔ procurement</option><option value="procurement_amendment" ${state.build019LifecycleTrack === 'procurement_amendment' ? 'selected' : ''}>Procurement ↔ amendment</option></select><span class="table-note">${numberFmt.format(rows.length)} of ${numberFmt.format(summary.investigations || 0)} targets</span></div>
    ${rows.length ? `<div class="b8-investigation-grid">${rows.map(b19InvestigationCard).join('')}</div>` : emptyState('No lifecycle targets under these filters', 'Widen the Build 019 review-state or lifecycle-track filter.')}
  </div></section>`;
}
function b19SourceEvidence(source) {
  const href = safeUrl(source?.source_url);
  const title = source?.label || source?.source_id || 'Source evidence';
  return `<div class="drawer-callout"><strong>${escapeHtml(title)}</strong><p>${escapeHtml(`${source?.domain || 'domain'} · ${source?.record_type || 'record'} · ${source?.source_locator || 'locator unavailable'} · ${source?.source_id || 'source id unavailable'}`)}</p>${href ? `<a class="source-link" href="${escapeHtml(href)}" target="_blank" rel="noreferrer">Open official source ↗</a>` : ''}</div>`;
}
function b19AmendmentEvidence(row) {
  const facts = [
    ['Report date', row.report_date],
    ['Purchase order', row.purchase_order],
    ['Original value', row.original_value == null ? '—' : money(row.original_value)],
    ['Cumulative amendment', row.effective_cumulative_amendment_value == null ? '—' : money(row.effective_cumulative_amendment_value)],
    ['Source updated value', row.updated_value_source == null ? '—' : money(row.updated_value_source)],
    ['Derived updated value', row.derived_updated_value == null ? '—' : money(row.derived_updated_value)],
    ['Source increase %', row.increase_pct_source == null ? '—' : `${decimalFmt.format(row.increase_pct_source)}%`],
    ['Derived increase %', row.derived_increase_pct == null ? '—' : `${decimalFmt.format(row.derived_increase_pct)}%`]
  ];
  return `<div class="drawer-section"><h3>${escapeHtml(row.name_source || 'CAO amendment observation')}</h3>${evidenceSteps(facts)}${row.reason_source ? `<p class="drawer-note">${escapeHtml(row.reason_source)}</p>` : ''}</div>`;
}
function b19ShowInvestigation(id) {
  const row = b19InvestigationRows().find(item => item.investigation_id === id);
  if (!row) return;
  const identifierSteps = [
    ['Review priority score', `${row.review_priority_score} · ${b19PriorityLabel(row.priority)}`],
    ['Capital account(s)', row.capital_project_accounts?.join(', ') || 'not linked'],
    ['Procurement reference(s)', row.procurement_references?.join(', ') || 'not linked'],
    ['Purchase order(s)', row.purchase_orders?.join(', ') || 'not linked'],
    ['Evidence domains', row.domains?.join(' → ') || '—'],
    ['Evidence records', row.evidence_record_count]
  ];
  const reasons = (row.review_reasons || []).map(reason => `<li>${escapeHtml(b19ReasonLabel(reason))}</li>`).join('');
  const observed = (row.observed_facts || []).map(fact => `<li>${escapeHtml(fact)}</li>`).join('');
  const amendments = (row.amendment_facts || []).map(b19AmendmentEvidence).join('');
  const sources = (row.source_evidence || []).map(b19SourceEvidence).join('');
  openDrawer({
    title: row.title,
    eyebrow: 'DETERMINISTIC LIFECYCLE REVIEW',
    html: `${evidenceSteps(identifierSteps)}
      <div class="drawer-section"><h3>Why this is in the queue</h3><ul>${reasons}</ul></div>
      <div class="drawer-section"><h3>Observed linked facts</h3><ul>${observed}</ul></div>
      ${amendments}
      <div class="drawer-callout"><strong>Interpretation boundary</strong><p>${escapeHtml(row.interpretation)}</p><p>No Build 019 lifecycle item currently establishes vendor payment, final paid value, a deterministic service-area budget link or an audited-PSAS crosswalk.</p></div>
      <div class="drawer-section"><h3>Source evidence</h3>${sources || '<p>No source links available.</p>'}</div>`
  });
}
function b19EnhanceInvestigations() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b19-lifecycle-investigations')) return;
  const firstNotice = stack.querySelector(':scope > .notice');
  if (firstNotice) firstNotice.insertAdjacentHTML('afterend', b19InvestigationPanel());
  else stack.insertAdjacentHTML('afterbegin', b19InvestigationPanel());
}
function b19BindInvestigationEvents() {
  const priority = $('#b19-lifecycle-priority');
  if (priority) priority.addEventListener('change', event => { state.build019LifecyclePriority = event.target.value; render(); });
  const track = $('#b19-lifecycle-track');
  if (track) track.addEventListener('change', event => { state.build019LifecycleTrack = event.target.value; render(); });
  $$('#content [data-build019-investigation-id]').forEach(card => card.addEventListener('click', () => b19ShowInvestigation(card.dataset.build019InvestigationId)));
}

window.b19InvestigationRows = b19InvestigationRows;
window.b19InvestigationSummary = b19InvestigationSummary;

const b19RenderBase = render;
render = function renderBuild019() {
  b19RenderBase();
  if (state.view === 'signals') b19EnhanceInvestigations();
  b19BindInvestigationEvents();
};
