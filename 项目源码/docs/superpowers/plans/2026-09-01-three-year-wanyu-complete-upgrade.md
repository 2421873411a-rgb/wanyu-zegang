# 皖域择岗三年长期维护全量升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不篡改源事实的前提下，把 v13.4 三年统一网站升级为可长期维护、可审计、可筛选、可比较、可回滚的 v14.0 数据工作台。

**Architecture:** 保留单文件 HTML 作为离线归档；以外置 JSON 静态维护站为主入口；新增来源登记、专业目录、成绩模块、跨年变更模块和复核队列，统一由 manifest 驱动。前端通过 `DataStore` 读取模块，视图不直接拼接文件路径；所有派生统计带口径，所有未知值保持未知。

**Tech Stack:** Python 3 标准库与现有解析器、JSON/UTF-8、现有 HTML/CSS/JavaScript 模板、Node.js 核心测试、Playwright 浏览器烟测、PowerShell 发布命令；不新增运行时第三方依赖，不要求数据库或在线服务。

## Global Constraints

- 发布基线：当前 v13.4；全量升级发布目标为 v14.0，v13.4 包保留为回退版本。
- 真实边界：当前三年 28,678 岗、42,058 人、8 项公开审计边界、116 条无法唯一匹配成绩；不得把未知改为 0。
- 源事实：`jobs.json` 中的岗位原文必须保留；展示清洗只能在 `catalog.json` 和 UI 适配层完成。
- 数据状态：只允许 `verified`、`source_bundle`、`derived`、`unpublished_or_unavailable`、`ambiguous_join`、`needs_review`。
- 专业筛选：候选值不得为纯数字、纯符号或编码残片；“专业不限”只有源字段明确出现时才能出现。
- 模块边界：`overview` 不含完整岗位行；`jobs` 保存岗位行；`catalog` 保存展示选项；`scores` 保存成绩关联；`audit` 保存证据边界；`changes` 保存变化候选。
- 兼容性：保留 `#overview`、`#cycle_compare`、`#jobs_ranking`、`#jobs_search`、`#data_boundary` 旧入口；新入口允许新增 hash，但不能破坏旧链接。
- 本地运行：单文件允许 `file://`；维护站 JSON 必须通过 HTTP 服务读取。
- 离线：正式交付不加载外部脚本、样式、字体或图片；外部来源只作为审计记录，不作为运行时依赖。
- 测试：每个功能先写失败测试，再写最小实现；每个任务结束都要有独立测试命令和可检查产物。
- 交付：没有 Git 仓库，不能以 commit 作为完成证明；以文件、测试、浏览器和 ZIP 校验为证据。

## 1. 文件职责总表

| 文件 | 责任 |
| --- | --- |
| `tools/anhui_web/source_registry.py` | 来源登记、快照哈希、来源状态和定位格式 |
| `tools/anhui_web/data_contract.py` | 证据对象、稳定 ID、空值和状态枚举 |
| `tools/anhui_web/build_catalog.py` | 专业、城市、考试、岗位类型展示目录和检索索引 |
| `tools/anhui_web/build_changes.py` | 相邻周期差异、匹配层级和不可比原因 |
| `tools/anhui_web/build_review_queue.py` | 汇总缺口、连接歧义、新源包和需人工复核事件 |
| `tools/anhui_web/build_maintainable_site.py` | 生成维护站模块、manifest、版本和哈希 |
| `tools/anhui_web/verify_maintainable_site.py` | 从磁盘重新读取并校验模块、数量、哈希和边界 |
| `tools/anhui_web/release.py` | 运行门禁、生成离线单文件、维护站和 ZIP |
| `tools/anhui_web/templates/maintainable-site.js` | 维护站壳、DataStore、路由、视图和交互 |
| `tools/anhui_web/templates/maintainable-site.css` | 维护站设计令牌、布局、表格、抽屉和响应式样式 |
| `tools/anhui_web/templates/maintainable-data.js` | 数据加载、缓存、失败状态和请求完整性校验 |
| `tests/test_data_contract.py` | 数据契约和稳定 ID 单元测试 |
| `tests/test_source_registry.py` | 来源登记与快照校验测试 |
| `tests/test_catalog_and_changes.py` | 专业目录、索引和跨年变化测试 |
| `tests/test_position_detail_contract.py` | 岗位详情、稳定 ID 和证据面板契约测试 |
| `tests/test_review_queue.py` | 缺口去重、复核状态和统计测试 |
| `tests/test_changes_and_comparability.py` | 跨年匹配、变化分类和分母可比性测试 |
| `tests/test_user_store_contract.cjs` | 筛选快照、收藏和导出安全测试 |
| `tests/test_datastore_contract.py` | manifest 驱动加载和模块哈希测试 |
| `tests/test_accessibility_and_export.py` | 分页、键盘语义和导出辅助函数测试 |
| `tests/test_release_v14.py` | v14.0 发布门禁和交接文档契约测试 |
| `tests/maintainable_browser_smoke.js` | 维护站三年切换、筛选、详情、收藏、审计与响应式测试 |
| `docs/数据更新操作手册.md` | 可复制执行的更新、复核、发布、回滚步骤 |
| `docs/数据字典.md` | 源字段、派生字段、状态、分母和空值解释 |
| `docs/长期维护网站架构方案_v2.md` | v14.0 架构和运维说明 |
| `deliverables/CHANGELOG.md` | 每个发布版本的模块、数量、边界和回滚点 |

