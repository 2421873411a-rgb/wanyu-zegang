# -*- coding: utf-8 -*-
"""批量下载2025省考职位表附件（xduim OSS直链）并验证。"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

OUT = Path(r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\source_data\anhui2025\raw")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
OUT.mkdir(parents=True, exist_ok=True)

FILES = {
    "2025省直职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/f8245c81a9f987fe7b079d823fef3db1.xlsx", "xlsx"),
    "2025合肥市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/4c1e33668270bcdac96b504217abd375.xlsx", "xlsx"),
    "2025淮北市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/74ac7e1e00d4a5587100afb5cf976287.xlsx", "xlsx"),
    "2025亳州市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/f555cf33aa53dd6741d1004170a5a876.xlsx", "xlsx"),
    "2025宿州市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/91dac9ff2a302e414385dd497e9a319d.xls", "xls"),
    "2025蚌埠市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/ae98372c922ba44cc22bb180f37f6bb7.xls", "xls"),
    "2025阜阳市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/145fa47ade333003018ab47c96403b3a.xlsx", "xlsx"),
    "2025淮南市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/ad283e3e7222e6eb2d07fa6f32c8d80b.xls", "xls"),
    "2025滁州市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/9c088e29dd1d01f7bf005fb78bdfacf6.xlsx", "xlsx"),
    "2025六安市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/8fec66ad59f8cc594d95de8af9ef69c2.xls", "xls"),
    "2025马鞍山市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/78c62255a7c07f63c28e987270cec015.xls", "xls"),
    "2025芜湖市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/914d3a041747b0d27c9c16a875b98fc2.xlsx", "xlsx"),
    "2025宣城市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/9d25642eb959d33c0c737b321463dd6f.xls", "xls"),
    "2025铜陵市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/32fc1414099b2abcfc8672b685437c1c.xlsx", "xlsx"),
    "2025池州市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/5a8fe82b1ebd065275c37a5c7c10302b.xls", "xls"),
    "2025安庆市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/8c5961425ddb3ecce66d5c23022ef2b7.xlsx", "xlsx"),
    "2025黄山市职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/a4d991ac8fd78ae0c595e0461e948625.xlsx", "xlsx"),
    "2025安徽选调生职位表": ("https://xduim-webs.oss-cn-hangzhou.aliyuncs.com/uploads/20250103/0d4751c8b4363d92f149a1042ad445f4.xlsx", "xlsx"),
}


def fetch(url: str, referer: str = "") -> bytes:
    headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=120).read()


def main() -> None:
    ok = fail = 0
    for name, (u, suf) in FILES.items():
        dest = OUT / f"{name}.{suf}"
        if dest.is_file() and dest.stat().st_size > 2048:
            print(f"SKIP {dest.name}")
            ok += 1
            continue
        try:
            blob = fetch(u, "https://www.xduim.com/zhaokao/detail/33669")
            dest.write_bytes(blob)
            print(f"OK {dest.name} {len(blob)}")
            ok += 1
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            fail += 1
        time.sleep(0.4)
    print(f"done ok={ok} fail={fail}")


if __name__ == "__main__":
    main()
