# 皖域择岗档案 v2 双文件多视图数据产品 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将岗位和待遇两个长报告融合为 2 个自包含的离线网站文件；每个文件内部使用多视图切换，完成真实地图三指标联动、动态排名、岗位比较工作台和档案分层展示。

**Architecture:** 保留 `python-docx` 顺序解析和单文件 HTML 构建模式，在构建阶段生成岗位/待遇数据集；岗位主文件内置观测台、排名、检索、档案四个视图，待遇主文件内置观测台、排名、档案三个视图。顶部标签和 URL hash 负责视图切换，两个主文件之间用相对链接联动；每个文件仍内联自身所需数据并保留完整源表。当前目录不是 Git 仓库，因此每个任务以测试、构建和截图作为检查点，不执行虚构的提交或分支操作。

**Tech Stack:** Python 3.12、python-docx 1.2.0、lxml 6.1.1、原生 HTML/CSS/SVG/JavaScript、Playwright 1.62.1、Python `unittest`。

## Global Constraints

- 最终成品仍为可双击打开、无需服务器、无需联网的离线 HTML。
- 岗位记录必须保持 544 条、招录合计 825 人；考试类别构成与源文档一致。
- 岗位档案保留源 Word 的 106 张表及全部非空段落和单元格；待遇档案保留 31 张表。
- 真实地图继续使用 `tools/anhui_web/data/anhui_340000_full.json`，不绘制近似行政区轮廓。
- 缺失字段显示 `—` 或“该来源无此字段”，不得按零值参与计算。
- 不生成岗位推荐、录取概率、竞争等级、城市综合评分或待遇与岗位的综合结论。
- 所有动效遵守 `prefers-reduced-motion`；关闭 JavaScript 后档案页面仍完整可读。
- 不覆盖 `C:\Users\24218\Desktop\皖域择岗档案_网页重构版_20260828.zip`。
- 当前目录不是 Git 仓库；使用完整测试、输出文件计数和截图 QA 作为替代检查点。

## Final delivery decision (2026-08-28)

本计划早期任务曾以“7 个正式页面 + 2 个兼容入口”作为中间实现方案。根据最终产品要求，发布前已收敛为两个网站文件：岗位主文件包含 `jobs_dashboard`、`jobs_ranking`、`jobs_search`、`jobs_archive` 四个内部视图；待遇主文件包含 `salary_dashboard`、`salary_ranking`、`salary_archive` 三个内部视图。旧拆分页不再作为交付物，内部跳转统一使用 hash，跨产品跳转使用另外一个主文件名。下面保留历史任务记录，验收以本节的双文件架构和最新烟测为准。

---

## 文件边界与职责

- `tools/anhui_web/build_pages.py`：解析 Word、规范化岗位/待遇数据、生成页面上下文和输出清单。
- `tools/anhui_web/templates/product-shell.html`：各内部视图共用的 HTML 外壳、导航、状态槽位和无脚本提示。
- `tools/anhui_web/templates/product-shell.css`：产品级颜色令牌、栅格、按钮、表格、抽屉和响应式基础。
- `tools/anhui_web/templates/product-jobs.js`：岗位观测台地图与检查器。
- `tools/anhui_web/templates/product-jobs-ranking.js`：岗位排名与城市对比。
- `tools/anhui_web/templates/product-jobs-search.js`：岗位筛选、结果表和岗位比较抽屉。
- `tools/anhui_web/templates/product-salary.js`：待遇地图、身份/工龄切换和检查器。
- `tools/anhui_web/templates/product-salary-ranking.js`：待遇排名、五节点轨迹和城市差值。
- `tests/test_anhui_web.py`：数据、页面清单、内容保真和离线约束测试。
- `tests/browser_smoke.js`：7 页面桌面/移动交互、深链和水平溢出回归。
- `tests/capture_design.js`：固定视口的设计 QA 截图。
- `design-qa.md`：目标截图、实现截图、问题记录和最终结论。

