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

    await page.goto(`${BASE_URL}#vendors`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() =>
      typeof window.b14LinkageStats === 'function' &&
      window.b14Data()?.summary?.observation_count === 58 &&
      document.querySelector('.b14-amendment-series'),
      null,
      { timeout: 20000 }
    );

    const stats = await page.evaluate(() => window.b14LinkageStats());
    if (stats.observations !== 58 || stats.fuzzy_links_created !== 0) {
      throw new Error(`${viewportName}: Build 014 related-record boundary failed`);
    }

    await page.locator('[data-build014-trajectory="contract:21-302"]').click();
    await page.waitForSelector('#evidence-drawer[open]');
    const drawerText = (await page.locator('#drawer-body').innerText()).toLowerCase();
    for (const phrase of [
      'related checked records',
      'deterministic source relationships only',
      'missing links remain missing rather than being filled by fuzzy matching',
      'no relationship is inferred from similar vendor names, project names or descriptive text'
    ]) {
      if (!drawerText.includes(phrase)) throw new Error(`${viewportName}: related-record drawer missing "${phrase}"`);
    }
    const dims = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth
    }));
    if (dims.scrollWidth > dims.clientWidth + 2) throw new Error(`${viewportName}: related-record drawer caused horizontal overflow`);

    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build014-related-records.png`, fullPage: true });
    report.views.push({ viewport: viewportName, ...stats });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build014-linkage-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
