# 长期维护三年岗位站 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留可双击交付的单文件离线快照的同时，增加一个由外置 JSON 驱动、支持三年切换、岗位榜单专业筛选和可重复构建的长期维护站点。

**Architecture:** 数据仍以现有三年构建链和审计结果为唯一来源，不在新页面手工复制岗位事实。新增 `deliverables/maintainable/` 作为 HTTP 静态站：`index.html` 只放应用壳，`assets/` 放运行时，`data/cycles/{year}.json` 按周期承载完整经核验载荷；原 `皖域择岗总览.html` 继续作为无服务器单文件回退快照。榜单专业筛选使用当前周期 `allMajors.rows` 的 `zy` 字段，支持输入关键词并保持“空值不推断为零”的数据语义。

**Tech Stack:** Python 3.11 构建器、现有审计/周期载荷模块、原生 HTML/CSS/JavaScript、Playwright 浏览器烟测、Python `unittest`。

## Global Constraints

- 三个周期必须继续使用现有冻结基线：2024 10,017 岗/15,331 人，2025 10,150 岗/14,721 人，2026 8,511 岗/12,006 人。
- 不把未发布、未回收、无法唯一匹配的官方资料填成 0；页面要展示证据状态和已登记边界。
- 新维护站不得把三年岗位行放进 `index.html`；岗位数据只能从 `data/cycles/*.json` 加载。
- 继续保留无远程资源、可离线打包的单文件入口；维护站在 `file://` 下给出启动提示，使用本地 HTTP 服务器加载 JSON。
- 生产代码遵循 TDD：先写一个会失败的行为测试，再写最小实现，再跑全量回归。
- 所有生成文件必须由构建脚本可重复产生，日期优先使用源快照日期，不使用当天日期制造内容哈希漂移。

## 文件边界

- Create: `tools/anhui_web/templates/maintainable-site.js` — 外置数据站路由、周期加载、总览/三年对照/榜单/检索/数据边界渲染。
- Create: `tools/anhui_web/templates/maintainable-site.css` — 维护站轻蓝灰视觉系统和响应式布局。
- Create: `tools/anhui_web/build_maintainable_site.py` — 从 `build_unified_bundles()` 导出三份周期 JSON、manifest、壳页面和静态资源。
- Create: `tools/anhui_web/serve_maintainable.py` — 本地 HTTP 服务器，避免直接打开 `file://` 时浏览器拒绝 `fetch`。
- Create: `tests/test_maintainable_site.py` — 构建产物、外置数据边界、榜单筛选契约测试。
- Modify: `tools/anhui_web/build_pages.py` — 岗位榜单加入专业输入/候选列表和行级专业钩子。
- Modify: `tools/anhui_web/templates/product-jobs-ranking.js` — 专业筛选、空结果提示、筛选后重新排名和 URL 状态。
- Modify: `tools/anhui_web/templates/ui-v13.css` — 顶部由深海军蓝降为中等蓝，周期上下文改为浅蓝灰，移动端保持不溢出。
- Modify: `tools/anhui_web/release.py` — 发布链同步生成维护站并纳入 ZIP 前验证。
- Modify: `tests/browser_smoke_v12.js` — 增加三年岗位榜单专业筛选的真实浏览器闭环。
- Create: `docs/长期维护网站架构方案_v1.md` — 数据分层、更新流程、回滚、审计门禁和运行方式。
- Modify: `deliverables/HANDOFF.md`, `deliverables/制作说明.md`, `HANDOFF.md` — 交接入口、双轨说明和最终验证结果。

### Task 1: 先锁定外置载荷与榜单交互契约

**Files:**
- Create: `tests/test_maintainable_site.py`
- Modify: `tests/browser_smoke_v12.js`

**Interfaces:**
- `build_maintainable_site.build_maintainable_site(root: Path, output_dir: Path) -> dict[str, object]` 返回 manifest 字典。
- 榜单 DOM 使用 `#ranking-major-input`、`#ranking-major-options`、`data-ranking-major` 和 `#ranking-filter-count`。

