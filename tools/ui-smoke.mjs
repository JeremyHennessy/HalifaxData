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
  views: []
};

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
      await page.goto(`${BASE_URL}#${route}`, { waitUntil: 'networkidle' });
      await page.waitForSelector('#content', { state: 'visible' });
      await page.waitForFunction(() => {
        const content = document.querySelector('#content');
        return content && !content.querySelector('.loading-card');
      });

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