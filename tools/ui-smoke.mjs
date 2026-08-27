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
  ['signals', 'Investigations'],
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
  generated_at: new Date().toISOString(), base_url: BASE_URL,
  console_errors: [], page_errors: [], http_errors: [], expected_optional_404s: [],
  views: [], interactions: [], released_domains: []
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
async function assertText(page, route, phrases) {
  await openRoute(page, route);
  const text = await page.locator('#content').innerText();
  for (const phrase of phrases) {
    if (!text.toLowerCase().includes(phrase.toLowerCase())) throw new Error(`${route}: missing "${phrase}"`);
  }
  return text;
}

async function assertReleasedDomainsReady(page, viewportName) {
  await openRoute(page, 'overview');
  await page.waitForFunction(domains => domains.every(domain => {
    const badge = document.querySelector(`.coverage-card[data-domain="${domain}"] .badge`)?.textContent?.trim() || '';
    return badge.startsWith('Ready');
  }), RELEASED_DOMAINS, { timeout: 15000 });
  const statuses = await page.evaluate(domains => Object.fromEntries(domains.map(domain => [domain, document.querySelector(`.coverage-card[data-domain="${domain}"] .badge`)?.textContent?.trim() || ''])), RELEASED_DOMAINS);
  for (const domain of RELEASED_DOMAINS) {
    const status = statuses[domain] || '';
    if (!status.startsWith('Ready') || /pending|missing|error|awaiting/i.test(status)) throw new Error(`${viewportName}/coverage: ${domain} is not released (${status || 'blank'})`);
  }
  report.released_domains.push({ viewport: viewportName, statuses });
}

