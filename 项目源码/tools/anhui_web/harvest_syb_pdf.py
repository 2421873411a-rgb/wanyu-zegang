# -*- coding: utf-8 -*-
"""事业编 PDF 成绩公告收割：下载 PDF → PyMuPDF 提取表格 → 合并进 syb2026_daxian_all.json。

用法：python harvest_syb_pdf.py 37378 37381 ...
合并规则与 harvest_syb_merge.py 一致：新 code 追加，已有 code 只补缺失字段。
"""
from __future__ import annotations

import json
import re
import shutil
import ssl
import sys
import time
import urllib.request
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw_syb_fugao"
SCAN = HERE / "data" / ".zhaokao_syb_scan.json"
OUT = HERE / "data" / "syb2026_daxian_all.json"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"


def get(url: str, binary: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.xduim.com/"})
    data = urllib.request.urlopen(req, timeout=120, context=CTX).read()
    return data if binary else data.decode("utf-8", "ignore")


CODE_RE = re.compile(r"^\d{3,9}$")


def _tables_on_page(page):
    try:
        tabs = page.find_tables()
        if tabs and tabs.tables:
            return [t.extract() for t in tabs.tables]
    except Exception:  # noqa: BLE001
        pass
    try:
        tabs = page.find_tables(strategy="text")
        return [t.extract() for t in tabs.tables]
    except Exception:  # noqa: BLE001
        return []


def pdf_rows(path: Path):
    """从 PDF 提取 (code, score=总分)：延续页无表头时沿用最近一次识别的列位。"""
    doc = pymupdf.open(path)
    rows: list[tuple[str, float]] = []
    code_ci = si = None
    pages_with_table = 0
    for page in doc:
        tables = _tables_on_page(page)
        if tables:
            pages_with_table += 1
        for data in tables:
            if not data or len(data) < 2:
                continue
            # 表头可能带合并标题行：在前 4 行里找含 岗位代码/职位代码 的行
            hidx = None
            for i, row in enumerate(data[:4]):
                joined = "".join(re.sub(r"\s", "", str(x or "")) for x in (row or []))
                if ("岗位代码" in joined or "职位代码" in joined) and ("总分" in joined or "成绩" in joined):
                    hidx = i
                    break
            if hidx is not None:
                hdr = [re.sub(r"\s", "", str(x or "")) for x in (data[hidx] or [])]
                code_ci = next((i for i, h in enumerate(hdr) if "岗位代码" in h or "职位代码" in h), None)
                score_cols = [i for i, h in enumerate(hdr) if "总分" in h or "成绩" in h or "分数" in h]
                si = next((c for c in score_cols if "总分" in hdr[c]),
                          next((c for c in score_cols if "笔试成绩" in hdr[c]), score_cols[-1] if score_cols else None))
                data = data[hidx + 1:]
            if code_ci is None or si is None:
                continue
            for row in data:
                if row is None or code_ci >= len(row) or si >= len(row):
                    continue
                code = re.sub(r"\s", "", str(row[code_ci] or ""))
                if not CODE_RE.match(code):
                    continue
                try:
                    rows.append((code, float(str(row[si]).strip())))
                except ValueError:
                    continue
    doc.close()
    print(f"   [debug] 有表格页 {pages_with_table}，提取 {len(rows)} 行")
    # 去重（同 code 同分保留一条）
    seen, out = set(), []
    for c, s in rows:
        if (c, s) not in seen:
            seen.add((c, s))
            out.append((c, s))
    return out


def main() -> int:
    ids = [int(a) for a in sys.argv[1:] if a.isdigit()]
    if not ids:
        print("用法: python harvest_syb_pdf.py <公告ID...>")
        return 1
    RAW.mkdir(parents=True, exist_ok=True)
    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    out = json.loads(OUT.read_text(encoding="utf-8"))
    backup = OUT.with_name("syb2026_daxian_all.backup.json")
    shutil.copyfile(OUT, backup)
    by_code = {str(p["code"]): p for p in out["positions"]}
    # 白名单 = 华图事业编职位表宇宙（防止跨考试杂码入库）
    syb = json.load(open(HERE / "data" / "huatu_syb_2026.json", encoding="utf-8"))
    allow = {str(r["code"]): (r.get("city") or "?") for r in syb["positions"]}

    added = updated = 0
    import statistics
    for pid in ids:
        info = scan.get(str(pid))
        if not info:
            print(f"{pid}: 无扫描记录")
            continue
        print(f"== {pid}: {info.get('title', '')[:44]}")
        done = False
        for au in info.get("atts", [])[:2]:
            try:
                blob = get(au, binary=True)
                if blob[:4] != b"%PDF":
                    print("   非 PDF，跳过:", au[-40:])
                    continue
                dest = RAW / f"sybpdf_{pid:05d}.pdf"
                dest.write_bytes(blob)
                rows = pdf_rows(dest)
                if not rows:
                    print("   未提取到行")
                    continue
                is_review = "复审" in info.get("title", "") or "入围" in info.get("title", "")
                # 按岗位聚合（限白名单内的 code）
                agg: dict[str, list[float]] = {}
                for code, score in rows:
                    if code in by_code or code in allow:
                        agg.setdefault(code, []).append(score)
                for code, scores in agg.items():
                    p = by_code.get(code)
                    if p is None:
                        p = {"code": code, "adv": None, "top": None, "avg": None,
                             "line": None, "rank_src": False, "review_src": False}
                        by_code[code] = p
                        out["positions"].append(p)
                        added += 1
                    rec = {"adv": len(scores), "lo": round(min(scores), 2),
                           "top": round(max(scores), 2), "avg": round(statistics.mean(scores), 2)}
                    chg = False
                    for k in ("adv", "top", "avg"):
                        if p.get(k) is None and rec[k] is not None:
                            p[k] = rec[k]
                            chg = True
                    if is_review and p.get("line") is None:
                        p["line"] = rec["lo"]
                        chg = True
                    if chg:
                        updated += 1
                print(f"   提取 {len(rows)} 行，命中 {len(agg)} 个已知岗位 code（其余为跨考试代码，跳过）")
                done = True
                break
            except Exception as e:  # noqa: BLE001
                print(f"   失败 {type(e).__name__}: {str(e)[:70]}")
        if not done:
            print(f"   {pid}: 未产出数据")

    # 二次聚合：对只补了 adv=1 的岗位，凡同 code 多行会重复 update——这里逐行处理已自然覆盖 top/avg
    out["total"] = len(out["positions"])
    out["generated_on"] = time.strftime("%Y-%m-%d")
    out["source"] = (out.get("source") or "") + f"（PDF 合并增量 {time.strftime('%Y-%m-%d %H:%M')}：{updated} 岗补字段，ID {ids}）"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n完成：补字段 {updated} 处 → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
