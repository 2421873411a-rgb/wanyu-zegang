# Maintainable Audit and Filter Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将三周期维护站升级为可审计、可分层更新、可组合筛选的长期数据工作台。

**Architecture:** 保留现有统一周期构建器作为唯一事实入口，将每个周期输出为 `overview.json`、`jobs.json`、`audit.json` 三个职责单一的模块，并额外输出三年 `audit/three-year.json` 汇总。前端通过 manifest 按视图懒加载模块，岗位榜单在同一份 `jobs.json` 上组合过滤；单文件离线快照不改变原始数据和既有验收口径。

**Tech Stack:** Python 3.11 标准库构建器与 unittest；原生 JavaScript、HTML、CSS；Playwright 浏览器烟测；PowerShell 发布脚本。

## Global Constraints

- 不修改 `allMajors.rows[*].zy` 等源事实；展示候选只能清洗、去重、过滤纯编码。
- 未发布、未回收、无法唯一匹配的值保持空值或公开边界，不推断为零。
- 维护站 HTML 不内嵌岗位行；岗位行只存在于外置 JSON。
- 周期只能来自 `2024`、`2025`、`2026`；manifest 必须提供稳定哈希。
- 组合筛选必须在同一周期内生效，并显示命中范围；清空后恢复全量。
- 继续使用浅色、低饱和、细边框工作台，不引入远程字体、图片或运行时依赖。

---

### Task 1: Lock the modular data and audit contracts

**Files:**
- Modify: `tests/test_maintainable_site.py`
- Modify: `tools/anhui_web/build_maintainable_site.py`

**Interfaces:**
- Produces manifest cycle entries with `data` compatibility alias and `modules.overview`, `modules.jobs`, `modules.audit` paths.
- Produces `data/audit/three-year.json` with the audited status definitions and all three cycle audit entries.

- [ ] **Step 1: Write failing tests**

Add tests that require every cycle to expose three module files, keep `jobs.json` as the only module containing `allMajors.rows`, and expose an audit summary with all three cycles, gap counts, and unresolved-score counts.

- [ ] **Step 2: Run the focused test to verify failure**

Run: `python -m unittest tests.test_maintainable_site -v`

Expected: FAIL because the current builder writes only `data/cycles/<cycle>.json` and has no audit summary file.

- [ ] **Step 3: Implement the smallest builder change**

Split `_payload_for(bundle)` into module projections without mutating source rows. Write a versioned JSON file under `data/cycles/<cycle>/` for each module, set `data` to the jobs module for compatibility, and write the source audit projection to `data/audit/three-year.json`. Preserve byte hashes for every generated file in the manifest.

- [ ] **Step 4: Run the focused test to verify green**

Run: `python -m unittest tests.test_maintainable_site -v`

Expected: PASS for the modular data contract and the existing external-site contract.

### Task 2: Add auditable frontend state and global audit center

**Files:**
- Modify: `tools/anhui_web/build_maintainable_site.py`
- Modify: `tools/anhui_web/templates/maintainable-site.js`
- Modify: `tools/anhui_web/templates/maintainable-site.css`
- Modify: `tests/maintainable_browser_smoke.js`

**Interfaces:**
- `state.modules` caches module payloads per cycle.
- `loadModule(cycle, module)` loads only a manifest-declared module.
- `renderAuditCenter(globalAudit, cycleAudit)` renders three-year audit coverage and the selected cycle's known boundaries.

- [ ] **Step 1: Write failing browser assertions**

Require the browser to see a `数据审计` view with three cycle rows, a global audit request, a selected-cycle audit request, and visible counts for gaps and unresolved joins.

- [ ] **Step 2: Run the focused browser test to verify failure**

Run: `node tests/maintainable_browser_smoke.js`

Expected: FAIL because the current site has only the per-cycle `数据边界` view and requests one monolithic cycle JSON.

- [ ] **Step 3: Implement module loading and audit rendering**

Load `overview` for initial cycle context, `jobs` only for overview/ranking/search, `audit` only for audit view, and the global audit file for the audit center. Keep clear loading/error states and retain the `file://` explanation. Replace the boundary-only copy with a global audit table plus selected-cycle detail while preserving the no-inference wording.

- [ ] **Step 4: Add focused visual rules**

Style the audit summary as a quiet light workspace: one primary audit table, restrained status chips, a source-chain strip, readable gap cards, and responsive stacking without dark full-bleed sections.

- [ ] **Step 5: Run the focused browser test to verify green**

Run: `node tests/maintainable_browser_smoke.js`

Expected: PASS with no console/page errors, no remote assets, and no horizontal overflow at 390, 768, and 1440px.

### Task 3: Upgrade ranking to truthful combination filters

**Files:**
- Modify: `tools/anhui_web/templates/maintainable-site.js`
- Modify: `tools/anhui_web/templates/maintainable-site.css`
- Modify: `tests/maintainable_browser_smoke.js`

**Interfaces:**
- `state.ranking = { major: '', city: '', exam: '', category: '', metric: 'jobs' }` stores ranking-only controls.
- `filterRows(payload, filters)` intersects only real row fields (`zy`, `city`, `exam`, `lb`).
- `aggregateCities(payload, filters)` aggregates the filtered rows without changing source rows.

- [ ] **Step 1: Write failing browser assertions**

Require city, exam, category, and major controls, verify a combined major-plus-city selection reduces results, and verify reset restores the original city count.

- [ ] **Step 2: Run the focused browser test to verify failure**

Run: `node tests/maintainable_browser_smoke.js`

Expected: FAIL because only major and metric controls exist today.

- [ ] **Step 3: Implement the minimal filter intersection**

Derive option lists from current rows, filter by normalized source text, keep human-readable major options, preserve input focus/cursor, and add one reset action for the full ranking state.

- [ ] **Step 4: Run the focused browser test to verify green**

Run: `node tests/maintainable_browser_smoke.js`

Expected: PASS for all ranking controls, reset behavior, and responsive layout.

### Task 4: Update release documentation and full verification

**Files:**
- Modify: `deliverables/制作说明.md`
- Modify: `deliverables/HANDOFF.md`
- Modify: `HANDOFF.md`
- Modify: `tools/anhui_web/release.py`
- Modify: `tools/anhui_web/data/manifest.json`
- Modify: `deliverables/MANIFEST.txt`

**Interfaces:**
- Handoff documents name the module paths, audit entry, local HTTP command, and current evidence boundaries.
- Release output includes the new maintainable files in the existing ZIP layout.

- [ ] **Step 1: Add documentation assertions**

Extend the maintainable-site contract test to require module path and audit-center instructions in the release/handoff text.

- [ ] **Step 2: Run the full test/build/release pipeline**

Run: `python tools/anhui_web/release.py --zip`

Expected: all Python, audit, Node, formal browser, maintainable browser, and package checks pass.

- [ ] **Step 3: Perform an independent read-only package check**

Run: `python tools/anhui_web/verify_single_file_v12.py package --zip <new Desktop ZIP>` and inspect the generated manifest/module hashes.

Expected: formal single-file checks remain green; maintainable output has no rows in `index.html`, three cycle module directories, and a global audit JSON.

