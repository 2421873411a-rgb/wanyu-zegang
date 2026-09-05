# -*- coding: utf-8 -*-
"""PDF 成绩附件解析器：收割器此前跳过 PDF（13 个文件未解析），本脚本补齐。

口径与 harvest_syb_scores.agg 一致：adv=行数（有效人数）、top=最高、lo=正分最低；
标题含 复审/入围/面试人员 → review（lo 优先作为入围线），否则 rank。
合并策略只增不减：仅补充侧料中缺失的代码；部署数据仅写回仍为哨兵/缺失且代码双侧唯一的行。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from surgical_repair_20260905 import score_observation  # noqa: E402

SITE = HERE.parents[2] / "网站"
RAW = HERE / "data" / "raw_syb_fugao"
PID_TITLE_RE = re.compile(r"^syb_(\d{5})\.pdf$")
CODE_RE = re.compile(r"^\d{6,8}$")
NUM_RE = re.compile(r"^\d{1,3}(?:\.\d{1,2})?$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_pdf(path: Path) -> dict[str, list[float]]:
    """返回 code -> [分数列表]（全文件聚合）。表格优先，无表格页走文本行兜底。"""
    scores: dict[str, list[float]] = defaultdict(list)
    line_re = re.compile(r"(\d{6,8})\s+(?:(?:\d{6,}\S*\s+)?){1,4}(\d{1,3}(?:\.\d{1,2})?)\s*$")
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            if tables:
                for table in tables:
                    for row in table:
                        cells = [str(c).strip() if c else "" for c in row or []]
                        code = next((c for c in cells if CODE_RE.match(c)), None)
                        if not code:
                            continue
                        nums = []
                        for c in cells:
                            if c != code and NUM_RE.match(c):
                                nums.append(float(c))
                        if nums:
                            scores[code].append(max(nums))
            else:
                for line in (page.extract_text() or "").splitlines():
                    m = line_re.search(line.strip())
                    if m and CODE_RE.match(m.group(1)):
                        scores[m.group(1)].append(float(m.group(2)))
    return scores


def main() -> int:
    report = []
    targets = set(json.loads((HERE / "data" / "sentinel_codes_2026.json").read_text(encoding="utf-8")))
    scan = json.loads((HERE / "data" / ".zhaokao_syb_scan.json").read_text(encoding="utf-8"))

    rank: dict[str, list[float]] = defaultdict(list)
    review: dict[str, list[float]] = defaultdict(list)
    for f in sorted(RAW.glob("*.pdf")):
        m = PID_TITLE_RE.match(f.name)
        if not m:
            continue
        pid = m.group(1)
        title = str((scan.get(pid) or {}).get("title") or "")
        is_review = any(k in title for k in ("复审", "入围", "面试人员"))
        file_scores = parse_pdf(f)
        hit = {c: v for c, v in file_scores.items() if c in targets}
        report.append(f"[pdf] {f.name} {title[:36]} → 哨兵码命中 {len(hit)}")
        bucket = review if is_review else rank
        for code, values in hit.items():
            bucket[code].extend(values)

    codes = set(rank) | set(review)
    report.append(f"[pdf] 合计命中哨兵码 {len(codes)}（rank {len(rank)} / review {len(review)}）")

    # 合并进侧料（只增不减：缺失代码新增；已存在但 line 为空的行补 line/adv/top）
    side_path = HERE / "data" / "syb2026_daxian_all.json"
    side = json.loads(side_path.read_text(encoding="utf-8"))
    existing = {str(p["code"]): p for p in side["positions"]}
    added_sidecar, patched_sidecar = 0, 0
    for code in sorted(codes):
        r_vals = rank.get(code, [])
        v_vals = review.get(code, [])
        pos_r = [x for x in r_vals if x > 0]
        pos_v = [x for x in v_vals if x > 0]
        line = (min(pos_v) if pos_v else None) or (min(pos_r) if pos_r else None)
        adv = len(r_vals) or len(v_vals) or None
        top = max(pos_r) if pos_r else (max(v_vals) if v_vals else None)
        if code not in existing:
            side["positions"].append({
                "code": code, "adv": adv, "top": top, "avg": None, "line": line,
                "rank_src": bool(r_vals), "review_src": bool(v_vals), "src_pdf": True,
            })
            added_sidecar += 1
        else:
            st = existing[code]
            if not st.get("line") and line:
                st["line"] = line
                st.setdefault("adv", adv)
                st.setdefault("top", top)
                st["src_pdf"] = True
                patched_sidecar += 1
    side["total"] = len(side["positions"])
    side["repair_note"] = (side.get("repair_note") or "") + "；2026-09-05 PDF 增量：13 个此前被跳过的 PDF 附件已解析并只增合并"
    side_path.write_text(json.dumps(side, ensure_ascii=False, indent=1), encoding="utf-8")
    report.append(f"[side] 侧料新增 {added_sidecar} 码（总量 {side['total']}）")

    # 写回部署数据（哨兵/缺失 且 代码双侧唯一）
    jobs_path = SITE / "data" / "cycles" / "2026" / "jobs.json"
    data = json.loads(jobs_path.read_text(encoding="utf-8"))
    rows = data["allMajors"]["rows"]
    cc = defaultdict(int)
    for r in rows:
        if r.get("exam") == "事业编":
            cc[str(r["code"])] += 1
    side_map = {str(p["code"]): p for p in side["positions"]}
    attributed = 0
    for r in rows:
        if r.get("exam") != "事业编":
            continue
        so = r.get("score_observation") or {}
        if so.get("status") not in {"suspected_sentinel", "unavailable"}:
            continue
        code = str(r["code"])
        s = side_map.get(code)
        if not s or cc[code] != 1:
            continue
        line = s.get("line")
        if not line or line <= 0:
            continue
        if r.get("adv") is None:
            r["adv"] = s.get("adv")
        if r.get("top") is None:
            r["top"] = s.get("top")
        r["line"] = line
        r["score_observation"] = score_observation(r.get("exam"), float(line))
        attributed += 1
    jobs_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    report.append(f"[jobs] 2026 部署数据写回 {attributed} 行")

    out = HERE / "pdf_score_report_20260905.txt"
    out.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"报告 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
