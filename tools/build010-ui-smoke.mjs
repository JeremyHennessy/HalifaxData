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

async function closeDrawer(page) {
  const drawer = page.locator('#evidence-drawer');
  if (await drawer.getAttribute('open') !== null) {
    await page.locator('#drawer-close').click();
    await page.waitForFunction(() => !document.querySelector('#evidence-drawer')?.open);
  }
}

async function assertNoOverflow(page, viewportName, route) {
  const dims = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth
  }));
  if (dims.scrollWidth > dims.clientWidth + 2) {
    throw new Error(`${viewportName}/${route}: horizontal overflow ${dims.scrollWidth}px > ${dims.clientWidth}px`);
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

    await openRoute(page, 'projects');
    await page.waitForFunction(() => /current-capital boundary/i.test(document.querySelector('#content')?.innerText || ''), null, { timeout: 15000 });
    const projectText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of [
      'current 2025/26 projects', '219', 'exact-code plan comparisons', '176',
      'approved adjustment rows', '14', 'explicit budget increases', '$9.5m',
      'historical-project boundary', '2,650', 'not transaction-level spend'
    ]) {
      if (!projectText.includes(phrase.toLowerCase())) throw new Error(`${viewportName}/projects: missing Build 010 phrase "${phrase}"`);
    }

    const currentHeaders = (await page.locator('.b10-current-capital table').first().locator('th').allTextContents()).map(text => text.trim().toLowerCase());
    if (currentHeaders.some(header => header === 'actual spend' || header.includes('spend-to-date') || header === 'final cost')) {
      throw new Error(`${viewportName}/projects: unsupported actual-spend/final-cost column present`);
    }

    const adjustmentCards = page.locator('.b10-current-capital [data-build008-investigation-id^="b10-cap-adjust-"]');
    if (await adjustmentCards.count() !== 2) throw new Error(`${viewportName}/projects: expected exactly two approved budget-increase investigation cards`);
    await adjustmentCards.first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    const adjustmentDrawer = (await page.locator('#drawer-body').innerText()).toLowerCase();
    for (const phrase of ['approved budget before', 'approved increase', 'approved budget after', 'council result', 'passed unanimously', 'not evidence that this amount has been spent']) {
      if (!adjustmentDrawer.includes(phrase)) throw new Error(`${viewportName}/projects adjustment drawer: missing "${phrase}"`);
    }
    await closeDrawer(page);

    const projectRows = page.locator('.b10-current-capital [data-build010-project]');
    if (await projectRows.count() < 100) throw new Error(`${viewportName}/projects: current-project explorer rendered too few rows`);
    await projectRows.first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    if ((await page.locator('#drawer-eyebrow').textContent())?.trim() !== 'CURRENT CAPITAL PLAN EVIDENCE') {
      throw new Error(`${viewportName}/projects: current-plan evidence drawer did not open`);
    }
    const projectDrawer = (await page.locator('#drawer-body').innerText()).toLowerCase();
    if (!projectDrawer.includes('not actual spend')) throw new Error(`${viewportName}/projects: current-project evidence boundary missing`);
    await closeDrawer(page);

    if (await page.locator('.b10-current-capital [data-build008-investigation-id^="b10-cap-plan-"]').count() < 5) {
      throw new Error(`${viewportName}/projects: expected multiple exact-code plan movement cards`);
    }
    await assertNoOverflow(page, viewportName, 'projects');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build010-projects.png`, fullPage: true });

    await openRoute(page, 'signals');
    await page.waitForFunction(() => [...document.querySelectorAll('#investigation-domain option')].some(option => option.value === 'Capital'), null, { timeout: 15000 });
    await page.locator('#investigation-domain').selectOption('Capital');
    await page.waitForFunction(() => document.querySelector('#investigation-domain')?.value === 'Capital');
    const capitalCards = page.locator('#content [data-build008-investigation-id^="b10-cap-"]');
    if (await capitalCards.count() < 5) throw new Error(`${viewportName}/investigations: Capital domain did not surface enough Build 010 leads`);
    const signalsText = (await page.locator('#content').innerText()).toLowerCase();
    if (!signalsText.includes('capital')) throw new Error(`${viewportName}/investigations: Capital domain label missing`);
    await assertNoOverflow(page, viewportName, 'signals');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build010-investigations.png`, fullPage: true });

    report.views.push({
      viewport: viewportName,
      currentProjects: await projectRows.count(),
      capitalInvestigationCards: await capitalCards.count()
    });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build010-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
