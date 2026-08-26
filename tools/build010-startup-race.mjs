import { chromium } from 'playwright';

const BASE_URL = (process.env.HALIFAXDATA_URL || 'http://127.0.0.1:8000/').replace(/\/?$/, '/');
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const pageErrors = [];
const consoleErrors = [];

page.on('pageerror', error => pageErrors.push(error.message));
page.on('console', message => {
  if (message.type() !== 'error') return;
  const text = message.text();
  if (text.startsWith('Failed to load resource: the server responded with a status of 404')) return;
  consoleErrors.push(text);
});

const delayRequired = async route => {
  await new Promise(resolve => setTimeout(resolve, 2500));
  await route.continue();
};

await page.route('**/data/generated/compensation.json', delayRequired);
await page.route('**/data/sources.json', delayRequired);

try {
  await page.goto(`${BASE_URL}#overview`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => {
    const content = document.querySelector('#content');
    return content && !content.querySelector('.loading-card') && /what deserves attention/i.test(content.innerText || '');
  }, null, { timeout: 15000 });

  if (pageErrors.length) {
    throw new Error(`startup race produced page error(s): ${pageErrors.join(' | ')}`);
  }
  if (consoleErrors.length) {
    throw new Error(`startup race produced console error(s): ${consoleErrors.join(' | ')}`);
  }

  const text = (await page.locator('#content').innerText()).toLowerCase();
  if (!text.includes('automated pattern engine')) throw new Error('Build 009 overview did not recover after delayed required data');
  if (!text.includes('capital')) throw new Error('Build 010 Capital investigations did not render after delayed required data');

  console.log(JSON.stringify({
    base_url: BASE_URL,
    required_delay_ms: 2500,
    page_errors: pageErrors,
    console_errors: consoleErrors,
    result: 'startup race guarded successfully'
  }, null, 2));
} finally {
  await context.close();
  await browser.close();
}
