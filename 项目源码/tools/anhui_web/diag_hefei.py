# -*- coding: utf-8 -*-
"""诊断合肥职位表：哪些行被排除。"""
import pandas as pd

p = r"D:\AI\CatPaw\2\皖域择岗档案_网页产品化升级版_20260830_v9.4\source_data\anhui2025\raw\2025合肥市职位表.xlsx"
df = pd.read_excel(p, header=None)
print("shape:", df.shape)
for i in range(4):
    print("H", i, [str(x)[:14] for x in df.iloc[i].tolist()])
hdr = df.iloc[1].tolist()
body = df.iloc[2:].copy()
body.columns = [str(x).replace("\n", "").strip() for x in hdr]
print("body rows:", len(body))
# code-like rows vs not
c = body.iloc[:, 6].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
print("col6 sample:", c.head(3).tolist())
mask = c.str.match(r"^\d{5,7}$", na=False)
print("matched:", mask.sum(), "unmatched:", (~mask).sum())
print("--- unmatched rows (first 12):")
print(body.loc[~mask, :].head(12).to_string()[:2000])
