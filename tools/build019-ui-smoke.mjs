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

function requirePhrases(text, phrases, label) {
  for (const phrase of phrases) {
    if (!text.includes(phrase)) throw new Error(`${label}: missing "${phrase}"`);
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

    await page.goto(`${BASE_URL}#signals`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => {
      const rows = typeof b19InvestigationRows === 'function' ? b19InvestigationRows() : [];
      return Boolean(document.querySelector('.b19-lifecycle-investigations') && rows.length === 29 && document.querySelectorAll('[data-build019-investigation-id]').length === 4);
    }, null, { timeout: 30000 });

    const stats = await page.evaluate(() => ({
      rows: b19InvestigationRows().length,
      investigations: b19InvestigationSummary().investigations,
      priorityReview: b19InvestigationSummary().priority_review,
      review: b19InvestigationSummary().review,
      context: b19InvestigationSummary().context,
      capitalProcurement: b19InvestigationSummary().capital_procurement,
      procurementAmendment: b19InvestigationSummary().procurement_amendment,
      councilLinked: b19InvestigationSummary().council_linked,
      paymentEvidence: b19InvestigationSummary().with_payment_evidence,
      defaultCards: document.querySelectorAll('[data-build019-investigation-id]').length,
      priorityFilter: document.querySelector('#b19-lifecycle-priority')?.value,
      oldCards: document.querySelectorAll('[data-build008-investigation-id]').length,
      oldInvestigationPanels: document.querySelectorAll('.b8-investigation-card').length
    }));

    if (stats.rows !== 29 || stats.investigations !== 29 || stats.defaultCards !== 4 || stats.priorityFilter !== 'attention') {
      throw new Error(`${viewportName}: unexpected Build 019 investigation/default shape ${JSON.stringify(stats)}`);
    }
    if (stats.priorityReview !== 2 || stats.review !== 2 || stats.context !== 25) {
      throw new Error(`${viewportName}: Build 019 review-state controls changed ${JSON.stringify(stats)}`);
    }
    if (stats.capitalProcurement !== 21 || stats.procurementAmendment !== 8 || stats.councilLinked !== 3 || stats.paymentEvidence !== 0) {
      throw new Error(`${viewportName}: Build 019 lifecycle controls changed ${JSON.stringify(stats)}`);
    }
    if (stats.oldCards < 1 || stats.oldInvestigationPanels <= stats.defaultCards) {
      throw new Error(`${viewportName}: preserved Build 008 investigation surface is missing ${JSON.stringify(stats)}`);
    }

    const panelText = (await page.locator('.b19-lifecycle-investigations').innerText()).toLowerCase();
    requirePhrases(panelText, [
      'deterministic lifecycle investigations',
      'review priority ≠ misconduct risk',
      'capital ↔ procurement',
      'procurement ↔ amendment',
      'payment evidence',
      'transaction analyses remain disabled',
      'priority + review',
      'all 29 targets',
      '4 of 29 targets',
      'not misconduct probability'
    ], `${viewportName} Build 019 panel`);

    const firstCard = page.locator('[data-build019-investigation-id]').first();
    if (await firstCard.count() !== 1) throw new Error(`${viewportName}: no Build 019 lifecycle card rendered`);
    await firstCard.click();
    await page.waitForSelector('#evidence-drawer[open]');
    const drawerText = `${await page.locator('#drawer-eyebrow').innerText()}\n${await page.locator('#drawer-title').innerText()}\n${await page.locator('#drawer-body').innerText()}`.toLowerCase();
    requirePhrases(drawerText, [
      'deterministic lifecycle review',
      'review priority score',
      'why this is in the queue',
      'observed linked facts',
      'interpretation boundary',
      'not a probability',
      'no build 019 lifecycle item currently establishes vendor payment',
      'source evidence'
    ], `${viewportName} Build 019 drawer`);
    await page.locator('#drawer-close').click();

    // Full lifecycle families remain inspectable when the user explicitly expands to all targets.
    await page.selectOption('#b19-lifecycle-priority', 'all');
    await page.waitForFunction(() => document.querySelectorAll('[data-build019-investigation-id]').length === 29);

    await page.selectOption('#b19-lifecycle-track', 'capital_procurement');
    await page.waitForFunction(() => document.querySelectorAll('[data-build019-investigation-id]').length === 21);
    let filtered = await page.locator('[data-build019-investigation-id]').count();
    if (filtered !== 21) throw new Error(`${viewportName}: expected 21 capital/procurement lifecycle cards, got ${filtered}`);

    await page.selectOption('#b19-lifecycle-track', 'procurement_amendment');
    await page.waitForFunction(() => document.querySelectorAll('[data-build019-investigation-id]').length === 8);
    filtered = await page.locator('[data-build019-investigation-id]').count();
    if (filtered !== 8) throw new Error(`${viewportName}: expected 8 procurement/amendment lifecycle cards, got ${filtered}`);

    // Reset track before independently verifying review-priority counts.
    await page.selectOption('#b19-lifecycle-track', 'all');
    await page.selectOption('#b19-lifecycle-priority', 'priority_review');
    await page.waitForFunction(() => document.querySelectorAll('[data-build019-investigation-id]').length === 2);
    filtered = await page.locator('[data-build019-investigation-id]').count();
    if (filtered !== 2) throw new Error(`${viewportName}: expected 2 priority-review lifecycle cards, got ${filtered}`);

    // Restore the compact production default for visual evidence.
    await page.selectOption('#b19-lifecycle-priority', 'attention');
    await page.waitForFunction(() => document.querySelectorAll('[data-build019-investigation-id]').length === 4);

    const dims = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth
    }));
    if (dims.scrollWidth > dims.clientWidth + 2) {
      throw new Error(`${viewportName}: Build 019 investigations caused horizontal overflow ${JSON.stringify(dims)}`);
    }

    await page.screenshot({ path: `${OUTPUT}/${viewportName}-build019-investigations.png`, fullPage: true });
    report.views.push({ viewport: viewportName, stats, dimensions: dims });
    await context.close();
  }
} finally {
  await browser.close();
}

await fs.writeFile(`${OUTPUT}/build019-report.json`, JSON.stringify(report, null, 2));
if (report.errors.length) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
