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
  await page.waitForFunction(() =>
    typeof window.b14Data === 'function' &&
    window.b14Data()?.summary?.report_count === 12 &&
    window.b14Data()?.summary?.observation_count === 58,
    null,
    { timeout: 20000 }
  );
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
    const facts = await page.evaluate(() => {
      const data = window.b14Data();
      const trajectory = data.trajectories.find(row => row.contract_key === 'contract:21-302');
      return {
        reports: data.summary.report_count,
        readyReports: data.summary.ready_report_count,
        observations: data.summary.observation_count,
        exactKeys: data.summary.unique_contract_keys,
        recurringKeys: data.summary.recurring_exact_contract_keys,
        arithmeticFlags: data.summary.source_arithmetic_flags,
        unkeyed: data.summary.unkeyed_observations,
        legacyRows: data.observations.filter(row => row.report_date === '2023-05-17').length,
        cumulativeRows: data.observations.filter(row => row.report_date === '2025-11-25').length,
        trajectoryDelta: trajectory?.steps?.[0]?.published_cumulative_amendment_delta ?? null,
        oldInvestigationCount: window.b8AllInvestigations().fiscal.filter(item => String(item.id).startsWith('b13-amend-')).length,
        newInvestigationCount: window.b8AllInvestigations().fiscal.filter(item => String(item.id).startsWith('b14-amend-')).length
      };
    });
    if (facts.reports !== 12 || facts.readyReports !== 12 || facts.observations !== 58 || facts.exactKeys !== 54) throw new Error(`${viewportName}/vendors: Build 014 series controls failed`);
    if (facts.recurringKeys !== 1 || facts.arithmeticFlags !== 3 || facts.unkeyed !== 3) throw new Error(`${viewportName}/vendors: Build 014 linkage/data-quality controls failed`);
    if (facts.legacyRows !== 2 || facts.cumulativeRows !== 11 || Math.abs(facts.trajectoryDelta - 23216) > 0.02) throw new Error(`${viewportName}/vendors: Build 014 schema/trajectory controls failed`);
    if (facts.oldInvestigationCount !== 0 || facts.newInvestigationCount < 25) throw new Error(`${viewportName}/vendors: Build 014 investigation replacement controls failed`);

    const vendorText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of [
      'historical cao amendment context — full public series', '12 identified public hrm reports',
      'amendment-report evidence, not payment evidence', 'source arithmetic flags',
      'exact-identifier longitudinal trajectories', 'contract 21-302',
      'not a complete historical amendment ledger', 'private/confidential amendment reports may be excluded'
    ]) {
      if (!vendorText.includes(phrase)) throw new Error(`${viewportName}/vendors: missing "${phrase}"`);
    }
    if (await page.locator('[data-build014-report]').count() !== 12) throw new Error(`${viewportName}/vendors: expected 12 timeline report cards`);
    if (await page.locator('[data-build014-amendment]').count() < 58) throw new Error(`${viewportName}/vendors: expected full-series rows plus quality cards`);

    await page.locator('[data-build014-trajectory="contract:21-302"]').click();
    await page.waitForSelector('#evidence-drawer[open]');
    let drawerText = (await page.locator('#drawer-body').innerText()).toLowerCase();
    for (const phrase of ['published cumulative-amendment movement', '$23,216', 'exact link basis', 'not an invoice/payment history', 'fuzzy vendor or project-name matching']) {
      if (!drawerText.includes(phrase.toLowerCase())) throw new Error(`${viewportName}/trajectory drawer: missing "${phrase}"`);
    }
    await closeDrawer(page);

    const slayterId = await page.evaluate(() => window.b14Observations().find(row => row.report_date === '2023-11-15' && row.po === '2070887247')?.id || null);
    if (!slayterId) throw new Error(`${viewportName}/vendors: Slayter Street control row missing`);
    await page.locator(`tr[data-build014-amendment="${slayterId}"]`).click();
    await page.waitForSelector('#evidence-drawer[open]');
    drawerText = (await page.locator('#drawer-body').innerText()).toLowerCase();
    for (const phrase of ['source arithmetic delta', '-$180', 'source values preserved without correction', 'not an invoice or payment', 'not a final paid value', 'not a complete contract history', 'not a wrongdoing finding']) {
      if (!drawerText.includes(phrase.toLowerCase())) throw new Error(`${viewportName}/observation drawer: missing "${phrase}"`);
    }
    await closeDrawer(page);

    await page.locator('#b14-report-filter').selectOption('2025-11-25');
    await page.waitForFunction(() => document.querySelectorAll('.b14-table tbody tr[data-build014-amendment]').length === 11);
    const novemberText = (await page.locator('.b14-table').innerText()).toLowerCase();
    if (!novemberText.includes('cumulative amendment · updated derived')) throw new Error(`${viewportName}/vendors: Nov. 2025 derived-updated semantic label missing`);
    await page.locator('#b14-report-filter').selectOption('2023-05-17');
    await page.waitForFunction(() => document.querySelectorAll('.b14-table tbody tr[data-build014-amendment]').length === 2);
    const legacyText = (await page.locator('.b14-table').innerText()).toLowerCase();
    if (!legacyText.includes('legacy total-to-date') || !legacyText.includes('derived from source total-to-date')) throw new Error(`${viewportName}/vendors: May 2023 legacy semantic label missing`);
    await page.locator('#b14-reset').click();
    await assertNoOverflow(page, viewportName, 'vendors');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build014-vendors.png`, fullPage: true });

    await openRoute(page, 'signals');
    await page.waitForFunction(() => [...document.querySelectorAll('#investigation-domain option')].some(option => option.value === 'Contract amendments'), null, { timeout: 15000 });
    await page.locator('#investigation-domain').selectOption('Contract amendments');
    const newCards = page.locator('#content [data-build008-investigation-id^="b14-amend-"]');
    if (await newCards.count() < 25) throw new Error(`${viewportName}/investigations: insufficient Build 014 amendment review leads`);
    if (await page.locator('#content [data-build008-investigation-id^="b13-amend-"]').count() !== 0) throw new Error(`${viewportName}/investigations: obsolete Build 013 amendment leads were double-counted`);
    const signalText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['contract amendments', '12 identified public cao amendment reports', 'not a probability of misconduct']) {
      if (!signalText.includes(phrase)) throw new Error(`${viewportName}/investigations: missing "${phrase}"`);
    }
    await newCards.first().click();
    await page.waitForSelector('#evidence-drawer[open]');
    drawerText = (await page.locator('#drawer-body').innerText()).toLowerCase();
    for (const phrase of ['cumulative amendment', 'source-stated reason', 'not necessarily one current change order', 'not a probability of corruption', 'not invoices, ap transactions or final paid values']) {
      if (!drawerText.includes(phrase)) throw new Error(`${viewportName}/investigations drawer: missing "${phrase}"`);
    }
    await closeDrawer(page);
    await assertNoOverflow(page, viewportName, 'signals');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build014-investigations.png`, fullPage: true });

    await openRoute(page, 'sources');
    const sourceText = (await page.locator('#content').innerText()).toLowerCase();
    for (const phrase of ['build 014 cao amendment source series', '12 identified official public hrm amendment-report pdfs', 'not a complete contract-amendment ledger', 'no vendor aliases or fuzzy contract links']) {
      if (!sourceText.includes(phrase)) throw new Error(`${viewportName}/sources: missing "${phrase}"`);
    }
    if (await page.locator('.b14-source-card').count() !== 12) throw new Error(`${viewportName}/sources: expected 12 Build 014 source cards`);
    await assertNoOverflow(page, viewportName, 'sources');
    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build014-sources.png`, fullPage: true });

    report.views.push({ viewport: viewportName, ...facts, renderedInvestigationCards: await newCards.count() });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build014-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
