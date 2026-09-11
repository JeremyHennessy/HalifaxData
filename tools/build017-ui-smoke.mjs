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
      return Boolean(
        panel &&
        ds?.status === 'ready' &&
        ds.data?.metadata?.source_count === 8 &&
        state?.build020AuditedFinancialSources?.status === 'ready'
      );
    }, null, { timeout: 30000 });

    const stats = await page.evaluate(() => {
      const ds = datasetStatus('financials');
      const rows = getRows(ds.data);
      const years = [...new Set(rows.map(row => Number(row.fiscal_year_end)))].sort((a, b) => a - b);
      const rows2018 = rows.filter(row => Number(row.fiscal_year_end) === 2018);
      const corrected2018 = rows2018.filter(row => Boolean(row.ocr_correction));
      const source2018 = sourceById('hrm-financials-2018');
      return {
        rows: rows.length,
        sourceCount: ds.data.metadata.source_count,
        years,
        rows2018: rows2018.length,
        corrected2018: corrected2018.length,
        sourceStatus2018: (ds.data.metadata.source_status || []).find(item => item.source_id === 'hrm-financials-2018') || null,
        runtimeSupplementSources: typeof b17RuntimeSupplementSources === 'function' ? b17RuntimeSupplementSources().length : 0,
        parseGapIds: typeof b17ParseGapIds === 'function' ? b17ParseGapIds() : [],
        partialYears: typeof b20PartialSourceYears === 'function' ? b20PartialSourceYears() : [],
        parser: ds.data.metadata.parser_version,
        ocrAdapter: ds.data.metadata.ocr_adapter_version,
        runtimeSource2018: source2018,
        runtimeSource2019: Boolean(sourceById('hrm-financials-2019')),
        runtimeSource2024: Boolean(sourceById('hrm-financials-2024'))
      };
    });
    if (stats.sourceCount !== 8) throw new Error(`${viewportName}: expected 8 released audited sources, got ${stats.sourceCount}`);
    if (stats.rows !== 1322) throw new Error(`${viewportName}: expected 1,322 audited facts, got ${stats.rows}`);
    if (JSON.stringify(stats.years) !== JSON.stringify([2018,2019,2020,2021,2022,2023,2024,2025])) throw new Error(`${viewportName}: unexpected released source years ${stats.years}`);
    if (stats.rows2018 !== 79 || stats.corrected2018 !== 8) throw new Error(`${viewportName}: unexpected 2018 OCR release shape rows=${stats.rows2018} corrections=${stats.corrected2018}`);
    if (stats.runtimeSupplementSources !== 6 || !stats.runtimeSource2018 || !stats.runtimeSource2019 || !stats.runtimeSource2024) throw new Error(`${viewportName}: Build 020 audited source overlay did not merge correctly`);
    if (JSON.stringify(stats.parseGapIds) !== JSON.stringify([])) throw new Error(`${viewportName}: obsolete 2018 primary-statement parse gap still exposed`);
    if (JSON.stringify(stats.partialYears) !== JSON.stringify([2018])) throw new Error(`${viewportName}: 2018 partial schedule boundary is not explicit`);
    if (stats.parser !== 'build005-financials-v4') throw new Error(`${viewportName}: standard parser semantics unexpectedly changed to ${stats.parser}`);
    if (stats.ocrAdapter !== 'build020-financials-2018-ocr-v4') throw new Error(`${viewportName}: unexpected 2018 OCR adapter ${stats.ocrAdapter}`);
    if (stats.runtimeSource2018.status !== 'ready-ocr-primary-statements-partial-schedules') throw new Error(`${viewportName}: runtime 2018 source status is stale (${stats.runtimeSource2018.status})`);
    if (!String(stats.runtimeSource2018.url || '').includes('180718afsc1211.pdf')) throw new Error(`${viewportName}: runtime 2018 source URL is not the validated Audit & Finance attachment`);
    if (stats.sourceStatus2018?.records !== 79 || stats.sourceStatus2018?.eligible_statement_pages !== 4) throw new Error(`${viewportName}: generated 2018 source status is not the proven 79-row/four-page shape`);

    const text = (await page.locator('.b17-financial-coverage').innerText()).toLowerCase();
    for (const phrase of [
      'audited financial history coverage',
      '2018–2025',
      '2018 partial source coverage',
      '79 normalized primary-statement facts',
      'eight current-year ocr digit corrections',
      '2018 schedules remain unreleased',
      'source-presented prior-year comparators',
      'does not treat repeated comparator values as independent additive facts'
    ]) {
      if (!text.includes(phrase)) throw new Error(`${viewportName}: financial coverage missing "${phrase}"`);
    }
    if (text.includes('2018 source parse gap') || text.includes('zero eligible statement pages')) throw new Error(`${viewportName}: stale 2018 parse-gap wording remains in released financial coverage`);

    // Open a released 2018 row and require the Build 020 overlay to resolve the
    // official source link in the established financial evidence drawer.
    const yearSelect = page.locator('#financial-year');
    await yearSelect.selectOption('2018');
    await page.waitForTimeout(150);
    const row2018 = page.locator('tr[data-financial-index]').first();
    if (await row2018.count() < 1) throw new Error(`${viewportName}: no 2018 financial rows rendered`);
    await row2018.click();
    await page.waitForSelector('#evidence-drawer[open]');
    const drawer = `${await page.locator('#drawer-title').innerText()}\n${await page.locator('#drawer-body').innerText()}`.toLowerCase();
    if (!drawer.includes('hrm-financials-2018')) throw new Error(`${viewportName}: 2018 financial drawer missing source ID`);
    if (!drawer.includes('official source')) throw new Error(`${viewportName}: 2018 financial drawer missing merged official source link`);
    await page.locator('#drawer-close').click();

    const dims = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
    if (dims.scrollWidth > dims.clientWidth + 2) throw new Error(`${viewportName}: Build 020 financial view caused horizontal overflow`);
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build017-financials.png`, fullPage: true });

    await page.goto(`${BASE_URL}#sources`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => document.querySelector('.b17-financial-sources'), null, { timeout: 20000 });
    const sourcesText = (await page.locator('.b17-financial-sources').innerText()).toLowerCase();
    for (const phrase of [
      'build 020 audited financial sources',
      '2018–2025',
      '2018 schedules not released',
      'bounded ocr primary-statement layer',
      'does not create an operating-budget crosswalk',
      'not invoices or accounts-payable transactions'
    ]) {
      if (!sourcesText.includes(phrase)) throw new Error(`${viewportName}: Build 020 source coverage missing "${phrase}"`);
    }
    if (sourcesText.includes('parser gap')) throw new Error(`${viewportName}: stale 2018 parser-gap wording remains on sources view`);
    if (await page.locator('.b17-financial-sources .build006-doc-link').count() !== 6) throw new Error(`${viewportName}: expected 6 supplemental released audited source links`);
    const source2018Href = await page.locator('.b17-financial-sources .build006-doc-link').first().getAttribute('href');
    if (!String(source2018Href || '').includes('180718afsc1211.pdf')) throw new Error(`${viewportName}: first supplemental source is not the validated 2018 Audit & Finance attachment`);
    const sourceDims = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
    if (sourceDims.scrollWidth > sourceDims.clientWidth + 2) throw new Error(`${viewportName}: Build 020 sources view caused horizontal overflow`);
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
