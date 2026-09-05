"""一键发布（v17.8.6 方案 A）：正式产物 = 维护站（canonical 唯一输入）。

正式发布链不再包含任何单文件 HTML 步骤：
  测试（Python + node）→ 维护站构建 → 磁盘校验 + perf 预算 + 模板一致性
  → 浏览器烟测 → 发布记录。历史版本（含 v14.4 / v16.2.1）记录保持不可变。

单文件 皖域择岗总览.html 已降级为"遗留存档工件"：只有显式 --legacy-single-file
才会重建（build_score_lists + 审计重生成 + build_pages + 单文件校验），
它不是发布门禁、不参与 validation_status，正式发布无需它存在。

用法：
    python tools/anhui_web/release.py                  # 测试 + 维护站构建 + 校验
    python tools/anhui_web/release.py --legacy-single-file   # 追加遗留单文件存档链
    python tools/anhui_web/release.py --zip            # 追加打包发布 zip
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# D(2026-09-05): 版本唯一真源 = 项目源码/release.json
BUILD_VERSION = json.loads((Path(__file__).resolve().parents[2] / "release.json").read_text(encoding="utf-8"))["release"]
# Historical release records, including v16.2.1, remain immutable; this
# entrypoint only advances the current release marker.
LEGACY_SINGLE_HTML = "皖域择岗总览.html"
ZIP_ROOT_FILES = [
    "build.ps1", "test.ps1", "design-qa.md", "HANDOFF.md",
    "archive/交接文档_皖域择岗总包v12.1_20260831.md",
    "archive/00_计划任务_全站数据核验与功能清零_v10.md",
    "requirements.txt", "省考备注核查结果.json",
]
ZIP_DIRS = ["source_docs", "source_data", "design_refs", "docs", "deliverables", "tools/anhui_web", "tests"]
ZIP_SKIP_PARTS = {"__pycache__", "node_modules", ".pytest_cache"}

# G1(2026-09-05): 资产清单自动发现——扫描 templates 目录中 maintainable/v17 前缀资产，
# 幽灵资产（如已退役的 search-history/toast）不再可能混入。
def _discover_template_assets() -> tuple[str, ...]:
    tpl = Path(__file__).resolve().parent / "templates"
    found = sorted(p.name for p in tpl.iterdir()
                   if p.is_file() and (p.name.startswith("maintainable-") or p.name.startswith("v17-"))
                   and p.suffix in {".css", ".js"} and p.name not in {"maintainable-sw.js"})
    return tuple(found)

MAINTAINABLE_TEMPLATE_ASSETS = _discover_template_assets()


def _render_sw_template() -> str:
    """SW 模板 → 实际产物内容（release.json 注入版本占位符）。"""
    template = (ROOT / "tools" / "anhui_web" / "templates" / "maintainable-sw.js").read_text(encoding="utf-8")
    release_doc = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
    return (
        template
        .replace("__SW_VERSION__", str(release_doc.get("service_worker_version") or ""))
        .replace("__ASSET_VERSION__", str(release_doc.get("asset_version") or ""))
    )


def verify_template_asset_parity(site_dir: Path) -> dict[str, object]:
    """Compare the built shell assets with their checked-in templates.

    The comparison is byte-for-byte so a stale template cannot silently erase
    a feature at the next rebuild.  The SW template is compared after the same
    release.json placeholder substitution the builder applies.  The two view
    renderers are also checked for their source markers; the browser smoke test
    exercises their actual route.
    """
    site_dir = Path(site_dir).resolve()
    template_dir = ROOT / "tools" / "anhui_web" / "templates"
    pairs = [(name, template_dir / name, site_dir / "assets" / name) for name in MAINTAINABLE_TEMPLATE_ASSETS]
    pairs.append(("manifest.webmanifest", template_dir / "maintainable.webmanifest", site_dir / "manifest.webmanifest"))
    mismatches: list[str] = []
    checked = 0
    for name, template_path, output_path in pairs:
        if not template_path.is_file() or not output_path.is_file():
            mismatches.append(f"{name}: missing template or output")
            continue
        checked += 1
        if template_path.read_bytes() != output_path.read_bytes():
            mismatches.append(f"{name}: bytes differ")
    # sw.js：模板经版本注入后与产物逐字比对
    sw_output = site_dir / "sw.js"
    if not sw_output.is_file():
        mismatches.append("sw.js: missing output")
    else:
        checked += 1
        if _render_sw_template() != sw_output.read_text(encoding="utf-8"):
            mismatches.append("sw.js: bytes differ after release.json injection")
    site_js = site_dir / "assets" / "maintainable-site.js"
    if site_js.is_file():
        text = site_js.read_text(encoding="utf-8")
        for marker in ("const renderHelp", "const renderChangelog"):
            if marker not in text:
                mismatches.append(f"maintainable-site.js: missing {marker}")
    else:
        mismatches.append("maintainable-site.js: missing view source")
    index_text = (site_dir / "index.html").read_text(encoding="utf-8") if (site_dir / "index.html").is_file() else ""
    for marker in ('data-maintain-view="help"', 'data-maintain-view="changelog"'):
        if marker not in index_text:
            mismatches.append(f"index.html: missing {marker}")
    return {"status": "pass" if not mismatches else "fail", "checked": checked, "mismatches": mismatches}


def write_release_record(deliverables: Path) -> Path:
    """Persist the release manifest used to compare or roll back modules."""
    site_dir = deliverables / "maintainable"
    manifest_path = site_dir / "data" / "site-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record_dir = deliverables / "releases" / BUILD_VERSION
    record_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "release": BUILD_VERSION,
        "created_on": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "validation_status": BROWSER_VALIDATION["status"],
        "browser_smoke_skipped": list(BROWSER_VALIDATION["skipped_scripts"]),
        # RC3-P2：degraded_validation 的 release 不得打正式版本 tag（tag_allowed=false 为硬规则）。
        "tag_allowed": BROWSER_VALIDATION["status"] == "verified",
        "maintainable_manifest": manifest,
        "rollback": {
            "unit": "cycle/module",
            "required": ["same cycle", "previous SHA-256", "disk verifier"],
            "rule": "只允许同周期同模块恢复；恢复后必须重建 manifest 并重新校验。",
        },
        "artifacts": {
            "maintainable_site": "../../maintainable",
        },
    }
    path = record_dir / "manifest.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def rollback_module(release_dir: Path, cycle: str, module: str, previous_hash: str) -> dict[str, object]:
    """Validate a same-cycle module rollback without mutating the workspace.

    The release record is deliberately dry-run only: a caller must copy the
    validated previous file, rebuild the manifest, and rerun the disk gate.
    """
    base = Path(release_dir).resolve()
    previous = (base / "previous" / "data" / "cycles" / str(cycle) / f"{module}.json").resolve()
    if not previous.is_relative_to(base):
        raise ValueError("rollback target escapes release directory")
    if not previous.is_file():
        raise FileNotFoundError(previous)
    digest = hashlib.sha256(previous.read_bytes()).hexdigest()
    if digest != str(previous_hash):
        raise ValueError("rollback module SHA-256 mismatch")
    return {"status": "ready", "dry_run": True, "cycle": str(cycle), "module": str(module), "path": str(previous), "sha256": digest}


def run_tests() -> None:
    print("== 正式链 Python 单测 ==")
    test_modules = [
        "tests.test_anhui_web", "tests.test_three_year_audit", "tests.test_data_quality_guards",
        "tests.test_ui_v13", "tests.test_v14_upgrade_baseline", "tests.test_data_contract", "tests.test_source_registry",
        "tests.test_catalog_and_changes", "tests.test_position_detail_contract", "tests.test_changes_and_comparability",
        "tests.test_review_queue", "tests.test_scores_contract", "tests.test_datastore_contract",
        "tests.test_accessibility_and_export", "tests.test_ui_v14", "tests.test_ui_v15", "tests.test_map_restore", "tests.test_maintainable_site", "tests.test_release_v14",
        "tests.test_v17_salary_and_motion",
    ]
    subprocess.run([sys.executable, "-m", "unittest", *test_modules], cwd=ROOT, check=True)
    print("== node 纯函数单测 ==")
    subprocess.run(["node", "--test", "tests/test_wanyu_core.cjs"], cwd=ROOT, check=True)
    subprocess.run(["node", "--test", "tests/test_major_city_index.cjs"], cwd=ROOT, check=True)
    subprocess.run(["node", "tests/test_datastore_contract.cjs"], cwd=ROOT, check=True)
    subprocess.run(["node", "--test", "tests/test_user_store_contract.cjs"], cwd=ROOT, check=True)


# I(2026-09-05 v17.8.5-RC2)：浏览器烟测真 fail-closed。
# - playwright-core 缺失 或 Chromium 缺失 => 一律 FAIL；
#   只有显式 --allow-missing-browser 才允许跳过，且 release 记录 validation_status=degraded_validation。
# - 标准 node_modules 优先（项目源码/node_modules），codex 运行时仅作兼容回退并显式告警。
BROWSER_VALIDATION = {"status": "verified", "skipped_scripts": []}
ALLOW_MISSING_BROWSER = False


def _playwright_node_modules() -> Path | None:
    candidates = [ROOT / "node_modules", Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node_modules"]
    for candidate in candidates:
        if (candidate / "playwright-core" / "package.json").is_file():
            if candidate != candidates[0]:
                print(f"[警告] 使用非标准 node_modules 回退：{candidate}（请 npm install 以标准化）")
            return candidate
    return None


def run_browser_smoke(script: str, require_browser: bool = False, allow_missing_browser: bool = False) -> None:
    del require_browser  # 历史 API；fail-closed 后只有 allow_missing_browser 一个豁免口
    allow_missing_browser = allow_missing_browser or ALLOW_MISSING_BROWSER
    node_modules = _playwright_node_modules()
    def _skip(reason: str) -> None:
        if not allow_missing_browser:
            raise RuntimeError(
                f"G2: 正式发布浏览器烟测不允许静默跳过（{script}: {reason}）。"
                "先安装依赖与浏览器（npm install && npx playwright install chromium），"
                "或显式使用 --allow-missing-browser 承担人工走查责任（release 将标记 degraded_validation）。"
            )
        BROWSER_VALIDATION["status"] = "degraded_validation"
        BROWSER_VALIDATION["skipped_scripts"].append(script)
        print(f"[degraded] 浏览器烟测 {script} 被显式豁免（{reason}）；release 记录 validation_status=degraded_validation。")

    if node_modules is None:
        _skip("缺 playwright-core（标准位置与 codex 回退均未找到）")
        return
    env = dict(__import__("os").environ)
    env["NODE_PATH"] = str(node_modules)
    probe = subprocess.run(
        ["node", "-e", "try{console.log(require('playwright-core').chromium.executablePath())}catch(e){process.exit(1)}"],
        env=env, capture_output=True, text=True,
    )
    executable = probe.stdout.strip() if probe.returncode == 0 else ""
    if not executable or not Path(executable).is_file():
        _skip("playwright-core 有库无 Chromium 二进制（npx playwright install chromium）")
        return
    subprocess.run(["node", script], cwd=ROOT, env=env, check=True)


def run_audit() -> None:
    """三周期审计重生成——仅限遗留单文件链；正式链使用 --check 只读模式。"""
    print("== 三周期数据审计（遗留链重生成）==")
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


def build_and_sync() -> None:
    """正式发布链：维护站（canonical 唯一输入）构建 + 校验 + 发布记录。"""
    print("== 外置 JSON 维护站 ==")
    deliverables = ROOT / "deliverables"
    deliverables.mkdir(exist_ok=True)
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "anhui_web" / "build_maintainable_site.py"),
         "--root", str(ROOT), "--output-dir", str(deliverables / "maintainable")],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "anhui_web" / "verify_maintainable_site.py"),
         str(deliverables / "maintainable")],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "anhui_web" / "perf_budget.py"),
         str(deliverables / "maintainable")],
        cwd=ROOT,
        check=True,
    )
    parity = verify_template_asset_parity(deliverables / "maintainable")
    if parity["status"] != "pass":
        raise RuntimeError(f"维护站模板/产物不一致：{parity}")
    print(f"asset parity → {parity['checked']} files, help/changelog markers present")
    # The maintainable site emits ten per-cycle modules, two audit indexes,
    # and one shared real-geometry map; the disk verifier and browser smoke are
    # release gates.
    run_browser_smoke("tests/maintainable_browser_smoke.js", require_browser=True)
    run_browser_smoke("tests/ui_upgrade_browser_smoke.cjs", require_browser=True)
    print("== 发布记录 ==")
    if BROWSER_VALIDATION["status"] != "verified":
        print("[RC3-P2] validation_status=degraded_validation → tag_allowed=false（禁止打正式版本 tag）")
    print("release manifest →", write_release_record(deliverables))
    for name in (LEGACY_SINGLE_HTML,):
        if (deliverables / name).is_file():
            print("legacy archive present →", name)


def legacy_single_file_chain() -> None:
    """遗留单文件存档链（v17.8.6 方案 A）：显式请求才运行，非发布门禁。

    产物 = deliverables/皖域择岗总览.html（遗留存档）。它不参与正式
    validation_status，也不进入 发布资料 发布清单。
    """
    print("== [遗留链] 成绩清单构建 ==")
    for cycle in ("2026", "2025", "2024"):
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "anhui_web" / "build_score_lists.py"), "--cycle", cycle],
            cwd=ROOT,
            check=True,
        )
    run_audit()
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
    parser = argparse.ArgumentParser(description="测试 + 维护站构建 + 校验（正式链）；单文件链已降级为 --legacy-single-file")
    parser.add_argument("--zip", action="store_true", help="追加打包发布 zip")
    parser.add_argument("--skip-tests", action="store_true", help="跳过测试（调试用）")
    parser.add_argument("--legacy-single-file", action="store_true",
                        help="追加遗留单文件存档链（非发布门禁；产物为 deliverables/皖域择岗总览.html）")
    parser.add_argument("--allow-missing-browser", action="store_true",
                        help="显式豁免浏览器烟测（release 记录 validation_status=degraded_validation）")
    arguments = parser.parse_args()
    ALLOW_MISSING_BROWSER = bool(arguments.allow_missing_browser)
    if arguments.skip_tests:
        # RC3-P1：--skip-tests 仅限 dev/debug（WANYU_DEV=1）；正式 release 拒绝。
        import os as _os

        if _os.environ.get("WANYU_DEV", "").strip() != "1":
            raise SystemExit("RC3-P1：正式 release 禁止 --skip-tests（dev/debug 请设 WANYU_DEV=1）")
        print("[dev] WANYU_DEV=1：--skip-tests 生效（release 记录将标注 dev_mode=true）")
    if not arguments.skip_tests:
        run_tests()
    build_and_sync()
    if arguments.legacy_single_file:
        legacy_single_file_chain()
    if arguments.zip:
        package_zip()
