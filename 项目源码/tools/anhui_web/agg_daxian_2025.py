# -*- coding: utf-8 -*-
"""聚合17考区达线名单：逐人→逐岗，与 ahsk2025_scores.json (4116岗) 对账。"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

RAW = Path(r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\source_data\anhui2025\raw")
FSX = Path(r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\tools\anhui_web\data\ahsk2025_scores.json")


def parse_table(path: Path) -> pd.DataFrame | None:
    """xls/xlsx 自适应表头，抽 职位代码+成绩。"""
    try:
        df = pd.read_excel(path, sheet_name=0, header=None)
    except Exception as exc:
        print("  parse fail:", exc)
        return None
    return _extract(df)


def _extract(df: pd.DataFrame) -> pd.DataFrame | None:
    for hrow in range(min(10, len(df))):
        hdr = [re.sub(r"\s", "", str(x)) for x in df.iloc[hrow].tolist()]
        code_col = next((i for i, h in enumerate(hdr) if "职位代码" in h or h == "岗位代码"), None)
        if code_col is None:
            continue
        score_col = next((i for i, h in enumerate(hdr)
                          if "笔试成绩" in h or "成绩合计" in h or "合成成绩" in h or h == "总成绩"), None)
        body = df.iloc[hrow + 1:].copy()
        if score_col is None:
            xc = next((i for i, h in enumerate(hdr) if "行测" in h), None)
            sl = next((i for i, h in enumerate(hdr) if "申论" in h), None)
            if xc is not None and sl is not None:
                body["_score"] = (pd.to_numeric(body.iloc[:, xc], errors="coerce")
                                  + pd.to_numeric(body.iloc[:, sl], errors="coerce"))
                score_col = "_score"
            else:
                continue
        code = body.iloc[:, code_col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        score = (body["_score"] if score_col == "_score"
                 else pd.to_numeric(body.iloc[:, score_col], errors="coerce"))
        keep = code.str.match(r"^\d{5,7}$", na=False) & score.notna()
        if keep.sum() > 10:
            out = pd.DataFrame({"code": code[keep], "score": score[keep]}).reset_index(drop=True)
            out["city"] = ""
            return out
    return None


def parse_pdf(path: Path) -> pd.DataFrame | None:
    """安庆类文本表格PDF：text策略重建表格，按列位置取 职位代码+笔试成绩。"""
    import pymupdf
    doc = pymupdf.open(path)
    rows = []
    for page in doc:
        tabs = page.find_tables(strategy="text")
        for t in tabs.tables:
            for r in t.extract():
                r = [("" if c is None else str(c).strip()) for c in r]
                if len(r) >= 7 and re.match(r"^\d{10,12}$", r[0]) and re.match(r"^\d{5,7}$", r[1]):
                    # 末列=划线分类，倒数第2列=笔试成绩
                    rows.append((r[1], r[-2]))
    doc.close()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["code", "score"])
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    return df.dropna(subset=["score"])


def main() -> None:
    frames = []
    rep = []
    for f in sorted(RAW.glob("daxian_*")):
        city = f.stem.split("_")[1]
        df = parse_pdf(f) if f.suffix.lower() == ".pdf" else parse_table(f)
        if df is None or not len(df):
            rep.append((city, f.name, "FAIL", 0, 0))
            continue
        df["city"] = city
        frames.append(df)
        rep.append((city, f.name, "OK", len(df), df["code"].nunique()))
    print(f"{'city':10s} {'file':40s} {'st':4s} {'people':>7s} {'posts':>6s}")
    total_p = total_c = 0
    for city, name, st, p, c in rep:
        print(f"{city:10s} {name:40s} {st:4s} {p:7d} {c:6d}")
        if st == "OK":
            total_p += p
            total_c += c
    print(f"\nTOTAL people={total_p} posts={total_c} (fsx=4116)")

    all_df = pd.concat(frames, ignore_index=True)
    all_df.to_csv(RAW.parent / "daxian_2025_people.csv", index=False, encoding="utf-8-sig")
    agg = all_df.groupby("code").size()
    fsx = {p["code"] for p in json.load(open(FSX, encoding="utf-8"))["positions"]}
    codes = set(agg.index)
    print(f"aggregated posts={len(codes)}")
    print(f"达线有而fsx无: {len(codes - fsx)} -> {sorted(codes - fsx)[:20]}")
    print(f"fsx有而达线无: {len(fsx - codes)} -> {sorted(fsx - codes)[:40]}")


import json  # noqa: E402

if __name__ == "__main__":
    main()