## Implementation status

All implementation tasks are complete. `deliverables/` now contains exactly two
final website files; each file embeds its own dashboard, ranking/search and
source-archive views. Python content tests and both bundled Playwright smoke
tests are the release gates.

---

### Task 1: 建立页面清单与兼容入口

**Files:**
- Modify: `tools/anhui_web/build_pages.py`
- Create: `tools/anhui_web/templates/product-shell.html`
- Modify: `tests/test_anhui_web.py`

**Interfaces:**
- Consumes: `DocumentModel`、现有 `build_all()`。
- Produces: `PAGE_MANIFEST`，包含 `jobs_dashboard/jobs_ranking/jobs_search/jobs_archive/salary_dashboard/salary_ranking/salary_archive` 七个输出路径；旧文件名作为兼容入口指向对应观测台。

- [ ] **Step 1: 写页面清单失败测试**

```python
def test_build_outputs_seven_product_pages_and_two_legacy_aliases(self):
    outputs = builder.build_all(OUTPUT_DIR, JOBS_DOCX, SALARY_DOCX)
    names = {path.name for path in outputs}
    expected = {
        "岗位观测台.html", "岗位排名对比.html", "岗位检索.html", "岗位档案.html",
        "待遇观测台.html", "待遇排名.html", "待遇档案.html",
        "安徽十六市2026软件工程可报岗位.html",
        "安徽全省16市本科普通岗全包分析.html",
    }
    self.assertTrue(expected.issubset(names))
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m unittest tests.test_anhui_web.PageManifestTests.test_build_outputs_seven_product_pages_and_two_legacy_aliases -v`

Expected: FAIL，当前构建器只返回两个 HTML。

- [ ] **Step 3: 实现页面清单和外壳装配**

新增：

```python
PAGE_MANIFEST = {
    "jobs_dashboard": "岗位观测台.html",
    "jobs_ranking": "岗位排名对比.html",
    "jobs_search": "岗位检索.html",
    "jobs_archive": "岗位档案.html",
    "salary_dashboard": "待遇观测台.html",
    "salary_ranking": "待遇排名.html",
    "salary_archive": "待遇档案.html",
}

def build_all(output_dir: Path, jobs_docx: Path, salary_docx: Path) -> tuple[Path, ...]:
    """Build seven product pages followed by two compatibility aliases."""
```

外壳必须从页面上下文接收 `PRODUCT_NAME`、`ACTIVE_ROUTE`、`PAGE_TITLE`、`PAGE_CONTENT`、`PAGE_DATA` 和 `PAGE_JS`，使用相对链接，并在无脚本时保留档案内容。

- [ ] **Step 4: 运行页面清单测试和旧测试**

Run: `python -m unittest tests.test_anhui_web -v`

Expected: 页面清单测试通过；若完整内容测试暂时因旧选择器失败，先在下一任务迁移测试，不删除源文档保真断言。

- [ ] **Step 5: 记录构建检查点**

记录 2 个最终输出文件的文件名和大小到 `design-qa.md`，不修改旧 ZIP。

---

### Task 2: 生成页面专属岗位和待遇数据集

**Files:**
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tests/test_anhui_web.py`

**Interfaces:**
- Consumes: `parse_docx()`、`extract_job_records()`、`build_job_metrics()`、`extract_salary_series()`。
- Produces: `build_jobs_dataset(model) -> dict[str, object]`、`build_salary_dataset(model) -> dict[str, object]`，以及页面所需的最小数据 payload。

- [ ] **Step 1: 写页面专属数据失败测试**

```python
def test_jobs_dataset_has_minimal_dashboard_and_archive_payloads(self):
    dataset = builder.build_jobs_dataset(parse_docx(JOBS_DOCX))
    self.assertEqual(dataset["metrics"]["totals"], {"jobs": 544, "recruits": 825})
    self.assertEqual(len(dataset["records"]), 544)
    self.assertEqual(len(dataset["cities"]), 16)
    self.assertEqual(len(dataset["dashboard_records"]), 0)
    self.assertEqual(len(dataset["archive_blocks"]), 262)

