"""一键发布（v17.8.6）：staging 构建 → 验证 → 原子提升（共享流水线）。

正式链全部经由 tools/anhui_web/release_pipeline.py 编排（单一真源）：
  测试 → precheck（git 干净）→ verify_sources（锁只读）→ validate_canonical
  → audit --check（three_year_audit 工件只读复核，不重生成）→ staging 构建
  → verify_maintainable_site.py 磁盘校验 + 2026 事实闸 + perf_budget.py 预算
  → 三脚本浏览器烟测（tests/maintainable_browser_smoke.js、
  tests/major_city_browser_smoke.cjs、tests/ui_upgrade_browser_smoke.cjs，
  经 WANYU_SITE_DIR 指向 staging）→ 发布资料 manifest + SHA256SUMS
  → 原子提升（网站→网站.previous，提升后验证失败自动回滚）。
历史版本记录（v14.4 / v16.2.1）不可变；本入口只推进当前 release 标记。

单文件 皖域择岗总览.html 已降级为"遗留存档工件"：只有显式 --legacy-single-file
才会重建（build_score_lists + 审计重生成 + build_pages + 单文件校验），
它不是发布门禁、不参与 validation_status，正式发布无需它存在。

用法：
    python tools/anhui_web/release.py                  # 测试 + staging + 原子提升
    python tools/anhui_web/release.py --legacy-single-file   # 追加遗留单文件存档链
    python tools/anhui_web/release.py --zip            # 追加打包发布 zip
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

# D(2026-09-05): 版本唯一真源 = 项目源码/release.json
BUILD_VERSION = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))["release"]

from tools.anhui_web import release_pipeline as _pipeline  # noqa: E402
from tools.anhui_web.release_pipeline import (  # noqa: E402
    BROWSER_VALIDATION,
    WORKSPACE,
    _render_sw_template,
    run_browser_smoke,
    run_pipeline,
    verify_template_asset_parity,
)

# 正式链测试模块（--legacy-single-file 遗留链的测试在 tests/test_single_file_legacy.py，
# 不进入本清单；新增正式测试模块时同步登记）。
FORMAL_TEST_MODULES = [
    "tests.test_anhui_web", "tests.test_three_year_audit", "tests.test_data_quality_guards",
    "tests.test_ui_v13", "tests.test_v14_upgrade_baseline", "tests.test_data_contract", "tests.test_source_registry",
    "tests.test_catalog_and_changes", "tests.test_position_detail_contract", "tests.test_changes_and_comparability",
    "tests.test_review_queue", "tests.test_scores_contract", "tests.test_datastore_contract",
    "tests.test_accessibility_and_export", "tests.test_ui_v14", "tests.test_ui_v15", "tests.test_map_restore", "tests.test_maintainable_site", "tests.test_release_v14",
    "tests.test_v17_salary_and_motion",
]

# 单文件链遗留工件（--legacy-single-file 才会生成；非正式发布物）
LEGACY_SINGLE_HTML = "皖域择岗总览.html"
ZIP_ROOT_FILES = [
    "build.ps1", "test.ps1", "design-qa.md", "HANDOFF.md",
    "archive/交接文档_皖域择岗总包v12.1_20260831.md",
    "archive/00_计划任务_全站数据核验与功能清零_v10.md",
    "requirements.txt", "省考备注核查结果.json",
]
ZIP_DIRS = ["source_docs", "source_data", "design_refs", "docs", "deliverables", "tools/anhui_web", "tests"]
ZIP_SKIP_PARTS = {"__pycache__", "node_modules", ".pytest_cache"}


def run_tests() -> None:
    print("== 正式链 Python 单测 ==")
    subprocess.run([sys.executable, "-m", "unittest", *FORMAL_TEST_MODULES], cwd=ROOT, check=True)
    print("== node 纯函数单测 ==")
    subprocess.run(["node", "--test", "tests/test_wanyu_core.cjs"], cwd=ROOT, check=True)
    subprocess.run(["node", "--test", "tests/test_major_city_index.cjs"], cwd=ROOT, check=True)
    subprocess.run(["node", "tests/test_datastore_contract.cjs"], cwd=ROOT, check=True)
    subprocess.run(["node", "--test", "tests/test_user_store_contract.cjs"], cwd=ROOT, check=True)


def release_pipeline_summary(skip_tests: bool) -> dict:
    return {
        "status": "skipped_dev" if skip_tests else "pass",
        "python_modules": len(FORMAL_TEST_MODULES),
        "node_suites": 4,
        "browser_smoke_scripts": 3,
    }


def legacy_single_file_chain() -> None:
    """遗留单文件存档链（v17.8.6 方案 A）：显式请求才运行，非发布门禁。"""
    print("== [遗留链] 成绩清单构建 ==")
    for cycle in ("2026", "2025", "2024"):
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "anhui_web" / "build_score_lists.py"), "--cycle", cycle],
            cwd=ROOT,
            check=True,
        )
    print("== [遗留链] 三周期数据审计重生成（仅遗留链允许写 three_year_audit 工件）==")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "anhui_web" / "audit_three_years.py"),
            "--root", str(ROOT),
            "--output-json", str(ROOT / "tools" / "anhui_web" / "data" / "three_year_audit.json"),
            "--report", str(ROOT / "docs" / "三年数据真实性与完整性审计_v14.md"),
        ],
        cwd=ROOT,
        check=True,
    )
    print("== [遗留链] 单文件页面构建 ==")
    deliverables = ROOT / "deliverables"
    deliverables.mkdir(exist_ok=True)
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "anhui_web" / "build_pages.py"), "--output-dir", str(deliverables)],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "anhui_web" / "verify_single_file_v12.py"), "postbuild", "--html", str(deliverables / LEGACY_SINGLE_HTML)],
        cwd=ROOT,
        check=True,
    )
    print(f"[遗留链] 存档工件构建完成：{deliverables / LEGACY_SINGLE_HTML}（非正式发布物，不参与 validation_status）")


def package_zip() -> Path:
    stamp = _dt.date.today().strftime("%Y%m%d")
    if not (ROOT / "source_docs").is_dir():
        print("[警告] source_docs/ 缺失：本包在新机器上将无法重建，请补齐两份源 Word 后再分发。")
    output_dir = Path.home() / "Desktop"
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"皖域择岗档案_网页产品化升级版_{stamp}_{BUILD_VERSION}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in ZIP_ROOT_FILES:
            path = ROOT / name
            if path.is_file():
                bundle.write(path, name)
        for directory in ZIP_DIRS:
            base = ROOT / directory
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*")):
                if path.is_file() and not (ZIP_SKIP_PARTS & set(path.parts)):
                    bundle.write(path, path.relative_to(ROOT).as_posix())
    print("zip →", zip_path, f"({zip_path.stat().st_size / 1e6:.1f} MB)")
    if (ROOT / "deliverables" / LEGACY_SINGLE_HTML).is_file():
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "anhui_web" / "verify_single_file_v12.py"), "package", "--zip", str(zip_path)],
            cwd=ROOT,
            check=True,
        )
    return zip_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试 + staging 构建 + 验证 + 原子提升（正式链）；单文件链已降级为 --legacy-single-file")
    parser.add_argument("--zip", action="store_true", help="追加打包发布 zip")
    parser.add_argument("--skip-tests", action="store_true", help="跳过测试（调试用）")
    parser.add_argument("--allow-dirty", action="store_true", help="容忍脏 git 树（必须同时 WANYU_DEV=1）")
    parser.add_argument("--legacy-single-file", action="store_true",
                        help="追加遗留单文件存档链（非发布门禁；产物为 deliverables/皖域择岗总览.html）")
    parser.add_argument("--allow-missing-browser", action="store_true",
                        help="显式豁免浏览器烟测（release 记录 validation_status=degraded_validation）")
    arguments = parser.parse_args()
    _pipeline.ALLOW_MISSING_BROWSER = bool(arguments.allow_missing_browser)
    if arguments.skip_tests:
        # RC3-P1：--skip-tests 仅限 dev/debug（WANYU_DEV=1）；正式 release 拒绝。
        import os as _os

        if _os.environ.get("WANYU_DEV", "").strip() != "1":
            raise SystemExit("RC3-P1：正式 release 禁止 --skip-tests（dev/debug 请设 WANYU_DEV=1）")
        print("[dev] WANYU_DEV=1：--skip-tests 生效（release 记录将标注 tests=skipped_dev，tag_allowed=false）")
    if not arguments.skip_tests:
        run_tests()
    summary = run_pipeline(
        WORKSPACE / ".release-staging",
        promote=True,
        allow_dirty=bool(arguments.allow_dirty),
        tests_summary=release_pipeline_summary(bool(arguments.skip_tests)),
    )
    print("== 发布完成 ==")
    print(f"release={BUILD_VERSION} validation={BROWSER_VALIDATION['status']} staging_promoted=True")
    if arguments.legacy_single_file:
        legacy_single_file_chain()
    if arguments.zip:
        package_zip()
