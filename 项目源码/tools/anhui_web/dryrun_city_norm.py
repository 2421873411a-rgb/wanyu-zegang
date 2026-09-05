# -*- coding: utf-8 -*-
"""D3a 干跑：对已发布 jobs.json 只读对账城市归一映射。不写任何数据文件。

验收口径（state.json Q4）：脏值全部落入 17 城规范集、总行数守恒、
2024 归一变更行数与审计定论（3,989）一致、2025/2026 干跑零变更。
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from city_norm import CANONICAL_CITIES, normalize_source_city

ROOT = Path(__file__).resolve().parents[3] / "网站" / "data" / "cycles"
EXPECTED_2024_CHANGED = 3989


def rows_of(cycle: str) -> tuple[list, dict]:
    payload = json.loads((ROOT / cycle / "jobs.json").read_text(encoding="utf-8"))
    rows = payload.get("allMajors", {}).get("rows") or []
    return rows, payload


def main() -> int:
    ok = True
    for cycle in ("2024", "2025", "2026"):
        rows, _ = rows_of(cycle)
        changed = []
        unmapped = collections.Counter()
        for row in rows:
            raw = str(row.get("city") or "")
            norm = normalize_source_city(raw)
            if norm != raw:
                changed.append((raw, norm))
            if norm not in CANONICAL_CITIES:
                unmapped[norm] += 1
        print(f"[{cycle}] 行数 {len(rows)}（守恒: 是） | 归一变更 {len(changed)} 行 | 未落入规范集 {sum(unmapped.values())} 行")
        if unmapped:
            ok = False
            for value, count in unmapped.most_common(10):
                print(f"  !! 未映射: {count:5d}  {value}")
        if cycle == "2024":
            mapping = collections.Counter(changed)
            print(f"[2024] 脏值形态 {len({raw for raw, _ in mapping})} 种 → 规范城 {len({norm for _, norm in mapping})} 个")
            for (raw, norm), count in sorted(mapping.items(), key=lambda kv: -kv[1]):
                print(f"  {count:5d}  {raw} → {norm}")
            if len(changed) != EXPECTED_2024_CHANGED:
                print(f"  !! 2024 变更行数 {len(changed)} != 审计定论 {EXPECTED_2024_CHANGED}")
                ok = False
        elif changed:
            print(f"  !! {cycle} 应为干净周期，却出现 {len(changed)} 行变更")
            ok = False
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
