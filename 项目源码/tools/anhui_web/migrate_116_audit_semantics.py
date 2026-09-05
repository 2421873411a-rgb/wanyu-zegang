# -*- coding: utf-8 -*-
"""v17.8.5-RC2 阶段 E：把 three_year_audit.json 里 116 的历史语义迁移为 resolved。

E1. score_lists.unresolved: 116 -> 0，并补 resolved=116 + 方法/证据。
E2. gaps / known_gaps / unverified_scope 移除“成绩附件存在 116 个无法唯一匹配项”
    （已解决项不得继续挂在 active gap）。
E3. 新增 resolution_history（kind=ambiguous_join, status=resolved, 116/116/0）。
E4. coverage.score_unresolved 同步归零；statuses.ambiguous_join 同步归零。

幂等：再次运行时若已迁移则原样退出。全量重生成仍被 legacy_v11 阻断（BLOCKED_BY_EVIDENCE），
本迁移只把源工件校正为当前已解决事实；audit_three_years.py 生成器已同步，
恢复 legacy 后重建即得到一致结果。
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT_PATH = HERE / "data" / "three_year_audit.json"
SCORE_PATH = HERE / "data" / "score_lists.json"
GAP_TITLE_SUB = "无法唯一匹配"
RESOLUTION_EVIDENCE = [
    "tools/anhui_web/data/score_lists.json keyed.resolution_20260905",
    "tools/anhui_web/d2_resolution_report_20260905.txt",
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    audit = load(AUDIT_PATH)
    keyed = (load(SCORE_PATH).get("keyed") or {})
    attributed = sum(
        int(block.get("attributed") or 0)
        for key, block in keyed.items()
        if isinstance(key, str) and key.startswith("resolution_") and isinstance(block, dict)
    )
    still = sum(
        int(block.get("still_ambiguous") or 0)
        for key, block in keyed.items()
        if isinstance(key, str) and key.startswith("resolution_") and isinstance(block, dict)
    )
    assert attributed == 116 and still == 0, (attributed, still)
    unresolved_list = keyed.get("unresolved") or []
    assert isinstance(unresolved_list, list) and len(unresolved_list) == 0, len(unresolved_list)

    cycle_entry = next((c for c in audit.get("cycles", []) if str(c.get("cycle")) == "2026"), None)
    assert cycle_entry is not None, "three_year_audit 缺少 2026 周期"
    stale = [
        cycle_entry.get("score_lists", {}).get("unresolved") == 116,
        (cycle_entry.get("coverage") or {}).get("score_unresolved") == 116,
    ]
    if not any(stale):
        has_history = any(
            rec.get("kind") == "ambiguous_join" and rec.get("status") == "resolved"
            for rec in cycle_entry.get("resolution_history") or []
        )
        if has_history:
            print("已迁移过，无变更。")
            return 0
        raise SystemExit("审计条目既非过期态也无 resolution_history，拒绝盲改，请人工检查")

    # E1：score_lists 归零 + resolved 记录
    sl = cycle_entry.setdefault("score_lists", {})
    assert sl.get("unresolved") == 116, sl.get("unresolved")
    sl["unresolved"] = 0
    sl["resolved"] = attributed
    sl["resolution_method"] = "公告来源定市（raw 附件 pid → scan 标题城市）"
    sl["resolution_evidence"] = RESOLUTION_EVIDENCE

    # E4：coverage 同步
    coverage = cycle_entry.setdefault("coverage", {})
    assert coverage.get("score_unresolved") == 116, coverage.get("score_unresolved")
    coverage["score_unresolved"] = 0

    # E2：active gap / known_gaps / unverified_scope 移除已解决项
    removed = 0
    for field in ("gaps", "known_gaps"):
        items = cycle_entry.get(field) or []
        kept = []
        for item in items:
            title = str(item.get("title") or "")
            kind = str(item.get("kind") or "")
            if kind == "ambiguous_join" or GAP_TITLE_SUB in title:
                removed += 1
                continue
            kept.append(item)
        cycle_entry[field] = kept
    scope = cycle_entry.get("unverified_scope") or []
    kept_scope = [s for s in scope if not (isinstance(s, str) and GAP_TITLE_SUB in s)]
    removed += len(scope) - len(kept_scope)
    cycle_entry["unverified_scope"] = kept_scope

    statuses = cycle_entry.setdefault("statuses", {})
    if "ambiguous_join" in statuses:
        statuses["ambiguous_join"] = 0

    # E3：resolution_history
    cycle_entry["resolution_history"] = [
        {
            "kind": "ambiguous_join",
            "status": "resolved",
            "original_count": attributed,
            "resolved_count": attributed,
            "remaining_count": 0,
            "resolved_at": "2026-09-05",
            "method": "公告来源定市（raw 附件 pid → scan 标题城市）；其中 110 组实为华图源跨市重复收录，幽灵行已标记 record_status=duplicate",
            "evidence": RESOLUTION_EVIDENCE,
        }
    ]

    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(
        f"three_year_audit.json 已迁移：unresolved 116->0（resolved {attributed}），"
        f"gaps/known_gaps/unverified_scope 移除 {removed} 处 116 语义，resolution_history 已写入。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
