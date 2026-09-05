const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright-core');

const projectRoot = path.resolve(__dirname, '..');
let siteDir = path.resolve(projectRoot, '..', '网站');
if (!fs.existsSync(siteDir)) siteDir = path.resolve(projectRoot, '..', 'site');
const serveScript = path.join(projectRoot, 'tools', 'anhui_web', 'serve_maintainable.py');
const port = 18765;
const base = `http://127.0.0.1:${port}/index.html?cycle=2026&major=${encodeURIComponent('法学类')}`;

async function waitForServer(url) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`HTTP server did not start: ${url}`);
}

(async () => {
  const server = spawn('python', [serveScript, '--directory', siteDir, '--port', String(port)], {
    cwd: projectRoot,
    windowsHide: true,
    stdio: 'ignore',
  });
  let browser;
  try {
    await waitForServer(base);
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
    const errors = [];
    const requests = [];
    page.on('console', (message) => message.type() === 'error' && errors.push(`console: ${message.text()}`));
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.stack || error.message}`));
    page.on('request', (request) => requests.push(request.url()));
    const requestPathOf = (url) => { try { return new URL(url).pathname; } catch { return url; } };
    await page.goto(base, { waitUntil: 'networkidle', timeout: 120000 });
    await page.waitForFunction(
      () => window.WanyuMaintainableSite?.state?.view === 'jobs_map' && document.querySelectorAll('[data-maint-map-region]').length === 16,
      null,
      { timeout: 120000 },
    );
    const fastText = await page.locator('#maintain-main').innerText();
    assert(fastText.includes('专业「法学类」'));
    assert(fastText.includes('1,132'));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/cycles/2026/major_city.json')), 'major_city fast path was not requested');
    assert(!requests.some((url) => requestPathOf(url).endsWith('/data/cycles/2026/jobs_lite.json')), 'jobs_lite should not load for exact major fast path');

    await page.locator('[data-maint-map-clear-major]').click();
    await page.waitForFunction(
      () => !document.querySelector('#maint-map-major')?.value && document.querySelectorAll('[data-maint-map-region]').length === 16,
      null,
      { timeout: 120000 },
    );
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/cycles/2026/jobs_lite.json')), 'jobs_lite fallback was not requested after clearing major');

    await page.setViewportSize({ width: 390, height: 844 });
    assert((await page.evaluate(() => document.documentElement.scrollWidth)) <= 391, 'mobile horizontal overflow');
    assert.deepEqual(errors, [], errors.join('\n'));
    console.log('major_city browser smoke: PASS (fast path, fallback, responsive)');
  } finally {
    await browser?.close();
    if (!server.killed) server.kill();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});
