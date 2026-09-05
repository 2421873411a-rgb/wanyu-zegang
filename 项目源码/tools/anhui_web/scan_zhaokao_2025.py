# -*- coding: utf-8 -*-
"""扫描 xduim.com/zhaokao/detail/{id}，定位2025年安徽省考相关公告并提取附件OSS直链。

用法:
  python scan_zhaokao_2025.py probe 20000          # 看单页标题/日期/附件
  python scan_zhaokao_2025.py bisect               # 二分找2025年3-6月id区间
  python scan_zhaokao_2025.py scan 17000 24000     # 全扫区间,存hits
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
HITS = DATA / ".zhaokao_hits_2025.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DELAY = 0.35
RETRIES = 3

ATT_RE = re.compile(r'href="([^"]+\.(?:xls|xlsx|pdf|doc|docx|zip|csv)[^"]*)"', re.I)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
DATE_RE = re.compile(r"(20\d{2}[-/年]\d{1,2}[-/月]\d{1,2})")


def fetch(url: str) -> bytes:
    last = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.xduim.com/",
            })
            return urllib.request.urlopen(req, timeout=40).read()
        except Exception as exc:
            last = exc
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def get_detail(pid: int) -> dict:
    try:
        raw = fetch(f"https://www.xduim.com/zhaokao/detail/{pid}")
    except Exception as exc:
        return {"id": pid, "error": str(exc)[:80]}
    # 尝试编码
    try:
        html = raw.decode("utf-8")
        if "<title>" not in html:
            html = raw.decode("gbk", "ignore")
    except UnicodeDecodeError:
        html = raw.decode("gbk", "ignore")
    m = TITLE_RE.search(html)
    title = (m.group(1).strip() if m else "")[:120]
    atts = []
    for u in ATT_RE.findall(html):
        u = u.replace("&amp;", "&")
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = "https://www.xduim.com" + u
        atts.append(u)
    atts = list(dict.fromkeys(atts))
    # 页面日期: 找发布时间
    dm = re.search(r"发布[时时间][:：]?\s*(20\d{2}-\d{2}-\d{2})", html)
    date = dm.group(1) if dm else None
    if not date:
        # 从附件URL猜测 /uploads/20250413/...
        for u in atts:
            m2 = re.search(r"/uploads/(20\d{6})/", u)
            if m2:
                date = f"{m2.group(1)[:4]}-{m2.group(1)[4:6]}-{m2.group(1)[6:8]}"
                break
    return {"id": pid, "title": title, "date": date, "atts": atts}


def load_hits() -> dict:
    if HITS.is_file():
        return json.loads(HITS.read_text(encoding="utf-8"))
    return {}


def save_hits(d: dict) -> None:
    HITS.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")


def is_target(title: str) -> bool:
    """2025安徽省考相关公告（含职位表/达线/面试/拟聘/成绩/报名人数）"""
    if "2025" not in title:
        return False
    keys = ["公务员", "职位表", "合格分数线", "达线", "成绩排名", "面试",
            "拟聘", "录用", "报名人数", "报考人数", "缴费", "审查"]
    return any(k in title for k in keys)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if mode == "probe":
        pid = int(sys.argv[2])
        r = get_detail(pid)
        print(json.dumps(r, ensure_ascii=False, indent=1)[:2000])
        return 0
    if mode == "bisect":
        # 逐步探测：打印 id -> title/date
        for pid in [int(x) for x in sys.argv[2:]]:
            r = get_detail(pid)
            print(pid, "|", r.get("date"), "|", r.get("title"))
            time.sleep(DELAY)
        return 0
    if mode == "scan":
        lo, hi = int(sys.argv[2]), int(sys.argv[3])
        hits = load_hits()
        for pid in range(lo, hi + 1):
            if str(pid) in hits:
                continue
            r = get_detail(pid)
            if r.get("title") and is_target(r["title"]):
                hits[str(pid)] = r
                print("HIT", pid, r["title"])
                save_hits(hits)
            elif pid % 100 == 0:
                print("...", pid, r.get("title", r.get("error", "")))
            time.sleep(DELAY)
        save_hits(hits)
        print("TOTAL HITS:", len(hits))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
