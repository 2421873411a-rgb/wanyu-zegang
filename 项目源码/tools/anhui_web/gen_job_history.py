# -*- coding: utf-8 -*-
"""D5 job_history.json 生产脚本恢复（资产可复现）。

规则（来自数据 key_semantics 与逆向对账）：键 = city|unit|zw 去空白小写；
逐周期聚合 posts/num/bm 求和、入围线取可复核（comparable）值区间 [lo, hi]；
只保留出现在 ≥2 个周期的岗位族。

用法：python gen_job_history.py            # 重建并与现库 diff（默认不落盘）
      python gen_job_history.py --write    # 重建并落盘（sources 哈希同步重绑）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

SITE = Path(__file__).resolve().parents[3] / "网站"
CYCLES = ("2024", "2025", "2026")
WS_RE = re.compile(r"\s+")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm_key(*parts: str) -> str:
    return WS_RE.sub("", "|".join(str(p or "") for p in parts)).lower()


def build() -> dict:
    families: dict[str, dict] = defaultdict(lambda: {"cycles": {}})
    for cycle in CYCLES:
        rows = json.loads((SITE / "data" / "cycles" / cycle / "jobs.json").read_text(encoding="utf-8"))["allMajors"]["rows"]
        grouped: dict[str, list] = defaultdict(list)
        for row in rows:
            city, unit, zw = str(row.get("city") or ""), str(row.get("unit") or ""), str(row.get("zw") or "")
            if not city or not unit or not zw:
                continue
            grouped[norm_key(city, unit, zw)].append(row)
        for key, group in grouped.items():
            posts = len(group)
            num = sum(int(r.get("num") or 0) for r in group)
            bm = sum(int(r.get("bm") or 0) for r in group)
            lines = [float(r["line"]) for r in group if isinstance(r.get("line"), (int, float)) and r["line"] > 0]
            entry = {"posts": posts, "num": num, "bm": bm if bm else None}
            if lines:
                entry["lo"] = min(lines)
                entry["hi"] = max(lines)
            families[key]["cycles"][cycle] = entry
    multi = {k: v for k, v in families.items() if len(v["cycles"]) >= 2}
    jobs = {}
    for key in sorted(multi):
        city = next(iter(multi[key]["cycles"].values())) and None
        jobs[key] = {"cycles": multi[key]["cycles"]}
    return jobs


def main() -> int:
    parser = argparse.ArgumentParser(description="重建 job_history.json")
    parser.add_argument("--write", action="store_true", help="落盘并重绑 sources 哈希")
    args = parser.parse_args()

    jobs = build()
    payload = {
        "schema": "wanyu-job-history/v1",
        "jobs_total": len(jobs),
        "jobs": jobs,
        "key_semantics": "city|unit|zw 去空白小写；聚合同键多岗：posts/num/bm 求和，入围线取可复核值区间",
        "sources": {},
    }
    for cycle in CYCLES:
        jp = SITE / "data" / "cycles" / cycle / "jobs.json"
        payload["sources"][cycle] = {"data": f"data/cycles/{cycle}/jobs.json", "sha256": sha256(jp)}

    current_path = SITE / "data" / "job_history.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    same_jobs = current.get("jobs") == jobs
    print(f"重建岗位族 {len(jobs)} | 现库 {current.get('jobs_total')} | jobs 内容一致: {same_jobs}")
    if not same_jobs:
        ck, nk = set(current.get("jobs") or {}), set(jobs)
        only_cur, only_new = list(ck - nk)[:3], list(nk - ck)[:3]
        print(f"  仅现库: {only_cur}")
        print(f"  仅重建: {only_new}")
        for k in list(ck & nk)[:2]:
            if current["jobs"][k] != jobs[k]:
                print(f"  值差异 {k}:\n    现 {json.dumps(current['jobs'][k], ensure_ascii=False)[:200]}\n    新 {json.dumps(jobs[k], ensure_ascii=False)[:200]}")
        return 1
    if args.write:
        keep = current.get("key_semantics")
        if keep:
            payload["key_semantics"] = keep
        if current.get("schema"):
            payload["schema"] = current["schema"]
        current_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已落盘并重绑 sources 哈希")
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
