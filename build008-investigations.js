/* Build 008 investigation layer.
 * Loaded last, over the verified Build 007 baseline.
 * Scope: derived analytical presentation only. No source, ingestion, normalization,
 * or evidence semantics are changed here.
 */

const BUILD008_SIGNAL_NAV = NAV.find(item => item[0] === 'signals');
if (BUILD008_SIGNAL_NAV) {
  BUILD008_SIGNAL_NAV[1] = 'Investigations';
  BUILD008_SIGNAL_NAV[3] = 'CROSS-DOMAIN REVIEW';
}

state.investigationDomain = 'all';
state.investigationPriority = 'all';

let build008InvestigationIndex = new Map();
let build008VendorCandidateIndex = new Map();

function b8Number(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
function b8Clamp(value, min = 0, max = 100) { return Math.min(max, Math.max(min, Number(value) || 0)); }
function b8Slug(value) { return normalize(value).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 120) || 'item'; }
function b8PctDelta(current, prior) {
  const a = b8Number(current); const b = b8Number(prior);
  if (a == null || b == null || Math.abs(b) < 1) return null;
  return (a - b) / Math.abs(b);
}
function b8ScoreMateriality(value, maxValue) {
  const v = Math.max(0, Math.abs(Number(value) || 0));
  const max = Math.max(1, Math.abs(Number(maxValue) || 0));
  return b8Clamp(Math.log1p(v) / Math.log1p(max) * 100);
}
function b8ScoreDeviation(fraction, multiplier = 250) {
  if (fraction == null || !Number.isFinite(Number(fraction))) return 0;
  return b8Clamp(Math.abs(Number(fraction)) * multiplier);
}
function b8Priority(score) { return score >= 78 ? 'high' : score >= 58 ? 'review' : 'context'; }
function b8OverallScore(parts) {
  return Math.round(
    b8Clamp(parts.materiality) * 0.44 +
    b8Clamp(parts.deviation) * 0.31 +
    b8Clamp(parts.persistence) * 0.15 +
    b8Clamp(parts.evidence) * 0.10
  );
}
function b8Direction(value) { return Number(value) > 0 ? 'increase' : Number(value) < 0 ? 'decrease' : 'no change'; }
function b8SignedMoney(value) {
  const n = b8Number(value);
  if (n == null) return '—';
  return `${n >= 0 ? '+' : '-'}${compactMoney(Math.abs(n))}`;
}
function b8PercentFraction(value) {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  return `${Number(value) >= 0 ? '+' : ''}${decimalFmt.format(Number(value) * 100)}%`;
}
function b8Unique(values) { return [...new Set(values.filter(Boolean))]; }
function b8SourceLinks(sourceIds) {
  const sources = b8Unique(sourceIds).map(sourceById).filter(Boolean);
  return sources.length ? `<div class="drawer-section"><h3>Official source records</h3><div class="drawer-source-list">${sources.map(source => `<a class="source-link" href="${escapeHtml(safeUrl(source.url) || '#')}" target="_blank" rel="noreferrer">${escapeHtml(source.name)} ↗</a>`).join('')}</div></div>` : '';
}
function b8ScoreStrip(item) {
  const labels = [
    ['Materiality', item.materiality],
    ['Deviation', item.deviation],
    ['Persistence', item.persistence],
    ['Evidence', item.evidence]
  ];
  return `<div class="b8-score-strip">${labels.map(([label, value]) => `<span><b>${escapeHtml(label)}</b>${Math.round(value)}</span>`).join('')}</div>`;
}
function b8InvestigationCard(item, compact = false) {
  const tone = item.priority === 'high' ? 'bad' : item.priority === 'review' ? 'warn' : 'info';
  return `<button type="button" class="b8-investigation-card ${compact ? 'compact' : ''}" data-build008-investigation-id="${escapeHtml(item.id)}">
    <div class="b8-investigation-top"><span>${badge(item.domain, 'muted')}${item.kind === 'quality' ? badge('data quality', 'info') : badge(item.priority === 'high' ? 'priority review' : item.priority === 'review' ? 'review' : 'context', tone)}</span><strong>${item.score}</strong></div>
    <h3>${escapeHtml(item.title)}</h3>
    <p>${escapeHtml(item.detail)}</p>
    ${item.materialityText ? `<div class="b8-materiality">${escapeHtml(item.materialityText)}</div>` : ''}
    ${compact ? '' : b8ScoreStrip(item)}
    <small>${escapeHtml(item.scope || 'Derived from released source-backed facts.')}</small>
  </button>`;
}

