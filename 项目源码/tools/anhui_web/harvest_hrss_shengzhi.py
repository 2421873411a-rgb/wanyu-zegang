# -*- coding: utf-8 -*-
"""省直事业单位联考成绩收割：爬 hrss.ah.gov.cn 事业单位专栏（66 页）。

筛选 2026-04-25 ~ 2026-06-30 之间、标题含 资格复审/成绩/专业测试 的公告
（排除下半年/高层次人才），下载 XLS/XLSX/PDF 附件，解析逐岗成绩，
按华图职位表白名单合并进 data/syb2026_daxian_all.json（只补缺失字段）。

用法：python harvest_hrss_shengzhi.py [--max-pages 66] [--dry-run]
"""
from __future__ import annotations

import json
import re
import shutil
import ssl
import statistics
import sys
import time
import urllib.request
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RAW = HERE / "data" / "raw_syb_shengzhi"
OUT = HERE / "data" / "syb2026_daxian_all.json"
BASE = "https://hrss.ah.gov.cn/zxzx/ztzl/ahssydwgkzp/"
COLUMN_API = "https://hrss.ah.gov.cn/content/column/6791573?pageIndex={p}"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"
SLEEP = 0.35

A_CERT = re.compile(r"A证|A类|（A）|\(A\)")  # 保留符号引用一致性（暂未用）


def get(url: str, binary: bool = False, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE})
    data = urllib.request.urlopen(req, timeout=timeout, context=CTX).read()
    return data if binary else data.decode("utf-8", "ignore")


CODE_RE = re.compile(r"^\d{6,8}$")
DATE_RE = re.compile(r"(2026-\d{2}-\d{2})")
ITEM_RE = re.compile(
    r'<a[^>]+href="((?:https?://hrss\.ah\.gov\.cn)?/(?:zxzx/ztzl/)?ahssydwgkzp/\d+\.html)"[^>]*>\s*(?:<span[^>]*>)?([^<]{6,150})', re.S)
ATT_RE = re.compile(r'href="([^"]+\.(?:xls|xlsx|pdf))"', re.I)


def crawl_entries(max_pages: int):
    """遍历列表接口，返回 [(url, title, date)]。"""
    entries, seen = [], set()
    empty_run = 0
    for p in range(1, max_pages + 1):
        url = COLUMN_API.format(p=p)
        try:
            html = get(url)
        except Exception as e:  # noqa: BLE001
            print(f"  第 {p} 页失败: {type(e).__name__} {str(e)[:60]}")
            empty_run += 1
            if empty_run >= 3:
                print("  连续 3 页失败，停止翻页")
                break
            continue
        found = 0
        for m in ITEM_RE.finditer(html):
            href, title = m.group(1), re.sub(r"\s+", "", m.group(2)).strip()
            if href.startswith("/"):
                href = "https://hrss.ah.gov.cn" + href
            if href in seen:
                continue
            tail = html[m.end():m.end() + 300]
            dm = DATE_RE.search(tail)
            date = dm.group(1) if dm else ""
            seen.add(href)
            entries.append((href, title, date))
            found += 1
        empty_run = 0 if found else empty_run + 1
        print(f"  第 {p} 页: +{found}（累计 {len(entries)}）")
        if empty_run >= 2 and p > 1:
            print("  连续空页，停止翻页")
            break
        time.sleep(SLEEP)
    return entries


def pick(entries):
    """筛选上半年联考成绩/复审/专业测试类公告。"""
    out = []
    for url, title, date in entries:
        if "2026" not in title and not date.startswith("2026-0"):
            continue
        if date and not ("2026-04-25" <= date <= "2026-06-30"):
            continue
        if any(k in title for k in ("下半年", "高层次", "职位表", "公告）", "招聘公告")):
            continue
        if not any(k in title for k in ("资格复审", "成绩", "专业测试", "入围")):
            continue
        out.append((url, title, date))
    return out