async function assertAnalyticalViews(page, viewportName) {
  await assertText(page, 'overview', ['What deserves attention?', 'Budget pressure snapshot', 'Procurement concentration snapshot', 'Data coverage & readiness']);
  const overviewLeads = page.locator('#content [data-build008-investigation-id]');
  if (await overviewLeads.count() < 3) throw new Error(`${viewportName}/overview: expected cross-domain investigation cards`);
  await overviewLeads.first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  if ((await page.locator('#drawer-eyebrow').textContent())?.trim() !== 'INVESTIGATION LEAD') throw new Error(`${viewportName}/overview: investigation evidence drawer did not open`);
  await closeDrawer(page);

  await assertText(page, 'budget', ['Budget pressure analysis', 'Historical budget evidence']);
  if (await page.locator('.b8-budget-pressure [data-build008-investigation-id]').count() < 1) throw new Error(`${viewportName}/budget: no budget-pressure investigation cards rendered`);
  if (await page.locator('[data-budget-history-index]').count() < 1) throw new Error(`${viewportName}/budget: historical budget rows did not render`);
  await page.locator('[data-budget-history-index]').first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  if ((await page.locator('#drawer-eyebrow').textContent())?.trim() !== 'HISTORICAL BUDGET EVIDENCE') throw new Error(`${viewportName}/budget: historical evidence drawer did not open`);
  await closeDrawer(page);

  const spendingText = await assertText(page, 'spending', ['not invoice or accounts-payable transactions', '1,753', 'Quarterly spending movement analysis', 'ambiguous key/dates excluded']);
  if (!spendingText.toLowerCase().includes('comparable movement leads')) throw new Error(`${viewportName}/spending: hero metric was not converted to comparable movements`);
  const spendingHeaders = (await page.locator('#content table').first().locator('th').allTextContents()).map(text => text.trim());
  if (spendingHeaders.includes('Vendor') || spendingHeaders.includes('Project')) throw new Error(`${viewportName}/spending: unsupported transaction columns are present`);
  if (await page.locator('.b8-spending-movement [data-build008-investigation-id]').count() < 1) throw new Error(`${viewportName}/spending: no comparable movement cards rendered`);
  await page.locator('[data-spending-index]').first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  if (!(await page.locator('#drawer-body').innerText()).includes('Not a transaction')) throw new Error(`${viewportName}/spending: source-row transaction boundary missing`);
  await closeDrawer(page);

  await assertText(page, 'vendors', ['5,502', 'Procurement concentration & repeat awards', 'Candidate vendor identity matches', 'Top collected award concentration']);
  if (await page.locator('.b8-procurement-analysis [data-build008-investigation-id]').count() < 1) throw new Error(`${viewportName}/vendors: no concentration/repeat-award cards rendered`);

  await assertText(page, 'projects', ['Historical-project boundary', '2,650']);
  const capitalHeaders = (await page.locator('#content table').first().locator('th').allTextContents()).map(text => text.trim());
  if (capitalHeaders.includes('Current budget') || capitalHeaders.includes('Actual spend')) throw new Error(`${viewportName}/projects: unsupported current cost columns are present`);

  await assertText(page, 'financials', ['Audited statement explorer', '350']);
  if (await page.locator('[data-financial-index]').count() < 1) throw new Error(`${viewportName}/financials: no audited statement rows rendered`);
  await page.locator('[data-financial-index]').first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  await closeDrawer(page);

  await assertText(page, 'council', ['Finance-tagged agenda attachments', '179']);
  if (await page.locator('[data-council-id]').count() < 1) throw new Error(`${viewportName}/council: no finance-context meetings rendered`);
  await page.locator('[data-council-id]').first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  if (!(await page.locator('#drawer-body').innerText()).includes('Not an approval finding')) throw new Error(`${viewportName}/council: decision-evidence boundary missing`);
  await closeDrawer(page);

  await assertText(page, 'benchmarks', ['HRM benchmark facts', '48', 'HRM funding facts', '14', 'Province program context', '212', 'Context ≠ Halifax']);
  if (await page.locator('[data-benchmark-origin]').count() < 1) throw new Error(`${viewportName}/benchmarks: no scoped municipal context rows rendered`);
  await page.locator('[data-benchmark-origin]').first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  await closeDrawer(page);

  await assertText(page, 'signals', ['Ranked investigations', 'Data-quality queue', 'Scoring interpretation']);
  const signalCards = page.locator('#content [data-build008-investigation-id]');
  if (await signalCards.count() < 3) throw new Error(`${viewportName}/investigations: expected multiple investigation cards`);
  await signalCards.first().click();
  await page.waitForSelector('#evidence-drawer[open]');
  if ((await page.locator('#drawer-eyebrow').textContent())?.trim() !== 'INVESTIGATION LEAD') throw new Error(`${viewportName}/investigations: evidence drawer did not open`);
  await closeDrawer(page);

  report.interactions.push({ viewport: viewportName, check: 'Build 008 investigation analytics and Build 006/007 evidence boundaries' });
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
      if (expectedOptional404) report.expected_optional_404s.push(record); else report.http_errors.push(record);
    });

    for (const [route, expectedTitle] of routes) {
      await openRoute(page, route);
      const title = (await page.locator('#view-title').textContent())?.trim();
      if (title !== expectedTitle) throw new Error(`${viewportName}/${route}: expected title "${expectedTitle}", got "${title}"`);
      const viewState = await page.evaluate(() => {
        const content = document.querySelector('#content'); const error = document.querySelector('.error-state');
        return {
          content_text_length: content?.innerText?.trim().length || 0,
          data_mode: document.querySelector('#data-mode')?.textContent?.trim() || null,
          error_text: error?.textContent?.trim() || null,
          scroll_width: document.documentElement.scrollWidth,
          client_width: document.documentElement.clientWidth
        };
      });
      if (viewState.error_text) throw new Error(`${viewportName}/${route}: ${viewState.error_text}`);
      if (viewState.content_text_length < 40) throw new Error(`${viewportName}/${route}: rendered content is unexpectedly sparse`);
      if (viewState.scroll_width > viewState.client_width + 2) throw new Error(`${viewportName}/${route}: horizontal overflow ${viewState.scroll_width}px > ${viewState.client_width}px`);
      await page.screenshot({ path: `${OUTPUT}/${viewportName}-${route}.png`, fullPage: true });
      report.views.push({ viewport: viewportName, route, title, ...viewState });
    }

    await assertReleasedDomainsReady(page, viewportName);
    await assertAnalyticalViews(page, viewportName);

    await openRoute(page, 'people');
    const allYearsCount = (await page.locator('.metrics-grid .metric-card').first().locator('.metric-value').textContent())?.trim();
    await page.locator('#global-year').selectOption('2025');
    await page.waitForFunction(() => document.querySelector('#global-year')?.value === '2025');
    const filteredCount = (await page.locator('.metrics-grid .metric-card').first().locator('.metric-value').textContent())?.trim();
    if (!allYearsCount || !filteredCount || allYearsCount === filteredCount) throw new Error(`${viewportName}/filters: fiscal-year filter did not change people disclosure count`);
    await page.locator('#global-year').selectOption('all');
    report.interactions.push({ viewport: viewportName, check: 'people fiscal-year filter', before: allYearsCount, after: filteredCount });

    await page.locator('#global-search').fill('Campbell');
    await page.locator('#global-search').press('Enter');
    await page.waitForSelector('#evidence-drawer[open]');
    if (!(await page.locator('#drawer-title').textContent())?.trim().startsWith('Search: Campbell')) throw new Error(`${viewportName}/search: unexpected drawer title`);
    const peopleResults = page.locator('#drawer-body [data-search-person]');
    if (await peopleResults.count() < 1) throw new Error(`${viewportName}/search: expected compensation person result`);
    await peopleResults.first().click();
    await page.waitForSelector('#evidence-drawer[open] .mini-history');
    const sourceHref = await page.locator('#evidence-drawer .source-link').getAttribute('href');
    if (!sourceHref || !/^https?:\/\//.test(sourceHref)) throw new Error(`${viewportName}/person-evidence: official source link missing`);
    await closeDrawer(page);

    await openRoute(page, 'sources');
    const sourceCards = page.locator('#content [data-source-id]');
    if (await sourceCards.count() < 1) throw new Error(`${viewportName}/sources: no source cards`);
    await sourceCards.first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    const registryHref = await page.locator('#evidence-drawer .source-link').getAttribute('href');
    if (!registryHref || !/^https?:\/\//.test(registryHref)) throw new Error(`${viewportName}/sources: official source link missing`);
    await closeDrawer(page);

    if (viewportName === 'desktop') {
      await openRoute(page, 'overview');
      await page.locator('#evidence-standard').click();
      await page.waitForSelector('#evidence-drawer[open]');
      if ((await page.locator('#drawer-title').textContent())?.trim() !== 'Evidence standard') throw new Error('desktop/evidence-standard: wrong drawer title');
      await closeDrawer(page);
    } else {
      await openRoute(page, 'overview');
      await page.locator('#menu-button').click();
      await page.waitForFunction(() => document.querySelector('#sidebar')?.classList.contains('open'));
      await page.locator('#nav [data-view="signals"]').click();
      await page.waitForFunction(() => document.querySelector('#view-title')?.textContent?.trim() === 'Investigations');
      if (await page.locator('#sidebar').evaluate(element => element.classList.contains('open'))) throw new Error('mobile/navigation: sidebar remained open after navigation');
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
