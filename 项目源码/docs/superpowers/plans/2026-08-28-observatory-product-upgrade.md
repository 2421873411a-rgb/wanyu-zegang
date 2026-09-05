# 皖域择岗档案产品升级 Implementation Plan

> **For agentic workers:** Execute this plan task-by-task in the current session, keeping each task independently testable.

**Goal:** 在保持两个统一离线 HTML、源数据事实和现有动态地图的前提下，把岗位与待遇网站升级为更克制、更易决策的研究型工作台。

**Architecture:** 继续使用 `tools/anhui_web/build_pages.py` 生成两份自包含 HTML。视觉层集中在 `product-shell.css`、`unified.css`，交互层按岗位/待遇模板脚本拆分；所有状态通过 URL 参数、hash 和 `localStorage` 在同一文件内部流转，不引入后端或远程资源。

**Tech Stack:** Python 3.12、python-docx、内联 HTML/CSS/JavaScript、SVG GeoJSON 地图、Playwright bundled smoke tests。

## Global Constraints

- 最终交付仍只有 `安徽十六市2026软件工程可报岗位.html` 和 `安徽全省16市本科普通岗全包分析.html` 两个正式 HTML。
- 岗位竞争比定义为“招录人数 ÷ 考试人数”，逐岗缺失考试人数时回退报名人数，页面统一显示 `1:N`。
- 不新增岗位优劣、推荐等级或薪资预测；新增标签只能描述源字段是否存在及数据来源。
- 地图必须整块城市区域和键盘入口均可操作，焦点样式使用蓝色描边，不出现浏览器原生黑框。
- 1440×900 与 390×844 均不得产生页面级横向溢出；`prefers-reduced-motion` 下关闭位移和数字滚动。
- 两份档案必须继续保留岗位 106 张源表、待遇 31 张源表及源段落/单元格。

---

### Task 1: 研究型视觉基础层

**Files:**
- Modify: `tools/anhui_web/templates/product-shell.css`
- Modify: `tools/anhui_web/templates/unified.css`
- Test: `tests/browser_smoke_v2.js`
- Verify: `tests/capture_design.js`

**Interfaces:**
- Consumes: 当前产品壳层的 `--blue`、`--line`、`--shadow` 变量和各视图现有 class。
- Produces: 统一的纸张背景、细线卡面、标题层级、导航 active/focus 状态，以及对比页桌面双列/移动单列视觉基线。

- [ ] **Step 1: Write the failing visual assertions**

在浏览器烟测中增加页面级检查：岗位对比视图存在、桌面 `jobs-compare-list` 为两列、390px 时页面 `scrollWidth <= 391`，导航 active 只有蓝色下划线且无黑色 outline。

- [ ] **Step 2: Run the focused browser test and verify it fails or exposes the current baseline**

Run: `& $node tests/browser_smoke_v2.js`

Expected: 新增断言在视觉基线尚未固定时暴露问题，现有功能断言保持通过。

- [ ] **Step 3: Implement the visual foundation**

在产品壳层中收敛背景与卡片阴影，统一 `:focus-visible`、导航 active 下划线、按钮 hover 和小屏间距；保留数据色含义，不改变任何源字段或计算值。

- [ ] **Step 4: Run the focused browser test and capture reference screenshots**

Run: `& $node tests/browser_smoke_v2.js` and `& $node tests/capture_design.js`

Expected: 两个视口无横向溢出，岗位对比页无遮挡层，截图更新到 `tests/artifacts/`。

### Task 2: 地图与排名状态动效

**Files:**
- Modify: `tools/anhui_web/templates/product-jobs.js`
- Modify: `tools/anhui_web/templates/product-salary.js`
- Modify: `tools/anhui_web/templates/product-jobs-ranking.js`
- Modify: `tools/anhui_web/templates/product-salary-ranking.js`
- Modify: `tools/anhui_web/templates/unified.css`
- Test: `tests/browser_smoke_v2.js`

**Interfaces:**
- Consumes: `window.productData.metrics`、`window.productData.series`、现有 SVG 城市节点和 `window.wanyuMotion`。
- Produces: 指标/身份/阶段切换时的颜色、数字、排名和事实条同步动画；地图整块区域与标签保持同一选中状态。

- [ ] **Step 1: Add interaction assertions**

验证岗位三指标切换会同时更新地图标题、检查器单位和事实条；待遇阶段切换会更新地图值、排名摘要和 URL 参数；点击地图区域后城市值与 URL 保持一致。

- [ ] **Step 2: Run smoke tests before implementation**

Run: `& $node tests/browser_smoke_v2.js`

Expected: 若断言针对新状态未挂载，应明确失败；已有地图点选和竞争比断言不回退。

- [ ] **Step 3: Implement state transitions**

