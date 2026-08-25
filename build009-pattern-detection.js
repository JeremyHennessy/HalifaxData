/* Build 009 automated pattern + cross-domain detection.
 * Loaded after the verified Build 008 investigation layer/refinements.
 * This file derives analytical patterns client-side from released source-backed data.
 * It does not modify ingestion, normalized artifacts, source semantics, or payment-source safeguards.
 */

let build009PatternIndex = new Map();

function b9FiscalEnd(value) {
  const match = String(value || '').match(/(20\d{2})\s*\/\s*(\d{2})/);
  if (!match) return null;
  return Number(match[1]) + 1;
}

function b9LongestRun(values, predicate) {
  let longest = 0;
  let current = 0;
  for (const value of values) {
    if (predicate(value)) {
      current += 1;
      longest = Math.max(longest, current);
    } else current = 0;
  }
  return longest;
}

function b9ExactDescription(value) {
  return normalize(value).replace(/\s+/g, ' ').trim();
}

function b9BudgetSeries() {
  const groups = new Map();
  const add = (row, isCurrent) => {
    const businessUnit = String(row.business_unit || '').trim();
    const serviceArea = String(row.service_area || '').trim();
    const currentBudget = b8Number(row.current_budget);
    const fiscalYear = String(row.fiscal_year || row.current_budget_period || '').trim();
    const fiscalEnd = b9FiscalEnd(fiscalYear);
    if (!businessUnit || !serviceArea || currentBudget == null || currentBudget <= 0 || fiscalEnd == null) return;
    if (isCurrent && row.is_total) return;
    if (!isCurrent && row.row_kind && row.row_kind !== 'detail') return;
    const finalSource = isCurrent ? true : row.source_is_final === true;
    const key = `${normalize(businessUnit)}||${normalize(serviceArea)}`;
    const group = groups.get(key) || {
      key,
      businessUnit,
      serviceArea,
      businessUnitKey: normalize(businessUnit),
      serviceAreaKey: normalize(serviceArea),
      years: new Map(),
      nonFinalContext: 0
    };
    if (!finalSource) {
      group.nonFinalContext += 1;
      groups.set(key, group);
      return;
    }
    if (!group.years.has(fiscalEnd)) group.years.set(fiscalEnd, []);
    group.years.get(fiscalEnd).push({
      fiscalYear,
      fiscalEnd,
      businessUnit,
      serviceArea,
      currentBudget,
      priorBudget: b8Number(row.prior_budget),
      priorActual: b8Number(row.prior_actual),
      projection: b8Number(row.projection),
      sourceId: row.source_id,
      sourceStatus: isCurrent ? 'current released budget' : (row.source_status || 'final historical source'),
      isCurrent
    });
    groups.set(key, group);
  };

  const currentRows = typeof budgetServiceRows === 'function'
    ? budgetServiceRows()
    : getRows(datasetStatus('budget').data).filter(row => row.record_type === 'service_area_budget');
  currentRows.forEach(row => add(row, true));
  if (typeof build006Rows === 'function') build006Rows('budgetHistory').forEach(row => add(row, false));

  return [...groups.values()].map(group => {
    let ambiguousYears = 0;
    const observations = [...group.years.entries()].flatMap(([, rows]) => {
      if (rows.length !== 1) {
        ambiguousYears += 1;
        return [];
      }
      return rows;
    }).sort((a, b) => a.fiscalEnd - b.fiscalEnd);
    return { ...group, observations, ambiguousYears };
  });
}

