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

async function openRoute(page, route) {
  await page.goto(`${BASE_URL}#${route}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('#content', { state: 'visible' });
  await page.waitForFunction(() => {
    const content = document.querySelector('#content');
    return content && !content.querySelector('.loading-card');
  });
}

async function assertNoOverflow(page, viewportName, route) {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth
  }));
  if (dimensions.scrollWidth > dimensions.clientWidth + 2) {
    throw new Error(`${viewportName}/${route}: horizontal overflow ${dimensions.scrollWidth}px > ${dimensions.clientWidth}px`);
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

    await openRoute(page, 'overview');
    await page.waitForFunction(() => /automated pattern engine/i.test(document.querySelector('#content')?.innerText || ''), null, { timeout: 15000 });
    const patternCounts = await page.evaluate(() => {
      const groups = window.b9AllPatternGroups();
      return {
        budget: groups.budget.length,
        procurement: groups.procurement.length,
        spending: groups.spending.length,
        cross: groups.cross.length
      };
    });
    if (patternCounts.budget < 1) throw new Error(`${viewportName}/overview: no multi-year budget patterns rendered`);
    if (patternCounts.procurement < 1) throw new Error(`${viewportName}/overview: no procurement persistence patterns rendered`);
    if (patternCounts.spending < 1) throw new Error(`${viewportName}/overview: no quarterly trajectory patterns rendered`);
    if (patternCounts.cross < 1) throw new Error(`${viewportName}/overview: no exact business-unit cross-domain corroborations rendered`);
    const overviewText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['automated pattern engine', 'cross-domain corroboration', 'dollar values are never added together']) {
      if (!overviewText.includes(phrase)) throw new Error(`${viewportName}/overview: missing Build 009 phrase "${phrase}"`);
    }
    await assertNoOverflow(page, viewportName, 'overview');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build009-overview.png`, fullPage: true });

    await openRoute(page, 'budget');
    const budgetText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['multi-year budget pressure patterns', 'draft/proposed/pre-covid rows remain context only']) {
      if (!budgetText.includes(phrase)) throw new Error(`${viewportName}/budget: missing "${phrase}"`);
    }
    const budgetCards = page.locator('.b9-budget-patterns [data-build009-investigation-id]');
    if (await budgetCards.count() < 1) throw new Error(`${viewportName}/budget: no Build 009 pattern cards rendered`);
    await budgetCards.first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    if ((await page.locator('#drawer-eyebrow').textContent())?.trim() !== 'INVESTIGATION LEAD') throw new Error(`${viewportName}/budget: pattern evidence drawer did not open`);
    const budgetDrawer = (await page.locator('#drawer-body').innerText()).toLowerCase();
    if (!budgetDrawer.includes('non-final historical rows kept out of persistence scoring')) throw new Error(`${viewportName}/budget: final-source persistence boundary missing`);
    await page.locator('#drawer-close').click();
    await assertNoOverflow(page, viewportName, 'budget');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build009-budget.png`, fullPage: true });

    await openRoute(page, 'vendors');
    const vendorText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['procurement persistence & acceleration', 'candidate aliases remain outside these calculations']) {
      if (!vendorText.includes(phrase)) throw new Error(`${viewportName}/vendors: missing "${phrase}"`);
    }
    if (await page.locator('.b9-procurement-patterns [data-build009-investigation-id]').count() < 1) throw new Error(`${viewportName}/vendors: no procurement pattern cards rendered`);
    await assertNoOverflow(page, viewportName, 'vendors');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build009-vendors.png`, fullPage: true });

    await openRoute(page, 'spending');
    const spendingText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['full quarterly spending trajectories', 'not invoice or accounts-payable transactions', 'ambiguous key/dates excluded']) {
      if (!spendingText.includes(phrase)) throw new Error(`${viewportName}/spending: missing "${phrase}"`);
    }
    if (await page.locator('.b9-spending-trajectories [data-build009-investigation-id]').count() < 1) throw new Error(`${viewportName}/spending: no trajectory pattern cards rendered`);
    await assertNoOverflow(page, viewportName, 'spending');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build009-spending.png`, fullPage: true });

    await openRoute(page, 'signals');
    const signalsText = (await page.locator('#content').innerText()).toLowerCase();
    if (!signalsText.includes('automated pattern engine')) throw new Error(`${viewportName}/investigations: pattern-engine summary missing`);
    const crossDomainOption = page.locator('#investigation-domain option[value="Cross-domain"]');
    if (await crossDomainOption.count() !== 1) throw new Error(`${viewportName}/investigations: cross-domain filter missing despite required corroborated leads`);
    await assertNoOverflow(page, viewportName, 'signals');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build009-investigations.png`, fullPage: true });

    report.views.push({ viewport: viewportName, patternCounts });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build009-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
