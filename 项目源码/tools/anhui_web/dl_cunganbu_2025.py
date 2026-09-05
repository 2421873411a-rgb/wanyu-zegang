# -*- coding: utf-8 -*-
"""下载村干部考录笔试成绩附件（15市，xduim OSS直链）。"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
HITS = HERE / "data" / ".zhaokao_hits_2025.json"
OUT = Path(r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\source_data\anhui2025\raw")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
OUT.mkdir(parents=True, exist_ok=True)

CITY = {"合肥": "hefei", "淮北": "huaibei", "亳州": "bozhou", "宿州": "suzhou",
        "蚌埠": "bengbu", "阜阳": "fuyang", "淮南": "huainan", "滁州": "chuzhou",
        "六安": "luan", "马鞍山": "maanshan", "芜湖": "wuhu", "宣城": "xuancheng",
        "铜陵": "tongling", "池州": "chizhou", "安庆": "anqing", "黄山": "huangshan"}


def download(url: str, dest: Path) -> int:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": "https://www.xduim.com/"})
            blob = urllib.request.urlopen(req, timeout=120).read()
            dest.write_bytes(blob)
            return len(blob)
        except Exception as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"FAIL {dest.name}: {last}")
    return -1


def main() -> None:
    hits = json.loads(HITS.read_text(encoding="utf-8"))
    for pid in sorted(hits, key=int):
        t = hits[pid].get("title", "")
        if "从优秀村" not in t and "村干部" not in t:
            continue
        if "笔试成绩" not in t and "加分" not in t:
            continue
        city = next((v for k, v in CITY.items() if k in t), "other")
        for i, u in enumerate(hits[pid].get("atts", [])):
            suffix = u.split("?")[0].rsplit(".", 1)[-1].lower()
            if suffix not in ("xls", "xlsx", "pdf"):
                continue
            dest = OUT / f"cunganbu_{city}_{pid}_{i}.{suffix}"
            if dest.is_file() and dest.stat().st_size > 2048:
                print("SKIP", dest.name)
                continue
            n = download(u, dest)
            print(f"OK {dest.name} {n}" if n > 0 else f"FAIL {dest.name}")
            time.sleep(0.35)


if __name__ == "__main__":
    main()
