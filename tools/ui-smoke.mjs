import { chromium } from 'playwright';
import fs from 'node:fs/promises';

const BASE_URL = (process.env.HALIFAXDATA_URL || 'http://127.0.0.1:8000/').replace(/\/?$/, '/');
const OUTPUT = 'artifacts/ui-smoke';
const routes = [
  ['overview', 'Command Center'],
  ['budget', 'Budget & Actuals'],
  ['financials', 'Financial Statements'],
  ['people', 'People & Compensation'],
  ['spending', 'Spend Explorer'],
  ['vendors', 'Vendors & Contracts'],
  ['projects', 'Capital Projects'],
  ['council', 'Council & Decisions'],
  ['benchmarks', 'Benchmarks & Funding'],
  ['signals', 'Signals Lab'],
  ['sources', 'Sources & Evidence']
];
const RELEASED_DOMAINS = ['budget', 'spending', 'procurement', 'capital', 'financials', 'council'];
const viewports = [
  ['desktop', { width: 1440, height: 1100 }],
  ['mobile', { width: 390, height: 844 }]
];
const OPTIONAL_404_SUFFIXES = ['/data/generated/signals.json'];

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
  released_domains: []
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

async function assertReleasedDomainsReady(page, viewportName) {
  await openRoute(page, 'overview');
  await page.waitForFunction(domains => domains.every(domain => {
    const card = document.querySelector(`.coverage-card[data-domain="${domain}"]`);
    const badge = card?.querySelector('.badge')?.textContent?.trim() || '';
    return badge.startsWith('Ready');
  }), RELEASED_DOMAINS, { timeout: 15000 });

  const statuses = await page.evaluate(domains => Object.fromEntries(domains.map(domain => {
    const card = document.querySelector(`.coverage-card[data-domain="${domain}"]`);
    return [domain, card?.querySelector('.badge')?.textContent?.trim() || ''];
  })), RELEASED_DOMAINS);

  for (const domain of RELEASED_DOMAINS) {
    const status = statuses[domain] || '';
    if (!status.startsWith('Ready')) throw new Error(`${viewportName}/coverage: ${domain} is not Ready (${status || 'blank'})`);
    if (/pending|missing|error|awaiting/i.test(status)) throw new Error(`${viewportName}/coverage: ${domain} has a non-release state (${status})`);
  }
  report.released_domains.push({ viewport: viewportName, statuses });
}