def test_salary_dataset_separates_series_from_archive(self):
    dataset = builder.build_salary_dataset(parse_docx(SALARY_DOCX))
    self.assertEqual(set(dataset["series"]), {"公务员", "事业编"})
    self.assertEqual(len(dataset["archive_blocks"]), 259)
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m unittest tests.test_anhui_web.DatasetTests -v`

Expected: FAIL，两个数据集接口尚未定义。

- [ ] **Step 3: 实现最小 payload 分层**

岗位观测台只内联 `cities/metrics/geojson`；岗位检索内联 `records`；岗位档案内联 `archive_blocks`。待遇观测台和待遇排名只内联 `series/stages`；待遇档案内联 `archive_blocks`。统一通过：

```python
def page_data_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
```

保留 `record_id/city/exam/code/unit_position/recruits/source_table/source_row/raw_cells`，不把源表中的缺失值改成数字零。

- [ ] **Step 4: 运行数据集和全文保真测试**

Run: `python -m unittest tests.test_anhui_web.DatasetTests tests.test_anhui_web.GeneratedPageTests.test_every_source_paragraph_and_table_cell_is_visible -v`

Expected: PASS，全部源文字仍在对应档案 payload 中。

---

### Task 3: 重做共享产品外壳和视觉令牌

**Files:**
- Create: `tools/anhui_web/templates/product-shell.css`
- Modify: `tools/anhui_web/templates/product-shell.html`
- Modify: `tests/test_anhui_web.py`

**Interfaces:**
- Consumes: Task 1 的页面清单和 `ACTIVE_ROUTE`。
- Produces: `.product-header`、`.product-nav`、`.product-shell`、`.route-state`、`.page-footer`，两个主文件内各视图共用的无障碍焦点和响应式基础。

- [ ] **Step 1: 写共享外壳失败测试**

```python
def test_product_pages_share_compact_shell_and_route_navigation(self):
    text = (OUTPUT_DIR / "岗位观测台.html").read_text(encoding="utf-8")
    for marker in ('class="product-header"', 'class="product-nav"', 'data-route="jobs-dashboard"', 'data-route="jobs-search"'):
        self.assertIn(marker, text)
    self.assertNotIn("ANHUI FIELD NOTES", text)
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m unittest tests.test_anhui_web.ShellTests.test_product_pages_share_compact_shell_and_route_navigation -v`

Expected: FAIL，当前岗位页仍使用旧长报告外壳。

- [ ] **Step 3: 实现紧凑外壳**

使用以下令牌并写入 CSS：

```css
:root {
  --product-bg: #f5f8fc;
  --product-panel: #ffffff;
  --product-ink: #162b47;
  --product-muted: #72849b;
  --product-line: #dce6f0;
  --product-blue: #246fe8;
  --product-cyan: #38aeb5;
  --product-amber: #e5aa3b;
}
```

导航固定高度约 64px；桌面使用 12 栏栅格，手机使用 4 栏栅格；默认卡片圆角 10–14px，主地图为唯一大视觉区。外壳不再渲染巨型宣传标题或无功能渐变。

- [ ] **Step 4: 运行 shell 和浏览器宽度测试**

Run: `python -m unittest tests.test_anhui_web.ShellTests -v`；随后执行 `node tests/browser_smoke.js`。

Expected: 外壳标记存在，1440px/390px 无页面级横向溢出。

---

### Task 4: 实现岗位观测台三指标真实地图

**Files:**
- Create: `tools/anhui_web/templates/jobs-dashboard.css`
- Create: `tools/anhui_web/templates/jobs-dashboard.js`
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tests/test_anhui_web.py`
- Modify: `tests/browser_smoke.js`

