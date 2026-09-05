"""皖域择岗维护站 · 性能预算门禁（治卡顿计划 §7 / §10 的落地件）。

对 deliverables/maintainable 的每个外置模块计算「原始字节」与「gzip 压缩后字节」，
与可回退的预算阈值(ratchet)对比；超标即退出码 1。默认只读、不改动站点。
阈值以「当前值 + 余量」为基线，用于阻止体积回涨(棘轮)，不是给新功能放水。
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SITE_DEFAULT = ROOT / "deliverables" / "maintainable"

# 压缩后(≈brotli 上界)预算，单位 字节。scores 已移到归档附件，不进入运行期统计。
BUDGET_GZIP: dict[str, int] = {
    "jobs_lite": 780_000,
    "catalog": 780_000,
    "positions": 660_000,
    "jobs": 1_350_000,
    "palette": 360_000,
    "derived": 20_000,
    "major_city": 80_000,
    "overview": 40_000,
    "audit": 40_000,
    "changes": 3_000_000,
    "scores": 3_200_000,
}
GLOBAL_BUDGET_GZIP: dict[str, int] = {
    "map": 40_000,
    "salary": 40_000,
    "audit": 40_000,  # three-year.json (site-manifest 'audit')
    "review_queue": 20_000,
    "job_history": 120_000,
    "supplement": 50_000,
}


def _gz(path: Path) -> int:
    return len(gzip.compress(path.read_bytes(), compresslevel=9))


def collect(site_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manifest = json.loads((site_dir / "data" / "site-manifest.json").read_text(encoding="utf-8"))
    for entry in manifest.get("cycles", []):
        cycle = str(entry.get("cycle"))
        for module, info in (entry.get("modules") or {}).items():
            path = site_dir / str(info.get("data"))
            if not path.is_file():
                rows.append({"scope": f"{cycle}/{module}", "raw": 0, "gzip": 0, "budget": BUDGET_GZIP.get(module), "status": "missing"})
                continue
            gz = _gz(path)
            budget = BUDGET_GZIP.get(module)
            rows.append({"scope": f"{cycle}/{module}", "raw": path.stat().st_size, "gzip": gz,
                         "budget": budget, "status": "ok" if budget is None or gz <= budget else "over"})
    for name in ("map", "salary", "audit", "review_queue", "job_history", "supplement"):
        info = manifest.get(name) or {}
        path = site_dir / str(info.get("data")) if info.get("data") else None
        if path and path.is_file():
            gz = _gz(path)
            budget = GLOBAL_BUDGET_GZIP.get(name)
            rows.append({"scope": f"global/{name}", "raw": path.stat().st_size, "gzip": gz,
                         "budget": budget, "status": "ok" if budget is None or gz <= budget else "over"})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="维护站性能预算门禁(棘轮)")
    parser.add_argument("site", nargs="?", default=str(SITE_DEFAULT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    site_dir = Path(args.site).resolve()
    if not (site_dir / "data" / "site-manifest.json").is_file():
        print(f"未找到 manifest：{site_dir}", )
        return 2
    rows = collect(site_dir)
    over = [r for r in rows if r["status"] == "over"]
    total_gz = sum(r["gzip"] for r in rows)
    if args.json:
        print(json.dumps({"total_gzip": total_gz, "over": over, "rows": rows}, ensure_ascii=False))
    else:
        print(f"{'scope':<26}{'raw':>14}{'gzip':>14}{'budget':>14}  status")
        for r in rows:
            bud = f"{r['budget']:,}" if r.get("budget") else "—"
            print(f"{r['scope']:<26}{r['raw']:>14,}{r['gzip']:>14,}{bud:>14}  {r['status'].upper()}")
        print(f"\n合计 gzip ≈ {total_gz/1e6:.1f} MB · 模块 {len(rows)} 个 · 超预算 {len(over)} 项")
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