async function assertBuild006DataViews(page, viewportName) {
  await openRoute(page, 'overview');
  const overviewText = await page.locator('#content').innerText();
  for (const phrase of ['Cross-domain review leads', 'Coverage gaps that still matter', 'No transaction-level AP ledger yet']) {
    if (!overviewText.includes(phrase)) throw new Error(`${viewportName}/overview: missing Build 006 intelligence phrase "${phrase}"`);
  }

  await openRoute(page, 'budget');
  await page.waitForFunction(() => /Historical budget evidence/i.test(document.querySelector('#content')?.innerText || ''), null, { timeout: 15000 });
  const historyRows = await page.locator('[data-budget-history-index]').count();
  if (historyRows < 1) throw new Error(`${viewportName}/budget: historical budget rows did not render`);
  await page.locator('[data-budget-history-index]').first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  const historyDrawer = (await page.locator('#drawer-eyebrow').textContent())?.trim();
  if (historyDrawer !== 'HISTORICAL BUDGET EVIDENCE') throw new Error(`${viewportName}/budget: historical evidence drawer did not open`);
  await closeDrawer(page);

  await openRoute(page, 'spending');
  const spendingText = await page.locator('#content').innerText();
  if (!spendingText.includes('not invoice or accounts-payable transactions')) throw new Error(`${viewportName}/spending: transaction-granularity boundary is missing`);
  if (!spendingText.includes('1,094')) throw new Error(`${viewportName}/spending: expected 1,094 quarterly summary rows`);
  const spendingHeaders = (await page.locator('#content table').first().locator('th').allTextContents()).map(text => text.trim());
  if (spendingHeaders.includes('Vendor') || spendingHeaders.includes('Project')) throw new Error(`${viewportName}/spending: unsupported transaction columns are still present`);
  await page.locator('[data-spending-index]').first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  const spendingDrawerText = await page.locator('#drawer-body').innerText();
  if (!spendingDrawerText.includes('Not a transaction')) throw new Error(`${viewportName}/spending: source-row evidence boundary missing`);
  await closeDrawer(page);

  await openRoute(page, 'vendors');
  const vendorText = await page.locator('#content').innerText();
  if (!vendorText.includes('Top collected award concentration') || !vendorText.includes('5,502')) throw new Error(`${viewportName}/vendors: award concentration integration is incomplete`);

  await openRoute(page, 'projects');
  const projectText = await page.locator('#content').innerText();
  if (!projectText.includes('Historical-project boundary') || !projectText.includes('2,650')) throw new Error(`${viewportName}/projects: historical capital boundary/count missing`);
  const capitalHeaders = (await page.locator('#content table').first().locator('th').allTextContents()).map(text => text.trim());
  if (capitalHeaders.includes('Current budget') || capitalHeaders.includes('Actual spend')) throw new Error(`${viewportName}/projects: unsupported current cost columns are still present`);

  await openRoute(page, 'financials');
  const financialText = await page.locator('#content').innerText();
  if (!financialText.includes('Audited statement explorer') || !financialText.includes('350')) throw new Error(`${viewportName}/financials: audited statement integration is incomplete`);
  const financialRows = await page.locator('[data-financial-index]').count();
  if (financialRows < 1) throw new Error(`${viewportName}/financials: no audited statement rows rendered`);
  await page.locator('[data-financial-index]').first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  await closeDrawer(page);

  await openRoute(page, 'council');
  const councilText = await page.locator('#content').innerText();
  if (!councilText.includes('Finance-tagged agenda attachments') || !councilText.includes('179')) throw new Error(`${viewportName}/council: finance document graph is not exposed`);
  const councilRows = await page.locator('[data-council-id]').count();
  if (councilRows < 1) throw new Error(`${viewportName}/council: no finance-context meetings rendered`);
  await page.locator('[data-council-id]').first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  const councilDrawerText = await page.locator('#drawer-body').innerText();
  if (!councilDrawerText.includes('Not an approval finding')) throw new Error(`${viewportName}/council: decision-evidence boundary missing`);
  await closeDrawer(page);

  await openRoute(page, 'benchmarks');
  const benchmarkText = await page.locator('#content').innerText();
  for (const phrase of ['HRM benchmark facts', '48', 'HRM funding facts', '14', 'Province program context', '212', 'Context ≠ Halifax']) {
    if (!benchmarkText.toLowerCase().includes(phrase.toLowerCase())) throw new Error(`${viewportName}/benchmarks: missing "${phrase}"`);
  }
  const benchmarkRows = await page.locator('[data-benchmark-origin]').count();
  if (benchmarkRows < 1) throw new Error(`${viewportName}/benchmarks: no scoped municipal context rows rendered`);
  await page.locator('[data-benchmark-origin]').first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  await closeDrawer(page);

  report.interactions.push({ viewport: viewportName, check: 'Build 006 full data-to-UI integration' });
}