**Interfaces:**
- Consumes: Task 2 的 `cities/metrics/geojson` payload。
- Produces: `#jobs-workbench`、`#jobs-map`、`#jobs-inspector`、`#job-metric`、`renderJobView(state)`、`selectJobCity(city)`。

- [ ] **Step 1: 写结构和三指标失败测试**

```python
def test_jobs_dashboard_contains_real_metric_surface(self):
    html = (OUTPUT_DIR / "岗位观测台.html").read_text(encoding="utf-8")
    for marker in ('id="jobs-workbench"', 'id="jobs-map"', 'id="jobs-inspector"', 'id="job-metric"', 'id="heat-min"', 'id="heat-max"'):
        self.assertIn(marker, html)
    self.assertEqual(html.count('data-job-region="'), 16)
```

```javascript
await page.locator('[data-job-metric="recruits"]').click();
await page.waitForTimeout(450);
assert.strictEqual(await page.locator('#job-metric-unit').innerText(), '人');
assert.strictEqual(await page.locator('[data-job-region="合肥"]').getAttribute('data-active-metric'), 'recruits');
assert.match(await page.locator('[data-map-label="合肥"]').innerText(), /人$/);
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m unittest tests.test_anhui_web.ShellTests.test_jobs_dashboard_contains_real_metric_surface -v` and `node tests/browser_smoke.js`.

Expected: FAIL，正式观测台和动态标签尚未生成。

- [ ] **Step 3: 生成真实 GeoJSON 地图**

从 `anhui_340000_full.json` 投影每个市级 feature，输出 16 个 `<path data-job-region>`；每个路径附带 `data-city`、`data-active-metric`、键盘焦点和源数据 `<title>`。地图标签单独输出 `data-map-label`，不把岗位数写死在 HTML。

- [ ] **Step 4: 实现统一视图渲染**

```javascript
const state = { metric: 'jobs', city: '', exam: '', query: '' };
function renderJobView(nextState) {
  // derive current values once, then update map, labels, legend, inspector and ranking
}
function selectJobCity(city, { scroll = false } = {}) {
  // update selected path, chip, inspector and URL; scroll only on explicit action
}
```

`jobs/recruits/ratio` 三种指标必须同步更新地图颜色、城市标签、图例、检查器、排名和对比图；`ratio` 以招录人数 ÷ 岗位数计算，岗位数为零时为 `—`。

- [ ] **Step 5: 运行岗位观测台交互测试**

Run: `node tests/browser_smoke.js`。

Expected: 三种指标均能切换；地图标签单位同步；城市点击更新检查器；控制台无错误。

---

### Task 5: 实现岗位排名与城市对比页

**Files:**
- Create: `tools/anhui_web/templates/jobs-ranking.css`
- Create: `tools/anhui_web/templates/jobs-ranking.js`
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tests/browser_smoke.js`

**Interfaces:**
- Consumes: Task 2 的城市聚合数据和 Task 4 的 URL 状态协议。
- Produces: `#jobs-ranking`、`#city-compare`、`#city-compare-chart`、`#city-compare-table`、`renderRanking(metric)`、`renderCityCompare(cities, metric)`。

- [ ] **Step 1: 写排名和对比失败测试**

```javascript
await page.goto(rankingUrl);
assert.strictEqual(await page.locator('[data-ranking-row]').count(), 16);
await page.locator('[data-job-metric="ratio"]').click();
const firstCity = await page.locator('[data-ranking-row]').first().getAttribute('data-city');
assert.ok(firstCity);
await page.locator('[data-compare-city="安庆"]').click();
assert.strictEqual(await page.locator('#city-compare-chart .chart-bar').count(), 9);
```

- [ ] **Step 2: 运行失败测试**

Run: `node tests/browser_smoke.js`。

Expected: FAIL，排名页和对比页尚未生成。

- [ ] **Step 3: 生成动态排名表**

每行显示排名、城市、岗位数、招录人数、单岗平均和当前指标占比；排序使用当前指标，缺失值置底；点击城市回到观测台并携带 `city` 和 `metric`。

