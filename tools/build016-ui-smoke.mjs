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

    await page.goto(`${BASE_URL}#council`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => {
      if (typeof window.b16Rows !== 'function' || !document.querySelector('.b16-decision-panel')) return false;
      return window.b16Rows().length >= 25;
    }, null, { timeout: 30000 });

    const stats = await page.evaluate(() => {
      const rows = window.b16Rows();
      const meta = window.b16Meta();
      return {
        rows: rows.length,
        modern: meta.modern_decision_records,
        legacy: meta.legacy_decision_records,
        modernMeetings: meta.modern_meetings_with_posted_minutes,
        legacyMeetings: meta.legacy_seed_meetings,
        passed: rows.filter(row => row.motion_passed).length,
        fiscal: rows.filter(row => row.fiscal_relevant).length,
        money: rows.filter(row => (row.money_mentions || []).length).length
      };
    });
    if (!(stats.rows >= 25)) throw new Error(`${viewportName}: Council decision artifact unexpectedly sparse`);
    if (!(stats.modern >= 10)) throw new Error(`${viewportName}: modern decision extraction unexpectedly sparse`);
    if (!(stats.legacyMeetings === 7)) throw new Error(`${viewportName}: expected 7 explicit legacy seed meetings, got ${stats.legacyMeetings}`);
    if (!(stats.legacy >= 7)) throw new Error(`${viewportName}: legacy decision seed produced fewer than one record per source`);
    if (!(stats.passed >= 10 && stats.fiscal >= 5 && stats.money >= 1)) throw new Error(`${viewportName}: expected passed/fiscal/monetary decision evidence`);

    const text = (await page.locator('.b16-decision-panel').innerText()).toLowerCase();
    for (const phrase of [
      'approved-minutes decision evidence',
      'what council actually adopted or defeated',
      'a dollar amount mentioned in the motion is not evidence',
      'fiscal-relevant only'
    ]) {
      if (!text.includes(phrase)) throw new Error(`${viewportName}: Council view missing "${phrase}"`);
    }

    const rows = page.locator('[data-build016-decision]');
    if (await rows.count() < 1) throw new Error(`${viewportName}: no decision rows rendered under default fiscal filter`);
    await rows.first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    const drawer = `${await page.locator('#drawer-title').innerText()}\n${await page.locator('#drawer-body').innerText()}`.toLowerCase();
    for (const phrase of ['recorded outcome', 'recorded motion text', 'official approved minutes', 'not payment evidence']) {
      if (!drawer.includes(phrase)) throw new Error(`${viewportName}: decision drawer missing "${phrase}"`);
    }
    await page.locator('#drawer-close').click();

    const dims = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
    if (dims.scrollWidth > dims.clientWidth + 2) throw new Error(`${viewportName}: Build 016 Council view caused horizontal overflow`);
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build016-council.png`, fullPage: true });

    await page.goto(`${BASE_URL}#sources`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => document.querySelector('.b16-source-coverage'), null, { timeout: 20000 });
    const sourcesText = (await page.locator('.b16-source-coverage').innerText()).toLowerCase();
    for (const phrase of ['build 016 council decision coverage', 'pre-2024', 'incomplete seed', 'approved-minutes']) {
      if (!sourcesText.includes(phrase)) throw new Error(`${viewportName}: Build 016 source coverage missing "${phrase}"`);
    }
    if (await page.locator('.b16-source-coverage .build006-doc-link').count() !== 7) throw new Error(`${viewportName}: expected 7 legacy source links`);
    const sourceDims = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
    if (sourceDims.scrollWidth > sourceDims.clientWidth + 2) throw new Error(`${viewportName}: Build 016 sources view caused horizontal overflow`);
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build016-sources.png`, fullPage: true });

    report.views.push({ viewport: viewportName, ...stats });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build016-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
