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

    await page.goto(`${BASE_URL}#spending`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => {
      if (typeof window.b15Stats !== 'function' || window.b15Sources?.().length !== 8 || !document.querySelector('.b15-current-fiscal')) return false;
      const stats = window.b15Stats();
      return stats.latestPeriodEnd === '2025-12-31' && stats.totalRows > 1094 && stats.currentRows > 0;
    }, null, { timeout: 30000 });

    const stats = await page.evaluate(() => window.b15Stats());
    if (stats.reportCount !== 8) throw new Error(`${viewportName}: expected 8 quarterly reports, got ${stats.reportCount}`);
    if (stats.currentReportCount !== 3) throw new Error(`${viewportName}: expected 3 2025/26 reports, got ${stats.currentReportCount}`);
    if (stats.latestPeriodEnd !== '2025-12-31') throw new Error(`${viewportName}: latest period ${stats.latestPeriodEnd}`);
    if (!(stats.totalRows > 1094)) throw new Error(`${viewportName}: refreshed row count did not exceed prior verified 1,094-row baseline`);
    if (!(stats.currentRows > 0)) throw new Error(`${viewportName}: no 2025/26 rows extracted`);
    if (!(stats.matchedSeries > 0)) throw new Error(`${viewportName}: no matched quarterly series`);

    const contentText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of [
      'current quarterly financial series',
      'q1 · q2 · q3 identified official reports',
      'financial-summary evidence, not transaction evidence',
      'spent or committed',
      'not converted into cash-payment evidence',
      '2024/25 q1 is not in the current checked source set'
    ]) {
      if (!contentText.includes(phrase)) throw new Error(`${viewportName}: spending view missing "${phrase}"`);
    }

    const currentCards = page.locator('.b15-quarter-card.current');
    if (await currentCards.count() !== 3) throw new Error(`${viewportName}: expected 3 current-fiscal timeline cards`);
    await currentCards.first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    const drawerText = `${await page.locator('#drawer-title').innerText()}\n${await page.locator('#drawer-body').innerText()}`.toLowerCase();
    if (!drawerText.includes('2025/26')) throw new Error(`${viewportName}: current report source drawer missing 2025/26 context`);
    if (!drawerText.includes('source id') || !drawerText.includes('coverage')) throw new Error(`${viewportName}: current report source drawer missing evidence fields`);
    await page.locator('#drawer-close').click();

    const dims = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth
    }));
    if (dims.scrollWidth > dims.clientWidth + 2) throw new Error(`${viewportName}: Build 015 spending view caused horizontal overflow`);

    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build015-spending.png`, fullPage: true });

    await page.goto(`${BASE_URL}#sources`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => document.querySelector('.b15-source-panel'), null, { timeout: 20000 });
    const sourcesText = (await page.locator('.b15-source-panel').innerText()).toLowerCase();
    for (const phrase of ['build 015 quarterly financial sources', 'q1-q3 2025/26', 'does not close the public accounts-payable/payment-ledger gap']) {
      if (!sourcesText.includes(phrase)) throw new Error(`${viewportName}: sources view missing "${phrase}"`);
    }
    if (await page.locator('.b15-source-panel .b15-quarter-card').count() !== 8) throw new Error(`${viewportName}: source panel did not render all 8 reports`);
    const sourceDims = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth
    }));
    if (sourceDims.scrollWidth > sourceDims.clientWidth + 2) throw new Error(`${viewportName}: Build 015 sources view caused horizontal overflow`);
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build015-sources.png`, fullPage: true });

    report.views.push({ viewport: viewportName, ...stats });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build015-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
