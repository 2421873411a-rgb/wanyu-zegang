# -*- coding: utf-8 -*-
"""临时勘察脚本：查看省考分析所需 JSON 的结构。"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

def peek(name, max_rows=2):
    p = os.path.join(DATA, name)
    with open(p, encoding="utf-8") as f:
        obj = json.load(f)
    print("=" * 70)
    print(name, "| type:", type(obj).__name__)
    if isinstance(obj, dict):
        print("top keys:", list(obj.keys())[:12])
        for k, v in obj.items():
            if isinstance(v, list) and v:
                print(f"  [{k}] list len={len(v)}; sample keys: {list(v[0].keys()) if isinstance(v[0], dict) else v[0]}")
                for row in v[:max_rows]:
                    print("   ", json.dumps(row, ensure_ascii=False)[:600])
            elif isinstance(v, dict):
                ks = list(v.keys())[:5]
                print(f"  [{k}] dict len={len(v)}; first keys: {ks}")
                for kk in ks[:max_rows]:
                    print("   ", kk, "->", json.dumps(v[kk], ensure_ascii=False)[:400])
            else:
                print(f"  [{k}] = {json.dumps(v, ensure_ascii=False)[:200]}")
    elif isinstance(obj, list):
        print("len:", len(obj))
        for row in obj[:max_rows]:
            print("  ", json.dumps(row, ensure_ascii=False)[:600])

peek("all_majors_2026.json")
peek("ahsk2026_official.json")
peek("ahsk2026_daxian_full.json")
peek("ahsk2026_hire.json")
peek("major_catalog.json")