## 2. Task 0：冻结 v13.4 基线和升级前差异

**Files:**
- Create: `tools/anhui_web/data/v13_4_baseline.json`
- Create: `tests/test_v14_upgrade_baseline.py`
- Modify: `docs/核验报告_v10.md` only if the current release references need a v14 transition note

**Interfaces:**
- Produces `load_baseline(path: Path) -> dict[str, object]`.
- Produces `snapshot_site(root: Path) -> dict[str, object]` with release, cycle counts, module hashes, gap count and unresolved count.

- [ ] **Step 1: Write the failing baseline test**

```python
def test_v13_4_baseline_contains_verified_cycle_totals():
    baseline = load_baseline(ROOT / "tools/anhui_web/data/v13_4_baseline.json")
    assert baseline["release"] == "v13.4"
    assert baseline["cycles"]["2024"] == {"posts": 10017, "recruits": 15331, "score_unresolved": 0}
    assert baseline["cycles"]["2025"] == {"posts": 10150, "recruits": 14721, "score_unresolved": 0}
    assert baseline["cycles"]["2026"] == {"posts": 8511, "recruits": 12006, "score_unresolved": 116}
    assert baseline["summary"] == {"posts": 28678, "recruits": 42058, "gaps": 8, "score_unresolved": 116}
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m unittest tests.test_v14_upgrade_baseline -v`  
Expected: FAIL because the baseline loader and v13.4 baseline file do not exist.

- [ ] **Step 3: Implement the baseline snapshot**

Write only verified values from `deliverables/maintainable/data/site-manifest.json` and `data/audit/three-year.json`; include the exact source paths, snapshot date, and module hashes. Do not copy the full job rows into the baseline.

- [ ] **Step 4: Run the test and inspect the diff**

Run: `python -m unittest tests.test_v14_upgrade_baseline -v`  
Expected: PASS; a read-only JSON diff must show only the new baseline artifact.

- [ ] **Step 5: Record the release gate**

Add the baseline command to the future v14 release checklist and state that any count delta must be explained by source additions, corrections, or an explicit evidence boundary.

## 3. Task 1：建立来源登记与数据契约

**Files:**
- Create: `tools/anhui_web/source_registry.py`
- Create: `tools/anhui_web/data_contract.py`
- Create: `tests/test_source_registry.py`
- Create: `tests/test_data_contract.py`
- Modify: `docs/数据字典.md`

**Interfaces:**
- `normalize_text(value: object) -> str`
- `make_record_id(cycle: str, row: dict[str, object]) -> str`
- `evidence(status: str, source_ref: str, source_locator: str, method: str, observed_at: str, note: str = "") -> dict[str, str]`
- `register_source(path: Path, cycle: str, source_type: str, publisher: str, observed_at: str) -> dict[str, object]`
- `validate_unknown_semantics(value: object, status: str) -> None`
- `ALLOWED_STATUSES: frozenset[str]`

- [ ] **Step 1: Write failing tests for statuses, unknowns, and stable IDs**

