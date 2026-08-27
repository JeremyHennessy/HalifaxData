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

    await page.goto(`${BASE_URL}#financials`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => {
      const panel = document.querySelector('.b17-financial-coverage');
      const ds = typeof datasetStatus === 'function' ? datasetStatus('financials') : null;
      return Boolean(panel && ds?.status === 'ready' && (ds.data?.metadata?.source_count || 0) === 8);
    }, null, { timeout: 30000 });

    const stats = await page.evaluate(() => {
      const ds = datasetStatus('financials');
      const rows = getRows(ds.data);
      const years = [...new Set(rows.map(row => Number(row.fiscal_year_end)))].sort((a, b) => a - b);
      return {
        rows: rows.length,
        sourceCount: ds.data.metadata.source_count,
        years,
        supplementSources: typeof b17SupplementSources === 'function' ? b17SupplementSources().length : 0,
        parser: ds.data.metadata.parser_version,
        runtimeSource2018: Boolean(sourceById('hrm-financials-2018')),
        runtimeSource2024: Boolean(sourceById('hrm-financials-2024'))
      };
    });
    if (stats.sourceCount !== 8) throw new Error(`${viewportName}: expected 8 audited sources, got ${stats.sourceCount}`);
    if (stats.rows < 900) throw new Error(`${viewportName}: audited history unexpectedly sparse (${stats.rows} rows)`);
    if (JSON.stringify(stats.years) !== JSON.stringify([2018,2019,2020,2021,2022,2023,2024,2025])) throw new Error(`${viewportName}: unexpected source years ${stats.years}`);
    if (stats.supplementSources !== 6 || !stats.runtimeSource2018 || !stats.runtimeSource2024) throw new Error(`${viewportName}: supplemental source registry did not merge correctly`);
    if (stats.parser !== 'build005-financials-v4') throw new Error(`${viewportName}: parser semantics unexpectedly changed to ${stats.parser}`);

    const text = (await page.locator('.b17-financial-coverage').innerText()).toLowerCase();
    for (const phrase of [
      'audited financial history coverage',
      '2018–2025',
      'source-presented prior-year comparators',
      'does not treat repeated comparator values as independent additive facts'
    ]) {
      if (!text.includes(phrase)) throw new Error(`${viewportName}: financial coverage missing "${phrase}"`);
    }

    const row2018 = page.locator('tr[data-financial-index]').filter({ hasText: '2018' }).first();
    if (await row2018.count()) {
      await row2018.click();
      await page.waitForSelector('#evidence-drawer[open]');
      const drawer = `${await page.locator('#drawer-title').innerText()}\n${await page.locator('#drawer-body').innerText()}`.toLowerCase();
      if (!drawer.includes('hrm-financials-2018')) throw new Error(`${viewportName}: 2018 financial drawer missing source ID`);
      if (!drawer.includes('official source')) throw new Error(`${viewportName}: 2018 financial drawer missing merged official source link`);
      await page.locator('#drawer-close').click();
    }

    const dims = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
    if (dims.scrollWidth > dims.clientWidth + 2) throw new Error(`${viewportName}: Build 017 financial view caused horizontal overflow`);
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build017-financials.png`, fullPage: true });

    await page.goto(`${BASE_URL}#sources`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => document.querySelector('.b17-financial-sources'), null, { timeout: 20000 });
    const sourcesText = (await page.locator('.b17-financial-sources').innerText()).toLowerCase();
    for (const phrase of ['build 017 audited financial sources', 'six additional official hrm', 'does not create an operating-budget crosswalk']) {
      if (!sourcesText.includes(phrase)) throw new Error(`${viewportName}: Build 017 source coverage missing "${phrase}"`);
    }
    if (await page.locator('.b17-financial-sources .build006-doc-link').count() !== 6) throw new Error(`${viewportName}: expected 6 supplemental audited source links`);
    const sourceDims = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
    if (sourceDims.scrollWidth > sourceDims.clientWidth + 2) throw new Error(`${viewportName}: Build 017 sources view caused horizontal overflow`);
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build017-sources.png`, fullPage: true });

    report.views.push({ viewport: viewportName, ...stats });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build017-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
