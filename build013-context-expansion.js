/* Build 013 — Context Data Expansion
 * Adds verified community-funding detail and a historical CAO amendment report.
 * Funding is contextual evidence only. It never creates wrongdoing/anomaly signals.
 */

state.build013Context = { status: 'loading', data: null, error: null };
state.build013Sources = { status: 'loading', data: null, error: null };
state.build013FundingQuery = '';
state.build013FundingType = 'all';
let build013SourcesMerged = false;

async function b13FetchJson(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

Promise.allSettled([
  b13FetchJson('./data/generated/context_expansion.json'),
  b13FetchJson('./data/context_sources.json')
]).then(([contextResult, sourceResult]) => {
  state.build013Context = contextResult.status === 'fulfilled'
    ? { status: 'ready', data: contextResult.value, error: null }
    : { status: 'error', data: null, error: contextResult.reason?.message || 'Context expansion failed to load' };
  state.build013Sources = sourceResult.status === 'fulfilled'
    ? { status: 'ready', data: sourceResult.value, error: null }
    : { status: 'error', data: null, error: sourceResult.reason?.message || 'Context sources failed to load' };
  b13MergeSources();
  if (typeof render === 'function') render();
});

function b13Data() { return state.build013Context?.data || null; }
function b13Meta() { return b13Data()?.metadata || {}; }
function b13CommunityGrants() { return b13Data()?.community_grants_2025 || null; }
function b13Museums() { return b13Data()?.community_museums_2025 || null; }
function b13Transit() { return b13Data()?.rural_transit_2025_26 || null; }
function b13AmendmentReport() { return b13Data()?.contract_amendments_2023_11 || null; }
function b13Amendments() { return Array.isArray(b13AmendmentReport()?.observations) ? b13AmendmentReport().observations : []; }
function b13SupplementSources() { return Array.isArray(state.build013Sources?.data?.sources) ? state.build013Sources.data.sources : []; }

function b13MergeSources() {
  if (build013SourcesMerged || state.build013Sources?.status !== 'ready' || !Array.isArray(state.sources?.sources)) return false;
  const existing = new Set(state.sources.sources.map(source => source.id));
  for (const source of b13SupplementSources()) {
    if (!existing.has(source.id)) {
      state.sources.sources.push(source);
      existing.add(source.id);
    }
  }
  const researched = state.build013Sources?.data?.metadata?.last_researched;
  if (researched && (!state.sources.metadata?.last_researched || researched > state.sources.metadata.last_researched)) {
    state.sources.metadata = { ...(state.sources.metadata || {}), last_researched: researched };
  }
  build013SourcesMerged = true;
  return true;
}

function b13SourceById(id) {
  return sourceById(id) || b13SupplementSources().find(source => source.id === id) || null;
}

function b13SourceLink(sourceId, label = null) {
  const source = b13SourceById(sourceId);
  const url = safeUrl(source?.url);
  return source && url ? `<a class="source-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(label || source.name)} ↗</a>` : '';
}

function b13SignedMoney(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return `${n > 0 ? '+' : n < 0 ? '-' : ''}${money(Math.abs(n))}`;
}

function b13Pct(value) {
  const n = Number(value);
  return Number.isFinite(n) ? `${decimalFmt.format(n)}%` : '—';
}

function b13CommunityGrantHtml() {
  const data = b13CommunityGrants();
  if (!data) return emptyState('Community Grants unavailable', 'The Build 013 Community Grants context is not loaded.');
  const requested = data.categories.reduce((sum, row) => sum + Number(row.requested || 0), 0);
  return `<div class="b13-funding-stack">
    <div class="metrics-grid compact b13-funding-metrics">
      ${metricCard('Applications', numberFmt.format(data.applications_received), `${numberFmt.format(data.applications_eligible)} eligible · ${numberFmt.format(data.applications_ineligible)} ineligible`, 'neutral')}
      ${metricCard('Staff recommendation', compactMoney(data.staff_recommended_total), `${numberFmt.format(data.staff_recommended_awards)} awards across 7 categories`, 'neutral')}
      ${metricCard('Council-approved total', compactMoney(data.council_approved_total), `${numberFmt.format(data.council_approved_awards)} awards · ${b13SignedMoney(data.council_adjustment)} net adjustment`, 'accent')}
      ${metricCard('Funding requested', compactMoney(requested), 'All 120 applications · not all requests were eligible', 'neutral')}
    </div>
    <div class="table-wrap"><table class="b13-category-table"><thead><tr><th>Category</th><th class="numeric">Applications</th><th class="numeric">Requested</th><th class="numeric">Recommended awards</th><th class="numeric">Recommended value</th></tr></thead><tbody>${data.categories.map(row => `<tr><td><strong>${escapeHtml(row.category)}</strong></td><td class="numeric">${numberFmt.format(row.applications)}</td><td class="numeric">${money(row.requested)}</td><td class="numeric">${numberFmt.format(row.recommended_awards)}</td><td class="numeric"><strong>${money(row.recommended_amount)}</strong></td></tr>`).join('')}<tr class="b13-total-row"><td><strong>Staff-recommendation control</strong></td><td class="numeric"><strong>${numberFmt.format(data.applications_received)}</strong></td><td class="numeric"><strong>${money(requested)}</strong></td><td class="numeric"><strong>${numberFmt.format(data.staff_recommended_awards)}</strong></td><td class="numeric"><strong>${money(data.staff_recommended_total)}</strong></td></tr></tbody></table></div>
    <div class="rule-list b13-context-list">${data.approval_context.map(item => `<div><strong>${escapeHtml(item.organization)} · ${escapeHtml(item.action.replace(/_/g, ' '))}</strong><span>${escapeHtml(item.reason)}${item.approved_amount != null ? ` · ${money(item.recommended_amount)} → ${money(item.approved_amount)}` : ''}</span></div>`).join('')}</div>
    <p class="table-note">${escapeHtml(data.caveat)} Repeated receipt of an eligible municipal grant is not treated as a fiscal anomaly.</p>
    <div class="b13-source-inline">${data.source_ids.map(id => b13SourceLink(id)).join('')}</div>
  </div>`;
}

function b13MuseumRows() {
  const data = b13Museums();
  if (!data) return [];
  const operating = data.operating_grants.map(row => ({ ...row, award_type: 'Operating', purpose: 'Annual museum operating grant in the 2025–2027 cycle.' }));
  const projects = data.project_grants.map(row => ({ ...row, award_type: row.grant_type || 'Project', tier: '—' }));
  return [...operating, ...projects];
}

function b13FilteredMuseumRows() {
  const query = normalize(state.build013FundingQuery);
  return b13MuseumRows().filter(row =>
    (state.build013FundingType === 'all' || row.award_type === state.build013FundingType) &&
    (!query || normalize(`${row.recipient} ${row.award_type} ${row.purpose || ''} ${row.condition || ''}`).includes(query))
  );
}

function b13MuseumHtml() {
  const data = b13Museums();
  if (!data) return emptyState('Museum funding unavailable', 'The Build 013 Community Museums context is not loaded.');
  const rows = b13FilteredMuseumRows();
  const types = [...new Set(b13MuseumRows().map(row => row.award_type))];
  const projectRecipients = new Set(data.project_grants.map(row => normalize(row.recipient)));
  const projectAlsoOperating = data.operating_grants.filter(row => projectRecipients.has(normalize(row.recipient))).length;
  return `<div class="b13-funding-stack">
    <div class="metrics-grid compact b13-funding-metrics">
      ${metricCard('Program budget', compactMoney(data.program_budget), `${compactMoney(data.balance)} unallocated after recommendations`, 'neutral')}
      ${metricCard('Annual operating grants', compactMoney(data.operating_grant_total), `${numberFmt.format(data.operating_grant_count)} museum participants`, 'accent')}
      ${metricCard('One-time project grants', compactMoney(data.project_grant_total), `${numberFmt.format(data.project_grant_count)} recommended projects`, 'neutral')}
      ${metricCard('Project + operating overlap', numberFmt.format(projectAlsoOperating), 'Project recipients also participate in operating grants by program design', 'neutral')}
    </div>
    <div class="local-toolbar build006-toolbar b13-toolbar"><label class="local-search"><span>⌕</span><input id="b13-funding-search" value="${escapeHtml(state.build013FundingQuery)}" placeholder="Search museum recipient or funded purpose" /></label><select id="b13-funding-type"><option value="all">All museum awards</option>${types.map(type => `<option value="${escapeHtml(type)}" ${type === state.build013FundingType ? 'selected' : ''}>${escapeHtml(type)}</option>`).join('')}</select><span class="table-note">${numberFmt.format(rows.length)} matched award rows</span></div>
    <div class="table-wrap"><table><thead><tr><th>Recipient</th><th>Award type</th><th>Purpose / context</th><th class="numeric">Amount</th></tr></thead><tbody>${rows.map(row => `<tr><td><strong>${escapeHtml(row.recipient)}</strong>${row.tier && row.tier !== '—' ? `<small class="cell-sub">Operating tier ${escapeHtml(row.tier)}</small>` : ''}</td><td>${escapeHtml(row.award_type)}</td><td>${escapeHtml(row.purpose || '—')}${row.condition ? `<small class="cell-sub">${escapeHtml(row.condition)}</small>` : ''}</td><td class="numeric"><strong>${money(row.amount)}</strong></td></tr>`).join('')}</tbody></table></div>
    <p class="table-note">${escapeHtml(data.caveat)}</p>
    <div class="b13-source-inline">${b13SourceLink(data.source_id)}</div>
  </div>`;
}

function b13TransitHtml() {
  const data = b13Transit();
  if (!data) return emptyState('Rural transit funding unavailable', 'The Build 013 Rural Transit context is not loaded.');
  const delta = Number(data.projected_total) - Number(data.prior_total);
  const pct = data.prior_total ? delta / Number(data.prior_total) * 100 : null;
  return `<div class="b13-funding-stack">
    <div class="b13-inline-summary">
      <div><strong>${money(data.prior_total)}</strong><span>${escapeHtml(data.prior_fiscal_year)} reported disbursements</span></div>
      <div><strong>${money(data.projected_total)}</strong><span>${escapeHtml(data.fiscal_year)} projected maximum</span></div>
      <div><strong>${b13SignedMoney(delta)}</strong><span>${pct == null ? '—' : `${b13Pct(pct)} projected movement`}</span></div>
      <div><strong>${numberFmt.format(data.providers.length)}</strong><span>service providers</span></div>
    </div>
    <div class="table-wrap"><table><thead><tr><th>Service provider</th><th class="numeric">2024/25 disbursement</th><th class="numeric">Projected km</th><th class="numeric">2025/26 projected grant</th></tr></thead><tbody>${data.providers.map(row => `<tr><td><strong>${escapeHtml(row.provider)}</strong></td><td class="numeric">${money(row.prior_disbursement)}</td><td class="numeric">${numberFmt.format(row.projected_km)}</td><td class="numeric"><strong>${money(row.projected_grant)}</strong></td></tr>`).join('')}</tbody></table></div>
    <p class="table-note">${escapeHtml(data.caveat)}</p>
    <div class="b13-source-inline">${b13SourceLink(data.source_id)}</div>
  </div>`;
}

function b13FundingSection() {
  if (state.build013Context?.status === 'loading') return `<section class="panel b13-community-funding"><header class="panel-header"><div><h2>Community funding context</h2><p>Loading Build 013 funding evidence.</p></div></header></section>`;
  if (state.build013Context?.status !== 'ready') return `<section class="panel b13-community-funding"><header class="panel-header"><div><h2>Community funding context</h2><p>Build 013 funding evidence is unavailable.</p></div></header><div class="panel-body">${emptyState('Context unavailable', state.build013Context?.error || 'Unknown load error')}</div></section>`;
  return `<section class="b13-community-funding page-stack">
    <div class="notice b13-funding-boundary"><strong>Funding context, not suspicion scoring</strong><span>These municipal grant/program records explain where public funding goes and how program rules affect repeat awards. They are not procurement awards, invoices, AP transactions or evidence that a repeated recipient is improper.</span></div>
    ${panel('2025/26 Community Grants', 'Application pressure, staff-recommendation categories and the final Council-approved program total are shown separately so the $4,000 Council adjustment is not silently redistributed across categories.', b13CommunityGrantHtml())}
    ${panel('2025 Community Museum funding', 'Recipient-level operating and project awards. Multi-year operating support and project grants are distinct program mechanisms.', b13MuseumHtml())}
    ${panel('2025/26 Rural Transit funding', 'Formula-based municipal grants to four rural transit service providers, with the prior year shown for context.', b13TransitHtml())}
  </section>`;
}

function b13AmendmentInvestigations() {
  if (state.build013Context?.status !== 'ready') return [];
  const rows = b13Amendments().filter(row => Number(row.published_increase_pct || 0) >= 50 || Number(row.published_amendment_value || 0) >= 250000);
  const maxAmount = Math.max(1, ...rows.map(row => Math.abs(Number(row.published_amendment_value || 0))));
  return rows.map(row => {
    const pct = Number(row.published_increase_pct || 0);
    const amount = Number(row.published_amendment_value || 0);
    const materiality = b8ScoreMateriality(amount, maxAmount);
    const deviation = b8ScoreDeviation(pct / 100, 180);
    const persistence = 32;
    const evidence = row.source_arithmetic_consistent === false ? 92 : 100;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    return {
      id: `b13-amend-${b8Slug(row.id)}`,
      domain: 'Contract amendments', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${row.name} — published cumulative amendment`,
      detail: `${row.po ? `PO ${row.po}` : row.contract ? `Contract ${row.contract}` : 'Published contract'} · ${money(row.original_value)} → ${money(row.updated_value)} · ${b13Pct(pct)} published increase`,
      materialityText: `${money(amount)} published amendment value in the Nov. 2023 aggregate report`,
      scope: 'One complete public Nov. 15, 2023 CAO amendment attachment table; private/confidential amendment reports excluded by source',
      sourceIds: [b13AmendmentReport().source_id, 'hrm-procurement-policy-2022-012-adm'],
      evidenceRows: [
        ['Report date', b13AmendmentReport().report_date],
        ['PO / contract', row.po || row.contract || '—'],
        ['Supplier named by source', row.vendor_source || 'Not separately identified in aggregate row'],
        ['Original value', money(row.original_value)],
        ['Published amendment value', money(row.published_amendment_value)],
        ['Published updated value', money(row.updated_value)],
        ['Published increase', b13Pct(row.published_increase_pct)],
        ['Source arithmetic', row.source_arithmetic_consistent ? 'Reconciles' : `${b13SignedMoney(row.source_arithmetic_delta)} mismatch vs original + amendment`],
        ['Source-stated reason', row.reason]
      ],
      caveat: 'The aggregate report’s “Value of Amendment” is treated as the cumulative amendment amount used to reach the updated value; it may include prior changes and is not necessarily the current change-order request. A large amendment can reflect legitimate scope, schedule, utility, market or operational changes and is not evidence of corruption.'
    };
  }).sort((a, b) => b.score - a.score);
}

const b13AllInvestigationsBase = b8AllInvestigations;
b8AllInvestigations = function b8AllInvestigationsBuild013() {
  const result = b13AllInvestigationsBase();
  const amendments = b13AmendmentInvestigations();
  if (!amendments.length) return result;
  const fiscal = [...result.fiscal, ...amendments].sort((a, b) => b.score - a.score);
  const all = [...fiscal, ...result.quality];
  build008InvestigationIndex = new Map(all.map(item => [item.id, item]));
  return { fiscal, quality: result.quality };
};

function b13AmendmentTableHtml() {
  const report = b13AmendmentReport();
  if (!report) return emptyState('Historical amendment context unavailable', 'The Build 013 amendment report is not loaded.');
  return `<div class="b13-funding-stack">
    <div class="metrics-grid compact b13-funding-metrics">
      ${metricCard('Public source-table rows', numberFmt.format(report.public_attachment_table_rows), `${numberFmt.format(report.financial_observations)} financial observations after a two-PO row is split`, 'neutral')}
      ${metricCard('Review-screen leads', numberFmt.format(b13AmendmentInvestigations().length), '≥50% published increase or ≥$250k published amendment value', 'warn')}
      ${metricCard('Source arithmetic flags', numberFmt.format(b13Amendments().filter(row => row.source_arithmetic_consistent === false).length), 'Preserved as source-data quality, not corrected silently', 'warn')}
      ${metricCard('Private/confidential', 'Excluded', 'The report explicitly excludes those amendment files', 'neutral')}
    </div>
    <div class="table-wrap"><table><thead><tr><th>PO / contract</th><th>Context</th><th class="numeric">Original</th><th class="numeric">Published amendment</th><th class="numeric">Updated</th><th class="numeric">Increase</th></tr></thead><tbody>${b13Amendments().map(row => `<tr data-build013-amendment="${escapeHtml(row.id)}"><td><strong>${escapeHtml(row.po || row.contract || '—')}</strong><small class="cell-sub">${escapeHtml(row.vendor_source || 'supplier not stated in aggregate row')}</small></td><td><strong>${escapeHtml(row.name)}</strong><small class="cell-sub">${escapeHtml(row.reason)}</small></td><td class="numeric">${money(row.original_value)}</td><td class="numeric"><strong>${money(row.published_amendment_value)}</strong></td><td class="numeric">${money(row.updated_value)}${row.source_arithmetic_consistent === false ? `<small class="cell-sub b13-source-flag">source math ${b13SignedMoney(row.source_arithmetic_delta)}</small>` : ''}</td><td class="numeric"><strong>${b13Pct(row.published_increase_pct)}</strong></td></tr>`).join('')}</tbody></table></div>
    <p class="table-note">${escapeHtml(report.amount_semantics)} ${escapeHtml(report.caveat)}</p>
    <div class="b13-source-inline">${b13SourceLink(report.source_id)}${b13SourceLink('hrm-procurement-policy-2022-012-adm', 'Procurement policy')}</div>
  </div>`;
}

function b13AmendmentSection() {
  return `<section class="panel b13-amendment-history"><header class="panel-header"><div><h2>Historical CAO amendment context</h2><p>A complete public aggregate attachment table from Nov. 15, 2023 adds earlier lifecycle context beyond Build 012's selected 2025 amendment examples.</p></div></header><div class="panel-body">${b13AmendmentTableHtml()}</div></section>`;
}

function b13ShowAmendment(id) {
  const row = b13Amendments().find(item => item.id === id);
  const report = b13AmendmentReport();
  if (!row || !report) return;
  openDrawer({
    title: row.name,
    eyebrow: 'CONTRACT AMENDMENT CONTEXT',
    html: `${evidenceSteps([
      ['Report date', report.report_date],
      ['PO / contract', row.po || row.contract || '—'],
      ['Supplier named by source', row.vendor_source || 'Not separately identified in aggregate row'],
      ['Original value', money(row.original_value)],
      ['Published amendment value', money(row.published_amendment_value)],
      ['Published updated value', money(row.updated_value)],
      ['Published increase', b13Pct(row.published_increase_pct)],
      ['Derived original + amendment', money(row.derived_updated_value)],
      ['Source arithmetic delta', b13SignedMoney(row.source_arithmetic_delta)],
      ['Source arithmetic consistent?', row.source_arithmetic_consistent ? 'Yes' : 'No — source values preserved without correction'],
      ['Reason in aggregate report', row.reason]
    ])}<div class="drawer-callout"><strong>Interpretation boundary</strong><p>${escapeHtml(report.amount_semantics)} This is amendment-report evidence, not an invoice, payment, final paid value, complete contract history or wrongdoing finding. The public report states that Private & Confidential amendment reports are excluded.</p></div><div class="drawer-section"><h3>Sources</h3><div class="drawer-source-list">${b13SourceLink(report.source_id)}${b13SourceLink('hrm-procurement-policy-2022-012-adm', 'Procurement policy')}</div></div>`
  });
}

function b13SourceCoverageHtml() {
  const sources = b13SupplementSources();
  return `<section class="panel b13-source-coverage"><header class="panel-header"><div><h2>Build 013 context sources</h2><p>Additional municipal funding, procurement-policy and historical amendment evidence.</p></div></header><div class="panel-body"><div class="b13-source-grid">${sources.map(source => `<div><strong>${escapeHtml(source.name)}</strong><span>${escapeHtml(source.coverage)}</span>${badge(source.status, sourceStatusTone(source.status))}${b13SourceLink(source.id, 'Open source')}</div>`).join('')}</div><div class="notice b13-funding-boundary"><strong>Coverage boundary</strong><span>These sources broaden context; they do not fill the accounts-payable/payment gap and they do not establish a complete grants or contract-amendment ledger.</span></div></div></section>`;
}

function b13EnhanceBenchmarks() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b13-community-funding')) return;
  stack.insertAdjacentHTML('beforeend', b13FundingSection());
}

function b13EnhanceVendors() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b13-amendment-history')) return;
  const anchor = stack.querySelector('.b12-amendment-section') || stack.querySelector('.b11-procurement') || stack.lastElementChild;
  if (anchor) anchor.insertAdjacentHTML('afterend', b13AmendmentSection());
}

function b13EnhanceSources() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b13-source-coverage')) return;
  stack.insertAdjacentHTML('beforeend', b13SourceCoverageHtml());
}

function b13BindEvents() {
  $$('#content [data-build013-amendment]').forEach(element => element.addEventListener('click', () => b13ShowAmendment(element.dataset.build013Amendment)));
  const search = $('#b13-funding-search');
  if (search) search.addEventListener('input', event => { state.build013FundingQuery = event.target.value; render(); });
  const type = $('#b13-funding-type');
  if (type) type.addEventListener('change', event => { state.build013FundingType = event.target.value; render(); });
  $$('#content .b13-amendment-history [data-build008-investigation-id]').forEach(element => element.addEventListener('click', () => b8ShowInvestigation(element.dataset.build008InvestigationId)));
}

const b13RenderBase = render;
render = function renderBuild013() {
  b13MergeSources();
  b13RenderBase();
  if (state.view === 'benchmarks') b13EnhanceBenchmarks();
  if (state.view === 'vendors') b13EnhanceVendors();
  if (state.view === 'sources') b13EnhanceSources();
  b13BindEvents();
};
