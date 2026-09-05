const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { chromium } = require('playwright-core');

const root = path.resolve(__dirname, '..');
const master = path.join(root, 'deliverables', '皖域择岗总览.html');
const artifacts = path.join(root, 'tests', 'artifacts', 'v12');
const filterIndex = process.argv.indexOf('--grep');
const filter = filterIndex >= 0 ? String(process.argv[filterIndex + 1] || '').toLowerCase() : '';

const expected = {
  '2024': { posts: '10,017', recruits: '15,331' },
  '2025': { posts: '10,150', recruits: '14,721' },
  '2026': { posts: '8,511', recruits: '12,006' },
};

function selected(name) { return !filter || name.toLowerCase().includes(filter); }
function localUrl(query = '', hash = '') { return `${pathToFileURL(master).href}${query}${hash}`; }

async function openPage(browser, query = '', hash = '', viewport = { width: 1440, height: 900 }, initScript = null) {
  const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
  if (initScript) await context.addInitScript(initScript);
  const page = await context.newPage();
  const errors = [];
  page.on('console', (message) => message.type() === 'error' && errors.push(`console: ${message.text()}`));
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.stack || error.message}`));
  await page.goto(localUrl(query, hash), { waitUntil: 'load', timeout: 120000 });
  await page.waitForFunction(() => Boolean(window.WanyuCycleStore && document.querySelector('[data-cycle-posts]')));
  await page.waitForTimeout(250);
  const onboardingClose = page.locator('.wanyu-overlay .wanyu-dialog__close');
  if (await onboardingClose.count()) await onboardingClose.first().click();
  return { context, page, errors };
}

async function checkNoRemoteAssets(page) {
  const remote = await page.evaluate(() => [...document.querySelectorAll('script[src],link[href],img[src]')]
    .map((node) => node.src || node.href)
    .filter((value) => /^https?:/i.test(value)));
  assert.deepEqual(remote, [], 'remote assets found');
}

async function runCase(name, fn) {
  if (!selected(name)) return false;
  await fn();
  console.log(`PASS ${name}`);
  return true;
}

(async () => {
  assert(fs.existsSync(master), `missing ${master}; run build_pages.py first`);
  fs.mkdirSync(artifacts, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  let passed = 0;
  try {
    if (await runCase('cycle store lists and activates all cycles', async () => {
      const { page, context, errors } = await openPage(browser, '', '#cycle_compare');
      assert.deepEqual(await page.evaluate(() => window.WanyuCycleStore.listCycles()), ['2024', '2025', '2026']);
      assert.equal(await page.locator('[data-cycle-tab]').count(), 3);
      assert.equal(await page.locator('[data-cycle-tab][aria-selected="true"]').getAttribute('data-cycle-tab'), '2026');
      assert.equal(await page.locator('[data-active-cycle="2026"]').count() >= 1, true);
      assert((await page.locator('#jobs-search-table tbody tr').count()) <= 240, 'search table should render a bounded first page');
      assert((await page.locator('body').innerText()).includes('116'));
      assert.equal(await page.locator('[data-cycle-payload]').count(), 3);
      await checkNoRemoteAssets(page);
      assert.deepEqual(errors, [], errors.join('\n'));
      await page.screenshot({ path: path.join(artifacts, 'cycle-compare-desktop.png'), fullPage: true });
      await context.close();
    })) passed += 1;

    if (await runCase('url restores 2024 search context', async () => {
      const { page, context, errors } = await openPage(browser, '?cycle=2024', '#jobs_search');
      assert.equal(await page.locator('[data-cycle-tab][aria-selected="true"]').getAttribute('data-cycle-tab'), '2024');
      assert.equal(await page.locator('[data-cycle-posts]').textContent(), expected['2024'].posts);
      assert.equal(await page.locator('.unified-view[data-view="jobs_search"].is-active').count(), 1);
      assert.equal(await page.locator('#jobs-search-table').count(), 1);
      assert((await page.locator('body').innerText()).includes(expected['2024'].recruits));
      assert.deepEqual(errors, [], errors.join('\n'));
      await page.screenshot({ path: path.join(artifacts, 'cycle-2024-search.png'), fullPage: true });
      await context.close();
    })) passed += 1;

    if (await runCase('url restores 2025 all jobs context', async () => {
      const { page, context, errors } = await openPage(browser, '?cycle=2025', '#jobs_all');
      assert.equal(await page.locator('[data-cycle-posts]').textContent(), expected['2025'].posts);
      assert.equal(await page.locator('.unified-view[data-view="jobs_all"].is-active').count(), 1);
      assert((await page.locator('body').innerText()).includes(expected['2025'].recruits));
      assert.deepEqual(errors, [], errors.join('\n'));
      await page.screenshot({ path: path.join(artifacts, 'cycle-2025-all.png'), fullPage: true });
      await context.close();
    })) passed += 1;

    if (await runCase('岗位榜单支持专业筛选并可恢复全量', async () => {
      const { page, context, errors } = await openPage(browser, '?cycle=2026', '#jobs_ranking');
      await page.waitForSelector('#ranking-major-input');
      const total = await page.locator('[data-ranking-row]').count();
      assert(total > 0, 'ranking table should have city rows');
      const candidates = await page.locator('#ranking-major-options option').evaluateAll((nodes) => nodes.map((node) => node.value));
      assert(candidates.length > 0, 'major datalist should expose selectable values');
      assert(candidates.every((value) => /[\u4e00-\u9fffA-Za-z]/.test(value) && !/^[\d\s()[\]{}._（）【】+\-*/、，,;；:.：?？]+$/.test(value)), 'major options must not be code-only labels');
      const candidate = candidates[0];
      assert(candidate, 'major datalist should expose a selectable value');
      await page.locator('#ranking-major-input').fill(candidate);
      await page.waitForFunction((value) => {
        const visible = [...document.querySelectorAll('[data-ranking-row]:not([hidden])')];
        return visible.length > 0 && visible.length < 16
          && visible.every((row) => String(row.dataset.rankingMajor || '').includes(value));
      }, candidate, { timeout: 30000 });
      const filtered = await page.locator('[data-ranking-row]:not([hidden])').count();
      assert(filtered < total, `major filter should reduce rows: ${filtered} vs ${total}`);
      assert((await page.locator('#ranking-filter-count').textContent()).includes(`${filtered}`));
      await page.locator('#ranking-major-clear').click();
      await page.waitForFunction((expectedTotal) =>
        document.querySelectorAll('[data-ranking-row]:not([hidden])').length === expectedTotal, total);
      assert.equal(await page.locator('[data-ranking-row]:not([hidden])').count(), total);
      assert.deepEqual(errors, [], errors.join('\n'));
      await context.close();
    })) passed += 1;

    if (await runCase('综合专业控件不展示纯代码候选', async () => {
      const { page, context, errors } = await openPage(browser, '?cycle=2026', '#jobs_all');
      const codeOnly = /^[\d\s()[\]{}._（）【】+\-*/、，,;；:.：?？]+$/;
      await page.locator('#wyall-p-major').focus();
      await page.waitForSelector('#wyall-major-list button');
      const comboValues = await page.locator('#wyall-major-list button').evaluateAll((nodes) => nodes.map((node) => node.textContent.trim()));
      const mapValues = await page.locator('#wyall-map-major-list option').evaluateAll((nodes) => nodes.map((node) => node.value));
      assert(comboValues.length > 0, 'major combo should expose selectable values');
      assert(mapValues.length > 0, 'map major datalist should expose selectable values');
      assert(comboValues.every((value) => /[\u4e00-\u9fffA-Za-z]/.test(value) && !codeOnly.test(value)), 'profile major candidates must not be code-only labels');
      assert(mapValues.every((value) => /[\u4e00-\u9fffA-Za-z]/.test(value) && !codeOnly.test(value)), 'map major candidates must not be code-only labels');
      assert.deepEqual(errors, [], errors.join('\n'));
      await context.close();
    })) passed += 1;

    if (await runCase('岗位检索覆盖三个周期全量岗位', async () => {
      for (const cycle of ['2024', '2025', '2026']) {
        const { page, context, errors } = await openPage(browser, `?cycle=${cycle}`, '#jobs_search');
        const total = Number(expected[cycle].posts.replaceAll(',', ''));
        await page.waitForFunction((expectedTotal) => window.__wanyuV12Search?.total === expectedTotal
          && document.querySelectorAll('#jobs-search-table tbody tr').length > 0
          && document.querySelectorAll('#jobs-search-table tbody tr').length <= 120, total, { timeout: 120000 });
        assert.equal(await page.locator('#search-count').textContent(), expected[cycle].posts);
        assert.equal(await page.locator('#v12-search-pager').count(), 1);
        assert.deepEqual(errors, [], errors.join('\n'));
        await context.close();
      }
    })) passed += 1;

    if (await runCase('迁移旧版收藏与备注到周期键', async () => {
      const initScript = () => {
        localStorage.setItem('wanyu.jobSaved.v1', JSON.stringify(['001', '002']));
        localStorage.setItem('wanyu.jobCompare.v1', JSON.stringify(['002']));
        localStorage.setItem('wanyu.jobNotes.v1', JSON.stringify({ '001': '重点关注' }));
      };
      const { page, context, errors } = await openPage(browser, '', '#overview', { width: 1440, height: 900 }, initScript);
      await page.waitForFunction(() => {
        const saved = JSON.parse(localStorage.getItem('wanyu.jobSaved.v2') || '[]');
        const compare = JSON.parse(localStorage.getItem('wanyu.jobCompare.v2') || '[]');
        return saved.includes('2026:001') && saved.includes('2026:002') && compare.includes('2026:002');
      }, { timeout: 120000 });
      assert.deepEqual(JSON.parse(await page.evaluate(() => localStorage.getItem('wanyu.jobSaved.v1'))), ['001', '002']);
      const first = await page.evaluate(() => JSON.parse(localStorage.getItem('wanyu.jobSaved.v2') || '[]'));
      assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('wanyu.jobNotes.v2') || '{}')['2026:001']), '重点关注');
      await page.reload({ waitUntil: 'load', timeout: 120000 });
      const second = await page.evaluate(() => JSON.parse(localStorage.getItem('wanyu.jobSaved.v2') || '[]'));
      assert.deepEqual(second, first);
      assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('wanyu.jobMigration.v12') || '{}').completed), true);
      assert.deepEqual(errors, [], errors.join('\n'));
      await context.close();
    })) passed += 1;

    if (await runCase('检索详情分页收藏与对比闭环', async () => {
      const { page, context, errors } = await openPage(browser, '?cycle=2026', '#jobs_search');
      const firstId = await page.locator('#jobs-search-table tbody tr').first().getAttribute('data-job-id');
      assert(firstId);
      await page.locator('#jobs-search-table tbody tr').first().locator('[data-job-detail]').click();
      await page.waitForSelector('.wanyu-overlay .wanyu-dialog', { timeout: 30000 });
      assert((await page.locator('.wanyu-overlay .wanyu-dialog').innerText()).includes('核心数据'));
      await page.locator('.wanyu-overlay .wanyu-dialog__close').click();
      await page.locator('#jobs-search-table tbody tr').first().locator('[data-job-save]').click();
      await page.locator('#jobs-search-table tbody tr').first().locator('[data-job-compare]').click();
      await page.waitForFunction((id) => JSON.parse(localStorage.getItem('wanyu.jobSaved.v2') || '[]').some((value) => value.endsWith(':' + id)), firstId, { timeout: 30000 });
      assert.equal(await page.locator('#search-compare-count').textContent(), '1 / 6');
      await page.locator('#v12-search-pager button[data-v12-page="2"]').click();
      await page.waitForFunction((id) => document.querySelector('#jobs-search-table tbody tr')?.dataset.jobId !== id, firstId, { timeout: 30000 });
      await page.locator('#open-job-compare').click();
      await page.waitForFunction(() => document.body.dataset.activeView === 'jobs_compare');
      assert.equal(await page.locator('[data-compare-card]').count(), 1);
      assert.deepEqual(errors, [], errors.join('\n'));
      await context.close();
    })) passed += 1;

    if (await runCase('cycle tab click updates same file and preserves view', async () => {
      const { page, context, errors } = await openPage(browser, '', '#jobs_all');
      await page.locator('[data-cycle-tab="2024"]').click();
      await page.waitForFunction(() => window.WanyuCycleStore?.getCycle?.() === '2024'
        && document.querySelector('[data-cycle-tab][aria-selected="true"]')?.dataset.cycleTab === '2024',
      { timeout: 120000 });
      assert.match(page.url(), /cycle=2024#jobs_all$/);
      assert.equal(await page.locator('[data-cycle-tab][aria-selected="true"]').getAttribute('data-cycle-tab'), '2024');
      assert.equal(await page.locator('[data-cycle-posts]').textContent(), expected['2024'].posts);
      assert.equal(await page.locator('.unified-view[data-view="jobs_all"].is-active').count(), 1);
      assert.deepEqual(errors, [], errors.join('\n'));
      await context.close();
    })) passed += 1;

    if (await runCase('history restore and keyboard cycle', async () => {
      const { page, context, errors } = await openPage(browser, '?cycle=2024', '#overview');
      await page.locator('[data-cycle-tab="2026"]').click();
      await page.waitForFunction(() => window.WanyuCycleStore?.getCycle?.() === '2026'
        && document.querySelector('[data-cycle-tab][aria-selected="true"]')?.dataset.cycleTab === '2026',
      { timeout: 120000 });
      await page.goBack({ waitUntil: 'load' });
      await page.waitForFunction(() => window.WanyuCycleStore?.getCycle?.() === '2024'
        && document.querySelector('[data-cycle-tab][aria-selected="true"]')?.dataset.cycleTab === '2024',
      { timeout: 120000 });
      await page.locator('[data-cycle-tab="2024"]').focus();
      await page.keyboard.press('ArrowRight');
      await page.waitForFunction(() => window.WanyuCycleStore?.getCycle?.() === '2025'
        && document.querySelector('[data-cycle-tab][aria-selected="true"]')?.dataset.cycleTab === '2025',
      { timeout: 120000 });
      assert.equal(await page.locator('[data-cycle-tab][aria-selected="true"]').getAttribute('data-cycle-tab'), '2025');
      await page.locator('[data-cycle-tab="2024"]').focus();
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => window.WanyuCycleStore?.getCycle?.() === '2024'
        && document.querySelector('[data-cycle-tab][aria-selected="true"]')?.dataset.cycleTab === '2024',
      { timeout: 120000 });
      assert.deepEqual(errors, [], errors.join('\n'));
      await context.close();
    })) passed += 1;

    for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
      const name = `responsive no overflow ${viewport.width}`;
      if (await runCase(name, async () => {
        const { page, context, errors } = await openPage(browser, '?cycle=2026', '#overview', viewport);
        const width = await page.evaluate(() => document.documentElement.scrollWidth);
        assert(width <= viewport.width + 1, `scrollWidth ${width} > ${viewport.width}`);
        await checkNoRemoteAssets(page);
        assert.deepEqual(errors, [], errors.join('\n'));
        await page.screenshot({ path: path.join(artifacts, `responsive-${viewport.width}.png`), fullPage: true });
        await context.close();
      })) passed += 1;
    }
  } finally {
    await browser.close();
  }
  console.log(`v12 browser walkthrough: PASS (${passed} cases)`);
})().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});
