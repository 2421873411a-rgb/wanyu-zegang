# -*- coding: utf-8 -*-
"""回收 2026 上半年事业单位联考的逐岗成绩（xduim 镜像的官方公告附件）。

数据源：data/.zhaokao_syb_scan.json（xduim /zhaokao/detail/{id} 标题含
事业单位/联考/统考 且为 成绩/排名/复审/入围 类的公告，附 OSS 附件直链）。

两类名单：
  笔试成绩排名公告 → 逐岗考生成绩表：adv=有效笔试人数、top=最高、avg=平均
  资格复审/入围名单 → 逐岗入围人员：line=入围线（最低分）、rvw=入围人数

输出：data/syb2026_daxian_all.json（字段合并；列表记录 regions 供核对）
"""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw_syb_fugao"
SCAN = HERE / "data" / ".zhaokao_syb_scan.json"
OUT = HERE / "data" / "syb2026_daxian_all.json"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"


def get(url: str, binary: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.xduim.com/"})
    data = urllib.request.urlopen(req, timeout=90, context=CTX).read()
    return data if binary else data.decode("utf-8", "ignore")


def parse_excel(path: Path) -> pd.DataFrame | None:
    try:
        book = pd.read_excel(path, sheet_name=None, header=None)
    except Exception:
        return None
    best = None
    for df in book.values():
        parsed = _parse_sheet(df)
        if parsed is not None and (best is None or len(parsed) > len(best)):
            best = parsed
    return best


def _parse_sheet(df: pd.DataFrame) -> pd.DataFrame | None:
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
    code_ci = None
    score_cols = []
    for ci, h in enumerate(hdr):
        if code_ci is None and ("岗位代码" in h or "职位代码" in h):
            code_ci = ci
        if "成绩" in h or "分数" in h:
            score_cols.append(ci)
    if code_ci is None or not score_cols:
        return None
    # 成绩列：优先 笔试成绩/综合成绩，否则最后一个成绩列
    si = next((c for c in score_cols if "笔试成绩" in hdr[c]),
              next((c for c in score_cols if "综合成绩" in hdr[c]), score_cols[-1]))
    df2["code"] = df2[code_ci].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df2 = df2[df2["code"].str.match(r"^\d{6,8}$", na=False)]
    df2["score"] = pd.to_numeric(df2[si], errors="coerce")
    df2 = df2.dropna(subset=["score"])
    return df2[["code", "score"]] if len(df2) else None


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    jobs = [(int(i), h) for i, h in scan.items()
            if ("事业单位" in h["title"] or "联考" in h["title"] or "统考" in h["title"]) and h["atts"]]
    print("jobs:", len(jobs))
    rank_rows, review_rows = [], []
    ok = fail = 0
    for n, (pid, info) in enumerate(jobs, 1):
        title = info["title"]
        is_review = "复审" in title or "入围" in title or "面试人员" in title
        got = False
        for au in info["atts"][:2]:
            try:
                blob = get(au, binary=True)
                suffix = ".pdf" if ".pdf" in au.lower() else (".xlsx" if "xlsx" in au.lower() else ".xls")
                dest = RAW / f"syb_{pid:05d}{suffix}"
                dest.write_bytes(blob)
                df = parse_excel(dest) if suffix != ".pdf" else None
                if df is None or not len(df):
                    continue
                df["src"] = f"{pid}:{title[:40]}"
                (rank_rows if not is_review else review_rows).append(df)
                ok += 1
                got = True
                break
            except Exception:  # noqa: BLE001
                continue
        if not got:
            fail += 1
        if n % 20 == 0:
            print(f"  {n}/{len(jobs)} ok={ok} fail={fail}")
        time.sleep(0.12)
    print(f"downloaded ok={ok} fail={fail}")

    def agg(frames):
        if not frames:
            return {}
        all_df = pd.concat(frames, ignore_index=True)
        # D1(2026-09-05): 缺考 0 分不得参与最小分(入围线 lo)计算——此前 lo=min(score) 把 0 当最低分，
        # 造成 778 条 line==0 哨兵。lo 取正分最小值；单列 n_zero/all_zero 供量纲闸门与对账；全 0 时 lo=None（落盘为空，不补 0）。
        pos_df = all_df[all_df["score"] > 0]
        g_pos = pos_df.groupby("code")["score"]
        stats = {str(k): {"adv": int(v["count"]), "lo": round(float(v["min"]), 2),
                          "top": round(float(v["max"]), 2), "avg": round(float(v["mean"]), 2)}
                 for k, v in g_pos.agg(["count", "min", "max", "mean"]).iterrows()}
        zero_counts = all_df[all_df["score"] == 0].groupby("code")["score"].size().to_dict()
        full_counts = all_df.groupby("code")["score"].size().to_dict()
        for code, total in full_counts.items():
            st = stats.setdefault(str(code), {"adv": int(total), "lo": None, "top": None, "avg": None})
            st["adv"] = int(total)
            st["n_zero"] = int(zero_counts.get(code, 0))
            st["all_zero"] = st["n_zero"] == int(total)
            if "top" not in st or st["top"] is None:
                st["top"] = round(float(all_df.loc[all_df["code"] == code, "score"].max()), 2)
        return stats

    rank = agg(rank_rows)
    review = agg(review_rows)
    codes = set(rank) | set(review)
    positions = []
    for c in sorted(codes):
        r, v = rank.get(c, {}), review.get(c, {})
        positions.append({
            "code": c,
            "adv": r.get("adv") or v.get("adv"),
            "top": r.get("top") or v.get("top"),
            "avg": r.get("avg"),
            "line": v.get("lo") or r.get("lo"),
            "rank_src": bool(r), "review_src": bool(v),
        })
    payload = {
        "cycle": "2026",
        "generated_on": time.strftime("%Y-%m-%d"),
        "source": "2026上半年事业单位联考笔试成绩排名/资格复审公告（各市县人社局/政府，xduim 镜像附件）逐岗汇总",
        "rank_announcements": len(rank_rows),
        "review_announcements": len(review_rows),
        "total": len(positions),
        "positions": positions,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT.name, payload["total"], "posts (rank:", len(rank), "review:", len(review), ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
