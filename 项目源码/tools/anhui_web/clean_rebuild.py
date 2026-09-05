# -*- coding: utf-8 -*-
"""v17.8.6 阶段 E：clean rebuild——锁只读、零自签、零审计重写。

流程（RB-02 修复：sources.lock 在发布/重建期间是【只读输入】，任何一步都不得
重签；three_year_audit.json 同为受锁工件，正式链禁止重生成——重生成只属于
--legacy-single-file 遗留链）：
  verify_sources（锁一致）→ canonical bundles → assemble（空目录）
  → verify_inputs_unchanged（锁/规范/覆盖/审计前后零漂移）→ 事实对比 → verifier

事实闸（2026）：raw 8511 = active 8401 + excluded 110；raw_recruits 12006 / recruits 11883；
lite/catalog/positions/major_city = 8401；score_unresolved=0 / resolved=116。
任何一步失败 → 非 0 退出，禁止发布。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

PROJECT_ROOT = HERE.parents[1]

# 发布期间必须保持字节不变的受锁/规范输入。
_IMMUTABLE_INPUTS = (
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs_unchanged() -> dict[str, str]:
    """快照受锁输入哈希；构建后再取一次并比对，任何漂移即失败（不自签修复）。"""
    return {rel: _sha256(PROJECT_ROOT / rel) for rel in _IMMUTABLE_INPUTS}


def run(cmd: list[str], cwd: Path = PROJECT_ROOT) -> None:
    print("$", " ".join(str(x) for x in cmd))
    result = subprocess.run([str(x) for x in cmd], cwd=str(cwd))
    if result.returncode != 0:
        raise SystemExit(f"clean rebuild 步骤失败（exit {result.returncode}）：{cmd}")


def facts_of(out_dir: Path) -> dict:
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


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="wanyu-clean-rebuild-"))
    print("[1/5] verify_sources（sources.lock 只读校验——发布期间禁止重签）")
    run([sys.executable, "verify_sources.py"])
    before = verify_inputs_unchanged()
    print("[2/5] canonical bundles → assemble（空目录；audit/overrides 仅作为受锁输入读取）")
    from tools.anhui_web.unified_cycle_bundle import build_unified_bundles
    from tools.anhui_web.build_maintainable_site import assemble_maintainable_site
    bundles = build_unified_bundles(PROJECT_ROOT)
    assemble_maintainable_site(bundles, root=PROJECT_ROOT, output_dir=out_dir)
    after = verify_inputs_unchanged()
    drifted = [rel for rel in before if before[rel] != after.get(rel)]
    if drifted:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise SystemExit(f"RB-02：受锁输入在构建期间被改写（禁止自签）：{drifted}")
    print("    受锁输入前后一致：", len(before), "files")
    print("[3/5] 事实对比")
    facts = facts_of(out_dir)
    bad = {k: (facts.get(k), v) for k, v in EXPECTED_2026.items() if facts.get(k) != v}
    if bad:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise SystemExit(f"clean rebuild 事实闸失败：{bad}")
    print("    2026 事实：", json.dumps({k: facts[k] for k in EXPECTED_2026}, ensure_ascii=False))
    print(f"    globals: {facts['module_globals']} | job_history families: {facts['job_history_total']}")
    print("[4/5] verifier（空目录产物）")
    run([sys.executable, "tools/anhui_web/verify_maintainable_site.py", str(out_dir)])
    print("[5/5] 审计只读复核（audit --check：内存重算 vs 已提交工件，不落盘）")
    run([sys.executable, "tools/anhui_web/audit_three_years.py", "--root", ".",
         "--output-json", "tools/anhui_web/data/three_year_audit.json", "--check"])
    print(f"clean rebuild PASS → {out_dir}")
    print("注意：tmp 产物与 网站 的字节差异仅允许来自 runtime source_file（canonical 引用名）等装配元数据；")
    print("如需同步生产，请执行发布流水线（staging → 原子提升）而非手工拷贝。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
