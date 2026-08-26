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
  await page.waitForFunction(() => typeof window.b13Data === 'function' && window.b13Data()?.community_grants_2025?.council_approved_total === 476430, null, { timeout: 15000 });
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

    await openRoute(page, 'benchmarks');
    const fundingText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of [
      'community funding context', 'funding context, not suspicion scoring',
      '2025/26 community grants', 'council-approved total',
      '2025 community museum funding', 'rural transit funding',
      'repeat funding is an explicit program feature', 'not invoices or vendor payments'
    ]) {
      if (!fundingText.includes(phrase.toLowerCase())) throw new Error(`${viewportName}/benchmarks: missing "${phrase}"`);
    }

    const facts = await page.evaluate(() => {
      const grants = window.b13CommunityGrants();
      const museums = window.b13Museums();
      const transit = window.b13Transit();
      const amendments = window.b13Amendments();
      const museumRows = window.b13MuseumRows();
      const operating = new Set(museums.operating_grants.map(row => row.recipient.toLowerCase()));
      return {
        grantCategories: grants.categories.length,
        grantApplications: grants.categories.reduce((sum, row) => sum + Number(row.applications || 0), 0),
        grantRequested: grants.categories.reduce((sum, row) => sum + Number(row.requested || 0), 0),
        grantRecommendedAwards: grants.categories.reduce((sum, row) => sum + Number(row.recommended_awards || 0), 0),
        grantRecommendedTotal: grants.categories.reduce((sum, row) => sum + Number(row.recommended_amount || 0), 0),
        grantFinalTotal: grants.council_approved_total,
        museumRows: museumRows.length,
        museumOperating: museums.operating_grants.reduce((sum, row) => sum + Number(row.amount || 0), 0),
        museumProjects: museums.project_grants.reduce((sum, row) => sum + Number(row.amount || 0), 0),
        museumOverlap: museums.project_grants.filter(row => operating.has(row.recipient.toLowerCase())).length,
        transitProviders: transit.providers.length,
        transitPrior: transit.providers.reduce((sum, row) => sum + Number(row.prior_disbursement || 0), 0),
        transitProjected: transit.providers.reduce((sum, row) => sum + Number(row.projected_grant || 0), 0),
        amendmentObservations: amendments.length,
        amendmentMathFlags: amendments.filter(row => row.source_arithmetic_consistent === false).length,
        amendmentLeads: window.b13AmendmentInvestigations().length
      };
    });

    if (facts.grantCategories !== 7 || facts.grantApplications !== 120 || facts.grantRecommendedAwards !== 63) throw new Error(`${viewportName}/benchmarks: Community Grants count controls failed`);
    if (Math.abs(facts.grantRequested - 1224009.14) > 0.02 || Math.abs(facts.grantRecommendedTotal - 480430) > 0.02 || Math.abs(facts.grantFinalTotal - 476430) > 0.02) throw new Error(`${viewportName}/benchmarks: Community Grants value controls failed`);
    if (facts.museumRows !== 22 || Math.abs(facts.museumOperating - 157890) > 0.02 || Math.abs(facts.museumProjects - 55920) > 0.02 || facts.museumOverlap !== 8) throw new Error(`${viewportName}/benchmarks: museum funding controls failed`);
    if (facts.transitProviders !== 4 || Math.abs(facts.transitPrior - 452696) > 0.02 || Math.abs(facts.transitProjected - 503851) > 0.02) throw new Error(`${viewportName}/benchmarks: rural-transit controls failed`);
    if (facts.amendmentObservations !== 8 || facts.amendmentMathFlags !== 1 || facts.amendmentLeads < 5) throw new Error(`${viewportName}: amendment controls failed`);
    await assertNoOverflow(page, viewportName, 'benchmarks');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build013-funding.png`, fullPage: true });

    await openRoute(page, 'vendors');
    const vendorText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['historical cao amendment context', 'nov. 15, 2023', 'source arithmetic flags', 'private/confidential', 'not a complete historical amendment ledger']) {
      if (!vendorText.includes(phrase.toLowerCase())) throw new Error(`${viewportName}/vendors: missing "${phrase}"`);
    }
    const amendmentRows = page.locator('[data-build013-amendment]');
    if (await amendmentRows.count() !== 8) throw new Error(`${viewportName}/vendors: expected eight amendment observations`);
    const mismatchId = await page.evaluate(() => window.b13Amendments().find(row => row.source_arithmetic_consistent === false)?.id || null);
    if (!mismatchId) throw new Error(`${viewportName}/vendors: missing source arithmetic mismatch`);
    await page.locator(`[data-build013-amendment="${mismatchId}"]`).click();
    await page.waitForSelector('#evidence-drawer[open]');
    const drawerText = (await page.locator('#drawer-body').innerText()).toLowerCase();
    for (const phrase of ['source arithmetic delta', 'source values preserved without correction', 'private & confidential amendment reports are excluded', 'not an invoice', 'not a complete contract history']) {
      if (!drawerText.includes(phrase)) throw new Error(`${viewportName}/vendors drawer: missing "${phrase}"`);
    }
    await closeDrawer(page);
    await assertNoOverflow(page, viewportName, 'vendors');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build013-vendors.png`, fullPage: true });

    await openRoute(page, 'signals');
    await page.waitForFunction(() => [...document.querySelectorAll('#investigation-domain option')].some(option => option.value === 'Contract amendments'), null, { timeout: 15000 });
    await page.locator('#investigation-domain').selectOption('Contract amendments');
    const cards = page.locator('#content [data-build008-investigation-id^="b13-amend-"]');
    if (await cards.count() < 5) throw new Error(`${viewportName}/investigations: insufficient Build 013 amendment leads`);
    const signalText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['contract amendments', 'private/confidential amendment reports excluded', 'published amendment value']) {
      if (!signalText.includes(phrase)) throw new Error(`${viewportName}/investigations: missing "${phrase}"`);
    }
    await cards.first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    const investigationDrawer = (await page.locator('#drawer-body').innerText()).toLowerCase();
    for (const phrase of ['published amendment value', 'source-stated reason', 'not necessarily the current change-order request', 'not evidence of corruption']) {
      if (!investigationDrawer.includes(phrase)) throw new Error(`${viewportName}/investigations drawer: missing "${phrase}"`);
    }
    await closeDrawer(page);
    await assertNoOverflow(page, viewportName, 'signals');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build013-investigations.png`, fullPage: true });

    await openRoute(page, 'sources');
    const sourceText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['build 013 context sources', 'community funding', 'procurement policy', 'complete grants or contract-amendment ledger']) {
      if (!sourceText.includes(phrase)) throw new Error(`${viewportName}/sources: missing "${phrase}"`);
    }
    if (await page.locator('.b13-source-grid > div').count() !== 6) throw new Error(`${viewportName}/sources: expected six Build 013 source records`);
    await assertNoOverflow(page, viewportName, 'sources');

    report.views.push({ viewport: viewportName, ...facts, amendmentCards: await cards.count() });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build013-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
