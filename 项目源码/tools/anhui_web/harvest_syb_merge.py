# -*- coding: utf-8 -*-
"""事业编成绩增量合并：只处理指定公告 ID，下载→解析→合并进 syb2026_daxian_all.json。

用法：python harvest_syb_merge.py 37378 37385 37381 37349
自动备份现有 OUT 为 syb2026_daxian_all.backup.json。
合并规则：新 code 追加；已有 code 仅补缺失字段（不覆盖已有值）。
"""
from __future__ import annotations

import json
import shutil
import ssl
import sys
import time
import urllib.request
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


def get(url: str, binary: bool = False, referer: str = "https://www.xduim.com/"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
    data = urllib.request.urlopen(req, timeout=90, context=CTX).read()
    return data if binary else data.decode("utf-8", "ignore")


def parse_excel(path: Path):
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


def _parse_sheet(df: pd.DataFrame):
    hrow = None
    for i in range(min(12, len(df))):
        txt = re.sub(r"\s", "", "".join(str(x) for x in df.iloc[i].tolist()))
        if ("岗位代码" in txt or "职位代码" in txt) and ("成绩" in txt or "分数" in txt or "总分" in txt):
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
    si = next((c for c in score_cols if "笔试成绩" in hdr[c]),
              next((c for c in score_cols if "综合成绩" in hdr[c]), score_cols[-1]))
    df2["code"] = df2[code_ci].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df2 = df2[df2["code"].str.match(r"^\d{3,9}$", na=False)]
    df2["score"] = pd.to_numeric(df2[si], errors="coerce")
    df2 = df2.dropna(subset=["score"])
    return df2[["code", "score"]] if len(df2) else None


import re  # noqa: E402  （放底部仅为可读性）

def main() -> int:
    ids = [int(a) for a in sys.argv[1:] if a.isdigit()]
    if not ids:
        print("用法: python harvest_syb_merge.py <公告ID...>")
        return 1
    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    out = json.loads(OUT.read_text(encoding="utf-8"))
    backup = OUT.with_name("syb2026_daxian_all.backup.json")
    shutil.copyfile(OUT, backup)
    print(f"已备份 → {backup.name}（现有 {out['total']} 岗）")

    by_code = {str(p["code"]): p for p in out["positions"]}
    added = updated = 0
    new_codes = set()
    ok = fail = 0
    for pid in ids:
        info = scan.get(str(pid))
        if not info:
            print(f"  {pid}: 扫描记录不存在，跳过")
            continue
        title = info.get("title", "")
        is_review = "复审" in title or "入围" in title or "面试人员" in title
        got_any = False
        for au in info.get("atts", [])[:4]:
            try:
                blob = get(au, binary=True)
                suffix = ".pdf" if ".pdf" in au.lower() else (".xlsx" if "xlsx" in au.lower() else ".xls")
                dest = RAW / f"syb_{pid:05d}{suffix}"
                dest.write_bytes(blob)
                df = parse_excel(dest) if suffix != ".pdf" else None
                if df is None or not len(df):
                    continue
                g = df.groupby("code")["score"].agg(["count", "min", "max", "mean"])
                touched = 0
                for code, v in g.iterrows():
                    code = str(code)
                    rec = {"adv": int(v["count"]), "lo": round(float(v["min"]), 2),
                           "top": round(float(v["max"]), 2), "avg": round(float(v["mean"]), 2)}
                    p = by_code.get(code)
                    if p is None:
                        np_ = {"code": code,
                               "adv": rec["adv"], "top": rec["top"],
                               "avg": rec["avg"],
                               "line": rec["lo"] if is_review else None,
                               "rank_src": not is_review, "review_src": is_review}
                        by_code[code] = np_
                        out["positions"].append(np_)
                        new_codes.add(code)
                        added += 1
                    else:
                        chg = False
                        for src_key, dst_key in (("adv", "adv"), ("top", "top"), ("avg", "avg")):
                            if p.get(dst_key) is None and rec[src_key] is not None:
                                p[dst_key] = rec[src_key]
                                chg = True
                        if is_review and p.get("line") is None:
                            p["line"] = rec["lo"]
                            chg = True
                        if chg:
                            updated += 1
                        touched += 1
                    got_any = got_any or touched > 0
                ok += 1
                print(f"  {pid}: {title[:36]} → 解析 {len(df)} 行（新 {len(g) - touched} 已有 {touched}）")
                break
            except Exception as e:  # noqa: BLE001
                print(f"  {pid}: 附件失败 {type(e).__name__}: {str(e)[:60]}")
                continue
        else:
            fail += 1
            continue
        if not got_any and ok:
            pass
        time.sleep(0.3)

    out["total"] = len(out["positions"])
    out["generated_on"] = time.strftime("%Y-%m-%d")
    note = f"（合并增量 {time.strftime('%Y-%m-%d %H:%M')}：+{added} 新岗 / {updated} 岗补字段，来源 ID {ids}）"
    out["source"] = (out.get("source") or "") + note
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n完成：新增 {added} 岗，补字段 {updated} 岗，总计 {out['total']} 岗 → {OUT.name}")
    print("新增岗 code 前缀分布:", sorted({c[:4] for c in new_codes}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
