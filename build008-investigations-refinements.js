/* Build 008 analytical refinements after visual review.
 * This file only tightens derived screening behavior. Source artifacts and ingestion remain untouched.
 */

b8Priority = function b8PriorityRefined(score) {
  return score >= 90 ? 'high' : score >= 70 ? 'review' : 'context';
};

function b8CanonicalProcurementEntity(raw) {
  const value = normalize(raw);
  if (value.includes('halifax regional municipality')) return 'Halifax Regional Municipality (HRM)';
  if (value.includes('halifax water')) return 'Halifax Water';
  if (value.includes('halifax public libraries')) return 'Halifax Public Libraries';
  return String(raw || 'Unknown entity').trim() || 'Unknown entity';
}

b8VendorExactGroups = function b8VendorExactGroupsRefined(rows = getRows(datasetStatus('procurement').data)) {
  const entityTotals = new Map();
  const groups = new Map();
  for (const row of rows) {
    const amount = b8Number(row.original_award_value) || 0;
    const entity = b8CanonicalProcurementEntity(row.entity);
    const vendor = String(row.vendor_name || 'Unknown vendor').trim() || 'Unknown vendor';
    entityTotals.set(entity, (entityTotals.get(entity) || 0) + amount);
    const key = `${entity}||${vendor}`;
    const group = groups.get(key) || {
      entity, vendor, value: 0, count: 0, rows: [], rawEntities: new Set(), dates: []
    };
    group.value += amount;
    group.count += 1;
    group.rows.push(row);
    if (row.entity) group.rawEntities.add(row.entity);
    if (row.awarded_date) group.dates.push(row.awarded_date);
    groups.set(key, group);
  }
  return [...groups.values()].map(group => ({
    ...group,
    entityTotal: entityTotals.get(group.entity) || 0,
    share: entityTotals.get(group.entity) ? group.value / entityTotals.get(group.entity) : 0
  }));
};

b8ProcurementInvestigations = function b8ProcurementInvestigationsRefined(rows = getRows(datasetStatus('procurement').data)) {
  const groups = b8VendorExactGroups(rows).filter(group =>
    group.value > 0 && (group.count >= 2 || group.share >= 0.05 || group.value >= 1000000)
  );
  const maxValue = Math.max(1, ...groups.map(group => group.value));
  return groups.map(group => {
    const materiality = b8ScoreMateriality(group.value, maxValue);
    const deviation = b8Clamp(group.share * 500);
    const persistence = b8Clamp(20 + Math.log2(Math.max(1, group.count)) * 18);
    const evidence = 90;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    const dates = group.dates.sort();
    const rawEntities = [...group.rawEntities].sort((a, b) => a.localeCompare(b));
    return {
      id: `b8-proc-${b8Slug(`${group.entity}-${group.vendor}`)}`,
      domain: 'Procurement', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${group.vendor} concentration & repeat awards`,
      detail: `${numberFmt.format(group.count)} exact-name public-tender award row${group.count === 1 ? '' : 's'} · ${decimalFmt.format(group.share * 100)}% of collected ${group.entity} award value`,
      materialityText: `${compactMoney(group.value)} published award value`,
      scope: `${group.entity} · exact raw vendor identity; reporting-body labels conservatively canonicalized; not final paid value`,
      sourceIds: b8Unique(group.rows.map(row => row.source_id)),
      evidenceRows: [
        ['Reporting body', group.entity],
        ['Source entity label(s)', rawEntities.join(' · ') || group.entity],
        ['Exact raw vendor', group.vendor],
        ['Collected award rows', numberFmt.format(group.count)],
        ['Published award value', money(group.value)],
        ['Share of reporting-body collected award value', `${decimalFmt.format(group.share * 100)}%`],
        ['Award-date span', dates.length ? `${dateOnly(dates[0])} → ${dateOnly(dates[dates.length - 1])}` : '—']
      ],
      caveat: 'Concentration and repeat-award frequency are calculated only from collected public-tender award rows using the exact published vendor name. They do not establish lack of competition, alternative procurement, amendments, final paid value, or improper spending.'
    };
  }).sort((a, b) => b.score - a.score);
};

b8VendorCandidates = function b8VendorCandidatesRefined(rows = getRows(datasetStatus('procurement').data)) {
  const groups = new Map();
  for (const row of rows) {
    const raw = String(row.vendor_name || '').trim();
    const stem = b8VendorStem(raw);
    if (!raw || stem.length < 5) continue;
    const entity = b8CanonicalProcurementEntity(row.entity);
    const key = `${entity}||${stem}`;
    const group = groups.get(key) || {
      id: `b8-vendor-candidate-${b8Slug(key)}`,
      entity, stem, variants: new Map(), rows: [], rawEntities: new Set()
    };
    const variant = group.variants.get(raw) || { name: raw, value: 0, count: 0 };
    variant.value += b8Number(row.original_award_value) || 0;
    variant.count += 1;
    group.variants.set(raw, variant);
    group.rows.push(row);
    if (row.entity) group.rawEntities.add(row.entity);
    groups.set(key, group);
  }
  const candidates = [...groups.values()].filter(group => group.variants.size > 1).map(group => {
    const variants = [...group.variants.values()].sort((a, b) => b.value - a.value);
    return {
      ...group,
      variants,
      combinedCandidateValue: variants.reduce((sum, item) => sum + item.value, 0)
    };
  }).sort((a, b) => b.combinedCandidateValue - a.combinedCandidateValue);
  build008VendorCandidateIndex = new Map(candidates.map(item => [item.id, item]));
  return candidates;
};

const b8FinancialInvestigationsUnrefined = b8FinancialInvestigations;
b8FinancialInvestigations = function b8FinancialInvestigationsRefined() {
  return b8FinancialInvestigationsUnrefined().filter(item => {
    const title = normalize(item.title);
    return !title.includes('$') &&
      !/\d/.test(title) &&
      !/\bbalance\b/.test(title) &&
      !title.includes('individual surpluses and reserves') &&
      !title.includes('accumulated surplus');
  });
};

b8DiverseTop = function b8DiverseTopRefined(items, limit = 8, maxPerDomain = 3) {
  const domains = [];
  const grouped = new Map();
  for (const item of items) {
    if (!grouped.has(item.domain)) {
      grouped.set(item.domain, []);
      domains.push(item.domain);
    }
    grouped.get(item.domain).push(item);
  }
  domains.sort((a, b) => (grouped.get(b)[0]?.score || 0) - (grouped.get(a)[0]?.score || 0));
  const selected = [];
  for (let round = 0; round < maxPerDomain && selected.length < limit; round++) {
    for (const domain of domains) {
      const item = grouped.get(domain)?.[round];
      if (item) selected.push(item);
      if (selected.length >= limit) break;
    }
  }
  return selected;
};

const b8ProcurementPanelsUnrefined = b8ProcurementPanels;
b8ProcurementPanels = function b8ProcurementPanelsRefined() {
  return b8ProcurementPanelsUnrefined().replace('entity/category share', 'reporting-body share');
};
