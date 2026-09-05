# -*- coding: utf-8 -*-
"""抓取 xduim（相对面）安徽省考分数线查询系统的全量逐岗数据。

数据内容（year=2026，一次查询约 190 页 × 20 行 ≈ 3,784 岗）：
  地区 / 职位代码 / 招聘单位 / 职位名称 / 学历 / 专业 / 招考人数
  / 报名人数 / 分数线（最低入围线）/ 最高分数 / 平均分

用法：
  python scrape_xduim_fsx.py            # 全量抓取（有磁盘缓存，断点续抓）
  python scrape_xduim_fsx.py --refresh  # 忽略缓存重新抓取

输出：data/ahsk2026_scores.json
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.xduim.com/zt/ahgwy/fsx/search"
HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "ahsk2026_scores.json"
CACHE = HERE / "data" / ".xduim_page_cache"
YEAR = "2026"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DELAY = 0.25          # 每次请求间隔（秒）
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


def cached_page(page: int, refresh: bool) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{YEAR}_p{page:03d}.html"
    if path.is_file() and not refresh:
        return path.read_text(encoding="utf-8", errors="ignore")
    url = f"{BASE}?year={YEAR}" + (f"&page={page}" if page > 1 else "")
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
    # 跳过 thead，只取 tbody 行
    tbody_m = re.search(r"<tbody>(.*)</tbody>", body, re.S)
    tbody = tbody_m.group(1) if tbody_m else body
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.S):
        raw_cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(raw_cells) < 12:
            continue
        # 列序自适应：以“详情”链接列为锚点从右往左取——
        # [年份(可选), 城市(可选), 地区, 代码, 单位, 职位, 学历, 专业,
        #  招考人数, 报名人数, 分数线, 最高分, 平均分, 详情]
        d = next((i for i, c in enumerate(raw_cells) if "code=" in c and "detail" in c), -1)
        if d < 10:
            continue
        cells = [clean(c) for c in raw_cells]
        tail = cells[:d]  # 详情之前的数值/文本列
        # 代码列 = 第一个 6 位纯数字、且右侧紧邻中文文本（单位名）的单元格；
        # 报名/招考等纯数字列因位数不足 6 或右侧仍为数字而被排除。
        code_idx = -1
        for i in range(len(tail) - 1):
            if re.fullmatch(r"\d{6}", tail[i]) and re.search(r"[\u4e00-\u9fff]", tail[i + 1]):
                code_idx = i
                break
        if code_idx < 1:
            continue
        code = tail[code_idx]
        region = tail[code_idx - 1]  # 紧邻代码左侧的列恒为地区
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
    refresh = "--refresh" in sys.argv
    first = cached_page(1, refresh)
    total_pages = last_page_of(first)
    print(f"[xduim] year={YEAR} pages={total_pages}")
    seen: dict[str, dict] = {}
    dup = 0
    empty_streak = 0
    for page in range(1, total_pages + 1):
        html = cached_page(page, refresh) if page > 1 else first
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
        "cycle": YEAR,
        "generated_on": time.strftime("%Y-%m-%d"),
        "source": "相对面教育·安徽省考分数线查询系统（xduim.com/zt/ahgwy/fsx，汇编官方达线名单与报名数据）",
        "total": len(seen),
        "duplicates_skipped": dup,
        "coverage": counts,
        "positions": sorted(seen.values(), key=lambda r: r["code"]),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[xduim] wrote {OUT.name}: {len(seen)} posts, dup={dup}, coverage={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
