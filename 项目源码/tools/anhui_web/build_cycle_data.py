# -*- coding: utf-8 -*-
"""组装 2025/2024 历史周期的构建数据包（data/cycles/{year}/）。

与 2026 数据链路同构（convert_wanyu2_data.py 的年份参数化重构）：
  输入：
    source_data/anhui{y}/shengkao_master.csv          省考职位表（含报名/分数线 join）
    source_data/anhui{y}/shengkao_bishi_mingdan.csv   省考笔试达线名单（逐人）
    source_data/anhui{y}/shengkao_mianshi_zongchengji.csv
    source_data/anhui{y}/shengkao_niluyong.csv
    source_data/anhui{y}/shengkao_kaokaochengji.csv
    tools/anhui_web/data/ahsk{y}_scores.json          xduim fsx 逐岗 top/avg
    source_data/guokao{y}/{y}guokao_anhui.csv         国考安徽职位表（官方 27 列）
    source_data/guokao{y}/guokao_anhui_jinmian.csv    国考进面名单（逐人）
    tools/anhui_web/data/guokao{y}_bmrank.json        xduim 国考报名/过审
    source_data/syb{y}/*.json                          事业编职位库与成绩
  输出（tools/anhui_web/data/cycles/{y}/）：
    all_majors_{y}.json        省考全专业库（all_majors 同构 schema）
    ahsk{y}_official.json      省考逐岗 bm/hg/jf/line + 考区汇总
    ahsk{y}_scores.json        fsx 逐岗 top/avg（转存）
    ahsk{y}_daxian_full.json   达线名单逐岗 adv/lo/top/avg
    ahsk{y}_hire.json          拟录用 × 面试总成绩
    guokao{y}.json             国考职位 + 进面 adv/line + 报名 bm/hg
    huatu_syb_{y}.json         事业编职位库（同构 schema，行内带 cycle 批次）
    syb{y}_daxian_all.json     事业编逐岗 adv/top/avg/line（join 用，带批次）
    cycle.json                 周期元数据（构建标签/统计/缺口）

用法：python build_cycle_data.py --year 2025 [--year 2024]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from pathlib import Path

import pandas as pd

PKG = Path(__file__).resolve().parent
ROOT = PKG.parents[1]
DATA = PKG / "data"
SRC_BASE = ROOT / "source_data"

CITY_RE = re.compile(r"^安徽省(.+?)市")


def _num(s: object):
    s = str(s or "").strip()
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return int(v) if v == int(v) else v


def _clean(s: object) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  -> {path.name}: {payload.get('total', '')}")


# ---------------------------------------------------------------- 省考 ----
def build_shengkao(year: str, src: Path, out: Path) -> dict:
    master = pd.read_csv(src / "shengkao_master.csv", dtype=str).fillna("")

    # 1) all_majors_{y}.json（省考全专业库）
    positions = []
    for _, r in master.iterrows():
        positions.append({
            "region": "", "zhengzhi": "", "xingbie": _clean(r.get("性别")),
            "unit": _clean(r.get("招录机关")), "jigou_xingzhi": _clean(r.get("机构性质")),
            "jigou_cengci": _clean(r.get("机构层级")), "zhiwei_leibie": _clean(r.get("职位类别")),
            "zhiwei": _clean(r.get("职位名称")), "zhiji_cengci": _clean(r.get("职务层次")),
            "code": str(r.get("职位代码", "")).strip(),
            "recruits": _num(r.get("招录人数")) or 0,
            "zhuanye": _clean(r.get("专业")), "xueli": _clean(r.get("学历")),
            "xuewei": _clean(r.get("学位")), "age": _clean(r.get("年龄")),
            "jingli": _clean(r.get("经历要求")), "qita": _clean(r.get("其他资格")),
            "shenlun": _clean(r.get("申论类别")), "zhuanyekemu": _clean(r.get("专业科目")),
            "beizhu": _clean(r.get("备注")), "dianhua": "",
            "city": _clean(r.get("考区")), "source_file": "官方职位表汇编（先锋网原件+镜像核对）",
        })
    codes = [p["code"] for p in positions]
    dup = len(codes) - len(set(codes))
    city_counts: dict[str, int] = {}
    for p in positions:
        city_counts[p["city"]] = city_counts.get(p["city"], 0) + 1
    _dump(out / f"all_majors_{year}.json", {
        "version": f"{year}-cycle-1", "exam": "省考", "cycle": year,
        "generated_on": time.strftime("%Y-%m-%d"),
        "source": f"安徽省{year}年度考试录用公务员官方职位表（省直+16市，报名/分数线经镜像核对）",
        "files": ["shengkao_master.csv（官方职位表汇编）"],
        "city_counts": city_counts, "total": len(positions),
        "duplicates_in_source": dup, "positions": positions,
    })

    # 2) ahsk{y}_official.json（逐岗 bm/hg/jf/line + 考区汇总）
    off_positions = []
    cov = {"bm": 0, "hg": 0, "jf": 0, "line": 0}
    for _, r in master.iterrows():
        bm, hg, jf = _num(r.get("报考人数")), _num(r.get("合格人数")), _num(r.get("缴费人数"))
        line = _num(r.get("笔试分数线"))
        for key, val in (("bm", bm), ("hg", hg), ("jf", jf), ("line", line)):
            if val is not None:
                cov[key] += 1
        off_positions.append({"code": str(r.get("职位代码", "")).strip(), "bm": bm,
                              "hg": hg, "jf": jf, "line": line})
    kaokao = []
    kk_path = src / "shengkao_kaokaochengji.csv"
    if kk_path.is_file():
        kaokao = pd.read_csv(kk_path, dtype=str).fillna("").to_dict("records")
    _dump(out / f"ahsk{year}_official.json", {
        "cycle": year, "generated_on": time.strftime("%Y-%m-%d"),
        "source": f"安徽省{year}年度考试录用公务员（报名/分数线逐岗汇编；合格/缴费官方无逐岗表）",
        "total": len(off_positions), "coverage": cov, "positions": off_positions,
        "kaokao": kaokao,
    })

    # 3) ahsk{y}_scores.json（fsx top/avg，转存）
    fsx = DATA / f"ahsk{year}_scores.json"
    if fsx.is_file():
        shutil.copyfile(fsx, out / f"ahsk{year}_scores.json")
        print(f"  -> ahsk{year}_scores.json: copied")

    # 4) ahsk{y}_daxian_full.json（达线名单逐岗汇总）
    bm_df = pd.read_csv(src / "shengkao_bishi_mingdan.csv", dtype=str).fillna("")
    bm_df["score"] = pd.to_numeric(bm_df["笔试合成成绩"], errors="coerce")
    bm_df = bm_df.dropna(subset=["score"])
    bm_df["职位代码"] = bm_df["职位代码"].astype(str).str.strip()
    g = bm_df.groupby("职位代码")["score"]
    agg = g.agg(adv="count", lo="min", top="max", avg="mean").reset_index()
    _dump(out / f"ahsk{year}_daxian_full.json", {
        "cycle": year, "generated_on": time.strftime("%Y-%m-%d"),
        "source": f"安徽省{year}省考各考区笔试达到合格分数线人员名单（全省汇总）",
        "people": int(len(bm_df)), "total": len(agg),
        "positions": [{"code": str(r["职位代码"]), "adv": int(r["adv"]),
                       "lo": round(float(r["lo"]), 2), "top": round(float(r["top"]), 2),
                       "avg": round(float(r["avg"]), 2)} for _, r in agg.iterrows()],
    })

    # 5) ahsk{y}_hire.json（拟录用 × 面试总成绩）
    nl = pd.read_csv(src / "shengkao_niluyong.csv", dtype=str).fillna("")
    ms = pd.read_csv(src / "shengkao_mianshi_zongchengji.csv", dtype=str).fillna("")
    zk = {}
    for _, r in ms.iterrows():
        zk[str(r["准考证号"]).strip()] = (r.get("笔试成绩"), r.get("考试总成绩"))
    hire_positions = []
    for _, r in nl.iterrows():
        code = str(r["职位代码"]).strip()
        zkz = str(r["准考证号"]).strip()
        hs = ht = None
        if zkz and zkz in zk:
            hs, ht = _num(zk[zkz][0]), _num(zk[zkz][1])
        hire_positions.append({"code": code, "zkz": zkz, "hs": hs, "ht": ht})
    _dump(out / f"ahsk{year}_hire.json", {
        "cycle": year, "generated_on": time.strftime("%Y-%m-%d"),
        "source": f"安徽省{year}省考拟聘用人员公示名单 × 面试/总成绩公告（逐岗录用者成绩参考）",
        "people": len(hire_positions),
        "total": len({p["code"] for p in hire_positions}),
        "positions": hire_positions,
    })
    return {
        "shengkao_posts": len(positions),
        "shengkao_recruits": int(sum(p["recruits"] for p in positions)),
        "shengkao_dup_codes": dup,
        "bm_total": int(sum(p["bm"] or 0 for p in off_positions)),
        "daxian_people": int(len(bm_df)),
        "daxian_posts": int(len(agg)),
        "hire_people": len(hire_positions),
    }


# ---------------------------------------------------------------- 国考 ----
def build_guokao(year: str, src: Path, out: Path) -> dict:
    zw = pd.read_csv(src / f"{year}guokao_anhui.csv", dtype=str).fillna("")
    jm = pd.read_csv(src / "guokao_anhui_jinmian.csv", dtype=str).fillna("")

    jm_map: dict[tuple[str, str], dict] = {}
    for _, r in jm.iterrows():
        key = (str(r["部门代码"]).strip(), str(r["职位代码"]).strip())
        jm_map.setdefault(key, {"adv": 0, "scores": []})
        jm_map[key]["adv"] += 1
        v = _num(r.get("最低面试分数"))
        if v is not None:
            jm_map[key]["scores"].append(v)

    rank = DATA / f"guokao{year}_bmrank.json"
    rank_rows = json.loads(rank.read_text(encoding="utf-8"))["rows"] if rank.is_file() else []
    # xduim 表无职位代码列，同名三元组在不同招考人数下可能重复：先四键精确匹配，再三键兼容
    rank_map4: dict[tuple[str, str, str, object], dict] = {}
    rank_map3: dict[tuple[str, str, str], dict] = {}
    for r in rank_rows:
        k3 = (re.sub(r"\s+", "", str(r.get("dept") or "")),
              re.sub(r"\s+", "", str(r.get("unit") or "")),
              re.sub(r"\s+", "", str(r.get("zw") or "")))
        rank_map3.setdefault(k3, r)
        rank_map4.setdefault((*k3, _num(r.get("num"))), r)

    positions = []
    bm_hit = 0
    for _, r in zw.iterrows():
        code = str(r.get("职位代码", "")).strip()
        dept_code = str(r.get("部门代码", "")).strip()
        wl = str(r.get("工作地点", "")).strip()
        m = CITY_RE.match(wl)
        city = m.group(1) if m else ("省直" if "安徽" in wl else "")
        jm_e = jm_map.get((dept_code, code)) or {}
        line = min(jm_e["scores"]) if jm_e.get("scores") else None
        k = (re.sub(r"\s+", "", str(r.get("部门名称", ""))),
             re.sub(r"\s+", "", str(r.get("用人司局", ""))),
             re.sub(r"\s+", "", str(r.get("招考职位", ""))))
        rk = rank_map4.get((*k, _num(r.get("招考人数")))) or rank_map3.get(k) or {}
        if rk.get("bm") is not None:
            bm_hit += 1
        qt = "；".join(x for x in (str(r.get("政治面貌", "")).strip(),
                                  str(r.get("服务基层项目工作经历", "")).strip(),
                                  str(r.get("是否在面试阶段组织专业能力测试", "")).strip()) if x)
        dh = " / ".join(x for x in (str(r.get("咨询电话1", "")).strip(),
                                    str(r.get("咨询电话2", "")).strip()) if x and x != "0")
        positions.append({
            "code": code, "city": city, "reg": f"{city}市" if city and city != "省直" else "",
            "dept": _clean(r.get("部门名称")), "unit": _clean(r.get("用人司局")),
            "xz": _clean(r.get("机构性质")), "cc": _clean(r.get("机构层级")),
            "lb": _clean(r.get("考试类别")), "zw": _clean(r.get("招考职位")),
            "num": _num(r.get("招考人数")) or 0, "zy": _clean(r.get("专业")),
            "xl": _clean(r.get("学历")), "xw": _clean(r.get("学位")),
            "jl": _clean(r.get("基层工作最低年限")), "qt": qt,
            "bz": _clean(r.get("职位简介")), "dh": dh,
            "sxbl": _clean(r.get("面试人员比例")),
            "adv": jm_e.get("adv") or None, "line": line,
            "bm": rk.get("bm"), "hg": rk.get("hg"),
        })
    coverage = {"adv": sum(1 for p in positions if p["adv"] is not None),
                "line": sum(1 for p in positions if p["line"] is not None),
                "bm": sum(1 for p in positions if p["bm"] is not None)}
    _dump(out / f"guokao{year}.json", {
        "cycle": year, "generated_on": time.strftime("%Y-%m-%d"),
        "source": f"{year}国家公务员考试安徽地区职位表（官方）+ 进面名单汇总 + 报名过审汇编",
        "total": len(positions),
        "recruits": int(sum(p["num"] for p in positions)),
        "coverage": coverage, "bm_source": f"xduim 国考职位报名排名（{year}）",
        "positions": positions,
    })
    return {"guokao_posts": len(positions),
            "guokao_recruits": int(sum(p["num"] for p in positions)),
            "guokao_jinmian_people": int(len(jm))}


# -------------------------------------------------------------- 事业编 ----
_AREA_CITY = {"bozhou": "亳州", "anqing": "安庆", "bengbu": "蚌埠", "chaohu": "合肥",
              "chizhou": "池州", "chuzhou": "滁州", "fuyang": "阜阳", "huaibei": "淮北",
              "huainan": "淮南", "huangshan": "黄山", "luan": "六安", "maanshan": "马鞍山",
              "mingguang": "滁州", "tongling": "铜陵", "wuhu": "芜湖", "xuancheng": "宣城",
              "suzhou": "宿州", "hefei": "合肥"}


def _syb_city(row: dict) -> str:
    city = _clean(row.get("city"))
    if city:
        city = re.sub(r"^安徽", "", city)
        return "省直" if city in ("省直", "直") else city
    area = str(row.get("area") or "").lower()
    for k, v in _AREA_CITY.items():
        if k in area:
            return v
    return ""


def _syb_row(p: dict, cycle_batch: str, note: str) -> dict:
    return {
        "code": str(p.get("code", "")).strip(),
        "city": _syb_city(p), "reg": "",
        "unit": _clean(p.get("unit")), "xz": "事业编", "cc": "",
        "lb": _clean(p.get("post") or p.get("zw") or p.get("lb")),
        "zw": "", "zj": "",
        "num": _num(p.get("num")) or 0,
        "zy": _clean(p.get("zy")), "xl": _clean(p.get("xl")),
        "xw": _clean(p.get("xw")), "age": _clean(p.get("age")),
        "jl": "", "qt": _clean(p.get("qt")), "sl": "", "km": _clean(p.get("km")),
        "bz": _clean(p.get("bz")), "dh": "",
        "bm": _num(p.get("bm")), "hg": _num(p.get("hg")), "jf": _num(p.get("jf")),
        "exam": "事业编", "cycle": cycle_batch, "slug": "",
        "source_note": note,
    }


def build_syb(year: str, src: Path, out: Path) -> dict:
    rows: list[dict] = []
    score_rows: list[dict] = []
    if year == "2025":
        h1 = json.loads((src / "syb2025_positions_h1.json").read_text(encoding="utf-8"))
        h2 = json.loads((src / "syb2025_positions_h2.json").read_text(encoding="utf-8"))
        for p in h1["positions"]:
            rows.append(_syb_row(p, "上半年", "华图2025安徽省事业单位联考职位汇总+单招官方岗位表（上半年）"))
        for p in h2["positions"]:
            rows.append(_syb_row(p, "下半年", "2025下半年联考各单位官方岗位表汇编"))
        for f, batch in (("syb2025_h1_daxian.json", "上半年"), ("syb2025_h2_daxian.json", "下半年")):
            d = json.loads((src / f).read_text(encoding="utf-8"))
            for p in d.get("positions", []):
                score_rows.append({"cycle": batch, **{k: p.get(k) for k in ("code", "adv", "top", "avg", "line")}})
    elif year == "2024":
        hw = json.loads((src / "huatu_syb_2024.json").read_text(encoding="utf-8"))
        # 基线必须在行转换前采集：_syb_row 不透传 fsx/top，转换后取不到（v9.9.3 修复）
        baseline: dict[tuple[str, str], dict] = {}
        for p in hw["positions"]:
            key = (str(p.get("cycle") or "上半年"), str(p.get("code", "")).strip())
            if key not in baseline:
                baseline[key] = {"adv": None, "top": _num(p.get("top")),
                                 "avg": None, "line": _num(p.get("fsx"))}
        for p in hw["positions"]:
            rows.append(_syb_row(p, str(p.get("cycle") or "上半年"), "华图职位检索系统快照（2024联考，含报名/分数线）"))
        # 成绩汇编叠加：代码唯一归属一个批次才叠加，歧义码不 join（防串批次）
        d = json.loads((src / "syb2024_scores.json").read_text(encoding="utf-8"))
        code_batches: dict[str, set[str]] = {}
        for r in rows:
            code_batches.setdefault(r["code"], set()).add(str(r["cycle"]))
        for p in d.get("positions", []):
            code = str(p.get("code", "")).strip()
            batches = code_batches.get(code) or set()
            if len(batches) != 1:
                continue
            score_rows.append({"cycle": next(iter(batches)),
                               **{k: p.get(k) for k in ("code", "adv", "top", "avg", "line")}})
    else:
        raise ValueError(f"unsupported cycle {year}")

    # 逐岗成绩 join（严格按批次+代码；无批次标签的汇编记录不参与，防串批次）
    joined_map: dict[tuple[str, str], dict] = {}
    for s in score_rows:
        if not s.get("cycle"):
            continue
        key = (str(s["cycle"]), str(s["code"]))
        m = joined_map.setdefault(key, {"adv": None, "top": None, "avg": None, "line": None})
        for k in ("adv", "top", "avg"):
            if s.get(k) is not None:
                m[k] = s[k]
        ln = s.get("line")
        if ln is not None and (ln or 0) > 0 and (m["line"] is None or (ln or 0) > (m["line"] or 0)):
            m["line"] = ln
    # 2024：无汇编覆盖的岗位回落到检索系统基线（自带线/最高分）
    if year == "2024":
        for key, b in baseline.items():
            if key not in joined_map:
                joined_map[key] = b
    joined = 0
    for r in rows:
        m = joined_map.get((str(r.get("cycle")), r["code"]))
        if m:
            r["_score"] = m
            if m.get("adv") is not None:
                joined += 1
    # 输出前剥离私有字段
    out_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    _dump(out / f"huatu_syb_{year}.json", {
        "snapshot": time.strftime("%Y-%m-%d"),
        "source": f"安徽事业单位{year}联考职位库（华图+官方岗位表汇编）",
        "caliber_note": "上半年/下半年合并；成绩为各单位公告汇编口径",
        "total": len(out_rows),
        "recruits": int(sum(r["num"] for r in out_rows)),
        "cycles": sorted({str(r["cycle"]) for r in out_rows}),
        "positions": out_rows,
    })
    _dump(out / f"syb{year}_daxian_all.json", {
        "cycle": year, "generated_on": time.strftime("%Y-%m-%d"),
        "source": f"安徽事业单位{year}各单位成绩排名/资格复审公告汇编（逐岗，含批次键）",
        "total": len(rows),
        "positions": [{"cycle": r.get("cycle"), "code": r["code"],
                       "adv": (r.get("_score") or {}).get("adv"),
                       "top": (r.get("_score") or {}).get("top"),
                       "avg": (r.get("_score") or {}).get("avg"),
                       "line": (r.get("_score") or {}).get("line")} for r in rows],
    })
    return {"syb_posts": len(rows), "syb_recruits": int(sum(r["num"] for r in rows)),
            "syb_score_joined": joined}


# ---------------------------------------------------------------- main ----
def build_cycle(year: str) -> None:
    src_a = SRC_BASE / f"anhui{year}"
    src_g = SRC_BASE / f"guokao{year}"
    src_s = SRC_BASE / f"syb{year}"
    out = DATA / "cycles" / year
    out.mkdir(parents=True, exist_ok=True)
    print(f"[cycle {year}] out={out}")
    stats: dict[str, object] = {"cycle": year}
    stats.update(build_shengkao(year, src_a, out))
    stats.update(build_guokao(year, src_g, out))
    stats.update(build_syb(year, src_s, out))
    total_posts = int(stats.get("shengkao_posts", 0) + stats.get("guokao_posts", 0) + stats.get("syb_posts", 0))
    total_recruits = int(stats.get("shengkao_recruits", 0) + stats.get("guokao_recruits", 0) + stats.get("syb_recruits", 0))
    gaps = {
        "2025": ["省考合格/缴费官方无逐岗表（全空）", "事业编逐岗报名人数官方未发布（仅考区汇总）",
                 "拟聘用官方附件仍有阜阳批次未回收（蚌埠/池州/铜陵/宣城已补采）"],
        "2024": ["省考合格/缴费官方无逐岗表（全空）", "拟聘用市级批次约 30+ 批未回收",
                 "事业编下半年官方原始 xlsx 未逐单位回收"],
    }.get(year, [])
    resolved_adjustments = {
        "2025": [
            {
                "kind": "official_archive",
                "title": "2025 省考拟聘用官方附件已补采 11 批次",
                "detail": "已直接归档蚌埠 5 批 283 人、池州 3 批 335 人、铜陵 1 批 76 人、宣城 2 批 326 人，共 1020 人；原始附件经表头、岗位代码、准考证号唯一性和 master 代码复核。未取得阜阳官方附件的批次仍不写入。",
                "evidence": "source_data/anhui2025/raw/nilu_bengbu_b1.xlsx 等 11 个官方附件",
                "severity": "medium",
                "source_urls": [
                    "http://bbxf.bb.ah.cn/ztzl/gsgg/10015291.html",
                    "http://bbxf.bb.ah.cn/ztzl/gsgg/10017871.html",
                    "http://bbxf.bb.ah.cn/ztzl/gsgg/10019271.html",
                    "http://bbxf.bb.ah.cn/ztzl/gsgg/10021031.html",
                    "http://bbxf.bb.ah.cn/ztzl/gsgg/10022221.html",
                    "https://www.czxf.gov.cn/Content/show/746895.html",
                    "https://www.czxf.gov.cn/Content/show/747492.html",
                    "https://www.czxf.gov.cn/Content/show/747752.html",
                    "https://www.tlxfzx.gov.cn/News/Content/a36de47b-16b5-4364-aebf-62345cbf9ef2",
                    "https://jtj.xuancheng.gov.cn/OpennessContent/show/3618944.html",
                    "https://zrzyghj.xuancheng.gov.cn/OpennessContent/show/3546802.html"
                ],
                "source_files": [
                    "source_data/anhui2025/raw/nilu_bengbu_b1.xlsx",
                    "source_data/anhui2025/raw/nilu_bengbu_b2.xlsx",
                    "source_data/anhui2025/raw/nilu_bengbu_b3.xlsx",
                    "source_data/anhui2025/raw/nilu_bengbu_b4.xlsx",
                    "source_data/anhui2025/raw/nilu_bengbu_b5.xlsx",
                    "source_data/anhui2025/raw/nilu_chizhou_b1.xlsx",
                    "source_data/anhui2025/raw/nilu_chizhou_b2.xlsx",
                    "source_data/anhui2025/raw/nilu_chizhou_b3.xlsx",
                    "source_data/anhui2025/raw/nilu_tongling_b7.xls",
                    "source_data/anhui2025/raw/nilu_xuancheng_b2.xlsx",
                    "source_data/anhui2025/raw/nilu_xuancheng_b3.xls"
                ]
            }
        ],
        "2024": [
            {
                "kind": "source_bundle",
                "title": "2024 省考 133 条源包补充行已显式标注",
                "detail": "133 岗/700 人不属于公开主表的无标记官方行，来自镜像/分数线源补充；每行保留“（镜像源合成）”备注，不冒充官方主表，页面继续展示其来源边界。",
                "evidence": "source_data/anhui2024/shengkao_master.csv",
                "severity": "medium",
            }
        ],
    }.get(year, [])
    _dump(out / "cycle.json", {
        "cycle": year, "label": f"{year}年度", "status": "historical",
        "generated_on": time.strftime("%Y-%m-%d"),
        "title_suffix": f"{year}年度",
        "snapshot_note": f"安徽省{year}年度公考历史周期数据包（省考+国考+事业编）",
        "stats": {**stats, "total_posts": total_posts, "total_recruits": total_recruits},
        "gaps": gaps,
        "resolved_adjustments": resolved_adjustments,
    })
    print(f"[cycle {year}] done: {total_posts} posts / {total_recruits} recruits")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", action="append", required=True, help="可重复：--year 2025 --year 2024")
    args = ap.parse_args()
    for y in args.year:
        build_cycle(y)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