function b9BudgetPatternInvestigations() {
  const raw = [];
  for (const series of b9BudgetSeries()) {
    const points = series.observations;
    if (points.length < 2) continue;
    const changes = [];
    for (let i = 1; i < points.length; i++) {
      const prior = points[i - 1];
      const current = points[i];
      const delta = current.currentBudget - prior.currentBudget;
      const fraction = prior.currentBudget > 0 ? delta / prior.currentBudget : null;
      changes.push({ prior, current, delta, fraction, consecutive: current.fiscalEnd - prior.fiscalEnd === 1 });
    }
    const consecutive = changes.filter(change => change.consecutive);
    const positiveRun = b9LongestRun(consecutive, change => change.delta > 0);
    const positiveConsecutive = consecutive.filter(change => change.delta > 0).length;
    const pressureCycles = points.filter(point =>
      point.priorBudget != null && point.priorBudget > 0 && point.projection != null &&
      point.projection > point.priorBudget && point.currentBudget > point.priorBudget
    );
    const first = points[0];
    const latest = points[points.length - 1];
    const spanYears = latest.fiscalEnd - first.fiscalEnd;
    const totalGrowth = latest.currentBudget - first.currentBudget;
    const totalGrowthFraction = first.currentBudget > 0 ? totalGrowth / first.currentBudget : null;
    const cagr = spanYears > 0 && first.currentBudget > 0 && latest.currentBudget > 0
      ? Math.pow(latest.currentBudget / first.currentBudget, 1 / spanYears) - 1
      : null;
    const latestChange = changes[changes.length - 1] || null;
    const maxProjectionFraction = Math.max(0, ...pressureCycles.map(point => (point.projection - point.priorBudget) / point.priorBudget));
    const patternAmount = Math.max(0, totalGrowth, latestChange?.delta || 0, ...pressureCycles.map(point => point.projection - point.priorBudget));
    const patternFraction = Math.max(0, totalGrowthFraction || 0, cagr || 0, latestChange?.fraction || 0, maxProjectionFraction);
    const qualifies = patternAmount >= 250000 && (
      points.length >= 3 || positiveConsecutive >= 1 || pressureCycles.length >= 1 || patternFraction >= 0.08
    );
    if (!qualifies) continue;
    raw.push({
      series, points, changes, consecutive, positiveRun, positiveConsecutive, pressureCycles,
      first, latest, spanYears, totalGrowth, totalGrowthFraction, cagr, latestChange,
      maxProjectionFraction, patternAmount, patternFraction
    });
  }

  const maxAmount = Math.max(1, ...raw.map(item => item.patternAmount));
  return raw.map(item => {
    const materiality = b8ScoreMateriality(item.patternAmount, maxAmount);
    const deviation = b8ScoreDeviation(item.patternFraction, 180);
    const persistence = b8Clamp(
      22 + item.points.length * 7 + item.positiveRun * 18 + item.pressureCycles.length * 13 +
      Math.min(12, item.positiveConsecutive * 4)
    );
    const evidence = item.series.ambiguousYears ? 91 : 98;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    const sourceIds = b8Unique(item.points.map(point => point.sourceId));
    const patternType = item.positiveRun >= 2
      ? 'persistent budget growth'
      : item.pressureCycles.length >= 2
        ? 'recurring projection pressure'
        : 'multi-year budget growth';
    const trajectory = item.points.map(point => `${point.fiscalYear}: ${compactMoney(point.currentBudget)}`).join(' → ');
    return {
      id: `b9-budget-${b8Slug(item.series.key)}`,
      domain: 'Budget', kind: 'fiscal', pattern: true, patternType,
      priority: b8Priority(score), score, materiality, deviation, persistence, evidence,
      title: `${item.series.serviceArea} ${patternType}`,
      detail: `${numberFmt.format(item.points.length)} final-source fiscal observations · ${item.first.fiscalYear} → ${item.latest.fiscalYear} ${b8SignedMoney(item.totalGrowth)} (${b8PercentFraction(item.totalGrowthFraction)})${item.cagr == null ? '' : ` · annualized ${b8PercentFraction(item.cagr)}`}`,
      materialityText: `${compactMoney(item.patternAmount)} largest positive multi-period pressure measure`,
      scope: `${item.series.businessUnit} · exact normalized business-unit + service-area identity across final/current source states only`,
      sourceIds,
      businessUnit: item.series.businessUnit,
      serviceArea: item.series.serviceArea,
      businessUnitKey: item.series.businessUnitKey,
      serviceAreaKey: item.series.serviceAreaKey,
      evidenceRows: [
        ['Business unit', item.series.businessUnit],
        ['Service area', item.series.serviceArea],
        ['Final-source observations', numberFmt.format(item.points.length)],
        ['Budget trajectory', trajectory],
        ['Consecutive positive changes', numberFmt.format(item.positiveConsecutive)],
        ['Longest consecutive increase run', numberFmt.format(item.positiveRun)],
        ['Projection-above-budget + following-budget-increase cycles', numberFmt.format(item.pressureCycles.length)],
        ['First-to-latest movement', `${b8SignedMoney(item.totalGrowth)} (${b8PercentFraction(item.totalGrowthFraction)})`],
        ['Annualized growth', item.cagr == null ? '—' : b8PercentFraction(item.cagr)],
        ['Ambiguous duplicate fiscal years excluded', numberFmt.format(item.series.ambiguousYears)],
        ['Non-final historical rows kept out of persistence scoring', numberFmt.format(item.series.nonFinalContext)]
      ],
      caveat: 'This pattern uses only exact normalized business-unit/service-area matches from final historical source states plus the current released budget row. Draft, proposed and pre-COVID source states are not promoted into persistence scoring. Budget growth or projection pressure is a review signal, not evidence of waste or overspending.'
    };
  }).sort((a, b) => b.score - a.score);
}

