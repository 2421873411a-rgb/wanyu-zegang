# -*- coding: utf-8 -*-
"""v11 资格规则库：从官方职位表结构化字段解析资格标签。

设计原则：
- 纯函数、零 IO、零全局状态；每个标签判定可解释（输出 matched_text）。
- 身份定向（核除级）必须同时满足「人群关键词」与「定向上下文」；
  "同等条件下优先"类优惠句式只产生 warning，不判定为定向。
- 标签命名沿用 v9.2 tag_labels 体系，便于与金标准直接对账。
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- 身份定向

DIRECTED_GROUP_PATTERNS = {
    "four_project": r"服务基层项目|三支一扶|西部计划|大学生村官|特岗教师",
    "veteran": r"退役士兵|退役军人",
    "military_family": r"随军家属|随调家属|军人配偶",
    "targeted": r"烈士子女|残疾人|优秀村(社区)?干部|村(社区)?干部|建档立卡|脱贫户",
}

# 户籍限定：限定报考人群但符合户籍即可报，不属于身份定向核除（v9.2 口径）
HUKOU_RE = re.compile(r"面向[^。；;，,]{0,8}户籍|限[^。；;，,]{0,4}户籍|本(市|县|区)户籍")

DIRECTED_CONTEXT = r"定向|专门面向|面向[^。；;，,]{0,12}(招聘|招录|招考|考录|选拔)|仅限|只限|限"

PRIORITY_CONTEXT = r"同等条件下优先|在同等条件下|优先"

# 定向判定只扫资格条件字段（其他/经历/政治面貌）；备注列是职位简介（描述工作内容），
# 扫它会把“退役军人服务保障”这类职责描述误判为定向；单位名同理。
DIRECTED_FIELDS = ("qita", "jingli", "zhengzhi")

FIELD_PRIORITY = ("qita", "jingli", "beizhu", "zhengzhi", "zhiwei", "unit")


def _context_ok(window: str, keyword: str) -> bool:
    if _priority_only(window):
        return False
    if re.search(DIRECTED_CONTEXT, window):
        return True
    # 官方表“其他”列直接写“服务基层项目人员/退役士兵”即限定身份，无需“定向”字样；
    # 豁免句式（优先/经历类）已在 _priority_only 拦截。
    return True


def _priority_only(window: str) -> bool:
    return bool(re.search(PRIORITY_CONTEXT, window)) and not re.search(
        r"定向|专门面向|仅限|只限", window
    )


def _scan_directed(text: str, field: str) -> tuple[list[dict], list[dict]]:
    hits, hukou = [], []
    if HUKOU_RE.search(text):
        hukou.append({"matched_text": HUKOU_RE.search(text).group(), "source_field": field})
    for category, pattern in DIRECTED_GROUP_PATTERNS.items():
        for m in re.finditer(pattern, text):
            start, end = max(0, m.start() - 16), min(len(text), m.end() + 16)
            window = text[start:end]
            if _context_ok(window, m.group()):
                hits.append(
                    {
                        "category": category,
                        "matched_text": m.group(),
                        "context": window,
                        "source_field": field,
                    }
                )
                break  # 每个类别每字段只记一次
    return hits, hukou


def detect_directed(position: dict) -> dict | None:
    """身份定向判定：仅扫资格条件字段，命中人群关键词且未被优先句式豁免。"""
    per_category: dict[str, dict] = {}
    for field in DIRECTED_FIELDS:
        text = (position.get(field) or "").strip()
        if not text:
            continue
        hits, _ = _scan_directed(text, field)
        for hit in hits:
            per_category.setdefault(hit["category"], hit)
    if not per_category:
        return None
    for category in ("four_project", "veteran", "military_family", "targeted"):
        if category in per_category:
            return per_category[category]
    return None


def detect_hukou(position: dict) -> list[dict]:
    """户籍限定标签（非核除）：任意字段命中户籍句式。"""
    seen, hits = set(), []
    for field in FIELD_PRIORITY:
        text = (position.get(field) or "").strip()
        if not text:
            continue
        _, hukou = _scan_directed(text, field)
        for h in hukou:
            key = h["matched_text"]
            if key not in seen:
                seen.add(key)
                hits.append({**h, "field": field})
    return hits


def collect_priority_warnings(position: dict) -> list[str]:
    """优惠句式警告：含人群词但属于“同等条件下优先”，不构成核除。"""
    warnings = []
    for field in DIRECTED_FIELDS:
        text = (position.get(field) or "").strip()
        if not text:
            continue
        for pattern in DIRECTED_GROUP_PATTERNS.values():
            for m in re.finditer(pattern, text):
                start, end = max(0, m.start() - 16), min(len(text), m.end() + 16)
                if _priority_only(text[start:end]):
                    warnings.append(f"{field}:优先句式[{m.group()}]")
                    break
    return warnings


# ---------------------------------------------------------------- 画像标签

FRESH_RE = re.compile(r"(?<!非)应届(?:高校)?毕业生|202[0-9]届|当年(毕业生|高校毕业)")
FRESH_TRAP_RE = r"高校毕业生(身份)?入伍"
MALE_RE = re.compile(r"限男性|仅限男性|适合男性|男性报考|性别:?男")
MALE_HARD_RE = re.compile(r"限男性|仅限男性|性别[:：]?\s*男")
MALE_SOFT_RE = re.compile(r"适合男性|男性报考")
FEMALE_RE = re.compile(r"限女性|仅限女性|适合女性|女性报考|性别:?女")
FEMALE_HARD_RE = re.compile(r"限女性|仅限女性|性别[:：]?\s*女")
FEMALE_SOFT_RE = re.compile(r"适合女性|女性报考")
SEX_UNLIMITED_RE = re.compile(r"不限|无")
PARTY_RE = re.compile(r"中共党员|共产党员")
LEAGUE_RE = re.compile(r"共青团员")
LEGAL_CERT_RE = re.compile(
    r"法律职业资格|国家统一法律职业资格考试|通过法律职业资格考试|法律职业资格证"
)
MIN_SERVICE_RE = re.compile(r"最低服务(?:年限|期)?[^0-9]{0,6}(\d+)\s*年|服务期[^0-9]{0,4}(\d+)\s*年")
PROF_TEST_RE = re.compile(r"专业测试|专业科目.{0,6}(考试|加试)|加试.{0,6}专业")
NIGHT_SHIFT_RE = re.compile(r"夜班|倒班|轮班|24小时值班|常年值班")
ALLOWANCE_DIFF_RE = re.compile(r"差额拨款|差额补贴|经费自理|自收自支")
HARSH_FIELD_RE = re.compile(r"野外|高空|井下|有毒有害|常年出差|驻点")


def _sex_unlimited(sex_value: str) -> bool:
    return bool(SEX_UNLIMITED_RE.fullmatch((sex_value or "").strip()))


def parse_tags(position: dict) -> dict:
    """画像级标签解析。"""
    qita = (position.get("qita") or "").strip()
    jingli = (position.get("jingli") or "").strip()
    beizhu = (position.get("beizhu") or "").strip()
    official_remark = (position.get("official_remark") or "").strip()
    zhengzhi = (position.get("zhengzhi") or "").strip()
    xingbie = (position.get("xingbie") or "").strip()
    jigou = (position.get("jigou_xingzhi") or "").strip()
    tags: list[str] = []
    notes: list[str] = []

    # 性别：独立列（硬）优先，其次“其他”列硬限制，最后软提示（“适合男性”多在备注）
    gender_source = None
    if xingbie and not _sex_unlimited(xingbie):
        if "男" in xingbie:
            tags.append("gender_male")
            gender_source = "hard"
        elif "女" in xingbie:
            tags.append("gender_female")
            gender_source = "hard"
    gender_text = qita + " " + beizhu + " " + jingli + " " + official_remark
    if "gender_male" not in tags and "gender_female" not in tags:
        female_hard = FEMALE_HARD_RE.search(qita + " " + jingli)
        male_hard = MALE_HARD_RE.search(qita + " " + jingli)
        if female_hard or male_hard:
            tags.append("gender_female" if female_hard else "gender_male")
            gender_source = "hard"
        elif FEMALE_SOFT_RE.search(gender_text):
            tags.append("gender_female")
            gender_source = "soft"
        elif MALE_SOFT_RE.search(gender_text):
            tags.append("gender_male")
            gender_source = "soft"
    if gender_source == "soft":
        notes.append("性别为软提示（适合某性别），非硬性限制")

    # 应届：排除"高校毕业生身份入伍"句式
    fresh_text = qita + " " + jingli + " " + official_remark
    if FRESH_RE.search(fresh_text) and not re.search(FRESH_TRAP_RE, fresh_text):
        tags.append("fresh_only")

    # 党员：独立列或"其他"列
    if PARTY_RE.search(zhengzhi) or PARTY_RE.search(qita) or PARTY_RE.search(official_remark):
        tags.append("party")
        if LEAGUE_RE.search(zhengzhi) and not PARTY_RE.search(zhengzhi):
            notes.append("政治面貌仅共青团员")

    if LEGAL_CERT_RE.search(qita + " " + beizhu + " " + jingli + " " + official_remark):
        tags.append("cert_legal")

    service = MIN_SERVICE_RE.search(qita + " " + beizhu + " " + jingli + " " + official_remark)
    if service:
        tags.append("min_service")
        years = service.group(1) or service.group(2)
        if years:
            notes.append(f"最低服务{years}年")

    if PROF_TEST_RE.search(qita + " " + beizhu + " " + jingli + " " + official_remark):
        tags.append("prof_test")

    if NIGHT_SHIFT_RE.search(beizhu + " " + qita + " " + jingli):
        tags.append("night_shift")

    if ALLOWANCE_DIFF_RE.search(jigou + " " + beizhu + " " + qita):
        tags.append("allowance_diff")

    if HARSH_FIELD_RE.search(beizhu + " " + qita):
        notes.append("艰苦字段提示")

    # 去重保序
    tags = list(dict.fromkeys(tags))
    return {"tags": tags, "notes": notes, "gender_source": gender_source}


# ---------------------------------------------------------------- 学历与专业

XUELI_LADDER = [
    (r"中专|高中", "zhongzhuan", 1),
    (r"(大专|高职|专科)(及以上)?", "dazhuan", 2),
    (r"本科", "benke", 3),
    (r"(硕士研究生|研究生|硕士)", "shuoshi", 4),
    (r"博士", "boshi", 5),
]
XUELI_ONLY_RE = re.compile(r"仅限|只限")


def parse_xueli(xueli: str) -> dict:
    """学历门槛归一化：floor 为最低门槛，only 为"仅限"标记。"""
    text = (xueli or "").strip()
    floor, floor_rank, only = None, 0, False
    for pattern, name, rank in XUELI_LADDER:
        if re.search(pattern, text):
            if rank > floor_rank:
                floor, floor_rank = name, rank
    # "本科及以上"中"本科"为门槛；"仅限本科"同时打 only
    if XUELI_ONLY_RE.search(text):
        only = True
    # "研究生"在"硕士及以上"语境：研究生=硕士门槛
    if re.search(r"研究生", text) and floor_rank < 4:
        floor, floor_rank = "shuoshi", 4
    return {"floor": floor, "only": only, "raw": text}


MAJOR_SPLIT_RE = re.compile(r"[、，,；;/\s]+")
MAJOR_UNLIMITED_RE = re.compile(r"^(不限|专业不限|无专业限制|不限专业|无)$")


def parse_majors(zhuanye: str) -> dict:
    """专业要求拆分：项列表、是否不限、大类项（"类/门类/类专业"结尾）。"""
    text = (zhuanye or "").strip()
    items = [item.strip() for item in MAJOR_SPLIT_RE.split(text) if item.strip()]
    unlimited = any(MAJOR_UNLIMITED_RE.match(item) for item in items) or text in ("", "不限")
    categories = [item for item in items if re.search(r"(类|门类)$", item)]
    return {"items": items, "unlimited": unlimited, "categories": categories, "raw": text}


def parse_eligibility(position: dict) -> dict:
    """规则库总入口：定向判定 + 画像标签 + 学历/专业解析。"""
    directed = detect_directed(position)
    hukou = detect_hukou(position)
    parsed = parse_tags(position)
    result = {
        "directed": directed,
        "hukou_local": hukou,
        "warnings": collect_priority_warnings(position) + parsed["notes"],
    }
    result.update({k: v for k, v in parsed.items() if k != "notes"})
    result["xueli_parsed"] = parse_xueli(position.get("xueli", ""))
    result["majors_parsed"] = parse_majors(position.get("zhuanye", ""))
    return result