- [ ] **Step 4: 生成最多 4 城比较**

比较选择最多 4 城，重新渲染城市卡片、考试类别构成条、柱状图和事实矩阵。图表只使用已有的岗位数、招录人数和类别岗位数，不产生推荐分或趋势预测。

- [ ] **Step 5: 运行排名和比较回归**

Run: `node tests/browser_smoke.js` and `python -m unittest tests.test_anhui_web -v`。

Expected: 16 行排名、对比城市数量和 URL 状态均正确。

---

### Task 6: 实现岗位检索页和比较抽屉

**Files:**
- Create: `tools/anhui_web/templates/jobs-search.css`
- Create: `tools/anhui_web/templates/jobs-search.js`
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tests/test_anhui_web.py`
- Modify: `tests/browser_smoke.js`

**Interfaces:**
- Consumes: Task 2 的 544 条岗位记录。
- Produces: `#jobs-search`、`#job-results`、`#job-compare-drawer`、`toggleSavedJob(id)`、`exportFilteredJobs()`、`renderComparisonDrawer()`。

- [ ] **Step 1: 写检索和对比失败测试**

```python
def test_job_search_page_has_stable_rows_and_drawer(self):
    html = (OUTPUT_DIR / "岗位检索.html").read_text(encoding="utf-8")
    self.assertEqual(html.count('data-job-id='), 544)
    self.assertIn('id="job-compare-drawer"', html)
    self.assertIn('data-job-code="010009"', html)
```

```javascript
await page.goto(searchUrl);
await page.locator('#job-query').fill('010009');
assert.strictEqual(await page.locator('[data-job-row]:visible').count(), 1);
await page.locator('[data-job-id="合肥-004-001"] [data-add-compare]').click();
assert.match(await page.locator('#job-compare-drawer').innerText(), /1 \/ 4/);
await page.locator('[data-diff-only]').click();
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m unittest tests.test_anhui_web.GeneratedPageTests.test_job_search_page_has_stable_rows_and_drawer -v` and `node tests/browser_smoke.js`。

Expected: FAIL，当前检索仍嵌在长档案中。

- [ ] **Step 3: 实现多条件筛选**

筛选输入为单位/职位/代码关键词，城市和考试类别为独立 facet；结果表保留源字段；筛选状态写入 `q/city/exam` URL；输入 `/` 聚焦，`Esc` 只清除关键词。

- [ ] **Step 4: 实现比较抽屉和 CSV**

抽屉最多 4 条；使用 `localStorage` 保存 `record_id`；支持移除单条、只看不同字段、复制摘要和 CSV 导出。导出字段固定为城市、考试类别、代码、单位与职位、招录人数及源表字段，不改写源文本。

- [ ] **Step 5: 运行检索/导出/移动端回归**

Run: `node tests/browser_smoke.js`。

Expected: 010009 精确筛选 1 条；比较抽屉最多 4 条；移动端无水平溢出；无控制台错误。

---

### Task 7: 装配待遇多视图、排名和档案

**Files:**
- Create: `tools/anhui_web/templates/salary-dashboard.css`
- Create: `tools/anhui_web/templates/salary-dashboard.js`
- Create: `tools/anhui_web/templates/salary-ranking.css`
- Create: `tools/anhui_web/templates/salary-ranking.js`
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tests/browser_smoke.js`

**Interfaces:**
- Consumes: `SalaryDataset.series/stages/archive_blocks`。
- Produces: `#salary-map`、`#employment-type`、`#career-stage`、`#salary-ranking`、`#salary-archive`，以及 `type/stage/city` URL 状态。

- [ ] **Step 1: 写待遇多页面失败测试**

```javascript
await page.goto(`${salaryDashboardUrl}?city=安庆&type=事业编&stage=10年`);
assert.strictEqual(await page.locator('#salary-map-city').innerText(), '安庆');
assert.strictEqual(await page.locator('#salary-view-label').innerText(), '事业编 · 入职10年');
await page.goto(salaryRankingUrl);
assert.strictEqual(await page.locator('[data-salary-city]').count(), 16);
```

