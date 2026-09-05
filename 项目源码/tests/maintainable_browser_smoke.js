const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright-core');

const root = path.resolve(__dirname, '..');
const port = 8765;
const baseUrl = `http://127.0.0.1:${port}/index.html`;
// v17.8.6-K：WANYU_SITE_DIR 环境变量最高优先（发布流水线用它把烟测指向 staging）。
const siteDir = (process.env.WANYU_SITE_DIR && fs.existsSync(path.resolve(process.env.WANYU_SITE_DIR)))
  ? path.resolve(process.env.WANYU_SITE_DIR)
  : fs.existsSync(path.resolve(root, '..', '网站'))
    ? path.resolve(root, '..', '网站')
    : path.resolve(root, 'deliverables', 'maintainable');
const artifacts = path.join(root, 'tests', 'artifacts', 'maintainable');

async function waitForServer(url) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`maintenance server did not start: ${url}`);
}

(async () => {
  const server = spawn('python', ['tools/anhui_web/serve_maintainable.py', '--directory', siteDir, '--port', String(port)], {
    cwd: root,
    windowsHide: true,
    stdio: 'ignore',
  });
  let browser;
  try {
    await waitForServer(baseUrl);
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const errors = [];
    const requests = [];
    page.on('console', (message) => message.type() === 'error' && errors.push(`console: ${message.text()}`));
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.stack || error.message}`));
    page.on('request', (request) => requests.push(request.url()));
    // 模块请求带 ?sha=/内容寻址查询串；断言一律按 pathname 判定。
    const requestPathOf = (url) => { try { return new URL(url).pathname; } catch { return url; } };
    // 全量 innerHTML 渲染会让任何点击/等待与重建竞态；抽屉类交互统一走自愈重试。
    const drawerPresent = async () => Boolean(await page.locator('[data-maint-detail-drawer]').count());
    const ensureDetailDrawer = async (openAction, attempts = 4) => {
      for (let attempt = 0; attempt < attempts; attempt += 1) {
        if (await drawerPresent()) return true;
        try { await openAction(); } catch { await page.waitForTimeout(400); }
        try { await page.waitForSelector('[data-maint-detail-drawer]', { timeout: 6000 }); return true; } catch { /* 重建窗口，重试 */ }
      }
      return drawerPresent();
    };
    await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 120000 });
    await page.waitForFunction(() => window.WanyuMaintainableSite?.state?.manifest && window.WanyuMaintainableSite.state.cycle === '2026');
    assert(await page.evaluate(() => Boolean(window.WanyuDataStore)));
    const initialOverviewText = await page.locator('#maintain-main').innerText();
    assert(initialOverviewText.includes('8,401'));
    assert(initialOverviewText.includes('11,883'));
    assert(!initialOverviewText.includes('省直市'), '省直必须保持省直，不应伪造市后缀');
    fs.mkdirSync(artifacts, { recursive: true });
    await page.screenshot({ path: path.join(artifacts, 'overview-desktop.png'), fullPage: true });
    assert.equal(await page.locator('script[src*="maintainable-site.js"]').count(), 1);
    assert.equal(await page.locator('script[src^="//"],script[src^="http://"],script[src^="https://"]').count(), 0);

    await page.locator('[data-maintain-cycle="2025"]').click();
    await page.waitForFunction(() => window.WanyuMaintainableSite.state.cycle === '2025' && document.querySelector('#maintain-main')?.innerText.includes('10,150'));
    assert((await page.locator('#maintain-main').innerText()).includes('14,721'));

    await page.locator('[data-maintain-cycle="2026"]').click();
    await page.waitForFunction(() => window.WanyuMaintainableSite.state.cycle === '2026' && document.querySelector('#maintain-main')?.innerText.includes('8,401'));
    await page.locator('[data-maintain-view="cycle_compare"]').first().click();
    await page.waitForSelector('[data-maint-change-summary]');
    const compareText = await page.locator('#maintain-main').innerText();
    assert(compareText.includes('年度变化') && compareText.includes('口径一致 · 可比'));
    assert((await page.locator('[data-maint-comparison-row]').count()) >= 2);
    await page.screenshot({ path: path.join(artifacts, 'compare-desktop.png'), fullPage: true });

    // The global exam scope must stay consistent across the three-year table,
    // city trend, auxiliary tools, and the core job views.
    await page.locator('[data-maint-exam-filter="事业编"]').click();
    await page.locator('[data-maint-exam-sub="上半年"]').click();
    await page.waitForFunction(() => {
      const site = window.WanyuMaintainableSite;
      return site.state.examFilter === '事业编'
        && site.state.examSub === '上半年'
        && document.querySelector('[data-maint-cycle-summary]')?.innerText.includes('4,819');
    });
    const upperRows = await page.locator('table[data-maint-cycle-summary] tbody tr').evaluateAll((nodes) => nodes.map((row) => [...row.querySelectorAll('th,td')].slice(0, 3).map((cell) => cell.innerText.trim())));
    assert.deepEqual(upperRows, [['2024', '4,819', '6,345'], ['2025', '4,840', '6,028'], ['2026', '3,411', '4,200']]);
    const upperCompareText = await page.locator('#maintain-main').innerText();
    assert(upperCompareText.includes('各城市竞争热度（事业编 · 上半年）'));
    assert(upperCompareText.includes('各城市岗位数对比（事业编 · 上半年）'));
    const upperTrendText = await page.locator('.maint-panel .maint-table').first().innerText();
    assert(upperTrendText.includes('马鞍山市'));
    assert(!upperTrendText.includes('马鞍山含山县'));

    await page.locator('[data-maint-exam-sub="下半年"]').click();
    await page.waitForFunction(() => document.querySelector('[data-maint-cycle-summary]')?.innerText.includes('396'));
    const lowerRows = await page.locator('table[data-maint-cycle-summary] tbody tr').evaluateAll((nodes) => nodes.map((row) => [...row.querySelectorAll('th,td')].slice(0, 3).map((cell) => cell.innerText.trim())));
    assert.deepEqual(lowerRows, [['2024', '396', '566'], ['2025', '651', '928'], ['2026', '655', '742']]);

    await page.locator('[data-maint-exam-filter="全部"]').click();
    await page.waitForFunction(() => window.WanyuMaintainableSite.state.examFilter === '全部'
      && window.WanyuMaintainableSite.state.examSub === ''
      && document.querySelector('[data-maint-cycle-summary]')?.innerText.includes('8,401'));

    await page.locator('[data-maint-exam-filter="事业编"]').click();
    await page.locator('[data-maintain-view="overview"]').first().click();
    await page.waitForFunction(() => window.WanyuMaintainableSite.state.examFilter === '事业编'
      && window.WanyuMaintainableSite.state.examSub === ''
      && document.querySelector('.bento__metric')?.innerText.includes('4,066'));
    assert((await page.locator('.bento__metric').first().innerText()).includes('4,066'));
    await page.locator('[data-maintain-view="jobs_ranking"]').first().click();
    await page.waitForSelector('#maint-ranking-major');
    assert((await page.locator('.maint-toolbar__count').first().innerText()).includes('4,066'));
    await page.locator('[data-maintain-view="jobs_search"]').first().click();
    await page.waitForSelector('#maint-search-major');
    assert((await page.locator('.maint-search-stats__total').innerText()).includes('4,066'));
    await page.locator('[data-maint-exam-filter="全部"]').click();
    await page.waitForFunction(() => window.WanyuMaintainableSite.state.examFilter === '全部'
      && window.WanyuMaintainableSite.state.examSub === ''
      && document.querySelector('.maint-search-stats__total')?.innerText.includes('8,401'));

    await page.locator('[data-maintain-view="jobs_map"]').first().click();
    await page.waitForSelector('[data-maint-map-region]');
    assert.equal(await page.locator('[data-maint-map-region]').count(), 16);
    const mapText = await page.locator('#maintain-main').innerText();
    assert(mapText.includes('岗位地图') && mapText.includes('16 市 + 省直'));
    assert(mapText.includes('省直') && !mapText.includes('省直市'));
    await page.locator('[data-maint-map-metric="recruits"]').click();
    await page.waitForSelector('[data-maint-map-metric="recruits"].is-active');
    const selectedMapCity = await page.locator('[data-maint-map-region]').first().getAttribute('data-maint-map-city');
    assert(selectedMapCity);
    await page.locator('[data-maint-map-region]').first().click();
    await page.waitForSelector('[data-maint-map-inspector]');
    assert((await page.locator('[data-maint-map-inspector]').innerText()).includes('招录人数'));
    assert.equal(await page.locator('[data-maint-map-open-city]').count(), 1);
    await page.screenshot({ path: path.join(artifacts, 'map-desktop.png'), fullPage: true });

    // A new map-to-search intent must not silently inherit stale search text.
    await page.locator('[data-maintain-view="jobs_search"]').first().click();
    await page.waitForSelector('#maint-search-major');
    await page.locator('#maint-search-major').fill('不会存在的岗位关键词');
    await page.waitForFunction(() => window.WanyuMaintainableSite.state.searchMajor === '不会存在的岗位关键词');
    await page.locator('[data-maintain-view="jobs_map"]').first().click();
    await page.waitForSelector('[data-maint-map-open-city]');
    await page.locator('[data-maint-map-open-city]').click();
    await page.waitForSelector('#maint-search-major');
    const mapSearchAfterFreshIntent = await page.locator('#maintain-main').innerText();
    assert(!mapSearchAfterFreshIntent.includes('找到 0 个岗位'), 'map navigation must show the selected city rows');
    assert.equal(await page.locator('#maint-search-major').inputValue(), '');
    assert.equal(await page.locator('[data-maint-clear-city-group]').count(), 1);
    assert.equal(await page.locator('[data-maint-clear-search]').count(), 1);
    await page.locator('[data-maint-clear-city-group]').click();
    assert.equal(await page.locator('[data-maint-clear-city-group]').count(), 0);
    await page.locator('[data-maint-clear-search]').click();
    await page.locator('[data-maintain-view="jobs_ranking"]').first().click();
    await page.waitForSelector('#maint-ranking-major');
    const rankingTotal = await page.locator('[data-maintain-ranking-row]').count();
    for (const selector of ['#maint-ranking-city', '#maint-ranking-exam', '#maint-ranking-category']) {
      assert.equal(await page.locator(selector).count(), 1, `${selector} should exist`);
    }
    const candidates = await page.locator('#maint-ranking-options option').evaluateAll((nodes) => nodes.map((node) => node.value));
    assert(candidates.length > 0, 'major datalist should not be empty');
    assert(candidates.every((value) => /[\u4e00-\u9fffA-Za-z]/.test(value) && !/^[\d\s()[\]{}._（）【】+\-*/、，,;；:.：?？]+$/.test(value)), 'major options must not be code-only labels');
    // 专业过滤的断言改为数据驱动：从 major_city 索引选一个“不满 17 城”的真实专业，
    // 避免前 300 个高频专业恰好覆盖全部城市导致的伪失败。
    const targetedMajor = await page.evaluate(async () => {
      const site = window.WanyuMaintainableSite;
      const lite = await site.state.dataStore.load(site.state.cycle, 'jobs_lite');
      const rows = (lite.allMajors && lite.allMajors.rows) || [];
      const response = await fetch(`/data/cycles/${site.state.cycle}/major_city.json`);
      const index = await response.json();
      for (const label of Object.keys(index.keywords || {})) {
        const cityCount = new Set(
          rows
            .filter((row) => String(row.zy || '').includes(label))
            .map((row) => String(row.city || row.reg || ''))
        ).size;
        if (cityCount > 1 && cityCount < 17) return label;
      }
      return '';
    });
    assert(targetedMajor, 'major_city index should contain a partial-coverage major');
    const fillRankingMajor = async (value) => {
      // 全量 innerHTML 重渲染会瞬时 detach 输入框；带退避重试避免竞态误报。
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          await page.locator('#maint-ranking-major').fill(value, { timeout: 5000 });
          // v17.7 键入保护：输入只记值，blur(focusout+150ms) 才触发重渲染。
          await page.locator('#maint-ranking-major').blur();
          await page.waitForTimeout(300);
          return;
        } catch {
          await page.waitForTimeout(300);
        }
      }
      throw new Error(`fill #maint-ranking-major failed: ${value}`);
    };
    await fillRankingMajor(targetedMajor);
    await page.waitForFunction((value) => window.WanyuMaintainableSite.state.ranking.major === value, targetedMajor);
    await page.waitForTimeout(250);
    const majorCityCount = await page.locator('[data-maintain-ranking-row]').count();
    assert(majorCityCount > 0 && majorCityCount < rankingTotal, 'major filter should reduce the ranking city set');
    assert((await page.locator('.maint-toolbar__count').first().innerText()).includes('专业'));
    const cityValue = await page.locator('#maint-ranking-city option').nth(1).getAttribute('value');
    assert(cityValue, 'ranking city options should be data-backed');
    await page.locator('#maint-ranking-city').selectOption(cityValue);
    const cityCount = await page.locator('[data-maintain-ranking-row]').count();
    assert(cityCount <= majorCityCount, 'city filter should intersect major filter');
    const examValue = await page.locator('#maint-ranking-exam option').nth(1).getAttribute('value');
    assert(examValue, 'ranking exam options should be data-backed');
    await page.locator('#maint-ranking-exam').selectOption(examValue);
    const examCount = await page.locator('[data-maintain-ranking-row]').count();
    assert(examCount <= cityCount, 'exam filter should intersect city filter');
    const categoryValue = await page.locator('#maint-ranking-category option').nth(1).getAttribute('value');
    assert(categoryValue, 'ranking category options should be data-backed');
    await page.locator('#maint-ranking-category').selectOption(categoryValue);
    assert((await page.locator('[data-maintain-ranking-row]').count()) <= examCount, 'category filter should intersect exam filter');
    // 空态行会额外渲染一个重置按钮（工具栏 + 行内），严格模式下取第一个。
    await page.locator('[data-maintain-clear-ranking]').first().click();
    assert.equal(await page.locator('[data-maintain-ranking-row]').count(), rankingTotal);
    await page.screenshot({ path: path.join(artifacts, 'ranking-major-desktop.png'), fullPage: true });

    await page.locator('[data-maintain-view="jobs_search"]').first().click();
    await page.waitForSelector('#maint-search-major');
    assert.equal(await page.locator('#maint-search-major').count(), 1);
    await page.locator('#maint-search-major').fill('软件');
    // 键入保护：blur 才触发重渲染
    await page.locator('#maint-search-major').blur();
    await page.waitForFunction(() => window.WanyuMaintainableSite.state.searchMajor === '软件');
    await page.waitForTimeout(250);
    // T1 三级专业匹配：命中含“按类可报/不限专业”行，表内不保证出现“软件”原文；
    // 断言改为“结果集确实收窄且非空”。
    const searchTotalText = await page.locator('.maint-search-stats__total').innerText();
    assert(/找到\s*[\d,]+\s*个岗位/.test(searchTotalText) && !searchTotalText.includes('8,401'), 'major filter should narrow the search set');
    assert((await page.locator('.maint-table--search tbody tr').count()) > 0, 'narrowed search should render rows');
    await page.waitForSelector('[data-maint-pagination]');
    const nextPage = page.locator('[data-maint-search-page="next"]');
    if (await nextPage.isEnabled()) {
      await nextPage.click();
      assert((await page.locator('[data-maint-pagination]').innerText()).includes('第 2'));
    }
    // “筛选已保存”通知会被随后的懒加载重渲染清掉，改断言持久化效果：快照数 +1。
    const snapshotsBefore = await page.evaluate(() => (JSON.parse(localStorage.getItem('wanyu-maintainable-user-store-v1') || '{}').snapshots || []).length);
    await page.locator('[data-maint-save-filter]').click();
    await page.waitForFunction((before) => (JSON.parse(localStorage.getItem('wanyu-maintainable-user-store-v1') || '{}').snapshots || []).length === before + 1, snapshotsBefore);
    assert(true, 'save filter persists a snapshot');
    await page.waitForSelector('[data-maint-position-detail]');
    assert(await ensureDetailDrawer(() => page.locator('[data-maint-position-detail]').first().click({ timeout: 5000 })), 'detail drawer should open');
    // 抽屉交互前等所有懒加载完成，避免后台渲染重建抽屉造成点击竞态。
    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    const detailText = await page.locator('[data-maint-detail-drawer]').innerText();
    assert(detailText.includes('证据') && detailText.includes('来源'));
    // 详情抽屉会被异步证据加载重建，点击带退避重试避免竞态误报。
    for (let attempt = 0; attempt < 4; attempt += 1) {
      try {
        await page.getByText('查看来源定位', { exact: true }).click({ timeout: 5000 });
        break;
      } catch {
        await page.waitForTimeout(400);
      }
    }
    const expandedDetailText = await page.locator('[data-maint-detail-drawer]').innerText();
    assert(!expandedDetailText.includes('2000-01-01'), 'source date must not use a fake placeholder');
    assert(expandedDetailText.includes('未提供') || /\d{4}-\d{2}-\d{2}/.test(expandedDetailText), 'source date must be explicit or a valid date');
    await page.screenshot({ path: path.join(artifacts, 'detail-desktop.png'), fullPage: true });
    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    for (let attempt = 0; attempt < 4; attempt += 1) {
      try {
        await page.locator('[data-maint-save-position]').click({ timeout: 5000 });
        break;
      } catch {
        await page.waitForTimeout(400);
      }
    }
    const diagAtSave = await page.evaluate(() => JSON.stringify({ detail: (window.WanyuMaintainableSite && window.WanyuMaintainableSite.state && window.WanyuMaintainableSite.state.detail) || null, view: window.WanyuMaintainableSite && window.WanyuMaintainableSite.state && window.WanyuMaintainableSite.state.view }));
    assert(await ensureDetailDrawer(() => page.locator('[data-maint-save-position]').click({ timeout: 5000 }).catch(() => {})), `drawer should stay open after saving; diag=${diagAtSave}; errors=${JSON.stringify(errors.slice(-5))}`);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('[data-maint-detail-drawer]').count(), 0);
    await page.locator('[data-maintain-view="saved"]').first().click();
    await page.waitForSelector('[data-maint-saved-panel]');
    assert((await page.locator('[data-maint-saved-panel]').innerText()).includes('筛选快照'));
    assert((await page.locator('[data-maint-saved-panel]').innerText()).includes('已收藏岗位'));
    assert((await page.locator('[data-maint-saved-position]').count()) >= 1, 'saved positions should be reopenable');
    assert(await ensureDetailDrawer(() => page.locator('[data-maint-saved-position]').first().click({ timeout: 5000 })), 'saved position should reopen the detail drawer');
    await page.keyboard.press('Escape');
    await page.locator('[data-maintain-view="data_boundary"]').first().click();
    await page.waitForSelector('[data-maint-audit-cycle-row]');
    await page.waitForSelector('[data-maint-supplement-evidence]');
    const supplementText = await page.locator('[data-maint-supplement-evidence]').innerText();
    assert(supplementText.includes('补充证据台账') && supplementText.includes('43') && supplementText.includes('正式入库'));
    assert.equal(await page.locator('[data-maint-audit-cycle-row]').count(), 3);
    assert((await page.locator('#maintain-main').innerText()).includes('公开缺口'));
    assert((await page.locator('#maintain-main').innerText()).includes('三年审计'));
    assert((await page.locator('#maintain-main').innerText()).includes('复核队列'));
    // 116 撞码项已迁移 resolved_history（v17.8.5-RC2），open 项 8→7。
    assert((await page.locator('[data-maint-review-item]').count()) >= 7);
    await page.locator('[data-maint-review-filter="high"]').click();
    assert((await page.locator('[data-maint-review-item]').count()) >= 1);
    await page.screenshot({ path: path.join(artifacts, 'audit-center-desktop.png'), fullPage: true });
    await page.locator('[data-maintain-view="help"]').first().click();
    await page.waitForSelector('h1');
    assert((await page.locator('#maintain-main').innerText()).includes('如何判断一个岗位'));
    await page.locator('[data-maintain-view="changelog"]').first().click();
    await page.waitForFunction(() => document.querySelector('#maintain-main')?.innerText.includes('更新日志'));
    assert((await page.locator('#maintain-main').innerText()).includes('更新日志'));
    await page.locator('[data-maintain-view="data_boundary"]').first().click();
    await page.waitForSelector('[data-maint-audit-cycle-row]');

    for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
      await page.setViewportSize(viewport);
      const width = await page.evaluate(() => document.documentElement.scrollWidth);
      assert(width <= viewport.width + 1, `scrollWidth ${width} > ${viewport.width}`);
      if (viewport.width === 390) await page.screenshot({ path: path.join(artifacts, 'boundary-mobile.png'), fullPage: true });
    }
    const remote = await page.evaluate(() => [...document.querySelectorAll('script[src],link[href],img[src]')]
      .map((node) => node.src || node.href).filter((value) => /^https?:/i.test(value) && !value.includes('127.0.0.1')));
    assert.deepEqual(remote, [], 'remote assets found');
    assert.deepEqual(errors, [], errors.join('\n'));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/site-manifest.json')));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/cycles/2026/overview.json')));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/cycles/2026/jobs.json')));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/audit/supplement-20260904.json')));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/cycles/2026/catalog.json')));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/cycles/2026/positions.json')));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/cycles/2025/changes.json')));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/cycles/2026/changes.json')));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/cycles/2025/overview.json')));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/audit/three-year.json')));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/audit/review-queue.json')));
    assert(requests.some((url) => requestPathOf(url).endsWith('/data/map/anhui.json')));
    await context.close();
    console.log('maintainable browser walkthrough: PASS (three cycles, ranking major filter, search, boundary, responsive)');
  } finally {
    await browser?.close();
    server.kill();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});