```python
def test_unknown_is_not_serialized_as_zero():
    with self.assertRaises(ValueError):
        validate_unknown_semantics(0, "unpublished_or_unavailable")

def test_same_normalized_row_has_same_record_id():
    row = {"exam": "省考", "city": "合肥", "code": "010009", "unit": "示例单位", "post_name": "综合管理"}
    assert make_record_id("2026", row) == make_record_id("2026", dict(row))

def test_source_registry_records_sha256_and_locator():
    with tempfile.NamedTemporaryFile("wb", delete=False) as handle:
        handle.write(b"source snapshot")
        temporary_path = Path(handle.name)
    record = register_source(temporary_path, "2026", "official_position_table", "发布机构", "2026-08-28")
    assert len(record["sha256"]) == 64
    assert record["cycle"] == "2026"
```

The test module imports `Path` and `tempfile`, and registers the temporary file for cleanup after the assertion; no repository fixture or external file is assumed.

- [ ] **Step 2: Run the focused tests**

Run: `python -m unittest tests.test_source_registry tests.test_data_contract -v`  
Expected: FAIL with missing module or missing functions.

- [ ] **Step 3: Implement the minimal contract**

Normalize only whitespace, full-width punctuation and code casing needed for matching; retain original values in a separate field. Reject invalid status/value combinations and reject a stable ID collision when the composite key is not unique. Register sources without copying secrets or external credentials.

- [ ] **Step 4: Add data dictionary entries**

Document `record_id`, `status`, `source_ref`, `source_locator`, `observed_at`, `method`, `value`, `null`, `derived` and `comparable`. Provide one example for a verified value, a source-bundle value, an unavailable value and an ambiguous join.

- [ ] **Step 5: Run focused and existing tests**

Run: `python -m unittest tests.test_source_registry tests.test_data_contract tests.test_data_quality_guards -v`  
Expected: all PASS; existing v13.4 data output remains byte-for-byte unchanged because the contract is additive at this stage.

## 4. Task 2：生成专业目录、真实筛选索引和可读候选

**Files:**
- Create: `tools/anhui_web/build_catalog.py`
- Create: `tests/test_catalog_and_changes.py`
- Modify: `tools/anhui_web/build_maintainable_site.py`
- Modify: `tools/anhui_web/templates/maintainable-site.js`
- Modify: `tools/anhui_web/templates/maintainable-site.css`

**Interfaces:**
- `build_catalog(cycle_payload: dict[str, object], cycle: str) -> dict[str, object]`
- `clean_major_label(raw: str) -> str | None`
- `build_facets(rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]`
- `filter_rows(rows: list[dict[str, object]], filters: dict[str, str]) -> list[dict[str, object]]`

- [ ] **Step 1: Write failing catalog tests**

```python
def test_catalog_filters_code_only_major_labels():
    catalog = build_catalog({"allMajors": {"rows": [{"zy": "0801048"}, {"zy": "软件工程"}, {"zy": ""}]}}, "2026")
    assert "软件工程" in catalog["majors"]
    assert all(any(ch.isalpha() or "\u4e00" <= ch <= "\u9fff" for ch in value) for value in catalog["majors"])
    assert "0801048" not in catalog["majors"]

def test_filter_intersection_uses_source_fields():
    rows = [{"zy": "软件工程", "city": "合肥", "exam": "省考", "lb": "行政执法"}]
    assert filter_rows(rows, {"major": "软件", "city": "合肥", "exam": "省考"}) == rows
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m unittest tests.test_catalog_and_changes -v`  
Expected: FAIL because the catalog builder and shared filter function do not exist.

- [ ] **Step 3: Implement catalog generation**

Generate only derived values: readable major candidates, city/exam/category options, normalized search tokens, counts by option and source field names. Keep the raw `zy` in `jobs.json`; write the derived catalog to `data/cycles/{cycle}/catalog.json` with source module hash and build method.

- [ ] **Step 4: Connect the UI to catalog data**

Replace duplicated candidate extraction in the maintainable frontend with `catalog.json` data. Display option counts, preserve free-text matching against raw `zy`, and show a compact “候选来自本周期岗位原文” note.

- [ ] **Step 5: Verify the focused interaction**

Run: `python -m unittest tests.test_catalog_and_changes -v` and `node tests/maintainable_browser_smoke.js`  
Expected: no pure-number major options; major + city + exam + category returns the intersection; reset restores all rows.

## 5. Task 3：来源/证据面板和岗位详情抽屉

