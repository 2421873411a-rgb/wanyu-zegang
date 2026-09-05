# 安徽岗位机会观测台重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以 `皖域择岗档案_网页重构版_20260828.zip` 为基线，把岗位页升级为与新版全包页同等级的真实地图观测台，并加入城市排名、三城比较、岗位收藏对比、CSV 导出和双页城市联动。

**Architecture:** 保留 Python 构建器生成单文件离线 HTML 的架构，在构建阶段把 Word 表格转换为规范化岗位记录和城市聚合数据，并将安徽 16 市边界、数据和组件模板内联进页面。运行时由岗位页 JavaScript 维护单一页面状态，统一驱动地图、检查器、排名、三城对比、检索结果和收藏对比篮；全包页只增加对称的城市深链入口。

**Tech Stack:** Python 3.12、python-docx 1.2.0、lxml 6.1.1、原生 HTML/CSS/SVG/JavaScript、Playwright 1.62.1、Python `unittest`。

## Global Constraints

- 实施基线固定为 `C:\Users\24218\Desktop\皖域择岗档案_网页重构版_20260828.zip`，不得覆盖原 ZIP。
- 最终成品仍为两个可双击打开的单文件离线 HTML，不加载 CDN、网络字体或远程脚本。
- 岗位页必须保留源 Word 的全部段落、106 张表格及全部非空单元格；全包页 31 张表不得回归。
- 不生成岗位推荐、录取概率、竞争等级、城市综合评分或待遇与岗位的综合结论。
- 真实地图继续使用 `tools/anhui_web/data/anhui_340000_full.json`，概念渲染图只作为布局和视觉参考。
- 缺失字段显示 `—` 或“该来源无此字段”，不得按零值参与计算。
- 所有动效遵守 `prefers-reduced-motion`；关闭 JavaScript 后源正文仍完整可读。
- 当前目录不是 Git 仓库，因此实施期间使用测试通过与文件快照作为检查点，不执行虚构的 Git 提交。

---

### Task 1: 建立新版独立工作副本和基线验收

**Files:**
- Create: `anhui_site_work_20260828/`
- Copy: `C:/Users/24218/Downloads/ChatGPT Image 2026年8月28日 08_53_15 (1).png` → `anhui_site_work_20260828/design_refs/jobs-workbench-desktop.png`
- Copy: `C:/Users/24218/Downloads/ChatGPT Image 2026年8月28日 08_53_15 (2).png` → `anhui_site_work_20260828/design_refs/jobs-ranking-compare.png`
- Copy: `C:/Users/24218/Downloads/ChatGPT Image 2026年8月28日 08_56_03 (1).png` → `anhui_site_work_20260828/design_refs/jobs-search-compare.png`
- Copy: `C:/Users/24218/Downloads/ChatGPT Image 2026年8月28日 08_56_03 (2).png` → `anhui_site_work_20260828/design_refs/jobs-mobile.png`
- Copy: `C:/Users/24218/Downloads/ChatGPT Image 2026年8月28日 08_56_04 (3).png` → `anhui_site_work_20260828/design_refs/jobs-motion-board.png`
- Test: `anhui_site_work_20260828/tests/test_anhui_web.py`

**Interfaces:**
- Consumes: 新版 ZIP 的 `anhui_site_work_20260827/` 根目录。
- Produces: 不覆盖源 ZIP 的可执行工作目录 `anhui_site_work_20260828/`。

- [ ] **Step 1: 解压到独立目录并保存五张视觉参考图**

使用 PowerShell `Expand-Archive` 解压，再把五张 PNG 复制到 `design_refs/`；若目标已存在则停止，避免覆盖未知工作。

- [ ] **Step 2: 运行 Python 基线测试**

Run:

```powershell
python -m unittest tests.test_anhui_web -v
```

Expected: 现有 7 项测试全部通过。

- [ ] **Step 3: 运行现有浏览器基线测试**

Run:

```powershell
node tests/browser_smoke.js
```

Expected: 桌面和移动视口无控制台错误、无页面级横向溢出，岗位页 106 张表、全包页 31 张表。

- [ ] **Step 4: 记录基线检查点**

在 `design-qa-jobs.md` 记录测试命令、结果和五张参考图的用途。

---

### Task 2: 规范化岗位记录与城市聚合指标

**Files:**
- Modify: `anhui_site_work_20260828/tools/anhui_web/build_pages.py`
- Modify: `anhui_site_work_20260828/tests/test_anhui_web.py`

