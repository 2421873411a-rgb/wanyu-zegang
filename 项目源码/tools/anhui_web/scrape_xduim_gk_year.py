# -*- coding: utf-8 -*-
"""抓取 xduim 国考职位排名系统（逐岗报名人数/过审人数）—— 年份参数化版。

xduim /zt/guokao/gkzwrank 按 (部门, 单位, 岗位名称) 展示报名/过审，
无职位代码列；输出独立 JSON，转换阶段与职位表按名称三元组 join。

用法：
  python scrape_xduim_gk_year.py --year 2025
  python scrape_xduim_gk_year.py --year 2024

输出：data/guokao{year}_bmrank.json + data/.gk_page_cache_{year}/
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "https://www.xduim.com/zt/guokao/gkzwrank"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"
DELAY = 0.25


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")


def cached(page: int, year: str, cache: Path) -> str:
    cache.mkdir(parents=True, exist_ok=True)
    p = cache / f"p{page:03d}.html"
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="ignore")
    url = f"{BASE}?year={year}&dq={urllib.parse.quote('安徽省')}" + (f"&page={page}" if page > 1 else "")
    html = fetch(url)
    p.write_text(html, encoding="utf-8")
    time.sleep(DELAY)
    return html


def _clean(s: str) -> str:
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", s))


def parse(html: str) -> list[dict]:
    m = re.search(r'<table[^>]*>(.*?)</table>', html, re.S)
    if not m:
        return []
    tbody = re.search(r"<tbody>(.*)</tbody>", m.group(1), re.S)
    body = tbody.group(1) if tbody else m.group(1)
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [_clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) < 8:
            continue
        def num(s):
            try:
                return int(s)
            except ValueError:
                return None
        out.append({
            "dept": cells[1], "unit": cells[2], "zw": cells[3],
            "num": num(cells[4]), "bm": num(cells[5]), "hg": num(cells[6]),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True)
    args = ap.parse_args()
    year = args.year
    cache = HERE / "data" / f".gk_page_cache_{year}"
    out = HERE / "data" / f"guokao{year}_bmrank.json"

    first = cached(1, year, cache)
    m = re.search(r"page=(\d+)'[^>]*尾页", first)
    total_pages = int(m.group(1)) if m else 1
    rows = []
    for p in range(1, total_pages + 1):
        rows.extend(parse(cached(p, year, cache)))
        print(f"page {p}/{total_pages} rows={len(rows)}", end="\r")
    print()
    if not rows:
        print("[gk] ERROR: no rows parsed")
        return 1
    payload = {
        "cycle": year,
        "generated_on": time.strftime("%Y-%m-%d"),
        "source": "相对面教育·国考职位报名排名（xduim.com/zt/guokao/gkzwrank，安徽地区）",
        "total": len(rows),
        "with_bm": sum(1 for r in rows if r["bm"] is not None),
        "rows": rows,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[gk] wrote {out.name}: {len(rows)} rows, with_bm={payload['with_bm']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
