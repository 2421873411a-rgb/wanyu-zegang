# -*- coding: utf-8 -*-
"""record_status_overrides.json 生成器 v2（RC3 阶段 J：证据链去循环）。

v1 的问题（外部复核指出）：从**网站成品** jobs.json 读取 source_note +
record_status 生成 overrides —— 产物→输入的循环依赖，且与 phantom_codes
构成双真源。

v2 证据链（不读任何 网站/ 产物、不读任何派生模块）：
  canonical/cycles/2026.json rows（raw 行，结构化真源）
    + 同码同单位跨市孪生 + 入围线(line)归属不对称（官方市 line>0，幽灵行 line 空）
  ⇒ 独立重推出 duplicate 集合（setB）

三重等式证明（任何一侧不等即 FAIL）：
  setA（行内 D2 标记 source_note「疑似重复收录」）
  == setB（本工具独立重推）
  == setC（已提交 overrides 的 duplicate_job_ids）

交叉核对：score_lists keyed.resolution_20260905.attributed == 116 / still_ambiguous == 0
（116 撞码全部归属；其中 110 组为跨市重复收录幽灵行）。
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from tools.anhui_web.invariants import BuildInvariantError  # noqa: E402
from tools.anhui_web.record_lifecycle import OVERRIDES_SCHEMA  # noqa: E402
from tools.anhui_web.unified_cycle_bundle import load_canonical_doc  # noqa: E402

PROJECT_ROOT = HERE.parents[1]
SITE = PROJECT_ROOT.parent / "网站"
DUPLICATE_MARKER = "疑似重复收录"
EXCLUSION_NOTE_BASIS = (
    "D2 证据链（RC3-J）：华图职位库快照 2026-08-29 行 × 同码同单位跨市孪生 × "
    "入围线(line)归属不对称——官方市 line>0、幽灵行 line 为空；与 keyed.resolution_20260905 "
    "(attributed=116/still_ambiguous=0) 交叉核对；110 组幽灵行全部在马鞍山侧"
)


def main() -> int:
    doc = load_canonical_doc(PROJECT_ROOT, "2026")
    rows = doc["all_majors"]["rows"]

    def has_line(row: dict) -> bool:
        value = row.get("line")
        return isinstance(value, (int, float)) and value > 0

    twins: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for row in rows:
        twins[(str(row.get("code") or ""), str(row.get("unit") or ""))].append(row)

    set_a = sorted(str(r["job_id"]) for r in rows if DUPLICATE_MARKER in str(r.get("source_note") or ""))
    set_b: list[str] = []
    for row in rows:
        note = str(row.get("source_note") or "")
        if "华图职位库快照" not in note or has_line(row):
            continue
        official_twins = [
            t
            for t in twins[(str(row.get("code") or ""), str(row.get("unit") or ""))]
            if t is not row and str(t.get("city") or "") != str(row.get("city") or "") and has_line(t)
        ]
        if official_twins:
            set_b.append(str(row["job_id"]))
    set_b = sorted(set_b)

    overrides_path = HERE / "data" / "record_status_overrides.json"
    overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    set_c = sorted(str(x) for x in overrides["cycles"]["2026"]["duplicate_job_ids"])

    keyed = json.loads((HERE / "data" / "score_lists.json").read_text(encoding="utf-8")).get("keyed") or {}
    resolution = keyed.get("resolution_20260905") or {}
    attributed = int(resolution.get("attributed") or 0)
    still = int(resolution.get("still_ambiguous") or 0)

    problems = []
    if set_a != set_b:
        problems.append(f"setA(行内标记 {len(set_a)}) != setB(证据重推 {len(set_b)})；差集 A-B={sorted(set(set_a)-set(set_b))[:5]} B-A={sorted(set(set_b)-set(set_a))[:5]}")
    if set_b != set_c:
        problems.append(f"setB(证据重推 {len(set_b)}) != setC(已提交 overrides {len(set_c)})；overrides 必须由证据重新生成")
    if attributed != 116 or still != 0:
        problems.append(f"keyed.resolution 交叉核对失败：attributed={attributed} still_ambiguous={still}（预期 116/0）")
    cities = {str(next(r for r in rows if str(r.get("job_id")) == j).get("city")) for j in set_b}
    if cities != {"马鞍山"}:
        problems.append(f"幽灵行城市分布异常：{sorted(cities)}（D2 结论=全部在马鞍山）")
    if problems:
        raise BuildInvariantError("生命周期证据链断裂：\n- " + "\n- ".join(problems))

    payload = {
        "schema": OVERRIDES_SCHEMA,
        "generator": "gen_record_status_overrides.py v2（canonical 证据链，零产物输入）",
        "cycles": {
            "2026": {
                "basis": EXCLUSION_NOTE_BASIS,
                "duplicate_job_ids": set_b,
                "count": len(set_b),
                "exclusion_reason": "cross_city_source_duplication",
                "exclusion_evidence": "tools/anhui_web/d2_resolution_report_20260905.txt",
                "excluded_at": "2026-09-05",
                "proof": {
                    "set_marker": len(set_a),
                    "set_derived": len(set_b),
                    "set_committed": len(set_c),
                    "exact_equality": True,
                    "collision_attributed": attributed,
                    "still_ambiguous": still,
                },
            }
        },
    }
    overrides_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"overrides v2 已重写：{len(set_b)} 组；三重等式成立（标记=重推=提交）；交叉核对 attributed=116/still=0；幽灵行城市=马鞍山")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
