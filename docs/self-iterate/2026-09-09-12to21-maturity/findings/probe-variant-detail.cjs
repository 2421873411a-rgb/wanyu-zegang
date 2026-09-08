// P1-003 判定性探针：地图检查器"岗位行"在 事业编→上半年 切片下的稳定值到底是 raw(3,521) 还是 active(3,411)。
// 运行：node docs/self-iterate/2026-09-09-12to21-maturity/findings/probe-map-facts.cjs
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const { chromium } = require('E:/zcode/择岗/项目源码/node_modules/playwright-core');

const projectRoot = path.resolve('E:/zcode/择岗/项目源码');
const siteDir = path.resolve('E:/zcode/择岗/网站');
const port = 8799;
const base = `http://127.0.0.1:${port}/index.html`;
const serveScript = path.join(projectRoot, 'tools', 'anhui_web', 'serve_maintainable.py');

(async () => {
  const server = spawn('python', [serveScript, '--directory', siteDir, '--port', String(port)], { cwd: projectRoot, windowsHide: true, stdio: 'ignore' });
  let browser;
  try {
    for (let i = 0; i < 80; i++) { try { const r = await fetch(base); if (r.ok) break; } catch {} await new Promise(r => setTimeout(r, 250)); }
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce', serviceWorkers: 'block' });
    const page = await context.newPage();
    await page.goto(`${base}?cycle=2026#jobs_search`, { waitUntil: 'networkidle', timeout: 120000 });
    await page.waitForFunction(() => window.WanyuMaintainableSite?.state?.view === 'jobs_search' && document.querySelector('[data-maint-position-detail]'), null, { timeout: 120000 });
    await page.locator('[data-maint-position-detail]').first().click();
    await page.waitForSelector('[data-maint-detail-drawer]', { state: 'visible', timeout: 30000 });
    await page.locator('[data-maint-detail-close]').click();
    await page.waitForTimeout(800);
    await page.goto(`http://127.0.0.1:${port}/index.html?cycle=2026#jobs_map`, { waitUntil: 'networkidle', timeout: 120000 });
    await page.waitForFunction(() => window.WanyuMaintainableSite?.state?.view === 'jobs_map' && document.querySelector('[data-maint-exam-filter="事业编"]'), null, { timeout: 120000 });
    await page.locator('[data-maint-exam-filter="事业编"]').click();
    await page.waitForTimeout(1500);
    await page.locator('[data-maint-exam-sub="上半年"]').click();
    // 每 500ms 采样 dd 值，共 8 秒，观察是否有两段式渲染
    const samples = [];
    for (let i = 0; i < 16; i++) {
      const txt = await page.locator('[data-maint-map-inspector] .maint-map-facts dd').first().innerText();
      samples.push(txt.trim());
      await page.waitForTimeout(500);
    }
    const uniq = [...new Set(samples)];
    console.log(JSON.stringify({ samples_uniq: uniq, timeline: samples }, null, 1));
    const state = await page.evaluate(() => ({
      exam: window.WanyuMaintainableSite?.state?.exam,
      examSub: window.WanyuMaintainableSite?.state?.examSub,
      ready: window.WanyuMaintainableSite?.state?.ready ?? window.WanyuMaintainableSite?.state?.dataReady ?? null,
    }));
    console.log('state:', JSON.stringify(state));
  } finally {
    await browser?.close();
    if (server && !server.killed) server.kill();
  }
})();
