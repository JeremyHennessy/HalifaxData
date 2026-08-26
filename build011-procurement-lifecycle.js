/* Build 011 — Procurement Lifecycle / Alternative Procurement evidence.
 * Derived presentation over validated procurement_quarterly.json.
 * This report-controlled layer is separate from the Nova Scotia public-tender awards.
 */

state.build011Procurement = { status: 'loading', data: null, error: null };
state.build011ProcurementPeriod = 'all';
state.build011ProcurementDepartment = 'all';
state.build011ProcurementQuery = '';

fetch('./data/generated/procurement_quarterly.json', { cache: 'no-store' })
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(data => {
    state.build011Procurement = { status: 'ready', data, error: null };
    if (typeof render === 'function') render();
  })
  .catch(error => {
    state.build011Procurement = { status: 'error', data: null, error: error.message };
    if (typeof render === 'function') render();
  });

function b11Data() { return state.build011Procurement?.data || null; }
function b11Meta() { return b11Data()?.metadata || {}; }
function b11Rows() { return Array.isArray(b11Data()?.alternative_procurement) ? b11Data().alternative_procurement : []; }
function b11Reports() { return Array.isArray(b11Data()?.reports) ? b11Data().reports : []; }
function b11VendorName(row) { return row?.vendor_display_name || row?.vendor_name || row?.supplier_source_text || 'Unresolved supplier'; }
function b11VendorKey(row) { return normalize(b11VendorName(row)); }
function b11Report(row) { return b11Reports().find(report => String(report.document_id) === String(row.report_document_id)); }

function b11VendorGroups() {
  const rows = b11Rows().filter(row => row.vendor_identity_eligible_for_grouping === true);
  const groups = new Map();
  for (const row of rows) {
    const key = b11VendorKey(row);
    if (!key) continue;
    const group = groups.get(key) || { key, name: b11VendorName(row), value: 0, count: 0, rows: [], periods: new Set(), types: new Set() };
    group.value += Number(row.award_value || 0);
    group.count += 1;
    group.rows.push(row);
    if (row.report_period) group.periods.add(row.report_period);
    if (row.procurement_type_display) group.types.add(row.procurement_type_display);
    groups.set(key, group);
  }
  const total = rows.reduce((sum, row) => sum + Number(row.award_value || 0), 0);
  return [...groups.values()].map(group => ({ ...group, total, share: total ? group.value / total : 0 }));
}