为已有 `render`/`selectCity` 增加统一的过渡 class、状态播报和数字格式化；避免新增定时器堆积，切换前取消上一次动画；在 reduced-motion 下直接写入最终值。

- [ ] **Step 4: Re-run tests and inspect screenshots**

Run: `python -m unittest discover -v`; `& $node tests/browser_smoke_v2.js`; `& $node tests/capture_design.js`

Expected: 16 个 Python 测试及两个浏览器烟测通过，截图中地图切换无黑框、无闪烁。

### Task 3: 岗位决策工作流

**Files:**
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tools/anhui_web/templates/product-jobs-search.js`
- Modify: `tools/anhui_web/templates/unified.css`
- Modify: `tests/test_anhui_web.py`
- Modify: `tests/browser_smoke_v2.js`

**Interfaces:**
- Consumes: 544 条 `records`、稳定 `record_id`、岗位检索视图和已确认的 `#jobs_compare`。
- Produces: 信息完整度/竞争比分母来源标签、岗位详情内部视图、最多 4 条岗位事实矩阵、收藏与筛选快照的本地状态接口；当前先落地收藏视图与原代码定位。

- [ ] **Step 1: Add data-boundary tests**

测试每个新增标签只由源字段存在性决定；收藏和筛选快照只写入 `localStorage`，刷新后不得改变岗位原始记录；岗位对比仍最多 4 条且导出字段顺序不变。

- [ ] **Step 2: Run tests and confirm missing behavior**

Run: `python -m unittest discover -v`; `& $node tests/browser_smoke_v2.js`

Expected: 新增行为断言在实现前失败，现有 16 个 Python 测试仍能定位当前基线。

- [ ] **Step 3: Implement neutral decision aids**

在检索表增加轻量字段来源标签和收藏入口；在对比视图增加关键字段/全部字段切换和差异高亮；保存筛选条件时序列化白名单参数，不写入源数据或生成推荐结论。

- [ ] **Step 4: Verify keyboard, storage and export flows**

Run: `& $node tests/browser_smoke_v2.js`

Expected: `/` 聚焦搜索、`Esc` 清空、收藏刷新恢复、对比移除/清空、CSV BOM 与公式防护均通过。

### Task 4: 双站档案联动与交付验收

**Files:**
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tests/capture_design.js`
- Modify: `HANDOFF.md`
- Modify: `design-qa.md`
- Modify: `deliverables/制作说明.md`
- Test: `tests/test_anhui_web.py`
- Test: `tests/browser_smoke.js`
- Test: `tests/browser_smoke_v2.js`

**Interfaces:**
- Consumes: 两套档案索引、城市 hash、跨站导航和前 3 个任务的交互状态。
- Produces: 最终两个 HTML、更新截图、QA 记录和桌面交接压缩包。

- [ ] **Step 1: Add final manifest assertions**

断言输出目录只有两个正式 HTML，岗位视图包含 `jobs_dashboard/jobs_ranking/jobs_search/jobs_compare/jobs_archive`，待遇视图包含三个内部视图，源表数量不变。

- [ ] **Step 2: Build and run the complete test suite**

Run: `python tools/anhui_web/build_pages.py --output-dir deliverables`; `python -m unittest discover -v`; bundled Node 运行 `tests/browser_smoke.js` 和 `tests/browser_smoke_v2.js`。

Expected: 构建成功、Python 16/16 通过、两个浏览器烟测 PASS。

- [ ] **Step 3: Perform in-app browser click verification**

实际点击岗位地图城市、待遇地图城市、指标/阶段、岗位检索加入对比、岗位对比返回和档案目录；确认城市、数值、hash、焦点样式和滚动位置正确。

- [ ] **Step 4: Refresh handoff package and record evidence**

Run: `powershell -ExecutionPolicy Bypass -File .\\package_handoff.ps1`

检查桌面压缩包存在、包含两个 HTML、设计截图、测试脚本、计划和 QA 文档；在 `HANDOFF.md` 与 `design-qa.md` 记录最终测试结果。

## 当前执行记录（2026-08-28）

- 已完成 Task 1/2 的第一轮视觉与动效切片：地图指标切换使用真实过渡 class，排名切换使用行级状态动画，并继续尊重 reduced-motion。
- 已完成 Task 3 的收藏子集：检索行新增本地收藏，`jobs_saved` 视图支持卡片、移除、清空和回到原代码筛选定位；岗位对比继续保持独立视图，不遮挡检索表。
- 已完成 Task 4 的构建与验收切片：输出仍为两个正式 HTML，Python 16/16、两个 bundled Playwright 烟测通过，设计截图已补充岗位对比与我的岗位页面。
- 下一轮待执行项保持在同一计划内：信息完整度与竞争比分母来源标签、岗位详情视图、筛选快照保存，以及待遇排名轨迹的进一步视觉打磨。
