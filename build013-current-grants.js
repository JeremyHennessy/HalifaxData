/* Build 013 current-year Community Grants context.
 * Proposal-stage 2026/27 data is kept distinct from the final 2025/26 Council total.
 */

state.build013CurrentGrants = { status: 'loading', data: null, error: null };

fetch('./data/generated/community_grants_2026.json', { cache: 'no-store' })
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(data => {
    state.build013CurrentGrants = { status: 'ready', data, error: null };
    if (typeof render === 'function') render();
  })
  .catch(error => {
    state.build013CurrentGrants = { status: 'error', data: null, error: error.message };
    if (typeof render === 'function') render();
  });

function b13CurrentGrants() { return state.build013CurrentGrants?.data || null; }

function b13CurrentGrantPanelHtml() {
  const current = b13CurrentGrants();
  const prior = b13CommunityGrants();
  if (!current) return '';
  const applicationDelta = prior ? Number(current.applications_received) - Number(prior.applications_received) : null;
  const awardCountDelta = prior ? Number(current.proposed_awards) - Number(prior.staff_recommended_awards) : null;
  const awardValueDelta = prior ? Number(current.proposed_award_total) - Number(prior.staff_recommended_total) : null;
  return panel(
    '2026/27 Community Grants — current staff proposal',
    'Current proposal-stage control table. It is compared only with the 2025/26 staff-recommendation stage; the separate 2025 Council-approved total remains final for that year.',
    `<div class="b13-funding-stack b13-current-grants">
      <div class="notice b13-current-stage"><strong>Proposal stage — not final Council awards</strong><span>${escapeHtml(current.metadata.note)}</span></div>
      <div class="metrics-grid compact b13-funding-metrics">
        ${metricCard('Applications received', numberFmt.format(current.applications_received), applicationDelta == null ? 'Current proposal' : `${applicationDelta >= 0 ? '+' : ''}${numberFmt.format(applicationDelta)} vs 2025 applications`, 'neutral')}
        ${metricCard('Proposed awards', numberFmt.format(current.proposed_awards), awardCountDelta == null ? 'Staff proposal' : `${awardCountDelta >= 0 ? '+' : ''}${numberFmt.format(awardCountDelta)} vs 2025 staff recommendations`, 'neutral')}
        ${metricCard('Proposed award value', compactMoney(current.proposed_award_total), awardValueDelta == null ? 'Staff proposal' : `${b13SignedMoney(awardValueDelta)} vs 2025 staff recommendation`, 'accent')}
        ${metricCard('Program budget', compactMoney(current.program_budget), `${compactMoney(current.balance_after_proposed_transfer)} projected balance after proposed $65k transfer`, 'neutral')}
      </div>
      <div class="table-wrap"><table><thead><tr><th>Category</th><th class="numeric">Applications</th><th class="numeric">Proposed awards</th><th class="numeric">Proposed value</th></tr></thead><tbody>${current.categories.map(row => `<tr><td><strong>${escapeHtml(row.category)}</strong></td><td class="numeric">${numberFmt.format(row.applications)}</td><td class="numeric">${numberFmt.format(row.proposed_awards)}</td><td class="numeric"><strong>${money(row.proposed_award_value)}</strong></td></tr>`).join('')}<tr class="b13-total-row"><td><strong>Proposal-stage control</strong></td><td class="numeric"><strong>${numberFmt.format(current.applications_received)}</strong></td><td class="numeric"><strong>${numberFmt.format(current.proposed_awards)}</strong></td><td class="numeric"><strong>${money(current.proposed_award_total)}</strong></td></tr></tbody></table></div>
      <div class="b13-inline-summary">
        <div><strong>${money(current.program_budget)}</strong><span>program budget</span></div>
        <div><strong>${money(current.balance_after_proposed_awards)}</strong><span>remaining after proposed awards</span></div>
        <div><strong>${money(current.proposed_transfer_to_M310_8004)}</strong><span>proposed transfer to M310-8004</span></div>
        <div><strong>${money(current.balance_after_proposed_transfer)}</strong><span>projected balance after transfer</span></div>
      </div>
      <p class="table-note">${escapeHtml(current.caveat)}</p>
      <div class="b13-source-inline">${b13SourceLink(current.metadata.source_id)}</div>
    </div>`
  );
}

const b13EnhanceBenchmarksCurrentBase = b13EnhanceBenchmarks;
b13EnhanceBenchmarks = function b13EnhanceBenchmarksCurrent() {
  b13EnhanceBenchmarksCurrentBase();
  if (state.build013CurrentGrants?.status !== 'ready') return;
  const section = $('#content .b13-community-funding');
  if (!section || section.querySelector('.b13-current-grants-panel')) return;
  const notice = section.querySelector('.b13-funding-boundary');
  const html = `<div class="b13-current-grants-panel">${b13CurrentGrantPanelHtml()}</div>`;
  if (notice) notice.insertAdjacentHTML('afterend', html);
  else section.insertAdjacentHTML('afterbegin', html);
};