try {
  for (const [viewportName, viewport] of viewports) {
    const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
    const page = await context.newPage();

    page.on('console', message => {
      if (message.type() !== 'error') return;
      const text = message.text();
      if (text.startsWith('Failed to load resource: the server responded with a status of 404')) return;
      report.console_errors.push({ viewport: viewportName, text });
    });
    page.on('pageerror', error => report.page_errors.push({ viewport: viewportName, text: error.message }));
    page.on('response', response => {
      if (response.status() < 400) return;
      const url = new URL(response.url());
      const record = { viewport: viewportName, status: response.status(), url: response.url() };
      const expectedOptional404 = response.status() === 404 && OPTIONAL_404_SUFFIXES.some(suffix => url.pathname.endsWith(suffix));
      if (expectedOptional404) report.expected_optional_404s.push(record);
      else report.http_errors.push(record);
    });

    for (const [route, expectedTitle] of routes) {
      await openRoute(page, route);
      const title = await page.locator('#view-title').textContent();
      if (title?.trim() !== expectedTitle) throw new Error(`${viewportName}/${route}: expected title "${expectedTitle}", got "${title?.trim()}"`);

      const viewState = await page.evaluate(() => {
        const body = getComputedStyle(document.body);
        const content = document.querySelector('#content');
        const error = document.querySelector('.error-state');
        return {
          body_background: body.backgroundColor,
          body_color: body.color,
          content_text_length: content?.innerText?.trim().length || 0,
          data_mode: document.querySelector('#data-mode')?.textContent?.trim() || null,
          error_text: error?.textContent?.trim() || null,
          scroll_width: document.documentElement.scrollWidth,
          client_width: document.documentElement.clientWidth
        };
      });
      if (viewState.error_text) throw new Error(`${viewportName}/${route}: ${viewState.error_text}`);
      if (viewState.content_text_length < 40) throw new Error(`${viewportName}/${route}: rendered content is unexpectedly sparse`);
      if (viewState.scroll_width > viewState.client_width + 2) throw new Error(`${viewportName}/${route}: horizontal page overflow ${viewState.scroll_width}px > ${viewState.client_width}px`);

      await page.screenshot({ path: `${OUTPUT}/${viewportName}-${route}.png`, fullPage: true });
      report.views.push({ viewport: viewportName, route, title: title.trim(), ...viewState });
    }

    await assertReleasedDomainsReady(page, viewportName);
    await assertBuild006DataViews(page, viewportName);

    await openRoute(page, 'overview');
    const allYearsCount = (await page.locator('.metrics-grid .metric-card').nth(1).locator('.metric-value').textContent())?.trim();
    await page.locator('#global-year').selectOption('2025');
    await page.waitForFunction(() => document.querySelector('#global-year')?.value === '2025');
    const filteredCount = (await page.locator('.metrics-grid .metric-card').nth(1).locator('.metric-value').textContent())?.trim();
    if (!allYearsCount || !filteredCount || allYearsCount === filteredCount) throw new Error(`${viewportName}/filters: fiscal-year filter did not change the compensation disclosure count`);
    report.interactions.push({ viewport: viewportName, check: 'fiscal-year filter', before: allYearsCount, after: filteredCount });
    await page.locator('#global-year').selectOption('all');
    await page.waitForFunction(() => document.querySelector('#global-year')?.value === 'all');

    await page.locator('#global-search').fill('Campbell');
    await page.locator('#global-search').press('Enter');
    await page.waitForSelector('#evidence-drawer[open]');
    const searchTitle = (await page.locator('#drawer-title').textContent())?.trim() || '';
    if (!searchTitle.startsWith('Search: Campbell')) throw new Error(`${viewportName}/search: unexpected drawer title "${searchTitle}"`);
    const personSearchResults = page.locator('#drawer-body [data-search-person]');
    if (await personSearchResults.count() < 1) throw new Error(`${viewportName}/search: expected at least one compensation person result`);
    await personSearchResults.first().click();
    await page.waitForSelector('#evidence-drawer[open] .mini-history');
    const personHistoryRows = await page.locator('#evidence-drawer .mini-history > div').count();
    if (personHistoryRows < 1) throw new Error(`${viewportName}/person-evidence: no disclosure history rendered`);
    const officialHref = await page.locator('#evidence-drawer .source-link').getAttribute('href');
    if (!officialHref || !/^https?:\/\//.test(officialHref)) throw new Error(`${viewportName}/person-evidence: official source link missing or invalid`);
    report.interactions.push({ viewport: viewportName, check: 'global search + person history + source link', history_rows: personHistoryRows, source_url: officialHref });
    await closeDrawer(page);

    await openRoute(page, 'signals');
    await page.waitForFunction(() => /validation pending/i.test(document.querySelector('#content')?.innerText || ''), null, { timeout: 15000 });
    report.interactions.push({ viewport: viewportName, check: 'signals validation-pending state' });

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
      report.interactions.push({ viewport: viewportName, check: 'evidence standard drawer' });
      await closeDrawer(page);
    } else {
      await openRoute(page, 'overview');
      await page.locator('#menu-button').click();
      await page.waitForFunction(() => document.querySelector('#sidebar')?.classList.contains('open'));
      await page.locator('#nav [data-view="council"]').click();
      await page.waitForFunction(() => document.querySelector('#view-title')?.textContent?.trim() === 'Council & Decisions');
      const sidebarStillOpen = await page.locator('#sidebar').evaluate(element => element.classList.contains('open'));
      if (sidebarStillOpen) throw new Error('mobile/navigation: sidebar remained open after Build 006 route navigation');
      report.interactions.push({ viewport: viewportName, check: 'compact Build 006 navigation' });
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