function b11AlternativeInvestigations() {
  if (state.build011Procurement?.status !== 'ready') return [];
  const groups = b11VendorGroups().filter(group => group.value >= 250000 || group.count >= 2 || group.share >= 0.03);
  const maxValue = Math.max(1, ...groups.map(group => group.value));
  return groups.map(group => {
    const materiality = b8ScoreMateriality(group.value, maxValue);
    const deviation = b8Clamp(group.share * 500);
    const persistence = b8Clamp(28 + Math.log2(Math.max(1, group.count)) * 22 + Math.max(0, group.periods.size - 1) * 12);
    const evidence = 98;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    const sourceIds = b8Unique(group.rows.map(row => row.source_id));
    return {
      id: `b11-alt-${b8Slug(group.key)}`,
      domain: 'Alternative procurement', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${group.name} alternative-procurement report concentration`,
      detail: `${numberFmt.format(group.count)} report-controlled row${group.count === 1 ? '' : 's'} across ${numberFmt.format(group.periods.size)} quarter${group.periods.size === 1 ? '' : 's'} · ${decimalFmt.format(group.share * 100)}% of grouping-eligible collected alternative-procurement value`,
      materialityText: `${compactMoney(group.value)} collected report-section award value`,
      scope: 'HRM quarterly Alternative Awards / Alternative Procurement appendix only · grouping-eligible supplier identity; separate from public-tender awards',
      sourceIds,
      evidenceRows: [
        ['Supplier display identity', group.name],
        ['Controlled appendix rows', numberFmt.format(group.count)],
        ['Quarterly periods represented', numberFmt.format(group.periods.size)],
        ['Collected award value', money(group.value)],
        ['Grouping-eligible layer value', money(group.total)],
        ['Share of grouping-eligible layer', `${decimalFmt.format(group.share * 100)}%`],
        ['Source type(s)', [...group.types].join(' · ') || '—']
      ],
      caveat: 'This screen ranks concentration within the collected HRM quarterly report-controlled alternative-procurement appendix only. It does not combine these values with public-tender awards, does not establish a complete procurement denominator, does not show bidder counts or final paid value, and is not evidence of improper or non-competitive procurement.'
    };
  }).sort((a, b) => b.score - a.score);
}

const b11AllInvestigationsBase = b8AllInvestigations;
b8AllInvestigations = function b8AllInvestigationsBuild011() {
  const result = b11AllInvestigationsBase();
  const alternative = b11AlternativeInvestigations();
  if (!alternative.length) return result;
  const fiscal = [...result.fiscal, ...alternative].sort((a, b) => b.score - a.score);
  const all = [...fiscal, ...result.quality];
  build008InvestigationIndex = new Map(all.map(item => [item.id, item]));
  return { fiscal, quality: result.quality };
};

function b11FilteredRows() {
  const query = normalize(state.build011ProcurementQuery);
  return b11Rows().filter(row =>
    (state.build011ProcurementPeriod === 'all' || row.report_period === state.build011ProcurementPeriod) &&
    (state.build011ProcurementDepartment === 'all' || (row.department || 'Not separately reported') === state.build011ProcurementDepartment) &&
    (!query || normalize(`${row.project_number || ''} ${row.solicitation || ''} ${row.award_title || ''} ${row.vendor_display_name || ''} ${row.vendor_name || ''} ${row.supplier_source_text || ''} ${row.procurement_type_display || ''} ${row.account_project_codes || ''} ${row.department || ''}`).includes(query))
  );
}

function b11ReportControlsHtml() {
  return `<div class="b11-report-grid">${b11Reports().map(report => `<article class="b11-report-card">
    <div><strong>${escapeHtml(report.report_period || 'Quarterly report')}</strong>${badge(`${numberFmt.format(report.parsed_alternative_rows || 0)} rows`, 'muted')}</div>
    <span>${money(report.parsed_alternative_value)} extracted appendix value</span>
    <small>${report.alternative_value == null ? 'Published count control reconciled; source report does not expose the later-format dollar control.' : `Published count + ${money(report.alternative_value)} value controls reconciled.`}</small>
    ${report.source_url_changed_since_graph ? `<small class="b11-source-change">Attachment replaced after graph capture; exact-title agenda resolution preserved both URLs.</small>` : ''}
  </article>`).join('')}</div>`;
}

function b11SupplierConcentrationHtml() {
  const investigations = b11AlternativeInvestigations().slice(0, 10);
  if (!investigations.length) return emptyState('No qualifying supplier concentration', 'No grouping-eligible supplier identity meets the current materiality/repeat screen.');
  return `<div class="b8-compact-list">${investigations.map(item => b8InvestigationCard(item, true)).join('')}</div>`;
}

function b11RowTableHtml() {
  const all = b11Rows();
  const rows = b11FilteredRows();
  const periods = [...new Set(all.map(row => row.report_period).filter(Boolean))];
  const departments = [...new Set(all.map(row => row.department || 'Not separately reported'))].sort((a, b) => a.localeCompare(b));
  const visible = [...rows].sort((a, b) => Number(b.award_value || 0) - Number(a.award_value || 0)).slice(0, 120);
  return `<div class="local-toolbar build006-toolbar b11-toolbar">
    <label class="local-search"><span>⌕</span><input id="b11-procurement-search" value="${escapeHtml(state.build011ProcurementQuery)}" placeholder="Search alternative award, supplier, project or reference" /></label>
    <select id="b11-procurement-period"><option value="all">All 8 report periods</option>${periods.map(period => `<option value="${escapeHtml(period)}" ${period === state.build011ProcurementPeriod ? 'selected' : ''}>${escapeHtml(period)}</option>`).join('')}</select>
    <select id="b11-procurement-department"><option value="all">All departments</option>${departments.map(department => `<option value="${escapeHtml(department)}" ${department === state.build011ProcurementDepartment ? 'selected' : ''}>${escapeHtml(department)}</option>`).join('')}</select>
    <span class="table-note">Showing ${numberFmt.format(visible.length)} of ${numberFmt.format(rows.length)} matched controlled rows</span>
  </div>
  <div class="table-wrap"><table><thead><tr><th>Period</th><th>Project / award</th><th>Supplier evidence</th><th>Source type</th><th>Department / reference</th><th class="numeric">Award value</th></tr></thead><tbody>${visible.map(row => `<tr data-build011-row="${escapeHtml(`${row.report_document_id}:${row.source_page}:${row.source_table}:${row.source_row}`)}">
    <td>${escapeHtml(row.report_period || '—')}</td>
    <td><strong>${escapeHtml(row.project_number || row.solicitation || 'Source award row')}</strong><small class="cell-sub">${escapeHtml(row.award_title || '—')}</small></td>
    <td><strong>${escapeHtml(b11VendorName(row))}</strong><small class="cell-sub">${row.vendor_identity_eligible_for_grouping ? 'grouping-eligible identity' : 'identity unresolved — excluded from supplier grouping'}</small></td>
    <td>${escapeHtml(row.procurement_type_display || '—')}</td>
    <td>${escapeHtml(row.department || 'Not separately reported')}<small class="cell-sub">${escapeHtml(row.account_project_codes || '—')}</small></td>
    <td class="numeric"><strong>${money(row.award_value)}</strong></td>
  </tr>`).join('')}</tbody></table></div>`;
}

function b11ProcurementSection() {
  const status = state.build011Procurement?.status;
  if (status === 'loading') return `<section class="panel b11-procurement"><header class="panel-header"><div><h2>Alternative procurement report evidence</h2><p>Loading the validated quarterly report artifact.</p></div></header><div class="panel-body">${emptyState('Loading report evidence', 'Reading the checked-in Build 011 artifact.')}</div></section>`;
  if (status !== 'ready') return `<section class="panel b11-procurement"><header class="panel-header"><div><h2>Alternative procurement report evidence</h2><p>The checked-in artifact could not be loaded.</p></div></header><div class="panel-body">${emptyState('Artifact unavailable', state.build011Procurement?.error || 'Unknown load error')}</div></section>`;
  const meta = b11Meta();
  const eligibleValue = b11Rows().filter(row => row.vendor_identity_eligible_for_grouping).reduce((sum, row) => sum + Number(row.award_value || 0), 0);
  return `<section class="b11-procurement page-stack">
    <div class="notice b11-boundary"><strong>Separate procurement evidence layer</strong><span>These ${numberFmt.format(meta.alternative_procurement_rows || 0)} rows come from HRM's controlled quarterly Alternative Awards / Alternative Procurement appendix sections. They are not added to the Nova Scotia public-tender award dataset, are not accounts-payable transactions, and are not final paid values.</span></div>
    <div class="metrics-grid compact">
      ${metricCard('Controlled appendix rows', numberFmt.format(meta.alternative_procurement_rows || 0), `${numberFmt.format(meta.report_count || 0)} quarterly reports`, 'accent')}
      ${metricCard('Collected appendix value', compactMoney(meta.alternative_procurement_value), 'Separate from public-tender award value', 'neutral')}
      ${metricCard('Grouping-eligible value', compactMoney(eligibleValue), `${numberFmt.format(80)} supplier-identity-eligible rows`, 'neutral')}
      ${metricCard('Identity unresolved', numberFmt.format(meta.vendor_identity_unresolved_rows || 0), 'Visible but excluded from supplier grouping', (meta.vendor_identity_unresolved_rows || 0) ? 'warn' : 'good')}
    </div>
    <div class="split-grid wide-left">
      ${panel('Alternative-procurement supplier concentration', 'Exact/derived supplier display identities only where the source summary supports grouping. This denominator is this report-controlled layer alone.', b11SupplierConcentrationHtml())}
      ${panel('Evidence controls', 'Every quarter reconciles to HRM’s published alternative-procurement row count; later-format reports also reconcile their published appendix value to the cent.', `<div class="rule-list"><div><strong>${numberFmt.format(meta.source_rows_at_exact_threshold || 0)} exact-$50,000 source rows retained</strong><span>HRM’s report wording says “exceeding $50,000,” but the controlled appendices include these rows; they are retained to reconcile exactly.</span></div><div><strong>${numberFmt.format(meta.reports_with_replaced_attachment_url || 0)} replaced attachment resolved</strong><span>The Aug. 25, 2026 report moved from eSCRIBE DocumentId 5716 to 5776. Both historical graph and live resolved URLs remain in provenance.</span></div><div><strong>No complete procurement denominator</strong><span>This layer does not establish every purchase, amendment, invoice, payment, bidder count or final paid value.</span></div></div>`)}
    </div>
    ${panel('Quarterly report controls', 'Control status is shown period by period; extracted row values are not represented as source-published totals where the older report format did not publish that control.', b11ReportControlsHtml())}
    ${panel('Controlled alternative-procurement rows', 'All 84 report-section rows remain inspectable, including rows excluded from supplier grouping. Click a row for exact source and attachment provenance.', b11RowTableHtml())}
  </section>`;
}

function b11FindRow(id) {
  return b11Rows().find(row => `${row.report_document_id}:${row.source_page}:${row.source_table}:${row.source_row}` === id);
}

function b11ShowRow(id) {
  const row = b11FindRow(id);
  if (!row) return;
  const report = b11Report(row) || {};
  const liveUrl = safeUrl(row.source_url_resolved || row.source_url);
  const graphUrl = safeUrl(row.source_url_registry);
  const agendaUrl = safeUrl(report.agenda_url);
  openDrawer({
    title: row.award_title || row.project_number || 'Alternative procurement source row',
    eyebrow: 'ALTERNATIVE PROCUREMENT EVIDENCE',
    html: `${evidenceSteps([
      ['Report period', row.report_period],
      ['Project / solicitation', row.project_number || row.solicitation || '—'],
      ['Supplier display', b11VendorName(row)],
      ['Raw supplier summary', row.supplier_source_text || row.vendor_name || '—'],
      ['Vendor identity status', row.vendor_identity_status],
      ['Eligible for supplier grouping', row.vendor_identity_eligible_for_grouping ? 'Yes' : 'No'],
      ['Source procurement type', row.procurement_type_display || '—'],
      ['Award value', money(row.award_value)],
      ['Department', row.department || 'Not separately reported'],
      ['Internal / project reference', row.account_project_codes || '—'],
      ['Source locator', `doc${row.report_document_id} / p${row.source_page} / t${row.source_table} / r${row.source_row}`],
      ['Attachment resolution', row.source_url_resolution],
      ['Historical graph URL changed?', row.source_url_changed_since_graph ? 'Yes — exact-title live agenda attachment resolved' : 'No']
    ])}
    <div class="drawer-callout"><strong>Interpretation boundary</strong><p>This is an HRM quarterly report-controlled Alternative Awards / Alternative Procurement appendix row. It is not an invoice, payment, complete procurement record, proof of lack of competition, contract amendment total or final paid value.</p></div>
    <div class="drawer-section"><h3>Source links</h3><div class="drawer-source-list">
      ${liveUrl ? `<a class="source-link" href="${escapeHtml(liveUrl)}" target="_blank" rel="noreferrer">Current resolved report attachment ↗</a>` : ''}
      ${row.source_url_changed_since_graph && graphUrl ? `<a class="source-link" href="${escapeHtml(graphUrl)}" target="_blank" rel="noreferrer">Historical graph attachment URL ↗</a>` : ''}
      ${agendaUrl ? `<a class="source-link" href="${escapeHtml(agendaUrl)}" target="_blank" rel="noreferrer">Owning Council agenda ↗</a>` : ''}
    </div></div>`
  });
}

function b11BindEvents() {
  $$('#content [data-build011-row]').forEach(element => element.addEventListener('click', () => b11ShowRow(element.dataset.build011Row)));
  const query = $('#b11-procurement-search');
  if (query) query.addEventListener('input', event => { state.build011ProcurementQuery = event.target.value; render(); });
  const period = $('#b11-procurement-period');
  if (period) period.addEventListener('change', event => { state.build011ProcurementPeriod = event.target.value; render(); });
  const department = $('#b11-procurement-department');
  if (department) department.addEventListener('change', event => { state.build011ProcurementDepartment = event.target.value; render(); });
  // The Build 011 render wrapper runs after Build 008/009/010 binders; bind any
  // newly rendered investigation cards created by this layer as well.
  $$('#content [data-build008-investigation-id]').forEach(element => {
    if (!element.dataset.b11Bound) {
      element.dataset.b11Bound = '1';
      element.addEventListener('click', () => b8ShowInvestigation(element.dataset.build008InvestigationId));
    }
  });
}

function b11EnhanceVendors() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b11-procurement')) return;
  const anchor = stack.querySelector('.b8-procurement-analysis') || stack.querySelector('.metrics-grid');
  if (anchor) anchor.insertAdjacentHTML('afterend', b11ProcurementSection());
  else stack.insertAdjacentHTML('afterbegin', b11ProcurementSection());
}

const b11RenderBase = render;
render = function renderBuild011() {
  b11RenderBase();
  if (state.view === 'vendors') b11EnhanceVendors();
  b11BindEvents();
};
