# -*- coding: utf-8 -*-
"""验证2025省考各职位表：行数、职位代码数、招考人数合计。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW = Path(r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\source_data\anhui2025\raw")

EXPECTED = {  # 官方公告口径
    "省直": 721, "合肥市": 710, "淮北市": 235, "亳州市": 455, "宿州市": 528,
    "蚌埠市": 364, "阜阳市": 402, "淮南市": 540, "滁州市": 432, "六安市": 525,
    "马鞍山市": 346, "芜湖市": 499, "宣城市": 502, "铜陵市": 305, "池州市": 374,
    "安庆市": 688, "黄山市": 396,
}

NUM_KEYS = ("招考人数", "招录人数", "人数")
CODE_KEYS = ("职位代码", "岗位代码")


def scan(df: pd.DataFrame) -> dict:
    """在任意表头偏移下定位职位代码列与人数列。"""
    best = None
    for hrow in range(min(6, len(df))):
        hdr = [str(x).replace("\n", "").strip() for x in df.iloc[hrow].tolist()]
        code_col = next((i for i, h in enumerate(hdr) if any(k in h for k in CODE_KEYS)), None)
        if code_col is None:
            continue
        num_col = next((i for i, h in enumerate(hdr) if any(k in h for k in NUM_KEYS)), None)
        if num_col is None:
            continue
        body = df.iloc[hrow + 1:].copy()
        body["code"] = body[code_col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        body = body[body["code"].str.match(r"^\d{5,7}$", na=False)]
        body["num"] = pd.to_numeric(body.iloc[:, num_col], errors="coerce")
        body = body.dropna(subset=["num"])
        if len(body):
            best = {"rows": int(len(body)), "codes": int(body["code"].nunique()),
                    "sum": float(body["num"].sum())}
            break
    return best or {}


def main() -> None:
    grand_rows = grand_codes = 0
    grand_sum = 0.0
    for f in sorted(RAW.glob("2025*职位表.*")):
        try:
            xl = pd.ExcelFile(f)
            df = xl.parse(xl.sheet_names[0], header=None)
        except Exception as exc:
            print(f"{f.name}: PARSE FAIL {exc}")
            continue
        info = scan(df)
        key = f.stem.replace("2025", "").replace("职位表", "")
        exp = EXPECTED.get(key)
        flag = ""
        if exp and info:
            flag = "OK" if abs(info["sum"] - exp) < 1 else f"MISMATCH(exp={exp})"
        print(f"{f.name}: rows={info.get('rows')} codes={info.get('codes')} "
              f"sum={info.get('sum')} {flag}")
        if key != "选调生" and info:
            grand_rows += info["rows"]
            grand_codes += info["codes"]
            grand_sum += info["sum"]
    print(f"\nGRAND(civil only): rows={grand_rows} codes={grand_codes} sum={grand_sum} (公告=8022)")


if __name__ == "__main__":
    main()
