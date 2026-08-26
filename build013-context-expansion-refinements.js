/* Build 013 presentation refinements.
 * Keep the loaded-state Community Funding surface explicitly titled and make the
 * historical amendment completeness boundary unambiguous. No data or scoring
 * thresholds change here.
 */

const b13FundingSectionBase = b13FundingSection;
b13FundingSection = function b13FundingSectionRefined() {
  const html = b13FundingSectionBase();
  if (state.build013Context?.status !== 'ready') return html;
  return html.replace(
    '<section class="b13-community-funding page-stack">',
    '<section class="b13-community-funding page-stack"><header class="b13-section-header"><p class="eyebrow">COMMUNITY FUNDING</p><h2>Community funding context</h2><p>Additional HRM grant and program-funding records shown with their approval stage, program rules and denominator boundaries.</p></header>'
  );
};

b13ShowAmendment = function b13ShowAmendmentRefined(id) {
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
    ])}<div class="drawer-callout"><strong>Interpretation boundary</strong><p>${escapeHtml(report.amount_semantics)} This is amendment-report evidence, not an invoice or payment, not a final paid value, and not a complete contract history or wrongdoing finding. The public report states that Private & Confidential amendment reports are excluded.</p></div><div class="drawer-section"><h3>Sources</h3><div class="drawer-source-list">${b13SourceLink(report.source_id)}${b13SourceLink('hrm-procurement-policy-2022-012-adm', 'Procurement policy')}</div></div>`
  });
};
