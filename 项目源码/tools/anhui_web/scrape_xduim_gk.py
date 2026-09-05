# -*- coding: utf-8 -*-
"""抓取 xduim 国考职位排名系统（逐岗报名人数/过审人数），回填 guokao2026.json。

xduim /zt/guokao/gkzwrank 按 (部门, 单位, 岗位名称) 展示报名/过审，
无职位代码列；与 data/guokao2026.json（来自职位表）按名称三元组 join，
重复元组按招考人数辅助消歧。

输出：更新 data/guokao2026.json（bm/hg 字段回填）+ data/.gk_page_cache/
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
GK_JSON = HERE / "data" / "guokao2026.json"
CACHE = HERE / "data" / ".gk_page_cache"
BASE = "https://www.xduim.com/zt/guokao/gkzwrank"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"
DELAY = 0.25


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")


def cached(page: int) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"p{page:03d}.html"
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="ignore")
    url = f"{BASE}?year=2026&dq={urllib.parse.quote('安徽省')}" + (f"&page={page}" if page > 1 else "")
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
    first = cached(1)
    m = re.search(r"page=(\d+)'[^>]*尾页", first)
    total_pages = int(m.group(1)) if m else 1
    rows = []
    for p in range(1, total_pages + 1):
        rows.extend(parse(cached(p)))
        print(f"page {p}/{total_pages} rows={len(rows)}", end="\r")
    print()
    gk = json.loads(GK_JSON.read_text(encoding="utf-8"))
    # 索引：名称三元组（去空白）→ 记录列表
    from collections import defaultdict
    src = defaultdict(list)
    for r in rows:
        src[(r["dept"], r["unit"], r["zw"], r["num"])].append(r)
    hit = miss = amb = 0
    for pos in gk["positions"]:
        key = (pos["dept"], pos["unit"], pos["zw"], pos["num"])
        cands = src.get(key) or src.get((pos["dept"], pos["unit"], pos["zw"], None)) or []
        if not cands:
            miss += 1
            continue
        if len(cands) > 1:
            amb += 1
        r = cands[0]
        if pos.get("bm") is None and r["bm"] is not None:
            pos["bm"] = r["bm"]
        if pos.get("hg") is None and r["hg"] is not None:
            pos["hg"] = r["hg"]
        hit += 1
    gk["bm_source"] = "相对面·国考职位排名统计（2026，报名/过审逐岗）"
    gk["coverage"]["bm"] = sum(1 for p in gk["positions"] if p.get("bm") is not None)
    gk["coverage"]["hg"] = sum(1 for p in gk["positions"] if p.get("hg") is not None)
    GK_JSON.write_text(json.dumps(gk, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"done: hit={hit} miss={miss} ambiguous={amb} coverage={gk['coverage']}")
    if miss:
        for pos in gk["positions"]:
            if pos.get("bm") is None:
                print("  MISS:", pos["dept"][:20], pos["unit"][:24], pos["zw"][:20])
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
