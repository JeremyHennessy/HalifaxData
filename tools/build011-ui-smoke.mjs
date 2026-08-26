import { chromium } from 'playwright';
import fs from 'node:fs/promises';

const BASE_URL = (process.env.HALIFAXDATA_URL || 'http://127.0.0.1:8000/').replace(/\/?$/, '/');
const OUTPUT = 'artifacts/ui-smoke';
const viewports = [
  ['desktop', { width: 1440, height: 1100 }],
  ['mobile', { width: 390, height: 844 }]
];
const EXPECTED_TOTAL = 25252794.75;
const EXPECTED_GROUPING_TOTAL = 24332031.75;

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
  await page.waitForFunction(() => window.state?.build011Procurement?.status === 'ready', null, { timeout: 15000 });
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

    await openRoute(page, 'vendors');
    const vendorsText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of [
      '5,502', 'alternative procurement report evidence', '84', '$25.3m',
      '8 quarterly reports', 'grouping-eligible value', '$24.3m',
      'identity unresolved', '4', 'separate procurement evidence layer',
      'not accounts-payable transactions', 'not final paid values',
      '5716', '5776', 'no complete procurement denominator'
    ]) {
      if (!vendorsText.includes(phrase.toLowerCase())) throw new Error(`${viewportName}/vendors: missing Build 011 phrase "${phrase}"`);
    }

    const facts = await page.evaluate(() => {
      const rows = window.b11Rows();
      const eligible = rows.filter(row => row.vendor_identity_eligible_for_grouping === true);
      const unresolved = rows.filter(row => row.vendor_identity_eligible_for_grouping !== true);
      const groups = window.b11VendorGroups();
      return {
        rows: rows.length,
        reports: window.b11Reports().length,
        total: rows.reduce((sum, row) => sum + Number(row.award_value || 0), 0),
        eligibleRows: eligible.length,
        groupingTotal: eligible.reduce((sum, row) => sum + Number(row.award_value || 0), 0),
        unresolvedRows: unresolved.length,
        unresolvedInGroups: groups.some(group => group.rows.some(row => row.vendor_identity_eligible_for_grouping !== true)),
        investigations: window.b11AlternativeInvestigations().length,
        reportCards: document.querySelectorAll('.b11-report-card').length,
        renderedRows: document.querySelectorAll('[data-build011-row]').length
      };
    });
    if (facts.rows !== 84) throw new Error(`${viewportName}/vendors: expected 84 controlled rows, got ${facts.rows}`);
    if (facts.reports !== 8 || facts.reportCards !== 8) throw new Error(`${viewportName}/vendors: expected eight report controls`);
    if (Math.abs(facts.total - EXPECTED_TOTAL) > 0.02) throw new Error(`${viewportName}/vendors: total ${facts.total} != ${EXPECTED_TOTAL}`);
    if (facts.eligibleRows !== 80) throw new Error(`${viewportName}/vendors: expected 80 grouping-eligible rows, got ${facts.eligibleRows}`);
    if (Math.abs(facts.groupingTotal - EXPECTED_GROUPING_TOTAL) > 0.02) throw new Error(`${viewportName}/vendors: grouping total ${facts.groupingTotal} != ${EXPECTED_GROUPING_TOTAL}`);
    if (facts.unresolvedRows !== 4 || facts.unresolvedInGroups) throw new Error(`${viewportName}/vendors: unresolved supplier identities leaked into grouping`);
    if (facts.investigations < 5) throw new Error(`${viewportName}/vendors: expected multiple alternative-procurement investigations`);
    if (facts.renderedRows !== 84) throw new Error(`${viewportName}/vendors: expected all 84 controlled rows rendered, got ${facts.renderedRows}`);

    const changedRowId = await page.evaluate(() => {
      const row = window.b11Rows().find(item => item.source_url_changed_since_graph === true);
      return row ? `${row.report_document_id}:${row.source_page}:${row.source_table}:${row.source_row}` : null;
    });
    if (!changedRowId) throw new Error(`${viewportName}/vendors: no replaced-attachment source row found`);
    await page.locator(`[data-build011-row="${changedRowId}"]`).click();
    await page.waitForSelector('#evidence-drawer[open]');
    if ((await page.locator('#drawer-eyebrow').textContent())?.trim() !== 'ALTERNATIVE PROCUREMENT EVIDENCE') {
      throw new Error(`${viewportName}/vendors: Build 011 evidence drawer did not open`);
    }
    const drawerText = (await page.locator('#drawer-body').innerText()).toLowerCase();
    for (const phrase of ['doc5716', 'exact-title live agenda attachment resolved', 'not an invoice', 'not a complete procurement record']) {
      if (!drawerText.includes(phrase)) throw new Error(`${viewportName}/vendors drawer: missing "${phrase}"`);
    }
    const currentHref = await page.locator('#evidence-drawer a').filter({ hasText: 'Current resolved report attachment' }).getAttribute('href');
    const historicalHref = await page.locator('#evidence-drawer a').filter({ hasText: 'Historical graph attachment URL' }).getAttribute('href');
    if (!currentHref?.endsWith('DocumentId=5776')) throw new Error(`${viewportName}/vendors: resolved attachment does not preserve DocumentId=5776`);
    if (!historicalHref?.endsWith('DocumentId=5716')) throw new Error(`${viewportName}/vendors: historical graph URL does not preserve DocumentId=5716`);
    await closeDrawer(page);

    const unresolvedRowId = await page.evaluate(() => {
      const row = window.b11Rows().find(item => item.vendor_identity_eligible_for_grouping !== true);
      return row ? `${row.report_document_id}:${row.source_page}:${row.source_table}:${row.source_row}` : null;
    });
    await page.locator(`[data-build011-row="${unresolvedRowId}"]`).click();
    await page.waitForSelector('#evidence-drawer[open]');
    const unresolvedDrawer = (await page.locator('#drawer-body').innerText()).toLowerCase();
    if (!unresolvedDrawer.includes('eligible for supplier grouping') || !unresolvedDrawer.includes('no')) {
      throw new Error(`${viewportName}/vendors: unresolved supplier grouping boundary missing`);
    }
    await closeDrawer(page);

    await assertNoOverflow(page, viewportName, 'vendors');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build011-vendors.png`, fullPage: true });

    await openRoute(page, 'signals');
    await page.waitForFunction(() => [...document.querySelectorAll('#investigation-domain option')].some(option => option.value === 'Alternative procurement'), null, { timeout: 15000 });
    await page.locator('#investigation-domain').selectOption('Alternative procurement');
    await page.waitForFunction(() => document.querySelector('#investigation-domain')?.value === 'Alternative procurement');
    const alternativeCards = page.locator('#content [data-build008-investigation-id^="b11-alt-"]');
    if (await alternativeCards.count() < 5) throw new Error(`${viewportName}/investigations: Alternative procurement domain did not surface enough leads`);
    const signalsText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['alternative procurement', 'separate from public-tender awards', 'not a complete procurement denominator']) {
      if (!signalsText.includes(phrase)) throw new Error(`${viewportName}/investigations: missing "${phrase}"`);
    }
    await alternativeCards.first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    const investigationDrawer = (await page.locator('#drawer-body').innerText()).toLowerCase();
    for (const phrase of ['grouping-eligible layer value', 'share of grouping-eligible layer', 'does not combine these values with public-tender awards']) {
      if (!investigationDrawer.includes(phrase)) throw new Error(`${viewportName}/investigations drawer: missing "${phrase}"`);
    }
    await closeDrawer(page);
    await assertNoOverflow(page, viewportName, 'signals');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build011-investigations.png`, fullPage: true });

    report.views.push({ viewport: viewportName, ...facts, alternativeCards: await alternativeCards.count() });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build011-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