**Files:**
- Create: `tools/anhui_web/build_position_index.py`
- Create: `tests/test_position_detail_contract.py`
- Modify: `tools/anhui_web/build_maintainable_site.py`
- Modify: `tools/anhui_web/templates/maintainable-site.js`
- Modify: `tools/anhui_web/templates/maintainable-site.css`
- Modify: `tests/maintainable_browser_smoke.js`

**Interfaces:**
- `build_position_index(rows: list[dict[str, object]], source_registry: dict[str, object]) -> dict[str, object]`
- `find_position(rows: list[dict[str, object]], record_id: str) -> dict[str, object] | None`
- `render_evidence_panel(position: dict[str, object], audit: dict[str, object]) -> str`

- [ ] **Step 1: Write failing detail tests**

```python
def test_position_index_has_stable_id_and_evidence_envelope():
    row = {"exam": "省考", "city": "合肥", "code": "010009", "unit": "示例单位", "post_name": "综合管理", "zy": "软件工程"}
    sources = {"2026": {"source_ref": "tools/anhui_web/data/all_majors_2026.json", "observed_at": "2026-08-28"}}
    index = build_position_index([row], sources)
    item = index["rows"][0]
    assert item["record_id"]
    assert item["source"]["status"] in {"verified", "source_bundle", "derived", "needs_review"}
    assert "source_ref" in item["source"]

def test_missing_source_value_explains_why():
    html = render_evidence_panel({"salary": None, "salary_status": "unpublished_or_unavailable"}, {})
    assert "未发布" in html or "未取得" in html
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m unittest tests.test_position_detail_contract -v`  
Expected: FAIL because there is no position index/evidence renderer.

- [ ] **Step 3: Build the index without changing source rows**

Create a compact index for search and detail lookup. Copy source values as-is into the detail payload and attach evidence references; do not fill absent fields. Use the existing stable ID convention where available and fail on collision.

- [ ] **Step 4: Add the detail drawer**

Add keyboard-openable row actions to search and ranking. The drawer shows conclusion fields, eligibility fields, raw source text, evidence source/locator/date/method, audit status, and adjacent-cycle match state. A missing value displays a reason label, not a blank or zero.

- [ ] **Step 5: Verify desktop, keyboard, and mobile**

Run: `node tests/maintainable_browser_smoke.js`  
Expected: open a position from search, view raw professional text and source path, close with Escape, reopen at 390 px as a bottom sheet, and preserve the active filter.

## 6. Task 4：三年变化、可比性和更新日志

**Files:**
- Create: `tools/anhui_web/build_changes.py`
- Create: `tools/anhui_web/data/cycles/2024/changes.json`
- Create: `tools/anhui_web/data/cycles/2025/changes.json`
- Create: `tools/anhui_web/data/cycles/2026/changes.json`
- Create: `tests/test_changes_and_comparability.py`
- Modify: `tools/anhui_web/build_maintainable_site.py`
- Modify: `tools/anhui_web/templates/maintainable-site.js`
- Modify: `docs/数据字典.md`
- Create: `deliverables/CHANGELOG.md`

**Interfaces:**
- `match_positions(base_rows: list[dict], target_rows: list[dict]) -> list[dict]`
- `classify_change(base: dict | None, target: dict | None, match_method: str) -> dict[str, object]`
- `comparable_metric(metric: str, base_meta: dict, target_meta: dict) -> dict[str, object]`

- [ ] **Step 1: Write failing matching tests**

```python
def test_exact_code_match_is_comparable():
    base = {"record_id": "2025:a", "code": "010009", "recruits": 1, "status": "verified"}
    target = {"record_id": "2026:a", "code": "010009", "recruits": 2, "status": "verified"}
    result = classify_change(base, target, "exact_code")
    assert result["status"] in {"unchanged", "revised"}
    assert result["comparable"] is True

def test_semantic_candidate_is_not_published_as_same_position():
    base = {"record_id": "2025:a", "code": "", "unit": "甲单位", "post_name": "综合管理"}
    target = {"record_id": "2026:a", "code": "", "unit": "甲单位", "post_name": "综合管理"}
    result = classify_change(base, target, "semantic_candidate")
    assert result["status"] == "needs_review"
    assert result["comparable"] is False

def test_different_denominator_blocks_percentage():
    result = comparable_metric("competition_rate", {"denominator": "paid"}, {"denominator": "registered"})
    assert result["comparable"] is False
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m unittest tests.test_changes_and_comparability -v`  
Expected: FAIL because no change builder or comparability rule exists.