- [ ] **Step 2: 运行失败测试**

Run: `node tests/browser_smoke.js`。

Expected: FAIL，当前待遇页仍把地图、排名、档案放在同一页面。

- [ ] **Step 3: 装配待遇内容**

观测台视图只保留地图、身份/工龄控制器、检查器和城市导航；排名视图保留五个源节点轨迹与城市差值；档案视图保留 31 张表和估算规则。所有视图装入待遇主文件，旧拆分页不作为交付物。

- [ ] **Step 4: 保持待遇地图状态同步**

身份、工龄、城市切换必须同时更新地图颜色、节点数值、检查器、排名标题和 URL；轨迹只连接源报告实际五个阶段。

- [ ] **Step 5: 运行待遇全量回归**

Run: `python -m unittest tests.test_anhui_web -v` and `node tests/browser_smoke.js`。

Expected: 待遇主文件内的档案视图保留 31 张源表，两个主文件均无控制台错误。

---

### Task 8: 实现跨页深链、动效和无障碍

**Files:**
- Modify: `tools/anhui_web/templates/product-shell.js` (Create if absent)
- Modify: `tools/anhui_web/templates/jobs-dashboard.js`
- Modify: `tools/anhui_web/templates/jobs-ranking.js`
- Modify: `tools/anhui_web/templates/jobs-search.js`
- Modify: `tools/anhui_web/templates/salary-dashboard.js`
- Modify: `tools/anhui_web/templates/salary-ranking.js`
- Modify: `tests/browser_smoke.js`

**Interfaces:**
- Consumes: Task 4–7 的页面状态和 DOM 标记。
- Produces: `readUrlState()`、`writeUrlState()`、`setupMotion()`、`setupKeyboardShortcuts()`。

- [ ] **Step 1: 写深链和 reduced-motion 失败测试**

```javascript
await page.goto(`${jobsDashboardUrl}?city=合肥&metric=recruits`);
assert.strictEqual(await page.locator('#inspector-city').innerText(), '合肥市');
assert.strictEqual(await page.locator('[data-job-metric="recruits"]').getAttribute('aria-pressed'), 'true');
await page.emulateMedia({ reducedMotion: 'reduce' });
assert.strictEqual(await page.locator('[data-job-region="合肥"]').evaluate(node => getComputedStyle(node).animationName), 'none');
```

- [ ] **Step 2: 运行失败测试**

Run: `node tests/browser_smoke.js`。

Expected: FAIL，7 页面状态尚未统一。

- [ ] **Step 3: 实现 URL 协议**

所有页面使用 `URLSearchParams` 读取并用 `history.replaceState` 写回。岗位页互传 `city/metric/exam/q/compare`；待遇页互传 `city/type/stage`；未知参数回退默认值。

- [ ] **Step 4: 实现有意义的动效**

页面进入 180–650ms 分层显现；指标切换地图 260ms、数字 420ms、排名 FLIP 320–360ms；城市选择 180–260ms；比较抽屉 180–240ms。每个动效都服务于状态变化，不使用自动轮播。

- [ ] **Step 5: 实现键盘和 aria**

地图区域支持 Enter/Space；指标和身份按钮使用 `aria-pressed`；检查器和结果计数使用 `aria-live="polite"`；`/` 聚焦检索，`Esc` 清关键词；焦点始终可见。

- [ ] **Step 6: 运行交互和无障碍回归**

Run: `node tests/browser_smoke.js`。

Expected: 普通动画和 reduced-motion 两种模式均无报错，深链能恢复状态，键盘操作可完成城市选择和岗位加入对比。

---

### Task 9: 档案分层、性能控制和内容保真

