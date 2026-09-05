# 皖域择岗多周期工作台 v10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"2026 单周期快照档案"升级为"多周期工作台"：数据周期 manifest 化、构建期周期标识注入、历史周期归档布局、悬项核查收尾与新周期接入 SOP，使 2027 国考公告（预计 2026-10 中旬）发布后，新数据可按固定流程接入而不覆盖历史参照。

**Architecture:** 数据周期元信息集中在 `tools/anhui_web/data/manifest.json`，由新模块 `tools/anhui_web/cycles.py` 统一读取；构建脚本（`build_pages.py`）从 manifest 解析周期标签并在构建期把"数据周期 · 快照日期"注入页面数据更新卡与页脚，运行时零远程依赖不变。历史周期数据迁入 `data/cycles/<cycle>/` 只读归档，地理边界数据（`anhui_340000_full.json`）不随周期变化，保留在 `data/` 根。悬项核查只修改 JSON 清单（`job_eligibility_exclusions.json`、`position_eligibility.json`）与报告文档，不改代码逻辑。

**Tech Stack:** Python 3.12、python-docx 1.2.0、lxml 6.1.1、原生 HTML/CSS/JavaScript、unittest、node --test、release.py 一键发布。

## Global Constraints

- 成品继续是可双击打开、无需服务器、无需联网的单文件 HTML；不新增远程资源。
- 保留源数据事实与中性口径：周期切换只改变数据来源与标识，不改写竞争比口径（招录 ÷ 考试人数，缺失回退报名）、不生成录用概率承诺、不补写缺失数据。
- 未取得的数据（国考逐岗备注等）只能标注"未核查"，不得臆造；悬项状态必须可在 manifest 与数据字典中追踪。
- 544 条源表岗位、825 人、16 市、106/31 张源表的保真测试不回退。
- 数据文件移动（data/cycles/ 归档）必须与 build_pages.py 路径改造同步落地，且以全套测试通过为完成标准；在无法重建源 Word 缺失的环境下，只做 manifest 声明，不做文件搬移。

---

### Task 0: 交接包可移植性修复（2026-08-29 已执行）

**Files:**
- Modify: `tests/test_anhui_web.py`
- Modify: `tools/anhui_web/release.py`
- Modify: `HANDOFF.md`
- Add: `tools/anhui_web/data/manifest.json`
- Add: `tools/anhui_web/cycles.py`
- Add: `docs/数据更新操作手册.md`
- Test: `tests/test_anhui_web.py`（新增 CycleManifestTests）

- [x] **Step 1: 移除测试回退到个人下载目录的硬编码路径**

源 Word 解析顺序改为 包内 `source_docs/` → 环境变量 `WANYU_JOBS_DOCX` / `WANYU_SALARY_DOCX`；两者皆缺时，依赖源文档的用例以 `unittest.skip` 跳过并附原因，不再以 FileNotFoundError 整类报错。

- [x] **Step 2: release.py 打包清单纳入 source_docs/（存在时）**

`ZIP_DIRS` 加入 `source_docs`（`package_zip` 已跳过缺失目录）；打包时若缺失则打印显式警告，避免再次发出无法重建的交接包。

- [x] **Step 3: HANDOFF.md 版本对齐**

标题从 v7 更正为 v9.2，补记 v9.1 / v9.2 增量（依据 polish.css、polish_v92.css 注释与 V9FeatureTests 断言），新增 2026-08-29 修缮记录。

- [x] **Step 4: 数据周期 manifest 与读取器落地**

`manifest.json` 声明 cycle=2026、snapshot_date=2026-08-28、源文档名、数据集文件与开放核查项（0801048 待复核、国考 3 条未核验）；`cycles.py` 提供 `load_manifest` / `resolve_dataset` / `cycle_label`；`CycleManifestTests` 校验清单字段完整且指向真实文件（不依赖源 Word，任何环境可跑）。

### Task 1: 构建期周期标识注入

**Files:**
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tools/anhui_web/templates/product-shell.css`
- Modify: `tests/test_anhui_web.py`
- Test: `tests/test_anhui_web.py`

**Interfaces:**
- Consumes: `cycles.load_manifest()` 的 cycle / snapshot_date；现有页面"数据更新卡"区块与页脚模板位。
- Produces: 三个 HTML 数据更新卡与页脚出现"数据周期 2026 · 快照 2026-08-28"标识（data-cycle 属性），打印样式保留。

- [ ] **Step 1: Write the failing assertions**

在 `PageManifestTests` 增加断言：`data-cycle="2026"` 与 `数据周期 2026` 同时出现在 master / jobs / salary 三页正文与页脚。

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m unittest tests.test_anhui_web.PageManifestTests -v`