- [ ] **Step 3: Implement conservative matching**

Use exact code first, then composite exact; output semantic candidates only to review. For each difference record `base_cycle`, `target_cycle`, `record_id`, `match_method`, changed fields, source refs, status and comparable flag.

- [ ] **Step 4: Build the three-year compare view**

Show summary trends only when metric denominators and evidence levels match. For position-level comparison show added, withdrawn, revised and needs review. Display source coverage warnings beside every chart/table.

- [ ] **Step 5: Add update log and verify**

Generate changelog entries from module diff results. Run focused tests and browser smoke; expected output includes a visible “可比性” label and no semantic candidate presented as an official same-position result.

## 7. Task 5：筛选快照、收藏和用户可复核路径

**Files:**
- Create: `tools/anhui_web/templates/maintainable-user-store.js`
- Create: `tests/test_user_store_contract.cjs`
- Modify: `tools/anhui_web/templates/maintainable-site.js`
- Modify: `tests/maintainable_browser_smoke.js`

**Interfaces:**
- `saveFilterSnapshot(snapshot: FilterSnapshot) -> void`
- `loadFilterSnapshots() -> FilterSnapshot[]`
- `savePosition(recordId: string, note: string = "") -> void`
- `removePosition(recordId: string) -> void`
- `serializeExport(rows: object[], format: "csv" | "json") -> string | Blob`

- [ ] **Step 1: Write failing storage tests**

```javascript
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { makeSnapshot, serializeExport } = require('../tools/anhui_web/templates/maintainable-user-store.js');

test('snapshot persists query, not full rows', () => {
  const snapshot = makeSnapshot('2026', { major: '软件工程', city: '合肥' }, 'recruits');
  assert.equal(Object.hasOwn(snapshot, 'rows'), false);
  assert.equal(snapshot.cycle, '2026');
});

test('CSV export has BOM and formula protection', () => {
  const csvText = serializeExport([{ unit: '=HYPERLINK("x")' }], 'csv');
  assert.equal(csvText.startsWith('\ufeff'), true);
  assert.equal(csvText.includes("'=HYPERLINK"), true);
});
```

The test module imports the CommonJS-compatible store helpers directly; the browser bundle exposes the same functions through `window.WanyuUserStore`.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `node --test tests/test_user_store_contract.cjs`  
Expected: FAIL because the v14 storage module does not exist.

- [ ] **Step 3: Implement versioned local storage**

Store only version, stable IDs, filters, notes and timestamps. Add migration from the current v13.4 saved-job key; invalid JSON or oversized state resets safely with a visible notice.

- [ ] **Step 4: Add the UI flow**

Add “保存筛选”“复制链接”“收藏岗位”“导出结果” actions. Show the active snapshot name and the exact cycle/version used. Do not claim a saved snapshot is live data after a new release without reloading the current module.

- [ ] **Step 5: Run browser acceptance**

Run: `node --test tests/test_user_store_contract.cjs` and `node tests/maintainable_browser_smoke.js`  
Expected: save a software-engineering filter, reload, return to the snapshot, favorite one stable ID, export, remove, and verify the independent search result remains correct.

## 8. Task 6：审计中心和复核队列

**Files:**
- Create: `tools/anhui_web/build_review_queue.py`
- Create: `tests/test_review_queue.py`
- Modify: `tools/anhui_web/build_maintainable_site.py`
- Modify: `tools/anhui_web/templates/maintainable-site.js`
- Modify: `tools/anhui_web/templates/maintainable-site.css`
- Modify: `tests/maintainable_browser_smoke.js`

**Interfaces:**
- `dedupe_audit_events(events: list[dict[str, object]]) -> list[dict[str, object]]`
- `build_review_queue(cycle_bundles: dict[str, dict], audit_index: dict) -> dict[str, object]`
- `summarize_review_queue(queue: dict) -> dict[str, int]`

- [ ] **Step 1: Write failing audit tests**

