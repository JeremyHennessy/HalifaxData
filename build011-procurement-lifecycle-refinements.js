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