function b9ProcurementPatternInvestigations(rows = getRows(datasetStatus('procurement').data)) {
  const groups = b8VendorExactGroups(rows).filter(group => group.value > 0);
  const raw = [];
  for (const group of groups) {
    const years = new Map();
    const descriptions = new Map();
    for (const row of group.rows) {
      const year = Number(String(row.awarded_date || '').slice(0, 4));
      if (Number.isFinite(year) && year >= 2000 && year <= 2100) {
        const bucket = years.get(year) || { year, value: 0, count: 0, rows: [] };
        bucket.value += b8Number(row.original_award_value) || 0;
        bucket.count += 1;
        bucket.rows.push(row);
        years.set(year, bucket);
      }
      const desc = b9ExactDescription(row.description);
      if (desc.length >= 12) descriptions.set(desc, (descriptions.get(desc) || 0) + 1);
    }
    const annual = [...years.values()].sort((a, b) => a.year - b.year);
    if (annual.length < 2 && group.count < 4) continue;
    const activeYears = annual.map(item => item.year);
    const yearRuns = [];
    for (let i = 0; i < annual.length; i++) {
      if (i === 0 || annual[i].year !== annual[i - 1].year + 1) yearRuns.push(1);
      else yearRuns[yearRuns.length - 1] += 1;
    }
    const activeStreak = Math.max(1, ...yearRuns);
    const repeatYears = annual.filter(item => item.count >= 2).length;
    const priorYear = annual.length >= 2 ? annual[annual.length - 2] : null;
    const latestYear = annual[annual.length - 1] || null;
    const latestConsecutive = priorYear && latestYear && latestYear.year === priorYear.year + 1;
    const latestDelta = latestConsecutive ? latestYear.value - priorYear.value : null;
    const latestFraction = latestDelta != null && priorYear.value > 0 ? latestDelta / priorYear.value : null;
    let acceleration = null;
    if (annual.length >= 3) {
      const a = annual[annual.length - 3], b = annual[annual.length - 2], c = annual[annual.length - 1];
      if (b.year === a.year + 1 && c.year === b.year + 1) {
        const firstDelta = b.value - a.value;
        const secondDelta = c.value - b.value;
        if (firstDelta > 0 && secondDelta > firstDelta) acceleration = secondDelta - firstDelta;
      }
    }
    const exactDescriptionRepeats = Math.max(0, ...[...descriptions.values()].filter(count => count >= 2));
    const patternFraction = Math.max(0, group.share || 0, latestFraction || 0);
    const qualifies = group.count >= 4 || annual.length >= 2 || activeStreak >= 2 || group.share >= 0.05;
    if (!qualifies) continue;
    raw.push({ group, annual, activeYears, activeStreak, repeatYears, latestDelta, latestFraction, acceleration, exactDescriptionRepeats, patternFraction });
  }

  const maxValue = Math.max(1, ...raw.map(item => item.group.value));
  return raw.map(item => {
    const materiality = b8ScoreMateriality(item.group.value, maxValue);
    const deviation = b8Clamp(Math.max((item.group.share || 0) * 450, Math.max(0, item.latestFraction || 0) * 150));
    const persistence = b8Clamp(
      18 + item.annual.length * 8 + item.activeStreak * 11 + item.repeatYears * 6 +
      Math.log2(Math.max(1, item.group.count)) * 7 + (item.acceleration != null ? 10 : 0)
    );
    const evidence = 91;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    const rawEntities = [...(item.group.rawEntities || [])].sort((a, b) => a.localeCompare(b));
    const annualText = item.annual.map(year => `${year.year}: ${compactMoney(year.value)} / ${year.count} award${year.count === 1 ? '' : 's'}`).join(' · ');
    const patternType = item.acceleration != null ? 'accelerating award value' : item.activeStreak >= 3 ? 'persistent annual awards' : 'multi-year repeat awards';
    return {
      id: `b9-proc-${b8Slug(`${item.group.entity}-${item.group.vendor}`)}`,
      domain: 'Procurement', kind: 'fiscal', pattern: true, patternType,
      priority: b8Priority(score), score, materiality, deviation, persistence, evidence,
      title: `${item.group.vendor} ${patternType}`,
      detail: `${numberFmt.format(item.group.count)} exact-name public-tender awards across ${numberFmt.format(item.annual.length)} active year${item.annual.length === 1 ? '' : 's'} · ${decimalFmt.format(item.group.share * 100)}% of collected ${item.group.entity} award value${item.latestDelta == null ? '' : ` · latest annual change ${b8SignedMoney(item.latestDelta)} (${b8PercentFraction(item.latestFraction)})`}`,
      materialityText: `${compactMoney(item.group.value)} published award value across exact-name history`,
      scope: `${item.group.entity} · exact published vendor identity; reporting-body labels conservatively canonicalized; not final paid value`,
      sourceIds: b8Unique(item.group.rows.map(row => row.source_id)),
      reportingBody: item.group.entity,
      vendorName: item.group.vendor,
      evidenceRows: [
        ['Reporting body', item.group.entity],
        ['Source entity label(s)', rawEntities.join(' · ') || item.group.entity],
        ['Exact raw vendor', item.group.vendor],
        ['Award rows', numberFmt.format(item.group.count)],
        ['Active award years', item.activeYears.join(' · ') || '—'],
        ['Longest consecutive active-year streak', numberFmt.format(item.activeStreak)],
        ['Years with multiple awards', numberFmt.format(item.repeatYears)],
        ['Annual award trajectory', annualText || '—'],
        ['Latest consecutive-year value change', item.latestDelta == null ? 'Not available' : `${b8SignedMoney(item.latestDelta)} (${b8PercentFraction(item.latestFraction)})`],
        ['Positive annual acceleration', item.acceleration == null ? 'Not detected' : b8SignedMoney(item.acceleration)],
        ['Largest exact-description repeat count', numberFmt.format(item.exactDescriptionRepeats)],
        ['Share of reporting-body collected award value', `${decimalFmt.format(item.group.share * 100)}%`]
      ],
      caveat: 'This pattern uses exact published vendor names in the collected public-tender award dataset. Multi-year awards, concentration, repeat descriptions or increasing annual value are screening conditions only. They do not establish lack of competition, contract amendments, final paid value, alternative procurement, or improper spending.'
    };
  }).sort((a, b) => b.score - a.score);
}

