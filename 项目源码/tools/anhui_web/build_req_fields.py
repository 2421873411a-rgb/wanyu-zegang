#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""报考条件结构化预计算脚本（皖域择岗 · 考生资格画像数据资产）

用途
----
读取 网站/data/cycles/<cycle>/jobs.json（结构 {"allMajors": {"rows": [...]}}），
把每个岗位的报考条件（学历 xl / 学位 xw / 年龄 age / 其他条件 qt / 标签 tags /
定向 dir / 户籍 hukou）解析成结构化对象，按 job_id 输出到
网站/data/req-fields-<cycle>.json，供前端"考生资格画像"做检索过滤。

本脚本对 jobs.json 只读，绝不修改它；输出文件是独立衍生资产，
不进入 site-manifest（是否接入校验链由协调者决定）。

用法
----
    python build_req_fields.py --cycle 2026
    python build_req_fields.py --cycle 2026 --input <jobs.json> --output <out.json>

路径解析：默认从脚本所在目录向上查找包含 网站/data/cycles 的交接包根目录；
也可用 --input/--output 显式覆盖。

归一规则摘要
------------
xl_norm（学历）：
  含 研究生/硕士            -> master_above（"仅限硕士研究生"枚举无 master_only，
                               "博士研究生"按规则归入最近桶 master_above，均已在报告中注明）
  含 本科 且含 大专/专科      -> associate_above（"大专及本科"= 专科即可报）
  含 本科 且含"仅限"或裸"本科" -> bachelor_only（仅限本科 / 本科（仅限本科））
  含 本科                    -> bachelor_above（本科及以上 / 大学本科及以上 / 本科（学士）及以上）
  含 大专/专科 且含 及以上     -> associate_above；否则 associate_only
  含 高中/中专               -> high_school_above（枚举外扩展值，低于专科，避免误归 unknown）
  空/纯空白                  -> unknown

xw_norm（学位）：
  含"及以上"或"与最高学历相对应" -> degree_above
  裸 学士/硕士/博士             -> degree_only
  空/纯空白（含 &nbsp;）        -> none_required
  （依据官方职位表惯例：学位列为空即"不限学位"。此为假设，
    若上游口径变化应改为 unknown 并人工复核。）

age：`(\d{2})周岁以下` 取该数字；`放宽至(\d{2})周岁` 取放宽值并置 age_complex=true；
  空文本 age_max=null；有文本但解析失败 age_max=null 且 age_complex=true（转人工）。

gender/fresh_only/party_only/cert_legal：优先 tags 结构化标签（兼容数组/对象两种形态），
  文本兜底在 qt 上正则命中"限男性|限女性|应届|中共党员|法律职业资格"。
  特例：qt 为"中共党员或共青团员"（团员亦可报）时 party_only=false，共 19 行。

dir_type：four_project/basic_service_project -> four_project（服务基层项目即四项目口径）；
  veteran -> veteran；targeted/military_family/user_flagged/空 -> any（定向细节见 qt 原文）。

confidence：high = 条件字段全部来自结构化标签（或本就无限项）；
  medium = 标签与文本兜底混用；low = 关键字段仅靠文本正则、或 age 复合表述、
  或 xl 有原文但解析失败（需人工核对）。

数据边界声明
------------
解析结果仅为检索辅助，报考资格以官方公告为准。

统计摘要打印到 stdout：总行数、各归一值分布、age 解析成功率、
各标签命中数（区分标签源/文本源）、confidence 分布、耗时。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# 正则与常量
# ---------------------------------------------------------------------------

RE_AGE_BELOW = re.compile(r"(\d{2})周岁以下")
RE_AGE_RELAX = re.compile(r"放宽至(\d{2})周岁")
RE_GENDER_TEXT = re.compile(r"限(男|女)性")
RE_PARTY_LEAGUE = "中共党员或共青团"  # 团员亦可报，不能算 party_only

TEXT_FALLBACKS = ("限男性", "限女性", "应届", "中共党员", "法律职业资格")

XL_UNKNOWN = "unknown"
XW_NONE = "none_required"

