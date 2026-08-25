import { chromium } from 'playwright';
import fs from 'node:fs/promises';

const BASE_URL = (process.env.HALIFAXDATA_URL || 'http://127.0.0.1:8000/').replace(/\/?$/, '/');
const OUTPUT = 'artifacts/ui-smoke';
const routes = [
  ['overview', 'Command Center'],
  ['budget', 'Budget & Actuals'],
  ['people', 'People & Compensation'],
  ['spending', 'Spend Explorer'],
  ['vendors', 'Public Tender Awards'],
  ['projects', 'Capital Projects'],
  ['signals', 'Signals Lab'],
  ['sources', 'Sources & Evidence']
];
const viewports = [
  ['desktop', { width: 1440, height: 1100 }],
  ['mobile', { width: 390, height: 844 }]
];
const OPTIONAL_404_SUFFIXES = [
  '/data/generated/spending.json',
  '/data/generated/capital.json',
  '/data/generated/financials.json',
  '/data/generated/council.json',
  '/data/generated/signals.json'
];
const QUALITY_BLOCKED_SUFFIXES = [
  '/data/generated/spending.json',
  '/data/generated/capital.json',
  '/data/generated/financials.json',
  '/data/generated/council.json',
  '/data/generated/signals.json'
];

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
  interactions: [],
  quality_gate: []
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
    const requestedPaths = new Set();

    page.on('console', message => {
      if (message.type() !== 'error') return;
      const text = message.text();
      if (text.startsWith('Failed to load resource: the server responded with a status of 404')) return;
      report.console_errors.push({ viewport: viewportName, text });
    });
    page.on('pageerror', error => report.page_errors.push({ viewport: viewportName, text: error.message }));
    page.on('request', request => {
      try {
        requestedPaths.add(new URL(request.url()).pathname);
      } catch {}
    });
    page.on('response', response => {
      if (response.status() < 400) return;
      const url = new URL(response.url());
      const record = { viewport: viewportName, status: response.status(), url: response.url() };
      const expectedOptional404 = response.status() === 404 && OPTIONAL_404_SUFFIXES.some(suffix => url.pathname.endsWith(suffix));
      if (expectedOptional404) {
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

    // Build 005 quality gate: only validated procurement is fetched among new domains.
    const gate = await page.evaluate(() => window.HalifaxDataQualityGate || null);
    if (!gate || gate.manifest_status !== 'ready') {
      throw new Error(`${viewportName}/quality-gate: manifest is not ready (${gate?.manifest_status || 'missing'})`);
    }
    const blockedDomains = new Set((gate.blocked || []).map(item => item.domain));
    const allowedDomains = new Set((gate.allowed || []).map(item => item.domain));
    for (const domain of ['spending', 'capital', 'financials', 'council', 'signals']) {
      if (!blockedDomains.has(domain)) throw new Error(`${viewportName}/quality-gate: ${domain} was not blocked`);
    }
    if (!allowedDomains.has('procurement')) throw new Error(`${viewportName}/quality-gate: procurement was not explicitly allowed`);
    const unsafeNetworkRequests = [...requestedPaths].filter(path => QUALITY_BLOCKED_SUFFIXES.some(suffix => path.endsWith(suffix)));
    if (unsafeNetworkRequests.length) {
      throw new Error(`${viewportName}/quality-gate: held artifacts reached the network: ${unsafeNetworkRequests.join(', ')}`);
    }
    if (![...requestedPaths].some(path => path.endsWith('/data/generated/procurement.json'))) {
      throw new Error(`${viewportName}/quality-gate: validated procurement artifact was not fetched`);
    }
    report.quality_gate.push({ viewport: viewportName, blocked_domains: [...blockedDomains].sort(), allowed_domains: [...allowedDomains].sort() });

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

    // Held domains must show their evidence-backed quality block instead of invalid facts.
    await openRoute(page, 'spending');
    const spendingText = (await page.locator('#content').innerText()).toLowerCase();
    if (!spendingText.includes('data quality hold') || !spendingText.includes('merged-cell')) {
      throw new Error(`${viewportName}/spending: verified quality-hold state is not visible`);
    }
    report.interactions.push({ viewport: viewportName, check: 'spending quality hold' });

    await openRoute(page, 'projects');
    const capitalText = (await page.locator('#content').innerText()).toLowerCase();
    if (!capitalText.includes('data quality hold') || !capitalText.includes('project-code')) {
      throw new Error(`${viewportName}/capital: verified quality-hold state is not visible`);
    }
    report.interactions.push({ viewport: viewportName, check: 'capital quality hold' });

    // Validated procurement: local search -> exact signed source row -> evidence drawer.
    await openRoute(page, 'vendors');
    const tenderRows = page.locator('#content [data-procurement-row]');
    if (await tenderRows.count() < 1) throw new Error(`${viewportName}/procurement: no tender rows rendered`);
    const entityOptions = await page.locator('#procurement-entity option').count();
    if (entityOptions < 4) throw new Error(`${viewportName}/procurement: expected all-entities option plus three reporting entities`);
    await page.locator('#procurement-search').fill('T15-299');
    await page.waitForFunction(() => document.querySelectorAll('#content [data-procurement-row]').length === 1);
    const filteredTenderText = await page.locator('#content [data-procurement-row]').first().innerText();
    if (!filteredTenderText.includes('John Ross & Sons')) throw new Error(`${viewportName}/procurement: exact source row did not survive local search`);
    await page.locator('#content [data-procurement-row]').first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    const tenderTitle = (await page.locator('#drawer-title').textContent())?.trim();
    const tenderEvidence = await page.locator('#drawer-body').innerText();
    if (tenderTitle !== 'T15-299') throw new Error(`${viewportName}/procurement-evidence: expected T15-299, got ${tenderTitle}`);
    if (!tenderEvidence.includes('John Ross & Sons') || !tenderEvidence.includes('1,500') || !tenderEvidence.toLowerCase().includes('signed source-value boundary')) {
      throw new Error(`${viewportName}/procurement-evidence: signed official source evidence is incomplete`);
    }
    const tenderSourceHref = await page.locator('#evidence-drawer .source-link').getAttribute('href');
    if (!tenderSourceHref || !/^https?:\/\//.test(tenderSourceHref)) throw new Error(`${viewportName}/procurement-evidence: official source link missing or invalid`);
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-procurement-evidence.png`, fullPage: false });
    report.interactions.push({ viewport: viewportName, check: 'procurement search + signed source evidence', tender: 'T15-299', source_url: tenderSourceHref });
    await closeDrawer(page);

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
      await openRoute(page, 'overview');
      await page.locator('#evidence-standard').click();
      await page.waitForSelector('#evidence-drawer[open]');
      const methodologyTitle = (await page.locator('#drawer-title').textContent())?.trim();
      if (methodologyTitle !== 'Evidence standard') throw new Error(`desktop/evidence-standard: unexpected title "${methodologyTitle}"`);
      await page.screenshot({ path: `${OUTPUT}/desktop-evidence-standard.png`, fullPage: false });
      report.interactions.push({ viewport: viewportName, check: 'evidence standard drawer' });
      await closeDrawer(page);
    } else {
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