function b9SpendingSeries(rows = getRows(datasetStatus('spending').data)) {
  const groups = new Map();
  for (const row of rows) {
    if (!row.posting_date || b8Number(row.amount) == null) continue;
    const key = b8SpendingMatchKey(row);
    const group = groups.get(key) || { key, dates: new Map() };
    const date = String(row.posting_date);
    if (!group.dates.has(date)) group.dates.set(date, []);
    group.dates.get(date).push(row);
    groups.set(key, group);
  }
  const series = [];
  let ambiguousDates = 0;
  for (const group of groups.values()) {
    const points = [...group.dates.entries()].flatMap(([date, items]) => {
      if (items.length !== 1) {
        ambiguousDates += 1;
        return [];
      }
      return [{ date, row: items[0] }];
    }).sort((a, b) => a.date.localeCompare(b.date));
    if (points.length >= 2) series.push({ key: group.key, points });
  }
  return { series, ambiguousDates };
}

function b9SpendingTrajectoryInvestigations(rows = getRows(datasetStatus('spending').data)) {
  const grouped = b9SpendingSeries(rows);
  const raw = [];
  for (const series of grouped.series) {
    const points = series.points;
    const row = points[points.length - 1].row;
    const label = typeof spendingLabel === 'function' ? spendingLabel(row) : (row.business_unit || row.category || row.account || row.record_type || 'Source row');
    const normalizedLabel = normalize(label);
    if (/^(grand )?total\b/.test(normalizedLabel) || normalizedLabel === 'net total') continue;
    const deltas = [];
    for (let i = 1; i < points.length; i++) {
      const prior = points[i - 1], current = points[i];
      const delta = Number(current.row.amount) - Number(prior.row.amount);
      const fraction = Math.abs(Number(prior.row.amount)) >= 1000 ? delta / Math.abs(Number(prior.row.amount)) : null;
      deltas.push({ prior, current, delta, fraction, sign: Math.sign(delta) });
    }
    const maxStep = Math.max(0, ...deltas.map(item => Math.abs(item.delta)));
    const maxFraction = Math.max(0, ...deltas.map(item => Math.abs(item.fraction || 0)));
    const netDelta = Number(points[points.length - 1].row.amount) - Number(points[0].row.amount);
    const netFraction = Math.abs(Number(points[0].row.amount)) >= 1000 ? netDelta / Math.abs(Number(points[0].row.amount)) : null;
    const signs = deltas.map(item => item.sign);
    const longestPositive = b9LongestRun(signs, sign => sign > 0);
    const longestNegative = b9LongestRun(signs, sign => sign < 0);
    let reversals = 0;
    for (let i = 1; i < signs.length; i++) if (signs[i] && signs[i - 1] && signs[i] !== signs[i - 1]) reversals += 1;
    const latest = deltas[deltas.length - 1] || null;
    const priorDelta = deltas.length >= 2 ? deltas[deltas.length - 2] : null;
    const acceleratingIncrease = Boolean(latest && priorDelta && latest.delta > 0 && priorDelta.delta > 0 && latest.delta > priorDelta.delta * 1.25);
    const yoyPairs = [];
    const byDate = new Map(points.map(point => [point.date, point]));
    for (const point of points) {
      const year = Number(point.date.slice(0, 4));
      if (!Number.isFinite(year)) continue;
      const priorKey = `${year - 1}${point.date.slice(4)}`;
      const prior = byDate.get(priorKey);
      if (!prior) continue;
      const delta = Number(point.row.amount) - Number(prior.row.amount);
      const fraction = Math.abs(Number(prior.row.amount)) >= 1000 ? delta / Math.abs(Number(prior.row.amount)) : null;
      yoyPairs.push({ prior, current: point, delta, fraction });
    }
    const latestYoy = yoyPairs[yoyPairs.length - 1] || null;
    const persistent = Math.max(longestPositive, longestNegative) >= 2;
    const qualifies = maxStep >= 500000 && (points.length >= 3 || yoyPairs.length >= 1 || persistent || acceleratingIncrease || reversals >= 1);
    if (!qualifies) continue;
    const patternType = longestPositive >= 2
      ? 'persistent increase'
      : acceleratingIncrease
        ? 'accelerating increase'
        : reversals >= 1
          ? 'multi-period reversal'
          : latestYoy && latestYoy.delta > 0
            ? 'year-over-year increase'
            : 'multi-period movement';
    raw.push({
      series, points, row, label, normalizedLabel, deltas, maxStep, maxFraction, netDelta, netFraction,
      longestPositive, longestNegative, reversals, acceleratingIncrease, yoyPairs, latestYoy,
      persistent, patternType
    });
  }

  const maxMovement = Math.max(1, ...raw.map(item => item.maxStep));
  const investigations = raw.map(item => {
    const materiality = b8ScoreMateriality(item.maxStep, maxMovement);
    const deviation = b8Clamp(Math.max(item.maxFraction * 150, Math.abs(item.latestYoy?.fraction || 0) * 160));
    const persistence = b8Clamp(
      20 + item.points.length * 8 + Math.max(item.longestPositive, item.longestNegative) * 16 +
      item.yoyPairs.length * 7 + (item.acceleratingIncrease ? 10 : 0) + Math.min(12, item.reversals * 4)
    );
    const evidence = 87;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    const trajectory = item.points.map(point => `${dateOnly(point.date)}: ${compactMoney(point.row.amount)}`).join(' → ');
    return {
      id: `b9-spend-${b8Slug(item.series.key)}`,
      domain: 'Spending summaries', kind: 'fiscal', pattern: true, patternType: item.patternType,
      priority: b8Priority(score), score, materiality, deviation, persistence, evidence,
      title: `${item.label} ${item.patternType} trajectory`,
      detail: `${numberFmt.format(item.points.length)} unambiguous quarterly source-row observations · net ${b8SignedMoney(item.netDelta)}${item.netFraction == null ? '' : ` (${b8PercentFraction(item.netFraction)})`} · largest step ${compactMoney(item.maxStep)}${item.latestYoy == null ? '' : ` · latest same-period YoY ${b8SignedMoney(item.latestYoy.delta)} (${b8PercentFraction(item.latestYoy.fraction)})`}`,
      materialityText: `${compactMoney(item.maxStep)} largest matched-row period movement`,
      scope: `${humanize(item.row.record_type || 'summary row')} · exact normalized label/context/amount-semantics series; ambiguous duplicate dates excluded`,
      sourceIds: b8Unique(item.points.map(point => point.row.source_id)),
      matchLabel: item.normalizedLabel,
      displayLabel: item.label,
      recordType: item.row.record_type,
      evidenceRows: [
        ['Matched source-row label', item.label],
        ['Record type', humanize(item.row.record_type)],
        ['Quarterly trajectory', trajectory],
        ['Unambiguous periods', numberFmt.format(item.points.length)],
        ['Net first-to-latest movement', `${b8SignedMoney(item.netDelta)}${item.netFraction == null ? '' : ` (${b8PercentFraction(item.netFraction)})`}`],
        ['Largest period step', compactMoney(item.maxStep)],
        ['Longest increase run', numberFmt.format(item.longestPositive)],
        ['Longest decrease run', numberFmt.format(item.longestNegative)],
        ['Direction reversals', numberFmt.format(item.reversals)],
        ['Same-period year-over-year comparisons', numberFmt.format(item.yoyPairs.length)],
        ['Latest same-period YoY', item.latestYoy == null ? 'Not available' : `${b8SignedMoney(item.latestYoy.delta)} (${b8PercentFraction(item.latestYoy.fraction)})`]
      ],
      caveat: 'This trajectory joins only unambiguous like-for-like official quarterly summary-table rows. It is not a transaction, invoice, vendor payment, project ledger, or proof of overspending. Direction changes may reflect timing, seasonality, accounting presentation or source-table scope.'
    };
  }).sort((a, b) => b.score - a.score);
  return { investigations, matchedSeries: grouped.series.length, ambiguousDates: grouped.ambiguousDates };
}