function b8BudgetPressureInvestigations() {
  const rows = (typeof budgetServiceRows === 'function' ? budgetServiceRows() : getRows(datasetStatus('budget').data).filter(row => row.record_type === 'service_area_budget'))
    .filter(row => !row.is_total && b8Number(row.prior_budget) != null && b8Number(row.current_budget) != null);
  const raw = rows.map(row => {
    const priorBudget = Number(row.prior_budget);
    const projection = b8Number(row.projection);
    const currentBudget = Number(row.current_budget);
    const priorActual = b8Number(row.prior_actual);
    const projectionDrift = projection == null ? null : projection - priorBudget;
    const nextBudgetGrowth = currentBudget - priorBudget;
    const projectionPct = projection == null ? null : b8PctDelta(projection, priorBudget);
    const budgetGrowthPct = b8PctDelta(currentBudget, priorBudget);
    const actualToBudgetPct = priorActual == null ? null : b8PctDelta(currentBudget, priorActual);
    const pressureAmount = Math.max(0, projectionDrift || 0, nextBudgetGrowth || 0);
    const pressureFraction = Math.max(0, projectionPct || 0, budgetGrowthPct || 0);
    const persistent = (projectionDrift || 0) > 0 && nextBudgetGrowth > 0;
    return { row, projectionDrift, nextBudgetGrowth, projectionPct, budgetGrowthPct, actualToBudgetPct, pressureAmount, pressureFraction, persistent };
  }).filter(item => item.pressureAmount > 0 || item.pressureFraction >= 0.08);
  const maxAmount = Math.max(1, ...raw.map(item => item.pressureAmount));
  return raw.map(item => {
    const materiality = b8ScoreMateriality(item.pressureAmount, maxAmount);
    const deviation = b8ScoreDeviation(item.pressureFraction, 220);
    const persistence = item.persistent ? 82 : ((item.projectionDrift || 0) > 0 || item.nextBudgetGrowth > 0 ? 48 : 20);
    const evidence = 96;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    const row = item.row;
    const details = [];
    if (item.projectionDrift != null) details.push(`2024/25 projection ${b8SignedMoney(item.projectionDrift)} vs 2024/25 budget (${b8PercentFraction(item.projectionPct)})`);
    details.push(`2025/26 budget ${b8SignedMoney(item.nextBudgetGrowth)} vs 2024/25 budget (${b8PercentFraction(item.budgetGrowthPct)})`);
    return {
      id: `b8-budget-${b8Slug(`${row.business_unit}-${row.service_area}`)}`,
      domain: 'Budget', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${row.service_area} budget pressure`,
      detail: details.join(' · '),
      materialityText: `${compactMoney(item.pressureAmount)} largest positive budget/projection movement`,
      scope: `${row.business_unit} · source-backed service-area budget row`,
      sourceIds: [row.source_id],
      evidenceRows: [
        ['Business unit', row.business_unit], ['Service area', row.service_area],
        ['2023/24 actual', money(row.prior_actual)], ['2024/25 budget', money(row.prior_budget)],
        ['2024/25 projection', money(row.projection)], ['2025/26 budget', money(row.current_budget)],
        ['Projection drift', item.projectionDrift == null ? '—' : b8SignedMoney(item.projectionDrift)],
        ['Next-budget growth', b8SignedMoney(item.nextBudgetGrowth)], ['Source ID', row.source_id]
      ],
      caveat: 'This ranking identifies service-area budget pressure from published budget/projection endpoints. It is not a finding of overspending or waste, and service-area rows are not summed into a synthetic municipality total.'
    };
  }).sort((a, b) => b.score - a.score);
}

function b8VendorExactGroups(rows = getRows(datasetStatus('procurement').data)) {
  const entityTotals = new Map();
  const groups = new Map();
  for (const row of rows) {
    const amount = b8Number(row.original_award_value) || 0;
    const entity = row.entity || 'Unknown entity';
    const vendor = row.vendor_name || 'Unknown vendor';
    entityTotals.set(entity, (entityTotals.get(entity) || 0) + amount);
    const key = `${entity}||${vendor}`;
    const group = groups.get(key) || { entity, vendor, value: 0, count: 0, rows: [], categories: new Set(), dates: [] };
    group.value += amount; group.count += 1; group.rows.push(row);
    if (row.category) group.categories.add(row.category);
    if (row.awarded_date) group.dates.push(row.awarded_date);
    groups.set(key, group);
  }
  return [...groups.values()].map(group => ({ ...group, entityTotal: entityTotals.get(group.entity) || 0, share: entityTotals.get(group.entity) ? group.value / entityTotals.get(group.entity) : 0 }));
}
function b8ProcurementInvestigations(rows = getRows(datasetStatus('procurement').data)) {
  const groups = b8VendorExactGroups(rows).filter(group => group.value > 0);
  const maxValue = Math.max(1, ...groups.map(group => group.value));
  const result = groups.map(group => {
    const materiality = b8ScoreMateriality(group.value, maxValue);
    const deviation = b8Clamp(group.share * 500);
    const persistence = b8Clamp(20 + Math.log2(Math.max(1, group.count)) * 18);
    const evidence = 88;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    const dates = group.dates.sort();
    return {
      id: `b8-proc-${b8Slug(`${group.entity}-${group.vendor}`)}`,
      domain: 'Procurement', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${group.vendor} award concentration`,
      detail: `${numberFmt.format(group.count)} exact-name award row${group.count === 1 ? '' : 's'} · ${decimalFmt.format(group.share * 100)}% of collected ${group.entity} award value under this dataset`,
      materialityText: `${compactMoney(group.value)} published award value`,
      scope: `${group.entity} · exact raw vendor identity; not final paid value`,
      sourceIds: b8Unique(group.rows.map(row => row.source_id)),
      evidenceRows: [
        ['Reporting entity', group.entity], ['Exact raw vendor', group.vendor],
        ['Collected award rows', numberFmt.format(group.count)], ['Published award value', money(group.value)],
        ['Share of entity-collected award value', `${decimalFmt.format(group.share * 100)}%`],
        ['Award-date span', dates.length ? `${dateOnly(dates[0])} → ${dateOnly(dates[dates.length - 1])}` : '—'],
        ['Categories represented', numberFmt.format(group.categories.size)]
      ],
      caveat: 'Concentration is calculated from collected public-tender award rows using the exact published vendor name. It does not establish lack of competition, alternative procurement, amendments, or final paid value.'
    };
  });

  const categoryTotals = new Map(); const categoryVendor = new Map();
  for (const row of rows) {
    const amount = b8Number(row.original_award_value) || 0;
    if (!row.category || !row.vendor_name || amount <= 0) continue;
    const categoryKey = `${row.entity || 'Unknown entity'}||${row.category}`;
    categoryTotals.set(categoryKey, (categoryTotals.get(categoryKey) || 0) + amount);
    const vendorKey = `${categoryKey}||${row.vendor_name}`;
    const group = categoryVendor.get(vendorKey) || { entity: row.entity || 'Unknown entity', category: row.category, vendor: row.vendor_name, value: 0, count: 0, rows: [] };
    group.value += amount; group.count += 1; group.rows.push(row); categoryVendor.set(vendorKey, group);
  }
  const categoryGroups = [...categoryVendor.values()].map(group => {
    const total = categoryTotals.get(`${group.entity}||${group.category}`) || 0;
    return { ...group, total, share: total ? group.value / total : 0 };
  }).filter(group => group.total >= 250000 && group.share >= 0.35 && group.value >= 100000);
  const maxCategoryValue = Math.max(1, ...categoryGroups.map(group => group.value));
  for (const group of categoryGroups) {
    const materiality = b8ScoreMateriality(group.value, maxCategoryValue);
    const deviation = b8Clamp(group.share * 115);
    const persistence = b8Clamp(25 + Math.log2(Math.max(1, group.count)) * 20);
    const evidence = 88;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    result.push({
      id: `b8-proc-cat-${b8Slug(`${group.entity}-${group.category}-${group.vendor}`)}`,
      domain: 'Procurement', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${group.vendor} category concentration`,
      detail: `${decimalFmt.format(group.share * 100)}% of collected ${group.category} award value for ${group.entity} · ${numberFmt.format(group.count)} exact-name award row${group.count === 1 ? '' : 's'}`,
      materialityText: `${compactMoney(group.value)} of ${compactMoney(group.total)} category award value`,
      scope: 'Category-level collected public-tender awards; exact raw vendor identity',
      sourceIds: b8Unique(group.rows.map(row => row.source_id)),
      evidenceRows: [['Entity', group.entity], ['Category', group.category], ['Exact raw vendor', group.vendor], ['Vendor award value', money(group.value)], ['Category award value', money(group.total)], ['Collected share', `${decimalFmt.format(group.share * 100)}%`], ['Award rows', numberFmt.format(group.count)]],
      caveat: 'A high collected category share is a screening condition only. Category definitions, contract size, market structure, bidder counts and procurement method must be reviewed before interpretation.'
    });
  }
  return result.sort((a, b) => b.score - a.score);
}

function b8VendorStem(raw) {
  return normalize(raw)
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\b(the|limited|ltd|incorporated|inc|corporation|corp|company|co|ulc|llc)\b/g, ' ')
    .replace(/\s+/g, ' ').trim();
}
function b8VendorCandidates(rows = getRows(datasetStatus('procurement').data)) {
  const groups = new Map();
  for (const row of rows) {
    const raw = String(row.vendor_name || '').trim(); const stem = b8VendorStem(raw);
    if (!raw || stem.length < 5) continue;
    const key = `${row.entity || 'Unknown entity'}||${stem}`;
    const group = groups.get(key) || { id: `b8-vendor-candidate-${b8Slug(key)}`, entity: row.entity || 'Unknown entity', stem, variants: new Map(), rows: [] };
    const variant = group.variants.get(raw) || { name: raw, value: 0, count: 0 };
    variant.value += b8Number(row.original_award_value) || 0; variant.count += 1;
    group.variants.set(raw, variant); group.rows.push(row); groups.set(key, group);
  }
  const candidates = [...groups.values()].filter(group => group.variants.size > 1).map(group => {
    const variants = [...group.variants.values()].sort((a, b) => b.value - a.value);
    return { ...group, variants, combinedCandidateValue: variants.reduce((sum, item) => sum + item.value, 0) };
  }).sort((a, b) => b.combinedCandidateValue - a.combinedCandidateValue);
  build008VendorCandidateIndex = new Map(candidates.map(item => [item.id, item]));
  return candidates;
}

function b8SpendingMatchKey(row) {
  const label = typeof spendingLabel === 'function' ? spendingLabel(row) : (row.business_unit || row.category || row.account || row.record_type || 'row');
  const context = row.category || row.account || '';
  const tokenCount = Array.isArray(row.values) ? row.values.length : 0;
  return [row.record_type || '', label, context, row.amount_semantics || '', tokenCount].map(normalize).join('||');
}
function b8SpendingMovementAnalysis(rows = getRows(datasetStatus('spending').data)) {
  const groups = new Map();
  for (const row of rows) {
    if (!row.posting_date || b8Number(row.amount) == null) continue;
    const key = b8SpendingMatchKey(row);
    const group = groups.get(key) || { key, dates: new Map() };
    const date = String(row.posting_date);
    if (!group.dates.has(date)) group.dates.set(date, []);
    group.dates.get(date).push(row); groups.set(key, group);
  }
  const rawMovements = []; let ambiguousDates = 0; let matchedKeys = 0;
  for (const group of groups.values()) {
    const points = [...group.dates.entries()].filter(([, items]) => {
      if (items.length !== 1) { ambiguousDates += 1; return false; }
      return true;
    }).map(([date, items]) => ({ date, row: items[0] })).sort((a, b) => a.date.localeCompare(b.date));
    if (points.length < 2) continue;
    matchedKeys += 1;
    const deltas = [];
    for (let i = 1; i < points.length; i++) {
      const prior = points[i - 1]; const current = points[i];
      const delta = Number(current.row.amount) - Number(prior.row.amount);
      const fraction = Math.abs(Number(prior.row.amount)) >= 1000 ? delta / Math.abs(Number(prior.row.amount)) : null;
      deltas.push(delta);
      const persistent = deltas.length >= 2 && Math.sign(deltas[deltas.length - 1]) !== 0 && Math.sign(deltas[deltas.length - 1]) === Math.sign(deltas[deltas.length - 2]);
      rawMovements.push({ prior, current, delta, fraction, persistent, key: group.key });
    }
  }
  const maxDelta = Math.max(1, ...rawMovements.map(item => Math.abs(item.delta)));
  const movements = rawMovements.map((item, index) => {
    const row = item.current.row;
    const label = typeof spendingLabel === 'function' ? spendingLabel(row) : (row.business_unit || row.category || row.account || row.record_type || 'Source row');
    const materiality = b8ScoreMateriality(item.delta, maxDelta);
    const deviation = item.fraction == null ? 20 : b8ScoreDeviation(item.fraction, 180);
    const persistence = item.persistent ? 82 : 38;
    const evidence = 84;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    return {
      id: `b8-spend-${b8Slug(`${item.key}-${item.current.date}-${index}`)}`,
      domain: 'Spending summaries', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${label} quarterly movement`,
      detail: `${dateOnly(item.prior.date)} → ${dateOnly(item.current.date)} · ${b8Direction(item.delta)} ${b8SignedMoney(item.delta)}${item.fraction == null ? '' : ` (${b8PercentFraction(item.fraction)})`}${item.persistent ? ' · repeated same-direction movement' : ''}`,
      materialityText: `${compactMoney(Math.abs(item.delta))} absolute matched-row movement`,
      scope: `${humanize(row.record_type || 'summary row')} · exact normalized label/context/amount-semantics match`,
      sourceIds: b8Unique([item.prior.row.source_id, item.current.row.source_id]),
      evidenceRows: [
        ['Matched source-row label', label], ['Record type', humanize(row.record_type)],
        ['Prior period', dateOnly(item.prior.date)], ['Prior amount', money(item.prior.row.amount)],
        ['Current period', dateOnly(item.current.date)], ['Current amount', money(item.current.row.amount)],
        ['Movement', b8SignedMoney(item.delta)], ['Relative movement', item.fraction == null ? 'Not calculated for small/zero baseline' : b8PercentFraction(item.fraction)],
        ['Prior source locator', `p${item.prior.row.source_page || '—'} / t${item.prior.row.source_table || '—'} / r${item.prior.row.source_row || '—'}`],
        ['Current source locator', `p${item.current.row.source_page || '—'} / t${item.current.row.source_table || '—'} / r${item.current.row.source_row || '—'}`]
      ],
      caveat: 'This is a like-for-like movement between official quarterly summary-table rows, not a transaction, invoice, vendor payment, or finding of overspending. Ambiguous duplicate matches are excluded.'
    };
  }).sort((a, b) => b.score - a.score);
  return { movements, ambiguousDates, matchedKeys };
}