```python
def test_duplicate_detail_events_share_one_public_boundary():
    events = [
        {"cycle": "2026", "kind": "score_join", "evidence": "tools/anhui_web/data/score_lists.json", "title": "116 attachments", "scope": "score"},
        {"cycle": "2026", "kind": "score_join", "evidence": "tools/anhui_web/data/score_lists.json", "title": "116 attachments", "scope": "score"},
    ]
    result = dedupe_audit_events(events)
    assert len(result) == 1

def test_current_summary_preserves_unresolved_116():
    bundles = {"2024": {}, "2025": {}, "2026": {"score_unresolved": 116}}
    audit_snapshot = {"summary": {"public_boundary_count": 8}}
    queue = build_review_queue(bundles, audit_snapshot)
    assert queue["summary"]["unresolved_score_count"] == 116
    assert queue["summary"]["public_boundary_count"] == 8
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m unittest tests.test_review_queue -v`  
Expected: FAIL because review queue generation does not exist.

- [ ] **Step 3: Implement event identity and deduplication**

Event identity uses cycle, kind, evidence path, title and normalized affected scope. Preserve the original detailed event list in the audit module and compute a separate de-duplicated public count. Never discard high-severity details just to reduce the number.

- [ ] **Step 4: Redesign the audit center**

Add tabs or filters for all, high risk, unpublished, source bundle, ambiguous join, needs review and resolved. Each row exposes evidence path, affected module, UI treatment, last checked date and the condition that would resolve it. Add separate cards for public boundary count and unresolved score count so they cannot be conflated.

- [ ] **Step 5: Verify the known boundaries**

Run: `python -m unittest tests.test_review_queue -v && node tests/maintainable_browser_smoke.js`  
Expected: the current UI visibly shows 8 public boundaries and 116 unresolved score joins, while detailed 2024/2025/2026 rows remain accessible.

## 9. Task 7：前端设计系统与工作台重构

**Files:**
- Create: `tools/anhui_web/templates/maintainable-tokens.css`
- Modify: `tools/anhui_web/templates/maintainable-site.css`
- Modify: `tools/anhui_web/templates/maintainable-site.js`
- Modify: `tests/test_ui_v14.py`
- Modify: `tests/maintainable_browser_smoke.js`

**Interfaces:**
- CSS custom properties: `--bg-context`, `--bg-surface`, `--text-strong`, `--text-muted`, `--border-subtle`, `--accent-primary`, `--status-verified`, `--status-warning`, `--status-unknown`.
- JS view contract: `renderView(viewName: string, state: AppState) -> Promise<string>`.
- JS loading contract: `DataStore.load(cycle: string, module: ModuleName) -> Promise<ModulePayload>`.

- [ ] **Step 1: Write failing visual/markup tests**

```python
from tools.anhui_web.build_maintainable_site import _index_html

def test_v14_uses_light_workspace_tokens_and_semantic_status_classes():
    css = (ROOT / "tools/anhui_web/templates/maintainable-site.css").read_text(encoding="utf-8")
    assert "--bg-context" in css
    assert "status-verified" in css
    assert "#0b1220" not in css.lower()

def test_shell_has_single_cycle_context_and_audit_navigation():
    html = _index_html()
    assert html.count('data-maintain-view="overview"') == 1
    assert 'data-maintain-view="data_boundary"' in html
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m unittest tests.test_ui_v14 -v`  
Expected: FAIL until the v14 token layer and shell contract are present.

- [ ] **Step 3: Implement the light workspace token layer**

Use a shallow cold-white/blue-gray palette, thin borders and restrained shadows. Keep status colors semantically distinct. Avoid large dark header regions, oversized decorative cards and gratuitous animation.

- [ ] **Step 4: Implement layout states**

Create consistent loading, empty, error, stale and success states. Use a desktop sidebar, 64 px context bar, content max width 1440 px, filter toolbar, dense table and evidence drawer. On mobile use a filter sheet and bottom detail sheet.

- [ ] **Step 5: Run responsive browser checks**

Run: `node tests/maintainable_browser_smoke.js`  
Expected: 1440/768/390 screenshots show the same information hierarchy, no full-page horizontal overflow, clear keyboard focus, and no deep navy redesign regression.

## 10. Task 8：DataStore、缓存、失败恢复和模块化加载

**Files:**
- Create: `tools/anhui_web/templates/maintainable-data.js`
- Modify: `tools/anhui_web/templates/maintainable-site.js`
- Modify: `tools/anhui_web/build_maintainable_site.py`
- Modify: `tools/anhui_web/verify_maintainable_site.py`
- Create: `tests/test_datastore_contract.py`
- Modify: `tests/maintainable_browser_smoke.js`