function b9CrossDomainInvestigations(budgetItems = b9BudgetPatternInvestigations(), spendingItems = b9SpendingTrajectoryInvestigations().investigations) {
  const currentBudgetRows = (typeof budgetServiceRows === 'function' ? budgetServiceRows() : [])
    .filter(row => !row.is_total && row.business_unit && row.service_area);
  const serviceCounts = new Map();
  for (const row of currentBudgetRows) {
    const key = normalize(row.service_area);
    serviceCounts.set(key, (serviceCounts.get(key) || 0) + 1);
  }

  const budgetByUnit = new Map();
  const budgetByUniqueService = new Map();
  for (const item of budgetItems) {
    if (!budgetByUnit.has(item.businessUnitKey)) budgetByUnit.set(item.businessUnitKey, []);
    budgetByUnit.get(item.businessUnitKey).push(item);
    if ((serviceCounts.get(item.serviceAreaKey) || 0) === 1) budgetByUniqueService.set(item.serviceAreaKey, item);
  }

  const candidates = new Map();
  for (const spending of spendingItems) {
    if (spending.recordType !== 'operating_expense_summary') continue;
    const key = spending.matchLabel;
    let budgetSet = budgetByUnit.get(key) || null;
    let scope = 'exact business-unit label';
    if (!budgetSet && budgetByUniqueService.has(key)) {
      budgetSet = [budgetByUniqueService.get(key)];
      scope = 'exact unique service-area label';
    }
    if (!budgetSet || !budgetSet.length) continue;
    const budget = [...budgetSet].sort((a, b) => b.score - a.score)[0];
    const id = `b9-cross-${b8Slug(`${key}-${scope}`)}`;
    const materiality = Math.max(budget.materiality, spending.materiality);
    const deviation = Math.max(budget.deviation, spending.deviation);
    const persistence = b8Clamp((budget.persistence + spending.persistence) / 2 + 10);
    const evidence = 92;
    const score = b8Clamp(b8OverallScore({ materiality, deviation, persistence, evidence }) + 5);
    const display = scope.includes('business-unit') ? budget.businessUnit : budget.serviceArea;
    candidates.set(id, {
      id,
      domain: 'Cross-domain', kind: 'fiscal', pattern: true, patternType: 'exact-label corroboration',
      priority: b8Priority(score), score, materiality, deviation, persistence, evidence,
      title: `${display} budget + quarterly spending corroboration`,
      detail: `${scope} links a multi-period budget pattern with an independent operating-expense-summary trajectory. The accounting views remain separate and their dollar values are not combined.`,
      materialityText: 'Two independent source-backed patterns · amounts intentionally not summed',
      scope: `${display} · ${scope} only`,
      sourceIds: b8Unique([...(budget.sourceIds || []), ...(spending.sourceIds || [])]),
      evidenceRows: [
        ['Exact shared normalized label', display],
        ['Match scope', scope],
        ['Budget pattern', budget.title],
        ['Budget pattern score', budget.score],
        ['Quarterly spending pattern', spending.title],
        ['Quarterly spending pattern score', spending.score],
        ['Accounting views combined?', 'No — corroboration only; dollars are not summed']
      ],
      caveat: 'Cross-domain corroboration means two released datasets contain independently interesting patterns under the same exact operating label. It does not prove the budget row and quarterly summary row use identical accounting scope, does not establish causation, and is not a finding of waste or wrongdoing.'
    });
  }
  return [...candidates.values()].sort((a, b) => b.score - a.score);
}

