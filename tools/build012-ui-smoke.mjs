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
    await page.waitForFunction(() => /authority-backed oversight/i.test(document.querySelector('#content')?.innerText || ''), null, { timeout: 15000 });
    const overviewText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['authority-backed oversight', 'policy-noncompliance findings', 'substantiated-wrongdoing findings']) {
      if (!overviewText.includes(phrase)) throw new Error(`${viewportName}/overview: missing Build 012 phrase "${phrase}"`);
    }
    const findingCards = page.locator('[data-build012-finding]');
    if (await findingCards.count() < 6) throw new Error(`${viewportName}/overview: expected authority-backed finding cards`);
    await findingCards.first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    if ((await page.locator('#drawer-eyebrow').textContent())?.trim() !== 'AUTHORITY FINDING') {
      throw new Error(`${viewportName}/overview: authority finding drawer did not open`);
    }
    const drawerText = (await page.locator('#drawer-body').innerText()).toLowerCase();
    if (!drawerText.includes('interpretation boundary')) throw new Error(`${viewportName}/overview: authority interpretation boundary missing`);
    await page.locator('#drawer-close').click();
    await assertNoOverflow(page, viewportName, 'overview');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build012-overview.png`, fullPage: true });

    await openRoute(page, 'signals');
    await page.waitForFunction(() => /evidence status ladder/i.test(document.querySelector('#content')?.innerText || ''), null, { timeout: 15000 });
    const investigationText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['evidence status ladder', 'control weakness', 'policy noncompliance', 'referred for investigation', 'substantiated wrongdoing', 'planned independent audits']) {
      if (!investigationText.includes(phrase)) throw new Error(`${viewportName}/signals: missing "${phrase}"`);
    }
    const statusCounts = await page.evaluate(() => window.b12StatusCounts());
    if (statusCounts.referred_for_investigation !== 0) throw new Error(`${viewportName}/signals: referral tier must remain zero in Build 012 artifact`);
    if (statusCounts.substantiated_wrongdoing !== 0) throw new Error(`${viewportName}/signals: wrongdoing tier must remain zero in Build 012 artifact`);
    if (statusCounts.policy_noncompliance !== 4) throw new Error(`${viewportName}/signals: expected four policy-noncompliance findings`);
    await assertNoOverflow(page, viewportName, 'signals');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build012-investigations.png`, fullPage: true });

    await openRoute(page, 'vendors');
    await page.waitForFunction(() => /contract amendment oversight/i.test(document.querySelector('#content')?.innerText || ''), null, { timeout: 15000 });
    const vendorText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['contract amendment oversight', 'fathom studio inc.', '115%', 'source arithmetic mismatch']) {
      if (!vendorText.includes(phrase)) throw new Error(`${viewportName}/vendors: missing "${phrase}"`);
    }
    const amendmentRows = page.locator('[data-build012-amendment]');
    if (await amendmentRows.count() !== 5) throw new Error(`${viewportName}/vendors: expected five selected amendment rows`);
    await amendmentRows.filter({ hasText: 'Fathom Studio Inc.' }).click();
    await page.waitForSelector('#evidence-drawer[open]');
    const amendmentDrawer = (await page.locator('#drawer-body').innerText()).toLowerCase();
    if (!amendmentDrawer.includes('published arithmetic delta')) throw new Error(`${viewportName}/vendors: source arithmetic evidence missing from amendment drawer`);
    if (!amendmentDrawer.includes('$95.23')) throw new Error(`${viewportName}/vendors: preserved Fathom arithmetic discrepancy not visible`);
    await page.locator('#drawer-close').click();
    await assertNoOverflow(page, viewportName, 'vendors');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build012-vendors.png`, fullPage: true });

    await openRoute(page, 'sources');
    await page.waitForFunction(() => /integrity source coverage/i.test(document.querySelector('#content')?.innerText || ''), null, { timeout: 15000 });
    const sourceText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['integrity source coverage', 'office of the mayor expenses audit', 'capital budgeting audit', '2024 mayoral candidate campaign finance disclosure', 'campaign-to-vendor relationships asserted']) {
      if (!sourceText.includes(phrase)) throw new Error(`${viewportName}/sources: missing "${phrase}"`);
    }
    const sourceState = await page.evaluate(() => ({
      merged: window.b12SourcesMergedStatus(),
      supplementCount: window.b12SupplementSources().length,
      campaignRelationships: window.b12Meta().campaign_relationship_records
    }));
    if (!sourceState.merged) throw new Error(`${viewportName}/sources: supplemental source registry was not merged`);
    if (sourceState.supplementCount !== 9) throw new Error(`${viewportName}/sources: expected nine supplemental source records`);
    if (sourceState.campaignRelationships !== 0) throw new Error(`${viewportName}/sources: campaign relationship count must remain zero`);
    await assertNoOverflow(page, viewportName, 'sources');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build012-sources.png`, fullPage: true });

    report.views.push({ viewport: viewportName, statusCounts, sourceState });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build012-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
