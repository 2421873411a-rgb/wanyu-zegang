# -*- coding: utf-8 -*-
"""临时勘察 2：字段取值分布，为分析口径定标。"""
import json, os, re
from collections import Counter

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
am = json.loads(open(os.path.join(DATA, "all_majors_2026.json"), encoding="utf-8").read())
pos = am["positions"]
print("positions:", len(pos), "total recruits:", sum(p["recruits"] for p in pos))

for field in ("xueli", "xuewei", "jigou_cengci", "jigou_xingzhi", "zhiwei_leibie", "shenlun", "city"):
    c = Counter((p.get(field) or "").strip() or "（空）" for p in pos)
    print(f"\n[{field}] {len(c)} distinct:", c.most_common(20))

# 专业要求 token 形态抽样
tok = Counter()
samples = {}
for p in pos:
    for item in re.split(r"[、，,；;/\s]+", p["zhuanye"]):
        item = re.sub(r"^(?:本科|研究生|硕士|博士)：", "", item.strip())
        if not item:
            continue
        key = "不限" if item in ("不限", "专业不限", "不限专业") else (
            "带括号注" if "（" in item else ("大类（*类/门类）" if item.endswith(("类", "门类")) else "具体专业名"))
        tok[key] += 1
        samples.setdefault(key, [])
        if len(samples[key]) < 12:
            samples[key].append(item)
print("\n[token 形态]:", dict(tok))
for k, v in samples.items():
    print(f"  {k}: {v}")

# 不限专业岗位规模
no_limit = [p for p in pos if p["zhuanye"].strip() in ("不限", "专业不限", "不限专业")]
print("\n不限专业岗位:", len(no_limit), "招录:", sum(p["recruits"] for p in no_limit))

# 学历口径细分
print("\n[xueli 原文去重]", Counter(p["xueli"] for p in pos).most_common())

# hire json 覆盖
hire = json.loads(open(os.path.join(DATA, "ahsk2026_hire.json"), encoding="utf-8").read())
with_score = [h for h in hire["positions"] if h.get("hs") is not None or h.get("ht") is not None]
print("\nhire people:", hire["people"], "rows:", len(hire["positions"]), "有成绩 rows:", len(with_score),
      "有成绩岗位:", len({h['code'] for h in with_score}))

# official bm 汇总
off = json.loads(open(os.path.join(DATA, "ahsk2026_official.json"), encoding="utf-8").read())
bm = sum(p["bm"] or 0 for p in off["positions"])
hg = sum(p["hg"] or 0 for p in off["positions"])
jf = sum(p["jf"] or 0 for p in off["positions"])
print(f"\n省考大盘: 报名 {bm:,} 审查合格 {hg:,} 缴费 {jf:,}")
print("line 非空:", sum(1 for p in off["positions"] if p.get("line") is not None))
