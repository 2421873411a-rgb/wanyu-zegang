# -*- coding: utf-8 -*-
"""从 2026 现库 raw 行生成 record_status_overrides.json（生命周期构建输入）。

判定基准：华图职位库快照 2026-08-29 的 source_note 自带“疑似重复收录”标注
（与六安同码同单位，成绩归属六安）。本工具把它固化为显式 job_id 清单，
并断言与现库 record_status=duplicate 集合一致，保证 builder 重放时零漂移。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.anhui_web.record_lifecycle import OVERRIDES_SCHEMA  # noqa: E402

SITE = HERE.parents[2] / "网站"
DUPLICATE_MARKER = "疑似重复收录"
EXCLUSION_NOTE_BASIS = (
    "华图职位库快照 2026-08-29 source_note「疑似重复收录（与六安同码同单位，成绩归属六安）」；"
    "D2 复核结论：110 组跨市重复收录，幽灵行全部在马鞍山侧"
)


def main() -> int:
    rows = json.loads((SITE / "data" / "cycles" / "2026" / "jobs.json").read_text(encoding="utf-8"))["allMajors"]["rows"]
    from_note = sorted(str(r["job_id"]) for r in rows if DUPLICATE_MARKER in str(r.get("source_note") or ""))
    from_status = sorted(str(r["job_id"]) for r in rows if r.get("record_status") == "duplicate")
    if not from_note:
        raise SystemExit("未找到任何疑似重复收录标记行；现库可能已被清洗，拒绝生成空 overrides")
    if from_note != from_status:
        diff = set(from_note).symmetric_difference(from_status)
        raise SystemExit(f"source_note 标记与 record_status 集合不一致：{sorted(diff)[:10]}")
    sample = next(r for r in rows if str(r["job_id"]) == from_note[0])
    payload = {
        "schema": OVERRIDES_SCHEMA,
        "generated_from": "网站/data/cycles/2026/jobs.json source_note 标记 + record_status 现状交叉核对",
        "cycles": {
            "2026": {
                "basis": EXCLUSION_NOTE_BASIS,
                "duplicate_job_ids": from_note,
                "count": len(from_note),
                "exclusion_reason": "cross_city_source_duplication",
                "exclusion_evidence": sample.get("exclusion_evidence") or "tools/anhui_web/d2_resolution_report_20260905.txt",
                "excluded_at": sample.get("excluded_at") or "2026-09-05",
            }
        },
    }
    out = HERE / "data" / "record_status_overrides.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"record_status_overrides.json：{len(from_note)} 个 duplicate job_id，reason/evidence 与现库一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