- [ ] **Step 1: 写失败测试**

  在 Python 中断言维护站构建后 `index.html` 不含 `data-cycle-payload`，manifest 列出 2024/2025/2026 的 `data/cycles/{year}.json`，每份 JSON 的岗位/招录总数等于冻结基线；同时断言 `_jobs_ranking_content()` 产出专业输入和候选列表钩子。

  在浏览器烟测中打开 `?cycle=2026#jobs_ranking`，选择第一个非空专业候选，断言筛选计数小于全量、每行 `data-ranking-major` 命中筛选词，并清空后恢复全量。

- [ ] **Step 2: 运行测试确认正确失败**

  运行 `python -m unittest tests.test_maintainable_site -v` 和 `node tests/browser_smoke_v12.js --grep ranking-major-filter`；预期分别因构建器不存在、榜单没有专业控件而失败。

### Task 2: 实现榜单专业筛选和更轻顶部

**Files:**
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tools/anhui_web/templates/product-jobs-ranking.js`
- Modify: `tools/anhui_web/templates/ui-v13.css`

**Interfaces:**
- 服务器端榜单行从当前周期 `allMajors.rows` 取得 `zy` 字段，使用安全 HTML 转义生成 `data-ranking-major`；不改变城市统计事实。
- 浏览器端把 `window.productData.allMajors.rows` 作为唯一专业候选源，输入值按大小写/空白归一化后做包含匹配；筛选只影响显示行和排名，不改原数据。

- [ ] **Step 1: 让 Task 1 的榜单测试先变绿**

  在 toolbar 添加 `label`、`input#ranking-major-input`、`datalist#ranking-major-options`、清除按钮和 `#ranking-filter-count`；每个候选专业去重、去空、按中文排序并限制首屏候选数量，完整候选通过 datalist 保留。

- [ ] **Step 2: 让浏览器筛选闭环变绿**

  JS 监听 `input` 与清除操作：用输入关键词匹配行的 `data-ranking-major`，将不匹配行 `hidden=true`，按选中的指标对可见行重新编号，显示“已筛选 X / 全部 Y 条城市榜单”；周期切换重新读取当前周期 rows，URL 使用 `major` 参数恢复状态。

- [ ] **Step 3: 调浅顶部并保持响应式**

  在现有 v13.1 校准层最后增加 `--research-header`、浅色 `.wy-context` 和按钮/文字对比度规则；用 `max-width:1100px` 与 `max-width:760px` 重申布局列数和宽度约束。

- [ ] **Step 4: 运行局部回归**

  运行 `python -m unittest tests.test_ui_v13 tests.test_maintainable_site -v`，再执行 `python tools/anhui_web/build_pages.py --output-dir deliverables` 和目标浏览器烟测。

### Task 3: 建立外置 JSON 维护站

**Files:**
- Create: `tools/anhui_web/build_maintainable_site.py`
- Create: `tools/anhui_web/templates/maintainable-site.js`
- Create: `tools/anhui_web/templates/maintainable-site.css`
- Create: `tools/anhui_web/serve_maintainable.py`
- Create: `docs/长期维护网站架构方案_v1.md`

**Interfaces:**
- 构建器调用 `build_unified_bundles(root)` 和 `_payload_for(bundle)`，只输出周期 JSON，不读取或拼接单文件中的岗位 HTML。
- `site-manifest.json` 提供 `schema`, `release`, `snapshot_date`, `default_cycle`, `cycles[]`，每个周期提供 `data`, `posts`, `recruits`, `bytes`, `sha256`。
- 浏览器运行时公开 `window.WanyuMaintainableSite`，至少包含 `loadCycle(cycle)`, `render(view)`, `state`，并支持 `#overview`, `#cycle_compare`, `#jobs_ranking`, `#jobs_search`, `#data_boundary`。

