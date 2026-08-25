/* Build 009 longitudinal-series refinement.
 * PDF table context and token-count shape can change between quarterly reports even
 * when the same exact source-row label/record type remains comparable. For full
 * trajectories we therefore use exact normalized record type + row label + amount
 * semantics, while rejecting any date that becomes non-unique under that key.
 * Build 008's stricter pairwise movement matcher remains unchanged underneath.
 */

function b9SpendingSeriesKey(row) {
  const label = typeof spendingLabel === 'function'
    ? spendingLabel(row)
    : (row.business_unit || row.category || row.account || row.record_type || 'row');
  return [row.record_type || '', label, row.amount_semantics || ''].map(normalize).join('||');
}

b9SpendingSeries = function b9SpendingSeriesRefined(rows = getRows(datasetStatus('spending').data)) {
  const groups = new Map();
  for (const row of rows) {
    if (!row.posting_date || b8Number(row.amount) == null) continue;
    const key = b9SpendingSeriesKey(row);
    const group = groups.get(key) || { key, dates: new Map(), contexts: new Set(), tokenCounts: new Set() };
    const date = String(row.posting_date);
    if (!group.dates.has(date)) group.dates.set(date, []);
    group.dates.get(date).push(row);
    if (row.account || row.category) group.contexts.add(normalize(row.account || row.category));
    if (Array.isArray(row.values)) group.tokenCounts.add(row.values.length);
    groups.set(key, group);
  }

  const series = [];
  let ambiguousDates = 0;
  let ambiguousSeries = 0;
  for (const group of groups.values()) {
    let groupAmbiguity = false;
    const points = [...group.dates.entries()].flatMap(([date, items]) => {
      if (items.length !== 1) {
        ambiguousDates += 1;
        groupAmbiguity = true;
        return [];
      }
      return [{ date, row: items[0] }];
    }).sort((a, b) => a.date.localeCompare(b.date));
    if (groupAmbiguity) ambiguousSeries += 1;
    if (points.length >= 2) {
      series.push({
        key: group.key,
        points,
        contextVariants: group.contexts.size,
        tokenCountVariants: group.tokenCounts.size,
        hadAmbiguousDate: groupAmbiguity
      });
    }
  }
  return { series, ambiguousDates, ambiguousSeries };
};

const b9SpendingTrajectoryInvestigationsBeforeRefinement = b9SpendingTrajectoryInvestigations;
b9SpendingTrajectoryInvestigations = function b9SpendingTrajectoryInvestigationsRefined(rows = getRows(datasetStatus('spending').data)) {
  const result = b9SpendingTrajectoryInvestigationsBeforeRefinement(rows);
  for (const item of result.investigations) {
    item.scope = `${humanize(item.recordType || 'summary row')} · exact normalized record type + row label + amount semantics; non-unique dates excluded`;
    item.evidenceRows = [
      ...(item.evidenceRows || []),
      ['Longitudinal series key', 'Exact record type + exact normalized row label + amount semantics'],
      ['PDF context/token shape used as join identity?', 'No — layout metadata may vary between reports; any resulting same-date ambiguity is excluded']
    ];
    item.caveat = 'This trajectory joins only source rows with the same exact normalized record type, row label and amount semantics. PDF table context and monetary-token count are not used as longitudinal identity because report layouts can change; if relaxing those layout attributes creates multiple candidates on the same date, that date is excluded. This remains a quarterly summary-table comparison, not a transaction, invoice, vendor payment, project ledger, or proof of overspending.';
  }
  return result;
};
