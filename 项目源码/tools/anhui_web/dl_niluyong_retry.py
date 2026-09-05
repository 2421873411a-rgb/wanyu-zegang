# -*- coding: utf-8 -*-
"""重试宿州/安庆拟聘附件（忽略SSL证书过期）。"""
import ssl
import time
import urllib.request
from pathlib import Path

OUT = Path(r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\source_data\anhui2025\raw")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

FILES = [
    ("nilu_suzhou_b1.xlsx", "https://www.szxf.gov.cn/upload/file/20250608/6388501601487241391512004.xlsx"),
    ("nilu_suzhou_b2.xlsx", "https://www.szxf.gov.cn/upload/file/20250615/6388561546250111925899789.xlsx"),
    ("nilu_suzhou_b4.xlsx", "https://www.szxf.gov.cn/upload/file/20250625/6388647313072173275140738.xlsx"),
    ("nilu_anqing_b1.pdf", "https://www.susong.gov.cn/group2/M00/07/8A/FBUWEmg_sTGALMKUAAMWxMy5Hk8288.pdf"),
    ("nilu_hefei_b1.xlsx", "https://www.hfxf.gov.cn/group5/M00/32/55/wKgEImhKG8SAW5oyAAD8m-YIQ3w64.xlsx"),
]


def main() -> None:
    for name, url in FILES:
        dest = OUT / name
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                           "Referer": url.rsplit("/", 1)[0] + "/"})
                blob = urllib.request.urlopen(req, timeout=120, context=CTX).read()
                dest.write_bytes(blob)
                print(f"OK {name} {len(blob)}")
                break
            except Exception as exc:
                print(f"retry {name}: {str(exc)[:80]}")
                time.sleep(1.5 * (attempt + 1))
        else:
            print(f"FAIL {name}")
        time.sleep(0.4)


if __name__ == "__main__":
    main()
