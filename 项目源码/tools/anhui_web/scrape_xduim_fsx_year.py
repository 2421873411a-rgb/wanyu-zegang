# -*- coding: utf-8 -*-
"""抓取 xduim（相对面）安徽省考分数线查询系统的全量逐岗数据 —— 年份参数化版。

数据内容（每个 year 一次查询，约 200 页 × 20 行）：
  年份 / 城市 / 地区 / 职位代码 / 单位 / 职位 / 学历 / 专业 / 招考人数
  / 报名人数 / 分数线（最低入围线）/ 最高分 / 平均分

用法：
  python scrape_xduim_fsx_year.py --year 2025
  python scrape_xduim_fsx_year.py --year 2024
  python scrape_xduim_fsx_year.py --year 2025 --refresh

输出：data/ahsk{year}_scores.json（与 ahsk2026_scores.json 同构）
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.xduim.com/zt/ahgwy/fsx/search"
HERE = Path(__file__).resolve().parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DELAY = 0.25
RETRIES = 3

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def _as_num(s: str):
    s = (s or "").strip()
    if not s or s in {"—", "-", "/"}:
        return None
    try:
        v = float(s)
        return int(v) if v == int(v) else v
    except ValueError:
        return None


def fetch(url: str) -> str:
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed after {RETRIES} tries: {url}: {last}")


def cached_page(page: int, year: str, cache: Path, refresh: bool) -> str:
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{year}_p{page:03d}.html"
    if path.is_file() and not refresh:
        return path.read_text(encoding="utf-8", errors="ignore")
    url = f"{BASE}?year={year}" + (f"&page={page}" if page > 1 else "")
    html = fetch(url)
    path.write_text(html, encoding="utf-8")
    time.sleep(DELAY)
    return html


def last_page_of(html: str) -> int:
    m = re.search(r"page=(\d+)'\s+title='尾页'", html)
    return int(m.group(1)) if m else 1


def clean(cell: str) -> str:
    return WS_RE.sub(" ", TAG_RE.sub("", cell)).strip()


def parse_rows(html: str) -> list[dict[str, str]]:
    m = re.search(r'<div class="pc-search-table">.*?<table id="table">(.*?)</table>',
                  html, re.S)
    if not m:
        return []
    rows: list[dict[str, str]] = []
    body = m.group(1)
    tbody_m = re.search(r"<tbody>(.*)</tbody>", body, re.S)
    tbody = tbody_m.group(1) if tbody_m else body
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.S):
        raw_cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(raw_cells) < 12:
            continue
        d = next((i for i, c in enumerate(raw_cells) if "code=" in c and "detail" in c), -1)
        if d < 10:
            continue
        cells = [clean(c) for c in raw_cells]
        tail = cells[:d]
        code_idx = -1
        for i in range(len(tail) - 1):
            if re.fullmatch(r"\d{6}", tail[i]) and re.search(r"[\u4e00-\u9fff]", tail[i + 1]):
                code_idx = i
                break
        if code_idx < 1:
            continue
        code = tail[code_idx]
        region = tail[code_idx - 1]
        rest = (tail[code_idx + 1:code_idx + 10] + [""] * 9)[:9]
        unit, zw, xl, zy, num, bm, line, top, avg = rest
        detail = ""
        dm = re.search(r"code=(\d+)&year=(\d+)(?:&type=([^&\"']+))?", cells[d])
        if dm:
            detail = urllib.parse.unquote(dm.group(3) or "")
        rows.append({
            "code": code,
            "region": region,
            "unit": unit,
            "zw": zw,
            "xl": xl,
            "zy": zy,
            "num": _as_num(num),
            "bm": _as_num(bm),
            "line": _as_num(line),
            "top": _as_num(top),
            "avg": _as_num(avg),
            "exam_type": detail or None,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    year = args.year
    cache = HERE / "data" / f".xduim_page_cache_{year}"
    out = HERE / "data" / f"ahsk{year}_scores.json"

    first = cached_page(1, year, cache, args.refresh)
    total_pages = last_page_of(first)
    print(f"[xduim] year={year} pages={total_pages}")
    seen: dict[str, dict] = {}
    dup = 0
    empty_streak = 0
    for page in range(1, total_pages + 1):
        html = cached_page(page, year, cache, args.refresh) if page > 1 else first
        rows = parse_rows(html)
        if not rows:
            empty_streak += 1
            if empty_streak >= 3:
                print("[xduim] 3 consecutive empty pages, stop early")
                break
            continue
        empty_streak = 0
        for r in rows:
            if r["code"] in seen:
                dup += 1
                continue
            seen[r["code"]] = r
        print(f"  page {page:>3}/{total_pages} rows={len(rows)} total={len(seen)}", end="\r")
    print()
    if not seen:
        print("[xduim] ERROR: no rows parsed — page structure changed?")
        return 1
    counts = {
        "bm": sum(1 for r in seen.values() if r["bm"] is not None),
        "line": sum(1 for r in seen.values() if r["line"] is not None),
        "top": sum(1 for r in seen.values() if r["top"] is not None),
        "avg": sum(1 for r in seen.values() if r["avg"] is not None),
    }
    payload = {
        "cycle": year,
        "generated_on": time.strftime("%Y-%m-%d"),
        "source": "相对面教育·安徽省考分数线查询系统（xduim.com/zt/ahgwy/fsx，汇编官方达线名单与报名数据）",
        "total": len(seen),
        "duplicates_skipped": dup,
        "coverage": counts,
        "positions": sorted(seen.values(), key=lambda r: r["code"]),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[xduim] wrote {out.name}: {len(seen)} posts, dup={dup}, coverage={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