function b9AllPatternGroups() {
  const budget = b9BudgetPatternInvestigations();
  const procurement = b9ProcurementPatternInvestigations();
  const spendingAnalysis = b9SpendingTrajectoryInvestigations();
  const spending = spendingAnalysis.investigations;
  const cross = b9CrossDomainInvestigations(budget, spending);
  return { budget, procurement, spending, spendingAnalysis, cross };
}

b8AllInvestigations = function b9PatternFirstAllInvestigations() {
  const patterns = b9AllPatternGroups();
  const fiscal = [
    ...patterns.cross.slice(0, 25),
    ...patterns.budget.slice(0, 35),
    ...patterns.procurement.slice(0, 45),
    ...patterns.spending.slice(0, 35),
    ...b8CompensationInvestigations().slice(0, 25),
    ...b8FinancialInvestigations().slice(0, 20)
  ].sort((a, b) => b.score - a.score);
  const quality = b8DataQualityInvestigations().sort((a, b) => b.score - a.score);
  build008InvestigationIndex = new Map([...fiscal, ...quality].map(item => [item.id, item]));
  build009PatternIndex = new Map([...patterns.budget, ...patterns.procurement, ...patterns.spending, ...patterns.cross].map(item => [item.id, item]));
  return { fiscal, quality };
};

