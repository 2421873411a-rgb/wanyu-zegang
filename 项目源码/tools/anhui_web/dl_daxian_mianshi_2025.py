# -*- coding: utf-8 -*-
"""从 zhaokao_hits_2025.json 批量下载各考区笔试成绩排名（达线）与面试成绩附件。"""
from __future__ import annotations

import json
import re
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
        "铜陵": "tongling", "池州": "chizhou", "安庆": "anqing", "黄山": "huangshan",
        "省直": "shengzhi"}


def city_of(title: str) -> str:
    for k, v in CITY.items():
        if k in title:
            return v
    return "other"


def stage_of(title: str) -> str:
    if "成绩排名" in title:
        return "daxian"
    if "面试" in title and ("总成绩" in title or "成绩" in title):
        return "mianshi"
    if "拟聘" in title or "拟录用" in title:
        return "niluyong"
    if "体检" in title:
        return "tijian"
    return "misc"


def download(url: str, dest: Path) -> int:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.xduim.com/"})
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
    n_ok = n_skip = n_fail = 0
    for pid in sorted(hits, key=int):
        r = hits[pid]
        title = r.get("title", "")
        # 2025省考相关：成绩排名/达线、面试成绩总成绩、体检、拟聘（排除国考/事业单位/村干部以外的干扰）
        if not re.search(r"公务员", title):
            continue
        if not any(k in title for k in ("成绩排名", "达线", "面试成绩", "总成绩", "体检名单", "拟聘", "拟录用")):
            continue
        if "从优秀村" in title or "村干部" in title:
            continue  # 另行公告序列，先不下
        if any(k in title for k in ("国家", "江苏", "浙江", "上海", "天津", "北京", "湖北", "福建", "广西", "重庆", "甘肃", "黑龙江", "云南", "山西", "河南", "广东", "山东")):
            continue
        if "公安" in title and "特殊" in title:
            continue
        city = city_of(title)
        stage = stage_of(title)
        atts = r.get("atts", [])
        for i, u in enumerate(atts):
            suffix = u.split("?")[0].rsplit(".", 1)[-1].lower()
            if suffix not in ("xls", "xlsx", "pdf", "doc", "docx", "zip"):
                continue
            dest = OUT / f"{stage}_{city}_{pid}_{i}.{suffix}"
            if dest.is_file() and dest.stat().st_size > 2048:
                n_skip += 1
                continue
            n = download(u, dest)
            if n > 2048:
                print(f"OK {dest.name} {n} | {title[:50]}")
                n_ok += 1
            else:
                n_fail += 1
            time.sleep(0.35)
    print(f"done ok={n_ok} skip={n_skip} fail={n_fail}")


if __name__ == "__main__":
    main()