# dir 字段值 -> dir_type 映射；未列出的（targeted/military_family/user_flagged）归 any
DIR_TYPE_MAP = {
    "four_project": "four_project",
    "basic_service_project": "four_project",  # 服务基层项目人员 = 四项目口径
    "veteran": "veteran",
}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def clean(text) -> str:
    """清理字段文本：None/纯空白/&nbsp;/全角空格 -> 归一后返回 stripped 字符串。"""
    if text is None:
        return ""
    s = str(text).replace("\u00a0", " ").replace("&nbsp;", " ")
    s = s.replace("\u3000", " ").strip()
    return s


def tag_keys(tags) -> set:
    """提取结构化标签键集合。兼容两种形态：
    - 数组（当前数据形态）：["party", "fresh_only", ...]，元素为字符串；
      元素若为 dict，则取其真值键兜底。
    - 对象：{"party": true, ...}，取真值键。
    """
    keys = set()
    if isinstance(tags, dict):
        for k, v in tags.items():
            if v:
                keys.add(str(k))
    elif isinstance(tags, (list, tuple)):
        for item in tags:
            if isinstance(item, str):
                keys.add(item)
            elif isinstance(item, dict):
                for k, v in item.items():
                    if v:
                        keys.add(str(k))
    return keys


def find_repo_root() -> Path:
    """从脚本目录向上查找包含 网站/data/cycles 的交接包根目录。"""
    cur = Path(__file__).resolve().parent
    for cand in (cur, *cur.parents):
        if (cand / "网站" / "data" / "cycles").is_dir():
            return cand
    raise SystemExit(
        "[build_req_fields] 未找到交接包根目录（需存在 网站/data/cycles）。"
        "请用 --input/--output 显式指定路径。"
    )


# ---------------------------------------------------------------------------
# 各字段归一
# ---------------------------------------------------------------------------

def norm_xl(raw: str) -> str:
    s = clean(raw)
    if not s:
        return XL_UNKNOWN
    if "研究生" in s or "硕士" in s:
        # 覆盖：研究生 / 研究生及以上 / 硕士研究生及以上 / 仅限(硕士)研究生 / 博士研究生
        return "master_above"
    if "本科" in s:
        if "大专" in s or "专科" in s:
            return "associate_above"  # 大专及本科：专科即可报
        if "仅限" in s or s == "本科":
            return "bachelor_only"  # 仅限本科 / 本科（仅限本科）/ 裸"本科"
        return "bachelor_above"  # 本科及以上 / 大学本科及以上 / 本科（学士）及以上
    if "大专" in s or "专科" in s:
        return "associate_only" if "及以上" not in s else "associate_above"
    if "高中" in s or "中专" in s or "中技" in s:
        return "high_school_above"  # 枚举外扩展值：低于专科，避免误归 unknown
    return XL_UNKNOWN


def norm_xw(raw: str) -> str:
    s = clean(raw)
    if not s:
        return XW_NONE  # 官方职位表惯例：学位列留空 = 不限学位（假设，见文件头注释）
    if "不限" in s:
        return XW_NONE
    if "及以上" in s or "与最高学历相对应" in s:
        return "degree_above"  # 学士及以上 / 硕士及以上 / 与最高学历相对应的学位
    if "学士" in s or "硕士" in s or "博士" in s:
        return "degree_only"  # 裸 学士/硕士/博士
    return XL_UNKNOWN


def parse_age(raw: str):
    """返回 (age_max:int|None, age_complex:bool, parsed_ok:bool)。"""
    s = clean(raw)
    if not s:
        return None, False, True  # 无 age 字段 -> age_max=null，不算解析失败
    relax = RE_AGE_RELAX.search(s)
    if relax:  # "放宽至XX周岁"：取放宽值，标记复合表述
        return int(relax.group(1)), True, True
    below = RE_AGE_BELOW.findall(s)
    if below:
        complex_ = len(below) > 1 or "放宽" in s
        return int(below[0]), complex_, True
    # 有文本但不符合任何规则：转人工
    return None, True, False


