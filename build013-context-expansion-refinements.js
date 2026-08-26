/* Build 013 presentation refinements.
 * Keep the loaded-state Community Funding surface explicitly titled; the loading
 * and error states already carry this heading.
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
