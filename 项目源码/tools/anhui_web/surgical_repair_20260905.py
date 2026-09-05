# -*- coding: utf-8 -*-
"""外科手术式数据修复（2026-09-05 · 升级规划 P1-D 线）

D1 哨兵恢复：收割排零修复（harvest_syb_scores.py agg() 排除缺考 0 分）后的重收割结果，
  与修复前底料（syb2026_daxian_all.pre_fix.json / .pre0830.json）做「只增不减」合并，
  按 build_pages.py v9.9.2 的 join 口径（事业编 + 代码双侧唯一 + 只补缺不覆盖）写回部署数据；
  分数标注复刻部署口径：事业单位 120–300 → comparable/syb_300，越界 → incompatible_scale。
D3 2024 城市归一：city_norm 规则应用于行级 city（干跑已验证 3,989/3,989 全覆盖、聚合层零影响）。
D6a floor 哨兵：floor==0 → null（学历层级未解析）。
发布：site-manifest 哈希/字节数重发布；audit.json 诚实更新可重算字段并追加修复记录。
原文件由 git 历史保全（上一提交可整体回滚）。
"""
from __future__ import annotations

import collections
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from city_norm import normalize_source_city  # noqa: E402

SITE = HERE.parents[2] / "网站"
DATA = SITE / "data"
CYC = DATA / "cycles"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def score_observation(exam: str, value: float) -> dict:
    """复刻部署口径的分数标注（事业单位 120–300 → comparable/syb_300）。"""
    base = {"metric_type": "cutoff", "stage": "cutoff", "unit": "分", "value": value, "scale_id": None}
    if 120 <= value <= 300:
        return {**base, "status": "comparable", "scale_id": "syb_300", "reason": "事业单位笔试合成分范围"}
    return {**base, "status": "incompatible_scale", "reason": "数值存在，但不符合当前模拟器的已知量纲"}


