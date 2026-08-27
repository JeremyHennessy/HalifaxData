/* Build 014 — defensible cross-domain links from amendment evidence.
 * Links use exact/canonical source identifiers only. No fuzzy vendor or project-name joins.
 */

function b14CanonicalRef(value) {
  return String(value || '')
    .trim()
    .toUpperCase()
    .replace(/^HRM[\s-]*/i, '')
    .replace(/\s*-\s*/g, '-')
    .replace(/\s+/g, '-');
}

function b14CanonicalToken(value) {
  return ` ${String(value || '').toUpperCase().replace(/[^A-Z0-9]+/g, ' ').trim()} `;
}

function b14MeetingNameKey(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function b14ProcurementMatches(row) {
  const refs = (row?.procurement_refs || []).map(b14CanonicalRef).filter(Boolean);
  if (!refs.length || state.optional?.procurement?.status !== 'ready') return [];
  const refSet = new Set(refs);
  return getRows(state.optional.procurement.data).filter(record => {
    const solicitation = b14CanonicalRef(first(record, ['solicitation', 'award_id', 'tender_id'], ''));
    return solicitation && refSet.has(solicitation);
  });
}

function b14CapitalMatches(row) {
  if (state.optional?.capital?.status !== 'ready') return [];
  const haystack = b14CanonicalToken(`${row?.name_source || ''} ${row?.reason_source || ''} ${(row?.source_cells || []).join(' ')}`);
  return getRows(state.optional.capital.data).filter(record => {
    const code = String(first(record, ['project_code', 'project_number', 'project_no'], '') || '').trim();
    if (code.length < 5 || !/[A-Za-z]/.test(code)) return false;
    const token = b14CanonicalToken(code).trim();
    return token && haystack.includes(` ${token} `);
  });
}

function b14CouncilMatches(row) {
  if (state.optional?.council?.status !== 'ready') return [];
  const targetDate = String(row?.report_date || '');
  const targetMeeting = 'audit and finance standing committee';
  return getRows(state.optional.council.data).filter(record => {
    const startDate = String(first(record, ['start_date', 'date'], '') || '').slice(0, 10);
    const meetingName = b14MeetingNameKey(first(record, ['meeting_name', 'meeting_type'], ''));
    return startDate === targetDate && meetingName === targetMeeting;
  });
}

function b14RelatedForObservation(row) {
  return {
    procurement: b14ProcurementMatches(row),
    capital: b14CapitalMatches(row),
    council: b14CouncilMatches(row)
  };
}

function b14Unique(records, keyFn) {
  const seen = new Set();
  return records.filter(record => {
    const key = keyFn(record);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function b14RelatedForTrajectory(trajectory) {
  const observations = (trajectory?.observation_ids || []).map(id => b14Observations().find(row => row.id === id)).filter(Boolean);
  const related = observations.map(b14RelatedForObservation);
  return {
    procurement: b14Unique(related.flatMap(item => item.procurement), record => `${first(record, ['solicitation', 'award_id'], '')}|${first(record, ['vendor_name'], '')}|${first(record, ['awarded_date'], '')}`),
    capital: b14Unique(related.flatMap(item => item.capital), record => `${first(record, ['project_code'], '')}|${first(record, ['project_id'], '')}`),
    council: b14Unique(related.flatMap(item => item.council), record => String(first(record, ['meeting_id'], '')))
  };
}

function b14ProcurementCard(record) {
  const solicitation = first(record, ['solicitation', 'award_id'], '—');
  const vendor = first(record, ['vendor_name'], 'Vendor not published');
  const amount = first(record, ['original_award_value', 'current_contract_value'], null);
  const date = String(first(record, ['awarded_date'], '') || '').slice(0, 10);
  return `<div class="b14-related-card"><strong>Public tender ${escapeHtml(solicitation)}</strong><span>${escapeHtml(vendor)}${amount != null ? ` · ${money(amount)}` : ''}${date ? ` · ${escapeHtml(b14Date(date))}` : ''}</span><small>${escapeHtml(first(record, ['description'], ''))}</small><span class="b14-related-basis">Join: same solicitation / source contract reference after HRM-prefix + whitespace/hyphen normalization</span></div>`;
}

function b14CapitalCard(record) {
  const code = first(record, ['project_code'], '—');
  return `<div class="b14-related-card"><strong>Capital project ${escapeHtml(code)}</strong><span>${escapeHtml(first(record, ['project_name'], ''))}</span><small>${escapeHtml(first(record, ['location_description', 'work_description'], ''))}</small><span class="b14-related-basis">Join: exact capital project-code token published in the amendment row</span></div>`;
}

function b14CouncilCard(record) {
  const url = safeUrl(first(record, ['meeting_url', 'agenda_html_url', 'agenda_pdf_url'], ''));
  const name = first(record, ['meeting_name', 'meeting_type'], 'Audit & Finance Standing Committee');
  const date = String(first(record, ['start_date'], '') || '').slice(0, 10);
  return `<div class="b14-related-card"><strong>${escapeHtml(name)}</strong><span>${date ? escapeHtml(b14Date(date)) : 'Same-date committee calendar record'}</span><small>Calendar/document context only; this link does not establish approval of an amendment.</small><span class="b14-related-basis">Join: exact report date + canonical Audit & Finance Standing Committee name</span>${url ? `<a class="source-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Open committee record ↗</a>` : ''}</div>`;
}

function b14EmptyRelatedCard(title, detail) {
  return `<div class="b14-related-card b14-related-empty"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail)}</span><small>No relationship is inferred from similar vendor names, project names or descriptive text.</small></div>`;
}

function b14RelatedHtml(related) {
  const procurement = related.procurement.length
    ? related.procurement.map(b14ProcurementCard).join('')
    : b14EmptyRelatedCard('No exact procurement award link', 'No source contract reference matched the checked public-tender solicitation IDs under the documented normalization rule.');
  const capital = related.capital.length
    ? related.capital.map(b14CapitalCard).join('')
    : b14EmptyRelatedCard('No exact capital project-code link', 'No checked capital project code appears as an exact token in this amendment evidence.');
  const council = related.council.length
    ? related.council.map(b14CouncilCard).join('')
    : b14EmptyRelatedCard('No same-date committee calendar link', 'No checked Audit & Finance calendar record matched this report date under the exact date/name rule.');
  return `<div class="drawer-section b14-related-records"><h3>Related checked records</h3><p class="table-note">Deterministic source relationships only. Missing links remain missing rather than being filled by fuzzy matching.</p><div class="b14-related-grid">${procurement}${capital}${council}</div></div>`;
}

function b14LinkageStats() {
  const observations = b14Observations();
  let procurementObservations = 0;
  let capitalObservations = 0;
  let councilObservations = 0;
  const procurementRecords = new Set();
  const capitalRecords = new Set();
  const councilRecords = new Set();
  for (const row of observations) {
    const related = b14RelatedForObservation(row);
    if (related.procurement.length) procurementObservations += 1;
    if (related.capital.length) capitalObservations += 1;
    if (related.council.length) councilObservations += 1;
    related.procurement.forEach(record => procurementRecords.add(`${first(record, ['solicitation', 'award_id'], '')}|${first(record, ['vendor_name'], '')}|${first(record, ['awarded_date'], '')}`));
    related.capital.forEach(record => capitalRecords.add(`${first(record, ['project_code'], '')}|${first(record, ['project_id'], '')}`));
    related.council.forEach(record => councilRecords.add(String(first(record, ['meeting_id'], ''))));
  }
  return {
    observations: observations.length,
    procurement_observations: procurementObservations,
    procurement_records: procurementRecords.size,
    capital_observations: capitalObservations,
    capital_records: capitalRecords.size,
    council_observations: councilObservations,
    council_records: councilRecords.size,
    fuzzy_links_created: 0
  };
}

const b14ShowObservationBeforeLinks = b14ShowObservation;
b14ShowObservation = function b14ShowObservationWithLinks(id) {
  const row = b14Observations().find(item => item.id === id);
  b14ShowObservationBeforeLinks(id);
  if (!row || !$('#drawer-body')) return;
  $('#drawer-body').insertAdjacentHTML('beforeend', b14RelatedHtml(b14RelatedForObservation(row)));
};

const b14ShowTrajectoryBeforeLinks = b14ShowTrajectory;
b14ShowTrajectory = function b14ShowTrajectoryWithLinks(contractKey) {
  const row = b14Trajectories().find(item => item.contract_key === contractKey);
  b14ShowTrajectoryBeforeLinks(contractKey);
  if (!row || !$('#drawer-body')) return;
  $('#drawer-body').insertAdjacentHTML('beforeend', b14RelatedHtml(b14RelatedForTrajectory(row)));
};
