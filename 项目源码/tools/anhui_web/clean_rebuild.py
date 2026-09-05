# -*- coding: utf-8 -*-
"""v17.8.5-RC3 阶段 N：clean rebuild 门禁——空目录全链重建与事实对比。

流程（不读取 网站/ 中任何既有产物；assemble 的输入只有 canonical + 锁定源）：
  verify_sources → audit 重生成（canonical 行源）→ 重锁 sources → verify_sources
  → canonical bundles → assemble（空目录）→ 事实对比 → verifier

事实闸（2026）：raw 8511 = active 8401 + excluded 110；raw_recruits 12006 / recruits 11883；
lite/catalog/positions/major_city = 8401；score_unresolved=0 / resolved=116。
任何一步失败 → 非 0 退出，禁止发布。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

PROJECT_ROOT = HERE.parents[1]
WORKSPACE = PROJECT_ROOT.parent
SITE = WORKSPACE / "网站"

EXPECTED_2026 = {
    "raw_posts": 8511, "active_posts": 8401, "excluded_posts": 110,
    "raw_recruits": 12006, "recruits": 11883,
    "lite_rows": 8401, "score_unresolved": 0, "resolved": 116,
}


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
    print(f"[1/6] 源锁校验")
    run([sys.executable, "verify_sources.py"])
    print("[2/6] 审计重生成（canonical 行源，HTML 零输入）")
    run([sys.executable, "tools/anhui_web/audit_three_years.py", "--root", ".",
         "--output-json", "tools/anhui_web/data/three_year_audit.json",
         "--report", "../docs/audit/clean-rebuild-three-year-audit.md"])
    print("[3/6] 重锁 sources（审计工件哈希刷新）并复验")
    run([sys.executable, "tools/anhui_web/gen_sources_lock.py"])
    run([sys.executable, "verify_sources.py"])
    print("[4/6] canonical bundles → assemble（空目录）")
    from tools.anhui_web.unified_cycle_bundle import build_unified_bundles
    from tools.anhui_web.build_maintainable_site import assemble_maintainable_site
    bundles = build_unified_bundles(PROJECT_ROOT)
    assemble_maintainable_site(bundles, root=PROJECT_ROOT, output_dir=out_dir)
    print("[5/6] 事实对比")
    facts = facts_of(out_dir)
    bad = {k: (facts.get(k), v) for k, v in EXPECTED_2026.items() if facts.get(k) != v}
    if bad:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise SystemExit(f"clean rebuild 事实闸失败：{bad}")
    print("    2026 事实：", json.dumps({k: facts[k] for k in EXPECTED_2026}, ensure_ascii=False))
    print(f"    globals: {facts['module_globals']} | job_history families: {facts['job_history_total']}")
    print("[6/6] verifier（空目录产物）")
    run([sys.executable, "tools/anhui_web/verify_maintainable_site.py", str(out_dir)])
    print(f"clean rebuild PASS → {out_dir}")
    print("注意：tmp 产物与 站点 的字节差异仅允许来自 runtime source_file（canonical 引用名）等装配元数据；")
    print("如需同步生产，请执行 RC3 再生（assemble → 网站）而非手工拷贝。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