def resolve_gender(tags: set, qt: str):
    """返回 (gender, source)；source in {'tag','text','none'}。"""
    male, female = "gender_male" in tags, "gender_female" in tags
    if male and not female:
        return "male", "tag"
    if female and not male:
        return "female", "tag"
    if male and female:  # 数据中未出现（0 行）；出现则视为不限并告警于统计
        return "any", "tag"
    m = RE_GENDER_TEXT.search(qt)
    if m:
        return ("male" if m.group(1) == "男" else "female"), "text"
    return "any", "none"


def resolve_flag(tag_name: str, text_pattern: str, tags: set, qt: str):
    """通用布尔条件：标签优先，qt 文本兜底。返回 (value, source)。"""
    if tag_name in tags:
        return True, "tag"
    if text_pattern and text_pattern in qt:
        return True, "text"
    return False, "none"


def build_record(row: dict) -> tuple[dict, dict]:
    """把一行岗位数据解析成结构化条件对象。
    返回 (record, debug)，debug 记录各字段来源用于统计与 confidence 判定。
    """
    tags = tag_keys(row.get("tags"))
    qt = clean(row.get("qt"))

    xl_raw = clean(row.get("xl"))
    xw_raw = clean(row.get("xw"))
    age_raw = clean(row.get("age"))
    xl_norm = norm_xl(xl_raw)
    xw_norm = norm_xw(xw_raw)
    age_max, age_complex, age_ok = parse_age(age_raw)

    gender, gender_src = resolve_gender(tags, qt)
    fresh_only, fresh_src = resolve_flag("fresh_only", "应届", tags, qt)
    party_only, party_src = resolve_flag("party", "中共党员", tags, qt)
    if party_only and RE_PARTY_LEAGUE in qt:
        party_only = False  # "中共党员或共青团员"：团员亦可报（19 行特例）
        party_src = "text"
    cert_legal, cert_src = resolve_flag("cert_legal", "法律职业资格", tags, qt)

    dir_val = clean(row.get("dir"))
    dir_type = DIR_TYPE_MAP.get(dir_val, "any")
    hukou_limited = bool(row.get("hukou"))

    record = {
        "xl_norm": xl_norm,
        "xw_norm": xw_norm,
        "age_max": age_max,
        "age_raw": age_raw,
        "age_complex": age_complex,
        "gender": gender,
        "fresh_only": fresh_only,
        "party_only": party_only,
        "cert_legal": cert_legal,
        "dir_type": dir_type,
        "hukou_limited": hukou_limited,
        "confidence": "high",
    }

    text_hits = sum(1 for s in (gender_src, fresh_src, party_src, cert_src) if s == "text")
    tag_hits = sum(1 for s in (gender_src, fresh_src, party_src, cert_src) if s == "tag")

    if text_hits and tag_hits:
        confidence = "medium"
    elif text_hits:
        confidence = "low"
    else:
        confidence = "high"
    # 强制降级：age 复合表述需人工核对；xl 有原文却解析失败
    if age_complex or (xl_raw and xl_norm == XL_UNKNOWN) or not age_ok:
        confidence = "low"

    record["confidence"] = confidence
    debug = {
        "gender_src": gender_src,
        "fresh_src": fresh_src,
        "party_src": party_src,
        "cert_src": cert_src,
        "age_ok": age_ok,
        "xl_raw_empty": not xl_raw,
    }
    return record, debug


