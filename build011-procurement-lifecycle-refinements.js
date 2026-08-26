/* Build 011 UI refinements.
 * Keep supplier grouping conservative: case/whitespace normalization only.
 * Candidate legal-name variants remain distinct unless the checked artifact itself
 * provides the same display identity.
 */

b11VendorKey = function b11VendorKeyExactDisplay(row) {
  return String(b11VendorName(row) || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('en-CA');
};

function b11SummaryFacts() {
  const groups = b11VendorGroups();
  const departmentRows = b11Rows().filter(row => String(row.department || '').trim());
  return {
    distinctSuppliers: groups.length,
    repeatSuppliers: groups.filter(group => group.count >= 2).length,
    multiQuarterSuppliers: groups.filter(group => group.periods.size >= 2).length,
    departmentRows: departmentRows.length,
    departmentValue: departmentRows.reduce((sum, row) => sum + Number(row.award_value || 0), 0)
  };
}

function b11SignedCount(value) {
  const n = Number(value || 0);
  if (!n) return 'no change';
  return `${n > 0 ? '+' : ''}${numberFmt.format(n)}`;
}

function b11SignedMoney(value) {
  const n = Number(value || 0);
  if (!n) return '$0';
  return `${n > 0 ? '+' : '-'}${compactMoney(Math.abs(n))}`;
}

function b11QuarterlyActivityHtml() {
  const reports = b11Reports();
  return `<div class="b11-quarter-list">${reports.map((report, index) => {
    const previous = index ? reports[index - 1] : null;
    const countDelta = previous ? Number(report.parsed_alternative_rows || 0) - Number(previous.parsed_alternative_rows || 0) : null;
    const valueDelta = previous ? Number(report.parsed_alternative_value || 0) - Number(previous.parsed_alternative_value || 0) : null;
    const controlText = report.alternative_value == null
      ? 'published count reconciled · appendix value extracted'
      : 'published count + value reconciled';
    return `<div class="b11-quarter-row">
      <div><strong>${escapeHtml(report.report_period || 'Quarter')}</strong><span>${escapeHtml(controlText)}</span></div>
      <div><b>${numberFmt.format(report.parsed_alternative_rows || 0)} rows</b><small>${previous ? `${b11SignedCount(countDelta)} vs prior report` : 'first collected quarter'}</small></div>
      <div><b>${money(report.parsed_alternative_value)}</b><small>${previous ? `${b11SignedMoney(valueDelta)} vs prior report` : 'extracted appendix value'}</small></div>
    </div>`;
  }).join('')}</div>`;
}

function b11TypeMixHtml() {
  const groups = new Map();
  for (const row of b11Rows()) {
    const name = row.procurement_type_display || 'Not separately reported';
    const group = groups.get(name) || { name, count: 0, value: 0 };
    group.count += 1;
    group.value += Number(row.award_value || 0);
    groups.set(name, group);
  }
  const total = Math.max(1, b11Rows().reduce((sum, row) => sum + Number(row.award_value || 0), 0));
  return `<div class="rule-list b11-breakdown-list">${[...groups.values()].sort((a, b) => b.value - a.value).map(group => `<div><strong>${escapeHtml(group.name)} · ${numberFmt.format(group.count)} row${group.count === 1 ? '' : 's'}</strong><span>${money(group.value)} · ${decimalFmt.format(group.value / total * 100)}% of collected appendix value</span></div>`).join('')}</div>`;
}

function b11DepartmentHtml() {
  const rows = b11Rows().filter(row => String(row.department || '').trim());
  const groups = new Map();
  for (const row of rows) {
    const name = String(row.department).trim();
    const group = groups.get(name) || { name, count: 0, value: 0 };
    group.count += 1;
    group.value += Number(row.award_value || 0);
    groups.set(name, group);
  }
  const total = Math.max(1, rows.reduce((sum, row) => sum + Number(row.award_value || 0), 0));
  return `<div class="b11-department-grid">${[...groups.values()].sort((a, b) => b.value - a.value).map(group => `<div><strong>${escapeHtml(group.name)}</strong><span>${numberFmt.format(group.count)} rows · ${money(group.value)}</span><small>${decimalFmt.format(group.value / total * 100)}% of department-coded appendix value</small></div>`).join('')}</div><p class="table-note">Department shares use only the ${numberFmt.format(rows.length)} rows where HRM publishes a department. Legacy rows without a department column are excluded from this denominator rather than assigned.</p>`;
}

function b11DetailHtml() {
  const facts = b11SummaryFacts();
  return `<div class="metrics-grid compact b11-detail-metrics">
    ${metricCard('Distinct grouping identities', numberFmt.format(facts.distinctSuppliers), 'Case/whitespace-normalized supplier display identities', 'neutral')}
    ${metricCard('Repeat identities', numberFmt.format(facts.repeatSuppliers), 'At least two controlled appendix rows', facts.repeatSuppliers ? 'warn' : 'good')}
    ${metricCard('Multi-quarter identities', numberFmt.format(facts.multiQuarterSuppliers), 'Same display identity appears in at least two report periods', 'neutral')}
    ${metricCard('Department-coded rows', numberFmt.format(facts.departmentRows), `${compactMoney(facts.departmentValue)} with a published department field`, 'neutral')}
  </div>
  <div class="split-grid wide-left b11-detail-grid">
    ${panel('Quarterly alternative-procurement activity', 'Report-by-report movement in controlled appendix row count and extracted appendix value. Older report values are extracted sums, not source-published dollar controls.', b11QuarterlyActivityHtml())}
    ${panel('Literal source-type mix', 'Preserves the procurement-type field as HRM publishes it. Legacy report-section rows are shown separately because those reports do not contain a distinct procurement-type column.', b11TypeMixHtml())}
  </div>
  ${panel('Department coverage', `Department concentration is calculated only inside rows with a literal department field; it is not a whole-procurement denominator.`, b11DepartmentHtml())}`;
}

const b11AlternativeInvestigationsBase = b11AlternativeInvestigations;
b11AlternativeInvestigations = function b11AlternativeInvestigationsRefined() {
  const groups = new Map(b11VendorGroups().map(group => [`b11-alt-${b8Slug(group.key)}`, group]));
  return b11AlternativeInvestigationsBase().map(item => {
    const group = groups.get(item.id);
    const history = group ? [...group.rows]
      .sort((a, b) => String(a.report_meeting_start_date || '').localeCompare(String(b.report_meeting_start_date || '')))
      .map(row => [
        `History · ${row.report_period}`,
        `${row.award_title || row.project_number || 'Source award row'} · ${money(row.award_value)} · ${row.procurement_type_display || 'type not separately reported'}`
      ]) : [];
    return {
      ...item,
      scope: `${item.scope}; not a complete procurement denominator`,
      evidenceRows: [
        ...item.evidenceRows,
        ['Supplier identity rule', 'Case/whitespace normalization only; legal-name/corporate variants remain separate'],
        ...history
      ]
    };
  });
};

const b11ProcurementSectionBase = b11ProcurementSection;
b11ProcurementSection = function b11ProcurementSectionRefined() {
  const eligibleCount = b11Rows().filter(row => row.vendor_identity_eligible_for_grouping === true).length;
  let html = b11ProcurementSectionBase().replace('80 supplier-identity-eligible rows', `${numberFmt.format(eligibleCount)} supplier-identity-eligible rows`);
  if (state.build011Procurement?.status === 'ready') {
    html = html.replace(
      '<section class="b11-procurement page-stack">',
      '<section class="b11-procurement page-stack"><header class="b11-section-header"><p class="eyebrow">PROCUREMENT LIFECYCLE</p><h2>Alternative procurement report evidence</h2><p>Quarterly HRM report-controlled Alternative Awards / Alternative Procurement appendix rows, kept analytically separate from public-tender awards.</p></header>'
    );
    html = html.replace('<div class="split-grid wide-left">', `${b11DetailHtml()}<div class="split-grid wide-left">`);
  }
  return html;
};

b11ShowRow = function b11ShowRowRefined(id) {
  const row = b11FindRow(id);
  if (!row) return;
  const report = b11Report(row) || {};
  const liveUrl = safeUrl(row.source_url_resolved || row.source_url);
  const graphUrl = safeUrl(row.source_url_registry);
  const agendaUrl = safeUrl(report.agenda_url);
  const reportControl = report.alternative_value == null
    ? `${numberFmt.format(report.parsed_alternative_rows || 0)} rows · published count reconciled · no source-published dollar control in this report format`
    : `${numberFmt.format(report.parsed_alternative_rows || 0)} rows · ${money(report.alternative_value)} published value · count and value reconciled`;
  const rawCells = Array.isArray(row.raw_cells) ? row.raw_cells.filter(Boolean).join(' | ') : '';
  openDrawer({
    title: row.award_title || row.project_number || 'Alternative procurement source row',
    eyebrow: 'ALTERNATIVE PROCUREMENT EVIDENCE',
    html: `${evidenceSteps([
      ['Report period', row.report_period],
      ['Report control', reportControl],
      ['Report extracted appendix value', money(report.parsed_alternative_value)],
      ['Source schema', row.source_schema || report.source_schema || '—'],
      ['Project / solicitation', row.project_number || row.solicitation || '—'],
      ['Supplier display', b11VendorName(row)],
      ['Raw supplier summary', row.supplier_source_text || row.vendor_name || '—'],
      ['Vendor identity status', row.vendor_identity_status],
      ['Eligible for supplier grouping', row.vendor_identity_eligible_for_grouping ? 'Yes' : 'No'],
      ['Source procurement type', row.procurement_type_display || '—'],
      ['Award value', money(row.award_value)],
      ['Department', row.department || 'Not separately reported'],
      ['Internal / project reference', row.account_project_codes || '—'],
      ['Source details', row.source_details || '—'],
      ['Source locator', `doc${row.report_document_id} / p${row.source_page} / t${row.source_table} / r${row.source_row}`],
      ['Attachment resolution', row.source_url_resolution],
      ['Historical graph URL changed?', row.source_url_changed_since_graph ? 'Yes — exact-title live agenda attachment resolved' : 'No']
    ])}
    <div class="drawer-callout"><strong>Interpretation boundary</strong><p>This is an HRM quarterly report-controlled Alternative Awards / Alternative Procurement appendix row. It is not an invoice or payment, not a complete procurement record, and not proof of lack of competition, contract amendment total or final paid value.</p></div>
    ${rawCells ? `<div class="drawer-section"><h3>Raw extracted table cells</h3><pre class="b11-raw-source">${escapeHtml(rawCells)}</pre></div>` : ''}
    <div class="drawer-section"><h3>Source links</h3><div class="drawer-source-list">
      ${liveUrl ? `<a class="source-link" href="${escapeHtml(liveUrl)}" target="_blank" rel="noreferrer">Current resolved report attachment ↗</a>` : ''}
      ${row.source_url_changed_since_graph && graphUrl ? `<a class="source-link" href="${escapeHtml(graphUrl)}" target="_blank" rel="noreferrer">Historical graph attachment URL ↗</a>` : ''}
      ${agendaUrl ? `<a class="source-link" href="${escapeHtml(agendaUrl)}" target="_blank" rel="noreferrer">Owning Council agenda ↗</a>` : ''}
    </div></div>`
  });
};

b11BindEvents = function b11BindEventsRefined() {
  $$('#content [data-build011-row]').forEach(element => element.addEventListener('click', () => b11ShowRow(element.dataset.build011Row)));
  const query = $('#b11-procurement-search');
  if (query) query.addEventListener('input', event => { state.build011ProcurementQuery = event.target.value; render(); });
  const period = $('#b11-procurement-period');
  if (period) period.addEventListener('change', event => { state.build011ProcurementPeriod = event.target.value; render(); });
  const department = $('#b11-procurement-department');
  if (department) department.addEventListener('change', event => { state.build011ProcurementDepartment = event.target.value; render(); });

  // Only Build 011 investigation cards injected into Vendors are created after the
  // existing Build 008/009/010 binders have run. Cards on Overview/Investigations
  // were already bound by the base render and must not receive a second listener.
  $$('#content .b11-procurement [data-build008-investigation-id]').forEach(element => {
    element.addEventListener('click', () => b8ShowInvestigation(element.dataset.build008InvestigationId));
  });
};
