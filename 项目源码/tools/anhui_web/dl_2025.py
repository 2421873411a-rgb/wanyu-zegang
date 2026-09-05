# -*- coding: utf-8 -*-
"""下载二进制附件（xls/xlsx/pdf/docx/zip）到 anhui2025/raw/。
用法: python dl_2025.py <url> <输出文件名> [referer]
"""
import sys
import time
import urllib.request
from pathlib import Path

OUT_DIR = Path(r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\source_data\anhui2025\raw")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def download(url: str, dest: Path, referer: str = "") -> int:
    last = None
    for attempt in range(3):
        try:
            headers = {
                "User-Agent": UA,
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            if referer:
                headers["Referer"] = referer
            req = urllib.request.Request(url, headers=headers)
            t0 = time.time()
            blob = urllib.request.urlopen(req, timeout=120).read()
            dest.write_bytes(blob)
            dt = time.time() - t0
            print(f"OK {dest.name} {len(blob)} bytes in {dt:.1f}s")
            return len(blob)
        except Exception as exc:
            last = exc
            print(f"retry {attempt+1}: {exc}")
            time.sleep(1.5 * (attempt + 1))
    print(f"FAIL {url}: {last}")
    return -1


if __name__ == "__main__":
    url, name = sys.argv[1], sys.argv[2]
    referer = sys.argv[3] if len(sys.argv) > 3 else ""
    n = download(url, OUT_DIR / name, referer)
    raise SystemExit(0 if n > 2048 else 1)