**Interfaces:**
- Consumes: `DocumentModel`、`_city_ranges(model)` 和 106 张岗位表。
- Produces: `extract_job_records(model) -> list[dict[str, object]]`、`build_job_metrics(records, summaries) -> dict[str, object]`、稳定字段 `record_id/city/exam/code/unit_position/recruits/source_table/source_row/raw_cells`。

- [ ] **Step 1: 写岗位记录和聚合数据失败测试**

```python
records = extract_job_records(parse_docx(JOBS_DOCX))
metrics = build_job_metrics(records, _jobs_city_summaries(parse_docx(JOBS_DOCX)))
self.assertEqual(len(records), 544)
self.assertEqual(sum(int(row["recruits"]) for row in records), 825)
self.assertEqual(metrics["totals"]["jobs"], 544)
self.assertEqual(metrics["totals"]["recruits"], 825)
self.assertEqual(set(metrics["cities"]), set(CITY_POSITIONS))
self.assertEqual(len({row["record_id"] for row in records}), 544)
```

- [ ] **Step 2: 运行测试确认缺少接口**

Run:

```powershell
python -m unittest tests.test_anhui_web.JobAnalyticsTests -v
```

Expected: FAIL，提示 `extract_job_records` 或 `build_job_metrics` 尚未定义。

- [ ] **Step 3: 实现记录抽取和口径安全聚合**

实现时逐表读取真实表头，通过同义表头映射识别 `代码`、`单位 · 职位`、`招录`；原始单元格完整保存在 `raw_cells`。`recruitsPerJob` 使用：

```python
recruits_per_job = round(city_recruits / city_jobs, 2) if city_jobs else None
```

考试类别构成同时保留岗位数和招录人数，所有聚合总数必须与源文档总览交叉验证，不一致时抛出 `ValueError`。

- [ ] **Step 4: 运行岗位数据测试**

Run: `python -m unittest tests.test_anhui_web.JobAnalyticsTests -v`  
Expected: PASS。

- [ ] **Step 5: 运行完整 Python 测试作为检查点**

Run: `python -m unittest tests.test_anhui_web -v`  
Expected: 全部通过，源内容完整性无回归。

---

### Task 3: 构建真实地图三栏岗位观测台

**Files:**
- Modify: `anhui_site_work_20260828/tools/anhui_web/build_pages.py`
- Rewrite: `anhui_site_work_20260828/tools/anhui_web/templates/jobs.css`
- Modify: `anhui_site_work_20260828/tools/anhui_web/templates/jobs.html`
- Modify: `anhui_site_work_20260828/tests/test_anhui_web.py`

**Interfaces:**
- Consumes: `build_job_metrics()`、`_load_anhui_boundaries()` 和全包页已经验证的 SVG 边界变换逻辑。
- Produces: `#jobs-workbench`、`#jobs-map`、`#jobs-inspector`、`#job-metric`、`[data-job-region]`、`[data-map-city]`。

- [ ] **Step 1: 写工作台结构失败测试**

```python
for marker in ('id="jobs-workbench"', 'id="jobs-map"', 'id="jobs-inspector"', 'id="job-metric"'):
    self.assertIn(marker, jobs_html)
self.assertEqual(jobs_html.count('data-job-region="'), 16)
self.assertIn('机会镜头', jobs_html)
```

- [ ] **Step 2: 运行测试确认旧岗位页不满足新结构**

Run: `python -m unittest tests.test_anhui_web.GeneratedPageTests.test_jobs_observatory_structure -v`  
Expected: FAIL，缺少新工作台标记。

- [ ] **Step 3: 复用真实边界生成岗位地图**

新增 `_jobs_boundary_map_svg(boundaries, metrics)`，为每个城市区域输出：

```html
<path class="jobs-map__region" data-job-region="合肥" tabindex="0">
  <title>合肥：40岗，64人</title>
</path>
```

SVG 只内联真实边界与源数据，城市标签独立放置并允许移动端隐藏非选中项。

- [ ] **Step 4: 重建首屏和三栏工作台 HTML**

左栏放置三指标分段控件和考试类别；中央放置真实地图、图例和状态说明；右栏放置城市检查器及考试类别构成条；底部放置 16 市导航。默认城市使用合肥，默认指标使用岗位数。

- [ ] **Step 5: 按参考图实现岗位专属浅色视觉系统**

