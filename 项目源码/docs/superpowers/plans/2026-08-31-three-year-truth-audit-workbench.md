# 三年数据真实性审计与统一工作台实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints. This workspace is not a Git repository; replace commit steps with file-level verification and preserve existing user changes.

**Goal:** 在不伪造或覆盖源事实的前提下，为 2024–2026 安徽公考数据建立可复跑的真实性/完整性审计，并将三年数据整理为统一的离线对照工作台。

**Architecture:** 新增只读审计器生成机器可读摘要和 Markdown 报告；构建器把摘要注入 2026 主站并为历史周期页增加统一状态入口；前端通过新的 `cycle_compare` 视图消费摘要，不重新计算岗位主数据。构建脚本在发布前运行审计，浏览器 smoke 覆盖三年视图和周期跳转。

**Tech Stack:** Python 3 标准库、现有 JSON/HTML 构建器、原生 JavaScript/CSS、Node test、现有浏览器 smoke。

## Global Constraints

- 不把缺失值填成 0，不猜测无法唯一匹配的成绩，不改变已有岗位事实和源 JSON。
- 只允许证据状态：`verified`、`source_bundle`、`unpublished_or_unavailable`、`ambiguous_join`。
- 保持 file:// 离线可用；不新增远程脚本、样式、字体或运行时依赖。
- 2024/2025/2026 岗位/招录基线分别为 10,017/15,331、10,150/14,721、8,511/12,006。
- 构建和审计失败必须返回非零退出码；已知官方未发布/未取得项应记录为缺口而不是让构建失败。
- 工作区无 Git 元数据，不执行提交、重置或覆盖用户无关修改。

## File Map

- Create: `tools/anhui_web/audit_three_years.py` — 三周期源 JSON、页面 HTML 和 manifest 的只读审计器。
- Create: `tools/anhui_web/data/three_year_audit.json` — 页面消费的三年摘要。
- Create: `tests/test_three_year_audit.py` — 审计器单元测试和摘要结构断言。
- Create: `tests/browser_smoke_v11.js` — 三年对照视图与状态条浏览器验收。
- Create: `docs/三年数据真实性与完整性审计_v11.md` — 运行生成的证据报告。
- Create: `docs/superpowers/specs/2026-08-31-three-year-truth-audit-workbench-design.md` — 已确认的设计规格。
- Modify: `tools/anhui_web/build_pages.py` — 加载摘要、注入 `threeYearAudit`、增加 `cycle_compare` 视图与周期状态入口。
- Modify: `tools/anhui_web/templates/master.js` — 渲染三年对照视图的结构化数据。
- Modify: `tools/anhui_web/templates/master.css` — 新视图、状态矩阵、趋势条和移动端布局。
- Modify: `tools/anhui_web/release.py`、`build.ps1` — 发布前运行审计并同步三周期构建。
- Modify: `tests/test_anhui_web.py`、`docs/数据字典.md`、`HANDOFF.md`、`tools/anhui_web/data/manifest.json` — 回归断言和交接文档同步。

### Task 1: Build the three-year audit profile

**Files:**
- Create: `tools/anhui_web/audit_three_years.py`
- Create: `tools/anhui_web/data/three_year_audit.json`
- Create: `tests/test_three_year_audit.py`
- Create: `docs/三年数据真实性与完整性审计_v11.md`

**Interfaces:**
- `audit_three_years.py` exposes `build_audit(root: Path, output_dir: Path) -> dict` and `write_report(summary: dict, path: Path) -> None`.
- Summary shape: `{"version": 1, "generated_on": "YYYY-MM-DD", "cycles": [{"cycle": "2024", "posts": int, "recruits": int, "exams": {}, "coverage": {}, "statuses": {}, "gaps": []}], "checks": {"passed": int, "failed": int}}`.
- `python tools/anhui_web/audit_three_years.py --root . --output-json tools/anhui_web/data/three_year_audit.json --report docs/三年数据真实性与完整性审计_v11.md` returns 0 when all structural and cross-layer checks pass.

- [x] **Step 1: Write failing tests for the audit contract.**