- [ ] **Step 1: 写最小外置导出**

  由三年 bundle 生成 `deliverables/maintainable/data/cycles/2024.json`, `2025.json`, `2026.json`，将岗位行、城市、审计、成绩关联和周期信息放在对应文件；生成带哈希的 manifest；生成不含岗位数据的壳 `index.html`。

- [ ] **Step 2: 实现运行时核心**

  `app.js` 启动后加载 manifest，默认加载 2026；切换周期时只 fetch 对应 JSON 并缓存；总览渲染周期 KPI，三年对照渲染 manifest 摘要和审计边界，榜单从 rows 聚合城市并支持专业输入，检索支持关键词/城市/考试类别，数据边界列出 `cycleInfo.gaps` 与安全留空计数。

- [ ] **Step 3: 实现轻量页面样式**

  使用白色卡片、雾蓝背景、中蓝操作色和少量金色提示；移动宽度 390/768 时导航换行、表格横向滚动仅限表格容器，页面根节点不得横向溢出。

- [ ] **Step 4: 加入本地服务入口和维护文档**

  `serve_maintainable.py` 默认服务 `deliverables/maintainable`，绑定 `127.0.0.1`，输出可访问地址；文档写明构建、服务、校验、更新、回滚和“官方缺口不推断”的规则。

- [ ] **Step 5: 用 HTTP 浏览器烟测验证三年**

  启动 `python tools/anhui_web/serve_maintainable.py --port 8765`，用 Playwright 访问首页，切换 2024/2025/2026，检索岗位，打开榜单并使用专业筛选；断言网络请求只指向本地 JSON、无远程资源、控制台无错误。

### Task 4: 接入发布链、审计交接和最终验收

**Files:**
- Modify: `tools/anhui_web/release.py`
- Modify: `deliverables/HANDOFF.md`
- Modify: `deliverables/制作说明.md`
- Modify: `HANDOFF.md`
- Modify: `tests/test_maintainable_site.py`

**Interfaces:**
- `release.py build_and_sync()` 在单文件构建和 postbuild 之后调用维护站构建器；ZIP 继续递归收录 `deliverables/maintainable`。
- 维护站的 manifest 和 HTML 是构建产物，单文件仍由既有 94 项 prebuild、51 项 postbuild、Node 和浏览器门禁保护。

- [ ] **Step 1: 加入发布链并验证构建顺序**

  在 `build_and_sync()` 中先生成单文件，再执行 `build_maintainable_site.py`；失败时以非零码中止发布，避免出现单文件和外置站版本不一致。

- [ ] **Step 2: 更新交接说明**

  明确两个入口：双击单文件用于无服务器离线查看；长期维护站通过本地 HTTP 服务或静态托管打开。写出三年数据文件位置、源快照日期、审计报告和 116 个无法唯一匹配项继续安全留空的事实。

- [ ] **Step 3: 执行全量验证**

  运行 `python tools/anhui_web/release.py --zip`，确认 Python 全量测试、prebuild、三年审计、页面 postbuild、Node 单测、原单文件浏览器烟测、维护站 HTTP 烟测和 ZIP verifier 全部通过；检查桌面交接 ZIP 的实际路径、大小和时间。

- [ ] **Step 4: 完成交付记录**

  在交接文档中记录可复现命令、通过项数量、维护站入口路径和单文件回退路径；最终回复只报告已验证事实，不把公开缺口描述成“全部官方数据已发布”。

## Self-Review

- 需求覆盖：专业可选已由 Task 1–2 覆盖；顶部变浅由 Task 2 覆盖；不把数据全塞进 HTML 由 Task 3 覆盖；长期更新、校验、回滚、交接由 Task 3–4 覆盖。
- 可测试性：榜单 DOM 契约、三年 JSON 总数、manifest 哈希、HTTP 加载、响应式和无远程资源均有明确断言。
- 数据一致性：外置 JSON 复用现有 `build_unified_bundles()`，不会产生第二套人工数据源；单文件保持既有完整快照能力。
