# -*- coding: utf-8 -*-
"""把另一工作区（zcode 2/anhui2026）汇编的官方数据转换为构建管线用的 JSON。

输入（默认 D:/AI/zcode/zcode 2/anhui2026，可用环境变量 WANYU2_SRC 覆盖）：
  shengkao_details.csv            省考逐岗：报名/合格/缴费/笔试分数线（3784，全对齐）
  shengkao_kaokaochengji.csv      分考区达线汇总（18 考区）
  raw/shengkao_shengzhi_daxian.xls 省直笔试达线人员名单（12366 人 / 239 岗）
  shiyebian_bgt_daxian.csv        事业编省直达线人员（单岗 3000061，279 人）
  raw/2026guokao_anhui.xlsx       2026 国考安徽职位表（551 岗）
  guokao_anhui_jinmian.csv        国考安徽进面名单（逐人）

输出（tools/anhui_web/data/）：
  ahsk2026_official.json     省考官方逐岗 bm/hg/jf/line + 考区汇总
  ahsk2026_daxian_szzk.json  省直逐岗 达线人数/最高/平均/最低（来自达线名单）
  syb2026_bgt_daxian.json    事业编省直逐岗达线汇总
  guokao2026.json            国考全量岗位（专业/学历已归一化）+ 进面统计
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pandas as pd
import time

_PKG_SRC = Path(__file__).resolve().parents[2] / "source_data" / "anhui2026"
_SRC_ENV = os.environ.get("WANYU2_SRC")
SRC = Path(_SRC_ENV) if _SRC_ENV else (_PKG_SRC if _PKG_SRC.is_dir() else Path("D:/AI/zcode/zcode 2/anhui2026"))
OUT = Path(__file__).resolve().parent / "data"

CITY_RE = re.compile(r"^安徽省(.+?)市")


def _num(x):
    try:
        v = float(x)
        return int(v) if v == int(v) else round(v, 2)
    except (TypeError, ValueError):
        return None


def _norm_guokao_zy(text: str) -> str:
    """国考专业列归一化：
    “大学本科：0305马克思主义理论类、1202工商管理类；研究生：1202工商管理学（审计学）、1257审计”
    → “本科：马克思主义理论类、工商管理类；研究生：工商管理学（审计学）、审计”
    """
    text = (text or "").strip()
    if not text:
        return ""
    segs = []
    for seg in re.split(r"[；;]", text):
        seg = seg.strip()
        if not seg:
            continue
        seg = re.sub(r"^(大学本科|本科|硕士研究生|研究生|硕士|博士)\s*[：:]", lambda m: ("研究生：" if m.group(1) in ("硕士研究生", "研究生", "硕士") else "本科："), seg)
        items = []
        for item in re.split(r"[、，,]", seg):
            item = item.strip()
            if not item:
                continue
            item = re.sub(r"^\d{4}(?=[\u4e00-\u9fff])", "", item)  # 去前缀专业代码
            if re.search(r"[\dA-Za-z][）)]$", item):
                item = re.sub(r"[（(][\dA-Za-z]+[）)]$", "", item)  # 去括号内纯代码，如 财务管理（1202Z1）
            if re.search(r"类$", item):
                item = re.sub(r"[（(][^（）()]*[)）]$", "", item)  # 大类去掉括注，如 交通运输类（交通运输）
            items.append(item)
        if items:
            segs.append("、".join(items))
    return "；".join(segs)


def convert_shengkao_official():
    det = pd.read_csv(SRC / "shengkao_details.csv", dtype=str)
    positions = []
    for _, r in det.iterrows():
        positions.append({
            "code": str(r["职位代码"]).strip(),
            "bm": _num(r.get("报名人数")),
            "hg": _num(r.get("合格人数")),
            "jf": _num(r.get("缴费人数")),
            "line": _num(r.get("笔试分数线")),
        })
    kq = pd.read_csv(SRC / "shengkao_kaokaochengji.csv", dtype=str)
    kaokao = []
    for _, r in kq.iterrows():
        kaokao.append({
            "region": str(r.iloc[0]).strip(),
            "daxian": _num(r.get("达合格线人数")),
            "avg": _num(r.get("达合格线平均分")),
            "runei": _num(r.get("拟入围人数")),
            "ratio": str(r.get("占比") or "").strip(),
            "lo": _num(r.get("拟入围最低分")),
            "hi": _num(r.get("拟入围最高分")),
            "mean": _num(r.get("拟入围平均分")),
        })
    payload = {
        "cycle": "2026",
        "generated_on": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "source": "安徽省2026年度考试录用公务员（报名/合格/缴费/笔试分数线官方汇编）",
        "total": len(positions),
        "coverage": {k: sum(1 for p in positions if p[k] is not None) for k in ("bm", "hg", "jf", "line")},
        "positions": sorted(positions, key=lambda p: p["code"]),
        "kaokao": kaokao,
    }
    (OUT / "ahsk2026_official.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ahsk2026_official.json:", payload["total"], payload["coverage"])


def convert_shengzhi_daxian():
    dx = pd.read_excel(SRC / "raw" / "shengkao_shengzhi_daxian.xls", sheet_name=0, header=2)
    dx.columns = ["准考证号", "职位代码", "行测成绩", "申论类别", "申论成绩",
                  "专业科目", "专业成绩", "笔试成绩", "划线分类"]
    dx = dx.dropna(subset=["职位代码"])
    dx["职位代码"] = dx["职位代码"].astype(float).astype(int).astype(str)
    dx["笔试成绩"] = pd.to_numeric(dx["笔试成绩"], errors="coerce")
    g = dx.groupby("职位代码")["笔试成绩"]
    agg = pd.DataFrame({"adv": g.count(), "lo": g.min(), "top": g.max(), "avg": g.mean().round(2)})
    positions = [{"code": c, "adv": int(r["adv"]), "lo": _num(r["lo"]),
                  "top": _num(r["top"]), "avg": _num(r["avg"])}
                 for c, r in agg.iterrows()]
    payload = {
        "cycle": "2026",
        "generated_on": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "source": "安徽省2026省考省直考区笔试达到合格分数线人员名单（逐岗汇总）",
        "people": int(len(dx)),
        "total": len(positions),
        "positions": sorted(positions, key=lambda p: p["code"]),
    }
    (OUT / "ahsk2026_daxian_szzk.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ahsk2026_daxian_szzk.json:", payload["total"], "posts /", payload["people"], "people")


def convert_syb_bgt():
    bgt = pd.read_csv(SRC / "shiyebian_bgt_daxian.csv", dtype=str)
    bgt = bgt.iloc[1:].copy()
    bgt.columns = ["准考证号", "岗位代码", "职测成绩", "综合应用成绩", "笔试成绩"]
    bgt["笔试成绩"] = pd.to_numeric(bgt["笔试成绩"], errors="coerce")
    bgt["岗位代码"] = bgt["岗位代码"].astype(str).str.strip()
    positions = []
    for code, g in bgt.groupby("岗位代码"):
        s = g["笔试成绩"].dropna()
        if s.empty:
            continue
        positions.append({
            "code": code, "adv": int(len(s)), "lo": _num(s.min()),
            "top": _num(s.max()), "avg": _num(round(s.mean(), 2)),
        })
    payload = {
        "cycle": "2026",
        "generated_on": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "source": "2026事业单位统考省直笔试达线人员名单（逐岗汇总）",
        "total": len(positions),
        "positions": positions,
    }
    (OUT / "syb2026_bgt_daxian.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("syb2026_bgt_daxian.json:", payload["total"])


def _guokao_city(work_loc: str) -> str:
    m = CITY_RE.match(str(work_loc or "").strip())
    return m.group(1) if m else "省直"


def convert_guokao():
    zw = pd.read_excel(SRC / "raw" / "2026guokao_anhui.xlsx", header=0)
    zw.columns = [str(c).strip() for c in zw.columns]
    jm = pd.read_csv(SRC / "guokao_anhui_jinmian.csv", dtype=str)
    stat = jm.groupby(["部门代码", "职位代码"]).agg(
        adv=("准考证号", "count"), line=("最低面试分数", "first")).reset_index()
    stat_map = {(str(r["部门代码"]), str(r["职位代码"])): r for _, r in stat.iterrows()}
    positions = []
    for _, r in zw.iterrows():
        code = str(r["职位代码"]).strip()
        dept = str(r["部门代码"]).strip()
        s = stat_map.get((dept, code))
        zy = _norm_guokao_zy(str(r.get("专业") or ""))
        # “本科或硕士研究生”按“本科及以上”口径（本科可报），避免解析器取高门槛
        xl = str(r.get("学历") or "").strip()
        if xl == "本科或硕士研究生":
            xl = "本科及以上"
        qts = [str(r.get(c) or "").strip() for c in
               ("政治面貌", "服务基层项目工作经历", "是否在面试阶段组织专业能力测试", "面试人员比例")]
        qt = "；".join([q for q in qts if q and q.lower() != "nan"])
        positions.append({
            "code": code,
            "city": _guokao_city(r.get("工作地点")),
            "reg": re.sub(r"^安徽省", "", str(r.get("工作地点") or "").strip()),
            "unit": str(r.get("用人司局") or "").strip(),
            "dept": str(r.get("部门名称") or "").strip(),
            "xz": str(r.get("机构性质") or "").strip(),
            "cc": str(r.get("机构层级") or "").strip(),
            "lb": str(r.get("考试类别") or "").strip(),
            "zw": str(r.get("招考职位") or "").strip(),
            "num": _num(r.get("招考人数")) or 0,
            "zy": zy,
            "xl": xl,
            "xw": str(r.get("学位") or "").strip(),
            "jl": str(r.get("基层工作最低年限") or "").strip(),
            "qt": qt,
            "bz": str(r.get("职位简介") or "").strip(),
            "official_remark": str(r.get("备注") or "").strip(),
            "dh": str(r.get("咨询电话") or "").strip(),
            "sxbl": str(r.get("面试人员比例") or "").strip(),
            "adv": int(s["adv"]) if s is not None else None,
            "line": _num(s["line"]) if s is not None else None,
        })
    payload = {
        "cycle": "2026",
        "generated_on": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "source": "2026国家公务员考试安徽地区职位表 + 进面名单汇总",
        "total": len(positions),
        "coverage": {
            "adv": sum(1 for p in positions if p["adv"] is not None),
            "line": sum(1 for p in positions if p["line"] is not None),
        },
        "recruits": sum(p["num"] for p in positions),
        "positions": sorted(positions, key=lambda p: p["code"]),
    }
    (OUT / "guokao2026.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("guokao2026.json:", payload["total"], "posts /", payload["recruits"], "recruits /", payload["coverage"])


def convert_bishi_full():
    """省考笔试达线名单（全省 23 万人）→ 逐岗 adv/top/avg（权威层，替代分市汇总）。"""
    bm = pd.read_csv(SRC / "shengkao_bishi_mingdan.csv", dtype=str).fillna("")
    bm["score"] = pd.to_numeric(bm["笔试合成成绩"], errors="coerce")
    bm = bm.dropna(subset=["score"])
    bm["职位代码"] = bm["职位代码"].astype(str).str.strip()
    g = bm.groupby("职位代码")["score"]
    agg = g.agg(adv="count", lo="min", top="max", avg="mean").reset_index()
    positions = [{"code": str(r["职位代码"]), "adv": int(r["adv"]), "lo": round(float(r["lo"]), 2),
                  "top": round(float(r["top"]), 2), "avg": round(float(r["avg"]), 2)}
                 for _, r in agg.iterrows()]
    payload = {
        "cycle": "2026",
        "generated_on": time.strftime("%Y-%m-%d"),
        "source": "安徽省2026省考各考区笔试达到合格分数线人员名单（全省汇总，23 万人）",
        "people": int(len(bm)),
        "total": len(positions),
        "positions": sorted(positions, key=lambda p: p["code"]),
    }
    (OUT / "ahsk2026_daxian_full.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ahsk2026_daxian_full.json:", payload["total"], "posts /", payload["people"], "people")


def convert_hire():
    """拟录用名单 × 笔试/面试总成绩 → 逐岗录用者参考成绩（hs=笔试, ht=总成绩）。"""
    nl = pd.read_csv(SRC / "shengkao_niluyong.csv", dtype=str).fillna("")
    ms = pd.read_csv(SRC / "shengkao_mianshi_zongchengji.csv", dtype=str).fillna("")
    zk = {}
    for _, r in ms.iterrows():
        zk[str(r["准考证号"]).strip()] = (r.get("笔试成绩"), r.get("考试总成绩"))
    positions = []
    for _, r in nl.iterrows():
        code = str(r["职位代码"]).strip()
        zkz = str(r["准考证号"]).strip()
        hs = ht = None
        if zkz in zk:
            hs, ht = _num(zk[zkz][0]), _num(zk[zkz][1])
        positions.append({"code": code, "zkz": zkz, "hs": hs, "ht": ht})
    # 同岗多录用者（招2+人）取多条
    payload = {
        "cycle": "2026",
        "generated_on": time.strftime("%Y-%m-%d"),
        "source": "安徽省2026省考拟聘用人员公示名单 × 面试/总成绩公告（逐岗录用者成绩参考）",
        "people": len(positions),
        "total": len({p["code"] for p in positions}),
        "positions": positions,
    }
    (OUT / "ahsk2026_hire.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ahsk2026_hire.json:", payload["total"], "posts /", payload["people"], "people")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    convert_shengkao_official()
    convert_shengzhi_daxian()
    convert_syb_bgt()
    convert_guokao()
    convert_bishi_full()
    convert_hire()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