function b9PatternCard(item, compact = false) {
  const tone = item.priority === 'high' ? 'bad' : item.priority === 'review' ? 'warn' : 'info';
  return `<button type="button" class="b8-investigation-card b9-pattern-card ${compact ? 'compact' : ''}" data-build009-investigation-id="${escapeHtml(item.id)}">
    <div class="b8-investigation-top"><span>${badge(item.domain, 'muted')}${badge(item.patternType || 'pattern', 'info')}${badge(item.priority === 'high' ? 'priority review' : item.priority === 'review' ? 'review' : 'context', tone)}</span><strong>${item.score}</strong></div>
    <h3>${escapeHtml(item.title)}</h3>
    <p>${escapeHtml(item.detail)}</p>
    ${item.materialityText ? `<div class="b8-materiality">${escapeHtml(item.materialityText)}</div>` : ''}
    ${compact ? '' : b8ScoreStrip(item)}
    <small>${escapeHtml(item.scope || 'Derived from released source-backed facts.')}</small>
  </button>`;
}

function b9SummaryPanel() {
  const patterns = b9AllPatternGroups();
  return `<section class="panel b9-pattern-summary"><header class="panel-header"><div><h2>Automated pattern engine</h2><p>Build 009 promotes persistence, acceleration and exact-label corroboration above isolated one-period movements. Cross-domain dollar values are never added together.</p></div></header><div class="panel-body">
    <div class="b8-inline-metrics">
      <div><strong>${numberFmt.format(patterns.budget.length)}</strong><span>multi-year budget patterns</span></div>
      <div><strong>${numberFmt.format(patterns.procurement.length)}</strong><span>procurement persistence patterns</span></div>
      <div><strong>${numberFmt.format(patterns.spending.length)}</strong><span>quarterly trajectories</span></div>
      <div><strong>${numberFmt.format(patterns.cross.length)}</strong><span>exact-label cross-domain corroborations</span></div>
    </div>
    <div class="b9-method-grid">
      <div><strong>Budget</strong><span>Final historical source states + current released rows; exact business-unit/service-area continuity only.</span></div>
      <div><strong>Procurement</strong><span>Exact vendor identity, annual award history, active-year persistence and concentration.</span></div>
      <div><strong>Spending summaries</strong><span>Full unambiguous row trajectories, direction runs, reversals, acceleration and same-period YoY comparisons.</span></div>
      <div><strong>Cross-domain</strong><span>Exact operating-label matches only; corroboration is displayed without asserting accounting equivalence or causality.</span></div>
    </div>
  </div></section>`;
}

function b9BudgetPanel() {
  const items = b9BudgetPatternInvestigations();
  const visible = items.slice(0, 10);
  const recurring = items.filter(item => /persistent|recurring/.test(item.patternType)).length;
  return `<section class="panel b9-budget-patterns"><header class="panel-header"><div><h2>Multi-year budget pressure patterns</h2><p>Exact service-area continuity across final historical sources and the current released budget. Draft/proposed/pre-COVID rows remain context only and do not increase persistence scores.</p></div></header><div class="panel-body"><div class="b8-inline-metrics"><div><strong>${numberFmt.format(items.length)}</strong><span>qualifying multi-year patterns</span></div><div><strong>${numberFmt.format(recurring)}</strong><span>persistent/recurring patterns</span></div><div><strong>${visible[0]?.materialityText ? escapeHtml(visible[0].materialityText) : '—'}</strong><span>largest ranked pattern measure</span></div></div>${visible.length ? `<div class="b8-investigation-grid">${visible.map(item => b9PatternCard(item)).join('')}</div>` : emptyState('No conservative multi-year budget patterns', 'No exact final-source label series meets the current materiality/persistence screen.')}</div></section>`;
}

function b9ProcurementPanel() {
  const rows = typeof filteredVendorRows === 'function' ? filteredVendorRows() : getRows(datasetStatus('procurement').data);
  const items = b9ProcurementPatternInvestigations(rows);
  const visible = items.slice(0, 10);
  const accelerated = items.filter(item => item.patternType === 'accelerating award value').length;
  return `<section class="panel b9-procurement-patterns"><header class="panel-header"><div><h2>Procurement persistence & acceleration</h2><p>Exact published vendor identities are tracked across award years. Candidate aliases remain outside these calculations unless separate identity evidence is established.</p></div></header><div class="panel-body"><div class="b8-inline-metrics"><div><strong>${numberFmt.format(items.length)}</strong><span>multi-year/repeat patterns</span></div><div><strong>${numberFmt.format(accelerated)}</strong><span>positive annual acceleration patterns</span></div><div><strong>${visible[0]?.materialityText ? escapeHtml(visible[0].materialityText) : '—'}</strong><span>largest ranked exact-name history</span></div></div>${visible.length ? `<div class="b8-investigation-grid">${visible.map(item => b9PatternCard(item)).join('')}</div>` : emptyState('No procurement persistence patterns', 'The current vendor filters leave no qualifying exact-name multi-year patterns.')}</div></section>`;
}