def row_key(row: dict, idx: int) -> str:
    """优先 job_id，兜底 row_id / code，最后用行号保证唯一。"""
    for field in ("job_id", "row_id", "code"):
        v = clean(row.get(field))
        if v:
            return v
    return f"row-{idx + 1:06d}"


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="报考条件结构化预计算（皖域择岗）")
    parser.add_argument("--cycle", default="2026", help="招聘年度，默认 2026")
    parser.add_argument("--input", default=None, help="覆盖输入 jobs.json 路径")
    parser.add_argument("--output", default=None, help="覆盖输出 JSON 路径")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    t0 = time.time()
    root = find_repo_root()
    in_path = Path(args.input) if args.input else root / "网站" / "data" / "cycles" / args.cycle / "jobs.json"
    out_path = Path(args.output) if args.output else root / "网站" / "data" / f"req-fields-{args.cycle}.json"

    if not in_path.is_file():
        raise SystemExit(f"[build_req_fields] 输入文件不存在：{in_path}")

    # 只读打开 jobs.json，绝不写回
    with open(in_path, encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("allMajors", {}).get("rows", [])
    if not rows:
        raise SystemExit(f"[build_req_fields] {in_path} 中没有 allMajors.rows 数据")

    records = {}
    key_dup = Counter()
    xl_dist, xw_dist, dir_dist, conf_dist = Counter(), Counter(), Counter(), Counter()
    age_stats = {"non_empty": 0, "parsed": 0, "complex": 0, "null": 0}
    tag_stats = {
        "gender_tag": 0, "gender_text": 0,
        "fresh_tag": 0, "fresh_text": 0,
        "party_tag": 0, "party_text": 0,
        "cert_tag": 0, "cert_text": 0,
        "hukou": 0,
    }

    for idx, row in enumerate(rows):
        key = row_key(row, idx)
        key_dup[key] += 1
        rec, dbg = build_record(row)
        if key in records:
            print(f"[warn] 重复键 {key}，后行覆盖前行", file=sys.stderr)
        records[key] = rec

        xl_dist[rec["xl_norm"]] += 1
        xw_dist[rec["xw_norm"]] += 1
        dir_dist[rec["dir_type"]] += 1
        conf_dist[rec["confidence"]] += 1
        if rec["age_raw"]:
            age_stats["non_empty"] += 1
        if rec["age_max"] is not None:
            age_stats["parsed"] += 1
        else:
            age_stats["null"] += 1
        if rec["age_complex"]:
            age_stats["complex"] += 1
        if rec["hukou_limited"]:
            tag_stats["hukou"] += 1
        for name, src_key in (("gender", "gender"), ("fresh", "fresh"),
                              ("party", "party"), ("cert", "cert")):
            src = dbg[f"{src_key}_src"]
            if src in ("tag", "text"):
                tag_stats[f"{name}_{src}"] += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
        f.write("\n")

    # ---------------- 统计摘要 ----------------
    total = len(rows)
    uniq = len(key_dup)
    rate_all = age_stats["parsed"] / total * 100 if total else 0.0
    rate_ne = (age_stats["parsed"] / age_stats["non_empty"] * 100
               if age_stats["non_empty"] else 0.0)

    def dist_str(counter: Counter) -> str:
        return ", ".join(f"{k}={v}" for k, v in counter.most_common())

    print("=" * 64)
    print(f"报考条件结构化预计算完成  cycle={args.cycle}")
    print(f"输入: {in_path}")
    print(f"输出: {out_path}  ({out_path.stat().st_size / 1024:.1f} KB)")
    print("=" * 64)
    print(f"总行数: {total}   唯一键数: {uniq}   键冲突: {sum(1 for v in key_dup.values() if v > 1)}")
    print(f"xl_norm 分布: {dist_str(xl_dist)}")
    print(f"xw_norm 分布: {dist_str(xw_dist)}")
    print(f"dir_type 分布: {dist_str(dir_dist)}")
    print(f"age 解析: 非空 {age_stats['non_empty']} / {total}，"
          f"成功解析 {age_stats['parsed']}（非空成功率 {rate_ne:.1f}%，全表成功率 {rate_all:.1f}%），"
          f"age_max=null {age_stats['null']}，复合表述 {age_stats['complex']}")
    print(f"标签命中: gender(标签 {tag_stats['gender_tag']} / 文本 {tag_stats['gender_text']}), "
          f"fresh(标签 {tag_stats['fresh_tag']} / 文本 {tag_stats['fresh_text']}), "
          f"party(标签 {tag_stats['party_tag']} / 文本 {tag_stats['party_text']}), "
          f"cert(标签 {tag_stats['cert_tag']} / 文本 {tag_stats['cert_text']}), "
          f"hukou={tag_stats['hukou']}")
    print(f"confidence 分布: {dist_str(conf_dist)}")
    print(f"耗时: {time.time() - t0:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
