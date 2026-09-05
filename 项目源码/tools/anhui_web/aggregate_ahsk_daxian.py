# -*- coding: utf-8 -*-
"""把 data/raw_daxian/ 下各考区达线名单（xls/xlsx/pdf）逐岗汇总为 ahsk2026_daxian_all.json。

文件命名 {城市}.xls/.xlsx/.pdf；xls/xlsx 由通用表格解析，PDF 按安庆式逐人文本流解析。
输出字段：code → {adv 达线人数, lo 最低, top 最高, avg 平均}。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pandas as pd
import pymupdf

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw_daxian"
OUT = HERE / "data" / "ahsk2026_daxian_all.json"


def parse_xlsx(path: Path) -> pd.DataFrame | None:
    from hunt_daxian_files import parse_table
    df = parse_table(path)
    if df is None or not len(df):
        return None
    df = df.copy()
    df["city"] = path.stem
    return df[["code", "score", "city"]]


def parse_pdf(path: Path) -> pd.DataFrame | None:
    doc = pymupdf.open(path)
    recs = []
    cur: dict = {}

    def flush():
        nonlocal cur
        if cur and cur.get("code") and cur.get("score") is not None:
            recs.append(cur)
        cur = {}

    for pno in range(len(doc)):
        for tok in doc[pno].get_text().split():
            tok = tok.strip()
            if re.fullmatch(r"\d{12}", tok):
                flush()
                cur = {"zkz": tok}
            elif cur is None:
                continue
            elif re.fullmatch(r"\d{6}", tok) and "code" not in cur:
                cur["code"] = tok
            elif re.fullmatch(r"\d+(\.\d+)?", tok):
                cur["score"] = float(tok)
    flush()
    if not recs:
        return None
    df = pd.DataFrame(recs)
    df["city"] = path.stem
    return df[["code", "score", "city"]]


def main() -> int:
    frames = []
    seen_files = []
    for path in sorted(RAW.iterdir()):
        if path.suffix.lower() in (".xls", ".xlsx"):
            df = parse_xlsx(path)
        elif path.suffix.lower() == ".pdf":
            df = parse_pdf(path)
        else:
            continue
        if df is None or not len(df):
            print("skip:", path.name)
            continue
        frames.append(df)
        seen_files.append(path.name)
        print(f"{path.name}: {len(df)} people, {df['code'].nunique()} posts")
    if not frames:
        print("no data")
        return 1
    all_df = pd.concat(frames, ignore_index=True)
    # 同一职位代码跨考区不会冲突（前缀独立），直接按代码聚合
    agg = all_df.groupby("code")["score"].agg(adv="count", lo="min", top="max", avg="mean").reset_index()
    positions = [{"code": str(r["code"]), "adv": int(r["adv"]), "lo": round(float(r["lo"]), 2),
                  "top": round(float(r["top"]), 2), "avg": round(float(r["avg"]), 2)}
                 for _, r in agg.iterrows()]
    payload = {
        "cycle": "2026",
        "generated_on": time.strftime("%Y-%m-%d"),
        "source": "安徽省2026省考各考区笔试达线人员成绩公告附件（各市先锋网官方）逐岗汇总",
        "regions": seen_files,
        "people": int(len(all_df)),
        "total": len(positions),
        "positions": sorted(positions, key=lambda p: p["code"]),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT.name, payload["total"], "posts /", payload["people"], "people")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