function b9SpendingPanel() {
  const rows = typeof filteredSpendingRows === 'function' ? filteredSpendingRows() : getRows(datasetStatus('spending').data);
  const analysis = b9SpendingTrajectoryInvestigations(rows);
  const visible = analysis.investigations.slice(0, 12);
  const persistent = analysis.investigations.filter(item => /persistent|accelerating/.test(item.patternType)).length;
  return `<section class="panel b9-spending-trajectories"><header class="panel-header"><div><h2>Full quarterly spending trajectories</h2><p>Series-level analysis replaces isolated pairwise emphasis: unambiguous like-for-like summary rows are evaluated across every available quarter, including same-period year-over-year comparisons where possible.</p></div></header><div class="panel-body"><div class="b8-inline-metrics"><div><strong>${numberFmt.format(analysis.matchedSeries)}</strong><span>unambiguous comparable series</span></div><div><strong>${numberFmt.format(analysis.investigations.length)}</strong><span>qualifying trajectory patterns</span></div><div><strong>${numberFmt.format(persistent)}</strong><span>persistent/accelerating patterns</span></div><div><strong>${numberFmt.format(analysis.ambiguousDates)}</strong><span>ambiguous key/dates excluded</span></div></div>${visible.length ? `<div class="b8-investigation-grid">${visible.map(item => b9PatternCard(item)).join('')}</div>` : emptyState('No multi-period spending trajectories', 'No unambiguous summary-row series meets the current materiality/persistence screen under these filters.')}</div></section>`;
}

function b9CrossDomainPanel() {
  const items = b9CrossDomainInvestigations();
  const visible = items.slice(0, 8);
  return `<section class="panel b9-cross-domain"><header class="panel-header"><div><h2>Cross-domain corroboration</h2><p>Independent budget and operating-expense-summary patterns are connected only when their operating labels match exactly after normalization. This is corroboration, not a forced accounting crosswalk.</p></div></header><div class="panel-body">${visible.length ? `<div class="b8-investigation-grid">${visible.map(item => b9PatternCard(item)).join('')}</div>` : emptyState('No exact-label cross-domain corroborations', 'No released budget-pattern label currently matches an operating-expense-summary trajectory under the conservative exact-label rule.')}</div></section>`;
}

function b9EnhanceOverview() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b9-pattern-summary')) return;
  const metrics = stack.querySelector('.metrics-grid');
  if (metrics) metrics.insertAdjacentHTML('afterend', b9SummaryPanel());
  const attention = [...stack.querySelectorAll('.panel')].find(panelElement => normalize(panelElement.querySelector('h2')?.textContent) === 'what deserves attention');
  if (attention && !stack.querySelector('.b9-cross-domain')) attention.insertAdjacentHTML('afterend', b9CrossDomainPanel());
}

function b9EnhanceBudget() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b9-budget-patterns')) return;
  const anchor = stack.querySelector('.b8-budget-pressure');
  if (anchor) anchor.insertAdjacentHTML('beforebegin', b9BudgetPanel());
  else {
    const metrics = stack.querySelector('.metrics-grid');
    if (metrics) metrics.insertAdjacentHTML('afterend', b9BudgetPanel());
  }
}

function b9EnhanceVendors() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b9-procurement-patterns')) return;
  const anchor = stack.querySelector('.b8-procurement-analysis');
  if (anchor) anchor.insertAdjacentHTML('beforebegin', b9ProcurementPanel());
  else {
    const metrics = stack.querySelector('.metrics-grid');
    if (metrics) metrics.insertAdjacentHTML('afterend', b9ProcurementPanel());
  }
}

function b9EnhanceSpending() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b9-spending-trajectories')) return;
  const anchor = stack.querySelector('.b8-spending-movement');
  if (anchor) anchor.insertAdjacentHTML('beforebegin', b9SpendingPanel());
  else {
    const metrics = stack.querySelector('.metrics-grid');
    if (metrics) metrics.insertAdjacentHTML('afterend', b9SpendingPanel());
  }
}

function b9EnhanceInvestigations() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b9-pattern-summary')) return;
  const metrics = stack.querySelector('.metrics-grid');
  if (metrics) metrics.insertAdjacentHTML('afterend', b9SummaryPanel());
}

function b9BindEvents() {
  $$('#content [data-build009-investigation-id]').forEach(element => element.addEventListener('click', () => b8ShowInvestigation(element.dataset.build009InvestigationId)));
}

const build008PatternRender = render;
render = function renderBuild009() {
  build008PatternRender();
  if (state.view === 'overview') b9EnhanceOverview();
  if (state.view === 'budget') b9EnhanceBudget();
  if (state.view === 'vendors') b9EnhanceVendors();
  if (state.view === 'spending') b9EnhanceSpending();
  if (state.view === 'signals') b9EnhanceInvestigations();
  b9BindEvents();
};