# —— 复用既有解析器 ——
from harvest_syb_merge import parse_excel  # noqa: E402
from harvest_syb_pdf import pdf_rows  # noqa: E402


def parse_any(dest: Path):
    if dest.suffix.lower() == ".pdf":
        return pdf_rows(dest)
    df = parse_excel(dest)
    if df is None:
        return None
    return [(str(r.code), float(r.score)) for r in df.itertuples()]


def main() -> int:
    max_pages = 66
    dry = "--dry-run" in sys.argv
    for a in sys.argv[1:]:
        if a.startswith("--max-pages"):
            max_pages = int(a.split("=")[1]) if "=" in a else 66

    print(f"爬取省直专题 {max_pages} 页 …")
    entries = crawl_entries(max_pages)
    picked = pick(entries)
    print(f"共 {len(entries)} 条公告，筛出目标 {len(picked)} 条")
    if dry:
        for u, t, dt in picked[:40]:
            print(f"  [{dt}] {t[:56]}")
        return 0

    RAW.mkdir(parents=True, exist_ok=True)
    out = json.loads(OUT.read_text(encoding="utf-8"))
    backup = OUT.with_name("syb2026_daxian_all.backup.json")
    shutil.copyfile(OUT, backup)
    by_code = {str(p["code"]): p for p in out["positions"]}
    syb = json.load(open(HERE / "data" / "huatu_syb_2026.json", encoding="utf-8"))
    allow = {str(r["code"]): (r.get("city") or "?") for r in syb["positions"]}

    added = updated = files_ok = files_fail = 0
    new_by_city: dict[str, int] = {}
    for i, (url, title, date) in enumerate(picked, 1):
        try:
            html = get(url)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}/{len(picked)}] 详情失败 {type(e).__name__}: {title[:30]}")
            files_fail += 1
            continue
        atts = ATT_RE.findall(html)
        atts = [a if a.startswith("http") else "https://hrss.ah.gov.cn" + a for a in atts]
        if not atts:
            time.sleep(SLEEP)
            continue
        is_review = ("复审" in title) or ("入围" in title)
        rows_all: list[tuple[str, float]] = []
        for au in atts[:3]:
            try:
                blob = get(au, binary=True, timeout=90)
                suffix = ".pdf" if ".pdf" in au.lower() else (".xlsx" if "xlsx" in au.lower() else ".xls")
                dest = RAW / f"sz_{i:03d}_{Path(au).stem[:30]}{suffix}"
                dest.write_bytes(blob)
                rows = parse_any(dest)
                if rows:
                    rows_all.extend(rows)
                    files_ok += 1
                else:
                    files_fail += 1
            except Exception as e:  # noqa: BLE001
                files_fail += 1
                print(f"    附件失败 {type(e).__name__}: {str(au)[-40:]} {str(e)[:40]}")
            time.sleep(SLEEP)
        if not rows_all:
            print(f"  [{i}/{len(picked)}] 无数据: {title[:40]}")
            continue
        agg: dict[str, list[float]] = {}
        for code, score in rows_all:
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
                cty = allow.get(code, "?")
                new_by_city[cty] = new_by_city.get(cty, 0) + 1
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
        if i % 10 == 0:
            print(f"  [{i}/{len(picked)}] 处理中… 文件 ok={files_ok} fail={files_fail} 新岗 {added}")
        time.sleep(SLEEP)

    out["total"] = len(out["positions"])
    out["generated_on"] = time.strftime("%Y-%m-%d")
    out["source"] = (out.get("source") or "") + (
        f"（省直专题收割 {time.strftime('%Y-%m-%d %H:%M')}：+{added} 新岗 / {updated} 岗补字段，"
        f"文件 ok {files_ok} fail {files_fail}）")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n完成：+{added} 新岗（按考区 {new_by_city}），{updated} 岗补字段")
    print(f"总计 {out['total']} 岗 → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