Expected: 缺少周期标识而失败（需先补齐 source_docs/ 使构建可运行）。

- [ ] **Step 3: Implement the cycle badge**

`build_jobs_context` / `build_salary_context` / `_generic_context` 从 `cycles.load_manifest()` 取周期标签注入模板占位符；徽标样式加入 `product-shell.css`（低饱和蓝胶囊，浅/暗两态）。

- [ ] **Step 4: Re-run tests and update data dictionary**

Run: `python -m unittest tests.test_anhui_web -v`；`python tools/anhui_web/gen_data_dict.py`

Expected: 全套 Python 用例通过，数据字典记录周期标识字段。

### Task 2: 历史周期归档布局

**Files:**
- Modify: `tools/anhui_web/build_pages.py`（数据路径解析改经 cycles 模块）
- Modify: `tools/anhui_web/data/README.md`
- Test: `tests/test_anhui_web.py`

- [ ] **Step 1: 定义目录约定并写入 README**

`data/cycles/<cycle>/` 存放该周期可变数据（position_eligibility.json、job_eligibility_exclusions.json、周期源 Word 副本可选）；`data/` 根保留地理边界等跨周期资产；manifest 移至 `data/cycles/<cycle>/manifest.json`，`data/manifest.json` 保留为"当前周期指针"（内容为 `{"current": "2026"}`）。

- [ ] **Step 2: build_pages.py 切换到 manifest 解析路径**

`POSITION_ELIGIBILITY_PATH` 等常量改为 `cycles.resolve_dataset(...)`；`--cycle` 命令行参数（默认取当前指针），目录缺失时报错信息给出补救指引。

- [ ] **Step 3: 迁移 2026 数据并回归**

移动 JSON 至 `data/cycles/2026/`，更新 manifest datasets 相对路径；Run: `python -m unittest tests.test_anhui_web -v` 全绿；`CycleManifestTests` 断言同步更新。

### Task 3: 悬项核查收尾

**Files:**
- Modify: `tools/anhui_web/data/job_eligibility_exclusions.json`（如结论变化）
- Modify: `tools/anhui_web/build_eligibility.py`（国考占位逻辑，如取得备注）
- Modify: `docs/定向岗核查报告_20260828.md`
- Modify: `tools/anhui_web/data/manifest.json`（open_items 状态更新）

- [ ] **Step 1: 跟踪 0801048 复核结论**

取得官方岗位表复核结论后：若确属定向，保留核除并把 `category` 从 `user_flagged` 改为对应定向类；若非定向，从排除清单移除并重跑 `build_eligibility.py` 与构建。无结论则维持待复核标记，并在 manifest open_items 记录最近跟踪日期。

- [ ] **Step 2: 补齐国考 3 条逐岗备注**

从官方国考职位表核对 300110013003 / 300147355001 / 300147357001 三条的"其他条件/备注"；取得后写入核查产物并重建 `position_eligibility.json`，数据字典更新覆盖说明；未取得则维持"未核验"口径。

- [ ] **Step 3: 口径一致性验证**

Run: `python -m unittest tests.test_anhui_web -v`（定向核除计数断言随结论联动更新）；检索页可报岗位计数与报告口径一致。

### Task 4: 新周期接入 SOP 与发布验收

**Files:**
- Modify: `docs/数据更新操作手册.md`（随 Task 1/2 落地刷新）
- Verify: `tools/anhui_web/release.py`

- [ ] **Step 1: 按 SOP 干跑一次 2027 周期接入演练**

用一份改名的新 Word（可为空壳或 2026 副本）走"归档 → manifest 声明 → 核查 → 构建 → 测试 → 发布"全流程，记录卡点并回写 SOP。

- [ ] **Step 2: 完整验收**

Run: `python -m unittest tests.test_anhui_web -v`；`node --test tests/test_wanyu_core.cjs`；`python tools/anhui_web/release.py --zip`

Expected: 全部通过，发布 zip 含 source_docs（或打包警告为已知豁免），HANDOFF.md 追加 v10 日志。

## 当前执行记录（2026-08-29）

- Task 0 四步已全部落地并通过验证（详见 HANDOFF.md"2026-08-29 交接包修缮"）；Task 1 起需要先取回 source_docs/ 两份源 Word 方可构建验证。