使用规格中的六个颜色令牌；选中区域使用双层“机会镜头”描边。桌面三栏比例约为 `220px minmax(520px, 1fr) 260px`，移动端重排为控件、检查器、地图、城市导航。

- [ ] **Step 6: 运行结构和全文保真测试**

Run:

```powershell
python -m unittest tests.test_anhui_web.GeneratedPageTests.test_jobs_observatory_structure -v
python -m unittest tests.test_anhui_web.GeneratedPageTests.test_every_source_paragraph_and_table_cell_is_visible -v
```

Expected: 两项通过。

---

### Task 4: 统一地图、检查器和动态排名状态

**Files:**
- Rewrite: `anhui_site_work_20260828/tools/anhui_web/templates/jobs.js`
- Modify: `anhui_site_work_20260828/tools/anhui_web/build_pages.py`
- Modify: `anhui_site_work_20260828/tests/browser_smoke.js`

**Interfaces:**
- Consumes: `page-data.jobMetrics`、`page-data.jobRecords` 和 Task 3 的 DOM 标记。
- Produces: 单一状态 `metric/city/previewCity/exam`，以及 `renderJobView(metric, city)`、`selectJobCity(city, options)`、`reorderJobRanking(metric)`。

- [ ] **Step 1: 写浏览器失败测试**

```javascript
await page.locator('[data-job-metric="recruits"]').click();
assert.strictEqual(await page.locator('#jobs-view-label').innerText(), '招录人数');
await page.locator('[data-map-city="芜湖"]').click();
assert.strictEqual(await page.locator('#jobs-inspector-city').innerText(), '芜湖');
assert.strictEqual(await page.locator('[data-job-region="芜湖"]').getAttribute('aria-pressed'), 'true');
```

- [ ] **Step 2: 运行浏览器测试确认交互尚未实现**

Run: `node tests/browser_smoke.js`  
Expected: FAIL，缺少指标或城市同步状态。

- [ ] **Step 3: 实现单一状态与派生指标**

所有地图填色、图例范围、检查器数字和排名数据从同一个 `currentEntries()` 产生。`previewCity` 只临时更新检查器，离开后恢复锁定城市。

- [ ] **Step 4: 实现数字和地图过渡**

数字过渡固定 420ms，地图填色固定 260ms；减少动画模式下直接写入最终值。为地图路径、城市标签、排名行和底部导航统一维护 `is-active`。

- [ ] **Step 5: 实现动态排名和 FLIP 重排**

排名行展示岗位数、招录人数、单岗平均招录人数和考试类别构成。排序只按当前指标数值降序，缺失值置底；使用 360ms FLIP 位移，不改变真实数据。

- [ ] **Step 6: 重跑浏览器交互测试**

Run: `node tests/browser_smoke.js`  
Expected: 指标切换、城市选择、检查器与排名同步通过，控制台无错误。

---

### Task 5: 三城比较台

**Files:**
- Modify: `anhui_site_work_20260828/tools/anhui_web/build_pages.py`
- Modify: `anhui_site_work_20260828/tools/anhui_web/templates/jobs.css`
- Modify: `anhui_site_work_20260828/tools/anhui_web/templates/jobs.js`
- Modify: `anhui_site_work_20260828/tests/browser_smoke.js`

**Interfaces:**
- Consumes: 城市聚合数据和 `compareCities: string[]`。
- Produces: `#city-compare`、`#city-compare-chart`、`#city-compare-table`、`toggleCompareCity(city)`。

- [ ] **Step 1: 写三城上限与同步失败测试**

```javascript
for (const city of ['合肥', '芜湖', '安庆']) await page.locator(`[data-compare-city="${city}"]`).click();
assert.strictEqual(await page.locator('#city-compare [data-compare-card]').count(), 3);
await page.locator('[data-compare-city="滁州"]').click();
assert.match(await page.locator('#city-compare-status').innerText(), /最多选择3座城市/);
```

- [ ] **Step 2: 运行测试确认缺少比较功能**

Run: `node tests/browser_smoke.js`  
Expected: FAIL，找不到城市比较标记。

- [ ] **Step 3: 实现比较选择器、卡片和 SVG 分组条**

默认比较合肥、芜湖、安庆。图表展示三项数值，构成条展示三类考试岗位占比；图表下方生成同值 HTML 表格，确保可读和可打印。