function b8CompensationInvestigations() {
  const rows = compensationRows(); const grouped = new Map();
  for (const row of rows) {
    const key = `${row.entity || 'Unknown'}||${row.person_key || row.name}`;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(row);
  }
  const raw = [];
  for (const group of grouped.values()) {
    const ordered = [...group].sort((a, b) => Number(a.fiscal_year_end) - Number(b.fiscal_year_end));
    let priorLargeDirection = 0;
    for (let i = 1; i < ordered.length; i++) {
      const prior = ordered[i - 1], current = ordered[i];
      if (Number(current.fiscal_year_end) - Number(prior.fiscal_year_end) !== 1 || Number(prior.total || 0) <= 0) continue;
      const delta = Number(current.total || 0) - Number(prior.total || 0);
      const fraction = delta / Math.abs(Number(prior.total));
      if (Math.abs(delta) < 50000 && Math.abs(fraction) < 0.30) { priorLargeDirection = 0; continue; }
      const direction = Math.sign(delta);
      raw.push({ prior, current, delta, fraction, persistent: priorLargeDirection !== 0 && priorLargeDirection === direction });
      priorLargeDirection = direction;
    }
  }
  const maxDelta = Math.max(1, ...raw.map(item => Math.abs(item.delta)));
  return raw.map(item => {
    const materiality = b8ScoreMateriality(item.delta, maxDelta);
    const deviation = b8ScoreDeviation(item.fraction, 180);
    const persistence = item.persistent ? 75 : 32;
    const evidence = 92;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    return {
      id: `b8-comp-${b8Slug(`${item.current.entity}-${item.current.person_key}-${item.current.fiscal_year_end}`)}`,
      domain: 'Compensation', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${item.current.name} compensation movement`,
      detail: `${item.prior.fiscal_year_end} → ${item.current.fiscal_year_end} · ${b8SignedMoney(item.delta)} (${b8PercentFraction(item.fraction)})${item.persistent ? ' · repeated same-direction movement' : ''}`,
      materialityText: `${compactMoney(Math.abs(item.delta))} disclosed-total movement`,
      scope: `${item.current.entity} · $100k+ disclosure history, not full payroll`,
      sourceIds: b8Unique([item.prior.source_id, item.current.source_id]),
      evidenceRows: [['Reporting entity', item.current.entity], ['Employee', item.current.name], ['Prior year', item.prior.fiscal_year_end], ['Prior total', money(item.prior.total)], ['Current year', item.current.fiscal_year_end], ['Current total', money(item.current.total)], ['Movement', b8SignedMoney(item.delta)], ['Relative movement', b8PercentFraction(item.fraction)]],
      caveat: 'Disclosure totals can change because of overtime, acting pay, severance, vacation payout, allowances or other source-defined components. Threshold disclosure is not a full-workforce payroll ledger.'
    };
  }).sort((a, b) => b.score - a.score);
}

function b8FinancialInvestigations() {
  const rows = getRows(datasetStatus('financials').data).filter(row => {
    if (b8Number(row.current_year) == null || b8Number(row.prior_year) == null) return false;
    const family = normalize(row.statement_family);
    const line = normalize(row.line_item);
    if (family && !family.includes('operation')) return false;
    if (/^total\b/.test(line)) return false;
    return true;
  });
  const raw = rows.map(row => {
    const delta = Number(row.current_year) - Number(row.prior_year);
    const fraction = Math.abs(Number(row.prior_year)) >= 1000 ? delta / Math.abs(Number(row.prior_year)) : null;
    return { row, delta, fraction };
  }).filter(item => Math.abs(item.delta) >= 5000000 || (item.fraction != null && Math.abs(item.fraction) >= 0.20));
  const maxDelta = Math.max(1, ...raw.map(item => Math.abs(item.delta)));
  return raw.map((item, index) => {
    const materiality = b8ScoreMateriality(item.delta, maxDelta);
    const deviation = item.fraction == null ? 20 : b8ScoreDeviation(item.fraction, 160);
    const persistence = 28;
    const evidence = 96;
    const score = b8OverallScore({ materiality, deviation, persistence, evidence });
    return {
      id: `b8-fin-${b8Slug(`${item.row.source_id}-${item.row.statement}-${item.row.line_item}-${index}`)}`,
      domain: 'Financial statements', kind: 'fiscal', priority: b8Priority(score), score,
      materiality, deviation, persistence, evidence,
      title: `${item.row.line_item || item.row.statement} audited movement`,
      detail: `${b8SignedMoney(item.delta)} source-presented current-versus-prior movement${item.fraction == null ? '' : ` (${b8PercentFraction(item.fraction)})`}`,
      materialityText: `${compactMoney(Math.abs(item.delta))} audited comparative movement`,
      scope: `${humanize(item.row.statement_family)} · audited statement row`,
      sourceIds: [item.row.source_id],
      evidenceRows: [['Statement', item.row.statement], ['Line item', item.row.line_item], ['Fiscal-year source', item.row.fiscal_year_end], ['Current year', money(item.row.current_year)], ['Prior year', money(item.row.prior_year)], ['Movement', b8SignedMoney(item.delta)], ['Source ID', item.row.source_id]],
      caveat: 'Audited statement rows can include accounting classifications, transfers and non-cash items. Totals beginning with “Total” are excluded from this screening queue to reduce double-counting, but source-row overlap can still exist.'
    };
  }).sort((a, b) => b.score - a.score);
}

function b8DataQualityInvestigations() {
  const quality = [];
  const budgetRows = typeof budgetServiceRows === 'function' ? budgetServiceRows() : [];
  for (const row of budgetRows.filter(row => Array.isArray(row.validation_flags) && row.validation_flags.length)) {
    quality.push({
      id: `b8-quality-budget-${b8Slug(`${row.business_unit}-${row.service_area}`)}`,
      domain: 'Budget', kind: 'quality', priority: 'review', score: 72,
      materiality: 0, deviation: 70, persistence: 20, evidence: 100,
      title: `${row.service_area} source arithmetic discrepancy`,
      detail: `${row.validation_flags.join(' · ')} · published change ${b8SignedMoney(row.source_reported_budget_change)} vs independently derived ${b8SignedMoney(row.derived_budget_change)}`,
      materialityText: 'Data-quality alert — not a spending finding', scope: row.business_unit,
      sourceIds: [row.source_id],
      evidenceRows: [['Business unit', row.business_unit], ['Service area', row.service_area], ['Published change', b8SignedMoney(row.source_reported_budget_change)], ['Derived change', b8SignedMoney(row.derived_budget_change)], ['Validation flags', row.validation_flags.join(' · ')], ['Source ID', row.source_id]],
      caveat: 'This is an arithmetic inconsistency in the published/source-extracted row. It is isolated from fiscal investigations and is not evidence that money was improperly spent.'
    });
  }
  for (const row of compensationRows().filter(row => Array.isArray(row.validation_flags) && row.validation_flags.includes('reported_total_mismatch'))) {
    quality.push({
      id: `b8-quality-comp-${b8Slug(`${row.entity}-${row.person_key}-${row.fiscal_year_end}`)}`,
      domain: 'Compensation', kind: 'quality', priority: 'review', score: 72,
      materiality: 0, deviation: 70, persistence: 20, evidence: 100,
      title: `${row.name} published total mismatch`,
      detail: `Published total differs from published wages + benefits by ${b8SignedMoney(row.source_total_delta)}`,
      materialityText: 'Data-quality alert — not a compensation finding', scope: `${row.entity} · ${row.fiscal_year_end}`,
      sourceIds: [row.source_id],
      evidenceRows: [['Entity', row.entity], ['Employee', row.name], ['Fiscal year', row.fiscal_year_end], ['Published wages', money(row.wages)], ['Published benefits', money(row.benefits)], ['Published total', money(row.total)], ['Published total delta', b8SignedMoney(row.source_total_delta)], ['Source ID', row.source_id]],
      caveat: 'This is a source-data arithmetic inconsistency retained by validation. HalifaxData does not silently correct it and does not treat it as evidence of wrongdoing.'
    });
  }
  return quality;
}

function b8AllInvestigations() {
  const fiscal = [
    ...b8BudgetPressureInvestigations().slice(0, 40),
    ...b8ProcurementInvestigations().slice(0, 50),
    ...b8SpendingMovementAnalysis().movements.slice(0, 50),
    ...b8CompensationInvestigations().slice(0, 35),
    ...b8FinancialInvestigations().slice(0, 30)
  ];
  const quality = b8DataQualityInvestigations();
  const all = [...fiscal, ...quality];
  build008InvestigationIndex = new Map(all.map(item => [item.id, item]));
  return { fiscal: fiscal.sort((a, b) => b.score - a.score), quality: quality.sort((a, b) => b.score - a.score) };
}
function b8DiverseTop(items, limit = 8, maxPerDomain = 3) {
  const counts = new Map(); const selected = [];
  for (const item of items) {
    const count = counts.get(item.domain) || 0;
    if (count >= maxPerDomain) continue;
    selected.push(item); counts.set(item.domain, count + 1);
    if (selected.length >= limit) break;
  }
  return selected;
}

function b8OverviewHtml() {
  const investigations = b8AllInvestigations();
  const top = b8DiverseTop(investigations.fiscal, 9, 3);
  const high = investigations.fiscal.filter(item => item.priority === 'high').length;
  const domains = new Set(investigations.fiscal.map(item => item.domain));
  const budgetTop = b8BudgetPressureInvestigations().slice(0, 5);
  const procurementTop = b8ProcurementInvestigations().slice(0, 5);
  return `<div class="page-stack b8-overview">
    <div class="notice"><strong>Investigation boundary</strong><span>HalifaxData now ranks cross-domain review leads by source-backed materiality, relative deviation, persistence and evidence quality. A high review score means “inspect this first,” not “misconduct is likely.”</span></div>
    <div class="metrics-grid">
      ${metricCard('Fiscal review leads', numberFmt.format(investigations.fiscal.length), 'Cross-domain derived screening candidates', 'accent')}
      ${metricCard('Priority review', numberFmt.format(high), 'Higher-ranked leads after domain-specific normalization', high ? 'warn' : 'good')}
      ${metricCard('Domains represented', numberFmt.format(domains.size), [...domains].join(' · '), 'neutral')}
      ${metricCard('Data-quality alerts', numberFmt.format(investigations.quality.length), 'Kept separate from spending/budget investigations', investigations.quality.length ? 'warn' : 'good')}
    </div>
    ${panel('What deserves attention?', 'Highest-ranked cross-domain leads with domain diversity. Click any item for the exact facts, methodology boundary and source records.', top.length ? `<div class="b8-investigation-grid">${top.map(item => b8InvestigationCard(item)).join('')}</div>` : emptyState('No investigation leads', 'Released datasets did not produce qualifying review leads.'))}
    <div class="split-grid wide-left">
      ${panel('Budget pressure snapshot', 'Service-area detail rows ranked by projection drift and next-budget growth; rows are not summed into a synthetic total.', budgetTop.length ? `<div class="b8-compact-list">${budgetTop.map(item => b8InvestigationCard(item, true)).join('')}</div>` : emptyState('No positive budget-pressure rows', 'No qualifying service-area pressure rows are available.'))}
      ${panel('Procurement concentration snapshot', 'Exact published vendor identities only. Candidate aliases are reviewed separately and never silently merged.', procurementTop.length ? `<div class="b8-compact-list">${procurementTop.map(item => b8InvestigationCard(item, true)).join('')}</div>` : emptyState('No procurement concentration leads', 'No qualifying public-tender award concentration was derived.'))}
    </div>
    ${panel('Data coverage & readiness', 'Coverage remains visible, but it is now supporting context rather than the primary landing-page task.', `<div class="coverage-grid">${['budget', 'spending', 'procurement', 'capital', 'financials', 'council'].map(domainCoverageCard).join('')}</div>`)}
    <div class="split-grid">
      ${panel('Public-money reconciliation path', 'Investigation ranking does not replace source reconciliation.', reconciliationGraph())}
      ${panel('Data-quality separation', 'Collection/parser/source inconsistencies are tracked independently from fiscal-review leads.', `<div class="rule-list"><div><strong>Fiscal lead</strong><span>Source-backed magnitude, deviation, recurrence or concentration says inspect the underlying financial context.</span></div><div><strong>Data-quality alert</strong><span>Published/source arithmetic or extraction inconsistency says inspect the data itself.</span></div><div><strong>Confirmed finding</strong><span>Neither queue becomes a finding without separate supporting evidence and human review.</span></div></div>`)}
    </div>
  </div>`;
}

function b8InvestigationsHtml() {
  const all = b8AllInvestigations();
  const domains = [...new Set(all.fiscal.map(item => item.domain))].sort((a, b) => a.localeCompare(b));
  const filtered = all.fiscal.filter(item =>
    (state.investigationDomain === 'all' || item.domain === state.investigationDomain) &&
    (state.investigationPriority === 'all' || item.priority === state.investigationPriority)
  );
  const visible = filtered.slice(0, 120);
  const high = all.fiscal.filter(item => item.priority === 'high').length;
  return `<div class="page-stack b8-investigations-page">
    <div class="notice"><strong>Review queue standard</strong><span>This queue is derived client-side from released source-backed domains. Scores are review-ordering aids built from materiality, deviation, persistence and evidence quality. They are not probabilities of waste, illegality, wrongdoing or policy breach.</span></div>
    <div class="metrics-grid">
      ${metricCard('Fiscal investigations', numberFmt.format(all.fiscal.length), 'Curated cross-domain screening leads', 'accent')}
      ${metricCard('Priority review', numberFmt.format(high), 'Higher review score; still not a finding', high ? 'warn' : 'good')}
      ${metricCard('Domains', numberFmt.format(domains.length), domains.join(' · '), 'neutral')}
      ${metricCard('Data-quality alerts', numberFmt.format(all.quality.length), 'Separate queue below', all.quality.length ? 'warn' : 'good')}
    </div>
    ${panel('Ranked investigations', 'Filter by domain or review priority. Repeated raw observations are condensed into evidence-backed analytical leads rather than thousands of undifferentiated signal cards.', `<div class="local-toolbar build006-toolbar"><select id="investigation-domain"><option value="all">All analytical domains</option>${domains.map(domain => `<option value="${escapeHtml(domain)}" ${state.investigationDomain === domain ? 'selected' : ''}>${escapeHtml(domain)}</option>`).join('')}</select><select id="investigation-priority"><option value="all">All review priorities</option><option value="high" ${state.investigationPriority === 'high' ? 'selected' : ''}>Priority review</option><option value="review" ${state.investigationPriority === 'review' ? 'selected' : ''}>Review</option><option value="context" ${state.investigationPriority === 'context' ? 'selected' : ''}>Context</option></select><span class="table-note">Showing ${numberFmt.format(visible.length)} of ${numberFmt.format(filtered.length)} matched leads</span></div>${visible.length ? `<div class="b8-investigation-grid">${visible.map(item => b8InvestigationCard(item)).join('')}</div>` : emptyState('No investigations under these filters', 'Widen the domain or priority filter.')}`)}
    ${panel('Data-quality queue', 'Published/source arithmetic inconsistencies stay visible but are intentionally isolated from fiscal-review ranking.', all.quality.length ? `<div class="b8-quality-grid">${all.quality.map(item => b8InvestigationCard(item, true)).join('')}</div>` : emptyState('No data-quality alerts', 'No current published/source arithmetic inconsistencies are flagged.'))}
    ${panel('Scoring interpretation', 'The four components make review ordering inspectable instead of hiding everything in one opaque number.', `<div class="lens-grid"><div><strong>Materiality</strong><p>Magnitude within its own analytical domain, normalized so one domain does not win merely because its units are larger.</p></div><div><strong>Deviation</strong><p>Relative change, concentration or comparable departure from the relevant source-backed baseline.</p></div><div><strong>Persistence</strong><p>Repeated awards or repeated same-direction movements receive more review weight than a single observation.</p></div><div><strong>Evidence</strong><p>Direct official facts score higher than derived comparisons that depend on matching multiple rows.</p></div><div><strong>Review score</strong><p>Weighted ordering aid only. It is not a probability, legal conclusion, fraud score or estimate of waste.</p></div><div><strong>Human finding</strong><p>Requires source reading, policy/accounting context and separate corroborating evidence.</p></div></div>`)}
  </div>`;
}

function b8BudgetPressurePanel() {
  const items = b8BudgetPressureInvestigations();
  const visible = items.slice(0, 10);
  const projectionPressure = items.filter(item => /projection/.test(normalize(item.detail))).length;
  return `<section class="panel b8-budget-pressure"><header class="panel-header"><div><h2>Budget pressure analysis</h2><p>Ranks service-area detail rows using published 2024/25 budget/projection and 2025/26 budget endpoints. It does not sum potentially overlapping source rows or describe a variance as waste.</p></div></header><div class="panel-body"><div class="b8-inline-metrics"><div><strong>${numberFmt.format(items.length)}</strong><span>positive pressure leads</span></div><div><strong>${numberFmt.format(projectionPressure)}</strong><span>projection/growth review candidates</span></div><div><strong>${visible[0]?.materialityText ? escapeHtml(visible[0].materialityText) : '—'}</strong><span>largest ranked pressure movement</span></div></div>${visible.length ? `<div class="b8-investigation-grid">${visible.map(item => b8InvestigationCard(item)).join('')}</div>` : emptyState('No budget pressure leads', 'No positive projection/budget-growth conditions qualified.')}</div></section>`;
}

function b8ProcurementPanels() {
  const rows = typeof filteredVendorRows === 'function' ? filteredVendorRows() : getRows(datasetStatus('procurement').data);
  const investigations = b8ProcurementInvestigations(rows).slice(0, 10);
  const candidates = b8VendorCandidates(rows).slice(0, 10);
  return `<section class="b8-procurement-analysis"><div class="split-grid wide-left">
    ${panel('Procurement concentration & repeat awards', 'Exact published vendor names only. Review score uses collected award value, entity/category share and repeat-award frequency.', investigations.length ? `<div class="b8-compact-list">${investigations.map(item => b8InvestigationCard(item, true)).join('')}</div>` : emptyState('No concentration leads', 'No qualifying concentration/repeat-award conditions under the current vendor filter.'))}
    ${panel('Candidate vendor identity matches', 'Potential raw-name variants are surfaced for human review and are never silently merged into concentration calculations.', candidates.length ? `<div class="b8-vendor-candidates">${candidates.map(item => `<button type="button" data-build008-vendor-candidate="${escapeHtml(item.id)}"><strong>${escapeHtml(item.variants.map(v => v.name).join(' ↔ '))}</strong><span>${escapeHtml(item.entity)} · ${compactMoney(item.combinedCandidateValue)} across raw variants</span><small>candidate normalized stem: ${escapeHtml(item.stem)}</small></button>`).join('')}</div>` : emptyState('No candidate raw-name variants', 'No multiple raw vendor names collapsed to the same conservative normalized stem under this filter.'))}
  </div></section>`;
}

function b8SpendingMovementPanel() {
  const rows = typeof filteredSpendingRows === 'function' ? filteredSpendingRows() : getRows(datasetStatus('spending').data);
  const analysis = b8SpendingMovementAnalysis(rows); const visible = analysis.movements.slice(0, 12);
  return `<section class="panel b8-spending-movement"><header class="panel-header"><div><h2>Quarterly spending movement analysis</h2><p>Matches like-for-like official summary rows by normalized record type, row label, context, amount semantics and token structure. Ambiguous duplicate keys are excluded rather than guessed.</p></div></header><div class="panel-body"><div class="b8-inline-metrics"><div><strong>${numberFmt.format(analysis.matchedKeys)}</strong><span>comparable source-row series</span></div><div><strong>${numberFmt.format(analysis.movements.length)}</strong><span>period-to-period movements</span></div><div><strong>${numberFmt.format(analysis.ambiguousDates)}</strong><span>ambiguous key/dates excluded</span></div></div>${visible.length ? `<div class="b8-investigation-grid">${visible.map(item => b8InvestigationCard(item)).join('')}</div>` : emptyState('No like-for-like quarterly movements', 'The current filters do not leave at least two unambiguous comparable periods for a source-row series.')}</div></section>`;
}

function b8ShowInvestigation(id) {
  const item = build008InvestigationIndex.get(id) || b8AllInvestigations().fiscal.find(candidate => candidate.id === id) || b8DataQualityInvestigations().find(candidate => candidate.id === id);
  if (!item) return;
  openDrawer({
    title: item.title,
    eyebrow: item.kind === 'quality' ? 'DATA QUALITY REVIEW' : 'INVESTIGATION LEAD',
    html: `${evidenceSteps([['Domain', item.domain], ['Review priority', item.priority], ['Review score', item.score], ['Materiality component', Math.round(item.materiality)], ['Deviation component', Math.round(item.deviation)], ['Persistence component', Math.round(item.persistence)], ['Evidence component', Math.round(item.evidence)], ...(item.evidenceRows || [])])}<div class="drawer-callout"><strong>Interpretation boundary</strong><p>${escapeHtml(item.caveat || 'This is a review lead, not a finding.')}</p></div>${b8SourceLinks(item.sourceIds || [])}`
  });
}
function b8ShowVendorCandidate(id) {
  const item = build008VendorCandidateIndex.get(id); if (!item) return;
  openDrawer({
    title: 'Candidate vendor identity match', eyebrow: 'IDENTITY REVIEW',
    html: `${evidenceSteps([['Reporting entity', item.entity], ['Candidate normalized stem', item.stem], ['Raw-name variants', item.variants.map(v => v.name).join(' · ')], ['Combined value across displayed raw variants', money(item.combinedCandidateValue)]])}<div class="drawer-section"><h3>Raw variants remain separate</h3><div class="rule-list">${item.variants.map(variant => `<div><strong>${escapeHtml(variant.name)}</strong><span>${numberFmt.format(variant.count)} award row${variant.count === 1 ? '' : 's'} · ${money(variant.value)}</span></div>`).join('')}</div></div><div class="drawer-callout"><strong>No automatic merge</strong><p>These raw names share a conservative punctuation/legal-suffix-normalized stem. HalifaxData does not treat them as the same legal vendor without corroborating identity evidence.</p></div>${b8SourceLinks(item.rows.map(row => row.source_id))}`
  });
}

function b8BindEvents() {
  $$('#content [data-build008-investigation-id]').forEach(element => element.addEventListener('click', () => b8ShowInvestigation(element.dataset.build008InvestigationId)));
  $$('#content [data-build008-vendor-candidate]').forEach(element => element.addEventListener('click', () => b8ShowVendorCandidate(element.dataset.build008VendorCandidate)));
  $$('#content .coverage-card[data-domain]').forEach(element => element.addEventListener('click', () => showDomainCoverage(element.dataset.domain)));
  const domain = $('#investigation-domain');
  if (domain) domain.addEventListener('change', event => { state.investigationDomain = event.target.value; render(); });
  const priority = $('#investigation-priority');
  if (priority) priority.addEventListener('change', event => { state.investigationPriority = event.target.value; render(); });
}

function b8EnhanceBudget() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b8-budget-pressure')) return;
  const metrics = stack.querySelector('.metrics-grid');
  if (metrics) metrics.insertAdjacentHTML('afterend', b8BudgetPressurePanel());
  else stack.insertAdjacentHTML('afterbegin', b8BudgetPressurePanel());
}
function b8EnhanceSpending() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b8-spending-movement')) return;
  const metrics = stack.querySelector('.metrics-grid');
  if (metrics) {
    const cards = metrics.querySelectorAll('.metric-card');
    const analysis = b8SpendingMovementAnalysis(typeof filteredSpendingRows === 'function' ? filteredSpendingRows() : getRows(datasetStatus('spending').data));
    if (cards[3]) {
      const label = cards[3].querySelector('.metric-label'); const value = cards[3].querySelector('.metric-value'); const detail = cards[3].querySelector('.metric-detail');
      if (label) label.textContent = 'Comparable movement leads';
      if (value) value.textContent = numberFmt.format(analysis.movements.length);
      if (detail) detail.textContent = `${numberFmt.format(analysis.matchedKeys)} unambiguous matched source-row series`;
    }
    metrics.insertAdjacentHTML('afterend', b8SpendingMovementPanel());
  } else stack.insertAdjacentHTML('afterbegin', b8SpendingMovementPanel());
}
function b8EnhanceVendors() {
  const stack = $('#content .page-stack');
  if (!stack || stack.querySelector('.b8-procurement-analysis')) return;
  const metrics = stack.querySelector('.metrics-grid');
  if (metrics) metrics.insertAdjacentHTML('afterend', b8ProcurementPanels());
  else stack.insertAdjacentHTML('afterbegin', b8ProcurementPanels());
}

const build007Render = render;
render = function renderBuild008() {
  build007Render();
  if (state.view === 'overview') $('#content').innerHTML = b8OverviewHtml();
  if (state.view === 'budget') b8EnhanceBudget();
  if (state.view === 'spending') b8EnhanceSpending();
  if (state.view === 'vendors') b8EnhanceVendors();
  if (state.view === 'signals') $('#content').innerHTML = b8InvestigationsHtml();

  const search = $('#global-search');
  if (search) search.placeholder = 'Search people, sources, investigations…';
  const filterbar = $('.filterbar');
  if (filterbar && ['overview', 'signals'].includes(state.view)) filterbar.hidden = true;
  b8BindEvents();
};
