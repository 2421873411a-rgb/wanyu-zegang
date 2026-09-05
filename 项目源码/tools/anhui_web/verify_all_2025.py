# -*- coding: utf-8 -*-
"""全量核查 anhui2025/raw 下所有文件：可打开性、行列数/页数、大小。"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

RAW = Path(r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\source_data\anhui2025\raw")
OUT = Path(r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\source_data\anhui2025\raw_manifest.csv")


def check(f: Path) -> dict:
    size = f.stat().st_size
    r = {"file": f.name, "size": size, "status": "OK", "detail": ""}
    if f.suffix.lower() in (".xls", ".xlsx"):
        try:
            xl = pd.ExcelFile(f)
            df = xl.parse(xl.sheet_names[0], header=None)
            r["detail"] = f"sheets={len(xl.sheet_names)} rows={df.shape[0]} cols={df.shape[1]}"
            if df.shape[0] < 2:
                r["status"] = "SUSPECT"
        except Exception as exc:
            r["status"] = "FAIL"
            r["detail"] = str(exc)[:60]
    elif f.suffix.lower() == ".pdf":
        try:
            import pymupdf
            doc = pymupdf.open(f)
            txt = doc[0].get_text()[:50]
            r["detail"] = f"pages={len(doc)} head={txt[:20]!r}"
            doc.close()
        except Exception as exc:
            r["status"] = "FAIL"
            r["detail"] = str(exc)[:60]
    elif f.suffix.lower() == ".docx":
        try:
            with zipfile.ZipFile(f) as z:
                ok = "word/document.xml" in z.namelist()
            r["detail"] = f"docx ok={ok}"
            if not ok:
                r["status"] = "SUSPECT"
        except Exception as exc:
            r["status"] = "FAIL"
            r["detail"] = str(exc)[:60]
    if size <= 2048:
        r["status"] = "TOO_SMALL"
    return r


def main() -> None:
    rows = []
    for f in sorted(RAW.iterdir()):
        if f.is_file():
            rows.append(check(f))
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    bad = df[df["status"] != "OK"]
    print(f"total files={len(df)} ok={len(df) - len(bad)} bad={len(bad)}")
    if len(bad):
        print(bad.to_string())
    print("manifest ->", OUT)


if __name__ == "__main__":
    main()