- [ ] **Step 4: 实现三城上限、替换和移除反馈**

第四座城市不自动挤掉原选择，显示明确状态；每张卡可移除，空位提供选择入口。

- [ ] **Step 5: 运行三城比较测试**

Run: `node tests/browser_smoke.js`  
Expected: 三城选择、上限提示、图表和表格同步通过。

---

### Task 6: 岗位检索、收藏对比篮和 CSV 导出

**Files:**
- Modify: `anhui_site_work_20260828/tools/anhui_web/build_pages.py`
- Modify: `anhui_site_work_20260828/tools/anhui_web/templates/jobs.css`
- Modify: `anhui_site_work_20260828/tools/anhui_web/templates/jobs.js`
- Modify: `anhui_site_work_20260828/tests/browser_smoke.js`

**Interfaces:**
- Consumes: `page-data.jobRecords` 和稳定 `record_id`。
- Produces: `savedJobs: string[]`、`toggleSavedJob(recordId)`、`renderSavedJobs()`、`exportFilteredJobs()`、`#job-compare-tray`。

- [ ] **Step 1: 写收藏、恢复和导出失败测试**

```javascript
await page.locator('[data-save-job]').nth(0).click();
await page.locator('[data-save-job]').nth(1).click();
assert.strictEqual(await page.locator('#job-compare-tray [data-saved-column]').count(), 2);
await page.reload();
assert.strictEqual(await page.locator('#job-compare-tray [data-saved-column]').count(), 2);
```

同时在 Python 测试中验证导出字段顺序固定为 `城市,考试类别,代码,单位与职位,招录人数`，且以 `= + - @` 开头的单元格会增加前导单引号。

- [ ] **Step 2: 运行测试确认功能缺失**

Run:

```powershell
python -m unittest tests.test_anhui_web.JobExportTests -v
node tests/browser_smoke.js
```

Expected: FAIL，缺少导出函数或对比篮。

- [ ] **Step 3: 为岗位行增加稳定收藏入口**

岗位表的每个数据行增加 `data-record-id` 和“加入对比”按钮；按钮不改动源单元格文字。收藏上限固定为 5，超限显示状态消息。

- [ ] **Step 4: 实现对比篮和本地恢复**

对比篮以公共字段为固定左轴，其他字段按源表原名补充；本地存储键固定为 `wanyu.savedJobs.v1`，读取时过滤不存在的记录。

- [ ] **Step 5: 实现筛选标签、关键词高亮和安全 CSV**

关键词高亮使用包裹文本节点的 `<mark>`，清除查询后恢复原文本。CSV 从原始 `page-data` 生成，字段包含双引号转义、UTF-8 BOM 和公式注入防护。

- [ ] **Step 6: 运行收藏、导出和原文完整性测试**

Run:

```powershell
python -m unittest tests.test_anhui_web.JobExportTests -v
python -m unittest tests.test_anhui_web.GeneratedPageTests.test_every_source_paragraph_and_table_cell_is_visible -v
node tests/browser_smoke.js
```

Expected: 全部通过。

---

### Task 7: 岗位与全包双页城市深链

**Files:**
- Modify: `anhui_site_work_20260828/tools/anhui_web/templates/jobs.js`
- Modify: `anhui_site_work_20260828/tools/anhui_web/templates/salary.js`
- Modify: `anhui_site_work_20260828/tools/anhui_web/build_pages.py`
- Modify: `anhui_site_work_20260828/tests/browser_smoke.js`

**Interfaces:**
- Consumes: `city` 查询参数和现有 `selectCity()`。
- Produces: `readLinkedCity(validCities) -> string | null`，跨页 URL `?city=<编码城市>#<城市章节>`。

- [ ] **Step 1: 写深链失败测试**

```javascript
await page.goto(`${jobsUrl}?city=${encodeURIComponent('芜湖')}`);
assert.strictEqual(await page.locator('#jobs-inspector-city').innerText(), '芜湖');
const salaryHref = await page.locator('#open-salary-city').getAttribute('href');
assert.match(salaryHref, /city=%E8%8A%9C%E6%B9%96/);
```

- [ ] **Step 2: 运行测试确认页面未恢复城市**

Run: `node tests/browser_smoke.js`  
Expected: FAIL，缺少深链初始化或链接。

- [ ] **Step 3: 实现参数校验与对称跳转**