```python
def test_summary_has_three_cycles_and_baselines():
    summary = audit_three_years.build_audit(ROOT, OUT)
    assert [item["cycle"] for item in summary["cycles"]] == ["2024", "2025", "2026"]
    assert [(item["posts"], item["recruits"]) for item in summary["cycles"]] == [
        (10017, 15331), (10150, 14721), (8511, 12006)
    ]

def test_statuses_use_only_explicit_evidence_states():
    summary = audit_three_years.build_audit(ROOT, OUT)
    allowed = {"verified", "source_bundle", "unpublished_or_unavailable", "ambiguous_join"}
    assert set(summary["status_definitions"]) == allowed
    assert all(set(item["statuses"]) <= allowed for item in summary["cycles"])

def test_known_unresolved_2026_join_is_not_filled():
    summary = audit_three_years.build_audit(ROOT, OUT)
    current = next(item for item in summary["cycles"] if item["cycle"] == "2026")
    assert current["coverage"]["score_unresolved"] == 116
    assert any(item["kind"] == "ambiguous_join" for item in current["gaps"])
```

- [x] **Step 2: Run the focused tests and confirm they fail for the missing module/contract.**

Run: `python -m unittest tests.test_three_year_audit -v`

Expected: FAIL because `audit_three_years.py` and the summary contract do not exist yet.

- [x] **Step 3: Implement source/profile readers.**

Use `json.loads(Path.read_text(encoding="utf-8"))`; derive 2026 from `tools/anhui_web/data/all_majors_2026.json` and `manifest.json`, derive 2024/2025 from `data/cycles/{cycle}/all_majors_{cycle}.json` and `cycle.json`, and never mutate loaded rows. Count missing values after treating `None` and whitespace-only strings as empty. Keep score coverage and unresolved counts from each cycle's `score_lists.json`.

- [x] **Step 4: Implement the three-layer reconciliation.**

Parse the `allMajors` JSON object embedded in each deliverable HTML using the existing page-data marker; compare row count, summed `num`, exam counts, and cycle metadata against the standard JSON. Emit a failed check for missing files, changed baseline totals, illegal evidence state, or page/JSON mismatch. Emit a documented gap for known `cycle.json.gaps`, manifest `open_items`, empty official fields, and ambiguous score keys.

- [x] **Step 5: Generate the machine-readable summary and Markdown report.**

The report must include dataset grain, row/column completeness, duplicate candidate keys, per-exam score coverage, source paths, checks passed/failed, evidence-state definitions, known gaps, analytical risk, and remediation. The report conclusion must say whether the source bundle is internally reconciled; it must not claim universal official completeness.

- [x] **Step 6: Run the focused audit tests and command.**

Run: `python -m unittest tests.test_three_year_audit -v`

Expected: PASS, followed by `python tools/anhui_web/audit_three_years.py --root . --output-json tools/anhui_web/data/three_year_audit.json --report docs/三年数据真实性与完整性审计_v11.md` with exit code 0 and an explicit unresolved/gap inventory.

### Task 2: Inject the audit summary and add the three-year view

**Files:**
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tools/anhui_web/templates/master.js`
- Modify: `tools/anhui_web/templates/master.css`
- Modify: `tests/test_anhui_web.py`

**Interfaces:**
- `build_pages.py` adds `_load_three_year_audit() -> dict` with an empty-safe failure only for legacy imports; the release path must run the audit first.
- Master `PAGE_DATA` includes `threeYearAudit` equal to the generated summary.
- The HTML contains exactly one `data-view="cycle_compare"` view and a navigation target `data-view-link="cycle_compare"`.

- [x] **Step 1: Add failing static tests for injection and view markers.**

```python
def test_master_contains_three_year_audit_view():
    page = (ROOT / "deliverables" / "皖域择岗总览.html").read_text(encoding="utf-8")
    assert 'data-view="cycle_compare"' in page
    assert 'data-view-link="cycle_compare"' in page
    assert '"threeYearAudit"' in page
```

- [x] **Step 2: Run the new test and confirm the current page fails it.**

Run: `python -m unittest tests.test_anhui_web.TestThreeYearWorkbench -v`

Expected: FAIL because v10 has no three-year view or injected audit summary.

- [x] **Step 3: Add builder data injection and master navigation.**

Load the summary once in `_build_master_site`, pass it to `_master_context`, add `("cycle_compare", "三年对照")` to `_master_nav`, and add a three-year state link to `_cycle_nav`. Keep all existing routes and compatibility aliases unchanged.

- [x] **Step 4: Add the static view shell.**

Create `_master_cycle_compare_content(audit: dict) -> str` that renders three year cards, a trend comparison table, an evidence-status matrix, a gap list, and links to `2024/皖域择岗总览.html`, `2025/皖域择岗总览.html`, and `#overview` for 2026. Values must come from `audit` and must display `—` for absent metrics.

- [x] **Step 5: Implement client rendering and view behavior.**

In `master.js`, render only the summary supplied by `window.productData.threeYearAudit`, add `cycle_compare` to the recognized view set, and preserve hash navigation. Do not calculate or overwrite job totals in JavaScript.

