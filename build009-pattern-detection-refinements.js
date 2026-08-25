/* Build 009 longitudinal-series and corroboration refinements.
 *
 * 1) PDF table context and token-count shape can change between quarterly reports
 *    even when the same exact source-row label/record type remains comparable.
 *    Full trajectories therefore use exact normalized record type + row label +
 *    amount semantics, while rejecting any date that becomes non-unique.
 * 2) Historical budget organization labels are not force-crosswalked. Cross-domain
 *    corroboration can instead use the released current Budget Pressure layer when
 *    its published business-unit label exactly matches an operating-expense series.
 *
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

function b9EvidenceValue(item, label) {
  const row = (item.evidenceRows || []).find(([key]) => key === label);
  return row ? row[1] : null;
}

function b9CurrentBudgetPressureCandidates() {
  return b8BudgetPressureInvestigations().flatMap(item => {
    const businessUnit = String(b9EvidenceValue(item, 'Business unit') || '').trim();
    const serviceArea = String(b9EvidenceValue(item, 'Service area') || '').trim();
    if (!businessUnit || !serviceArea) return [];
    return [{
      ...item,
      businessUnit,
      serviceArea,
      businessUnitKey: normalize(businessUnit),
      serviceAreaKey: normalize(serviceArea),
      corroborationBasis: 'current released service-area budget pressure'
    }];
  });
}

b9CrossDomainInvestigations = function b9CrossDomainInvestigationsRefined(
  budgetItems = b9BudgetPatternInvestigations(),
  spendingItems = b9SpendingTrajectoryInvestigations().investigations
) {
  const budgetCandidates = [
    ...budgetItems.filter(item => item.businessUnitKey).map(item => ({
      ...item,
      corroborationBasis: item.patternType || 'multi-year budget pattern'
    })),
    ...b9CurrentBudgetPressureCandidates()
  ];

  const budgetByUnit = new Map();
  for (const budget of budgetCandidates) {
    if (!budget.businessUnitKey) continue;
    if (!budgetByUnit.has(budget.businessUnitKey)) budgetByUnit.set(budget.businessUnitKey, []);
    budgetByUnit.get(budget.businessUnitKey).push(budget);
  }

  const candidates = new Map();
  for (const spending of spendingItems) {
    if (spending.recordType !== 'operating_expense_summary') continue;
    const sharedKey = spending.matchLabel;
    const matches = budgetByUnit.get(sharedKey) || [];
    if (!matches.length) continue;

    const budget = [...matches].sort((a, b) => b.score - a.score)[0];
    const businessUnit = budget.businessUnit;
    const serviceArea = budget.serviceArea || b9EvidenceValue(budget, 'Service area') || '—';
    const id = `b9-cross-${b8Slug(sharedKey)}`;
    const materiality = Math.max(budget.materiality, spending.materiality);
    const deviation = Math.max(budget.deviation, spending.deviation);
    const persistence = b8Clamp((budget.persistence + spending.persistence) / 2 + 10);
    const evidence = 94;
    const score = b8Clamp(b8OverallScore({ materiality, deviation, persistence, evidence }) + 5);

    candidates.set(id, {
      id,
      domain: 'Cross-domain',
      kind: 'fiscal',
      pattern: true,
      patternType: 'exact business-unit corroboration',
      priority: b8Priority(score),
      score,
      materiality,
      deviation,
      persistence,
      evidence,
      title: `${businessUnit} budget + quarterly spending corroboration`,
      detail: `Exact published business-unit label links ${budget.corroborationBasis} (${serviceArea}) with an independent operating-expense-summary trajectory. The accounting views remain separate and their dollar values are not combined.`,
      materialityText: 'Two independent source-backed patterns · amounts intentionally not summed',
      scope: `${businessUnit} · exact normalized published business-unit label only`,
      sourceIds: b8Unique([...(budget.sourceIds || []), ...(spending.sourceIds || [])]),
      evidenceRows: [
        ['Exact shared business-unit label', businessUnit],
        ['Budget evidence basis', budget.corroborationBasis],
        ['Budget service area', serviceArea],
        ['Budget lead', budget.title],
        ['Budget lead score', budget.score],
        ['Quarterly spending lead', spending.title],
        ['Quarterly spending lead score', spending.score],
        ['Accounting views combined?', 'No — corroboration only; dollars are not summed']
      ],
      caveat: 'Cross-domain corroboration means the released current budget evidence and an operating-expense-summary trajectory contain independently interesting patterns under the same exact published business-unit label. A shared label does not prove identical accounting scope, causation, overspending, waste or wrongdoing. Dollar amounts from the two accounting views are intentionally not combined.'
    });
  }
  return [...candidates.values()].sort((a, b) => b.score - a.score);
};
