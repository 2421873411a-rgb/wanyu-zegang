# -*- coding: utf-8 -*-
"""下载安徽先锋网官方省直附件（221.130.129.68:6008 CMS直链）。"""
import time
import urllib.request
from pathlib import Path

OUT = Path(r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\source_data\anhui2025\raw")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
OUT.mkdir(parents=True, exist_ok=True)

FILES = [
    ("官方公告_职位表_ahxf.xlsx", "http://221.130.129.68:6008/upload/file/20250103/6387152804893560207485139.xlsx"),
    ("官方公告_报考指南_ahxf.docx", "http://221.130.129.68:6008/upload/file/20250104/6387158101757371852436335.docx"),
    ("达线_省直_2025.xls", "http://221.130.129.68:6008/upload/file/20250412/6388005874347408636651425.xls"),
    ("省直面试人选_2025.xls", "http://221.130.129.68:6008/upload/file/20250415/6388032726656794886015940.xls"),
    ("省直面试成绩总成绩一_2025.xls", "http://221.130.129.68:6008/upload/file/20250519/6388326537526740612320899.xls"),
    ("省直面试成绩总成绩二_2025.XLS", "http://221.130.129.68:6008/upload/file/20250526/6388386797335188807242362.XLS"),
    ("省直体检人员名单一_2025.xls", "http://221.130.129.68:6008/upload/file/20250520/6388333465495705841966039.xls"),
    ("省直体检人员名单二_2025.XLS", "http://221.130.129.68:6008/upload/file/20250526/6388387092586574648370104.XLS"),
    ("省直拟录用第一批_2025.xlsx", "http://221.130.129.68:6008/upload/file/20250612/6388534816251062324897605.xlsx"),
    ("省直拟录用第二批_2025.xlsx", "http://221.130.129.68:6008/upload/file/20250615/6388558026527111661031983.xlsx"),
    ("省直拟录用第三批_2025.xlsx", "http://221.130.129.68:6008/upload/file/20250617/6388578109361998495162639.xlsx"),
    ("省直拟录用第四批_2025.xlsx", "http://221.130.129.68:6008/upload/file/20250625/6388647228264910849260562.xlsx"),
    ("省直拟录用第五批_2025.xlsx", "http://221.130.129.68:6008/upload/file/20250629/6388681527073815273531792.xlsx"),
    ("省直拟录用第六批_2025.xlsx", "http://221.130.129.68:6008/upload/file/20250706/6388741643652667854836251.xlsx"),
    ("省直拟录用第七批_2025.xlsx", "http://221.130.129.68:6008/upload/file/20250716/6388828915583765535832609.xlsx"),
]


def download(url: str, dest: Path) -> int:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.ahxf.gov.cn/"})
            blob = urllib.request.urlopen(req, timeout=120).read()
            dest.write_bytes(blob)
            return len(blob)
        except Exception as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"FAIL {dest.name}: {last}")
    return -1


def main() -> None:
    for name, url in FILES:
        dest = OUT / name
        if dest.is_file() and dest.stat().st_size > 2048:
            print(f"SKIP {name}")
            continue
        n = download(url, dest)
        print(f"OK {name} {n}" if n > 0 else f"FAIL {name}")
        time.sleep(0.4)


if __name__ == "__main__":
    main()
