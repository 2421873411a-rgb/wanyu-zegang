# -*- coding: utf-8 -*-
"""v17.8.5 阶段 B+C：116 收口（全部投影）+ record_status 生命周期 + active 口径重算。

标定策略：每个推导式先在「含幽灵的全量行」上复算现值，断言一致后才切换 active 口径。
不变式：raw_posts(8511) = active_posts(8401) + excluded_posts(110)。
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[3] / "网站"
PHANTOM_NOTE = "疑似重复收录"


def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def save(p, d): Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    jobs_path = SITE / "data" / "cycles" / "2026" / "jobs.json"
    lite_path = SITE / "data" / "cycles" / "2026" / "jobs_lite.json"
    ov_path = SITE / "data" / "cycles" / "2026" / "overview.json"
    rq_path = SITE / "data" / "audit" / "review-queue.json"

    jobs = load(jobs_path)
    rows = jobs["allMajors"]["rows"]
    raw_total = len(rows)

    # ---- C1/C2：110 行正式生命周期标记（jobs + lite） ----
    marked = 0
    for r in rows:
        if PHANTOM_NOTE in str(r.get("source_note") or ""):
            r["record_status"] = "duplicate"
            r["exclusion_reason"] = "cross_city_source_duplication"
            r["exclusion_evidence"] = "tools/anhui_web/d2_resolution_report_20260905.txt"
            r["excluded_at"] = "2026-09-05"
            marked += 1
    assert marked == 110, marked
    active_rows = [r for r in rows if r.get("record_status") != "duplicate"]
    active_total, excluded_total = len(active_rows), marked
    assert raw_total == active_total + excluded_total, (raw_total, active_total, excluded_total)

    # ---- 标定：推导式在「含幽灵全量行」上必须复现现值 ----
    def compute_meta(sample_rows):
        return {
            "total": len(sample_rows),
            "recruits": sum(int(r.get("num") or 0) for r in sample_rows),
            "examCounts": dict(collections.Counter(str(r.get("exam")) for r in sample_rows)),
            "compJoined": sum(1 for r in sample_rows if r.get("jf") is not None),
            "directed": sum(1 for r in sample_rows if (r.get("dir") or r.get("dirText"))),
            "hukou": sum(1 for r in sample_rows if r.get("hukou")),
            "scoreCoverage": {
                "adv": sum(1 for r in sample_rows if (r.get("competition_observations") or {}).get("examinees", {}).get("value") is not None),
                "bm": sum(1 for r in sample_rows if r.get("bm") is not None),
                "hg": sum(1 for r in sample_rows if r.get("hg") is not None),
                "jf": sum(1 for r in sample_rows if r.get("jf") is not None),
                "hire": sum(1 for r in sample_rows if r.get("hire") is not None),
                "line": sum(1 for r in sample_rows if isinstance(r.get("line"), (int, float)) and r.get("line", 0) > 0),
                "perExam": {
                    exam: {
                        "total": sum(1 for r in sample_rows if str(r.get("exam")) == exam),
                        "adv": sum(1 for r in sample_rows if str(r.get("exam")) == exam and (r.get("competition_observations") or {}).get("examinees", {}).get("value") is not None),
                        "bm": sum(1 for r in sample_rows if str(r.get("exam")) == exam and r.get("bm") is not None),
                        "line": sum(1 for r in sample_rows if str(r.get("exam")) == exam and isinstance(r.get("line"), (int, float)) and r.get("line", 0) > 0),
                    } for exam in ("省考", "国考", "事业编")
                },
            },
        }

    calib = compute_meta(rows)
    old_meta = jobs["allMajors"]["meta"]
    for key in ("examCounts", "directed", "hukou", "recruits", "compJoined"):
        assert calib[key] == old_meta.get(key), (key, calib[key], old_meta.get(key))
    old_cov = old_meta.get("scoreCoverage") or {}
    for key in ("adv", "bm", "hg", "jf"):
        assert calib["scoreCoverage"][key] == old_cov.get(key), (key, calib["scoreCoverage"][key], old_cov.get(key))
    for exam in ("省考", "国考", "事业编"):
        assert calib["scoreCoverage"]["perExam"][exam]["total"] == (old_cov.get("perExam") or {}).get(exam, {}).get("total"), exam
    # line 预期不等（D1 恢复后现库 meta.line=7381 已过期）——记录到报告
    line_delta = calib["scoreCoverage"]["line"] - old_cov.get("line", 0)

    # ---- active 口径 meta ----
    active_meta = compute_meta(active_rows)
    # hire 为构建期录用名单投影（行级无此字段）；幽灵行全为事业编，省考录用数不受影响 → 保留现值
    active_meta["scoreCoverage"]["hire"] = old_cov.get("hire")
    active_meta["raw_total"] = raw_total
    active_meta["excluded"] = excluded_total
    active_meta["record_status_model"] = "wanyu-record-status/v1"
    order = ["total", "recruits", "raw_total", "excluded", "record_status_model",
             "examCounts", "compJoined", "directed", "hukou", "scoreCoverage", "cities", "categories", "cycle", "snapshot"]
    def ordered(meta_src, new_fields):
        out = {k: new_fields[k] for k in order if k in new_fields}
        for k, v in meta_src.items():
            if k not in out:
                out[k] = v
        return out
    jobs["allMajors"]["meta"] = ordered(jobs["allMajors"]["meta"], active_meta)
    save(jobs_path, jobs)

    # jobs_lite：同标记 + 同 meta 口径（lite 行无 score 字段，scoreCoverage 按 0 计？——lite 无 line/adv，保留其原 scoreCoverage 不动，仅重算 total/recruits/examCounts/compJoined/directed/hukou）
    lite = load(lite_path)
    lrows = lite["allMajors"]["rows"]
    lmarked = 0
    for r in lrows:
        if PHANTOM_NOTE in str(r.get("source_note") or "") or (str(r.get("city")) == "马鞍山" and r.get("record_status") != "duplicate" and str(r.get("code")) in set(str(x["code"]) for x in rows if x.get("record_status") == "duplicate")):
            r["record_status"] = "duplicate"
            r["exclusion_reason"] = "cross_city_source_duplication"
            r["exclusion_evidence"] = "tools/anhui_web/d2_resolution_report_20260905.txt"
            r["excluded_at"] = "2026-09-05"
            lmarked += 1
    assert lmarked == 110, lmarked
    lactive = [r for r in lrows if r.get("record_status") != "duplicate"]
    lmeta = lite["allMajors"]["meta"]
    lmeta["total"] = len(lactive)
    lmeta["recruits"] = sum(int(r.get("num") or 0) for r in lactive)
    lmeta["examCounts"] = dict(collections.Counter(str(r.get("exam")) for r in lactive))
    lmeta["raw_total"] = len(lrows)
    lmeta["excluded"] = lmarked
    lmeta["record_status_model"] = "wanyu-record-status/v1"
    save(lite_path, lite)

    # ---- B：overview / review-queue 投影收口 ----
    ov = load(ov_path)
    ov["allMajors"]["meta"] = ordered(ov["allMajors"]["meta"], active_meta)
    ov["auditSummary"]["score_unresolved"] = 0
    ov["auditSummary"]["resolved_score_count"] = 116
    rt = ov.get("cycleRuntime") or {}
    if rt:
        rt["row_count"] = active_total
        rt["raw_row_count"] = raw_total
        rt["score_unresolved"] = 0
    save(ov_path, ov)

    rq = load(rq_path)
    summ = rq.setdefault("summary", {})
    summ["unresolved_score_count"] = 0
    summ["resolved_score_count"] = 116
    for item in rq.get("items", []):
        if item.get("kind") == "ambiguous_join":
            item["status"] = "resolved"
            item["resolved_at"] = "2026-09-05"
            item["remaining_count"] = 0
            item["resolution"] = "116 组撞码经公告来源定市全部归属（110 组实为华图源跨市重复收录，幽灵行在马鞍山侧已标记 duplicate）；证据 tools/anhui_web/d2_resolution_report_20260905.txt"
    save(rq_path, rq)

    print(f"[C] jobs 标记 {marked} 行 / lite 标记 {lmarked} 行 | raw {raw_total} = active {active_total} + excluded {excluded_total}")
    print(f"[C] active meta: total {active_meta['total']} | recruits {active_meta['recruits']} | examCounts {active_meta['examCounts']}")
    print(f"[标定] 全部标定断言通过；scoreCoverage.line 修正 +{line_delta}（D1 恢复后现库 meta 已过期，本次同步）")
    print(f"[B] overview.auditSummary 0/116；review-queue summary 0/116，ambiguous_join 项标记 resolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