**Interfaces:**
- `class DataStore { load(cycle: string, module: string): Promise<object>; clear(cycle?: string, module?: string): void; }`
- `verifyModulePayload(module: string, payload: object, manifestEntry: object) -> None`
- `modulePath(manifest: dict, cycle: str, module: str) -> str`

- [ ] **Step 1: Write failing loader tests**

```python
def test_loader_uses_manifest_module_path_and_not_hardcoded_rows_path():
    manifest = {"cycles": [{"cycle": "2026", "modules": {"catalog": {"data": "data/cycles/2026/catalog.json"}}}]}
    assert module_path(manifest, "2026", "catalog") == "data/cycles/2026/catalog.json"

def test_loader_rejects_hash_mismatch():
    payload = {"schema": "wanyu-maintainable-module/v1", "cycle": "2026"}
    with self.assertRaises(ValueError):
        verify_module_payload("jobs", payload, {"sha256": "0" * 64})
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m unittest tests.test_datastore_contract -v`  
Expected: FAIL because the shared loader and module verifier do not exist.

- [ ] **Step 3: Implement manifest-driven loading**

Resolve every module path from `site-manifest.json`; cache by cycle/module/hash; validate response shape and hash metadata; retry once; on failure show the exact module, version and retry action. Never silently fall back to a different cycle.

- [ ] **Step 4: Update the builder and disk verifier**

Add module entries for catalog, scores and changes. Verify that overview/audit/catalog contain no full job row payload, that jobs row counts equal manifest counts, and that all module hashes match disk.

- [ ] **Step 5: Verify file:// and HTTP behavior separately**

Run the single-file smoke against `file://` and the maintainable smoke through `python tools/anhui_web/serve_maintainable.py --port 8765`. Expected: the single file opens without fetch; the maintainable site loads JSON only under HTTP and gives a helpful message if opened directly from `file://`.

## 11. Task 9：性能、无障碍和数据导出质量

**Files:**
- Modify: `tools/anhui_web/templates/maintainable-site.js`
- Modify: `tools/anhui_web/templates/maintainable-site.css`
- Create: `tests/test_accessibility_and_export.py`
- Modify: `tests/maintainable_browser_smoke.js`

**Interfaces:**
- `paginateRows(rows: list[dict], page: int, page_size: int = 120) -> Page`
- `escapeCsvCell(value: object) -> str`
- `announce(message: str) -> None`

- [ ] **Step 1: Write failing tests**

```python
def test_pagination_never_renders_more_than_page_size_rows():
    page = paginate_rows([{}] * 10000, 1, 120)
    assert len(page["rows"]) == 120

def test_export_escapes_formula_prefix():
    assert escape_csv_cell("+SUM(A1:A2)").startswith("'+")
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_accessibility_and_export -v`  
Expected: FAIL until the shared pagination and export helpers exist.

- [ ] **Step 3: Implement bounded rendering**

Render at most 120 rows per page in the first release; show total results and page position. Keep table column metadata so a future windowed renderer can replace pagination without changing the data API.

- [ ] **Step 4: Implement accessibility feedback**

Add semantic headings, labels, `aria-live` result counts, focus return after drawer close, Escape handling, visible focus rings, sufficient contrast, and reduced-motion rules.

- [ ] **Step 5: Verify large result sets and exports**

Run: `node tests/maintainable_browser_smoke.js` plus the CSV/JSON unit tests. Expected: no long blocking render, correct row totals, safe CSV, and keyboard-only completion of the primary journey.

## 12. Task 10：发布门禁、更新手册和回滚包

**Files:**
- Modify: `tools/anhui_web/release.py`
- Modify: `tools/anhui_web/verify_maintainable_site.py`
- Modify: `deliverables/MANIFEST.txt`
- Create: `docs/长期维护网站架构方案_v2.md`
- Modify: `docs/数据更新操作手册.md`
- Create: `deliverables/CHANGELOG.md`
- Modify: `deliverables/HANDOFF.md`
- Modify: `tests/test_release_v14.py`

**Interfaces:**
- `run_v14_gates(root: Path) -> ReleaseReport`
- `package_zip(output_dir: Path, version: str) -> Path`
- `rollback_module(release_dir: Path, cycle: str, module: str, previous_hash: str) -> None`

- [ ] **Step 1: Write the release gate test**

