# -*- coding: utf-8 -*-
"""抓取安徽 16 市 + 省直“笔试达线人员成绩”官方附件，逐岗汇总达线人数/最高分。

流程：华图各市公告页 → 提取附件链接（先锋网 gov.cn / huatu CDN）→ 下载到
data/raw_daxian/ → pandas 解析（列名自适应）→ 按职位代码汇总。

输出：data/ahsk2026_daxian_all.json
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw_daxian"
OUT = HERE / "data" / "ahsk2026_daxian_all.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"

# 2026-04 华图“XX市笔试合格分数线和达线人员成绩排名”公告页（省直 0411）
PAGES = [
    ("省直", "https://ah.huatu.com/2026/0411/3227417.html"),
    ("合肥", "https://ah.huatu.com/2026/0413/3228852.html"),
    ("蚌埠", "https://ah.huatu.com/2026/0413/3228826.html"),
    ("安庆", "https://ah.huatu.com/2026/0413/3228712.html"),
    ("芜湖", "https://ah.huatu.com/2026/0413/3228733.html"),
    ("亳州", "https://ah.huatu.com/2026/0413/3228714.html"),
    ("池州", "https://ah.huatu.com/2026/0413/3228718.html"),
    ("滁州", "https://ah.huatu.com/2026/0413/3228911.html"),
    ("宿州", "https://ah.huatu.com/2026/0413/3228731.html"),
    ("黄山", "https://ah.huatu.com/2026/0413/3228708.html"),
    ("宣城", "https://ah.huatu.com/2026/0413/3228704.html"),
    ("铜陵", "https://ah.huatu.com/2026/0413/3228694.html"),
    ("淮南", "https://ah.huatu.com/2026/0413/3228706.html"),
    ("淮北", "https://ah.huatu.com/2026/0413/3228696.html"),
    ("六安", "https://ah.huatu.com/2026/0413/3228729.html"),
    ("阜阳", "https://ah.huatu.com/2026/0413/3228716.html"),
    ("马鞍山", "https://ah.huatu.com/2026/0413/3228710.html"),
]


def fetch(url: str, enc: str = "utf-8", binary: bool = False):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://ah.huatu.com/",
    })
    data = urllib.request.urlopen(req, timeout=60).read()
    return data if binary else data.decode(enc, "ignore")


def find_attachments(html: str, base: str) -> list[str]:
    urls = re.findall(r'href="([^"]+)"', html) + re.findall(r'src="([^"]+)"', html)
    out = []
    for u in urls:
        u = re.sub(r"\s", "", u)
        if re.search(r"\.(xls|xlsx)(\?|$)", u, re.I):
            if u.startswith("//"):
                u = "https:" + u
            elif u.startswith("/"):
                m = re.match(r"(https?://[^/]+)", base)
                u = m.group(1) + u
            out.append(u)
    # 官方 gov 链接优先
    out.sort(key=lambda u: 0 if "gov" in u else 1)
    return list(dict.fromkeys(out))


def parse_table(path: Path) -> pd.DataFrame | None:
    try:
        if path.suffix.lower() == ".xls":
            df = pd.read_excel(path, sheet_name=0, header=None)
        else:
            df = pd.read_excel(path, sheet_name=0, header=None)
    except Exception as exc:  # noqa: BLE001
        print("    parse fail:", exc)
        return None
    # 找表头行（含“职位代码”或“准考证号”）
    hrow = None
    for i in range(min(10, len(df))):
        txt = " ".join(str(x) for x in df.iloc[i].tolist())
        if ("职位代码" in txt) or ("准考证号" in txt and "成绩" in txt):
            hrow = i
            break
    if hrow is None:
        return None
    hdr = [str(x).strip() for x in df.iloc[hrow].tolist()]
    df2 = df.iloc[hrow + 1:].copy()
    df2.columns = hdr
    # 列名归一
    colmap = {}
    for c in df2.columns:
        s = re.sub(r"\s", "", str(c))
        if "职位代码" in s or s == "岗位代码":
            colmap[c] = "code"
        elif "准考证" in s:
            colmap[c] = "zkz"
        elif "笔试成绩" in s or s == "总成绩" or "成绩合计" in s:
            colmap[c] = "score"
        elif "行测" in s:
            colmap[c] = "xc"
        elif "申论" in s:
            colmap[c] = "sl"
    need = {"code", "score"}
    if not need.issubset(set(colmap.values())):
        # 有些表没有“笔试成绩”列，只有行测+申论 → 求和
        if {"xc", "sl"}.issubset(set(colmap.values())):
            df2["score"] = pd.to_numeric(df2[[c for c, v in colmap.items() if v in ("xc", "sl")][0]], errors="coerce") + \
                           pd.to_numeric(df2[[c for c, v in colmap.items() if v == "sl"][0]], errors="coerce")
            colmap[df2.columns[-1]] = "score"
        else:
            return None
    code_col = [c for c, v in colmap.items() if v == "code"][0]
    score_col = [c for c, v in colmap.items() if v == "score"][0]
    df2 = df2[df2[code_col].astype(str).str.match(r"^\d{4,8}(\.0)?$", na=False)].copy()
    df2["code"] = df2[code_col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df2["score"] = pd.to_numeric(df2[score_col], errors="coerce")
    df2 = df2.dropna(subset=["score"])
    return df2[["code", "score"]]


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    frames = []
    report = []
    for city, page in PAGES:
        try:
            html = fetch(page, enc="gbk")
        except Exception as exc:  # noqa: BLE001
            report.append((city, "PAGE FAIL", str(exc)[:60]))
            continue
        atts = find_attachments(html, page)
        atts = [a for a in atts if not re.search(r"村干部|复审|邮箱|电话", urllib.parse.unquote(a))]
        got = None
        best = None
        for au in atts[:6]:
            try:
                blob = fetch(au, binary=True)
                suffix = ".xlsx" if "xlsx" in au.lower() else ".xls"
                dest = RAW / f"{city}_try{atts.index(au)}{suffix}"
                dest.write_bytes(blob)
                df = parse_table(dest)
                if df is not None and len(df):
                    if best is None or len(df) > len(best[0]):
                        best = (df, au)
            except Exception as exc:  # noqa: BLE001
                report.append((city, "DL FAIL", au[:60] + " " + str(exc)[:40]))
        if best:
            df, au = best
            df["city"] = city
            df["src"] = au
            frames.append(df)
            got = (len(df), au[:80])
        if got:
            print(f"[{city}] people={got[0]} src={got[1]}")
        else:
            report.append((city, "NO ATTACHMENT", "; ".join(a[:60] for a in atts[:3])))
            print(f"[{city}] no usable attachment; candidates={atts[:3]}")
        time.sleep(0.4)
    if frames:
        all_df = pd.concat(frames, ignore_index=True)
        agg = all_df.groupby("code")["score"].agg(adv="count", lo="min", top="max", avg="mean").reset_index()
        positions = [{"code": r["code"], "adv": int(r["adv"]), "lo": round(float(r["lo"]), 2),
                      "top": round(float(r["top"]), 2), "avg": round(float(r["avg"]), 2)}
                     for _, r in agg.iterrows()]
        payload = {
            "cycle": "2026",
            "generated_on": time.strftime("%Y-%m-%d"),
            "source": "安徽省2026省考各考区笔试达线人员成绩公告附件（先锋网/华图转载）逐岗汇总",
            "files": sorted({Path(f["src"].iloc[0]).name for _, f in pd.concat(frames, axis=0).groupby(level=0) for f in [_]}.union()) if False else None,
            "people": int(len(all_df)),
            "total": len(positions),
            "positions": sorted(positions, key=lambda p: p["code"]),
        }
        payload.pop("files", None)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print("wrote", OUT.name, payload["total"], "posts /", payload["people"], "people")
    for r in report:
        print("REPORT:", r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
