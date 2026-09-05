# -*- coding: utf-8 -*-
"""下载各市拟聘用公示附件（浏览器提取的gov直链清单）。"""
import time
import urllib.request
from pathlib import Path

OUT = Path(r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\source_data\anhui2025\raw")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
OUT.mkdir(parents=True, exist_ok=True)

FILES = [
    # 合肥
    ("nilu_hefei_b1.xlsx", "https://www.hfxf.gov.cn/group5/M00/32/55/wKgEImhKG8SAW5oyAAD8m-YIQ3w64.xlsx"),
    ("nilu_hefei_b1b.xlsx", "https://www.hfxf.gov.cn/group5/M00/32/54/wKgEImhJgN6AMEi-AAD6WArnLec93.xlsx"),
    ("nilu_hefei_b2.xlsx", "https://www.hfxf.gov.cn/group5/M00/32/60/wKgEImhMLYmALnNpAABLxgIFywk76.xlsx"),
    ("nilu_hefei_b5.xlsx", "https://www.hfxf.gov.cn/group5/M00/32/79/wKgEImhXt0-AFh8OAAA1rZEA00Q14.xlsx"),
    # 芜湖
    ("nilu_wuhu_b1.pdf", "https://www.whxf.gov.cn/site/5/upload/file/20250610/6388517133915458645496124.pdf"),
    # 亳州
    ("nilu_bozhou_b1.xlsx", "https://www.bzxfw.gov.cn/d/file/p/2025/06-05/f89cc01c35340b8cedb8624613001630.xlsx"),
    ("nilu_bozhou_b2.xlsx", "http://www.lxxfw.gov.cn/upload/file/20250623/6388626436249275368488433.xlsx"),
    ("nilu_bozhou_b3.xlsx", "http://www.lxxfw.gov.cn/upload/file/20250623/6388626445173293248989155.xlsx"),
    # 六安
    ("nilu_luan_b1.xls", "https://www.luan.gov.cn/group1/M00/12/A9/wKgSGWhKGzeAKOpMAABoAOcZb_E345.xls"),
    ("nilu_luan_b2.xls", "https://www.laxf.gov.cn/oldfiles/luanxfwoldfiles/attachment/578c48e0ceab069177526171/202506/202506121927001348_98zUGhaj.xls"),
    # 滁州
    ("nilu_chuzhou_b2.xls", "https://www.czxfw.gov.cn/UploadFiles/file/20250609/20250609105643_0230.xls"),
    ("nilu_chuzhou_b3.xls", "https://www.czxfw.gov.cn/UploadFiles/file/20250610/20250610174918_0064.xls"),
    # 淮南
    ("nilu_huainan_b4.xlsx", "http://www.hnxfw.gov.cn/uploadfiles/2025/06/20250623174518323.xlsx"),
    # 宿州
    ("nilu_suzhou_b1.xlsx", "https://www.szxf.gov.cn/upload/file/20250608/6388501601487241391512004.xlsx"),
    ("nilu_suzhou_b2.xlsx", "https://www.szxf.gov.cn/upload/file/20250615/6388561546250111925899789.xlsx"),
    ("nilu_suzhou_b4.xlsx", "https://www.szxf.gov.cn/upload/file/20250625/6388647313072173275140738.xlsx"),
    # 马鞍山
    ("nilu_maanshan_b1.xls", "https://rsj.mas.gov.cn/group4/M00/0C/BF/Cu7KgmhD43GAFjf3AACKAD9B18M412.xls"),
    # 安庆
    ("nilu_anqing_b1.pdf", "https://www.susong.gov.cn/group2/M00/07/8A/FBUWEmg_sTGALMKUAAMWxMy5Hk8288.pdf"),
    ("nilu_anqing_b2.pdf", "https://www.tongcheng.gov.cn/group3/M00/24/22/FBUWE2iw9d2AA3wdAAMbzdH8ThM440.pdf"),
    ("nilu_anqing_b3.pdf", "https://www.tongcheng.gov.cn/group3/M00/24/22/FBUWE2iw96aAU6VrAAPpWSj47jo700.pdf"),
    # 黄山
    ("nilu_huangshan_b1.xls", "http://www.hsxfw.gov.cn/group1/M00/23/41/wKiM92hFTy-AG27CAACWAEm6rRY125.xls"),
    ("nilu_huangshan_b2.xls", "http://www.hsxfw.gov.cn/group1/M00/23/7F/wKiM92hI8ZGAd9-7AADQACkH2OY050.xls"),
    ("nilu_huangshan_b3.xls", "http://www.hsxfw.gov.cn/group1/M00/23/EB/wKiM92hSkzaAcRdsAAB8ABooZO4017.xls"),
]


def download(url: str, dest: Path) -> int:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Referer": url.rsplit("/", 1)[0] + "/"})
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
            print("SKIP", name)
            continue
        n = download(url, dest)
        print(f"OK {name} {n}" if n > 0 else f"FAIL {name}")
        time.sleep(0.4)


if __name__ == "__main__":
    main()