def main() -> int:
    report: list[str] = []

    # ---- 1. 只增不减合并收割底料 ----
    merged_path = HERE / "data" / "syb2026_daxian_all.json"
    current = load(merged_path)
    base = None
    for name in ("syb2026_daxian_all.pre_fix.json", "syb2026_daxian_all.pre0830.json"):
        p = HERE / "data" / name
        if p.is_file():
            base = load(p)
            report.append(f"[merge] 底料 = {name}（{len(base['positions'])} 行）")
            break
    assert base is not None, "缺少修复前底料"
    base_map = {str(r["code"]): r for r in base["positions"]}
    recovered_in_sidecar = 0
    for row in current["positions"]:
        code = str(row["code"])
        old = base_map.get(code)
        if old is None:
            base_map[code] = row  # 新增键原样并入
        elif not old.get("line") and row.get("line"):
            old["line"] = row["line"]          # 恢复
            if row.get("avg") is not None:
                old["avg"] = row["avg"]
            recovered_in_sidecar += 1
    base["positions"] = list(base_map.values())
    base["total"] = len(base["positions"])
    base["repair_note"] = "2026-09-05 只增不减合并：底料全量保留 + 排零重收割的 line/avg 恢复覆盖"
    save(merged_path, base)
    report.append(f"[merge] 合并后 {base['total']} 行（恢复 line {recovered_in_sidecar} 条，零删减）")

    # ---- 2. 2026 jobs.json：哨兵恢复 + floor null ----
    jobs26_path = CYC / "2026" / "jobs.json"
    d26 = load(jobs26_path)
    rows = d26["allMajors"]["rows"]
    fg_plain: dict[str, list[dict]] = collections.defaultdict(list)
    for p in base["positions"]:
        fg_plain[str(p["code"])].append(p)
    code_counts = collections.Counter(str(r["code"]) for r in rows if r.get("exam") == "事业编")
    floor_fixed = 0
    repaired: list[tuple[str, str, str, float]] = []
    for r in rows:
        if r.get("floor") == 0:
            r["floor"] = None
            floor_fixed += 1
        if r.get("exam") != "事业编":
            continue
        so = r.get("score_observation") or {}
        if so.get("status") not in {"suspected_sentinel", "unavailable"}:
            continue
        code = str(r["code"])
        cands = fg_plain.get(code, [])
        if len(cands) != 1 or code_counts.get(code, 0) != 1:
            continue  # 撞码/歧义：保持未知，绝不猜（v9.9.2 口径）
        line = cands[0].get("line")
        if not line or line <= 0:
            continue
        if r.get("adv") is None:
            r["adv"] = cands[0].get("adv")
        if r.get("top") is None:
            r["top"] = cands[0].get("top")
        r["line"] = line
        r["score_observation"] = score_observation(r.get("exam"), float(line))
        repaired.append((code, str(r.get("city")), so.get("status"), float(line)))
    save(jobs26_path, d26)
    statuses = collections.Counter((r.get("score_observation") or {}).get("status") for r in rows)
    report.append(f"[D1] 2026 哨兵/缺失恢复 {len(repaired)} 行；floor null 化 {floor_fixed} 行")
    report.append(f"[D1] 修复后状态分布: {dict(statuses)}")
    for code, city, old_status, line in repaired[:20]:
        report.append(f"  样例 {code} {city} {old_status} → line={line}")

    # ---- 3. 2024 jobs.json：城市归一 ----
    jobs24_path = CYC / "2024" / "jobs.json"
    d24 = load(jobs24_path)
    rows24 = d24["allMajors"]["rows"]
    canon = {"合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山",
             "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城", "省直"}
    city_fixed = 0
    unmapped = collections.Counter()
    for r in rows24:
        raw = str(r.get("city") or "")
        norm = normalize_source_city(raw)
        if norm != raw:
            r["city"] = norm
            city_fixed += 1
        if norm not in canon:
            unmapped[norm] += 1
    save(jobs24_path, d24)
    report.append(f"[D3] 2024 城市归一 {city_fixed} 行；未落入规范集 {sum(unmapped.values())} 行")
    assert sum(unmapped.values()) == 0, f"存在未映射城市: {dict(unmapped)}"

    # ---- 4. manifest 哈希重发布 ----
    manifest_path = DATA / "site-manifest.json"
    man = load(manifest_path)
    for cyc_entry in man["cycles"]:
        year = str(cyc_entry["cycle"])
        jp = CYC / year / "jobs.json"
        if year in {"2024", "2026"}:
            entry = cyc_entry["modules"]["jobs"]
            entry["bytes"] = jp.stat().st_size
            entry["sha256"] = sha256(jp)
            cyc_entry["bytes"] = jp.stat().st_size
            cyc_entry["sha256"] = entry["sha256"]
            cyc_entry["data"] = f"data/cycles/{year}/jobs.json"
        if year == "2026":
            cyc_entry["score_unresolved"] = sum(
                1 for r in rows
                if r.get("exam") == "事业编"
                and code_counts.get(str(r["code"]), 0) > 1
                and (r.get("score_observation") or {}).get("status") in {"suspected_sentinel", "unavailable"}
            )
    save(manifest_path, man)
    report.append("[manifest] 2024/2026 jobs 哈希+字节数已重发布；2026 score_unresolved 重算")

    # ---- 5. audit.json 诚实更新 ----
    audit_path = CYC / "2026" / "audit.json"
    audit = load(audit_path)
    sl = audit.get("scoreLists") or {}
    if isinstance(sl, dict):
        if "sentinel" in sl or "suspected_sentinel" in sl:
            sl["suspected_sentinel"] = statuses.get("suspected_sentinel", 0)
        if "line_coverage" in sl:
            sl["line_coverage"] = sum(1 for r in rows if (r.get("score_observation") or {}).get("value"))
        sl["repair_20260905"] = {
            "recovered_rows": len(repaired),
            "merge_policy": "只增不减（pre_fix/pre0830 底料 + 排零重收割 line 恢复）",
            "scale_gate": "事业单位 120-300 → comparable/syb_300；越界 → incompatible_scale",
        }
        audit["scoreLists"] = sl
    gaps = audit.setdefault("gaps", [])
    gaps.append({
        "kind": "surgical_repair_20260905",
        "detail": f"哨兵恢复 {len(repaired)} 行（重收割合并）；floor null {floor_fixed} 行；"
                  f"抽样见修复报告。原值由 git 历史（v17.7.2-baseline）保全。",
    })
    save(audit_path, audit)
    report.append("[audit] 2026 audit.json scoreLists 修复记录已追加")

    out = Path(__file__).with_name("repair_report_20260905.txt")
    out.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"报告 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
