# -*- coding: utf-8 -*-
"""通用县官网成绩公告收割：抓公告页→提取附件→解析→白名单合并。

用法：python harvest_gov_page.py <公告URL> <简称>
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RAW = HERE / "data" / "raw_syb_county"
OUT = HERE / "data" / "syb2026_daxian_all.json"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"


def get(url: str, binary: bool = False, timeout: int = 90):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": url})
    data = urllib.request.urlopen(req, timeout=timeout, context=CTX).read()
    return data if binary else data.decode("utf-8", "ignore", )


def absolutize(base: str, href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    root = re.match(r"(https?://[^/]+)", base).group(1)
    if href.startswith("/"):
        return root + href
    return base.rsplit("/", 1)[0] + "/" + href


def main() -> int:
    url = sys.argv[1]
    tag = sys.argv[2] if len(sys.argv) > 2 else "county"
    if re.search(r"\.(xls|xlsx|pdf)$", url.split("?")[0], re.I):
        atts = [url]  # 直链模式
    else:
        html = get(url)
        atts = re.findall(r'href="([^"]+\.(?:xls|xlsx|pdf))"', html, re.I)
        # 兼容单引号与 JS 变量
        atts += re.findall(r"['\"]([^'\"]+\.(?:xls|xlsx|pdf))['\"]", html, re.I)
        atts = list(dict.fromkeys(absolutize(url, a) for a in atts))
        atts = [a for a in atts if not any(x in a.lower() for x in ("logo", "banner", "images/"))]
    print(f"公告: {url}\n附件 {len(atts)} 个:")
    for a in atts:
        print("  ", a[:120])
    if not atts:
        return 1

    from harvest_syb_merge import parse_excel
    from harvest_syb_pdf import pdf_rows

    RAW.mkdir(parents=True, exist_ok=True)
    out = json.loads(OUT.read_text(encoding="utf-8"))
    backup = OUT.with_name("syb2026_daxian_all.backup.json")
    shutil.copyfile(OUT, backup)
    by_code = {str(p["code"]): p for p in out["positions"]}
    syb = json.load(open(HERE / "data" / "huatu_syb_2026.json", encoding="utf-8"))
    allow = {str(r["code"]): (r.get("city") or "?") for r in syb["positions"]}

    rows_all = []
    for i, au in enumerate(atts[:3], 1):
        try:
            blob = get(au, binary=True)
            suffix = ".pdf" if ".pdf" in au.lower() else (".xlsx" if "xlsx" in au.lower() else ".xls")
            dest = RAW / f"{tag}_{i}{suffix}"
            dest.write_bytes(blob)
            rows = pdf_rows(dest) if suffix == ".pdf" else None
            if rows is None:
                df = parse_excel(dest)
                rows = [(str(r.code), float(r.score)) for r in df.itertuples()] if df is not None else None
            print(f"  [{i}] {Path(au).name[:60]} → {len(rows) if rows else 0} 行")
            if rows:
                rows_all.extend(rows)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}] 失败 {type(e).__name__}: {str(e)[:80]}")

    if not rows_all:
        print("未提取到任何行")
        return 1
    agg: dict[str, list[float]] = {}
    for code, score in rows_all:
        if code in by_code or code in allow:
            agg.setdefault(code, []).append(score)
    added = updated = 0
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
        if p.get("line") is None:
            p["line"] = rec["lo"]
            chg = True
        if chg:
            updated += 1
    out["total"] = len(out["positions"])
    out["generated_on"] = time.strftime("%Y-%m-%d")
    out["source"] = (out.get("source") or "") + (
        f"（{tag} 官网收割 {time.strftime('%m-%d %H:%M')}：+{added}/{updated}）")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成：+{added} 新岗 / {updated} 补字段 → 总 {out['total']} 岗")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