只有 16 市白名单中的值可以改变初始状态；未知城市保持默认值。岗位页链接到全包档案，全包页链接到岗位城市章节，两个页面使用 `URLSearchParams` 生成地址。

- [ ] **Step 4: 运行深链和无脚本测试**

Run: `node tests/browser_smoke.js`  
Expected: 两页深链、默认回退和无 JavaScript 正文通过。

---

### Task 8: 动效、响应式、打印和视觉细化

**Files:**
- Modify: `anhui_site_work_20260828/tools/anhui_web/templates/common.css`
- Modify: `anhui_site_work_20260828/tools/anhui_web/templates/jobs.css`
- Modify: `anhui_site_work_20260828/tools/anhui_web/templates/jobs.js`
- Modify: `anhui_site_work_20260828/tests/browser_smoke.js`

**Interfaces:**
- Consumes: 五张参考图和 Tasks 3–7 的稳定 DOM。
- Produces: `setupJobReveals()`、`animateJobNumber()`、`animateOpportunityLens()` 和完整响应式/打印规则。

- [ ] **Step 1: 增加平板、减少动画和打印断言**

浏览器测试增加 1024×768 视口、`reducedMotion: 'reduce'` 和打印媒体；断言无水平溢出、关键控制可见、动画时长归零、打印时工作台控制轨隐藏。

- [ ] **Step 2: 运行测试捕获布局与动画缺口**

Run: `node tests/browser_smoke.js`  
Expected: 新增断言至少一项失败。

- [ ] **Step 3: 实现规格中的动效时长和降级**

首屏总时长不超过 640ms，地图 260ms、数字 420ms、排名 360ms、比较卡 180ms；所有时长通过 CSS 自定义属性统一管理，减少动画媒体查询将其设为 `0ms`。

- [ ] **Step 4: 完成 1024 与 390 布局**

1024px 以下控制轨转顶部；720px 以下按检查器、地图、城市导航顺序排列。390px 只常驻选中城市标签，数据表保持容器内横向滚动。

- [ ] **Step 5: 完成打印和键盘焦点**

打印隐藏筛选控件、浮动工具和动画图层，保留城市比较表、岗位对比表和全部原始表；所有可交互 SVG 区域与按钮使用清晰的 `:focus-visible`。

- [ ] **Step 6: 重跑完整浏览器验收**

Run: `node tests/browser_smoke.js`  
Expected: 1440×900、1024×768、390×844、减少动画、打印和无脚本模式全部通过。

---

### Task 9: 最终内容验证、视觉 QA 和交接包

**Files:**
- Modify: `anhui_site_work_20260828/design-qa-jobs.md`
- Modify: `anhui_site_work_20260828/deliverables/制作说明.md`
- Modify: `anhui_site_work_20260828/HANDOFF.md`
- Create: `anhui_site_work_20260828/tests/artifacts/jobs-redesign-*.png`
- Create: `C:/Users/24218/Desktop/皖域择岗档案_网页重构升级版_20260828.zip`

**Interfaces:**
- Consumes: 通过全部自动化测试的构建结果。
- Produces: 可复现、无缓存和无凭据的最终桌面交接 ZIP。

- [ ] **Step 1: 运行完整 Python 测试**

Run: `python -m unittest tests.test_anhui_web -v`  
Expected: 0 failures，明确报告测试数量。

- [ ] **Step 2: 运行完整浏览器测试并保存截图**

Run: `node tests/browser_smoke.js`  
Expected: 0 errors，并保存桌面工作台、动态排名、三城比较、岗位检索、对比篮和手机首屏截图。

- [ ] **Step 3: 逐张对照五张概念图做视觉审查**

检查信息结构、视觉层级、留白、地图占比、检查器密度、表格可读性和移动端重排；只吸收可实现的设计语言，不复制图片中的虚构数字、趋势和字段。

- [ ] **Step 4: 更新交接文档**

说明新增三项指标、三城比较、岗位收藏、CSV、跨页深链、动效降级和数据口径边界，并记录准确测试结果。

- [ ] **Step 5: 创建并验证桌面 ZIP**

压缩时排除 `__pycache__`、`.pyc`、`.env`、凭据文件和临时截图；打开 ZIP 验证两份 HTML、源 Word、边界 JSON、源码、测试、设计规格、实施计划和 QA 文档均存在。

- [ ] **Step 6: 输出最终交付路径和已验证结果**

只在读取测试退出码、浏览器结果和 ZIP 内容清单后声明完成。