```python
def test_release_gate_requires_audit_disk_and_package_verifier():
    source = (ROOT / "tools/anhui_web/release.py").read_text(encoding="utf-8")
    assert "verify_maintainable_site.py" in source
    assert "package" in source
    assert "three_year" in source
```

- [ ] **Step 2: Run the focused release test and verify failure**

Run: `python -m unittest tests.test_release_v14 -v`  
Expected: FAIL until v14.0 gates and documents are wired.

- [ ] **Step 3: Add the full gate sequence**

Run in order: Python unit tests → frozen baseline → three-year audit → single-file build/postbuild → Node/core smoke → maintainable build → maintainable disk verifier → maintainable browser smoke → ZIP package verifier. Stop on the first failure and do not create a release label that says passed.

- [ ] **Step 4: Add module-level rollback**

Store previous release paths and hashes in `deliverables/releases/{version}/manifest.json`. Implement a dry-run rollback that checks the target cycle/module is inside the release directory, restores the selected module, rebuilds manifest, and reruns disk verification.

- [ ] **Step 5: Update handoff documents**

Document the two entry points, local HTTP command, v14.0 module map, exact current counts, known boundaries, update sequence, rollback command and verification evidence. State that no Git commit exists in this workspace.

- [ ] **Step 6: Run the release candidate**

Run: `python tools/anhui_web/release.py --zip`  
Expected: all gates pass, `deliverables/皖域择岗总览.html` remains available, `deliverables/maintainable/` contains the new modules, and the ZIP package contains the verifier, audit index, changelog and handoff.

## 13. Task 11：最终端到端验收

**Files:**
- Modify: `tests/maintainable_browser_smoke.js`
- Create: `tests/artifacts/maintainable-v14/`
- Create: `docs/三年数据真实性与完整性审计_v14.md`

**Interfaces:**
- `run_acceptance_matrix() -> dict[str, object]`
- `assert_no_remote_assets(html: str) -> None`

- [ ] **Step 1: Run data reconciliation**

Run: `python tools/anhui_web/verify_maintainable_site.py deliverables/maintainable`  
Expected: all modules exist, hashes match manifest, row/recruit totals match, and audit summary is 28,678 / 42,058 / 8 / 116.

- [ ] **Step 2: Run formal browser paths**

Run: `node tests/maintainable_browser_smoke.js` and the existing single-file v12 walkthrough. Cover overview, cycle switch, major/city/exam/category intersection, detail evidence drawer, compare comparability, saved filter, favorite, audit queue, reset, 390/768/1440 widths and file:// fallback.

- [ ] **Step 3: Inspect screenshots and content**

Inspect the overview, ranking, detail, compare, audit and mobile artifacts. Reject any screen where a missing value looks like zero, the main area becomes dark, filter state is invisible, source evidence is hidden behind decoration, or text is truncated without an accessible full view.

- [ ] **Step 4: Verify package contents**

Run: `$zip = Get-ChildItem "$env:USERPROFILE/Desktop/皖域择岗档案_网页产品化升级版_*_v14.0.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1; python tools/anhui_web/verify_single_file_v12.py package --zip $zip.FullName`  
Expected: package verifier passes; manifest hashes inside the ZIP match the files inside the ZIP, not only the workspace.

- [ ] **Step 5: Write the final audit and handoff**

Record actual commands, pass counts, output paths, current public boundaries, unresolved score joins, known limitations and rollback entry. Do not write “全部官方数据已补齐” unless a future official source check actually proves it.

## 14. Release definition of done

- [ ] One unified web entry switches 2024/2025/2026.
- [ ] External data modules are manifest-driven; HTML does not contain the full maintainable job payload.
- [ ] Major candidates are readable and no pure-code option is shown.
- [ ] Ranking and search support real field combinations and preserve raw source text.
- [ ] Position detail exposes source path, locator, date, method and evidence state.
- [ ] Three-year comparison distinguishes comparable, background-only and non-comparable metrics.
- [ ] Audit center separates public boundary count from unresolved score count and keeps detailed events.
- [ ] Current known 2026 unresolved 116 remains safe-null and visible.
- [ ] Update log, source registry, data dictionary, release gate and rollback instructions exist.
- [ ] Light, responsive, keyboard-usable UI passes 390/768/1440 browser checks.
- [ ] Python, Node, browser, disk and package verification all pass.
- [ ] Final ZIP, offline HTML, maintainable site, audit report and handoff paths are recorded.
