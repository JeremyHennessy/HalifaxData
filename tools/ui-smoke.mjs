import { chromium } from 'playwright';
import fs from 'node:fs/promises';

const BASE_URL = process.env.HALIFAXDATA_URL || 'http://127.0.0.1:8000/';
const OUTPUT = 'artifacts/ui-smoke';
const routes = [
  ['overview', 'Command Center'],
  ['budget', 'Budget & Actuals'],
  ['people', 'People & Compensation'],
  ['spending', 'Spend Explorer'],
  ['vendors', 'Vendors & Contracts'],
  ['projects', 'Capital Projects'],
  ['signals', 'Signals Lab'],
  ['sources', 'Sources & Evidence']
];
const viewports = [
  ['desktop', { width: 1440, height: 1100 }],
  ['mobile', { width: 390, height: 844 }]
];
const OPTIONAL_404_PATHS = new Set([
  '/data/generated/spending.json',
  '/data/generated/procurement.json',
  '/data/generated/capital.json',
  '/data/generated/financials.json',
  '/data/generated/council.json',
  '/data/generated/signals.json'
]);

await fs.rm(OUTPUT, { recursive: true, force: true });
await fs.mkdir(OUTPUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const report = {
  generated_at: new Date().toISOString(),
  base_url: BASE_URL,
  console_errors: [],
  page_errors: [],
  http_errors: [],
  expected_optional_404s: [],
  views: [],
  interactions: []
};

async function waitForDashboard(page) {
  await page.waitForSelector('#content', { state: 'visible' });
  await page.waitForFunction(() => {
    const content = document.querySelector('#content');
    return content && !content.querySelector('.loading-card');
  });
}

async function openRoute(page, route) {
  await page.goto(`${BASE_URL}#${route}`, { waitUntil: 'networkidle' });
  await waitForDashboard(page);
}

async function closeDrawer(page) {
  const drawer = page.locator('#evidence-drawer');
  if (await drawer.getAttribute('open') !== null) {
    await page.locator('#drawer-close').click();
    await page.waitForFunction(() => !document.querySelector('#evidence-drawer')?.open);
  }
}

try {
  for (const [viewportName, viewport] of viewports) {
    const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
    const page = await context.newPage();

    page.on('console', message => {
      if (message.type() !== 'error') return;
      const text = message.text();
      // Chromium emits a generic console error for every HTTP 404. Exact URLs are
      // classified separately in the response handler below so unexpected 404s
      // still fail the smoke test.
      if (text === 'Failed to load resource: the server responded with a status of 404 (File not found)') return;
      report.console_errors.push({ viewport: viewportName, text });
    });
    page.on('pageerror', error => report.page_errors.push({ viewport: viewportName, text: error.message }));
    page.on('response', response => {
      if (response.status() < 400) return;
      const url = new URL(response.url());
      const record = { viewport: viewportName, status: response.status(), url: response.url() };
      if (response.status() === 404 && OPTIONAL_404_PATHS.has(url.pathname)) {
        report.expected_optional_404s.push(record);
      } else {
        report.http_errors.push(record);
      }
    });

    for (const [route, expectedTitle] of routes) {
      await openRoute(page, route);

      const title = await page.locator('#view-title').textContent();
      if (title?.trim() !== expectedTitle) {
        throw new Error(`${viewportName}/${route}: expected title "${expectedTitle}", got "${title?.trim()}"`);
      }

      const state = await page.evaluate(() => {
        const body = getComputedStyle(document.body);
        const sidebar = document.querySelector('.sidebar');
        const content = document.querySelector('#content');
        const dataMode = document.querySelector('#data-mode');
        const error = document.querySelector('.error-state');
        return {
          body_background: body.backgroundColor,
          body_color: body.color,
          sidebar_display: sidebar ? getComputedStyle(sidebar).display : null,
          content_text_length: content?.innerText?.trim().length || 0,
          data_mode: dataMode?.textContent?.trim() || null,
          error_text: error?.textContent?.trim() || null,
          scroll_width: document.documentElement.scrollWidth,
          client_width: document.documentElement.clientWidth
        };
      });

      if (state.error_text) throw new Error(`${viewportName}/${route}: ${state.error_text}`);
      if (state.content_text_length < 40) throw new Error(`${viewportName}/${route}: rendered content is unexpectedly sparse`);
      if (state.scroll_width > state.client_width + 2) {
        throw new Error(`${viewportName}/${route}: horizontal page overflow ${state.scroll_width}px > ${state.client_width}px`);
      }

      await page.screenshot({
        path: `${OUTPUT}/${viewportName}-${route}.png`,
        fullPage: true
      });

      report.views.push({ viewport: viewportName, route, title: title.trim(), ...state });
    }

    // Global filter: prove the disclosure count changes under a real fiscal-year filter.
    await openRoute(page, 'overview');
    const allYearsCount = (await page.locator('.metrics-grid .metric-card').nth(1).locator('.metric-value').textContent())?.trim();
    await page.locator('#global-year').selectOption('2025');
    await page.waitForFunction(() => document.querySelector('#global-year')?.value === '2025');
    const filteredCount = (await page.locator('.metrics-grid .metric-card').nth(1).locator('.metric-value').textContent())?.trim();
    if (!allYearsCount || !filteredCount || allYearsCount === filteredCount) {
      throw new Error(`${viewportName}/filters: fiscal-year filter did not change the compensation disclosure count`);
    }
    report.interactions.push({ viewport: viewportName, check: 'fiscal-year filter', before: allYearsCount, after: filteredCount });

    // Reset without relying on a control that the compact mobile layout may intentionally hide.
    await page.locator('#global-year').selectOption('all');
    await page.waitForFunction(() => document.querySelector('#global-year')?.value === 'all');

    // Global search -> person evidence -> historical disclosure -> official source link.
    await page.locator('#global-search').fill('Campbell');
    await page.locator('#global-search').press('Enter');
    await page.waitForSelector('#evidence-drawer[open]');
    const searchTitle = (await page.locator('#drawer-title').textContent())?.trim() || '';
    if (!searchTitle.startsWith('Search: Campbell')) throw new Error(`${viewportName}/search: unexpected drawer title "${searchTitle}"`);
    const personSearchResults = page.locator('#drawer-body [data-search-person]');
    if (await personSearchResults.count() < 1) throw new Error(`${viewportName}/search: expected at least one compensation person result`);
    await personSearchResults.first().click();
    await page.waitForSelector('#evidence-drawer[open] .mini-history');
    const historyRows = await page.locator('#evidence-drawer .mini-history > div').count();
    if (historyRows < 1) throw new Error(`${viewportName}/person-evidence: no disclosure history rendered`);
    const officialHref = await page.locator('#evidence-drawer .source-link').getAttribute('href');
    if (!officialHref || !/^https?:\/\//.test(officialHref)) throw new Error(`${viewportName}/person-evidence: official source link missing or invalid`);
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-person-evidence.png`, fullPage: false });
    report.interactions.push({ viewport: viewportName, check: 'global search + person history + source link', history_rows: historyRows, source_url: officialHref });
    await closeDrawer(page);

    // Missing-domain state must remain explicit rather than presenting synthetic records.
    await openRoute(page, 'spending');
    const spendingText = (await page.locator('#content').innerText()).toLowerCase();
    if (!spendingText.includes('awaiting generated artifact')) {
      throw new Error(`${viewportName}/spending: missing generated-artifact state is not visible`);
    }
    report.interactions.push({ viewport: viewportName, check: 'missing-domain state', route: 'spending' });

    // Source registry cards must open provenance and expose an official link.
    await openRoute(page, 'sources');
    const sourceCards = page.locator('#content [data-source-id]');
    if (await sourceCards.count() < 1) throw new Error(`${viewportName}/sources: no clickable source records rendered`);
    await sourceCards.first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    const sourceHref = await page.locator('#evidence-drawer .source-link').getAttribute('href');
    if (!sourceHref || !/^https?:\/\//.test(sourceHref)) throw new Error(`${viewportName}/sources: official source link missing or invalid`);
    report.interactions.push({ viewport: viewportName, check: 'source evidence drawer', source_url: sourceHref });
    await closeDrawer(page);

    if (viewportName === 'desktop') {
      // Methodology drawer has a dedicated desktop affordance.
      await openRoute(page, 'overview');
      await page.locator('#evidence-standard').click();
      await page.waitForSelector('#evidence-drawer[open]');
      const methodologyTitle = (await page.locator('#drawer-title').textContent())?.trim();
      if (methodologyTitle !== 'Evidence standard') throw new Error(`desktop/evidence-standard: unexpected title "${methodologyTitle}"`);
      await page.screenshot({ path: `${OUTPUT}/desktop-evidence-standard.png`, fullPage: false });
      report.interactions.push({ viewport: viewportName, check: 'evidence standard drawer' });
      await closeDrawer(page);
    } else {
      // Compact navigation must open, navigate, and close again.
      await openRoute(page, 'overview');
      await page.locator('#menu-button').click();
      await page.waitForFunction(() => document.querySelector('#sidebar')?.classList.contains('open'));
      await page.locator('#nav [data-view="budget"]').click();
      await page.waitForFunction(() => document.querySelector('#view-title')?.textContent?.trim() === 'Budget & Actuals');
      const sidebarStillOpen = await page.locator('#sidebar').evaluate(element => element.classList.contains('open'));
      if (sidebarStillOpen) throw new Error('mobile/navigation: sidebar remained open after route navigation');
      report.interactions.push({ viewport: viewportName, check: 'compact navigation' });
    }

    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/report.json`, JSON.stringify(report, null, 2));

if (report.console_errors.length || report.page_errors.length || report.http_errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}

console.log(JSON.stringify(report, null, 2));