**Files:**
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tests/test_anhui_web.py`
- Modify: `HANDOFF.md`

**Interfaces:**
- Consumes: Task 2 的 `archive_blocks` 和 Task 1 的页面清单。
- Produces: 两个单文件网站、内部档案视图、重建说明和输出文件检查。

- [ ] **Step 1: 写页面长度和档案保真测试**

```python
def test_dashboards_are_shorter_than_archive_pages(self):
    dashboard = (OUTPUT_DIR / "岗位观测台.html").stat().st_size
    archive = (OUTPUT_DIR / "岗位档案.html").stat().st_size
    self.assertLess(dashboard, archive)
    self.assertEqual((OUTPUT_DIR / "岗位档案.html").read_text(encoding="utf-8").count('data-source-table='), 106)
    self.assertEqual((OUTPUT_DIR / "待遇档案.html").read_text(encoding="utf-8").count('data-source-table='), 31)
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m unittest tests.test_anhui_web.GeneratedPageTests.test_dashboards_are_shorter_than_archive_pages -v`

Expected: FAIL，当前两个页面都包含完整源表。

- [ ] **Step 3: 将源表移入档案页**

观测台、排名视图和检索视图不渲染完整城市章节；档案视图逐字渲染所有源段落、非空单元格和表编号。每个主文件只装配一次对应源档案内容。

- [ ] **Step 4: 更新交接说明**

在 `HANDOFF.md` 写明两个主文件、内部 hash 视图、跨站链接、构建命令、测试命令、源文档和不覆盖旧 ZIP 的约束。

- [ ] **Step 5: 运行全文保真和页面大小测试**

Run: `python -m unittest tests.test_anhui_web -v`。

Expected: 106/31 张表计数正确，全部源文档片段仍可见，默认视图保持短首屏，档案内容按需切换。

---

### Task 10: 设计 QA、浏览器验收和桌面交接包

**Files:**
- Modify: `tests/browser_smoke.js`
- Modify: `tests/capture_design.js`
- Modify: `design-qa.md`
- Modify: `HANDOFF.md`
- Modify: `package_handoff.ps1`

**Interfaces:**
- Consumes: 两个主文件的全部内部视图和全部测试结果。
- Produces: 1440×900/390×844 截图、QA 报告和桌面 `皖域择岗档案_网页产品化升级版_20260828.zip`。

- [ ] **Step 1: 写最终浏览器验收场景**

覆盖：岗位三指标、地图 16 区域、城市深链、排名 16 行、最多 4 城比较、010009 精确检索、对比抽屉、CSV 下载触发、待遇身份/工龄深链、两个主文件内部视图无水平溢出。

- [ ] **Step 2: 运行完整构建和测试**

Run:

```powershell
python -m unittest tests.test_anhui_web -v
node tests/browser_smoke.js
```

Expected: Python 全绿；所有页面桌面/移动无控制台错误和页面级水平溢出。

- [ ] **Step 3: 生成同视口设计截图**

使用 `tests/capture_design.js` 生成：岗位观测台桌面、岗位排名桌面、岗位检索桌面、待遇观测台桌面、岗位观测台移动端；与 `design_refs/` 中 5 张用户参考图逐项检查字体、间距、颜色、地图、标签和动效。

- [ ] **Step 4: 更新 QA 报告**

在 `design-qa.md` 记录 P0/P1/P2 问题、修复结果、保留的 P3 取舍、测试命令输出和最终 `passed/blocked` 结论。

- [ ] **Step 5: 生成并验证桌面交接包**

`package_handoff.ps1` 只复制两个主 HTML、源文档、构建器、模板、测试、设计参考图、计划、规格和 QA；排除 `__pycache__` 与临时目录；输出 ZIP 后验证仅有两个 deliverable HTML。

- [ ] **Step 6: 最终完成前验证**

再次执行完整 Python 测试、浏览器测试和 ZIP 内容计数；确认旧 ZIP 时间戳和文件大小未被覆盖，随后交付两个主文件：

```text
安徽十六市2026软件工程可报岗位.html
安徽全省16市本科普通岗全包分析.html
```

---