- [x] **Step 6: Add visual styles and responsive rules.**

In `master.css`, style the comparison as an archival timeline: neutral blue for verified/source-bundle, amber for unpublished/unavailable, muted red for ambiguous join; use CSS grid that collapses to one column at `max-width: 760px`; keep navigation labels on one line; set focus-visible states and reduced-motion behavior.

- [x] **Step 7: Run focused Python tests and syntax checks.**

Run: `python -m unittest tests.test_anhui_web.TestThreeYearWorkbench -v` and the existing JS syntax checks used by `tests/test_anhui_web.py`.

Expected: PASS after rebuilding pages in Task 4; before rebuild, only source/template checks may pass.

### Task 3: Normalize cycle status and documentation

**Files:**
- Modify: `tools/anhui_web/release.py`
- Modify: `build.ps1`
- Modify: `tools/anhui_web/data/manifest.json`
- Modify: `docs/数据字典.md`
- Modify: `HANDOFF.md`

**Interfaces:**
- Release command runs audit before any page write and includes `three_year_audit.json` and `docs/三年数据真实性与完整性审计_v11.md` in the package.
- Manifest release advances to `v11.0` only after the audit and browser checks pass; it records the audit report and summary paths, not fabricated official claims.

- [x] **Step 1: Add a release preflight assertion.**

Run the audit subprocess with the same Python interpreter used by release; if return code is nonzero, raise `RuntimeError` before `build_pages.py` is called. Keep the existing output directory safety and source-data inclusion rules.

- [x] **Step 2: Update the Windows build entrypoint.**

Add the audit command before score-list/page builds in `build.ps1`, retaining Windows PowerShell 5 compatibility and ASCII-only syntax.

- [x] **Step 3: Update evidence documentation.**

Document the four evidence states, three-year baselines, audit command, allowed empty score semantics, and unresolved join semantics in `docs/数据字典.md`; update `HANDOFF.md` with the new entrypoint and explicit remaining gaps.

- [x] **Step 4: Update manifest only after measured output exists.**

Set the release version/date and add `three_year_audit` fields using the generated report values. Preserve current open items and cycle gaps; do not close them by wording changes.

### Task 4: Rebuild and verify the delivered pages

**Files:**
- Modify: `deliverables/` generated HTML only through build scripts
- Create: `tests/artifacts/v11-cycle-compare-desktop.png`, `tests/artifacts/v11-cycle-compare-mobile.png`, and additional smoke screenshots
- Create/modify: `tests/browser_smoke_v11.js`

- [x] **Step 1: Rebuild all three cycles from the audited source bundle.**

Run:

```powershell
python tools/anhui_web/audit_three_years.py --root . --output-json tools/anhui_web/data/three_year_audit.json --report docs/三年数据真实性与完整性审计_v11.md
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
python tools/anhui_web/build_pages.py --cycle 2025 --output-dir deliverables
python tools/anhui_web/build_pages.py --cycle 2024 --output-dir deliverables
```

Expected: all commands exit 0; generated pages include the audit view and preserve the three baseline totals.

- [x] **Step 2: Add browser checks before running them.**

The smoke script must open the main page via `file://`, click `#cycle_compare`, verify the three year cards, click 2025 and 2024 links, open the gap/status panel, and repeat at 390×844. Fail on console/page errors, missing view markers, external asset URLs, or horizontal overflow.

- [x] **Step 3: Run the complete verification suite.**

Run: `python -m unittest tests.test_three_year_audit tests.test_anhui_web -v`; `node --test tests/test_wanyu_core.cjs`; `python tools/anhui_web/snapshot_baseline.py --check`; `python tools/anhui_web/verify_full_v10.py --report docs/核验报告_v10.md`; `node tests/browser_smoke_v11.js`; `node tests/browser_smoke_v10.js`; `node tests/audit_v9.js`.

Expected: all existing tests and new checks pass; page errors are zero; baseline diff is either zero or has a written audit explanation.

- [x] **Step 4: Repackage and post-check the handoff archive.**

Run the existing release packaging command after tests. Confirm the ZIP contains the three cycle pages, source bundle, audit script, summary JSON, report, docs and screenshots; scan filenames for secrets; record archive path, entry count and size in `HANDOFF.md`.

## Execution Notes

- The project is not a Git repository, so “commit” checkpoints in generic Superpowers instructions are replaced by the file map, test output, report, and archive checks above.
- If a test exposes a real mismatch, stop at that task, inspect the exact source/page/key evidence, and patch only the smallest in-scope issue. Do not relax a failing baseline assertion to force green.
