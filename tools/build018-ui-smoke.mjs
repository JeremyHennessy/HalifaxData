import { chromium } from 'playwright';
import fs from 'node:fs/promises';

const BASE_URL = (process.env.HALIFAXDATA_URL || 'http://127.0.0.1:8000/').replace(/\/?$/, '/');
const OUTPUT = 'artifacts/ui-smoke';
const viewports = [
  ['desktop', { width: 1440, height: 1100 }],
  ['mobile', { width: 390, height: 844 }]
];

await fs.mkdir(OUTPUT, { recursive: true });
const browser = await chromium.launch({ headless: true });
const report = { generated_at: new Date().toISOString(), base_url: BASE_URL, views: [], errors: [] };

function requirePhrases(text, phrases, label) {
  for (const phrase of phrases) {
    if (!text.includes(phrase)) throw new Error(`${label}: missing "${phrase}"`);
  }
}

try {
  for (const [viewportName, viewport] of viewports) {
    const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
    const page = await context.newPage();
    page.on('pageerror', error => report.errors.push({ viewport: viewportName, type: 'pageerror', text: error.message }));
    page.on('console', message => {
      if (message.type() === 'error' && !message.text().startsWith('Failed to load resource: the server responded with a status of 404')) {
        report.errors.push({ viewport: viewportName, type: 'console', text: message.text() });
      }
    });

    await page.goto(`${BASE_URL}#budget`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => {
      const rows = typeof b18BudgetRows === 'function' ? b18BudgetRows() : [];
      return Boolean(document.querySelector('.b18-current-budget') && rows.length === 105);
    }, null, { timeout: 30000 });

    const budgetStats = await page.evaluate(() => ({
      rows: b18BudgetRows().length,
      overviewPages: b18BudgetMeta().overview_page_count,
      netTotals: b18BudgetMeta().net_total_count,
      municipalExpenditures: b18BudgetMeta().published_controls?.municipal_expenditures,
      parser: b18BudgetMeta().parser_version,
      discrepancyRows: b18BudgetMeta().source_arithmetic_discrepancy_rows,
      budgetSource: Boolean(sourceById('hrm-budget-2026-27-final-package')),
      approvalSource: Boolean(sourceById('hrm-council-2026-03-31-budget-ratification')),
      oldBudgetExplorer: Boolean(document.querySelector('#budget-search')),
      oldBudgetRows: document.querySelectorAll('[data-budget-row]').length
    }));
    if (budgetStats.rows !== 105 || budgetStats.overviewPages !== 20 || budgetStats.netTotals !== 20) {
      throw new Error(`${viewportName}: unexpected Build 018 budget shape ${JSON.stringify(budgetStats)}`);
    }
    if (budgetStats.municipalExpenditures !== 1211700000 || budgetStats.parser !== 'build018-current-budget-v2') {
      throw new Error(`${viewportName}: Build 018 current-budget controls changed ${JSON.stringify(budgetStats)}`);
    }
    if (budgetStats.discrepancyRows !== 1 || !budgetStats.budgetSource || !budgetStats.approvalSource) {
      throw new Error(`${viewportName}: Build 018 budget source/discrepancy contract not exposed`);
    }
    if (!budgetStats.oldBudgetExplorer || budgetStats.oldBudgetRows < 1) {
      throw new Error(`${viewportName}: preserved 2025/26 budget explorer is missing`);
    }

    const budgetText = (await page.locator('.b18-current-budget').innerText()).toLowerCase();
    requirePhrases(budgetText, [
      'ratified-current 2026/27 budget',
      'budget authority — not spending',
      'municipal expenditures',
      'one published percentage does not reconcile',
      '2026/27 service-area budget explorer',
      'the proven 2025/26 budget and audited-history views remain unchanged below'
    ], `${viewportName} Build 018 budget`);

    const warningRow = page.locator('.b18-current-budget tr.budget-source-warning[data-build018-budget-row]').first();
    if (await warningRow.count() !== 1) throw new Error(`${viewportName}: expected one visible Build 018 budget source-warning row`);
    await warningRow.click();
    await page.waitForSelector('#evidence-drawer[open]');
    const budgetDrawer = `${await page.locator('#drawer-eyebrow').innerText()}\n${await page.locator('#drawer-title').innerText()}\n${await page.locator('#drawer-body').innerText()}`.toLowerCase();
    requirePhrases(budgetDrawer, [
      'ratified-current budget evidence',
      'published source arithmetic flag',
      'budget authority is not evidence of a payment',
      'proposed 2026/27 budget — final post-bal staff package'
    ], `${viewportName} Build 018 budget drawer`);
    await page.locator('#drawer-close').click();

    let dims = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
    if (dims.scrollWidth > dims.clientWidth + 2) throw new Error(`${viewportName}: Build 018 budget view caused horizontal overflow`);
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build018-budget.png`, fullPage: true });

    await page.goto(`${BASE_URL}#projects`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => {
      const rows = typeof b18CapitalRows === 'function' ? b18CapitalRows() : [];
      return Boolean(document.querySelector('.b18-current-capital') && document.querySelector('.b10-current-capital') && rows.length === 52);
    }, null, { timeout: 30000 });

    const capitalStats = await page.evaluate(() => ({
      rows: b18CapitalRows().length,
      discrete: b18CapitalMeta().discrete_project_rows,
      ongoing: b18CapitalMeta().ongoing_program_rows,
      currentBudget: b18CapitalMeta().current_2026_27_multiyear_budget,
      computedGrand: b18CapitalMeta().computed_schedule_grand_total,
      sourceGrand: b18CapitalMeta().source_schedule_grand_total,
      discrepancies: b18CapitalMeta().source_control_discrepancies?.length,
      parser: b18CapitalMeta().parser_version,
      capitalSource: Boolean(sourceById('hrm-capital-2026-27-multiyear-revised')),
      oldCapitalExplorer: Boolean(document.querySelector('#b10-capital-search')),
      oldCapitalSection: Boolean(document.querySelector('.b10-current-capital'))
    }));
    if (capitalStats.rows !== 52 || capitalStats.discrete !== 29 || capitalStats.ongoing !== 23) {
      throw new Error(`${viewportName}: unexpected Build 018 capital shape ${JSON.stringify(capitalStats)}`);
    }
    if (capitalStats.currentBudget !== 196656000 || capitalStats.computedGrand !== 2152999431 || capitalStats.sourceGrand !== 2152999430) {
      throw new Error(`${viewportName}: Build 018 capital totals changed ${JSON.stringify(capitalStats)}`);
    }
    if (capitalStats.discrepancies !== 4 || capitalStats.parser !== 'build018-current-capital-v1' || !capitalStats.capitalSource) {
      throw new Error(`${viewportName}: Build 018 capital source/control contract not exposed`);
    }
    if (!capitalStats.oldCapitalExplorer || !capitalStats.oldCapitalSection) {
      throw new Error(`${viewportName}: preserved Build 010 current-capital view is missing`);
    }

    const capitalText = (await page.locator('.b18-current-capital').innerText()).toLowerCase();
    requirePhrases(capitalText, [
      'approved-current 2026/27 multi-year capital schedule',
      'schedule boundary',
      'not a complete capital-project ledger',
      'published control-table defects preserved',
      '2026/27 capital multi-year project/program explorer',
      'previously indexed attachment url now returns 404'
    ], `${viewportName} Build 018 capital`);

    const capitalRow = page.locator('.b18-current-capital [data-build018-capital-row]').first();
    if (await capitalRow.count() < 1) throw new Error(`${viewportName}: no Build 018 capital rows rendered`);
    await capitalRow.click();
    await page.waitForSelector('#evidence-drawer[open]');
    const capitalDrawer = `${await page.locator('#drawer-eyebrow').innerText()}\n${await page.locator('#drawer-title').innerText()}\n${await page.locator('#drawer-body').innerText()}`.toLowerCase();
    requirePhrases(capitalDrawer, [
      'approved-current capital schedule evidence',
      'project account id',
      'row grand total',
      'not spend-to-date',
      'revised 2026/27 multi-year capital plan — attachment 2'
    ], `${viewportName} Build 018 capital drawer`);
    await page.locator('#drawer-close').click();

    dims = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
    if (dims.scrollWidth > dims.clientWidth + 2) throw new Error(`${viewportName}: Build 018 capital view caused horizontal overflow`);
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build018-capital.png`, fullPage: true });

    report.views.push({ viewport: viewportName, budget: budgetStats, capital: capitalStats });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build018-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
