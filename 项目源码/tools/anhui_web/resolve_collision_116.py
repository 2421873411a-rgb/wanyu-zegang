# -*- coding: utf-8 -*-
"""D2 六安/马鞍山 116 组撞码成绩归属（公告来源定市法）。

链路：raw_syb_fugao/syb_{pid}.xls(x) ← .zhaokao_syb_scan.json[pid].title（含城市名）
→ 解析每个附件的岗位代码集合 → code → 来源城市集合。
- 唯一城市 → 成绩归属该市行；另一市同码同行同单位行打「疑似重复收录」标记（不删除，待官方职位表核对）
- 两个城市都出现 → 仍属真歧义，保持 unresolved（绝不猜）
- 无附件可解析 → 保持 unresolved
铁律：只增不减、歧义不猜、全部变更留 audit 记录。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harvest_syb_scores import parse_excel  # noqa: E402
from surgical_repair_20260905 import score_observation  # noqa: E402

SITE = HERE.parents[2] / "网站"
CITIES = ("合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆",
          "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城")
RAW = HERE / "data" / "raw_syb_fugao"
PID_RE = re.compile(r"^syb_(\d{5})\.(xls|xlsx)$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    report = []
    scan = json.loads((HERE / "data" / ".zhaokao_syb_scan.json").read_text(encoding="utf-8"))

    # 1) 解析全部带 pid 的原始附件 → code → {城市: set(pid)}
    code_cities: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    parsed_files = 0
    for f in sorted(RAW.iterdir()):
        m = PID_RE.match(f.name)
        if not m:
            continue
        pid = m.group(1)
        title = str((scan.get(pid) or {}).get("title") or "")
        city = next((c for c in CITIES if c in title), None)
        if not city:
            continue
        df = parse_excel(f)
        if df is None or not len(df):
            continue
        parsed_files += 1
        for code in set(df["code"].astype(str)):
            code_cities[code][city].add(pid)

    # 2) 读 unresolved 清单逐个归类
    sl_path = HERE / "data" / "score_lists.json"
    sl = json.loads(sl_path.read_text(encoding="utf-8"))
    unresolved = sl["keyed"]["unresolved"]
    resolved, ambiguous, missing = [], [], []
    for u in unresolved:
        code = str(u["code"])
        cities = code_cities.get(code, {})
        if not cities:
            missing.append(code)
        elif len(cities) == 1:
            resolved.append((code, next(iter(cities))))
        else:
            ambiguous.append((code, sorted(cities)))
    report.append(f"[解析] 带城市附件 {parsed_files} 个；116 撞码：唯一城市 {len(resolved)} | 双城歧义 {len(ambiguous)} | 无附件 {len(missing)}")

    # 3) 侧料（合并后的 daxian）拿成绩值
    side = json.loads((HERE / "data" / "syb2026_daxian_all.json").read_text(encoding="utf-8"))
    side_map = {str(p["code"]): p for p in side["positions"]}

    # 4) 写回 2026 部署数据
    jobs_path = SITE / "data" / "cycles" / "2026" / "jobs.json"
    data = json.loads(jobs_path.read_text(encoding="utf-8"))
    rows = data["allMajors"]["rows"]
    cc = defaultdict(int)
    for r in rows:
        if r.get("exam") == "事业编":
            cc[str(r["code"])] += 1
    attributed, flagged = 0, 0
    for code, owner in resolved:
        s = side_map.get(code) or {}
        line = s.get("line")
        pair = [r for r in rows if r.get("exam") == "事业编" and str(r["code"]) == code]
        owner_rows = [r for r in pair if str(r.get("city")) == owner]
        other_rows = [r for r in pair if str(r.get("city")) != owner]
        for r in owner_rows:
            if r.get("line") in (None, 0):
                if r.get("adv") is None:
                    r["adv"] = s.get("adv")
                if r.get("top") is None:
                    r["top"] = s.get("top")
                if line:
                    r["line"] = line
                    r["score_observation"] = score_observation(r.get("exam"), float(line))
                    attributed += 1
        owner_unit = str(owner_rows[0].get("unit")) if owner_rows else ""
        for r in other_rows:
            if owner_unit and str(r.get("unit")) == owner_unit and "疑似重复收录" not in str(r.get("source_note") or ""):
                r["source_note"] = f"{r.get('source_note') or '官方职位表'}；疑似重复收录（与{owner}同码同单位，成绩归属{owner}），待官方职位表核对"
                flagged += 1
    jobs_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    report.append(f"[D2] 成绩归属 {attributed} 行；幽灵重复行打标 {flagged} 行（不删除，待官方核对）")

    # 5) unresolved 更新：仅真歧义与无附件保留
    sl["keyed"]["unresolved"] = [u for u in unresolved if str(u["code"]) in set(ambiguous and [a for a, _ in ambiguous]) | set(missing)]
    sl["keyed"]["resolution_20260905"] = {
        "attributed": len(resolved), "still_ambiguous": len(ambiguous), "no_attachment": len(missing),
        "method": "公告来源定市（raw 附件 pid → scan 标题城市）",
    }
    sl_path.write_text(json.dumps(sl, ensure_ascii=False, indent=1), encoding="utf-8")
    report.append(f"[D2] keyed.unresolved 116 → {len(sl['keyed']['unresolved'])}（歧义 {len(ambiguous)} + 无附件 {len(missing)}）")

    # 6) manifest：jobs / audit 哈希重发 + score_unresolved 同步
    mp = SITE / "data" / "site-manifest.json"
    man = json.loads(mp.read_text(encoding="utf-8"))
    for c in man["cycles"]:
        if str(c["cycle"]) == "2026":
            for mod in ("jobs", "audit"):
                p = SITE / c["modules"][mod]["data"]
                c["modules"][mod]["bytes"] = p.stat().st_size
                c["modules"][mod]["sha256"] = sha256(p)
            c["data"] = "data/cycles/2026/jobs.json"
            c["sha256"] = c["modules"]["jobs"]["sha256"]
            c["bytes"] = c["modules"]["jobs"]["bytes"]
            c["score_unresolved"] = len(sl["keyed"]["unresolved"])
    mp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    report.append("[manifest] 2026 jobs/audit 哈希重发，score_unresolved 已同步")

    out = HERE / "d2_resolution_report_20260905.txt"
    out.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"报告 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
