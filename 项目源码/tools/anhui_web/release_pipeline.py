# -*- coding: utf-8 -*-
"""v17.8.6 阶段 N：正式发布共享流水线（单一真源）。

clean_rebuild.py = run_pipeline(promote=False)（临时目录，绝不触碰 网站/）；
release.py       = run_pipeline(promote=True)（staging → 验证 → 原子提升）。
两条链共用同一实现，禁止各自为政。

阶段（全部 fail-closed）：
  1 precheck        git 工作树干净（豁免需 WANYU_DEV=1 + 显式 --allow-dirty）
  2 verify_sources  sources.lock 只读校验（发布期间禁止重签，RB-02）
  3 validate_canonical  schema + 守恒 + 溯源 + score_state + 2026 回归锁定
  4 audit --check   三年审计内存重算 vs 已提交工件（不落盘，不覆盖）
  5 build           canonical bundles → assemble → 暂存目录（生产不受影响）
  6 verify_inputs_unchanged  受锁输入构建前后字节零漂移（不自签）
  7 verify_site     磁盘 verifier + 2026 事实闸 + perf 预算 + 模板一致性
  8 browser smoke   三脚本 × WANYU_SITE_DIR=staging（fail-closed）
  9 (promote) manifest → 发布资料/releases/<ver>/manifest.json + SHA256SUMS + 锁摘要
 10 (promote) 原子提升：网站→网站.previous，staging→网站；失败自动回滚并复验
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

PROJECT_ROOT = HERE.parents[1]
WORKSPACE = PROJECT_ROOT.parent
PROD_SITE = WORKSPACE / "网站"
BACKUP_SITE = WORKSPACE / "网站.previous"
RELEASE_ROOT = WORKSPACE / "发布资料" / "releases"
BUILD_VERSION = json.loads((PROJECT_ROOT / "release.json").read_text(encoding="utf-8"))["release"]

# 发布期间必须保持字节不变的受锁/规范输入（相对 项目源码）。
IMMUTABLE_INPUTS = (
    "sources.lock.json",
    "canonical/schema.json",
    "canonical/cycles/2024.json",
    "canonical/cycles/2025.json",
    "canonical/cycles/2026.json",
    "canonical/curated/req-fields-2026.json",
    "canonical/curated/calendar.json",
    "tools/anhui_web/data/record_status_overrides.json",
    "tools/anhui_web/data/three_year_audit.json",
)

EXPECTED_2026 = {
    "raw_posts": 8511, "active_posts": 8401, "excluded_posts": 110,
    "raw_recruits": 12006, "recruits": 11883,
    "lite_rows": 8401, "score_unresolved": 0, "resolved": 116,
}
EXPECTED_MODULE_GLOBALS = {"job_history", "calendar", "supplement", "map", "salary", "audit", "review_queue"}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs_unchanged() -> dict[str, str]:
    """快照受锁输入哈希；构建后再取一次并比对，任何漂移即失败（不自签修复）。"""
    return {rel: sha256_of(PROJECT_ROOT / rel) for rel in IMMUTABLE_INPUTS}


def run_step(cmd: list[str], cwd: Path = PROJECT_ROOT) -> subprocess.CompletedProcess:
    print("$", " ".join(str(x) for x in cmd))
    result = subprocess.run([str(x) for x in cmd], cwd=str(cwd))
    if result.returncode != 0:
        raise RuntimeError(f"发布流水线步骤失败（exit {result.returncode}）：{cmd}")
    return result


# ---------------------------------------------------------------- 阶段 1
def _dirty_entries() -> list[str]:
    """git status --porcelain（core.quotepath=off），返回原始脏项行。"""
    result = subprocess.run(
        ["git", "-c", "core.quotepath=off", "status", "--porcelain"],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8",
    )
    return [line for line in (result.stdout or "").splitlines() if line.strip()]


def _pipeline_owned(line: str) -> bool:
    """发布资料/ = 流水线自产发布记录（本运行写入/重写），不算脏项。"""
    path = line[3:].strip().strip('"').strip()
    return path == "发布资料" or path.startswith("发布资料/")


def git_precheck(allow_dirty: bool = False) -> bool:
    """正式发布要求 git 工作树干净（发布资料/ 豁免：流水线自产输出）；豁免脏树必须同时满足 WANYU_DEV=1。返回 dirty 标记。"""
    dirty = [line for line in _dirty_entries() if not _pipeline_owned(line)]
    if not dirty:
        return False
    if not allow_dirty or os.environ.get("WANYU_DEV", "").strip() != "1":
        raise RuntimeError(f"precheck：git 工作树不干净（{len(dirty)} 项），正式发布拒绝：{dirty[:5]}")
    print(f"[dev] WANYU_DEV=1 + --allow-dirty：容忍 {len(dirty)} 项未提交变更（release 记录 dirty=true）")
    return True


def probe_browser() -> tuple[Path | None, str]:
    """返回 (node_modules, chromium 可执行文件)；任一缺失 → (None, '')。"""
    return _probe_browser()


def _playwright_node_modules() -> Path | None:
    candidates = [PROJECT_ROOT / "node_modules", Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node_modules"]
    for candidate in candidates:
        if (candidate / "playwright-core" / "package.json").is_file():
            if candidate != candidates[0]:
                print(f"[警告] 使用非标准 node_modules 回退：{candidate}（请 npm install 以标准化）")
            return candidate
    return None


def _probe_browser() -> tuple[Path | None, str]:
    node_modules = _playwright_node_modules()
    if node_modules is None:
        return None, ""
    env = dict(os.environ)
    env["NODE_PATH"] = str(node_modules)
    probe = subprocess.run(
        ["node", "-e", "try{console.log(require('playwright-core').chromium.executablePath())}catch(e){process.exit(1)}"],
        env=env, capture_output=True, text=True,
    )
    executable = probe.stdout.strip() if probe.returncode == 0 else ""
    if not executable or not Path(executable).is_file():
        return node_modules, ""
    return node_modules, executable


# ---------------------------------------------------------------- 阶段 2/3/4
def verify_sources() -> None:
    run_step([sys.executable, "verify_sources.py"])


def validate_canonical() -> None:
    run_step([sys.executable, "tools/anhui_web/validate_canonical.py", "--root", "."])


def audit_check() -> None:
    run_step([sys.executable, "tools/anhui_web/audit_three_years.py", "--root", ".",
              "--output-json", "tools/anhui_web/data/three_year_audit.json", "--check"])


# ---------------------------------------------------------------- 阶段 5
def build_site(output_dir: Path) -> Path:
    """canonical bundles → assemble（唯一正式构建入口；HTML 零输入）。"""
    from tools.anhui_web.unified_cycle_bundle import build_unified_bundles
    from tools.anhui_web.build_maintainable_site import assemble_maintainable_site

    bundles = build_unified_bundles(PROJECT_ROOT)
    assemble_maintainable_site(bundles, root=PROJECT_ROOT, output_dir=output_dir)
    return output_dir


# ---------------------------------------------------------------- 阶段 7
def facts_of(out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    manifest = json.loads((out_dir / "data" / "site-manifest.json").read_text(encoding="utf-8"))
    entry = next(e for e in manifest["cycles"] if str(e.get("cycle")) == "2026")
    lite = json.loads((out_dir / "data" / "cycles" / "2026" / "jobs_lite.json").read_text(encoding="utf-8"))
    audit = json.loads((out_dir / "data" / "cycles" / "2026" / "audit.json").read_text(encoding="utf-8"))
    catalog = json.loads((out_dir / "data" / "cycles" / "2026" / "catalog.json").read_text(encoding="utf-8"))
    positions = json.loads((out_dir / "data" / "cycles" / "2026" / "positions.json").read_text(encoding="utf-8"))
    major_city = json.loads((out_dir / "data" / "cycles" / "2026" / "major_city.json").read_text(encoding="utf-8"))
    return {
        "raw_posts": entry.get("raw_posts"),
        "active_posts": entry.get("active_posts"),
        "excluded_posts": entry.get("excluded_posts"),
        "raw_recruits": entry.get("raw_recruits"),
        "recruits": entry.get("recruits"),
        "lite_rows": len(lite["allMajors"]["rows"]),
        "score_unresolved": audit["scoreLists"]["keyed"]["unresolved"],
        "resolved": (audit.get("audit", {}).get("score_lists") or {}).get("resolved"),
        "catalog_rows": catalog.get("row_count"),
        "positions_rows": positions.get("row_count"),
        "major_city_rows": major_city.get("rows_total"),
        "module_globals": sorted(k for k in ("job_history", "calendar", "supplement", "map", "salary", "audit", "review_queue") if k in manifest),
        "job_history_total": json.loads((out_dir / "data" / "job_history.json").read_text(encoding="utf-8"))["jobs_total"],
    }


def facts_gate(site_dir: Path) -> dict:
    facts = facts_of(site_dir)
    bad = {k: (facts.get(k), v) for k, v in EXPECTED_2026.items() if facts.get(k) != v}
    if bad:
        raise RuntimeError(f"2026 事实闸失败：{bad}")
    missing_globals = EXPECTED_MODULE_GLOBALS - set(facts["module_globals"])
    if missing_globals:
        raise RuntimeError(f"2026 事实闸失败：缺少全局模块 {sorted(missing_globals)}")
    return facts


def _discover_template_assets() -> tuple[str, ...]:
    tpl = HERE / "templates"
    found = sorted(p.name for p in tpl.iterdir()
                   if p.is_file() and (p.name.startswith("maintainable-") or p.name.startswith("v17-"))
                   and p.suffix in {".css", ".js"} and p.name not in {"maintainable-sw.js"})
    return tuple(found)


MAINTAINABLE_TEMPLATE_ASSETS = _discover_template_assets()


def _render_sw_template() -> str:
    """SW 模板 → 实际产物内容（release.json 注入版本占位符）。"""
    template = (HERE / "templates" / "maintainable-sw.js").read_text(encoding="utf-8")
    release_doc = json.loads((PROJECT_ROOT / "release.json").read_text(encoding="utf-8"))
    return (
        template
        .replace("__SW_VERSION__", str(release_doc.get("service_worker_version") or ""))
        .replace("__ASSET_VERSION__", str(release_doc.get("asset_version") or ""))
    )


def verify_template_asset_parity(site_dir: Path) -> dict[str, object]:
    """Compare the built shell assets with their checked-in templates (byte-for-byte)."""
    site_dir = Path(site_dir).resolve()
    template_dir = HERE / "templates"
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


def verify_site(site_dir: Path) -> dict:
    """暂存/生产站点的完整磁盘验证：verifier + 事实闸 + perf 预算 + 模板一致性。"""
    site_dir = Path(site_dir)
    run_step([sys.executable, "tools/anhui_web/verify_maintainable_site.py", str(site_dir)])
    run_step([sys.executable, "tools/anhui_web/perf_budget.py", str(site_dir)])
    parity = verify_template_asset_parity(site_dir)
    if parity["status"] != "pass":
        raise RuntimeError(f"维护站模板/产物不一致：{parity}")
    print(f"asset parity → {parity['checked']} files, help/changelog markers present")
    return facts_gate(site_dir)


# ---------------------------------------------------------------- 阶段 8
BROWSER_VALIDATION = {"status": "verified", "skipped_scripts": []}
ALLOW_MISSING_BROWSER = False
SMOKE_SCRIPTS = ("tests/maintainable_browser_smoke.js", "tests/major_city_browser_smoke.cjs", "tests/ui_upgrade_browser_smoke.cjs")


def run_browser_smoke(script: str, site_dir: Path | None = None, allow_missing_browser: bool = False) -> None:
    """fail-closed 烟测；site_dir 非空时经 WANYU_SITE_DIR 指向暂存目录。"""
    allow_missing_browser = allow_missing_browser or ALLOW_MISSING_BROWSER
    node_modules, executable = _probe_browser()

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
    if not executable:
        _skip("playwright-core 有库无 Chromium 二进制（npx playwright install chromium）")
        return
    env = dict(os.environ)
    env["NODE_PATH"] = str(node_modules)
    if site_dir is not None:
        env["WANYU_SITE_DIR"] = str(site_dir)
    _run_with_env(["node", script], env)


def _run_with_env(cmd: list[str], env: dict[str, str]) -> bool:
    print("$", " ".join(cmd), f"(WANYU_SITE_DIR={env.get('WANYU_SITE_DIR', '-')})")
    result = subprocess.run([str(x) for x in cmd], cwd=str(PROJECT_ROOT), env=env)
    if result.returncode != 0:
        raise RuntimeError(f"浏览器烟测失败（exit {result.returncode}）：{cmd}")
    return False


def run_all_smokes(site_dir: Path | None, allow_missing_browser: bool = False) -> None:
    for script in SMOKE_SCRIPTS:
        run_browser_smoke(script, site_dir=site_dir, allow_missing_browser=allow_missing_browser)


# ---------------------------------------------------------------- 阶段 9
def sha256_tree(base: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for path in sorted(Path(base).rglob("*")):
        if path.is_file():
            entries[path.relative_to(base).as_posix()] = sha256_of(path)
    return entries


def write_release_manifest(staging_dir: Path, facts: dict, tests_summary: dict, dirty: bool) -> Path:
    """不可变发布记录：发布资料/releases/<ver>/manifest.json + SHA256SUMS + 锁摘要。"""
    staging_dir = Path(staging_dir)
    site_manifest = json.loads((staging_dir / "data" / "site-manifest.json").read_text(encoding="utf-8"))
    record_dir = RELEASE_ROOT / BUILD_VERSION
    record_dir.mkdir(parents=True, exist_ok=True)
    git_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(PROJECT_ROOT), capture_output=True, text=True).stdout.strip()
    record = {
        "release": BUILD_VERSION,
        "created_on": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "git_commit": git_commit,
        "git_dirty": bool(dirty),
        "canonical_schema": "wanyu-cycle-bundle/v1",
        "metrics_contract": site_manifest.get("metrics_contract"),
        "source_lock_sha256": sha256_of(PROJECT_ROOT / "sources.lock.json"),
        "locked_inputs_sha256": {rel: sha256_of(PROJECT_ROOT / rel) for rel in IMMUTABLE_INPUTS},
        "validation_status": BROWSER_VALIDATION["status"],
        "browser_smoke_skipped": list(BROWSER_VALIDATION["skipped_scripts"]),
        # RC3-P2：degraded_validation / 脏树 / 跳过测试的 release 不得打正式版本 tag。
        "tag_allowed": (
            BROWSER_VALIDATION["status"] == "verified"
            and not bool(dirty)
            and str(tests_summary.get("status")) == "pass"
        ),
        "tests": tests_summary,
        "data_facts": {"2026": {k: facts[k] for k in EXPECTED_2026}, "module_globals": facts["module_globals"], "job_history_total": facts["job_history_total"]},
        "artifacts": {"maintainable_site": "网站/"},
        "rollback": {
            "unit": "whole-site",
            "backup": "网站.previous",
            "rule": "原子提升失败自动回滚；手工回滚 = 还原 网站.previous 并重跑 verify_maintainable_site。",
        },
    }
    path = record_dir / "manifest.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sums = "\n".join(f"{digest}  {rel}" for rel, digest in sorted(sha256_tree(staging_dir).items())) + "\n"
    (record_dir / "SHA256SUMS").write_text(sums, encoding="utf-8")
    print(f"release manifest → {path}（SHA256SUMS {len(sha256_tree(staging_dir))} files）")
    return path


# ---------------------------------------------------------------- 阶段 10
def promote_site(staging_dir: Path, verify_production) -> None:
    """原子提升：网站→网站.previous，staging→网站；提升后验证失败自动回滚。"""
    staging_dir = Path(staging_dir).resolve()
    if BACKUP_SITE.exists():
        print("[promote] 移除上一轮回滚点 网站.previous（git 历史保留已发布树）")
        shutil.rmtree(BACKUP_SITE)
    if not PROD_SITE.exists():
        raise RuntimeError("promote：生产目录 网站 缺失，拒绝首装式覆盖（请先确认产品树）")
    PROD_SITE.rename(BACKUP_SITE)
    try:
        staging_dir.rename(PROD_SITE)
    except Exception:
        BACKUP_SITE.rename(PROD_SITE)  # 提升（rename）失败 → 原地恢复
        raise
    print("[promote] 提升完成，执行生产后验证")
    try:
        verify_production(PROD_SITE)
    except Exception:
        shutil.rmtree(PROD_SITE, ignore_errors=True)
        BACKUP_SITE.rename(PROD_SITE)
        print("[promote] 生产后验证失败 → 已回滚到 网站.previous", file=sys.stderr)
        raise


# ---------------------------------------------------------------- 编排
def run_pipeline(output_dir: Path, *, promote: bool, allow_dirty: bool, tests_summary: dict) -> dict:
    """共享编排；promote=False 时只构建到 output_dir 并验证，绝不触碰 网站/。

    git 干净预检仅提升链（promote=True）强制；clean_rebuild 等非提升形态允许脏树。
    """
    output_dir = Path(output_dir)
    dirty = git_precheck(allow_dirty) if promote else _dirty_flag()
    print("[pipeline 2/8] verify_sources（锁只读）")
    verify_sources()
    print("[pipeline 3/8] validate_canonical")
    validate_canonical()
    print("[pipeline 4/8] audit --check（只读复核）")
    audit_check()
    before = verify_inputs_unchanged()
    print(f"[pipeline 5/8] build → {output_dir}")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    build_site(output_dir)
    after = verify_inputs_unchanged()
    drifted = [rel for rel in before if before[rel] != after.get(rel)]
    if drifted:
        raise RuntimeError(f"RB-02：受锁输入在构建期间被改写（禁止自签）：{drifted}")
    print(f"[pipeline 6/8] 受锁输入前后一致：{len(before)} files → verify_site")
    facts = verify_site(output_dir)
    print("[pipeline 7/8] browser smoke ×3（WANYU_SITE_DIR → staging）")
    run_all_smokes(output_dir)
    result = {"facts": facts, "dirty": bool(dirty)}
    if promote:
        print("[pipeline 8/8] release manifest + 原子提升")
        write_release_manifest(output_dir, facts, tests_summary, result["dirty"])
        promote_site(output_dir, verify_site)
    return result


def _dirty_flag() -> bool:
    """非提升形态的脏标记（发布资料/ 豁免同 precheck）。"""
    return bool([line for line in _dirty_entries() if not _pipeline_owned(line)])
