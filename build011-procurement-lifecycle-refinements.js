/* Build 011 UI refinements.
 * Keep supplier grouping conservative: case/whitespace normalization only.
 * Candidate legal-name variants remain distinct unless the checked artifact itself
 * provides the same display identity.
 */

b11VendorKey = function b11VendorKeyExactDisplay(row) {
  return String(b11VendorName(row) || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('en-CA');
};

const b11AlternativeInvestigationsBase = b11AlternativeInvestigations;
b11AlternativeInvestigations = function b11AlternativeInvestigationsRefined() {
  return b11AlternativeInvestigationsBase().map(item => ({
    ...item,
    scope: `${item.scope}; not a complete procurement denominator`
  }));
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
    <div class="drawer-callout"><strong>Interpretation boundary</strong><p>This is an HRM quarterly report-controlled Alternative Awards / Alternative Procurement appendix row. It is not an invoice or payment, not a complete procurement record, and not proof of lack of competition, contract amendment total or final paid value.</p></div>
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
