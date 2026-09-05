const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright-core');

const projectRoot = path.resolve(__dirname, '..');
const generatedSiteDir = path.join(projectRoot, 'deliverables', 'maintainable');
const siteDir = fs.existsSync(path.join(generatedSiteDir, 'index.html'))
  ? generatedSiteDir
  : path.resolve(projectRoot, '..', 'site');
const serveScript = path.join(projectRoot, 'tools', 'anhui_web', 'serve_maintainable.py');
const port = 18767;
const base = `http://127.0.0.1:${port}/index.html?cycle=2026#jobs_search`;

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
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      reducedMotion: 'reduce',
      serviceWorkers: 'block',
    });
    const page = await context.newPage();
    const errors = [];
    const failedRequests = [];
    page.on('console', (message) => message.type() === 'error' && errors.push(`console: ${message.text()}`));
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.stack || error.message}`));
    page.on('requestfailed', (request) => failedRequests.push(`${request.url()} · ${request.failure()?.errorText || 'failed'}`));
    await page.goto(base, { waitUntil: 'networkidle', timeout: 120000 });
    await page.waitForFunction(
      () => window.WanyuMaintainableSite?.state?.view === 'jobs_search' && document.querySelector('[data-ui-search-flow]') && document.querySelector('[data-maint-position-detail]'),
      null,
      { timeout: 120000 },
    );

    const mobileNav = page.locator('[data-maint-mobile-nav]');
    assert(await mobileNav.isVisible(), 'mobile bottom navigation should be visible');
    assert.equal(await page.locator('[data-maint-mobile-nav] > *').count(), 5, 'mobile nav should expose four tasks plus more');
    const navColumns = await mobileNav.evaluate((node) => getComputedStyle(node).gridTemplateColumns.trim().split(/\s+/).length);
    assert.equal(navColumns, 5, 'mobile nav should stay on one row');
    assert((await page.evaluate(() => document.documentElement.scrollWidth)) <= 391, 'mobile horizontal overflow');
    assert.equal(await page.locator('[data-ui-search-flow] .ui-search-flow__step').count(), 3, 'search decision rail should have three steps');

    await page.locator('[data-maint-mobile-more-toggle]').click();
    assert.equal(await page.locator('[data-maint-mobile-more]').evaluate((node) => node.hidden), false, 'more drawer should open');
    assert.equal(await page.locator('.maint-mobile-more__grid a').count(), 6, 'more drawer should expose secondary views');
    await page.locator('[data-maint-mobile-more-close]').click();
    assert.equal(await page.locator('[data-maint-mobile-more]').evaluate((node) => node.hidden), true, 'more drawer should close');

    await page.locator('[data-maint-position-detail]').first().click();
    try {
      await page.waitForSelector('[data-maint-detail-drawer]', { state: 'visible', timeout: 30000 });
    } catch (error) {
      console.error(JSON.stringify({
        status: await page.locator('.maintain-status').innerText().catch(() => ''),
        failedRequests,
        errors,
      }));
      throw error;
    }
    const detailText = await page.locator('[data-maint-detail-drawer]').innerText();
    assert(detailText.includes('岗位原始字段') && detailText.includes('证据与来源'), 'detail drawer should remain source-backed');
    assert(!(await page.locator('.maintain-status').innerText()).includes('加载中'), 'detail open should settle the status indicator');
    await page.locator('[data-maint-detail-close]').click();
    assert((await page.locator('.maintain-status').innerText()).includes('外置模块已加载'), 'closing detail should restore the module status');

    await page.goto(`${base.split('#')[0]}#jobs_map`, { waitUntil: 'networkidle', timeout: 120000 });
    await page.waitForFunction(
      () => window.WanyuMaintainableSite?.state?.view === 'jobs_map'
        && document.querySelector('[data-maint-exam-filter="事业编"]')
        && document.querySelector('[data-maint-map-inspector]'),
      null,
      { timeout: 120000 },
    );
    await page.locator('[data-maint-exam-filter="事业编"]').click();
    const firstHalf = page.locator('[data-maint-exam-sub="上半年"]');
    const secondHalf = page.locator('[data-maint-exam-sub="下半年"]');
    assert.equal(await firstHalf.isDisabled(), false, '上半年联考 should be clickable');
    assert.equal(await secondHalf.isDisabled(), false, '下半年联考 should be clickable');
    await firstHalf.click();
    await page.waitForFunction(
      () => window.WanyuMaintainableSite?.state?.examSub === '上半年'
        && document.querySelector('[data-maint-exam-sub="上半年"]')?.classList.contains('is-active'),
      null,
      { timeout: 30000 },
    );
    assert.equal(await page.locator('[data-maint-map-inspector] .maint-map-facts dd').first().innerText(), '3,521', '上半年岗位数据应被筛出');
    await page.locator('[data-maint-exam-sub="下半年"]').click();
    await page.waitForFunction(
      () => window.WanyuMaintainableSite?.state?.examSub === '下半年'
        && document.querySelector('[data-maint-exam-sub="下半年"]')?.classList.contains('is-active'),
      null,
      { timeout: 30000 },
    );
    assert.equal(await page.locator('[data-maint-map-inspector] .maint-map-facts dd').first().innerText(), '655', '下半年岗位数据应被筛出');
    assert.deepEqual(errors, [], errors.join('\n'));
    console.log('ui upgrade browser smoke: PASS (search rail, mobile nav, more drawer, detail drawer, exam batches)');
  } finally {
    await browser?.close();
    if (!server.killed) server.kill();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});
