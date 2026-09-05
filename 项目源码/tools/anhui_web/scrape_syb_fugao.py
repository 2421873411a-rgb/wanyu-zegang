# -*- coding: utf-8 -*-
"""抓取 2026 上半年事业单位联考 各市县/单位 资格复审·成绩排名公告（261 链接），
从附件/内联表提取 岗位代码→成绩 列表，逐岗汇总为 syb2026_daxian_all.json。

名单语义：复审名单=入围人员（line=入围线、adv=入围人数）；成绩排名=达线全员。
解析列自适应：找含“岗位代码/职位代码”与成绩（笔试成绩/综合成绩/成绩）的表。
输出同时保留 region（公告标题截断）便于核对。
"""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw_syb_fugao"
OUT = HERE / "data" / "syb2026_daxian_all.json"
_PKG_SRC3 = Path(__file__).resolve().parents[2] / "source_data" / "anhui2026"
INDEX = _PKG_SRC3 / "shiyebian_fugao_index.csv" if _PKG_SRC3.is_dir() else Path(r"D:/AI/zcode/zcode 2/anhui2026/shiyebian_fugao_index.csv")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"


def get(url: str, binary: bool = False, referer: str = ""):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": referer or url,
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    data = urllib.request.urlopen(req, timeout=60, context=CTX).read()
    if binary:
        return data
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore")


def index_links() -> list[str]:
    idx = pd.read_csv(INDEX, dtype=str).fillna("")
    links = []
    for col in idx.columns:
        for v in idx[col]:
            for u in re.findall(r"https?://[^\s|]+", v):
                if "huatu.com/20" in u:
                    links.append(u.strip())
    return list(dict.fromkeys(links))


def attachments(html: str, base: str) -> list[str]:
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
    return list(dict.fromkeys(out))


def parse_sheet(df: pd.DataFrame) -> pd.DataFrame | None:
    """在无表头 sheet 中定位 岗位代码列 与 成绩列。"""
    hrow = None
    for i in range(min(12, len(df))):
        txt = "".join(str(x) for x in df.iloc[i].tolist())
        if ("岗位代码" in txt or "职位代码" in txt) and ("成绩" in txt or "分数" in txt):
            hrow = i
            break
    if hrow is None:
        return None
    hdr = [re.sub(r"\s", "", str(x)) for x in df.iloc[hrow].tolist()]
    df2 = df.iloc[hrow + 1:].copy()
    df2.columns = range(len(hdr))
    code_ci = score_ci = None
    for ci, h in enumerate(hdr):
        if code_ci is None and ("岗位代码" in h or "职位代码" in h):
            code_ci = ci
        if "成绩" in h or "分数" in h:
            score_ci = ci  # 取最后一个成绩列（综合/笔试成绩在后）
    if code_ci is None or score_ci is None:
        return None
    df2["code"] = df2[code_ci].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df2 = df2[df2["code"].str.match(r"^\d{6,8}$", na=False)]
    df2["score"] = pd.to_numeric(df2[score_ci], errors="coerce")
    df2 = df2.dropna(subset=["score"])
    if not len(df2):
        return None
    return df2[["code", "score"]]


def parse_excel(path: Path) -> pd.DataFrame | None:
    try:
        book = pd.read_excel(path, sheet_name=None, header=None)
    except Exception:
        return None
    best = None
    for df in book.values():
        parsed = parse_sheet(df)
        if parsed is not None and (best is None or len(parsed) > len(best)):
            best = parsed
    return best


def parse_inline_tables(html: str) -> pd.DataFrame | None:
    rows = []
    for tb in re.findall(r"<table[^>]*>(.*?)</table>", html, re.S):
        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)
        if len(trs) < 2:
            continue
        grid = []
        for tr in trs:
            cells = [re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", c)) for c in
                     re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            grid.append(cells)
        head = next((i for i, g in enumerate(grid)
                     if any(("岗位代码" in c or "职位代码" in c) for c in g)
                     and any("成绩" in c or "分数" in c for c in g)), None)
        if head is None:
            continue
        hdr = grid[head]
        code_cols = [i for i, c in enumerate(hdr) if "岗位代码" in c or "职位代码" in c]
        score_cols = [i for i, c in enumerate(hdr) if "成绩" in c or "分数" in c]
        if not code_cols or not score_cols:
            continue
        ci, si = code_cols[0], score_cols[-1]
        for g in grid[head + 1:]:
            if len(g) <= max(ci, si):
                continue
            code = g[ci].strip()
            if re.fullmatch(r"\d{6,8}", code):
                try:
                    rows.append({"code": code, "score": float(g[si])})
                except ValueError:
                    continue
    if not rows:
        return None
    return pd.DataFrame(rows)


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    links = index_links()
    print("links:", len(links))
    frames = []
    ok_pages = att_pages = 0
    for n, url in enumerate(links, 1):
        try:
            html = get(url)
        except Exception as exc:  # noqa: BLE001
            print(f"[{n}] PAGE FAIL {url[-40:]} {exc}")
            continue
        ok_pages += 1
        got = False
        # 1) 附件
        for au in attachments(html, url)[:3]:
            try:
                blob = get(au, binary=True, referer=url)
                dest = RAW / f"{n:03d}_{Path(urllib.parse.unquote(au)).name}"
                dest.write_bytes(blob)
                df = parse_excel(dest)
                if df is not None and len(df):
                    df["region"] = f"#{n}"
                    df["src"] = au
                    frames.append(df)
                    att_pages += 1
                    got = True
                    break
            except Exception:  # noqa: BLE001
                continue
        # 2) 内联表
        if not got:
            df = parse_inline_tables(html)
            if df is not None and len(df):
                df["region"] = f"#{n}"
                df["src"] = url
                frames.append(df)
                got = True
        print(f"[{n}/{len(links)}] {'OK ' + str(len(frames[-1])) if got else 'empty'} {url[-36:]}", end="\n" if got else "\r")
        time.sleep(0.15)
    print()
    if not frames:
        print("no data parsed")
        return 1
    all_df = pd.concat(frames, ignore_index=True)
    agg = all_df.groupby("code")["score"].agg(adv="count", lo="min", top="max", avg="mean").reset_index()
    positions = [{"code": str(r["code"]), "adv": int(r["adv"]), "lo": round(float(r["lo"]), 2),
                  "top": round(float(r["top"]), 2), "avg": round(float(r["avg"]), 2)}
                 for _, r in agg.iterrows()]
    payload = {
        "cycle": "2026",
        "generated_on": time.strftime("%Y-%m-%d"),
        "source": "2026上半年事业单位联考 各市县/单位资格复审·成绩排名公告（华图转载汇总）逐岗提取",
        "pages_ok": ok_pages,
        "pages_parsed": len(frames),
        "people": int(len(all_df)),
        "total": len(positions),
        "positions": sorted(positions, key=lambda p: p["code"]),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT.name, payload["total"], "posts /", payload["people"], "people / parsed", payload["pages_parsed"], "pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
