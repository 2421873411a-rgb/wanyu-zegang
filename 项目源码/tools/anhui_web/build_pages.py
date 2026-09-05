from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.oxml.ns import qn

try:
    from .data_quality import annotate_position_row, competition_observations
except ImportError:  # pragma: no cover - supports direct script execution
    from data_quality import annotate_position_row, competition_observations

try:
    from .city_norm import normalize_source_city
except ImportError:  # pragma: no cover - supports direct script execution
    from city_norm import normalize_source_city


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PACKAGED_JOBS_DOCX = ROOT / "source_docs" / "安徽十六市2026软件工程可报岗位汇总_最终定稿版.docx"
PACKAGED_SALARY_DOCX = ROOT / "source_docs" / "安徽全省16市本科普通岗全包分析_完善版(1).docx"


def _resolve_source_docx(env_key: str, packaged: Path) -> Path:
    """源 Word 解析顺序：环境变量覆盖 → 包内 source_docs/；不回退到个人机器路径。"""
    import os

    override = os.environ.get(env_key, "").strip()
    return Path(override) if override else packaged


JOBS_DOCX = _resolve_source_docx("WANYU_JOBS_DOCX", PACKAGED_JOBS_DOCX)
SALARY_DOCX = _resolve_source_docx("WANYU_SALARY_DOCX", PACKAGED_SALARY_DOCX)
OUTPUT_DIR = ROOT / "deliverables"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
ANHUI_GEOJSON = Path(__file__).resolve().parent / "data" / "anhui_340000_full.json"
JOB_EXCLUSIONS_JSON = Path(__file__).resolve().parent / "data" / "job_eligibility_exclusions.json"
ALL_MAJORS_JSON = Path(__file__).resolve().parent / "data" / "all_majors_2026.json"
CHUZHOU_SYB_HTML = Path(__file__).resolve().parent / "data" / "chuzhou_shiyeban_2026.html"
HUATU_SYB_JSON = Path(__file__).resolve().parent / "data" / "huatu_syb_2026.json"
MANIFEST_JSON = Path(__file__).resolve().parent / "data" / "manifest.json"
AHSK_SCORES_JSON = Path(__file__).resolve().parent / "data" / "ahsk2026_scores.json"
AHSK_OFFICIAL_JSON = Path(__file__).resolve().parent / "data" / "ahsk2026_official.json"
AHSK_DAXIAN_SZ_JSON = Path(__file__).resolve().parent / "data" / "ahsk2026_daxian_szzk.json"
AHSK_DAXIAN_ALL_JSON = Path(__file__).resolve().parent / "data" / "ahsk2026_daxian_all.json"
AHSK_DAXIAN_FULL_JSON = Path(__file__).resolve().parent / "data" / "ahsk2026_daxian_full.json"
AHSK_HIRE_JSON = Path(__file__).resolve().parent / "data" / "ahsk2026_hire.json"
SCORE_LISTS_JSON = Path(__file__).resolve().parent / "data" / "score_lists.json"
THREE_YEAR_AUDIT_JSON = Path(__file__).resolve().parent / "data" / "three_year_audit.json"
SYB_BGT_JSON = Path(__file__).resolve().parent / "data" / "syb2026_bgt_daxian.json"
SYB_FUGAO_JSON = Path(__file__).resolve().parent / "data" / "syb2026_daxian_all.json"
GUOKAO_JSON = Path(__file__).resolve().parent / "data" / "guokao2026.json"


def _cycle_label() -> str:
    """数据周期标签（manifest/cycle.json 驱动），用于前端口径说明；缺失时返回空串。"""
    try:
        manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
        if "label" in manifest and "snapshot_date" not in manifest:  # 历史周期 cycle.json
            return f'{manifest.get("label", "")} · 历史周期数据包'
        return f'{manifest.get("cycle", "")} · 快照 {manifest.get("snapshot_date", "")}'
    except (OSError, ValueError):
        return ""


CYCLE = "2026"


def _apply_cycle_paths(cycle: str) -> None:
    """--cycle 历史周期：数据文件全局指向 data/cycles/{cycle}/ 同构包。

    2026 走根目录原文件（零回归）；历史周期同时屏蔽 2026 专属数据源
    （2026 达线/事业编省直/滁州官方表），防止同码跨年污染。
    """
    global CYCLE, ALL_MAJORS_JSON, AHSK_SCORES_JSON, AHSK_OFFICIAL_JSON
    global AHSK_DAXIAN_ALL_JSON, AHSK_DAXIAN_SZ_JSON, AHSK_DAXIAN_FULL_JSON
    global AHSK_HIRE_JSON, SYB_BGT_JSON, SYB_FUGAO_JSON, GUOKAO_JSON, HUATU_SYB_JSON
    global MANIFEST_JSON, SCORE_LISTS_JSON, _ALL_CACHE
    CYCLE = cycle
    _ALL_CACHE = None
    if cycle == "2026":
        return
    d = Path(__file__).resolve().parent / "data" / "cycles" / cycle
    ALL_MAJORS_JSON = d / f"all_majors_{cycle}.json"
    AHSK_SCORES_JSON = d / f"ahsk{cycle}_scores.json"
    AHSK_OFFICIAL_JSON = d / f"ahsk{cycle}_official.json"
    AHSK_DAXIAN_ALL_JSON = d / "absent_daxian_all.json"      # 屏蔽 2026 逐市达线
    AHSK_DAXIAN_SZ_JSON = d / "absent_daxian_szzk.json"     # 屏蔽 2026 省直达线
    AHSK_DAXIAN_FULL_JSON = d / f"ahsk{cycle}_daxian_full.json"
    AHSK_HIRE_JSON = d / f"ahsk{cycle}_hire.json"
    SYB_BGT_JSON = d / "absent_syb_bgt.json"                # 屏蔽 2026 事业编省直达线
    SYB_FUGAO_JSON = d / f"syb{cycle}_daxian_all.json"
    HUATU_SYB_JSON = d / f"huatu_syb_{cycle}.json"
    GUOKAO_JSON = d / f"guokao{cycle}.json"
    MANIFEST_JSON = d / "cycle.json"
    SCORE_LISTS_JSON = d / "score_lists.json"               # 历史周期暂无逐人成绩单名单

EXCLUSION_CATEGORY_LABELS = {
    "basic_service_project": "服务基层项目定向",
    "veteran": "退役士兵定向",
    "military_family": "随军家属定向",
    "other_directed": "其他定向",
    "user_flagged": "用户标记·待复核",
}


def load_job_exclusions(path: Path = JOB_EXCLUSIONS_JSON) -> dict[str, dict[str, str]]:
    """Load identity-directed job exclusions verified against the recruitment notices.

    Codes listed here are定向招聘（服务基层项目人员 / 退役士兵 / 随军家属 等）岗位，
    报考人身份不符。构建时从可报口径剔除，但原始行仍渲染在档案表中并明确标记。
    """
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    exclusions = payload.get("exclusions", {})
    labels = dict(EXCLUSION_CATEGORY_LABELS)
    labels.update(payload.get("category_labels", {}))
    resolved: dict[str, dict[str, str]] = {}
    for code, entry in exclusions.items():
        category = str(entry.get("category", "other_directed"))
        resolved[str(code).strip()] = {
            "category": category,
            "category_label": str(entry.get("category_label") or labels.get(category, "定向岗位")),
            "reason": str(entry.get("source_remark") or entry.get("note") or "").strip(),
            "source": str(entry.get("source_url") or "").strip(),
            "verified_by": str(entry.get("verified_by") or "").strip(),
        }
    return resolved


JOB_EXCLUSIONS = load_job_exclusions()
POSITION_ELIGIBILITY_PATH = Path(__file__).resolve().parent / "data" / "position_eligibility.json"


def load_position_eligibility(path: Path = POSITION_ELIGIBILITY_PATH) -> dict[str, dict[str, object]]:
    """Load per-code eligibility facts (remark/other/tags) verified against official tables."""
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(code): entry for code, entry in payload.get("positions", {}).items()}


POSITION_ELIGIBILITY = load_position_eligibility()
ELIGIBILITY_TAG_LABELS = {
    "four_project": "四项目定向",
    "veteran": "退役士兵定向",
    "military_family": "随军家属定向",
    "targeted": "其他定向",
    "fresh_only": "仅应届",
    "gender_male": "限男性",
    "gender_female": "限女性",
    "party": "中共党员",
    "cert_legal": "法律职业资格",
    "min_service": "最低服务期",
    "allowance_diff": "差额补贴",
    "night_shift": "夜班/值班",
    "prof_test": "专业测试",
}
JOBS_HTML_NAME = "安徽十六市2026软件工程可报岗位.html"
SALARY_HTML_NAME = "安徽全省16市本科普通岗全包分析.html"
MASTER_HTML_NAME = "皖域择岗总览.html"
BUILD_VERSION = "v12.1"
DATA_SNAPSHOT = "2026-08-31"

# 岗位性质标签：按职位名正则归类（构建期一次打标，检索筛选 / 详情浮层共用）。
# 顺序即展示优先级；一条岗位可命中多类，展示时最多取 3 类。
JOB_NATURE_RULES: list[tuple[str, str, str]] = [
    ("grassroots", "乡镇街道", r"乡镇|街道"),
    ("law", "执法警务", r"执法|稽查|公安|监狱|戒毒|警察|司法所|派出所"),
    ("office", "文秘综合", r"办公室|文秘|综合|秘书|文字|宣传"),
    ("finance", "财会审计", r"会计|财务|财会|审计|出纳"),
    ("tech", "计算机信息", r"计算机|信息|大数据|网络|软件|数据"),
    ("legal", "法律法务", r"法学|法律|法务"),
    ("engineer", "工程规划", r"工程|规划|建设|建筑|市政|水利|交通"),
    ("medical", "医疗卫生", r"医[院师疗护]|卫生|疾控|康复|药"),
    ("education", "教育文化", r"教育|教师|师范|文化|旅游|广电|体育|文物"),
    ("econ", "经济金融", r"金融|经济|统计|证券|投资|招商"),
]


def _job_natures(unit_position: str) -> list[dict[str, str]]:
    text = str(unit_position or "")
    natures: list[dict[str, str]] = []
    for key, label, pattern in JOB_NATURE_RULES:
        if re.search(pattern, text):
            natures.append({"key": key, "label": label})
    return natures[:3]


GLOSSARY_TERMS = [
    ["有效笔试/达线", "来源中明确记录的参考、达线或进面人数。它与报名人数属于不同分母，页面只在同一分母口径内计算竞争比，不把缺失值当成 0。"],
    ["最低入围/线", "进入下一环节（资格复审/面试）的最低笔试成绩；事业单位联考满分为 300，省考合成成绩（行测+申论÷2）满分为 100。"],
    ["核减", "报名或缴费达不到开考比例被取消/削减的招录计划；职位库中“核减后人数”为最终招录数。"],
    ["递补", "前排人员放弃资格后，按成绩依次补录。"],
    ["差额补贴", "经费来源为差额拨款的事业单位岗位，待遇稳定性弱于全额拨款。"],
    ["专业测试", "部分岗位在笔试外另设专业测试（如六安“专业测试2”），影响总成绩构成。"],
    ["四项目", "服务基层项目人员：大学生村官、“三支一扶”、西部计划志愿者、特岗教师。"],
    ["员额制", "不属于传统事业编的用人方式（如合肥新站高新区岗位），本档案已排除。"],
    ["服务基层项目", "即“四项目”：大学生村官、三支一扶、西部计划志愿者、特岗教师；定向岗仅限该身份报考。"],
    ["最低服务年限", "部分岗位要求在用人单位最低服务 5 年（含试用期），期间一般不得借调、遴选或在职报考其他岗位。"],
    ["资格复审", "笔试入围后核验毕业证、学位证、身份与资格条件原件；专业口径以学位证书与招考公告目录为准。"],
    ["竞争比（1:N）", "招录人数 ÷ 有效笔试人数（缺失时回退报名人数），展示为 1:N；N 越小竞争越缓。"],
]
PRODUCT_PAGE_NAMES = {
    "jobs_dashboard": "岗位观测台.html",
    "jobs_ranking": "岗位排名对比.html",
    "jobs_search": "岗位检索.html",
    "jobs_archive": "岗位档案.html",
    "salary_dashboard": "待遇观测台.html",
    "salary_ranking": "待遇排名.html",
    "salary_archive": "待遇档案.html",
}
LEGACY_PAGE_NAMES = {"jobs": JOBS_HTML_NAME, "salary": SALARY_HTML_NAME}

CITY_POSITIONS = {
    "亳州": (31, 14),
    "淮北": (55, 10),
    "宿州": (67, 16),
    "阜阳": (24, 28),
    "蚌埠": (58, 31),
    "淮南": (43, 34),
    "滁州": (73, 38),
    "六安": (29, 46),
    "合肥": (49, 48),
    "马鞍山": (72, 55),
    "芜湖": (68, 61),
    "铜陵": (55, 65),
    "安庆": (35, 68),
    "池州": (48, 73),
    "宣城": (69, 73),
    "黄山": (54, 88),
}

CITY_LABEL_LAYOUT = {
    "亳州": (-4.8, 0.8, "end"),
    "淮北": (0, -6.4, "middle"),
    "宿州": (4.8, 0.8, "start"),
    "阜阳": (-4.8, 0.8, "end"),
    "蚌埠": (4.8, 0.8, "start"),
    "淮南": (-4.8, 0.8, "end"),
    "滁州": (4.8, 0.8, "start"),
    "六安": (-4.8, 0.8, "end"),
    "合肥": (4.8, 0.8, "start"),
    "马鞍山": (4.8, -1.3, "start"),
    "芜湖": (4.8, 2.2, "start"),
    "铜陵": (-4.8, -1.4, "end"),
    "安庆": (-4.8, 0.8, "end"),
    "池州": (-4.8, 2.2, "end"),
    "宣城": (4.8, 0.8, "start"),
    "黄山": (4.8, 0.8, "start"),
}


@dataclass
class CellModel:
    text: str
    colspan: int = 1
    rowspan: int = 1
    header: bool = False


@dataclass
class TableModel:
    index: int
    rows: list[list[CellModel]]


@dataclass
class Block:
    kind: str
    text: str = ""
    style: str = ""
    table: TableModel | None = None


@dataclass
class DocumentModel:
    blocks: list[Block]
    tables: list[TableModel]
    paragraph_node_count: int
    all_text: str


def _element_text(element) -> str:
    """Read visible Word text in document order, including hyperlinks."""
    parts: list[str] = []
    for node in element.iter():
        if node.tag == qn("w:t"):
            parts.append(node.text or "")
        elif node.tag == qn("w:tab"):
            parts.append("\t")
        elif node.tag in {qn("w:br"), qn("w:cr")}:
            parts.append("\n")
    return "".join(parts)


def _paragraph_style(element, style_names: dict[str, str]) -> str:
    p_pr = element.find(qn("w:pPr"))
    if p_pr is None:
        return "Normal"
    p_style = p_pr.find(qn("w:pStyle"))
    if p_style is None:
        return "Normal"
    style_id = p_style.get(qn("w:val"), "")
    return style_names.get(style_id, style_id or "Normal")


def _parse_table(table_element, index: int) -> TableModel:
    rows: list[list[CellModel]] = []
    active_vertical: dict[int, CellModel] = {}

    for row_index, tr in enumerate(table_element.findall(qn("w:tr"))):
        rendered_row: list[CellModel] = []
        grid_column = 0
        continued_columns: set[int] = set()

        for tc in tr.findall(qn("w:tc")):
            tc_pr = tc.find(qn("w:tcPr"))
            grid_span = tc_pr.find(qn("w:gridSpan")) if tc_pr is not None else None
            colspan = int(grid_span.get(qn("w:val"), "1")) if grid_span is not None else 1
            v_merge = tc_pr.find(qn("w:vMerge")) if tc_pr is not None else None
            merge_value = v_merge.get(qn("w:val")) if v_merge is not None else None

            if v_merge is not None and merge_value != "restart":
                origin = active_vertical.get(grid_column)
                if origin is not None:
                    origin.rowspan += 1
                    continued_columns.update(range(grid_column, grid_column + colspan))
                else:
                    rendered_row.append(
                        CellModel(
                            text=_element_text(tc),
                            colspan=colspan,
                            header=row_index == 0,
                        )
                    )
            else:
                cell = CellModel(
                    text=_element_text(tc),
                    colspan=colspan,
                    header=row_index == 0,
                )
                rendered_row.append(cell)
                for column in range(grid_column, grid_column + colspan):
                    if v_merge is not None and merge_value == "restart":
                        active_vertical[column] = cell
                    else:
                        active_vertical.pop(column, None)
            grid_column += colspan

        for column in list(active_vertical):
            if column < grid_column and column not in continued_columns:
                owner = active_vertical[column]
                if owner not in rendered_row:
                    active_vertical.pop(column, None)
        rows.append(rendered_row)

    return TableModel(index=index, rows=rows)


def parse_docx(path: Path) -> DocumentModel:
    document = Document(path)
    style_names = {style.style_id: style.name for style in document.styles}
    blocks: list[Block] = []
    tables: list[TableModel] = []
    paragraph_node_count = 0

    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph_node_count += 1
            blocks.append(
                Block(
                    kind="paragraph",
                    text=_element_text(child),
                    style=_paragraph_style(child, style_names),
                )
            )
        elif child.tag == qn("w:tbl"):
            table = _parse_table(child, len(tables))
            tables.append(table)
            blocks.append(Block(kind="table", table=table))

    text_parts: list[str] = []
    for block in blocks:
        if block.kind == "paragraph":
            text_parts.append(block.text)
        elif block.table:
            text_parts.extend(cell.text for row in block.table.rows for cell in row)

    return DocumentModel(
        blocks=blocks,
        tables=tables,
        paragraph_node_count=paragraph_node_count,
        all_text="\n".join(text_parts),
    )


def _render_text(text: str) -> str:
    return html.escape(text, quote=True).replace("\n", "<br>").replace("\t", "&emsp;")


def csv_quote(value: object) -> str:
    """Return a CSV cell that is safe to open in spreadsheet software."""
    text = "" if value is None else str(value)
    if text[:1] in "=+-@":
        text = "'" + text
    return '"' + text.replace('"', '""') + '"'


def _class_token(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-")


def _render_table(
    table: TableModel,
    extra_class: str = "",
    row_attributes: dict[int, dict[str, str]] | None = None,
    action_column: bool = False,
    excluded_codes: dict[str, dict[str, str]] | None = None,
) -> str:
    def render_row(row: list[CellModel], row_index: int) -> str:
        cells: list[str] = []
        for cell_index, cell in enumerate(row):
            tag = "th" if cell.header or row_index == 0 else "td"
            attrs = []
            if tag == "th" and row_index == 0:
                attrs.append('scope="col"')
            if cell.colspan > 1:
                attrs.append(f'colspan="{cell.colspan}"')
            if cell.rowspan > 1:
                attrs.append(f'rowspan="{cell.rowspan}"')
            attr_text = (" " + " ".join(attrs)) if attrs else ""
            content = _render_text(cell.text)
            if (
                excluded_codes
                and cell_index == 0
                and row_index > 0
                and cell.text.strip() in excluded_codes
            ):
                label = excluded_codes[cell.text.strip()].get("category_label", "定向·不可报")
                content += f'<span class="job-excluded-tag">{_render_text(label)}·不可报</span>'
            cells.append(f"<{tag}{attr_text}>{content}</{tag}>")
        if action_column and row_index > 0:
            cells.append(
                '<td class="job-row__action"><button type="button" class="job-compare-button" '
                'data-job-compare>Add to compare</button></td>'
            )
        attributes = row_attributes.get(row_index, {}) if row_attributes else {}
        if excluded_codes and row_index > 0 and row and row[0].text.strip() in excluded_codes:
            attributes = {**attributes, "data-excluded": "1"}
        attr_text = "".join(
            f' {html.escape(str(name), quote=True)}="{html.escape(str(value), quote=True)}"'
            for name, value in attributes.items()
        )
        return "<tr" + attr_text + ">" + "".join(cells) + "</tr>"

    header_rows = table.rows[:1]
    body_rows = table.rows[1:]
    header_html = "".join(render_row(row, index) for index, row in enumerate(header_rows))
    if action_column and header_html:
        header_html = header_html.replace("</tr>", '<th scope="col">操作</th></tr>', 1)
    body_html = "".join(render_row(row, index + 1) for index, row in enumerate(body_rows))
    class_name = "table-shell" + (f" {extra_class}" if extra_class else "")
    return (
        f'<div class="{class_name}"><table class="data-table" data-source-table="{table.index}">'
        f'<caption class="sr-only">源文档第 {table.index + 1} 张表</caption>'
        + (f"<thead>{header_html}</thead>" if header_html else "")
        + (f"<tbody>{body_html}</tbody>" if body_html else "")
        + "</table></div>"
    )


def render_blocks(blocks: Iterable[Block], page_kind: str, excluded_codes: dict[str, dict[str, str]] | None = None) -> str:
    rendered: list[str] = []
    for block in blocks:
        if block.kind == "table" and block.table is not None:
            rendered.append(_render_table(block.table, excluded_codes=excluded_codes))
            continue
        if block.kind != "paragraph" or not block.text.strip():
            continue
        style = block.style.lower()
        safe = _render_text(block.text)
        token = _class_token(block.style)
        if "heading 1" in style:
            rendered.append(f'<h2 class="doc-heading {token}">{safe}</h2>')
        elif "heading 2" in style:
            rendered.append(f'<h3 class="doc-heading {token}">{safe}</h3>')
        elif "heading 3" in style:
            rendered.append(f'<h4 class="doc-heading {token}">{safe}</h4>')
        elif "list" in style:
            rendered.append(f'<p class="doc-list-item {token}">{safe}</p>')
        else:
            rendered.append(f'<p class="doc-paragraph {token}" data-page-kind="{page_kind}">{safe}</p>')
    return "\n".join(rendered)


def _template_text(name: str, *, optional: bool = False) -> str:
    path = TEMPLATE_DIR / name
    if optional and not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def assemble_page(template_name: str, context: dict[str, str]) -> str:
    source = _template_text(template_name)
    for key, value in context.items():
        source = source.replace("{{" + key + "}}", value)
    if "{{" in source:
        unresolved = sorted({part.split("}}", 1)[0] for part in source.split("{{")[1:]})
        raise ValueError(f"模板仍有未解析槽位: {', '.join(unresolved)}")
    return source


def _generic_context(model: DocumentModel, page_kind: str) -> dict[str, str]:
    is_jobs = page_kind == "jobs"
    page_title = "安徽十六市 2026 年度\n软件工程专业可报岗位汇总" if is_jobs else "安徽全省 16 市本科普通岗\n公务员 / 事业编年度全包分析"
    page_note = (
        "岗位总览与逐岗数据终稿 · 省考 / 事业单位 / 国考"
        if is_jobs
        else "覆盖市直、104 个县级行政区及乡镇街道适用规则"
    )
    hero = (
        '<div class="shell" style="padding:72px 0 82px">'
        '<p style="margin:0 0 18px;color:#9dc8c3;letter-spacing:.22em">皖域择岗档案 · ANHUI FIELD NOTES</p>'
        f'<h1 style="max-width:900px;margin:0;font-family:var(--display);font-size:clamp(38px,6vw,76px);line-height:1.15;white-space:pre-line">{_render_text(page_title)}</h1>'
        f'<p style="max-width:760px;margin:24px 0 0;color:rgba(255,255,255,.68)">{_render_text(page_note)}</p>'
        "</div>"
    )
    nav = (
        '<nav class="section-nav" aria-label="章节导航"><div class="section-nav__inner shell">'
        '<a href="#original-content" aria-current="true">完整文档</a>'
        "</div></nav>"
    )
    content = (
        '<section class="content-stage shell" id="original-content">'
        '<div class="document-flow">'
        + render_blocks(model.blocks, page_kind)
        + "</div></section>"
    )
    return {
        "COMMON_CSS": _template_text("common.css"),
        "PAGE_CSS": _template_text(f"{page_kind}.css", optional=True),
        "PAGE_HERO": hero,
        "PAGE_NAV": nav,
        "PAGE_CONTENT": content,
        "PAGE_DATA": json.dumps({}, ensure_ascii=False),
        "PAGE_JS": _template_text(f"{page_kind}.js", optional=True),
    }


def _table_plain_text(table: TableModel) -> str:
    return " ".join(cell.text for row in table.rows for cell in row)


def _jobs_city_summaries(model: DocumentModel) -> list[dict[str, object]]:
    overview = model.tables[0]
    summaries: list[dict[str, object]] = []
    for row in overview.rows[1:]:
        values = [cell.text.strip() for cell in row]
        if len(values) < 4 or values[0] == "合计":
            continue
        summaries.append(
            {
                "city": values[0],
                "jobs": int(values[1]),
                "recruits": int(values[2]),
                "reference": values[3],
            }
        )
    return summaries


def _exam_kind(title: str) -> str:
    if "国家公务员" in title or "国考" in title:
        return "国考"
    if "事业单位" in title:
        return "事业单位"
    if "省考" in title:
        return "省考"
    return "其他"


def _city_ranges(model: DocumentModel) -> list[tuple[str, int, int, int, int]]:
    starts: list[tuple[str, int, int, int]] = []
    pattern = re.compile(r"^(.+?)市｜(\d+)岗 / (\d+)人$")
    for index, block in enumerate(model.blocks):
        if block.kind != "paragraph":
            continue
        match = pattern.match(block.text.strip())
        if match:
            starts.append((match.group(1), int(match.group(2)), int(match.group(3)), index))
    ranges: list[tuple[str, int, int, int, int]] = []
    for item_index, (city, jobs, recruits, start) in enumerate(starts):
        end = starts[item_index + 1][3] if item_index + 1 < len(starts) else len(model.blocks)
        ranges.append((city, jobs, recruits, start, end))
    return ranges


def _integer_cell(value: str) -> int:
    """Parse a source count cell while keeping the document's dash semantics safe."""
    match = re.search(r"\d[\d,]*", value.replace("，", ","))
    return int(match.group(0).replace(",", "")) if match else 0


def _competition_counts(fields: dict[str, str], exam: str = "") -> dict[str, object]:
    """Resolve the competition denominator at row grain.

    The source reports use effective written-test/qualified counts where
    available.  Rows without that count explicitly fall back to registration,
    preserving the user's requested priority instead of silently treating a
    missing value as zero.
    """
    examinees = _integer_cell(fields.get("有效笔试/达线/规模参考", ""))
    if not examinees:
        examinees = _integer_cell(fields.get("有效笔试/达线", ""))
    registrations = _integer_cell(fields.get("报名*", ""))
    observations = competition_observations(fields)
    if examinees:
        metric_type = "interview_shortlisted" if str(exam) == "国考" else "examinees"
        return {"examinees": examinees, "registrations": registrations, "competition_base": examinees, "competition_source": "考试人数", "competition_metric_type": metric_type, "competition_observations": observations}
    if registrations:
        return {"examinees": 0, "registrations": registrations, "competition_base": registrations, "competition_source": "报名人数", "competition_metric_type": "registrations", "competition_observations": observations}
    return {"examinees": 0, "registrations": 0, "competition_base": 0, "competition_source": "无可用分母", "competition_metric_type": None, "competition_observations": observations}


def _competition_display(ratio: float | int) -> str:
    """Render the stored recruits/examinees ratio in the familiar 1:N form."""
    value = float(ratio or 0)
    return f"1:{1 / value:.1f}" if value > 0 else "—"


def _row_ratio_chip(record: dict[str, object]) -> str:
    """Inline 1:N chip with an explicit denominator type."""
    base = int(record.get("competition_base", 0) or 0)
    recruits = int(record.get("recruits", 0) or 0)
    source = str(record.get("competition_source", "") or "")
    metric_type = str(record.get("competition_metric_type", "") or "")
    if base <= 0 or recruits <= 0:
        return ""
    display = _competition_display(recruits / base)
    title = f"竞争比 = 招录 {recruits} ÷ {source}分母 {base}。不同分母不合并；报名期人数更新后可手动修正。"
    fallback = "" if source == "考试人数" else " row-ratio--fallback"
    return (
        f'<span class="row-ratio{fallback}" data-base="{base}" data-competition-type="{html.escape(metric_type, quote=True)}" title="{html.escape(title, quote=True)}">{display}</span>'
    )


def _recruit_structure(records: list[dict[str, object]]) -> list[dict[str, object]]:
    """Bucket jobs by recruits size for the opportunity insight view."""
    buckets = [
        {"label": "1 人岗", "min": 1, "max": 1},
        {"label": "2–3 人岗", "min": 2, "max": 3},
        {"label": "≥4 人岗", "min": 4, "max": 10 ** 6},
    ]
    for bucket in buckets:
        selected = [record for record in records if bucket["min"] <= int(record["recruits"]) <= bucket["max"]]
        bucket["jobs"] = len(selected)
        bucket["recruits"] = sum(int(record["recruits"]) for record in selected)
    return buckets


def _city_clusters(
    cities: list[dict[str, object]],
    salary: dict[str, dict[str, dict[str, float | None]]],
    k: int = 3,
    rounds: int = 12,
) -> list[dict[str, object]]:
    """Deterministic k-means over [jobs, recruits, ratio, salary3y]; clusters named by salary order."""
    import math

    features: dict[str, list[float]] = {}
    for item in cities:
        city = str(item["city"])
        value = float(salary.get("公务员", {}).get(city, {}).get("3年") or 0)
        features[city] = [float(int(item["jobs"])), float(int(item["recruits"])), float(item.get("ratio", 0) or 0), value]
    means = [[0.0] * 4 for _ in range(k)]
    for dimension in range(4):
        values = sorted(float(row[dimension]) for row in features.values())
        low, high = values[0], values[-1]
        for cluster_index in range(k):
            means[cluster_index][dimension] = low + (high - low) * cluster_index / max(k - 1, 1)
    assignment: dict[str, int] = {}
    for _ in range(rounds):
        changed = False
        for city, row in features.items():
            best, best_distance = 0, float("inf")
            for cluster_index, mean in enumerate(means):
                distance = math.sqrt(sum((row[dim] - mean[dim]) ** 2 for dim in range(4)))
                if distance < best_distance:
                    best, best_distance = cluster_index, distance
            if assignment.get(city) != best:
                assignment[city] = best
                changed = True
        for cluster_index in range(k):
            members = [features[city] for city, index in assignment.items() if index == cluster_index]
            if members:
                means[cluster_index] = [
                    sum(row[dim] for row in members) / len(members) for dim in range(4)
                ]
        if not changed:
            break
    clusters: list[dict[str, object]] = []
    for cluster_index in range(k):
        members = [str(item["city"]) for item in cities if assignment.get(str(item["city"])) == cluster_index]
        if not members:
            continue
        salary_mean = sum(float(salary.get("公务员", {}).get(city, {}).get("3年") or 0) for city in members) / len(members)
        jobs_mean = sum(int(next(int(item["jobs"]) for item in cities if str(item["city"]) == city)) for city in members) / len(members)
        clusters.append({"index": cluster_index, "cities": members, "salary_mean": salary_mean, "jobs_mean": jobs_mean})
    clusters.sort(key=lambda cluster: -cluster["salary_mean"])
    labels = ("待遇领先梯队", "中部梯队", "性价比潜力梯队")
    for rank, cluster in enumerate(clusters):
        cluster["label"] = labels[min(rank, len(labels) - 1)]
    return clusters


def _quadrant_svg(
    cities: list[dict[str, object]],
    salary: dict[str, dict[str, dict[str, float | None]]],
) -> str:
    """竞争比 × 待遇四象限散点：找“高待遇却没那么卷”的格子。"""
    points: list[tuple[str, float, float, int]] = []
    for item in cities:
        city = str(item["city"])
        ratio = float(item.get("ratio", 0) or 0)
        value = float(salary.get("公务员", {}).get(city, {}).get("3年") or 0)
        if ratio <= 0 or value <= 0:
            continue
        points.append((city, ratio, value, int(item["jobs"])))
    if len(points) < 4:
        return ""
    width, height, pad = 720.0, 420.0, 56.0
    xs = sorted(point[1] for point in points)
    ys = sorted(point[2] for point in points)
    median_x = xs[len(xs) // 2]
    median_y = ys[len(ys) // 2]
    x0, x1 = 0.0, xs[-1] * 1.08
    y0, y1 = ys[0] - 0.5, ys[-1] + 0.5
    scale_x = (width - pad * 2) / (x1 - x0)
    scale_y = (height - pad * 2) / (y1 - y0)
    max_jobs = max(point[3] for point in points) or 1

    def px(ratio: float) -> float:
        return pad + (ratio - x0) * scale_x

    def py(value: float) -> float:
        return height - pad - (value - y0) * scale_y

    mx, my = px(median_x), py(median_y)
    placed_boxes: list[tuple[float, float, float, float]] = []
    dots: list[str] = []
    for city, ratio, value, jobs in sorted(points, key=lambda item: item[2], reverse=True):
        cx, cy = px(ratio), py(value)
        r = 4.5 + (jobs / max_jobs) ** 0.5 * 7
        quadrant = ("r" if value >= median_y else "b") + ("g" if ratio >= median_x else "h")
        fill = {"rg": "#2b9e9a", "rh": "#2167dc", "bg": "#d9912c", "bh": "#93a1b5"}[quadrant]
        label = city
        label_w = 12 * len(label) + 8
        side_right = cx < width - (label_w + 26)
        lx = cx + r + 5 if side_right else cx - r - 5
        anchor = "start" if side_right else "end"
        box_x0 = lx if side_right else lx - label_w
        box_x1 = lx + label_w if side_right else lx
        placed = None
        for dy in (3.5, -8, 15, -19.5, 26):
            by0 = cy + dy - 8
            by1 = cy + dy + 3
            if all(box_x1 < bx0 or box_x0 > bx1 or by1 < b_y0 or by0 > b_y1 for bx0, b_y0, bx1, b_y1 in placed_boxes):
                placed = (cy + dy, (box_x0, by0, box_x1, by1))
                break
        title = f"{city}：竞争 1:{1 / ratio:.0f} · 公务员3年 {value:.1f} 万 · {jobs} 岗"
        text = ""
        if placed is not None:
            label_y, box = placed
            placed_boxes.append(box)
            text = f'<text x="{lx:.1f}" y="{label_y:.1f}" text-anchor="{anchor}" font-size="10.5" fill="#54637d">{city}</text>'
        dots.append(
            f'<g class="quad-dot" data-city="{html.escape(city, quote=True)}">'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" fill-opacity=".82" stroke="#fff" stroke-width="1.2">'
            f"<title>{html.escape(title)}</title></circle>{text}</g>"
        )
    return (
        '<svg class="quad-scatter" viewBox="0 0 720 420" role="img" aria-label="竞争比与待遇四象限散点图">'
        f'<rect x="{pad}" y="{pad}" width="{mx - pad:.1f}" height="{my - pad:.1f}" fill="#2b9e9a" opacity=".06"/>'
        f'<rect x="{mx:.1f}" y="{pad}" width="{width - pad - mx:.1f}" height="{my - pad:.1f}" fill="#2167dc" opacity=".06"/>'
        f'<rect x="{pad}" y="{my:.1f}" width="{mx - pad:.1f}" height="{height - pad - my:.1f}" fill="#d9912c" opacity=".07"/>'
        f'<rect x="{mx:.1f}" y="{my:.1f}" width="{width - pad - mx:.1f}" height="{height - pad - my:.1f}" fill="#93a1b5" opacity=".08"/>'
        f'<line x1="{mx:.1f}" y1="{pad}" x2="{mx:.1f}" y2="{height - pad}" stroke="#b8cdf0" stroke-dasharray="5 4"/>'
        f'<line x1="{pad}" y1="{my:.1f}" x2="{width - pad}" y2="{my:.1f}" stroke="#b8cdf0" stroke-dasharray="5 4"/>'
        + "".join(dots)
        + f'<line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" stroke="#c9d9ee"/>'
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height - pad}" stroke="#c9d9ee"/>'
        f'<text x="{(pad + width) / 2:.0f}" y="{height - 12}" text-anchor="middle" font-size="10.5" fill="#7a8aa0">竞争缓和（1:N 小）→</text>'
        f'<text x="16" y="{height / 2:.0f}" text-anchor="middle" font-size="10.5" fill="#7a8aa0" transform="rotate(-90 16 {height / 2:.0f})">公务员 3 年待遇（万元/年）→</text>'
        f'<text x="{mx + (width - pad - mx) / 2:.0f}" y="{pad + 16}" text-anchor="middle" font-size="11" fill="#2167dc" font-weight="700">高待遇 · 竞争紧</text>'
        f'<text x="{pad + (mx - pad) / 2:.0f}" y="{pad + 16}" text-anchor="middle" font-size="11" fill="#1f7a75" font-weight="700">高待遇 · 竞争缓 ★</text>'
        f'<text x="{pad + (mx - pad) / 2:.0f}" y="{height - pad - 8}" text-anchor="middle" font-size="11" fill="#a06613" font-weight="700">待遇一般 · 竞争缓</text>'
        f'<text x="{mx + (width - pad - mx) / 2:.0f}" y="{height - pad - 8}" text-anchor="middle" font-size="11" fill="#6d7b90" font-weight="700">待遇一般 · 竞争紧</text>'
        "</svg>"
    )


def _squarify(items: list[tuple[str, float]], x: float, y: float, w: float, h: float) -> list[tuple[str, float, float, float, float]]:
    """Squarified treemap（面积归一化）；返回 (label, x, y, w, h) 像素矩形。"""
    rects: list[tuple[str, float, float, float, float]] = []
    total = sum(value for _, value in items)
    scaled = [(label, (value / total) * w * h) for label, value in items] if total > 0 else []
    remaining = list(scaled)

    def worst(row: list[tuple[str, float]], length: float) -> float:
        row_sum = sum(area for _, area in row)
        if row_sum <= 0 or length <= 0:
            return float("inf")
        side = row_sum / length
        worst_ratio = 0.0
        for _, area in row:
            strip = area / side
            worst_ratio = max(worst_ratio, side / strip, strip / side)
        return worst_ratio

    def place(row: list[tuple[str, float]]) -> None:
        nonlocal x, y, w, h
        row_sum = sum(area for _, area in row)
        if row_sum <= 0 or w <= 0 or h <= 0:
            return
        if w >= h:
            side = row_sum / h
            offset = y
            for label, area in row:
                height = area / side
                rects.append((label, x, offset, side, height))
                offset += height
            x += side
            w = max(w - side, 0.0)
        else:
            side = row_sum / w
            offset = x
            for label, area in row:
                width = area / side
                rects.append((label, offset, y, width, side))
                offset += width
            y += side
            h = max(h - side, 0.0)

    row: list[tuple[str, float]] = []
    while remaining:
        length = max(min(w, h), 0.001)
        candidate = row + [remaining[0]]
        if not row or worst(candidate, length) <= worst(row, length):
            row = candidate
            remaining.pop(0)
        else:
            place(row)
            row = []
    if row:
        place(row)
    return rects


def _jobs_treemap_svg(cities: list[dict[str, object]]) -> str:
    """招录名额树图：矩形面积 = 该市招录人数。"""
    items = [(str(item["city"]), float(int(item["recruits"]))) for item in cities if int(item["recruits"]) > 0]
    items.sort(key=lambda pair: -pair[1])
    width, height = 640.0, 300.0
    rects = _squarify(items, 0, 0, width, height)
    max_value = max((value for _, value in items), default=1)
    cells: list[str] = []
    for label, x, y, w, h in rects:
        if w < 26 or h < 22:
            continue
        intensity = next(value for name, value in items if name == label) / max_value
        cells.append(
            f'<g class="treemap-cell" data-city="{html.escape(label, quote=True)}" style="--tint:{intensity:.3f}">'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w - 2:.1f}" height="{h - 2:.1f}" rx="6"><title>{label}：招录 {next(int(value) for name, value in items if name == label)} 人</title></rect>'
            + (f'<text x="{x + w / 2:.1f}" y="{y + h / 2 - 2:.1f}">{label}</text><text class="treemap-value" x="{x + w / 2:.1f}" y="{y + h / 2 + 13:.1f}">{next(int(value) for name, value in items if name == label)} 人</text>' if w > 52 and h > 34 else "")
            + "</g>"
        )
    return (
        '<svg class="jobs-treemap" viewBox="0 0 640 300" role="img" aria-label="招录名额城市树图">'
        + "".join(cells)
        + "</svg>"
    )



def extract_job_records(model: DocumentModel) -> list[dict[str, object]]:
    """Extract one stable, source-addressable record for every岗位 row.

    The overview table is deliberately excluded: only tables that follow a city
    Heading 2 are considered job tables.  This keeps the record count aligned
    with the source document's 544岗位 rows and preserves every raw cell for
    rendering/export without inventing fields.
    """
    records: list[dict[str, object]] = []
    for city, _jobs, _recruits, start, end in _city_ranges(model):
        city = normalize_source_city(city)
        index = start + 1
        while index < end:
            block = model.blocks[index]
            if (
                block.kind == "paragraph"
                and "heading 2" in block.style.lower()
                and index + 1 < end
                and model.blocks[index + 1].kind == "table"
                and model.blocks[index + 1].table is not None
            ):
                title = block.text.strip()
                exam = _exam_kind(title)
                table = model.blocks[index + 1].table
                headers = [cell.text.strip() for cell in table.rows[0]] if table.rows else []
                for row_index, row in enumerate(table.rows[1:], start=1):
                    values = [cell.text.strip() for cell in row]
                    fields = {
                        headers[column_index] if column_index < len(headers) else f"字段{column_index + 1}": value
                        for column_index, value in enumerate(values)
                    }
                    competition = _competition_counts(fields, exam)
                    code = values[0] if values else ""
                    unit_position = values[1] if len(values) > 1 else ""
                    recruits = _integer_cell(values[2]) if len(values) > 2 else 0
                    record_id = f"{city}-{table.index:03d}-{row_index:03d}"
                    record = {
                        "record_id": record_id,
                        "city": city,
                        "exam": exam,
                        "title": title,
                        "code": code,
                        "unit_position": unit_position,
                        "recruits": recruits,
                        "source_table": table.index,
                        "source_row": row_index,
                        "fields": fields,
                        "raw_cells": values,
                        "natures": _job_natures(unit_position),
                        **competition,
                    }
                    exclusion = JOB_EXCLUSIONS.get(str(code).strip())
                    if exclusion:
                        record["exclusion"] = exclusion
                    eligibility = POSITION_ELIGIBILITY.get(str(code).strip())
                    if eligibility:
                        record["eligibility"] = eligibility
                    records.append(record)
                index += 2
                continue
            index += 1
    return records


def build_job_metrics(
    records: list[dict[str, object]], summaries: list[dict[str, object]] | None = None
) -> dict[str, object]:
    """Build small deterministic rollups used by the岗位 workbench and tests."""
    exam_rollup: dict[str, dict[str, int]] = {}
    city_rollup: dict[str, dict[str, int]] = {}
    city_exam: dict[str, dict[str, dict[str, int]]] = {}
    city_competition: dict[str, dict[str, dict[str, object]]] = {}
    for record in records:
        exam = str(record["exam"])
        city = str(record["city"])
        recruits = int(record["recruits"])
        exam_item = exam_rollup.setdefault(exam, {"jobs": 0, "recruits": 0})
        exam_item["jobs"] += 1
        exam_item["recruits"] += recruits
        city_item = city_rollup.setdefault(city, {"jobs": 0, "recruits": 0})
        city_item["jobs"] += 1
        city_item["recruits"] += recruits
        city_exam_item = city_exam.setdefault(city, {}).setdefault(exam, {"jobs": 0, "recruits": 0})
        city_exam_item["jobs"] += 1
        city_exam_item["recruits"] += recruits
        competition_item = city_competition.setdefault(city, {}).setdefault(
            exam,
            {
                "examinees": 0, "registrations": 0, "competition_base": 0,
                "fallback_rows": 0, "examinee_rows": 0, "registration_rows": 0,
                "examinee_recruits": 0, "registration_recruits": 0,
                "examinee_base": 0, "registration_base": 0,
                "interview_shortlisted_rows": 0, "interview_shortlisted_recruits": 0,
                "interview_shortlisted_base": 0,
            },
        )
        examinees = int(record.get("examinees", 0) or 0)
        registrations = int(record.get("registrations", 0) or 0)
        competition_base = int(record.get("competition_base", 0) or 0)
        competition_item["examinees"] += examinees
        competition_item["registrations"] += registrations
        competition_item["competition_base"] += competition_base
        competition_item["fallback_rows"] += int(record.get("competition_source") == "报名人数")
        metric_type = str(record.get("competition_metric_type") or ("interview_shortlisted" if exam == "国考" and examinees > 0 else "examinees" if examinees > 0 else "registrations" if registrations > 0 else ""))
        if metric_type == "interview_shortlisted" and examinees > 0:
            competition_item["interview_shortlisted_base"] += examinees
            competition_item["interview_shortlisted_rows"] += 1
            competition_item["interview_shortlisted_recruits"] += recruits
        elif metric_type == "examinees" and examinees > 0:
            competition_item["examinee_base"] += examinees
            competition_item["examinee_rows"] += 1
            competition_item["examinee_recruits"] += recruits
        elif metric_type == "registrations" and registrations > 0:
            competition_item["registration_base"] += registrations
            competition_item["registration_rows"] += 1
            competition_item["registration_recruits"] += recruits

    ordered_cities: list[dict[str, object]] = []
    if summaries:
        for summary in summaries:
            city = str(summary["city"])
            item = city_rollup.get(city, {"jobs": 0, "recruits": 0})
            ordered_cities.append(
                {
                    "city": city,
                    "jobs": int(item["jobs"]),
                    "recruits": int(item["recruits"]),
                    "reference": summary.get("reference", ""),
                    "exam": city_exam.get(city, {}),
                }
            )
    else:
        ordered_cities = [
            {"city": city, "jobs": item["jobs"], "recruits": item["recruits"], "exam": city_exam.get(city, {})}
            for city, item in city_rollup.items()
        ]
    for city, exam_items in city_competition.items():
        for exam, exam_item in exam_items.items():
            base = int(exam_item["competition_base"] or 0)
            recruits_for_exam = int(city_exam.get(city, {}).get(exam, {}).get("recruits", 0) or 0)
            exam_item["ratio"] = round(recruits_for_exam / base, 8) if base else 0
            exam_item["source"] = "考试人数优先，缺失回退报名" if int(exam_item["fallback_rows"] or 0) else ("考试人数" if base else "无可用分母")
            row_count = int(city_exam.get(city, {}).get(exam, {}).get("jobs", 0) or 0)
            metric_specs = {
                "examinees": ("examinee_rows", "examinee_recruits", "examinee_base"),
                "interview_shortlisted": ("interview_shortlisted_rows", "interview_shortlisted_recruits", "interview_shortlisted_base"),
                "registrations": ("registration_rows", "registration_recruits", "registration_base"),
            }
            competition_metrics = {}
            for metric_name, (rows_key, recruits_key, base_key) in metric_specs.items():
                metric_rows = int(exam_item.get(rows_key, 0) or 0)
                metric_base = int(exam_item.get(base_key, 0) or 0)
                metric_recruits = int(exam_item.get(recruits_key, 0) or 0)
                if metric_rows or metric_base:
                    competition_metrics[metric_name] = {
                        "base": metric_base or None,
                        "recruits": metric_recruits,
                        "coverage_rows": metric_rows,
                        "coverage_rate": round(metric_rows / row_count, 4) if row_count else 0,
                        "ratio": round(metric_recruits / metric_base, 8) if metric_base else None,
                    }
            types = [key for key, value in competition_metrics.items() if int(value.get("coverage_rows", 0) or 0) > 0]
            if len(types) > 1:
                ratio_status = "mixed_denominators"
            elif not types:
                ratio_status = "unavailable"
            elif competition_metrics[types[0]]["coverage_rows"] < row_count:
                ratio_status = "partial_coverage"
            else:
                ratio_status = "single_denominator"
            exam_item["competition_metrics"] = competition_metrics
            exam_item["ratio_status"] = ratio_status
            exam_item["ratio_comparable"] = ratio_status == "single_denominator"
    for row in ordered_cities:
        city = str(row["city"])
        exam_items = city_competition.get(city, {})
        examinees = sum(int(item["examinees"] or 0) for item in exam_items.values())
        registrations = sum(int(item["registrations"] or 0) for item in exam_items.values())
        competition_base = sum(int(item["competition_base"] or 0) for item in exam_items.values())
        fallback_rows = sum(int(item["fallback_rows"] or 0) for item in exam_items.values())
        all_row_count = sum(int((city_exam.get(city, {}).get(exam) or {}).get("jobs", 0) or 0) for exam in exam_items)
        competition_metrics = {}
        for metric_name in ("examinees", "interview_shortlisted", "registrations"):
            base = sum(int((item.get("competition_metrics") or {}).get(metric_name, {}).get("base") or 0) for item in exam_items.values())
            metric_recruits = sum(int((item.get("competition_metrics") or {}).get(metric_name, {}).get("recruits") or 0) for item in exam_items.values())
            coverage_rows = sum(int((item.get("competition_metrics") or {}).get(metric_name, {}).get("coverage_rows") or 0) for item in exam_items.values())
            if base or coverage_rows:
                competition_metrics[metric_name] = {
                    "base": base or None,
                    "recruits": metric_recruits,
                    "coverage_rows": coverage_rows,
                    "coverage_rate": round(coverage_rows / all_row_count, 4) if all_row_count else 0,
                    "ratio": round(metric_recruits / base, 8) if base else None,
                }
        metric_types = [key for key, value in competition_metrics.items() if int(value.get("coverage_rows", 0) or 0) > 0]
        if len(metric_types) > 1:
            city_ratio_status = "mixed_denominators"
        elif not metric_types:
            city_ratio_status = "unavailable"
        elif competition_metrics[metric_types[0]]["coverage_rows"] < all_row_count:
            city_ratio_status = "partial_coverage"
        else:
            city_ratio_status = "single_denominator"
        row.update(
            {
                "examinees": examinees,
                "registrations": registrations,
                "competition_base": competition_base,
                "competition_source": "考试人数优先，缺失回退报名" if fallback_rows else ("考试人数" if competition_base else "无可用分母"),
                "competition": exam_items,
                "ratio": round(int(row["recruits"]) / competition_base, 8) if competition_base else 0,
                "competition_metrics": competition_metrics,
                "ratio_status": city_ratio_status,
                "ratio_comparable": city_ratio_status == "single_denominator",
            }
        )
    return {
        "totals": {"jobs": len(records), "recruits": sum(int(record["recruits"]) for record in records)},
        "exam": exam_rollup,
        "cities": ordered_cities,
        "competition": city_competition,
    }


def _render_job_group(
    city: str,
    heading: Block,
    table: TableModel,
    records_by_source: dict[tuple[int, int], dict[str, object]] | None = None,
) -> str:
    title = heading.text.strip()
    exam = _exam_kind(title)
    row_count = max(len(table.rows) - 1, 0)
    row_attributes: dict[int, dict[str, str]] = {}
    for row_index, row in enumerate(table.rows[1:], start=1):
        record = (records_by_source or {}).get((table.index, row_index))
        if record is None:
            continue
        raw_search = " ".join(str(cell.text).strip() for cell in row)
        row_attributes[row_index] = {
            "data-job-id": str(record["record_id"]),
            "data-job-city": city,
            "data-job-exam": exam,
            "data-job-code": str(record["code"]),
            "data-search": f"{city} {exam} {title} {raw_search}",
        }
    return (
        f'<details class="job-group" data-city="{html.escape(city, quote=True)}" '
        f'data-exam="{exam}" data-rows="{row_count}" open>'
        '<summary class="job-group__summary">'
        f'<span><small>{exam}</small>{_render_text(title)}</span>'
        f'<b>{row_count} 条记录</b>'
        "</summary>"
        + _render_table(table, "job-table", row_attributes, action_column=True)
        + "</details>"
    )


def _render_city_section(
    city: str,
    jobs: int,
    recruits: int,
    blocks: list[Block],
    sequence: int,
    records_by_source: dict[tuple[int, int], dict[str, object]] | None = None,
) -> str:
    rendered: list[str] = []
    index = 1  # 城市标题已经进入章节抬头
    while index < len(blocks):
        block = blocks[index]
        if block.kind == "paragraph" and "heading 2" in block.style.lower():
            next_index = index + 1
            while next_index < len(blocks) and blocks[next_index].kind == "paragraph" and not blocks[next_index].text.strip():
                next_index += 1
            if next_index < len(blocks) and blocks[next_index].table is not None:
                rendered.append(_render_job_group(city, block, blocks[next_index].table, records_by_source))
                index = next_index + 1
                continue
        if block.kind == "table" and block.table is not None:
            table_class = "scope-table" if len(block.table.rows) == 1 and len(block.table.rows[0]) == 1 else "summary-table"
            rendered.append(_render_table(block.table, table_class))
        elif block.kind == "paragraph" and block.text.strip():
            style = block.style.lower()
            if "heading 1" in style:
                rendered.append(f'<h3 class="city-subheading">{_render_text(block.text)}</h3>')
            else:
                rendered.append(f'<p class="doc-paragraph">{_render_text(block.text)}</p>')
        index += 1

    city_id = f"city-{city}"
    return (
        f'<section class="city-section" id="{city_id}" data-city="{html.escape(city, quote=True)}" data-sequence="{sequence:02d}">'
        '<header class="city-section__header">'
        f'<div class="city-seal" aria-hidden="true">{sequence:02d}</div>'
        '<div>'
        f'<p class="city-section__eyebrow">{_render_text(blocks[0].text)} · {sequence:02d}/16</p>'
        f'<h2>{_render_text(city)}<span>市</span></h2>'
        "</div>"
        '<dl class="city-totals">'
        f'<div><dt>可报岗位</dt><dd>{jobs}<small>岗</small></dd></div>'
        f'<div><dt>招录人数</dt><dd>{recruits}<small>人</small></dd></div>'
        "</dl></header>"
        '<div class="city-section__body">'
        + "".join(rendered)
        + "</div></section>"
    )


def _jobs_map_svg(summaries: list[dict[str, object]]) -> str:
    if not ANHUI_GEOJSON.is_file():
        raise FileNotFoundError(f"缺少安徽省地图数据：{ANHUI_GEOJSON}")
    geojson = json.loads(ANHUI_GEOJSON.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    all_points = [
        point
        for feature in features
        for ring in _geometry_rings(feature["geometry"])
        for point in ring
    ]
    min_lon = min(point[0] for point in all_points)
    max_lon = max(point[0] for point in all_points)
    min_lat = min(point[1] for point in all_points)
    max_lat = max(point[1] for point in all_points)
    width, height, padding = 640.0, 660.0, 30.0
    scale = min((width - padding * 2) / (max_lon - min_lon), (height - padding * 2) / (max_lat - min_lat))
    draw_width = (max_lon - min_lon) * scale
    draw_height = (max_lat - min_lat) * scale
    offset_x = (width - draw_width) / 2
    offset_y = (height - draw_height) / 2

    def project(point: list[float]) -> tuple[float, float]:
        lon, lat = point
        return offset_x + (lon - min_lon) * scale, offset_y + (max_lat - lat) * scale

    def path_for(feature: dict) -> str:
        chunks: list[str] = []
        for ring in _geometry_rings(feature["geometry"]):
            projected = [project(point) for point in ring]
            if not projected:
                continue
            chunks.append("M" + ",".join(f"{x:.1f} {y:.1f}" for x, y in projected) + " Z")
        return " ".join(chunks)

    summary_by_city = {str(item["city"]): item for item in summaries}
    feature_by_city = {
        feature.get("properties", {}).get("name", "").removesuffix("市"): feature
        for feature in features
    }
    maximum = max(int(item["jobs"]) for item in summaries) or 1
    regions: list[str] = []
    labels: list[str] = []
    label_offsets: dict[str, tuple[float, float]] = {
        "亳州": (-10, -10), "淮北": (-8, -10), "宿州": (10, -8), "阜阳": (-10, -4),
        "蚌埠": (12, -5), "淮南": (-12, 12), "滁州": (12, -2), "六安": (-12, -4),
        "合肥": (12, -8), "马鞍山": (12, -9), "芜湖": (12, 8), "铜陵": (-12, 13),
        "安庆": (-12, -7), "池州": (-12, 12), "宣城": (12, 8), "黄山": (12, 9),
    }
    for index, item in enumerate(summaries):
        city = str(item["city"])
        feature = feature_by_city.get(city)
        if feature is None:
            continue
        jobs = int(item["jobs"])
        recruits = int(item["recruits"])
        intensity = jobs / maximum
        d = path_for(feature)
        regions.append(
            f'<path class="jobs-map__region" data-job-region="{city}" data-city="{city}" '
            f'role="button" tabindex="0" aria-pressed="false" pathLength="1" '
            f'style="--job-intensity:{intensity:.4f};--region-delay:{index * 32}ms" d="{d}">'
            f'<title>{city} · {jobs}岗 · 招录{recruits}人</title></path>'
        )
        center = feature.get("properties", {}).get("centroid") or feature.get("properties", {}).get("center")
        x, y = project(center)
        dx, dy = label_offsets.get(city, (10, -8))
        anchor = "end" if dx < 0 else "start"
        labels.append(
            f'<g class="jobs-map__label" data-city="{city}" role="button" tabindex="0" aria-label="{city}市" pointer-events="all">'
            f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anchor}">{city}</text>'
            f'<text class="jobs-map__value" x="{x + dx:.1f}" y="{y + dy + 14:.1f}" text-anchor="{anchor}">{jobs} 岗</text></g>'
        )
    return (
        '<svg id="jobs-map" class="jobs-map" viewBox="0 0 640 660" role="img" preserveAspectRatio="xMidYMid meet" '
        'aria-labelledby="jobs-map-title jobs-map-desc">'
        '<title id="jobs-map-title">安徽十六市软件工程可报岗位热力地图</title>'
        '<desc id="jobs-map-desc">地图颜色按当前选择的岗位数、招录人数或竞争比由低到高变化，点击城市可筛选岗位。</desc>'
        '<g class="jobs-map__regions">' + "".join(regions) + '</g><g class="jobs-map__labels">' + "".join(labels) + "</g></svg>"
    )


def build_jobs_context(model: DocumentModel) -> dict[str, str]:
    summaries = _jobs_city_summaries(model)
    city_ranges = _city_ranges(model)
    summary_by_city = {str(item["city"]): item for item in summaries}
    records = extract_job_records(model)
    metrics = build_job_metrics(records, summaries)
    total_competition_base = sum(int(record.get("competition_base", 0) or 0) for record in records)
    total_competition_ratio = int(metrics["totals"]["recruits"]) / total_competition_base if total_competition_base else 0
    records_by_source = {(int(record["source_table"]), int(record["source_row"])): record for record in records}
    map_svg = _jobs_map_svg(summaries)

    city_lookup = {str(item["city"]): item for item in metrics["cities"]}
    ranked = sorted(metrics["cities"], key=lambda item: (-int(item["jobs"]), -int(item["recruits"]), str(item["city"])))
    rank_rows: list[str] = []
    for rank, item in enumerate(ranked, start=1):
        city = str(item["city"])
        jobs = int(item["jobs"])
        recruits = int(item["recruits"])
        ratio = float(item.get("ratio", 0) or 0)
        ratio_comparable = bool(item.get("ratio_comparable") or item.get("ratio_status") == "single_denominator")
        rank_rows.append(
            f'<tr data-ranking-row data-city="{city}" data-jobs="{jobs}" data-recruits="{recruits}" data-ratio="{ratio:.8f}" data-ratio-comparable="{str(ratio_comparable).lower()}" data-ratio-status="{html.escape(str(item.get("ratio_status", "unavailable")), quote=True)}">'
            f'<td class="rank-cell">{rank:02d}</td><td><button type="button" data-ranking-city="{city}">{city}市</button></td>'
            f'<td class="num-cell">{jobs:,}</td><td class="num-cell">{recruits:,}</td>'
            f'<td><div class="mini-bar"><i style="--bar:{jobs / max(int(ranked[0]["jobs"]), 1) * 100:.1f}%"></i></div><span class="bar-value">{jobs / 544 * 100:.1f}%</span></td></tr>'
        )

    def exam_percent(city: str, exam: str) -> float:
        city_item = city_lookup.get(city, {})
        exam_item = (city_item.get("exam") or {}).get(exam, {}) if isinstance(city_item, dict) else {}
        jobs = int(city_item.get("jobs", 0)) if isinstance(city_item, dict) else 0
        return (int(exam_item.get("jobs", 0)) / jobs * 100) if jobs else 0

    first_city = str(summaries[0]["city"])
    initial_compare = [str(item["city"]) for item in summaries[:3]]
    compare_buttons = "".join(
        f'<button type="button" class="compare-city-button{" is-selected" if city in initial_compare else ""}" '
        f'data-compare-city="{city}" aria-pressed="{str(city in initial_compare).lower()}">{city}市</button>'
        for item in summaries
        for city in [str(item["city"])]
    )
    compare_cards = "".join(
        f'<article class="compare-card" data-compare-card="{city}"><header><span>{index + 1:02d}</span><h3>{city}市</h3></header>'
        f'<dl><div><dt>岗位数</dt><dd data-compare-jobs>{int(item["jobs"]):,}</dd></div><div><dt>招录人数</dt><dd data-compare-recruits>{int(item["recruits"]):,}</dd></div>'
        f'<div><dt>竞争比</dt><dd data-compare-ratio>{_competition_display(item.get("ratio", 0))}</dd></div></dl>'
        f'<div class="compare-stack" aria-label="{city}考试类别构成">'
        f'<i data-compare-exam="省考" style="--segment:{exam_percent(city, "省考"):.2f}%"></i>'
        f'<i data-compare-exam="事业单位" style="--segment:{exam_percent(city, "事业单位"):.2f}%"></i>'
        f'<i data-compare-exam="国考" style="--segment:{exam_percent(city, "国考"):.2f}%"></i></div></article>'
        for index, city in enumerate(initial_compare)
        for item in [city_lookup[city]]
    )

    hero = (
        '<div class="jobs-hero shell">'
        '<div class="jobs-hero__copy">'
        '<p class="hero-kicker"><span>ANHUI · 2026</span> 软件工程岗位观测</p>'
        '<h1><small>十六市岗位地图</small>把机会，<br><em>放回城市里看。</em></h1>'
        '<p class="hero-lead">把 544 条可报岗位与 825 个招录名额放进同一张省域工作台。先看分布，再按考试类别、单位和职位代码下钻到原始表。</p>'
        '<div class="hero-actions"><a class="hero-action" href="#jobs-workbench">进入观测台 <span aria-hidden="true">↓</span></a>'
        '<a class="hero-action hero-action--quiet" href="#job-finder">直接检索岗位</a></div>'
        '<div class="hero-scale" aria-label="终稿规模"><span>终稿规模</span><strong>544 岗 / 825 人</strong>'
        '<small>省考 406 岗 / 678 人 · 事业单位 135 岗 / 144 人 · 国考 3 岗 / 3 人</small></div>'
        '</div><aside class="hero-snapshot" aria-label="数据快照"><span class="snapshot-label">LIVE SNAPSHOT · 2026</span>'
        '<div class="snapshot-ring"><b>16</b><small>座城市</small></div><dl>'
        '<div><dt>岗位总数</dt><dd>544</dd></div><div><dt>招录总数</dt><dd>825</dd></div><div><dt>竞争比</dt><dd>'+_competition_display(total_competition_ratio)+'</dd></div></dl>'
        '<p>点击地图城市，右侧信息卡与下方排行会同步更新。</p></aside></div>'
    )

    nav_links = "".join(f'<a href="#city-{item["city"]}">{item["city"]}</a>' for item in summaries)
    nav = (
        '<nav class="section-nav jobs-nav" aria-label="章节与城市导航"><div class="section-nav__inner shell">'
        '<a href="#jobs-workbench" aria-current="true">观测台</a><a href="#city-compare">排名对比</a><a href="#job-finder">岗位检索</a>'
        + nav_links
        + "</div></nav>"
    )

    workbench = (
        '<section class="jobs-workbench shell" id="jobs-workbench" data-reveal>'
        '<header class="jobs-workbench__header"><div><p class="eyebrow">01 · OPPORTUNITY LENS</p><h2>职位机会观测台</h2>'
        '<span>按岗位数、招录人数和竞争比切换一张地图的读法；竞争比按考试人数优先计算。</span></div>'
        '<div class="metric-switch" id="job-metric" role="group" aria-label="地图指标">'
        '<button type="button" data-job-metric="jobs" aria-pressed="true">岗位数</button>'
        '<button type="button" data-job-metric="recruits" aria-pressed="false">招录人数</button>'
        '<button type="button" data-job-metric="ratio" aria-pressed="false">竞争比</button></div></header>'
        '<div class="jobs-workbench__grid"><aside class="jobs-console" aria-label="岗位筛选控制台">'
        '<div class="console-card console-card--intro"><span>范围已锁定</span><strong>安徽省 16 市</strong><small>数据更新：2025-05-18</small></div>'
        '<div class="console-section"><label for="city-filter">定位城市</label><select id="city-filter"><option value="">全部城市</option>'
        + "".join(f'<option value="{item["city"]}">{item["city"]}市</option>' for item in summaries)
        + '</select></div><div class="console-section"><label for="exam-filter">考试类别</label><select id="exam-filter"><option value="">全部类别</option><option>省考</option><option>事业单位</option><option>国考</option></select></div>'
        '<div class="console-section console-section--legend"><span>岗位热力</span><div class="heat-legend"><i></i><span>低</span><b>高</b></div></div>'
        '<button type="button" class="console-reset" id="clear-filters">重置筛选</button></aside>'
        '<figure class="jobs-map-stage"><div class="map-stage__topline"><span>ANHUI · 16 CITY LAYERS</span><span class="map-live"><i aria-hidden="true"></i>数据已就绪</span></div>'
        + map_svg
        + '<figcaption><span>城市导航热力示意</span><small>颜色随当前指标变化 · 点击城市聚焦</small></figcaption></figure>'
        '<aside class="jobs-inspector" id="jobs-inspector" aria-live="polite"><span class="inspector-tag">机会镜头 · 当前城市</span>'
        '<div class="inspector-city"><small id="inspector-city-label">当前范围</small><strong id="inspector-city">安徽省</strong></div>'
        '<p class="inspector-value"><strong id="job-metric-value">544</strong><span id="job-metric-unit">岗</span></p><p class="inspector-context" id="job-metric-context">全省岗位总数</p>'
        '<div class="inspector-donut" id="inspector-donut" style="--p1:74.6%;--p2:24.8%;--p3:.6%"><span>考试<br>构成</span></div>'
        '<ul class="inspector-legend"><li><i></i><span>省考</span><b id="inspector-provincial">406 · 74.6%</b></li><li><i></i><span>事业单位</span><b id="inspector-institution">135 · 24.8%</b></li><li><i></i><span>国考</span><b id="inspector-national">3 · 0.6%</b></li></ul>'
        '<div class="inspector-foot"><span>全省排名</span><strong id="inspector-rank">—</strong></div><a class="inspector-action" href="#job-finder" id="inspector-action">查看完整岗位</a></aside></div>'
        '<footer class="jobs-workbench__footer"><span>城市导航</span><div class="map-city-strip">'
        + "".join(f'<button type="button" data-map-city="{item["city"]}">{item["city"]}市</button>' for item in summaries)
        + '</div></footer></section>'
    )

    source_overview = render_blocks(model.blocks[: city_ranges[0][3]], "jobs")
    overview = '<section class="overview-stage shell" id="province-overview"><div class="source-overview"><p class="eyebrow">源文档 · 口径底盘</p><h2>所有数字，都能回到原始表。</h2>' + source_overview + '</div></section>'

    comparison = (
        '<section class="city-compare shell" id="city-compare" data-reveal><header class="section-intro section-intro--wide"><p>02 · RANKING & COMPARE</p>'
        '<h2>排名之外，看见机会构成。</h2><span>排序只做定位，不替代岗位条件判断。三城对比会跟随你的选择即时重排。</span></header>'
        '<div class="ranking-layout"><div class="ranking-panel"><header><div><span>机会热力榜</span><strong id="ranking-title">按岗位数</strong></div><span class="ranking-note">岗位数 · 招录人数</span></header>'
        '<div class="ranking-table-wrap"><table class="ranking-table"><thead><tr><th>排名</th><th>城市</th><th>岗位数</th><th>招录人数</th><th>岗位占比</th></tr></thead><tbody id="job-ranking-body">'
        + "".join(rank_rows)
        + '</tbody></table></div></div><aside class="compare-picker"><p class="eyebrow">三城比较台</p><h3>选择最多 3 座城市</h3><div class="compare-city-list" id="compare-city-picker">'
        + compare_buttons
        + '</div><div class="compare-legend"><i></i><span>省考</span><i></i><span>事业单位</span><i></i><span>国考</span></div></aside></div>'
        '<div class="compare-cards" id="compare-cards">' + compare_cards + '</div>'
        '<div class="compare-visual"><div class="compare-visual__head"><div><p class="eyebrow">结构透视</p><h3>三城岗位数构成对比</h3></div><span id="compare-caption">当前选择：合肥 · 滁州 · 马鞍山</span></div>'
        '<div class="compare-chart" id="city-compare-chart" role="img" aria-label="三城岗位数对比图"></div>'
        '<div class="compare-data-table" id="city-compare-table"></div></div></section>'
    )

    city_options = "".join(f'<option value="{item["city"]}">{item["city"]}</option>' for item in summaries)
    city_options = "".join(f'<option value="{item["city"]}">{item["city"]}</option>' for item in summaries)
    finder = (
        '<section class="finder-stage" id="job-finder"><div class="finder-panel shell"><div class="finder-heading"><p class="eyebrow">03 · SOURCE SEARCH</p><h2>在原始表中直接找</h2><span>输入关键词、代码，或用城市与考试类别缩小范围。</span></div>'
        '<div class="finder-controls"><label class="search-control"><span>单位 / 职位 / 代码</span><input id="job-search" type="search" placeholder="例如：数据资源、010009、市场监管" autocomplete="off"></label>'
        f'<label><span>城市</span><select id="finder-city-filter"><option value="">全部城市</option>{city_options}</select></label>'
        '<label><span>考试类别</span><select id="finder-exam-filter"><option value="">全部类别</option><option>省考</option><option>事业单位</option><option>国考</option></select></label>'
        '<button class="finder-button" id="finder-clear" type="button">清除条件</button><button class="finder-button finder-button--quiet" id="toggle-groups" type="button">收起分类</button></div>'
        '<div class="finder-status"><strong id="result-count" role="status" aria-live="polite">正在载入岗位记录</strong><span>筛选不会改动原始数据</span></div><p class="empty-state" id="job-empty" hidden>未找到符合当前条件的原始岗位。请缩短关键词或清除筛选条件。</p></div></section>'
    )

    sections: list[str] = []
    for sequence, (city, jobs, recruits, start, end) in enumerate(city_ranges, start=1):
        expected = summary_by_city.get(city)
        if expected and (jobs != int(expected["jobs"]) or recruits != int(expected["recruits"])):
            raise ValueError(f"{city}城市标题与总览数字不一致")
        sections.append(_render_city_section(city, jobs, recruits, model.blocks[start:end], sequence, records_by_source))

    content = workbench + comparison + overview + finder + '<div class="city-archive shell">' + "".join(sections) + '</div><div id="job-compare-tray" class="job-compare-tray" hidden></div>'
    data = {"cities": summaries, "metrics": metrics, "records": records}
    page_data = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return {
        "COMMON_CSS": _template_text("common.css"),
        "PAGE_CSS": _template_text("jobs.css"),
        "PAGE_HERO": hero,
        "PAGE_NAV": nav,
        "PAGE_CONTENT": content,
        "PAGE_DATA": page_data,
        "PAGE_JS": _template_text("jobs.js"),
    }


def _number_or_none(value: str) -> float | None:
    cleaned = value.strip().replace(",", "")
    if not cleaned or cleaned == "—":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_salary_series(model: DocumentModel) -> dict[str, dict[str, dict[str, float | None]]]:
    stages = ("刚入职", "1年", "3年", "5年", "10年")
    result: dict[str, dict[str, dict[str, float | None]]] = {}
    for employment_type, table_index in (("公务员", 3), ("事业编", 4)):
        table = model.tables[table_index]
        headers = [cell.text.strip() for cell in table.rows[0]]
        if headers[:6] != ["城市", *stages]:
            raise ValueError(f"{employment_type}市直表的列结构与预期不一致")
        city_data: dict[str, dict[str, float | None]] = {}
        for row in table.rows[1:]:
            values = [cell.text.strip() for cell in row]
            city = values[0]
            city_data[city] = {stage: _number_or_none(values[index + 1]) for index, stage in enumerate(stages)}
        result[employment_type] = city_data
    return result


def _salary_city_ranges(model: DocumentModel) -> tuple[list[tuple[str, int, int]], int]:
    starts: list[tuple[str, int]] = []
    pattern = re.compile(r"^3\.\d+\s+(.+?)市（")
    post_start = len(model.blocks)
    for index, block in enumerate(model.blocks):
        if block.kind != "paragraph":
            continue
        text = block.text.strip()
        match = pattern.match(text)
        if match:
            starts.append((match.group(1), index))
        elif starts and "heading 1" in block.style.lower() and text.startswith("四、"):
            post_start = index
            break
    ranges: list[tuple[str, int, int]] = []
    for item_index, (city, start) in enumerate(starts):
        end = starts[item_index + 1][1] if item_index + 1 < len(starts) else post_start
        ranges.append((city, start, end))
    return ranges, post_start


def _geometry_rings(geometry: dict) -> list[list[list[float]]]:
    coordinates = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        return list(coordinates)
    if geometry.get("type") == "MultiPolygon":
        return [ring for polygon in coordinates for ring in polygon]
    return []


def _geometry_polygons(geometry: dict) -> list[list[list[list[float]]]]:
    """Return Polygon and MultiPolygon coordinates in one JS-safe shape."""
    coordinates = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        return [list(coordinates)]
    if geometry.get("type") == "MultiPolygon":
        return list(coordinates)
    return []


def _salary_map_svg(series: dict[str, dict[str, dict[str, float | None]]]) -> str:
    default_values = series["公务员"]
    if not ANHUI_GEOJSON.is_file():
        raise FileNotFoundError(f"缺少安徽省地图数据：{ANHUI_GEOJSON}")

    geojson = json.loads(ANHUI_GEOJSON.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    all_points = [
        point
        for feature in features
        for ring in _geometry_rings(feature["geometry"])
        for point in ring
    ]
    min_lon = min(point[0] for point in all_points)
    max_lon = max(point[0] for point in all_points)
    min_lat = min(point[1] for point in all_points)
    max_lat = max(point[1] for point in all_points)
    width, height, padding = 1000.0, 660.0, 32.0
    scale = min(
        (width - padding * 2) / (max_lon - min_lon),
        (height - padding * 2) / (max_lat - min_lat),
    )
    draw_width = (max_lon - min_lon) * scale
    draw_height = (max_lat - min_lat) * scale
    offset_x = (width - draw_width) / 2
    offset_y = (height - draw_height) / 2

    def project(point: list[float]) -> tuple[float, float]:
        lon, lat = point
        return (
            offset_x + (lon - min_lon) * scale,
            offset_y + (max_lat - lat) * scale,
        )

    def path_for(feature: dict) -> str:
        paths: list[str] = []
        for ring in _geometry_rings(feature["geometry"]):
            projected = [project(point) for point in ring]
            if not projected:
                continue
            commands = [f"M{projected[0][0]:.1f},{projected[0][1]:.1f}"]
            commands.extend(f"L{x:.1f},{y:.1f}" for x, y in projected[1:])
            commands.append("Z")
            paths.append("".join(commands))
        return "".join(paths)

    label_offsets: dict[str, tuple[float, float]] = {
        "亳州": (-10, -12),
        "淮北": (-8, -13),
        "宿州": (10, -10),
        "阜阳": (-10, -8),
        "蚌埠": (12, -8),
        "淮南": (-12, 13),
        "滁州": (12, -2),
        "六安": (-12, -6),
        "合肥": (12, -9),
        "马鞍山": (12, -11),
        "芜湖": (12, 9),
        "铜陵": (-12, 14),
        "安庆": (-12, -8),
        "池州": (-12, 13),
        "宣城": (12, 8),
        "黄山": (12, 10),
    }
    regions: list[str] = []
    hit_regions: list[str] = []
    nodes: list[str] = []
    feature_by_city = {
        feature.get("properties", {}).get("name", "").removesuffix("市"): feature
        for feature in features
    }
    for index, (city, stages) in enumerate(default_values.items()):
        feature = feature_by_city.get(city)
        if feature is None:
            continue
        value = stages["3年"]
        regions.append(
            f'<path class="salary-map__region" data-city="{city}" role="button" tabindex="0" aria-label="{city}市" '
            f'style="--region-delay:{index * 34}ms" fill-rule="evenodd" '
            f'vector-effect="non-scaling-stroke" pathLength="1" d="{path_for(feature)}"/>'
        )
        hit_regions.append(
            f'<path class="salary-map__hit-region" data-city="{city}" aria-hidden="true" '
            f'fill-rule="evenodd" vector-effect="non-scaling-stroke" d="{path_for(feature)}"/>'
        )
        properties = feature.get("properties", {})
        center = properties.get("centroid") or properties.get("center")
        x, y = project(center)
        dx, dy = label_offsets.get(city, (10, -8))
        label_x, label_y = x + dx, y + dy
        anchor = "end" if dx < 0 else "start"
        nodes.append(
            f'<g class="salary-node" data-city="{city}" role="button" tabindex="0" '
            f'style="--node-delay:{180 + index * 48}ms" '
            f'aria-label="{city}，公务员入职3年估算中位数{value:.1f}万元">'
            f'<title>{city} · 公务员入职3年 · {value:.1f}万元</title>'
            f'<circle class="salary-node__hit" cx="{x:.1f}" cy="{y:.1f}" r="18"/>'
            f'<line class="salary-node__leader" x1="{x:.1f}" y1="{y:.1f}" x2="{label_x:.1f}" y2="{label_y:.1f}"/>'
            f'<circle class="salary-node__pulse" cx="{x:.1f}" cy="{y:.1f}" r="8"/>'
            f'<circle class="salary-node__heat" cx="{x:.1f}" cy="{y:.1f}" r="4.6"/>'
            f'<text class="salary-node__label" x="{label_x:.1f}" y="{label_y - 3:.1f}" text-anchor="{anchor}">{city}</text>'
            f'<text class="salary-node__value" x="{label_x:.1f}" y="{label_y + 11:.1f}" text-anchor="{anchor}">{value:.1f}</text>'
            "</g>"
        )
    return (
        '<svg id="salary-map" class="salary-map" viewBox="0 0 1000 660" role="img" '
        'preserveAspectRatio="xMidYMid meet" aria-labelledby="salary-map-title salary-map-desc">'
        '<title id="salary-map-title">安徽十六市年度全包城市热力示意</title>'
        '<desc id="salary-map-desc">城市级导航热力示意，默认显示公务员入职3年估算中位数，单位为万元每年。</desc>'
        '<g class="salary-map__regions">'
        + "".join(regions)
        + '</g><g class="salary-map__nodes">'
        + "".join(nodes)
        + '</g><g class="salary-map__hit-regions" aria-hidden="true">'
        + "".join(hit_regions)
        + "</g></svg>"
    )


def _render_salary_city(
    city: str,
    blocks: list[Block],
    sequence: int,
    series: dict[str, dict[str, dict[str, float | None]]],
) -> str:
    public_value = series["公务员"][city]["3年"]
    institution_value = series["事业编"][city]["3年"]
    heading_text = next((block.text for block in blocks if block.kind == "paragraph" and block.text.strip()), city)
    rendered: list[str] = []
    skipped_heading = False
    for block in blocks:
        if block.kind == "paragraph" and "heading 2" in block.style.lower() and not skipped_heading:
            skipped_heading = True
            continue
        if block.kind == "table" and block.table is not None:
            rendered.append(_render_table(block.table, "district-table"))
        elif block.kind == "paragraph" and block.text.strip():
            style = block.style.lower()
            if "heading 3" in style:
                rendered.append(f'<h3 class="dossier-subheading">{_render_text(block.text)}</h3>')
            elif "list" in style:
                rendered.append(f'<p class="dossier-point">{_render_text(block.text)}</p>')
            else:
                rendered.append(f'<p class="dossier-copy">{_render_text(block.text)}</p>')
    return (
        f'<section class="city-dossier" id="salary-city-{city}" data-city="{city}" data-reveal>'
        '<header class="city-dossier__header">'
        f'<span class="city-dossier__sequence">{sequence:02d}</span>'
        '<div>'
        f'<p>{_render_text(heading_text)}</p><h2>{city}<small>市</small></h2>'
        "</div>"
        '<dl class="dossier-benchmark">'
        f'<div><dt>公务员 · 3年</dt><dd>{public_value:.1f}<small>万元/年</small></dd></div>'
        f'<div><dt>事业编 · 3年</dt><dd>{institution_value:.1f}<small>万元/年</small></dd></div>'
        f'</dl><div class="city-dossier__actions"><a class="city-dossier__back" href="#salary-workbench">返回地图</a>'
        f'<a class="city-dossier__jobs-link" href="安徽十六市2026软件工程可报岗位.html?city={html.escape(city, quote=True)}#city-{html.escape(city, quote=True)}">查看{html.escape(city, quote=True)}岗位</a></div></header>'
        '<div class="city-dossier__content">'
        + "".join(rendered)
        + "</div></section>"
    )


def build_salary_context(model: DocumentModel) -> dict[str, str]:
    series = extract_salary_series(model)
    map_svg = _salary_map_svg(series)
    stages = ("刚入职", "1年", "3年", "5年", "10年")
    stage_buttons = "".join(
        f'<button type="button" data-stage-button="{stage}" aria-pressed="{str(stage == "3年").lower()}">'
        f'<span>{index + 1:02d}</span>{stage}</button>'
        for index, stage in enumerate(stages)
    )
    city_map_buttons = "".join(
        f'<button type="button" class="map-city-chip" data-map-city="{city}">{city}</button>'
        for city in series["公务员"]
    )

    hero = (
        '<div class="salary-hero shell">'
        '<section class="salary-intro" data-reveal>'
        '<div class="salary-intro__copy">'
        '<p class="hero-kicker"><span>ANHUI · 2026</span> 省域待遇交互研究</p>'
        '<h1>安徽 16 市<br><em>年度全包研究</em></h1>'
        '<p class="salary-hero__lead">把岗位身份、职业阶段与城市差异放回同一张地图。不是一眼看完的排行榜，而是一套可以追问、比较和继续下钻的择岗坐标。</p>'
        '<div class="hero-actions"><a class="hero-action" href="#salary-workbench">进入数据地图</a>'
        '<a class="hero-action hero-action--quiet" href="#city-dossiers">浏览城市档案</a></div>'
        '</div>'
        '<dl class="salary-intro__facts" aria-label="研究概况">'
        '<div><dt>覆盖城市</dt><dd><strong>16</strong><small>市</small></dd></div>'
        '<div><dt>核心锚点</dt><dd><strong>120</strong><small>个</small></dd></div>'
        '<div><dt>工龄阶段</dt><dd><strong>5</strong><small>档</small></dd></div>'
        '<div><dt>当前范围</dt><dd><strong>9.1–16.3</strong><small>万元</small></dd></div>'
        '</dl></section>'
        '<section class="salary-workbench" id="salary-workbench" data-reveal aria-label="安徽16市年度全包交互地图">'
        '<header class="salary-workbench__header">'
        '<div><span>PROVINCIAL OBSERVATORY</span><strong>省域年度全包观测台</strong></div>'
        '<div class="salary-current"><span>当前视图</span><strong id="salary-view-label" role="status" aria-live="polite">公务员 · 入职3年</strong></div>'
        '</header>'
        '<div class="salary-workbench__body">'
        '<aside class="salary-console" aria-label="地图控制台">'
        '<div class="console-section"><span class="console-label">身份类别</span>'
        '<div id="employment-type" class="employment-switch" role="group" aria-label="选择身份类型" aria-controls="salary-map salary-ridges">'
        '<button type="button" data-type="公务员" aria-pressed="true">公务员</button>'
        '<button type="button" data-type="事业编" aria-pressed="false">事业编</button></div></div>'
        '<div class="console-section"><span class="console-label">工龄阶段</span>'
        '<div class="stage-rail" id="stage-timeline" role="group" aria-label="选择工龄阶段">'
        + stage_buttons
        + '</div><label class="stage-select-wrap"><span>移动端工龄选择</span><select id="career-stage" aria-controls="salary-map salary-ridges">'
        + "".join(f'<option value="{stage}"{(" selected" if stage == "3年" else "")}>{stage}</option>' for stage in stages)
        + '</select></label></div>'
        '<div class="console-section console-section--legend"><span class="console-label">年度全包 · 万元/年</span>'
        '<div class="salary-map-legend" aria-label="热力色阶"><span>低</span><i aria-hidden="true"></i><span>高</span></div>'
        '<div class="salary-map-range"><b id="heat-min">—</b><small>当前视图范围</small><b id="heat-max">—</b></div></div>'
        '<p class="console-note">统一口径估算 · 非政策工资<br>点击城市即可更新右侧检查器</p>'
        '</aside>'
        '<figure class="salary-map-stage">'
        '<div class="salary-map-stage__topline"><span>16 CITY LAYERS</span><span class="map-live"><i aria-hidden="true"></i>数据已就绪</span></div>'
        + map_svg
        + '<figcaption><span>城市级导航热力示意</span><small>颜色表示当前身份与工龄下的相对水平</small></figcaption>'
        '</figure>'
        '<aside class="salary-inspector" id="salary-map-readout" aria-live="polite">'
        '<span class="salary-map-readout__tag">城市检查器</span>'
        '<div class="salary-inspector__city"><small>当前选中</small><strong id="salary-map-city">合肥</strong></div>'
        '<p class="salary-inspector__amount"><strong id="salary-map-number">16.3</strong><span>万元/年</span></p>'
        '<p class="salary-inspector__context" id="salary-map-context">公务员 · 入职3年</p>'
        '<span class="sr-only" id="salary-map-value">合肥，公务员入职3年，16.3万元/年</span>'
        '<dl class="salary-inspector__metrics">'
        '<div><dt>全省排序</dt><dd id="inspector-rank">1 / 16</dd></div>'
        '<div><dt>相对省均值</dt><dd id="inspector-delta">+42.1%</dd></div>'
        '<div><dt>职业阶段</dt><dd id="inspector-stage">第 3 档</dd></div>'
        '</dl>'
        '<button class="inspector-action" id="open-city-dossier" type="button">查看完整城市档案</button>'
        '<p class="salary-inspector__note">金额为统一口径估算中位数，不代表政策规定工资或个人收入承诺。</p>'
        '</aside></div>'
        '<footer class="salary-workbench__footer"><span>城市导航</span><div class="map-city-strip">'
        + city_map_buttons
        + '</div></footer>'
        '</section></div>'
    )

    nav = (
        '<nav class="section-nav salary-nav" aria-label="章节导航"><div class="section-nav__inner shell">'
        '<a href="#salary-workbench">数据地图</a><a href="#salary-comparison">动态排名</a><a href="#report-basis">报告口径</a>'
        '<a href="#city-dossiers">逐市档案</a><a href="#methods-and-sources">规则与来源</a>'
        "</div></nav>"
    )

    initial_rows = sorted(series["公务员"].items(), key=lambda item: item[1]["3年"] or -1, reverse=True)
    city_rows = "".join(
        f'<div class="ridge-row" data-city="{city}" style="--row-index:{rank - 1}">'
        f'<span class="ridge-rank" data-rank>{rank:02d}</span>'
        f'<button type="button" data-city="{city}"><strong>{city}</strong><small data-ridge-delta>—</small></button>'
        '<svg viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true"><g class="ridge-plot"></g></svg>'
        f'<span class="ridge-value"><strong data-ridge-value>{values["3年"]:.1f}</strong><small>万元/年</small></span></div>'
        for rank, (city, values) in enumerate(initial_rows, start=1)
    )
    city_options = "".join(f'<option value="{city}">{city}</option>' for city in series["公务员"])
    comparison = (
        '<section class="salary-comparison shell" id="salary-comparison">'
        '<div class="comparison-layout">'
        '<header class="section-intro section-intro--sticky" data-reveal><p>02 · DYNAMIC RANKING</p>'
        '<h2>排名之外，<br>看见增长轨迹。</h2>'
        '<span>排名随身份与工龄实时重排；迷你轨迹只连接源表已有的五个节点，不进行节点间预测。</span>'
        '<dl class="comparison-overview">'
        '<div><dt>当前最高</dt><dd id="comparison-topcity">合肥</dd></div>'
        '<div><dt>城市极差</dt><dd id="comparison-spread">—</dd></div>'
        '<div><dt>全省均值</dt><dd id="comparison-average">—</dd></div>'
        '</dl>'
        '<label class="city-search-label">定位城市<select id="salary-city-search"><option value="">选择城市</option>'
        + city_options
        + '</select></label></header>'
        '<div class="ranking-panel" data-reveal>'
        '<div class="ranking-panel__head"><div><span>实时排序</span><strong id="ranking-title">公务员 · 入职3年</strong></div>'
        '<div class="stage-legend" aria-hidden="true">'
        + "".join(f'<span data-stage="{stage}">{stage}</span>' for stage in stages)
        + '</div></div>'
        '<div class="ridge-board" id="salary-ridges">'
        + city_rows
        + '</div></div></div></section>'
    )

    city_ranges, post_start = _salary_city_ranges(model)
    pre_city_start = city_ranges[0][1]
    report_basis = (
        '<section class="report-basis shell" id="report-basis">'
        '<header class="chapter-intro" data-reveal><p>03 · RESEARCH BASIS</p><h2>先理解口径，<br>再相信差异。</h2>'
        '<span>把估算方法、适用边界和数据来源放在结果之前，避免把研究值误读成政策承诺。</span></header>'
        '<div class="research-sheet" data-reveal>'
        + render_blocks(model.blocks[:pre_city_start], "salary")
        + "</div></section>"
    )

    dossiers = "".join(
        _render_salary_city(city, model.blocks[start:end], sequence, series)
        for sequence, (city, start, end) in enumerate(city_ranges, start=1)
    )
    dossier_links = "".join(
        f'<a href="#salary-city-{city}" data-dossier-link="{city}"><span>{index:02d}</span>{city}</a>'
        for index, city in enumerate(series["公务员"], start=1)
    )
    dossier_stage = (
        '<section class="dossier-stage shell" id="city-dossiers">'
        '<header class="chapter-intro chapter-intro--wide" data-reveal><p>04 · CITY DOSSIERS</p>'
        '<h2>十六座城市，<br>十六种现实语境。</h2>'
        '<span>地图负责建立直觉，城市档案负责补足地区层级、适用规则与细分数据。</span></header>'
        '<div class="dossier-layout"><nav class="dossier-index" aria-label="城市档案索引">'
        + dossier_links
        + '</nav><div class="dossier-list">'
        + dossiers
        + '</div></div></section>'
    )
    post_content = (
        '<section class="post-report shell" id="methods-and-sources">'
        '<header class="chapter-intro" data-reveal><p>05 · METHODS & SOURCES</p><h2>所有结论，<br>都应该能够被追溯。</h2>'
        '<span>这里保留源报告的规则解释、计算依据与使用提醒。</span></header>'
        '<div class="research-sheet" data-reveal>'
        + render_blocks(model.blocks[post_start:], "salary")
        + "</div></section>"
    )

    data = {"series": series, "stages": stages, "positions": CITY_POSITIONS}
    page_data = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return {
        "COMMON_CSS": _template_text("common.css"),
        "PAGE_CSS": _template_text("salary.css"),
        "PAGE_HERO": hero,
        "PAGE_NAV": nav,
        "PAGE_CONTENT": comparison + report_basis + dossier_stage + post_content,
        "PAGE_DATA": page_data,
        "PAGE_JS": _template_text("salary.js"),
    }


def _exclusion_rollup(records: list[dict[str, object]]) -> dict[str, object]:
    by_city: dict[str, dict[str, int]] = {}
    by_exam: dict[str, dict[str, int]] = {}
    by_category: dict[str, dict[str, int]] = {}
    for record in records:
        exclusion = record.get("exclusion") or {}
        label = str(exclusion.get("category_label") or exclusion.get("category") or "定向岗位")
        for bucket, key in ((by_city, str(record["city"])), (by_exam, str(record["exam"])), (by_category, label)):
            item = bucket.setdefault(key, {"jobs": 0, "recruits": 0})
            item["jobs"] += 1
            item["recruits"] += int(record["recruits"])
    return {
        "jobs": len(records),
        "recruits": sum(int(record["recruits"]) for record in records),
        "by_city": by_city,
        "by_exam": by_exam,
        "by_category": by_category,
    }


def _adjust_city_summaries(
    summaries: list[dict[str, object]], excluded: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Subtract excluded rows from the source overview counts so可报口径 stays consistent."""
    per_city: dict[str, dict[str, int]] = {}
    for record in excluded:
        item = per_city.setdefault(str(record["city"]), {"jobs": 0, "recruits": 0})
        item["jobs"] += 1
        item["recruits"] += int(record["recruits"])
    adjusted: list[dict[str, object]] = []
    for summary in summaries:
        city = str(summary["city"])
        delta = per_city.get(city)
        if not delta:
            adjusted.append(summary)
            continue
        adjusted.append(
            {
                **summary,
                "jobs": int(summary["jobs"]) - delta["jobs"],
                "recruits": int(summary["recruits"]) - delta["recruits"],
            }
        )
    return adjusted


def build_jobs_dataset(model: DocumentModel) -> dict[str, object]:
    summaries = _jobs_city_summaries(model)
    records = extract_job_records(model)
    excluded_records = [record for record in records if record.get("exclusion")]
    active_records = [record for record in records if not record.get("exclusion")]
    active_summaries = _adjust_city_summaries(summaries, excluded_records)
    metrics = build_job_metrics(active_records, active_summaries)
    metrics["excluded"] = _exclusion_rollup(excluded_records)
    ranked = sorted(metrics["cities"], key=lambda item: (-int(item["jobs"]), str(item["city"])))
    rank_by_city = {str(item["city"]): index for index, item in enumerate(ranked, start=1)}
    cities = []
    for item in metrics["cities"]:
        jobs, recruits, city = int(item["jobs"]), int(item["recruits"]), str(item["city"])
        cities.append({**item, "rank": rank_by_city[city], "share": round(jobs / len(active_records) * 100, 1) if active_records else 0})
    excluded_lookup = {
        str(record["code"]): dict(record["exclusion"])  # type: ignore[arg-type]
        for record in excluded_records
    }
    return {
        "metrics": metrics,
        "cities": cities,
        "records": active_records,
        "all_records": records,
        "excluded_records": excluded_records,
        "excluded_lookup": excluded_lookup,
        "dashboard_records": [],
        "archive_blocks": model.blocks,
        "source_counts": {"paragraphs": model.paragraph_node_count, "tables": len(model.tables)},
    }


def build_salary_dataset(model: DocumentModel) -> dict[str, object]:
    series = extract_salary_series(model)
    return {"series": series, "stages": ["刚入职", "1年", "3年", "5年", "10年"], "cities": list(series["公务员"].keys()), "archive_blocks": model.blocks, "source_counts": {"paragraphs": model.paragraph_node_count, "tables": len(model.tables)}}


def _page_data(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def encode_json_script_payload(value: object) -> str:
    """Public v12 serializer; keeps JSON data inside an HTML script safely."""
    try:
        from .single_file_site import encode_json_script_payload as _encode
    except ImportError:
        from tools.anhui_web.single_file_site import encode_json_script_payload as _encode

    return _encode(value)


def render_cycle_payload_scripts(bundles: object) -> str:
    """Render the three cycle payload blocks used by the single-file site."""
    try:
        from .single_file_site import render_cycle_payload_scripts as _render
    except ImportError:
        from tools.anhui_web.single_file_site import render_cycle_payload_scripts as _render

    return _render(bundles)  # type: ignore[arg-type]


def extract_embedded_payload_for_test(html_text: str, cycle: str) -> dict[str, object]:
    try:
        from .single_file_site import extract_embedded_payload_for_test as _extract
    except ImportError:
        from tools.anhui_web.single_file_site import extract_embedded_payload_for_test as _extract

    return _extract(html_text, cycle)


def build_single_file_html(root: Path = ROOT) -> str:
    """Build the v12 three-cycle document in memory for tests and release."""
    try:
        from .single_file_site import build_single_file_html as _build
    except ImportError:
        from tools.anhui_web.single_file_site import build_single_file_html as _build

    return _build(root)


def _archive_sections(blocks: list[Block], kind: str, cities: Iterable[str]) -> list[tuple[str, list[Block]]]:
    """Split source blocks into navigable archive sections without changing text."""
    starts: list[tuple[int, str]] = []
    city_names = [
        (city.get("city", "") if isinstance(city, dict) else str(city))
        for city in cities
    ]
    if kind == "jobs":
        for index, block in enumerate(blocks):
            text = str(getattr(block, "text", "") or "").strip()
            for city in city_names:
                if text.startswith(f"{city}市") and ("岗" in text or "岗位" in text):
                    starts.append((index, f"{city}市"))
                    break
    else:
        for index, block in enumerate(blocks):
            text = str(getattr(block, "text", "") or "").strip()
            style = str(getattr(block, "style", "") or "").lower()
            if text and "heading 1" in style:
                starts.append((index, text))
    starts = sorted({index: label for index, label in starts}.items())
    if not starts:
        return [("完整源档案", list(blocks))]
    sections: list[tuple[str, list[Block]]] = []
    first_index = starts[0][0]
    if first_index:
        sections.append(("报告总览", list(blocks[:first_index])))
    for position, (index, label) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(blocks)
        sections.append((label, list(blocks[index:end])))
    return sections


def _exclusion_notice(dataset: dict[str, object]) -> str:
    excluded = dataset.get("excluded_records") or []
    lookup = dataset.get("excluded_lookup") or {}
    if not excluded:
        return ""
    by_city: dict[str, list[dict[str, object]]] = {}
    for record in excluded:
        by_city.setdefault(str(record["city"]), []).append(record)
    items: list[str] = []
    for city, records in by_city.items():
        codes = "、".join(str(record["code"]) for record in records)
        labels = sorted({str((record.get("exclusion") or {}).get("category_label", "定向岗位")) for record in records})
        items.append(
            f'<li><strong>{html.escape(city)}</strong><span>{html.escape("、".join(labels))}</span>'
            f'<small>{html.escape(codes)}</small></li>'
        )
    total_jobs = len(excluded)
    total_recruits = sum(int(record["recruits"]) for record in excluded)
    user_flagged = sum(1 for record in excluded if (record.get("exclusion") or {}).get("category") == "user_flagged")
    verify_note = ""
    if user_flagged:
        codes = "、".join(str(record["code"]) for record in excluded if (record.get("exclusion") or {}).get("category") == "user_flagged")
        verify_note = f'<p class="archive-exclusion-note__flag">其中 {codes} 由用户标记为四项目定向岗，外部职位库未显示定向备注，正式报名前请以官方岗位表为准。</p>'
    sources = sorted({str((record.get("exclusion") or {}).get("source") or "") for record in excluded} - {""})
    source_note = f'<p class="archive-exclusion-note__src">核验依据：华图职位库 2026（数据源：安徽人事考试网）等公开招聘职位表；共 {len(sources)} 个核验页。详见交付包《定向岗核查报告》。</p>'
    return (
        '<details class="archive-exclusion-note" id="job-exclusion-note">'
        f'<summary><strong>定向岗核除说明</strong><span>共核除 {total_jobs} 条 / {total_recruits} 人，可报口径已更新</span><i aria-hidden="true">⌄</i></summary>'
        '<div class="archive-exclusion-note__body">'
        '<p>以下岗位经逐条核验为身份定向招聘（“服务基层项目”人员即四项目：大学生村官、三支一扶、西部计划志愿者、特岗教师；以及退役士兵、随军家属等），报考人身份不符，已从可报口径与检索中剔除。原始行仍保留在下方案表中并标记，数字可回溯。</p>'
        '<ul>' + "".join(items) + '</ul>'
        + verify_note + source_note +
        '</div></details>'
    )


def _archive_shell(dataset: dict[str, object], kind: str, title: str, lead: str, count_label: str) -> str:
    """Render a compact archive index and collapsible source sections."""
    blocks = list(dataset["archive_blocks"])
    cities = dataset.get("cities", [])
    excluded_codes = dataset.get("excluded_lookup") if kind == "jobs" else None
    active_count = len(dataset.get("records") or [])
    excluded_count = len(dataset.get("excluded_records") or [])
    sections = _archive_sections(blocks, kind, cities)
    prefix = "jobs" if kind == "jobs" else "salary"
    back_view = "#jobs_search" if kind == "jobs" else "#salary_dashboard"
    index_links: list[str] = []
    details: list[str] = []
    for index, (label, section_blocks) in enumerate(sections):
        section_id = f"{prefix}-archive-section-{index + 1}"
        open_attr = " open" if index == 0 else ""
        expanded = "true" if index == 0 else "false"
        rendered = render_blocks(section_blocks, kind, excluded_codes=excluded_codes)
        index_links.append(
            f'<a href="#{section_id}" data-archive-index-link>{html.escape(label, quote=True)}<small>{len(section_blocks)} 节点</small></a>'
        )
        details.append(
            f'<details class="archive-section" id="{section_id}" data-archive-section{open_attr}>'
            f'<summary aria-expanded="{expanded}"><span class="archive-section__marker">{index + 1:02d}</span>'
            f'<strong>{html.escape(label, quote=True)}</strong><small>{len(section_blocks)} 个源节点</small><i aria-hidden="true">⌄</i></summary>'
            f'<div class="archive-section__body">{rendered}</div></details>'
        )
    if kind == "jobs":
        source_meta = (
            f'<strong>106 张源表</strong><span>源表全量 544 条岗位</span>'
            f'<span>可报 {active_count} 条 · 定向核除 {excluded_count} 条</span>'
        )
        notice = _exclusion_notice(dataset)
    else:
        source_meta = (
            f'<strong>{"106 张源表" if kind == "jobs" else "31 张源表"}</strong>'
            f'<span>{"544 条岗位" if kind == "jobs" else "228 个段落节点"}</span>'
            f'<span>{"156 个段落节点" if kind == "jobs" else "16 座城市"}</span>'
        )
        notice = ""
    return (
        f'<main class="product-main shell archive-main" id="main-content">'
        f'<section class="product-hero product-hero--compact"><div><p class="eyebrow">{count_label}</p>'
        f'<h1>{html.escape(title)}</h1><p class="hero-lead">{html.escape(lead)}</p></div>'
        f'<a class="quiet-link" href="{back_view}">{"去检索 →" if kind == "jobs" else "去观测台 →"}</a></section>'
        f'<div class="archive-meta">{source_meta}</div>'
        + notice +
        f'<section class="archive-index-shell" aria-label="档案导航">'
        f'<div class="archive-index-head"><div><span class="eyebrow">ARCHIVE INDEX</span><strong>先看目录，再打开原表</strong></div>'
        f'<div class="archive-index-tools"><label><span class="sr-only">搜索档案</span><input type="search" data-archive-search placeholder="搜索城市、章节或关键词" autocomplete="off"></label>'
        f'<button type="button" data-archive-toggle="all" aria-expanded="false">展开全部</button></div></div>'
        f'<nav class="archive-index" id="{prefix}-archive-index">{"".join(index_links)}</nav>'
        f'<p class="archive-search-status" data-archive-search-status role="status" aria-live="polite">显示全部 {len(sections)} 个档案分组</p>'
        f'</section><section class="archive-flow" id="{prefix}-archive">{"".join(details)}</section></main>'
    )


def _product_nav(active: str) -> str:
    links = [("jobs_dashboard", "岗位观测台", PRODUCT_PAGE_NAMES["jobs_dashboard"]), ("jobs_ranking", "岗位排名", PRODUCT_PAGE_NAMES["jobs_ranking"]), ("jobs_search", "岗位检索", PRODUCT_PAGE_NAMES["jobs_search"]), ("salary_dashboard", "待遇观测台", PRODUCT_PAGE_NAMES["salary_dashboard"]), ("salary_ranking", "待遇排名", PRODUCT_PAGE_NAMES["salary_ranking"])]
    nav = "".join(f'<a class="product-nav__link {"is-current" if key == active else ""}" href="{href}" {"aria-current=page" if key == active else ""}>{label}</a>' for key, label, href in links)
    return '<nav class="product-nav" aria-label="产品导航"><div class="product-nav__inner shell"><a class="product-brand" href="岗位观测台.html"><span class="product-brand__mark">皖</span><span><strong>皖域择岗档案</strong><small>数据洞察 · 科学择岗</small></span></a><div class="product-nav__links">' + nav + '</div><div class="product-nav__tools"><button type="button" data-action="theme">◐</button><button type="button" data-action="print">⌁</button></div></div></nav>'


def _product_context(active: str, title: str, content: str, data: object, script: str = "") -> dict[str, str]:
    shared_script = _template_text("product-shell.js")
    return {"PAGE_TITLE": html.escape(title, quote=True), "PAGE_DESCRIPTION": "安徽公考数据产品页，离线可用。", "ACTIVE_ROUTE": active, "COMMON_CSS": _template_text("common.css"), "PAGE_CSS": _template_text("product-shell.css") + _template_text("polish.css"), "PAGE_CONTENT": content, "PAGE_DATA": _page_data(data), "PAGE_JS": shared_script + "\n" + script, "PRODUCT_NAV": _product_nav(active)}


def _salary_small_multiples(salary: dict[str, object]) -> str:
    """16 市五年待遇轨迹小倍数阵列：每格一条折线，纵轴全省统一刻度。"""
    series = salary["series"]["公务员"]
    stages = salary["stages"]
    flat = [float(value or 0) for city_values in series.values() for value in city_values.values()]
    y0, y1 = min(flat), max(flat)
    median = sorted(float(values["3年"] or 0) for values in series.values())[len(series) // 2]
    width, height = 150.0, 52.0
    cards: list[str] = []
    for city, values in series.items():
        points = []
        for index, stage in enumerate(stages):
            value = float(values[stage] or 0)
            x = 6 + index * (width - 12) / (len(stages) - 1)
            y = height - 6 - (value - y0) / ((y1 - y0) or 1) * (height - 16)
            points.append((x, y))
        v3 = float(values["3年"] or 0)
        color = "#d9912c" if v3 >= median else "#2f5fca"
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.1" fill="{color}"/>' for x, y in points)
        cards.append(
            f'<button type="button" class="mini-city" data-master-select-city="{html.escape(city, quote=True)}" '
            f'title="{city}：刚入职 {float(values[stages[0]] or 0):.1f} 万 → 10年 {float(values[stages[-1]] or 0):.1f} 万，点击选中该市">'
            f'<span class="mini-city__name">{html.escape(city)}<b>{v3:.1f}</b></span>'
            f'<svg viewBox="0 0 {width:.0f} {height:.0f}" aria-hidden="true">'
            f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>{dots}</svg></button>'
        )
    return (
        '<section class="mini-multiples" id="salary-mini-multiples" aria-label="16市待遇轨迹一览">'
        '<header><div><p class="eyebrow">SMALL MULTIPLES</p><h2>16 市待遇轨迹一览</h2>'
        '<p>每格一条五年轨迹（刚入职 → 10 年），纵轴全省统一刻度；暖色 = 3 年待遇高于全省中位。点击格子选中该市。</p></div>'
        '<small class="chart-disclaimer">统一口径估算 · 非收入承诺</small></header>'
        '<div class="mini-multiples__grid">' + "".join(cards) + '</div></section>'
    )


def _master_overview_content(jobs: dict[str, object], salary: dict[str, object]) -> str:
    cities = jobs["cities"]
    default = next((item for item in cities if str(item["city"]) == "合肥"), cities[0])
    default_city = str(default["city"])
    default_salary = float(salary["series"]["公务员"][default_city]["3年"] or 0)
    options = "".join(f'<option value="{html.escape(str(item["city"]), quote=True)}">{html.escape(str(item["city"]))}市</option>' for item in cities)
    stages = salary["stages"]
    stage_buttons = "".join(f'<button type="button" data-master-stage="{html.escape(str(stage), quote=True)}" class="{"is-selected" if stage == "3年" else ""}">{html.escape(str(stage))}</button>' for stage in stages)
    return (
        '<main class="product-main shell master-main" id="main-content">'
        '<section class="master-hero"><div class="master-evidence-rail" aria-label="证据索引"><span>01 · SOURCE</span><i aria-hidden="true"></i><span>02 · METRIC</span><i aria-hidden="true"></i><span>03 · DECISION</span></div><div><p class="eyebrow">00 · ANHUI DECISION DESK</p>'
        '<h1>把岗位与待遇，放进同一张决策桌。</h1>'
        '<p class="hero-lead">从全省总览开始，选定条件、聚焦城市，再把机会、竞争与长期待遇放进同一个判断闭环。</p></div>'
        '<div class="master-hero__stamp"><span>ARCHIVE STATUS · OFFLINE</span><strong>2024—26</strong><small>3 个周期 · 16 座城市</small><em>数据边界公开 · 可回到原表复核</em></div></section>'
        '<section class="master-filterbar" id="master-filters" aria-label="全局筛选">'
        '<div class="master-filterbar__intro"><span class="eyebrow">GLOBAL FILTERS</span><strong>先定条件，再看城市</strong><small>这组条件会贯穿总览与两个地图视图</small></div>'
        '<label class="master-filter"><span>考试类别</span><select id="master-exam-filter"><option value="全部">全部类别</option><option value="省考">省考</option><option value="事业单位">事业单位</option><option value="国考">国考</option></select></label>'
        '<label class="master-filter"><span>身份类型</span><select id="master-type-filter"><option value="公务员">公务员</option><option value="事业编">事业编</option></select></label>'
        '<div class="master-filter master-filter--stage"><span>职业阶段</span><div class="master-stage-control" id="master-stage-filter">'+stage_buttons+'</div></div>'
        '<label class="master-filter"><span>聚焦城市</span><select id="master-city-select"><option value="">选择城市</option>'+options+'</select></label>'
        '<label class="master-filter master-filter--expect"><span>期望年薪下限 <b id="master-expect-out">不限</b></span><input id="master-expect" type="range" min="0" max="20" step="0.5" value="0" aria-label="期望年薪下限，万元"></label>'
        '<div class="master-filterbar__summary"><span>当前组合</span><strong id="master-filter-summary">全部类别 · 公务员 · 3年</strong><small id="master-expect-note">设定期望线后，矩阵中未达标城市会变暗</small></div></section>'
        '<section class="master-kpis" id="master-kpis" aria-label="当前条件摘要">'
'<div class="master-caliber" aria-label="数据口径切换"><span class="eyebrow">CALIBER</span><div class="master-stage-control" id="master-caliber-toggle"><button type="button" data-master-caliber="archive" class="is-selected">软件工程档案口径</button><button type="button" data-master-caliber="all">全岗位库口径</button><button type="button" data-master-caliber="major">按专业匹配</button></div><span id="master-major-wrap" hidden><input id="master-major-input" list="master-major-options" placeholder="输入或选择专业，如：会计学" aria-label="专业匹配口径的专业"></span><datalist id="master-major-options"></datalist></div>'
        '<div class="master-kpi master-kpi--jobs" title="来源：106 张源表逐行合计，身份定向岗已核除"><span>可报岗位</span><strong id="master-kpi-jobs">'+f'{int(jobs["metrics"]["totals"]["jobs"]):,}'+'</strong><small>岗 · 当前类别</small></div>'
        '<div class="master-kpi master-kpi--recruits" title="来源：逐市岗位表招录人数合计（可报口径）"><span>招录人数</span><strong id="master-kpi-recruits">'+f'{int(jobs["metrics"]["totals"]["recruits"]):,}'+'</strong><small>人 · 当前类别</small></div>'
        '<div class="master-kpi master-kpi--salary" title="来源：《安徽全省16市本科普通岗全包分析》统一口径估算中位数，非政策工资"><span>待遇参考</span><strong id="master-kpi-salary">'+f'{default_salary:.1f}'+'</strong><small>万元 / 年 · '+html.escape(default_city)+'公务员3年</small></div>'
        '<div class="master-kpi master-kpi--cities"><span>覆盖范围</span><strong>16</strong><small>座城市 · 统一口径</small></div></section>'
        '<section class="master-workbench" id="master-workbench" aria-labelledby="master-workbench-title">'
        '<header class="master-workbench__head"><div><p class="eyebrow">CITY LENS · V6</p><h2 id="master-workbench-title">城市机会 × 待遇坐标</h2><p>横轴看岗位选择面，纵轴看当前待遇参考；点选任一城市打开完整画像。</p></div>'
        '<div class="master-workbench__active"><span>ACTIVE CITY</span><strong id="master-selected-city">'+html.escape(default_city)+'市</strong><small id="master-selection-status">跟随上方条件同步</small></div></header>'
        '<div class="master-workbench__grid"><div class="master-matrix-card"><div class="master-matrix-card__head"><div><span>16 CITY FIELD</span><strong>机会与长期回报的相对位置</strong></div><small id="master-matrix-context">公务员 · 3年</small></div>'
        '<div class="master-matrix" id="master-matrix" role="group" aria-label="安徽16市机会与待遇矩阵"><div class="master-matrix__quadrant master-matrix__quadrant--tl">低机会 · 高待遇</div><div class="master-matrix__quadrant master-matrix__quadrant--br">高机会 · 低待遇</div><div class="master-matrix__axis master-matrix__axis--y"><span>待遇高</span><span>待遇低</span></div><div class="master-matrix__axis master-matrix__axis--x"><span>岗位规模低</span><span>岗位规模高</span></div><div class="master-matrix__gridlines" aria-hidden="true"></div><div id="master-matrix-points"></div></div>'
        '<p class="master-matrix-card__note">位置为城市聚合值的相对关系，不代表个人录用概率或收入承诺。</p></div>'
        '<aside class="master-profile" id="master-city-profile" aria-live="polite"><div class="master-profile__head"><div><span class="eyebrow">ACTIVE CITY PROFILE</span><h3 id="master-city-name">'+html.escape(default_city)+'市</h3><p id="master-city-meta">全部类别 · 公务员 · 3年</p></div><span class="master-profile__rank" id="master-profile-rank">机会 #'+f'{int(default["rank"]):02d}'+'</span></div>'
        '<p class="master-profile__summary" id="master-profile-summary">选择条件后，这里会把岗位机会和待遇参考合并成一句可读的判断。</p>'
        '<dl class="master-profile__metrics"><div><dt>岗位规模</dt><dd id="master-profile-jobs">'+f'{int(default["jobs"]):,}'+'</dd><small>当前类别</small></div><div><dt>招录人数</dt><dd id="master-profile-recruits">'+f'{int(default["recruits"]):,}'+'</dd><small>当前类别</small></div><div><dt>竞争比</dt><dd id="master-profile-ratio">'+_competition_display(default["ratio"])+'</dd><small>1:N 参考</small></div><div><dt>待遇参考</dt><dd id="master-profile-salary">'+f'{default_salary:.1f}'+'</dd><small>万元 / 年</small></div></dl>'
        '<div class="master-profile__score"><span>综合位置</span><strong id="master-profile-score">机会 × 待遇</strong><small id="master-profile-score-note">选择城市后生成相对位置</small></div>'
        '<div class="master-profile__actions"><button type="button" data-master-view="jobs_dashboard">看机会地图 <span>↗</span></button><button type="button" data-master-view="salary_dashboard">看待遇地图 <span>↗</span></button><button type="button" id="master-shortlist-toggle">加入城市短名单 <span>＋</span></button></div></aside></div></section>'
        + _salary_small_multiples(salary) +
        '<section class="master-shortlist-preview" id="master-shortlist-preview"><header><div><p class="eyebrow">SHORTLIST</p><h2>把决定留在这里</h2><p>暂存值得继续比较的城市，再进入岗位短名单。</p></div><div class="master-shortlist-preview__actions"><button type="button" data-master-view="shortlist">打开我的短名单 →</button><button type="button" class="primary-button primary-button--quiet" data-build-decision>生成决策单</button></div></header><div id="master-shortlist-preview-list"><div class="master-empty-state"><strong>还没有城市短名单</strong><span>点选城市画像里的“加入城市短名单”。</span></div></div></section>'
        '<section class="master-next-steps" aria-label="下一步"><article><span>01</span><div><strong>先定口径</strong><small>上方筛选贯穿整套工作台</small></div></article><article><span>02</span><div><strong>再看画像</strong><small>从双轴位置进入城市细节</small></div></article><article><span>03</span><div><strong>保留短名单</strong><small>最后再下钻到岗位原表</small></div></article></section></main>'
    )


def _master_shortlist_content(jobs: dict[str, object]) -> str:
    saved = _jobs_saved_content(jobs)
    saved_start = saved.find('<section class="saved-summary-strip"')
    saved_inner = saved[saved_start:-len('</main>')] if saved_start >= 0 else ''
    return (
        '<main class="product-main shell master-shortlist-main" id="main-content">'
        '<section class="product-hero product-hero--compact"><div><p class="eyebrow">04 · MY SHORTLIST</p><h1>我的短名单</h1><p class="hero-lead">把值得继续比较的城市和具体岗位放在一起，形成下一步行动清单。</p></div><button type="button" class="quiet-link master-back-button" data-master-view="overview">← 返回总览</button></section>'
        '<section class="master-city-board"><header><div><p class="eyebrow">CITY SHORTLIST</p><h2>城市选择</h2></div><button type="button" class="text-button" id="master-clear-shortlist">清空城市</button></header><p class="master-board-note" id="master-shortlist-status">城市短名单只保存在当前浏览器。</p><div id="master-city-shortlist-list"><div class="master-empty-state"><strong>还没有城市</strong><span>回到总览，点选城市后加入短名单。</span><button type="button" data-master-view="overview">去总览选择 →</button></div></div></section>'
        + saved_inner
        + '</main>'
    )


def _master_archive_content(jobs: dict[str, object], salary: dict[str, object]) -> str:
    jobs_archive = _jobs_archive_content(jobs)
    salary_archive = _salary_archive_content(salary)
    jobs_start = '<main class="product-main shell archive-main" id="main-content">'
    salary_start = '<main class="product-main shell archive-main" id="main-content">'
    jobs_part = jobs_archive.replace(jobs_start, '<section class="master-archive-part is-active" data-master-archive-part="jobs">', 1).replace('</main>', '</section>', 1)
    salary_part = salary_archive.replace(salary_start, '<section class="master-archive-part" data-master-archive-part="salary">', 1).replace('</main>', '</section>', 1)
    return (
        '<main class="product-main shell master-archive-main" id="main-content">'
        '<section class="product-hero product-hero--compact"><div><p class="eyebrow">05 · SOURCE ARCHIVE</p><h1>原始档案库</h1><p class="hero-lead">岗位与待遇的完整源文档都在这里；先用目录定位，再打开对应表格。</p></div><button type="button" class="quiet-link master-back-button" data-master-view="overview">← 返回总览</button></section>'
        '<div class="master-archive-tabs" role="tablist" aria-label="档案类型"><button type="button" class="is-selected" data-master-archive-tab="jobs" role="tab" aria-selected="true">岗位源档案 <small>106 张表</small></button><button type="button" data-master-archive-tab="salary" role="tab" aria-selected="false">待遇源档案 <small>31 张表</small></button></div>'
        '<div class="master-archive-parts">'+jobs_part+salary_part+'</div></main>'
    )


def _jobs_dashboard_content(dataset: dict[str, object]) -> str:
    totals, cities = dataset["metrics"]["totals"], dataset["cities"]
    chips = "".join(f'<button class="metric-chip {"is-selected" if key == "jobs" else ""}" data-metric="{key}" aria-pressed="{str(key == "jobs").lower()}"><strong>{label}</strong><small>{unit}</small></button>' for key, label, unit in (("jobs", "岗位数", "岗"), ("recruits", "招录人数", "人"), ("ratio", "竞争比", "1:N")))
    exams = "".join(f'<div class="stat-card"><span>{kind}</span><strong>{int(v["jobs"]):,}</strong><small>岗 · {int(v["recruits"]):,}人</small></div>' for kind, v in dataset["metrics"]["exam"].items())
    avg_jobs = sum(int(item["jobs"]) for item in cities) / max(len(cities), 1)
    avg_recruits = sum(int(item["recruits"]) for item in cities) / max(len(cities), 1)
    default = next((item for item in cities if str(item["city"]) == "合肥"), cities[0])
    decision_ranked = sorted(cities, key=lambda item: (-int(item["jobs"]), -int(item["recruits"]), str(item["city"])))
    decision_default = decision_ranked[0]
    decision_cards = "".join(
        f'<button type="button" class="decision-city-card" data-decision-city="{html.escape(str(item["city"]), quote=True)}" aria-label="查看{html.escape(str(item["city"]))}市决策详情">'
        f'<span class="decision-card__rank">{index:02d}</span><span class="decision-card__main"><strong>{html.escape(str(item["city"]))}市</strong>'
        f'<small>数据排序参考 · {int(item["jobs"]):,} 岗</small><span class="decision-card__bar"><i style="--decision-score:{int(int(item["jobs"]) / max(int(decision_default["jobs"]), 1) * 100)}%"></i></span>'
        f'<span class="decision-card__facts"><em>{int(item["jobs"]):,} 岗</em><em>{int(item["recruits"]):,} 人</em><em>{_competition_display(item.get("ratio", 0))}</em></span></span>'
        '<span class="decision-card__arrow" aria-hidden="true">→</span></button>'
        for index, item in enumerate(decision_ranked[:3], start=1)
    )
    decision = (
        '<section class="decision-cockpit" id="decision-cockpit" aria-labelledby="decision-title">'
        '<header class="decision-cockpit__header"><div><p class="eyebrow">DECISION DESK · V5</p><h2 id="decision-title">把偏好变成一张可解释的城市清单。</h2>'
        '<p>选择你更在意的因素，系统只用当前筛选下的城市聚合数据做排序参考。</p></div>'
        '<div class="decision-cockpit__meta"><span class="decision-live"><i aria-hidden="true"></i>本地计算</span><span id="decision-context">全部类别 · 16 座城市</span></div></header>'
        '<div class="decision-cockpit__grid"><aside class="decision-controls" aria-label="择岗偏好设置"><div class="decision-controls__head"><span>选择策略</span><small>PRESET</small></div>'
        '<div class="decision-presets" role="tablist" aria-label="择岗策略"><button type="button" class="decision-preset" data-decision-preset="steady" role="tab" aria-selected="false"><strong>稳妥</strong><small>低竞争优先</small></button>'
        '<button type="button" class="decision-preset is-selected" data-decision-preset="balanced" role="tab" aria-selected="true"><strong>平衡</strong><small>机会与竞争</small></button>'
        '<button type="button" class="decision-preset" data-decision-preset="opportunity" role="tab" aria-selected="false"><strong>机会优先</strong><small>岗位与招录</small></button></div>'
        '<div class="decision-controls__head decision-controls__head--weights"><span>调整权重</span><small><b id="decision-weight-total">100</b>% 自动归一化</small></div>'
        '<div class="decision-slider-list">'
        '<label class="decision-slider"><span><b>岗位规模</b><small>选择面更宽</small></span><output id="decision-opportunity-output" for="decision-opportunity">35</output><input id="decision-opportunity" type="range" min="0" max="100" value="35" data-decision-weight="opportunity" aria-label="岗位规模权重"></label>'
        '<label class="decision-slider"><span><b>招录人数</b><small>名额更集中</small></span><output id="decision-recruits-output" for="decision-recruits">35</output><input id="decision-recruits" type="range" min="0" max="100" value="35" data-decision-weight="recruits" aria-label="招录人数权重"></label>'
        '<label class="decision-slider"><span><b>低竞争</b><small>更关注 1:N</small></span><output id="decision-competition-output" for="decision-competition">30</output><input id="decision-competition" type="range" min="0" max="100" value="30" data-decision-weight="competition" aria-label="低竞争权重"></label></div>'
        '<p class="decision-disclaimer">排序只基于城市聚合值，不代表录用预测；切换考试类别后会重新计算。</p></aside>'
        '<div class="decision-results" aria-live="polite"><header class="decision-results__head"><div><p class="eyebrow">RECOMMENDATION</p><h3>先看这三座城市</h3></div><span class="decision-results__state" id="decision-strategy-label">平衡参考</span></header>'
        f'<div class="decision-lead"><div class="decision-lead__city"><span>01 · TOP MATCH</span><strong id="decision-top-city">{html.escape(str(decision_default["city"]))}</strong><small id="decision-top-score">综合得分待计算</small></div>'
        '<div class="decision-lead__reason"><span>为什么在前面</span><p id="decision-top-reason">正在根据当前岗位规模、招录人数和竞争口径计算。</p></div></div>'
        '<p class="decision-result-caption" id="decision-result-caption">按全部类别计算 · 三项权重自动归一化</p><div class="decision-list" id="decision-list">'+decision_cards+'</div></div></div>'
        '<footer class="decision-cockpit__footer"><span>下一步</span><strong>点选城市查看地图与原始岗位</strong><a href="#jobs_search">去检索岗位 →</a></footer></section>'
    )
    return (
        '<main class="product-main shell" id="main-content">'
        '<section class="product-hero"><div><p class="eyebrow">01 · JOBS OBSERVATORY</p><h1>岗位观测台</h1>'
        '<p class="hero-lead">把 16 座城市的岗位机会放在同一张可追问的地图上。切换指标，颜色、数值与排序一起变化。</p></div>'
        '<div class="hero-note"><span>数据更新</span><strong>2026 · 终稿</strong><small>省考 / 事业单位 / 国考</small></div></section>'
        '<section class="kpi-strip"><div title="来源：源文档 106 张逐市岗位表逐行合计；44 条身份定向岗已核除，详见报考手册·数据口径"><span>可报岗位</span><strong>'+f'{int(totals["jobs"]):,}'+'</strong><small>岗</small></div>'
        '<div title="来源：逐市岗位表招录人数合计（核除后可报口径）"><span>招录人数</span><strong>'+f'{int(totals["recruits"]):,}'+'</strong><small>人</small></div><div><span>覆盖城市</span><strong>16</strong><small>市</small></div>'
        '<div class="kpi-strip__hint"><span>交互提示</span><strong>点击城市查看档案</strong><small>地图与检查器同步更新</small></div></section>'
        '<section class="observatory-grid" id="jobs-observatory"><aside class="control-rail"><div class="rail-head"><span>观测指标</span><small>METRIC</small></div>'
        '<div class="metric-chips">'+chips+'</div><div class="rail-block"><span class="rail-label">考试类别</span><div class="filter-pills" id="exam-filter">'
        '<button class="is-selected" data-exam="全部">全部</button><button data-exam="省考">省考</button><button data-exam="事业单位">事业单位</button><button data-exam="国考">国考</button></div></div>'
        '<div class="rail-block"><span class="rail-label">当前选择</span><p class="rail-selection" id="jobs-selection">全省 · 全部类别</p><button class="text-button" id="reset-jobs">清除选择 ↺</button></div>'
        '<a class="rail-link" href="岗位排名对比.html">进入动态排名 <span>↗</span></a></aside>'
        '<figure class="map-panel"><div class="panel-heading"><div><span class="eyebrow">安徽省域</span><h2>16 市机会热力图</h2></div><div class="legend"><span>低</span><i></i><span>高</span></div></div>'
        '<div class="map-stage">'+_jobs_map_svg(cities)+'<div class="map-tooltip" id="jobs-map-tooltip" role="status" aria-live="polite">悬停或点选城市查看</div><span class="sr-only" id="map-toast" aria-live="polite">选择指标，地图会重新计算</span></div>'
        '<figcaption class="map-caption"><span id="map-caption">当前显示：岗位数</span><small>零值城市保留边界</small></figcaption></figure>'
        '<aside class="inspector" id="jobs-inspector" aria-live="polite"><button type="button" class="inspector-close" data-inspector-close aria-label="关闭城市详情">×</button><span class="inspector-kicker">CITY INSPECTOR</span><p>当前城市</p><h2 id="inspector-city">合肥市</h2>'
        '<div class="inspector-value"><strong id="inspector-value">'+f'{int(default["jobs"]):,}'+'</strong><span id="inspector-unit">岗</span></div>'
        '<dl><div><dt>全省排名</dt><dd id="inspector-rank">01 / 16</dd></div><div><dt>招录人数</dt><dd id="inspector-recruits">'+f'{int(default["recruits"]):,}'+' 人</dd></div>'
        '<div><dt>竞争比</dt><dd id="inspector-ratio">'+_competition_display(default["ratio"])+'</dd></div></dl><a id="inspector-link" href="岗位档案.html?city=合肥#city-合肥">查看合肥岗位档案 →</a><p class="inspector-note">显示为 1:N；原始口径为招录人数 ÷ 考试人数，逐岗缺失时回退报名人数。</p></aside></section>'
        '<section class="fact-strip" id="jobs-fact-strip" aria-label="当前选择事实"><header class="fact-strip__head"><div><p class="eyebrow">LIVE FACTS</p><h2>当前选择</h2></div><span id="jobs-fact-context">合肥 · 全部</span></header>'
        '<div class="fact-strip__grid"><div><span>城市</span><strong id="jobs-fact-city">合肥</strong></div><div><span>当前指标</span><strong id="jobs-fact-value">'+f'{int(default["jobs"]):,}'+'</strong><small id="jobs-fact-unit">岗位</small></div>'
        '<div><span>省均参考</span><strong id="jobs-fact-average">'+f'{avg_jobs:.1f}'+'</strong><small id="jobs-fact-average-unit">岗位</small></div><div class="fact-strip__note"><span>事实提示</span><strong id="jobs-fact-note">选中城市后可下钻到原表</strong></div></div></section>'
        + decision +
        '<section class="signal-row"><div><p class="eyebrow">EXAM MIX</p><h2>机会从哪里来</h2><p>考试类别的结构会改变选择路径。</p></div><div class="signal-cards">'+exams+'</div></section>'
        f'<section class="treemap-band" id="jobs-treemap" aria-label="招录名额城市树图"><header><div><p class="eyebrow">RECRUIT TREEMAP</p><h2>{int(sum(int(c["recruits"]) for c in cities)):,} 个名额都落在哪</h2><p>矩形面积 = 该市招录人数；悬停看具体值。</p></div><button type="button" class="text-button" data-export-svg=".jobs-treemap">存 PNG</button><small class="chart-disclaimer">相对规模参考</small></header>' + _jobs_treemap_svg(cities) + '</section>'
        + '<section class="next-cards"><a href="岗位排名对比.html"><span>02</span><strong>岗位排名对比</strong><small>看排名之外的差异 →</small></a><a href="岗位检索.html"><span>03</span><strong>岗位检索</strong><small>按代码与关键词定位 →</small></a><a href="待遇观测台.html"><span>↗</span><strong>待遇观测台</strong><small>切换到年度全包坐标 →</small></a></section></main>'
    )


def _jobs_ranking_content(dataset: dict[str, object]) -> str:
    major_by_city: dict[str, list[str]] = {}
    source_records = dataset.get("all_records") or dataset.get("records") or []
    if isinstance(source_records, list):
        for record in source_records:
            if not isinstance(record, dict):
                continue
            city = str(record.get("city") or "").strip()
            major = str(record.get("zy") or "").strip()
            if city and major:
                values = major_by_city.setdefault(city, [])
                if major not in values:
                    values.append(major)

    def major_summary(city: str) -> str:
        return html.escape("；".join(major_by_city.get(city, [])), quote=True)

    rows = []
    for rank, item in enumerate(sorted(dataset["cities"], key=lambda x: (-int(x["jobs"]), str(x["city"]))), 1):
        city, jobs, recruits = str(item["city"]), int(item["jobs"]), int(item["recruits"])
        ratio = float(item.get("ratio", 0) or 0)
        ratio_comparable = bool(item.get("ratio_comparable") or item.get("ratio_status") == "single_denominator")
        ratio_text = _competition_display(ratio) if ratio_comparable else "不可比"
        ratio_status = html.escape(str(item.get("ratio_status", "unavailable")), quote=True)
        rows.append(f'<tr data-ranking-row data-ranking-major="{major_summary(city)}" data-city="{city}" data-jobs="{jobs}" data-recruits="{recruits}" data-ratio="{ratio:.8f}" data-ratio-comparable="{str(ratio_comparable).lower()}" data-ratio-status="{ratio_status}"><td class="rank-cell">{rank:02d}</td><th scope="row"><button data-ranking-city="{city}">{city}市</button></th><td>{jobs:,}</td><td>{recruits:,}</td><td>{ratio_text}<sup class="data-source-mark" title="竞争比分母：{html.escape(str(item.get("competition_source", "")), quote=True)}；状态：{ratio_status}">{html.escape("≈" if "回退" in str(item.get("competition_source", "")) else "✓" if ratio_comparable and item.get("competition_source") == "考试人数" else "—")}</sup></td><td><span class="rank-bar"><i style="--bar:{jobs / 40 * 100:.1f}%"></i></span><small>{float(item["share"]):.1f}%</small></td><td><button class="compare-add" data-city-compare="{city}">+ 对比</button></td></tr>')
    return '<main class="product-main shell" id="main-content"><section class="product-hero product-hero--compact"><div><p class="eyebrow">02 · RANKING & COMPARE</p><h1>排名之外，看见机会构成</h1><p class="hero-lead">岗位数、招录人数与竞争比三种视角可随时切换；竞争比以 1:N 展示。</p></div><a class="quiet-link" href="岗位观测台.html">← 返回观测台</a></section><section class="ranking-toolbar"><div class="segmented" id="ranking-metric"><button class="is-selected" data-metric="jobs">岗位数</button><button data-metric="recruits">招录人数</button><button data-metric="ratio">竞争比</button></div><label class="ranking-major-picker" for="ranking-major-input"><span>专业</span><input id="ranking-major-input" type="search" list="ranking-major-options" autocomplete="off" placeholder="输入或选择专业" aria-describedby="ranking-filter-count"></label><datalist id="ranking-major-options"></datalist><span class="toolbar-note" id="ranking-note">按岗位数降序</span><span class="ranking-filter-count" id="ranking-filter-count">全部城市</span><button class="text-button" id="ranking-major-clear" type="button">清空专业</button><button class="text-button" id="clear-compare">清空对比</button></section><section class="ranking-layout"><div class="table-panel"><table class="product-table" id="jobs-ranking-table"><thead><tr><th>排名</th><th>城市</th><th>岗位数</th><th>招录人数</th><th>竞争比（1:N）</th><th>岗位占比</th><th>操作</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div><aside class="compare-dock" id="jobs-compare-dock"><div class="dock-head"><span>三城对比台</span><small id="compare-count">0 / 4</small></div><p id="compare-empty">从排名表选择城市，最多保留 4 个。</p><div class="compare-guide" id="jobs-compare-guide" aria-label="对比使用提示"><div><b>01</b><strong>选城市</strong><small>点击 + 对比</small></div><div><b>02</b><strong>看事实</strong><small>同步岗位 / 招录</small></div><div><b>03</b><strong>再检索</strong><small>进入逐岗筛选</small></div></div><div id="compare-cards"></div><a href="岗位检索.html" class="rail-link">去岗位检索 →</a></aside></section></main>'


def _jobs_search_content(dataset: dict[str, object]) -> str:
    rows = []
    all_records = dataset.get("all_records") or dataset["records"]
    for record in all_records:
        city = html.escape(str(record["city"]), quote=True)
        exam = html.escape(str(record["exam"]), quote=True)
        code = html.escape(str(record["code"]), quote=True)
        record_id = html.escape(str(record["record_id"]), quote=True)
        search_text = html.escape(" ".join(str(x) for x in record["raw_cells"]), quote=True)
        position = html.escape(str(record["unit_position"]), quote=True)
        natures = [dict(item) for item in (record.get("natures") or [])]
        nature_attr = html.escape(" ".join(str(item["key"]) for item in natures), quote=True)
        nature_chips = "".join(
            f'<span class="nature-chip" title="岗位性质：{html.escape(str(item["label"]), quote=True)}（点击顶部“性质”筛选同类）">{html.escape(str(item["label"]))}</span>'
            for item in natures
        )
        fields = record["fields"]
        def source_value(*names: str) -> str:
            for name in names:
                value = fields.get(name)
                if value not in (None, ""):
                    return html.escape(str(value), quote=True)
            return "—"
        registration = source_value("报名*")
        audit = source_value("审查合格*")
        effective = source_value("有效笔试/达线/规模参考", "有效笔试/达线")
        minimum = source_value("最低入围/线", "最低面试线")
        highest = source_value("最高笔试")
        exclusion = record.get("exclusion") or {}
        is_excluded = bool(exclusion)
        eligibility = record.get("eligibility") or {}
        tags = [str(tag) for tag in (eligibility.get("tags") or [])]
        tag_attr = html.escape(" ".join(tags), quote=True)
        row_class = ' class="job-row--excluded"' if is_excluded else ""
        badge = (
            f'<span class="job-excluded-tag" data-role="excluded-badge" title="{html.escape(str(exclusion.get("category_label", "")), quote=True)}">定向·不可报</span>'
            if is_excluded
            else ""
        )
        excluded_attr = ' data-excluded="1"' if is_excluded else ""
        rows.append(f'<tr{row_class} data-search="{search_text}" data-city="{city}" data-exam="{exam}" data-job-id="{record_id}" data-job-code="{code}" data-tags="{tag_attr}" data-natures="{nature_attr}"{excluded_attr}><td>{city}市</td><td>{exam}</td><td>{code}{badge}</td><th scope="row">{position}{nature_chips}</th><td>{record["recruits"]}{_row_ratio_chip(record)}</td><td>{registration}</td><td>{audit}</td><td>{effective}</td><td>{minimum}</td><td>{highest}</td><td><div class="search-actions"><button class="detail-open" type="button" data-job-detail="{record_id}" aria-label="查看{city}市 {code} 详情">详情</button><button class="compare-add" type="button" data-job-compare="{record_id}" aria-label="将{city}市 {code} 加入岗位对比">+ 加入对比</button><button class="save-add" type="button" data-job-save="{record_id}" aria-label="收藏{city}市 {code}">☆ 收藏</button></div></td></tr>')
    return '<main class="product-main shell" id="main-content"><section class="product-hero product-hero--compact"><div><p class="eyebrow">03 · POSITION SEARCH</p><h1>岗位检索</h1><p class="hero-lead">把源表里 ' + f'{len(dataset["records"]):,}' + ' 条可报岗位变成可定位、可比较的工作台；身份定向岗已在档案中单独标记。</p></div><a class="quiet-link" href="#jobs_score_sim">去分数模拟 →</a></section><section class="search-bar"><label>关键词<input id="job-search" type="search" placeholder="单位、职位、代码或专业关键词" autocomplete="off"></label><label>城市<select id="city-filter"><option value="">全部城市</option>'+''.join(f'<option value="{html.escape(str(item["city"]), quote=True)}">{html.escape(str(item["city"]))}</option>' for item in dataset["cities"])+'</select></label><label>考试类别<select id="exam-filter-search"><option value="">全部类别</option><option>省考</option><option>事业单位</option><option>国考</option></select></label><label>性质<select id="nature-filter"><option value="">全部性质</option>'+''.join(f'<option value="{html.escape(key, quote=True)}">{html.escape(label)}</option>' for key, label, _pattern in JOB_NATURE_RULES)+'</select></label><label>排序<select id="search-sort"><option value="default">默认（源表序）</option><option value="match">适配度</option><option value="recruits">招录人数</option><option value="ratio">竞争比（缓→紧）</option><option value="line">入围线（低→高）</option></select></label><button class="primary-button" id="reset-search" type="button">重置筛选</button><button class="primary-button primary-button--quiet" id="bulk-codes" type="button">批量代码</button><button class="primary-button primary-button--quiet" id="match-settings" type="button">⚙ 适配度</button></section><div class="tag-filter-row" id="tag-filter-row" role="group" aria-label="资格标签筛选"><span class="tag-filter-row__label">资格标签</span>' + ''.join(f'<button type="button" class="tag-chip" data-tag-filter="{html.escape(key, quote=True)}">{html.escape(label)}</button>' for key, label in ELIGIBILITY_TAG_LABELS.items()) + '<button type="button" class="tag-chip tag-chip--ghost" id="open-profile">⚙ 我的条件</button><button type="button" class="tag-chip tag-chip--ghost is-hidden" id="clear-bulk-codes">清除代码限定 ×</button></div><div class="search-meta"><strong id="search-count" role="status" aria-live="polite">' + f'{len(dataset["records"]):,}' + '</strong> 条岗位<span id="search-status" class="sr-only" role="status" aria-live="polite"></span><button class="compare-open-link" id="open-job-compare" type="button">查看对比 <small id="search-compare-count">0 / 6</small> →</button><span class="search-hint">可选 6 个进入对比 · / 搜索 · j/k 移动 · s 收藏 · c 对比</span></div><p class="empty-state" id="search-empty" hidden>未找到符合当前条件的岗位。请缩短关键词或清除筛选条件。</p><section class="table-panel table-panel--search"><table class="product-table" id="jobs-search-table"><thead><tr><th>城市</th><th>类别</th><th>代码</th><th>单位与职位</th><th>招录 / 竞争</th><th>报名</th><th>审核合格</th><th>有效笔试/达线</th><th>最低入围/线</th><th>最高笔试</th><th>操作</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></section></main>'


def _jobs_score_sim_content(dataset: dict[str, object]) -> str:
    """笔试分数模拟视图 v9：双科滑杆 + 波动概率 + 岗位级对照 + 方案保存。"""
    return (
        '<main class="product-main shell" id="main-content">'
        '<section class="product-hero product-hero--compact"><div><p class="eyebrow">04 · SCORE SIMULATOR</p><h1>分数模拟</h1>'
        '<p class="hero-lead">分科输入行测 / 申论（或职测 / 综应），按源表入围线给出“稳 / 达线 / 贴线 / 差分”清单；调高“发挥波动”还能看到每个岗位的进面概率估计。只做对照，不是进面预测。</p></div>'
        '<div class="hero-note"><span>口径</span><strong>源表入围线</strong><small>逐岗对照 · 本地计算</small></div></section>'
        '<section class="sim-controls" id="score-sim-controls" aria-label="分数模拟控制">'
        '<div class="sim-control"><span class="rail-label">考试类别</span><div class="segmented" id="sim-exam"><button class="is-selected" data-sim-exam="事业单位">事业单位</button><button data-sim-exam="省考">省考</button></div></div>'
        '<div class="sim-control"><span class="rail-label">范围 <small class="sim-scope-count"></small></span><select id="sim-city" aria-label="限定城市或全省"><option value="">全省（16 市）</option></select></div>'
        '<input id="sim-score" type="hidden" value="215" aria-hidden="true">'
        '<div class="sim-subjects">'
        '<div class="sim-sub"><span class="sim-sub__label">职测</span><input type="range" min="60" max="150" step="0.5" value="107.5" aria-label="第一科分数"><output>107.5</output></div>'
        '<div class="sim-sub"><span class="sim-sub__label">综应</span><input type="range" min="60" max="150" step="0.5" value="107.5" aria-label="第二科分数"><output>107.5</output></div>'
        '<div class="sim-sub sim-sub--composite"><span class="sim-sub__label">合成 <small class="sim-compose-label">职测 + 综应</small></span>'
        '<output id="sim-score-out" for="sim-score">215.0</output></div></div>'
        '<div class="sim-control sim-control--vol"><span class="rail-label">发挥波动 <output id="sim-vol-out" for="sim-vol">±0</output></span>'
        '<input id="sim-vol" type="range" min="0" max="10" step="0.5" value="0" aria-label="发挥波动幅度，用于概率估计"></div>'
        '<div class="sim-control sim-control--meta"><label><span>合成成绩直输</span><input id="sim-score-num" type="number" min="0" max="300" step="0.5" value="215"></label>'
        '<button class="text-button" id="sim-reset" type="button">重置 ↺</button></div>'
        '<div class="sim-control sim-control--schemes"><span class="rail-label">模拟方案</span>'
        '<div class="sim-scheme-bar"><input id="sim-scheme-name" type="text" placeholder="方案名，如：乐观 75" aria-label="方案名">'
        '<button class="text-button" id="sim-scheme-save" type="button">保存</button>'
        '<select id="sim-schemes" aria-label="已存模拟方案"><option value="">选择已存方案…</option></select>'
        '<button class="text-button" id="sim-scheme-delete" type="button">删除</button></div></div>'
        '<div class="sim-legend"><span>档位</span><b class="sim-band sim-band--safe">稳</b><b class="sim-band sim-band--hit">达线</b><b class="sim-band sim-band--near">贴线</b><b class="sim-band sim-band--miss">差分</b><small>稳＝高于入围线 5 分以上；贴线＝差 3 分以内</small></div>'
        '</section>'
        '<section class="sim-summary" id="sim-summary" aria-live="polite">'
        '<div><span>当前口径</span><strong id="sim-context">事业单位 · 215 分</strong></div>'
        '<div><span>稳</span><strong id="sim-count-safe">—</strong></div>'
        '<div><span>达线</span><strong id="sim-count-hit">—</strong></div>'
        '<div><span>贴线</span><strong id="sim-count-near">—</strong></div>'
        '<div><span>不可比 / 缺口</span><strong id="sim-count-noline">—</strong></div>'
        '<div><span>情景模拟均值</span><strong id="sim-prob">—</strong></div>'
        '<div><span>收藏稳档</span><strong id="sim-count-saved">—</strong></div></section>'
        '<section class="sim-jobbox" aria-label="岗位级对照">'
        '<header><p class="eyebrow">JOB-LEVEL LENS</p><h2>岗位级对照</h2></header>'
        '<div class="sim-jobbox__pick"><label><span>岗位代码（支持从收藏选择）</span>'
        '<select id="sim-job-select"><optgroup label="我的收藏" data-group="saved"><option value="">—</option></optgroup><optgroup label="全部岗位" data-group="all"><option value="">—</option></optgroup></select></label></div>'
        '<div class="sim-jobbox__readout" id="sim-job-readout"><p class="sim-jobbox__empty">输入或选择岗位代码后，这里给出该岗的逐点对照。</p></div></section>'
        '<section class="sim-board" aria-label="分数模拟结果">'
        '<header class="sim-board__head"><div><p class="eyebrow">RESULT LADDER</p><h2>按分差排列的岗位清单</h2></div>'
        '<small class="sim-board__hint">当前范围跟随顶部“范围”选择</small></header>'
        '<div class="sim-histwrap"><div class="sim-histogram" id="sim-histogram" role="img" aria-label="入围线分布直方图"></div></div>'
        '<div class="sim-list" id="sim-list"></div>'
        '<p class="empty-state" id="sim-empty" hidden>当前分数与城市下没有可对照的岗位，试试调整分数或切换类别。</p>'
        '<p class="sim-note">仅纳入已识别为同一量纲的入围线：事业编合成分按 300 分口径、省考合成分按 100 分口径。缺失、非正哨兵值和量纲不明的记录会明确排除；结果是正态波动下的情景模拟，不是官方录用概率或录用预测。</p>'
        '<p class="sim-quality-note" id="sim-quality-note" role="status" aria-live="polite">正在检查分数口径…</p>'
        '</section></main>'
    )


def _jobs_insight_content(jobs: dict[str, object], salary: dict[str, object]) -> str:
    """机会洞察：多人岗 / 竞争×待遇四象限 / 招录结构 / 城市梯队 / 考情速览。"""
    records = jobs.get("records") or []
    cities = jobs["cities"]
    series = salary["series"]
    multi = sorted(
        (record for record in records if int(record["recruits"]) >= 2),
        key=lambda record: (-int(record["recruits"]), str(record["code"])),
    )
    multi_recruits = sum(int(record["recruits"]) for record in multi)
    structure = _recruit_structure(records)
    total_recruits = sum(int(record["recruits"]) for record in records) or 1
    clusters = _city_clusters(cities, series)
    cluster_by_city = {city: cluster["label"] for cluster in clusters for city in cluster["cities"]}
    multi_rows = "".join(
        f'<tr data-recruits="{int(record["recruits"])}" data-city="{html.escape(str(record["city"]), quote=True)}" data-exam="{html.escape(str(record["exam"]), quote=True)}">'
        f'<td>{html.escape(str(record["city"]))}</td><td>{html.escape(str(record["exam"]))}</td><td class="num-cell">{html.escape(str(record["code"]))}</td>'
        f'<th scope="row">{html.escape(str(record["unit_position"]))}</th><td class="num-cell"><b>{int(record["recruits"])}</b></td>'
        f'<td>{html.escape(str(record["fields"].get("报名*") or "—"))}</td><td>{html.escape(str(record["fields"].get("有效笔试/达线/规模参考") or record["fields"].get("有效笔试/达线") or "—"))}</td>'
        f'<td>{html.escape(str(record["fields"].get("最低入围/线") or record["fields"].get("最低面试线") or "—"))}</td></tr>'
        for record in multi
    )
    structure_bars = "".join(
        f'<div class="structure-row"><span class="structure-label">{item["label"]}</span>'
        f'<span class="structure-bar"><i style="--w:{item["recruits"] / total_recruits * 100:.1f}%"></i></span>'
        f'<span class="structure-facts"><b>{item["jobs"]}</b> 岗 · <b>{item["recruits"]}</b> 人 · 占名额 {item["recruits"] / total_recruits * 100:.0f}%</span></div>'
        for item in structure
    )
    tier_cards = "".join(
        f'<button type="button" class="tier-card" data-tier-card="{html.escape(cluster["label"], quote=True)}" data-tiers="{" ".join(html.escape(city, quote=True) for city in cluster["cities"])}">'
        f'<span class="tier-card__label">{html.escape(str(cluster["label"]))}</span>'
        f'<strong>{html.escape(" · ".join(cluster["cities"]))}</strong>'
        f'<small>均值：公务员3年 {cluster["salary_mean"]:.1f} 万 · {cluster["jobs_mean"]:.0f} 岗/市</small></button>'
        for cluster in clusters
    )
    quick_rows = "".join(
        f'<tr data-tier="{html.escape(str(cluster_by_city.get(str(item["city"]), "—")), quote=True)}" data-city="{html.escape(str(item["city"]), quote=True)}">'
        f'<th scope="row">{html.escape(str(item["city"]))}</th><td class="num-cell">{int(item["jobs"]):,}</td><td class="num-cell">{int(item["recruits"]):,}</td>'
        f'<td>{_competition_display(item.get("ratio", 0))}</td><td class="num-cell">{float(series.get("公务员", {}).get(str(item["city"]), {}).get("3年") or 0):.1f}</td>'
        f'<td><span class="tier-tag">{html.escape(str(cluster_by_city.get(str(item["city"]), "—")))}</span></td></tr>'
        for item in sorted(cities, key=lambda row: -float(row.get("ratio", 0) or 0))
    )
    return (
        '<main class="product-main shell" id="main-content">'
        '<section class="product-hero product-hero--compact"><div><p class="eyebrow">05 · OPPORTUNITY INSIGHT</p><h1>机会洞察</h1>'
        '<p class="hero-lead">把容易错过的结构机会放在一页：多人岗、竞争 × 待遇四象限、招录结构与 16 市梯队。</p></div>'
        '<div class="hero-note"><span>视角</span><strong>结构参考</strong><small>相对比较 · 非录用预测</small></div></section>'
        '<section class="kpi-strip"><div><span>多人岗（≥2 人）</span><strong>' + f'{len(multi):,}' + '</strong><small>岗</small></div>'
        f'<div><span>多人岗名额</span><strong>{multi_recruits:,}</strong><small>人 · 占全部名额 {multi_recruits / total_recruits * 100:.0f}%</small></div>'
        f'<div><span>单 1 人岗</span><strong>{structure[0]["jobs"]:,}</strong><small>岗 · 名额占 {structure[0]["recruits"] / total_recruits * 100:.0f}%</small></div>'
        '<div class="kpi-strip__hint"><span>怎么用</span><strong>先挑多人岗</strong><small>容错空间更大</small></div></section>'
        '<section class="insight-section" id="insight-multi">'
        '<header class="insight-section__head"><div><p class="eyebrow">MULTI-SEAT JOBS</p><h2>多人岗清单（招 2 人及以上）</h2>'
        '<p>一次招多人 = 笔试失误的容错更高；结合入围线看“稳档”把握。</p></div>'
        '<div class="insight-tools"><div class="segmented" id="insight-multi-min" role="group" aria-label="最少招录人数">'
        '<button type="button" data-multi-min="2" class="is-selected">≥2 人</button><button type="button" data-multi-min="3">≥3 人</button><button type="button" data-multi-min="5">≥5 人</button></div>'
        '<label><span class="sr-only">城市</span><select id="insight-city"><option value="">全部城市</option>' + "".join(f'<option value="{html.escape(str(item["city"]), quote=True)}">{html.escape(str(item["city"]))}</option>' for item in cities) + '</select></label>'
        '<label><span class="sr-only">类别</span><select id="insight-exam"><option value="">全部类别</option><option>省考</option><option>事业单位</option></select></label>'
        '<button class="primary-button primary-button--quiet" id="insight-export" type="button">导出 CSV</button></div></header>'
        f'<p class="insight-count">当前显示 <strong id="insight-multi-count">{len(multi):,}</strong> 条</p>'
        f'<div class="table-panel"><table class="product-table" id="insight-multi-table"><thead><tr><th>城市</th><th>类别</th><th>代码</th><th>单位与职位</th><th>招录</th><th>报名</th><th>有效笔试/达线</th><th>最低入围/线</th></tr></thead><tbody>{multi_rows}</tbody></table></div>'
        '</section>'
        '<section class="insight-section" id="insight-quadrant">'
        '<header class="insight-section__head"><div><p class="eyebrow">COMPETITION × PAY QUADRANT</p><h2>竞争 × 待遇四象限</h2>'
        '<p>横轴竞争比（越右越缓）、纵轴公务员 3 年待遇；圆点大小 = 该市岗位数。左上角是“高待遇却没那么卷”的格子。</p></div>'
        '<small class="chart-disclaimer">城市聚合相对参考 · 非录用预测</small>'
        '<button type="button" class="text-button" data-export-svg=".quad-scatter">存 PNG</button></header>'
        + _quadrant_svg(cities, series) +
        '</section>'
        '<section class="insight-section" id="insight-structure">'
        '<header class="insight-section__head"><div><p class="eyebrow">RECRUIT STRUCTURE</p><h2>招录名额结构</h2>'
        '<p>全部可报名额里，多少人岗只招 1 人、多少来自多人岗。</p></div></header>'
        f'<div class="structure-bars">{structure_bars}</div>'
        '</section>'
        '<section class="insight-section" id="insight-tiers">'
        '<header class="insight-section__head"><div><p class="eyebrow">CITY TIERS</p><h2>16 市自动聚类</h2>'
        '<p>按岗位数、招录人数、竞争比与待遇做 k-means 聚类（k=3），只作相对参考。点击卡片可在下方速览表高亮同梯队城市。</p></div></header>'
        f'<div class="tier-cards">{tier_cards}</div>'
        '<div class="table-panel"><table class="product-table" id="insight-quick-table"><thead><tr><th>城市</th><th>岗位</th><th>招录</th><th>竞争比</th><th>公务员3年（万）</th><th>梯队</th></tr></thead><tbody>{quick_rows}</tbody></table></div>'.replace('{quick_rows}', quick_rows) +
        '</section></main>'
    )


CITY_NOTES: dict[str, str] = {
    "合肥": "岗位与名额常年全省最多，市直热门单位竞争最激烈；县域与开发区岗位往往是更缓的入口。",
    "芜湖": "第二梯队的名额规模，市区与县域分化明显，待遇位于全省前列。",
    "马鞍山": "名额少而稳定，人均待遇靠前，竞争比常年偏高，选岗要看清分母口径。",
    "铜陵": "小体量城市，本地考生黏性高；跨市报考宜盯住冷门单位与乡镇岗。",
    "安庆": "县域与乡镇岗位占比高，整体竞争相对温和，适合作为保底池。",
    "黄山": "名额处于全省最少量级，文旅口特色岗多，待遇中等。",
    "滁州": "名额稳定，毗邻南京；乡镇与执法类岗位占比较高。",
    "阜阳": "人口大市报名基数大，热门岗动辄数百人竞争，需用低竞争岗对冲。",
    "宿州": "县域名额多，竞争分层明显，乡镇岗是主要消化方向。",
    "六安": "名额较多，山区县岗位分散；部分岗位另设专业测试，报名前看清口径。",
    "蚌埠": "名额中游，市直热门岗集中，县域相对缓和。",
    "淮南": "资源型城市，应急管理与安全口岗位有特色，竞争中等。",
    "淮北": "小体量城市名额少，本地竞争集中，外市考生关注性价比。",
    "宣城": "名额中小，毗邻江浙；乡镇与综合管理岗占比高。",
    "池州": "全省名额最少量级，生态环境与文旅口特色明显。",
    "亳州": "名额中游偏多，中医药产业相关口有特色，县域竞争分层。",
}

_EXAM_CALENDAR = [
    ("公告发布", "2027-01 上旬", "省考公告 + 职位表 + 报考指南三件套同日发布，通读再选岗。"),
    ("网上报名", "2027-01 中下旬", "报名期约一周；关注报名人数动态，避免最后一日拥堵。"),
    ("缴费确认", "报名后 2–3 日内", "逾期未缴费视为放弃，缴费成功才算报名完成。"),
    ("打印准考证", "笔试前一周", "保存 PDF 备份，多打两份。"),
    ("笔试（省考）", "2027-03 中下旬", "行测 + 申论两科；合成口径见分数模拟视图。"),
    ("成绩公布", "2027-04 中旬", "同期公布入围名单与复审安排。"),
    ("资格复审 / 面试", "2027-05–06", "复审材料提前备齐；面试多为结构化。"),
    ("联考笔试（事业单位）", "2027-05 下旬", "职测 + 综应两科，与省考分数不可混用。"),
]

_MANUAL_FAQ = [
    ("“软件工程”能不能报“计算机类”？", "以官方专业目录为准：先在职位表的专业列找到大类名称，再对照招考公告附件的目录逐级核对。本档案的岗位表已是软件工程可报口径，但每年度公告的目录可能有微调，报名前务必再核一遍。"),
    ("竞争比 1:52 是不是没戏了？", "别慌：这个分母若来自报名人数，实际弃考率不低，更有参考意义的是“有效笔试/达线”人数。检索页行内的 1:N 徽标可点击手动修正分母；再结合入围线看分差，比只看比例靠谱。"),
    ("去年的入围线今年还能用吗？", "只能当参考区间。试题难度、招录人数、报名热度都会让线漂移；分数模拟里建议配合“发挥波动”看概率区间，而不是押一个整数。"),
    ("事业单位和省考可以同时报吗？", "时间不冲突通常可以兼报，但两者笔试科目不同（职测+综应 vs 行测+申论），满分口径也不同（300 vs 100），分数模拟里切换类别分别对照。"),
    ("应届身份怎么认定？", "以公告为准：一般含当年毕业与择业期内未落实编制内工作的毕业生；是否缴纳社保、三方协议状态都可能影响认定，拿不准就打招录单位电话。"),
    ("非全日制本科能报吗？", "看职位表的学历与学位列：注明“本科及以上”且未限制全日制的一般可报；标注“仅限全日制”的不可报。本档案只收录本科可报岗位，个别岗位另有学位要求，详见档案页原始行。"),
    ("多人岗就一定好进吗？", "招 2 人以上容错确实更高（机会洞察页有完整清单），但热门单位的大招岗反而会吸引更多报名者，仍要回到竞争比与入围线判断。"),
    ("最低服务年限 5 年意味着什么？", "服务期内一般不得借调、遴选、在职报考其他公务员岗位，部分岗位还有乡镇服务期约定；签约前把它当成“未来五年的定居决定”来考虑。"),
]


def _jobs_manual_content(jobs: dict[str, object] | None = None, salary: dict[str, object] | None = None) -> str:
    """报考手册：考试日历 / 名词百科 / 全流程时间线 / 雷区清单 / 16 市考情 / 误区 FAQ / 口径与快照。"""
    glossary_cards = "".join(
        f'<div class="manual-term" data-manual-term><dt>{html.escape(term)}</dt><dd>{html.escape(desc)}</dd></div>'
        for term, desc in GLOSSARY_TERMS
    )
    calendar_rows = "".join(
        f'<tr><th scope="row">{html.escape(stage)}</th><td>{html.escape(window)}</td><td>{html.escape(desc)}</td></tr>'
        for stage, window, desc in _EXAM_CALENDAR
    )
    countdown_bits = "".join(
        f'<div class="calendar-countdown__item"><span>距 {html.escape(label)}<small>预计 {date}</small></span><strong data-countdown-date="{date}">—</strong></div>'
        for label, date in (("2027 省考笔试", "2027-03-21"), ("2027 事业单位联考", "2027-05-22"))
    )
    city_note_cards = ""
    if jobs and salary:
        city_items = list(jobs.get("cities") or [])
        series = salary.get("series") or {}
        clusters = _city_clusters(city_items, series)
        tier_by_city = {city: cluster["label"] for cluster in clusters for city in cluster["cities"]}
        cards = []
        for item in sorted(city_items, key=lambda row: -int(row.get("recruits", 0) or 0)):
            city = str(item["city"])
            ratio = float(item.get("ratio", 0) or 0)
            salary3y = float(series.get("公务员", {}).get(city, {}).get("3年") or 0)
            cards.append(
                f'<article class="city-note-card" data-city="{html.escape(city, quote=True)}">'
                f'<header><h3>{html.escape(city)}市</h3><span class="tier-tag">{html.escape(str(tier_by_city.get(city, "—")))}</span></header>'
                f'<p>{html.escape(CITY_NOTES.get(city, "以岗位结构与竞争数据为主，结合个人城市偏好判断。"))}</p>'
                f'<dl><div><dt>岗位</dt><dd>{int(item.get("jobs", 0) or 0)}</dd></div>'
                f'<div><dt>招录</dt><dd>{int(item.get("recruits", 0) or 0)}</dd></div>'
                f'<div><dt>竞争</dt><dd>{_competition_display(ratio)}</dd></div>'
                f'<div><dt>公务员3年</dt><dd>{salary3y:.1f} 万</dd></div></dl></article>'
            )
        city_note_cards = f'<div class="city-note-grid">{"".join(cards)}</div>'
    faq_items = "".join(
        f'<details class="manual-faq__item"><summary>{html.escape(question)}</summary><p>{html.escape(answer)}</p></details>'
        for question, answer in _MANUAL_FAQ
    )
    steps = [
        ("查看公告与职位表", "确认招考公告、职位表、报考指南三份文件；以官方职位表为准核对专业目录。"),
        ("网上报名", "在报名期内提交职位与个人信息；关注报名人数动态，避免最后一日拥堵。"),
        ("资格初审", "招录单位 online 审核学历、专业与身份条件；未通过可在期限内改报。"),
        ("缴费确认", "逾期未缴费视为放弃；缴费成功才算报名完成。"),
        ("打印准考证", "留意打印时间窗，保存 PDF 备份。"),
        ("笔试", "省考＝行测+申论；事业单位联考＝职测+综应。合成口径见分数模拟视图。"),
        ("成绩与入围", "按比例确定入围名单；对照源表“最低入围/线”可预判分差。"),
        ("资格复审", "携带证书原件复核；此时最容易因材料口径被刷，提前准备。"),
        ("面试", "多为结构化面试；部分岗位另有专业测试，见资格标签“专业测试”。"),
        ("体检与考察", "参照公务员录用体检通用标准；考察含档案与政审。"),
        ("公示与录用", "公示期无异议后办理录用；注意最低服务年限约定。"),
    ]
    timeline = "".join(
        f'<li><span class="manual-step__index">{index:02d}</span><div><strong>{html.escape(title)}</strong><p>{html.escape(desc)}</p></div></li>'
        for index, (title, desc) in enumerate(steps, start=1)
    )
    pitfalls = [
        "专业名称口径：以毕业证 / 学位证上的专业全称为准，对照官方专业目录；大类与具体专业口径不同会直接影响审核。",
        "应届身份：择业期内是否算应届以公告为准；缴纳社保可能影响认定。",
        "证书时效：四六级、计算机、法律职业资格等需在报名或复审节点前取得。",
        "党员身份：需组织关系所在党组织出具证明，预备党员按公告口径认定。",
        "定向岗身份：四项目 / 退役士兵 / 随军家属定向岗需要相应服务证明或证件，普通考生不可报。",
        "最低服务年限：一般 5 年，期间不得借调 / 遴选 / 在职报考，签约前想清楚。",
        "诚信档案：放弃面试或录用可能计入诚信档案，影响后续报考。",
    ]
    pitfall_items = "".join(f'<li>{html.escape(item)}</li>' for item in pitfalls)
    return (
        '<main class="product-main shell" id="main-content">'
        '<section class="product-hero product-hero--compact"><div><p class="eyebrow">06 · CANDIDATE MANUAL</p><h1>报考手册</h1>'
        '<p class="hero-lead">考试日历、名词百科、全流程时间线、资格复审雷区、16 市考情与高频误区——把“为什么是这个数”讲清楚。</p></div></section>'
        '<section class="manual-section" id="manual-calendar">'
        '<header class="insight-section__head"><div><p class="eyebrow">EXAM CALENDAR</p><h2>考试日历（参考 2026 周期节奏）</h2><p>用于倒排备考计划的具体日期以官方公告为准；倒计时按预计窗口起点估算。</p></div></header>'
        f'<div class="calendar-countdown">{countdown_bits}<small class="calendar-countdown__note">倒计时为本机日期实时计算 · 日期为预计窗口起点</small></div>'
        f'<div class="table-panel"><table class="product-table manual-calendar-table"><thead><tr><th>阶段</th><th>预计窗口</th><th>要点</th></tr></thead><tbody>{calendar_rows}</tbody></table></div>'
        '</section>'
        '<section class="manual-section" id="manual-glossary">'
        '<header class="insight-section__head"><div><p class="eyebrow">GLOSSARY</p><h2>名词百科</h2></div>'
        '<label><span class="sr-only">搜索名词</span><input type="search" id="manual-search" placeholder="搜索名词或关键词" autocomplete="off"></label></header>'
        f'<dl class="manual-glossary">{glossary_cards}</dl>'
        '<p class="empty-state" id="manual-search-empty" hidden>没有匹配的名词，换个关键词试试。</p>'
        '</section>'
        '<section class="manual-section" id="manual-timeline">'
        '<header class="insight-section__head"><div><p class="eyebrow">TIMELINE</p><h2>报考全流程时间线</h2><p>从公告到录用的一般顺序；各年度具体日期以官方公告为准。</p></div></header>'
        f'<ol class="manual-timeline">{timeline}</ol>'
        '</section>'
        '<section class="manual-section manual-section--warn" id="manual-pitfalls">'
        '<header class="insight-section__head"><div><p class="eyebrow">CHECKLIST</p><h2>资格复审雷区清单</h2><p>每年都有人栽在这些口径上；报名前逐条自查。</p></div></header>'
        f'<ul class="manual-pitfalls">{pitfall_items}</ul>'
        '</section>'
        '<section class="manual-section" id="manual-city-cards">'
        '<header class="insight-section__head"><div><p class="eyebrow">CITY BRIEFINGS</p><h2>16 市考情速览</h2><p>按招录人数排序；数据来自源表汇总（岗位 / 招录 / 竞争比 / 公务员 3 年待遇），梯队为 k-means 自动聚类。</p></div></header>'
        + city_note_cards +
        '</section>'
        '<section class="manual-section" id="manual-faq">'
        '<header class="insight-section__head"><div><p class="eyebrow">FAQ · PITFALLS</p><h2>高频误区 FAQ</h2><p>选岗咨询里被问得最多的 8 个问题，点击展开。</p></div></header>'
        f'<div class="manual-faq">{faq_items}</div>'
        '</section>'
        '<section class="manual-section" id="manual-basis">'
        '<header class="insight-section__head"><div><p class="eyebrow">DATA BASIS</p><h2>数据口径与快照</h2></div></header>'
        '<div class="manual-basis-grid">'
        '<div><dt>数据快照</dt><dd>岗位 544 条 / 招录 825 人 · 待遇 16 市 × 2 身份 × 5 工龄 · 快照 2026-05 终稿，本页构建于 ' + DATA_SNAPSHOT + '（' + BUILD_VERSION + '）</dd></div>'
        '<div><dt>定向岗核除</dt><dd>44 条身份定向岗（四项目 26、退役士兵 15、随军家属 2、用户标记 1）已从可报口径剔除，依据为华图职位库与省直 + 16 市官方职位表逐条比对；档案页保留原始行并可回溯。</dd></div>'
        '<div><dt>竞争比口径</dt><dd>招录人数 ÷ 有效笔试人数，缺失回退报名人数；检索页行内 1:N 徽标可在报名期手动修正分母（只存本机）。</dd></div>'
        '<div><dt>待遇口径</dt><dd>年度全包估算中位数：应发工资 + 津补贴 + 公积金 + 年终等合计折算，非政策规定工资，不代表个人收入承诺。</dd></div>'
        '<div><dt>适配度评分</dt><dd>机会（招录）、低竞争（1:N）、待遇、城市偏好四项加权归一化；权重可在检索页「⚙ 适配度」调整，仅作排序参考。</dd></div>'
        '<div><dt>概率估计</dt><dd>分数模拟的进面概率 = 假设正态波动的蒙特卡洛抽样（默认 500 次），是统计参考而非预测。</dd></div>'
        '</div></section></main>'
    )


def _jobs_compare_content(dataset: dict[str, object]) -> str:
    return '<main class="product-main shell" id="main-content"><section class="product-hero product-hero--compact"><div><p class="eyebrow">04 · POSITION COMPARE</p><h1>岗位对比</h1><p class="hero-lead">把已选岗位放在同一张桌面上，只比较源表事实；每列里相对更优的数值会自动标绿（招录更高、竞争与入围线更低）。</p></div><a class="quiet-link" href="#jobs_search">← 返回岗位检索</a></section><section class="compare-summary-strip"><div><span>已选岗位</span><strong id="jobs-compare-count">0 / 6</strong><small>最多 6 条</small></div><div class="compare-summary-strip__note"><span>比较口径</span><strong>城市 · 类别 · 招录 · 报名 · 笔试</strong><small>字段直接取自源表</small></div></section><section class="compare-board" aria-live="polite"><header class="compare-board__head"><div><p class="eyebrow">SELECTED POSITIONS</p><h2>逐岗对比</h2></div><div class="compare-board__actions"><button id="copy-job-compare" type="button">复制摘要</button><button id="export-job-compare" type="button">导出 CSV</button><button id="clear-job-compare" type="button">清空</button></div></header><p id="jobs-compare-status" class="sr-only" role="status" aria-live="polite"></p><div id="jobs-compare-empty" class="compare-empty"><strong>还没有选中的岗位</strong><span>回到岗位检索，点击“加入对比”即可在这里并排查看。</span><a href="#jobs_search">返回岗位检索 →</a></div><div class="jobs-compare-list" id="jobs-compare-list"></div></section></main>'


def _jobs_saved_content(dataset: dict[str, object]) -> str:
    return ('<main class="product-main shell" id="main-content"><section class="product-hero product-hero--compact"><div><p class="eyebrow">05 · SAVED POSITIONS</p><h1>我的岗位</h1><p class="hero-lead">把暂时想再看的岗位收进一页：支持分组、私人笔记、结构体检与按模拟分的稳档标注，全部只保存在本机浏览器。</p></div>'
            '<button type="button" class="primary-button" data-build-decision>生成决策单</button></section>'
            '<section class="saved-summary-strip"><div><span>已收藏</span><strong id="saved-jobs-count">0</strong><small>条岗位</small></div>'
            '<div><span>收藏稳档</span><strong id="saved-sim-safe">—</strong><small>按当前模拟分</small></div>'
            '<div class="saved-summary-strip__note"><span>保存方式</span><strong>仅保存在当前浏览器</strong><small>不上传，不改变源数据</small></div></section>'
            '<section class="saved-audit" id="saved-audit" hidden><header><p class="eyebrow">RISK AUDIT</p><h2>收藏结构体检</h2></header><ul id="saved-audit-list"></ul></section>'
            '<section class="saved-board" aria-live="polite"><header class="saved-board__head"><div><p class="eyebrow">MY SHORTLIST</p><h2>稍后再看</h2></div><button id="clear-saved-jobs" class="text-button" type="button">清空收藏</button></header>'
            '<div class="saved-group-bar" id="saved-group-bar" role="group" aria-label="收藏分组筛选"></div>'
            '<p id="saved-jobs-status" class="sr-only" role="status" aria-live="polite"></p>'
            '<div id="saved-jobs-empty" class="saved-empty"><strong>还没有收藏岗位</strong><span>回到岗位检索，点击“☆ 收藏”即可在这里集中查看。</span><a href="#jobs_search">返回岗位检索 →</a></div><div id="saved-jobs-list" class="saved-jobs-list"></div></section>'
            '<section class="decision-sheet" id="decision-sheet" hidden aria-label="报考决策单"></section></main>')


def _jobs_archive_content(dataset: dict[str, object]) -> str:
    return _archive_shell(
        dataset,
        "jobs",
        "岗位档案",
        "保留源 Word 的全部段落、表格和城市顺序；先用目录定位城市，再打开原表。",
        "06 · SOURCE ARCHIVE",
    )


def _salary_dashboard_content(dataset: dict[str, object]) -> str:
    stages, cities = dataset["stages"], dataset["cities"]
    stage_buttons = "".join(f'<button data-stage="{stage}" class="{"is-selected" if stage == "3年" else ""}">{stage}</button>' for stage in stages)
    options = "".join(f'<option value="{city}">{city}市</option>' for city in cities)
    return '<main class="product-main shell" id="main-content"><section class="product-hero"><div><p class="eyebrow">01 · INCOME OBSERVATORY</p><h1>待遇观测台</h1><p class="hero-lead">切换身份与工龄，让地图追踪五个源表节点，城市检查器给出同口径差异。</p></div><div class="hero-note"><span>估算范围</span><strong>9.1–16.3 万元</strong><small>统一口径中位数 · 非政策承诺</small></div></section><section class="kpi-strip"><div><span>覆盖城市</span><strong>16</strong><small>市</small></div><div><span>身份类型</span><strong>2</strong><small>类</small></div><div><span>工龄节点</span><strong>5</strong><small>档</small></div><div class="kpi-strip__hint"><span>交互提示</span><strong>选身份与工龄</strong><small>所有城市颜色同步变化</small></div></section><section class="observatory-grid salary-grid"><aside class="control-rail"><div class="rail-head"><span>待遇口径</span><small>VIEW</small></div><div class="rail-block"><span class="rail-label">身份类型</span><div class="filter-pills" id="employment-type"><button class="is-selected" data-type="公务员">公务员</button><button data-type="事业编">事业编</button></div></div><div class="rail-block"><span class="rail-label">职业阶段</span><div class="stage-pills" id="career-stage">'+stage_buttons+'</div></div><div class="rail-block"><span class="rail-label">定位城市</span><select id="salary-city-search"><option value="">选择城市</option>'+options+'</select></div><a class="rail-link" href="待遇排名.html">查看五节点排名 →</a></aside><figure class="map-panel"><div class="panel-heading"><div><span class="eyebrow">ANHUI · 16 CITY LAYERS</span><h2>年度全包热力图</h2></div><div class="legend"><span>低</span><i></i><span>高</span></div></div><div class="map-stage">'+_salary_map_svg(dataset["series"])+'</div><figcaption class="map-caption"><span id="salary-caption">公务员 · 入职3年</span><small>单位：万元 / 年 · 估算中位数</small></figcaption></figure><aside class="inspector" aria-live="polite"><button type="button" class="inspector-close" data-inspector-close aria-label="关闭城市详情">×</button><span class="inspector-kicker">CITY INSPECTOR</span><p>当前城市</p><h2 id="salary-city">合肥市</h2><div class="inspector-value"><strong id="salary-value">16.3</strong><span>万元/年</span></div><dl><div><dt>全省排名</dt><dd id="salary-rank">01 / 16</dd></div><div><dt>省均差</dt><dd id="salary-delta">—</dd></div><div><dt>当前视图</dt><dd id="salary-stage">入职3年</dd></div></dl><a id="salary-dossier-link" href="待遇档案.html?city=合肥#salary-city-合肥">查看合肥待遇档案 →</a><p class="inspector-note">金额为统一口径估算中位数，不代表政策规定工资或个人收入承诺。</p></aside></section><section class="next-cards"><a href="待遇排名.html"><span>02</span><strong>待遇排名</strong><small>用五个节点观察城市轨迹 →</small></a><a href="待遇档案.html"><span>03</span><strong>待遇档案</strong><small>查看报告口径与逐市原表 →</small></a><a href="岗位观测台.html"><span>↗</span><strong>岗位观测台</strong><small>回到岗位机会地图 →</small></a></section></main>'


def _salary_dashboard_content_v3(dataset: dict[str, object]) -> str:
    content = _salary_dashboard_content(dataset)
    series = dataset["series"]
    cities = list(dataset["cities"])
    default_city = "合肥" if "合肥" in cities else cities[0]
    default_value = float(series["公务员"][default_city]["3年"] or 0)
    tooltip = '<div class="map-tooltip" id="salary-map-tooltip" role="status" aria-live="polite">悬停或点选城市查看</div>'
    content = content.replace('<div class="map-stage">', '<div class="map-stage">' + tooltip, 1)
    fact = (
        '<section class="fact-strip" id="salary-fact-strip" aria-label="当前选择事实"><header class="fact-strip__head"><div><p class="eyebrow">LIVE FACTS</p><h2>当前选择</h2></div><span id="salary-fact-context">公务员 · 入职3年</span></header>'
        '<div class="fact-strip__grid"><div><span>城市</span><strong id="salary-fact-city">'+html.escape(default_city)+'</strong></div><div><span>当前值</span><strong id="salary-fact-value">'+f'{default_value:.1f}'+'</strong><small>万元/年</small></div>'
        '<div><span>全省均值</span><strong id="salary-fact-average">—</strong><small>万元/年</small></div><div class="fact-strip__note"><span>口径提示</span><strong id="salary-fact-note">统一口径估算中位数</strong></div></div></section>'
    )
    return content.replace('<section class="next-cards">', fact + '<section class="next-cards">', 1)


def _jobs_ranking_content_v3(dataset: dict[str, object]) -> str:
    content = _jobs_ranking_content(dataset)
    summary = '<section class="compare-summary" id="jobs-compare-summary" aria-label="岗位对比事实"><header class="compare-summary__head"><div><span class="eyebrow">COMPARE BOARD</span><strong>城市事实速览</strong></div><small id="jobs-compare-summary-note">选择 1–4 个城市查看</small></header><div class="compare-bars" data-compare-bars id="jobs-compare-bars"><p class="compare-summary__empty">从排名表选择城市，查看同口径数据。</p></div></section>'
    return content.replace('<section class="ranking-layout">', summary + '<section class="ranking-layout">', 1)


def _salary_growth_scatter(dataset: dict[str, object], jobs_cities: list[dict[str, object]] | None = None) -> str:
    """入职3年 × 10年 待遇散点：看起点与增速的相对位置；气泡大小 = 该市岗位数。"""
    series = dataset["series"]["公务员"]
    jobs_by_city = {str(item["city"]): int(item["jobs"]) for item in (jobs_cities or [])}
    points = [(city, float(values["3年"] or 0), float(values["10年"] or 0)) for city, values in series.items()]
    if not points:
        return ""
    max_jobs = max(jobs_by_city.values(), default=0) or 1

    def radius_for(city: str) -> float:
        jobs = jobs_by_city.get(city, 0)
        return 4.0 + (jobs / max_jobs) ** 0.5 * 5.5 if jobs else 5.5

    xs = [p1 for _, p1, _ in points]
    width, height, pad = 720.0, 380.0, 48.0
    x0, x1 = min(xs) - 0.4, max(xs) + 0.4
    ys = [p2 for _, _, p2 in points]
    y0, y1 = min(ys) - 0.4, max(ys) + 0.4
    scale_x = (width - pad * 2) / (x1 - x0)
    scale_y = (height - pad * 2) / (y1 - y0)

    def ref_y_at(x: float) -> float:
        return height - pad - ((x * 1.6) - y0) * scale_y

    lx0 = pad
    lx1 = width - pad
    ly0 = max(pad, min(height - pad, ref_y_at(x0)))
    ly1 = max(pad, min(height - pad, ref_y_at(x1)))
    avg_x = pad + (sum(xs) / len(xs) - x0) * scale_x
    avg_y = height - pad - (sum(ys) / len(ys) - y0) * scale_y

    growth_values = sorted(yv - xv for _, xv, yv in points)
    median_growth = growth_values[len(growth_values) // 2]
    placed_boxes: list[tuple[float, float, float, float]] = []
    dots: list[str] = []
    labeled = 0
    for city, xv, yv in sorted(points, key=lambda item: (item[2], item[1])):
        cx = pad + (xv - x0) * scale_x
        cy = height - pad - (yv - y0) * scale_y
        growth = yv - xv
        fill = "#d9912c" if growth >= median_growth else "#2f5fca"
        label = f"{city} {yv:.1f}"
        label_w = 12 * (len(label) - 2) + 30
        side_right = cx < width - (label_w + 30)
        lx = cx + 10 if side_right else cx - 10
        anchor = "start" if side_right else "end"
        box_x0 = lx if side_right else lx - label_w
        box_x1 = lx + label_w if side_right else lx
        placed = None
        for dy in (4, -9, 17, -22, 30):
            by0 = cy + dy - 9
            by1 = cy + dy + 4
            ok = True
            for bx0, by0, bx1, by1 in placed_boxes:
                if not (box_x1 < bx0 or box_x0 > bx1 or by1 < by0 or by0 > by1):
                    ok = False
                    break
            if ok:
                placed = (cy + dy, (box_x0, by0, box_x1, by1))
                break
        title = f"{city}：3年 {xv:.1f} 万 · 10年 {yv:.1f} 万 · 增 {growth:.1f} 万"
        if placed is None:
            dots.append(
                f'<g class="growth-dot" data-city="{html.escape(city, quote=True)}">'
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius_for(city):.1f}" fill="{fill}" fill-opacity=".85" stroke="#fff" stroke-width="1.2">'
                f"<title>{html.escape(title)}</title></circle></g>"
            )
            continue
        label_y, box = placed
        placed_boxes.append(box)
        labeled += 1
        dots.append(
            f'<g class="growth-dot" data-city="{html.escape(city, quote=True)}">'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius_for(city):.1f}" fill="{fill}" fill-opacity=".85" stroke="#fff" stroke-width="1.2">'
            f"<title>{html.escape(title)}</title></circle>"
            f'<text x="{lx:.1f}" y="{label_y:.1f}" text-anchor="{anchor}" font-size="10.5" fill="#54637d">{html.escape(label)}</text></g>'
        )

    return (
        '<svg class="growth-scatter" viewBox="0 0 720 380" role="img" aria-label="入职3年与10年待遇散点图">'
        f'<line x1="{lx0:.1f}" y1="{ly0:.1f}" x2="{lx1:.1f}" y2="{ly1:.1f}" stroke="#b8cdf0" stroke-width="1.4" stroke-dasharray="6 4"></line>'
        f'<text x="{(lx0 + lx1) / 2:.0f}" y="{(ly0 + ly1) / 2 - 6:.0f}" text-anchor="middle" font-size="10.5" fill="#8a97ab">1.6× 参考增速线</text>'
        + "".join(dots)
        + f'<line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" stroke="#c9d9ee" stroke-width="1.2"></line>'
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height - pad}" stroke="#c9d9ee" stroke-width="1.2"></line>'
        f'<text x="{width / 2:.0f}" y="{height - 10}" text-anchor="middle" font-size="10.5" fill="#7a8aa0">入职 3 年（万元/年）→</text>'
        f'<text x="14" y="{height / 2:.0f}" text-anchor="middle" font-size="10.5" fill="#7a8aa0" transform="rotate(-90 14 {height / 2:.0f})">入职 10 年（万元/年）→</text>'
        f'<text x="{avg_x:.1f}" y="{height - pad + 14}" text-anchor="middle" font-size="10" fill="#9aa5b5">省均 {sum(xs) / len(xs):.1f}</text>'
        f'<circle cx="{avg_x:.1f}" cy="{avg_y:.1f}" r="3" fill="none" stroke="#d9912c" stroke-width="1.5"></circle>'
        "</svg>"
    )


def _salary_ranking_content_v3(dataset: dict[str, object], jobs: dict[str, object] | None = None) -> str:
    content = _salary_ranking_content(dataset)
    summary = '<section class="compare-summary" id="salary-compare-summary" aria-label="待遇对比事实"><header class="compare-summary__head"><div><span class="eyebrow">COMPARE BOARD</span><strong>城市五节点速览</strong></div><small id="salary-compare-summary-note">选择 1–4 个城市查看</small></header><div class="compare-bars" data-compare-bars id="salary-compare-bars"><p class="compare-summary__empty">从排名表选择城市，查看五个工龄节点。</p></div><div class="radar-card" id="salary-radar" aria-label="五工龄节点雷达对比"></div></section>'
    growth = (
        '<section class="growth-panel" id="salary-growth" aria-label="待遇性价比散点">'
        '<header class="growth-panel__head"><div><p class="eyebrow">GROWTH LENS</p><h2>起点与增速，放在同一张图里</h2></div>'
        '<small>圆点越高 10 年越高、越大岗位越多；点色越暖相对增速越快；数据为统一口径估算。</small>'
        '<button type="button" class="text-button" data-export-svg=".growth-scatter">存 PNG</button></header>'
        + _salary_growth_scatter(dataset, (jobs or {}).get("cities"))
        + '</section>'
    )
    return content.replace('<section class="ranking-layout">', summary + growth + '<section class="ranking-layout">', 1)


def _salary_ranking_content(dataset: dict[str, object]) -> str:
    series, stages = dataset["series"], dataset["stages"]
    cities = sorted(dataset["cities"], key=lambda city: -(series["公务员"][city]["3年"] or -1))
    row_parts = []
    for index, city in enumerate(cities, 1):
        values = []
        for stage in stages:
            value = series["公务员"][city][stage]
            values.append(f'<td data-stage-value="{stage}">{"—" if value is None else f"{value:.1f}"}</td>')
        row_parts.append(f'<tr data-salary-row data-city="{city}" data-current="{series["公务员"][city]["3年"] or 0}"><td class="rank-cell">{index:02d}</td><th scope="row"><button data-city="{city}">{city}市</button></th>{"".join(values)}<td><span class="sparkline"></span></td><td><button class="compare-add" data-salary-compare="{city}">+ 对比</button></td></tr>')
    rows = "".join(row_parts)
    buttons = "".join(f'<button data-stage="{stage}" class="{"is-selected" if stage == "3年" else ""}">{stage}</button>' for stage in stages)
    return '<main class="product-main shell" id="main-content"><section class="product-hero product-hero--compact"><div><p class="eyebrow">02 · INCOME RANKING</p><h1>待遇排名</h1><p class="hero-lead">城市排名只回答“谁高”，五个源表节点才回答“怎么走”。</p></div><a class="quiet-link" href="待遇观测台.html">← 返回观测台</a></section><section class="ranking-toolbar"><div class="segmented" id="salary-type"><button class="is-selected" data-type="公务员">公务员</button><button data-type="事业编">事业编</button></div><div class="segmented" id="salary-stage-pills">'+buttons+'</div><span class="toolbar-note" id="salary-ranking-note">公务员 · 入职3年</span></section><section class="ranking-layout"><div class="table-panel"><table class="product-table salary-ranking-table" id="salary-ranking-table"><thead><tr><th>排名</th><th>城市</th>'+''.join(f'<th>{stage}</th>' for stage in stages)+'<th>轨迹</th><th>操作</th></tr></thead><tbody>'+rows+'</tbody></table></div><aside class="compare-dock" id="salary-compare-dock"><div class="dock-head"><span>待遇对比台</span><small id="salary-compare-count">0 / 4</small></div><p id="salary-compare-empty">选择城市，比较身份与阶段。</p><div class="compare-guide" id="salary-compare-guide" aria-label="对比使用提示"><div><b>01</b><strong>选城市</strong><small>点击 + 对比</small></div><div><b>02</b><strong>看节点</strong><small>切换身份 / 工龄</small></div><div><b>03</b><strong>做判断</strong><small>保留估算口径</small></div></div><div id="salary-compare-cards"></div></aside></section></main>'


def _salary_archive_content(dataset: dict[str, object]) -> str:
    return _archive_shell(
        dataset,
        "salary",
        "待遇档案",
        "完整保留年度全包分析报告的口径、规则、城市档案与 31 张源表；按章节逐段打开。",
        "03 · SOURCE ARCHIVE",
    )


def _build_product_page(active: str, jobs: dict[str, object], salary: dict[str, object]) -> str:
    jobs_core = {"metrics": jobs["metrics"], "cities": jobs["cities"]}
    salary_core = {"series": salary["series"], "stages": salary["stages"], "cities": salary["cities"]}
    if active == "jobs_dashboard": content, data, script, title = _jobs_dashboard_content(jobs), {"kind": "jobs-dashboard", **jobs_core, "salary": salary_core}, "product-jobs.js", "岗位观测台｜皖域择岗档案"
    elif active == "jobs_ranking": content, data, script, title = _jobs_ranking_content_v3(jobs), {"kind": "jobs-ranking", **jobs_core}, "product-jobs-ranking.js", "岗位排名对比｜皖域择岗档案"
    elif active == "jobs_search": content, data, script, title = _jobs_search_content(jobs), {"kind": "jobs-search", "records": jobs.get("all_records") or jobs["records"], "active_count": len(jobs["records"])}, "product-jobs-search.js", "岗位检索｜皖域择岗档案"
    elif active == "jobs_archive": content, data, script, title = _jobs_archive_content(jobs), {"kind": "jobs-archive"}, "product-shell.js", "岗位档案｜皖域择岗档案"
    elif active == "salary_dashboard": content, data, script, title = _salary_dashboard_content_v3(salary), {"kind": "salary-dashboard", **salary_core, "jobs": jobs_core}, "product-salary.js", "待遇观测台｜皖域择岗档案"
    elif active == "salary_ranking": content, data, script, title = _salary_ranking_content_v3(salary), {"kind": "salary-ranking", **salary_core}, "product-salary-ranking.js", "待遇排名｜皖域择岗档案"
    else: content, data, script, title = _salary_archive_content(salary), {"kind": "salary-archive"}, "product-shell.js", "待遇档案｜皖域择岗档案"
    return assemble_page("product-shell.html", _product_context(active, title, content, data, _template_text(script)))


# ---------------------------------------------------------------- 全专业岗位库（v9.3 新增，加法不改旧）

try:
    from .eligibility_rules import parse_eligibility as _parse_eligibility_all
except ImportError:  # 兼容以脚本方式直接运行
    try:
        from eligibility_rules import parse_eligibility as _parse_eligibility_all  # type: ignore
    except ImportError:
        _parse_eligibility_all = None

_ALL_CACHE: dict[str, object] | None = None
_HUATU_DEDUP_STATS: dict[str, object] = {"kept": 0, "dropped": 0}
_ALL_XUELI_RANK = {"zhongzhuan": 1, "dazhuan": 2, "benke": 3, "shuoshi": 4, "boshi": 5}
_ALL_CS_MEMBERS = [
    "计算机科学与技术", "软件工程", "网络工程", "信息安全", "物联网工程",
    "数字媒体技术", "智能科学与技术", "空间信息与数字技术", "电子与计算机工程",
    "数据科学与大数据技术", "网络空间安全", "新媒体技术", "电影制作", "保密技术",
    "服务科学与工程", "虚拟现实技术", "区块链工程", "密码科学与技术",
]


def _all_majors_dataset(jobs_records: list | None = None) -> dict[str, object]:
    """加载官方省考全专业岗位并预打标；与软件工程 544 条口径互不影响。

    jobs_records：v9.2 档案 records（含报名/审查/入围线/入围人数），按职位代码 join
    到全专业库对应岗位；无档案数据的岗位留空并标注口径。
    """
    global _ALL_CACHE
    if _ALL_CACHE is not None:
        return _ALL_CACHE
    meta = {"total": 0, "recruits": 0, "directed": 0, "hukou": 0, "compJoined": 0,
            "cities": [], "categories": [], "csMembers": _ALL_CS_MEMBERS, "cats": [], "majors": []}
    payload: dict[str, object] = {"rows": [], "meta": meta, "map": []}
    if _parse_eligibility_all is not None and ALL_MAJORS_JSON.is_file():
        comp: dict[str, dict] = {}
        # v9.6：全量省考逐岗数据打底（相对面汇编官方达线名单/报名数据），
        # v9.7：官方逐岗报名/合格/缴费/分数线覆盖其上，档案条目（软件工程 544 岗，
        # 含审查合格/达线人数明细）再逐岗覆盖。
        if AHSK_SCORES_JSON.is_file():
            ahsk = json.loads(AHSK_SCORES_JSON.read_text(encoding="utf-8"))
            for p in ahsk.get("positions", []):
                comp[str(p["code"])] = {
                    "bm": p.get("bm"), "hg": None, "jf": None, "adv": None,
                    "line": p.get("line"), "top": p.get("top"),
                    "compBase": "", "compSrc": "省考成绩汇编",
                }
        if AHSK_OFFICIAL_JSON.is_file():
            off = json.loads(AHSK_OFFICIAL_JSON.read_text(encoding="utf-8"))
            for p in off.get("positions", []):
                slot = comp.setdefault(str(p["code"]), {
                    "bm": None, "hg": None, "jf": None, "adv": None,
                    "line": None, "top": None, "compBase": "", "compSrc": "",
                })
                for key in ("bm", "hg", "jf", "line"):
                    if p.get(key) is not None:
                        slot[key] = p[key]
                if slot.get("line") is not None and not slot.get("compSrc"):
                    slot["compSrc"] = "省考官方分数线"
        for rec in (jobs_records or []):
            f = rec.get("fields") or {}
            code = str(rec.get("code") or f.get("代码") or "")
            if code:
                slot = comp.setdefault(code, {
                    "bm": None, "hg": None, "jf": None, "adv": None,
                    "line": None, "top": None, "compBase": "", "compSrc": "",
                })
                for key, val in (
                    ("bm", _num_or(f.get("报名*"))),
                    ("hg", _num_or(f.get("审查合格*"))),
                    ("adv", _num_or(f.get("有效笔试/达线") or f.get("有效笔试/达线/规模参考"))),
                    ("line", _num_or(f.get("最低入围/线"))),
                    ("top", _num_or(f.get("最高笔试"))),
                ):
                    if val is not None:
                        slot[key] = val
                if rec.get("competition_base"):
                    slot["compBase"] = rec["competition_base"]
                if rec.get("competition_source"):
                    slot["compSrc"] = rec["competition_source"]
        raw = json.loads(ALL_MAJORS_JSON.read_text(encoding="utf-8"))["positions"]
        rows = []
        major_universe: set[str] = set()
        joined = 0
        for p in raw:
            result = _parse_eligibility_all(p)
            xueli = result["xueli_parsed"]
            directed = result["directed"]
            for item in re.split(r"[、，,；;/\s]+", p["zhuanye"]):
                item = re.sub(r"^(?:本科|研究生|硕士|博士)：", "", item.strip()).replace("专业", "")
                if item and item not in ("不限", "专业不限") and not item.endswith(("类", "门类")) and "：" not in item:
                    major_universe.add(item)
            c = comp.get(p["code"])
            if c and (c.get("bm") is not None or c.get("line") is not None):
                joined += 1
            rows.append({
                "code": p["code"], "city": p["city"], "reg": p.get("region", ""),
                "unit": p["unit"], "xz": p.get("jigou_xingzhi", ""),
                "cc": p.get("jigou_cengci", ""), "lb": p.get("zhiwei_leibie", ""),
                "zw": p["zhiwei"], "zj": p.get("zhiji_cengci", ""), "num": p["recruits"],
                "zy": p["zhuanye"], "xl": p["xueli"], "xw": p.get("xuewei", ""),
                "age": p.get("age", ""), "jl": p.get("jingli", ""), "qt": p.get("qita", ""),
                "sl": p.get("shenlun", ""), "km": p.get("zhuanyekemu", ""),
                "bz": p.get("beizhu", ""), "dh": p.get("dianhua", ""),
                "tags": result["tags"],
                "dir": directed["category"] if directed else "",
                "dirText": directed["context"] if directed else "",
                "hukou": bool(result["hukou_local"]),
                "floor": _ALL_XUELI_RANK.get(xueli["floor"]),
                "only": xueli["only"], "unlim": result["majors_parsed"]["unlimited"],
                "exam": "省考", "source_note": "官方职位表",
                "bm": c.get("bm") if c else None, "hg": c.get("hg") if c else None,
                "jf": c.get("jf") if c else None, "hq": None, "ht": None,
                "adv": c.get("adv") if c else None, "line": c.get("line") if c else None,
                "top": c.get("top") if c else None,
            })
        # 事业编（滁州市直全专业 + 档案口径 135）与国考（档案口径 3）并入
        for p in _parse_chuzhou_syb():
            synth = {"qita": p["qt"], "jingli": p["jl"], "beizhu": p["bz"], "zhengzhi": "",
                     "xingbie": "", "zhiwei": p["zw"], "unit": p["unit"],
                     "xueli": p["xl"], "zhuanye": p["zy"]}
            result = _parse_eligibility_all(synth)
            xueli = result["xueli_parsed"]
            directed = result["directed"]
            for item in re.split(r"[、，,；;/\s]+", p["zy"]):
                item = re.sub(r"^(?:本科|研究生|硕士|博士)：", "", item.strip()).replace("专业", "")
                if item and item not in ("不限", "专业不限") and not item.endswith(("类", "门类")) and "：" not in item:
                    major_universe.add(item)
            rows.append({**p,
                "tags": result["tags"],
                "dir": directed["category"] if directed else "",
                "dirText": directed["context"] if directed else "",
                "hukou": bool(result["hukou_local"]),
                "floor": _ALL_XUELI_RANK.get(xueli["floor"]),
                "only": xueli["only"], "unlim": result["majors_parsed"]["unlimited"],
                "bm": None, "hg": None, "jf": None, "adv": None, "line": None, "top": None})
        # v9.7：2026 国考安徽全量职位（551 岗）并入，进面人数/最低进面分逐岗内嵌
        guokao_codes: set[str] = set()
        if GUOKAO_JSON.is_file():
            gk = json.loads(GUOKAO_JSON.read_text(encoding="utf-8"))
            for p in gk.get("positions", []):
                guokao_codes.add(str(p["code"]))
                synth = {"qita": p.get("qt", ""), "jingli": p.get("jl", ""),
                         "beizhu": p.get("bz", ""), "official_remark": p.get("official_remark", ""), "zhengzhi": "",
                         "xingbie": "", "zhiwei": p.get("zw", ""),
                         "unit": p.get("unit", ""), "xueli": p.get("xl", ""),
                         "zhuanye": p.get("zy", "")}
                result = _parse_eligibility_all(synth)
                xueli = result["xueli_parsed"]
                directed = result["directed"]
                zy_text = p.get("zy", "")
                for item in re.split(r"[、，,；;/\s]+", zy_text):
                    item = re.sub(r"^(?:本科|研究生|硕士|博士)：", "", item.strip()).replace("专业", "")
                    if item and item not in ("不限", "专业不限") and not item.endswith(("类", "门类")) and "：" not in item:
                        major_universe.add(item)
                c = comp.get(str(p["code"])) or {}
                rows.append({
                    "code": p["code"], "city": p.get("city", ""), "reg": p.get("reg", ""),
                    "unit": p.get("unit", ""), "xz": p.get("xz", ""), "cc": p.get("cc", ""),
                    "lb": p.get("lb", ""), "zw": p.get("zw", ""), "zj": "",
                    "num": p.get("num", 0), "zy": zy_text, "xl": p.get("xl", ""),
                    "xw": p.get("xw", ""), "age": "", "jl": p.get("jl", ""),
                    "qt": p.get("qt", ""), "sl": "", "km": "", "bz": p.get("bz", ""),
                    "officialRemark": p.get("official_remark", ""),
                    "dh": p.get("dh", ""),
                    "tags": result["tags"],
                    "dir": directed["category"] if directed else "",
                    "dirText": directed["context"] if directed else "",
                    "hukou": bool(result["hukou_local"]),
                    "floor": _ALL_XUELI_RANK.get(xueli["floor"]),
                    "only": xueli["only"], "unlim": result["majors_parsed"]["unlimited"],
                    "exam": "国考", "source_note": f"{CYCLE}国考职位表（安徽）",
                    # 报名/过审以国考排名汇编为准，缺失时回退档案口径；进面人数/线以进面名单为准
                    "bm": p.get("bm") if p.get("bm") is not None else c.get("bm"),
                    "hg": p.get("hg") if p.get("hg") is not None else c.get("hg"),
                    "jf": c.get("jf"),
                    "adv": p.get("adv"), "line": p.get("line"), "top": c.get("top"),
                })
        rows.extend(_archive_extra_rows(jobs_records or [], skip_codes=guokao_codes))
        # 华图职位库快照（2026 上/下半年事业编联考全专业全量）并入；与档案口径去重
        for p in _huatu_syb_rows(jobs_records or []):
            synth = {"qita": "", "jingli": "", "beizhu": "", "zhengzhi": "",
                     "xingbie": "", "zhiwei": p["zw"], "unit": p["unit"],
                     "xueli": p["xl"], "zhuanye": p["zy"]}
            result = _parse_eligibility_all(synth)
            xueli = result["xueli_parsed"]
            directed = result["directed"]
            for item in re.split(r"[、，,；;/\s]+", p["zy"]):
                item = re.sub(r"^(?:本科|研究生|硕士|博士)：", "", item.strip()).replace("专业", "")
                if item and item not in ("不限", "专业不限") and not item.endswith(("类", "门类")) and "：" not in item:
                    major_universe.add(item)
            rows.append({**p,
                "tags": result["tags"],
                "dir": directed["category"] if directed else "",
                "dirText": directed["context"] if directed else "",
                "hukou": bool(result["hukou_local"]),
                "floor": _ALL_XUELI_RANK.get(xueli["floor"]),
                "only": xueli["only"], "unlim": result["majors_parsed"]["unlimited"],
                "adv": None, "line": None, "top": None})
        # v9.7：官方达线名单逐岗汇总（省直 + 16 市）覆盖达线人数与最高分
        dz_map: dict[str, dict] = {}
        for dz_path in (AHSK_DAXIAN_ALL_JSON, AHSK_DAXIAN_SZ_JSON, AHSK_DAXIAN_FULL_JSON):
            if dz_path.is_file():
                dz = json.loads(dz_path.read_text(encoding="utf-8"))
                for p in dz.get("positions", []):
                    dz_map[str(p["code"])] = p
            for r in rows:
                # These attachments are province-exam lists without an exam
                # or city column. Restrict the join to the province rows;
                # cross-exam code collisions must remain unbound.
                d = dz_map.get(str(r["code"])) if r.get("exam") == "省考" else None
                if d:
                    r["adv"] = d.get("adv")
                    r["top"] = d.get("top")
                    if r.get("line") is None:
                        r["line"] = d.get("lo")
        if SYB_BGT_JSON.is_file():
            bgt = json.loads(SYB_BGT_JSON.read_text(encoding="utf-8"))
            bgt_map = {str(p["code"]): p for p in bgt.get("positions", [])}
            for r in rows:
                d = bgt_map.get(str(r["code"])) if r.get("exam") == "事业编" else None
                if d:
                    r["adv"] = d.get("adv")
                    r["top"] = d.get("top")
                    if r.get("line") is None:
                        r["line"] = d.get("lo")
        # v9.7.2：上半年事业编联考各单位复审·成绩名单（仅补缺，不覆盖档案口径）
        # v9.9.2：周期包成绩行带批次键，按（批次,代码）精确 join，防上/下半年同码串批次
        if SYB_FUGAO_JSON.is_file():
            fg = json.loads(SYB_FUGAO_JSON.read_text(encoding="utf-8"))
            fg_map: dict[tuple, list[dict]] = {}
            fg_plain: dict[str, list[dict]] = {}
            fg_has_cycle = False
            for p in fg.get("positions", []):
                cyc = str(p.get("cycle") or "")
                if cyc:
                    fg_has_cycle = True
                    fg_map.setdefault((cyc, str(p["code"])), []).append(p)
                else:
                    fg_plain.setdefault(str(p["code"]), []).append(p)
            row_code_counts: dict[str, int] = {}
            for candidate in rows:
                if candidate.get("exam") == "事业编":
                    code = str(candidate["code"])
                    row_code_counts[code] = row_code_counts.get(code, 0) + 1
            for r in rows:
                if r["exam"] != "事业编":
                    continue
                candidates = (fg_map.get((str(r.get("cycle") or ""), str(r["code"])), [])
                              if fg_has_cycle else fg_plain.get(str(r["code"]), []))
                # A score attachment without city cannot safely populate a
                # repeated code across cities, even if the source row itself
                # is unique. Leave that row as unknown instead of guessing.
                d = candidates[0] if len(candidates) == 1 and row_code_counts.get(str(r["code"]), 0) == 1 else None
                if d:
                    if r.get("adv") is None:
                        r["adv"] = d.get("adv")
                    if r.get("top") is None:
                        r["top"] = d.get("top")
                    if r.get("line") is None:
                        r["line"] = d.get("line")
        # v9.7.3：拟录用名单 × 面试总成绩 → 逐岗录用者参考成绩（省考）
        if AHSK_HIRE_JSON.is_file():
            hj = json.loads(AHSK_HIRE_JSON.read_text(encoding="utf-8"))
            hire_map: dict[str, list] = {}
            for p in hj.get("positions", []):
                hire_map.setdefault(str(p["code"]), []).append(p)
            for r in rows:
                hs_list = hire_map.get(str(r["code"])) if r.get("exam") == "省考" else None
                if hs_list:
                    vals_hs = [p["hs"] for p in hs_list if p.get("hs") is not None]
                    vals_ht = [p["ht"] for p in hs_list if p.get("ht") is not None]
                    r["hq"] = min(vals_hs) if vals_hs else None
                    r["ht"] = min(vals_ht) if vals_ht else None
        # Add deterministic IDs and explicit quality states only after all
        # source joins are complete; the raw source values above remain intact.
        rows = [annotate_position_row(CYCLE, row) for row in rows]
        cats = sorted({i for r in rows for i in re.split(r"[、，,；;/\s]+", r["zy"]) if i.endswith(("类", "门类"))})
        geo = json.loads(ANHUI_GEOJSON.read_text(encoding="utf-8"))
        features = [
            {"name": f["properties"]["name"].replace("市", ""),
             "cx": f["properties"]["centroid"][0], "cy": f["properties"]["centroid"][1],
             "polys": _geometry_polygons(f["geometry"])}
            for f in geo["features"]
        ]
        meta = {
            "total": len(rows),
            "recruits": sum(r["num"] for r in rows),
            "directed": sum(1 for r in rows if r["dir"]),
            "hukou": sum(1 for r in rows if r["hukou"]),
            "compJoined": joined,
            "cycle": _cycle_label(),
            "scoreCoverage": {
                "bm": sum(1 for r in rows if r.get("bm") is not None),
                "hg": sum(1 for r in rows if r.get("hg") is not None),
                "jf": sum(1 for r in rows if r.get("jf") is not None),
                "adv": sum(1 for r in rows if r.get("adv") is not None),
                "line": sum(1 for r in rows if r.get("line") is not None),
                "top": sum(1 for r in rows if r.get("top") is not None),
                "hire": sum(1 for r in rows if r.get("hq") is not None),
                "perExam": {
                    ex: {
                        "total": sum(1 for r in rows if r["exam"] == ex),
                        "bm": sum(1 for r in rows if r["exam"] == ex and r.get("bm") is not None),
                        "adv": sum(1 for r in rows if r["exam"] == ex and r.get("adv") is not None),
                        "line": sum(1 for r in rows if r["exam"] == ex and r.get("line") is not None),
                    } for ex in ("省考", "事业编", "国考")
                },
            },
            "scoreSources": (["软件工程档案源表", "省考官方逐岗汇编（报名/合格/缴费/分数线）",
                             "省考省直与事业编省直达线名单", "2026国考职位表+进面名单"] if CYCLE == "2026" else
                             [f"安徽省{CYCLE}年度官方职位表（省直+16市）",
                              f"{CYCLE}省考各考区笔试达线名单（全省汇总）",
                              f"{CYCLE}国考安徽职位表+进面名单",
                              f"安徽事业单位{CYCLE}联考职位库+各单位成绩公告汇编"]),
            "examCounts": {
                "省考": sum(1 for r in rows if r["exam"] == "省考"),
                "事业编": sum(1 for r in rows if r["exam"] == "事业编"),
                "国考": sum(1 for r in rows if r["exam"] == "国考"),
            },
            "cities": sorted({r["city"] for r in rows}, key=lambda c: (c == "省直", c)),
            "categories": sorted({r["lb"] for r in rows if r["lb"]}),
            "csMembers": _ALL_CS_MEMBERS, "cats": cats,
            "majors": sorted(major_universe),
            "catalog": _major_catalog(),
        }
        payload = {"rows": rows, "meta": meta, "map": features}
    _ALL_CACHE = payload
    return payload


def _num_or(value) -> float | int | str | None:
    """源表数值容错：提取首个数字（含小数），无数字返回 None。"""
    if value is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if not m:
        return None
    text = m.group()
    return float(text) if "." in text else int(text)


def _parse_chuzhou_syb() -> list[dict]:
    """解析滁州市直事业单位招聘岗位表（金标尺 HTML 版，全专业 ~64 岗）。

    九列：招聘单位 / 岗位名称 / 拟聘人数 / 专业 / 学历 / 学位 / 年龄 / 其他 / 笔试类别。
    官方表无职位代码，按行序编 CZSB 前缀码并在详情中注明。
    """
    if CYCLE != "2026":
        return []  # 历史周期不并入 2026 滁州官方表
    if not CHUZHOU_SYB_HTML.is_file():
        return []
    text = CHUZHOU_SYB_HTML.read_text(encoding="utf-8", errors="ignore")
    rows = []
    seq = 0
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != 9:
            continue
        texts = [re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", c)) for c in cells]
        unit, zw, num, zy, xl, xw, age, qt, sl = texts
        if not unit or unit.startswith("招聘单位") or "年度滁州" in unit:
            continue
        seq += 1
        num_m = re.search(r"\d+", num)
        rows.append({
            "code": f"CZSB{seq:03d}", "city": "滁州", "reg": "市直",
            "unit": unit, "xz": "事业编", "cc": "", "lb": "",
            "zw": zw, "zj": "", "num": int(num_m.group()) if num_m else 1,
            "zy": zy, "xl": xl, "xw": xw, "age": age, "jl": "", "qt": qt,
            "sl": sl, "km": "", "bz": "", "dh": "",
            "exam": "事业编", "cycle": "上半年", "source_note": "官方表无职位代码，按行序编号",
        })
    return rows


def _huatu_syb_rows(jobs_records: list) -> list[dict]:
    """读入华图职位库快照（2026 上下半年事业编全专业），剔除与档案口径重复的岗位。

    档案 135 条事业编来自同一华图职位库（上半年），以 市+单位+人数 模糊键去重，
    保留档案行（含报名/成绩与定向标记）。

    v9.9.1 修复（核查报告 P1）：华图行单位名带主管部门前缀（如「庐江县水务局
    庐江县水库（河道）管理中心」），截断键不命中导致同一岗位多保留一行（实测
    109 组「同市+同码」重复）。新增职位码精确键（市+职位代码+招录人数）：档案行
    与华图行代码一致即判为同岗，优先保留档案行。
    注意：不可改用「单位名互含」判定——实测会在同单位多岗位场景误删 73 个不同码
    岗位（如池州职业技术学院 1501003~1501008 为 6 个不同岗位）。命中清单全部
    记入 _HUATU_DEDUP_STATS 供核查，不做静默删除。
    """
    if not HUATU_SYB_JSON.is_file():
        return []
    payload = json.loads(HUATU_SYB_JSON.read_text(encoding="utf-8"))

    def _norm(text: object) -> str:
        return re.sub(r"\s+", "", str(text or ""))

    def _key(city: str, unit: str, num: object) -> tuple:
        return (city, _norm(unit)[:12], num)

    seen: set[tuple] = set()
    code_seen: set[tuple[str, str, object]] = set()

    def _add_seen(city: object, unit: str, num: object, code: object = "") -> None:
        u = _norm(unit)
        if u:
            seen.add(_key(str(city), u, num))
        c = _norm(code)
        if c:
            code_seen.add((str(city), c, _num_or(num)))

    for rec in (jobs_records or []):
        if rec.get("exam") not in ("事业单位", "国考"):
            continue
        unit, _, _zw = str(rec.get("unit_position", "")).partition(" · ")
        _add_seen(rec.get("city", ""), unit, rec.get("recruits", 0), rec.get("code", ""))
    # 滁州市直已由官方 9 列表（CZSB，含其他条件/学位）覆盖，华图同批岗位去重
    for p in _parse_chuzhou_syb():
        _add_seen(p.get("city", ""), p.get("unit", ""), p.get("num", 0), p.get("code", ""))

    rows = []
    dropped = 0
    exact_dropped = 0
    code_pairs: list[dict] = []
    for p in payload.get("positions", []):
        if _key(p.get("city", ""), p.get("unit", ""), p.get("num", 0)) in seen:
            dropped += 1
            exact_dropped += 1
            continue
        if (str(p.get("city", "")), _norm(p.get("code", "")), _num_or(p.get("num", 0))) in code_seen:
            dropped += 1
            code_pairs.append({
                "city": p.get("city"), "code": p.get("code"), "num": p.get("num"),
                "huatu_unit": p.get("unit"), "huatu_zw": p.get("zw"),
            })
            continue
        p.pop("jf", None)
        rows.append(p)
    _HUATU_DEDUP_STATS["kept"] = len(rows)
    _HUATU_DEDUP_STATS["dropped"] = dropped
    _HUATU_DEDUP_STATS["exact_dropped"] = exact_dropped
    _HUATU_DEDUP_STATS["code_dropped"] = len(code_pairs)
    _HUATU_DEDUP_STATS["code_pairs"] = code_pairs
    return rows


def _archive_extra_rows(jobs_records: list, skip_codes: set | None = None) -> list[dict]:
    """把软件工程档案中的事业编 135 + 国考 3 条并入全岗位库（携带报名/成绩与标签）。

    skip_codes：v9.7 起国考全量职位表已并入，档案口径的国考行若代码在其中则跳过，
    避免同岗重复（其报名/竞争数据仍经 comp 层落到全量行上）。
    """
    rows = []
    for rec in (jobs_records or []):
        exam = rec.get("exam", "")
        if exam not in ("事业单位", "国考"):
            continue
        if exam == "国考" and skip_codes and str(rec.get("code", "")) in skip_codes:
            continue
        f = rec.get("fields") or {}
        unit_position = str(rec.get("unit_position", ""))
        unit, _, zw = unit_position.partition(" · ")
        elig = rec.get("eligibility") or {}
        rows.append({
            "code": rec["code"], "city": rec.get("city", ""), "reg": "",
            "unit": unit, "xz": "事业编" if exam == "事业单位" else exam, "cc": "", "lb": "",
            "zw": zw or unit_position, "zj": "", "num": rec.get("recruits", 0),
            "zy": "", "xl": "", "xw": "", "age": "", "jl": "", "qt": str(elig.get("other", "") or ""),
            "sl": "", "km": "", "bz": str(elig.get("remark", "") or ""), "dh": "",
            "tags": list(elig.get("tags", [])),
            "dir": rec.get("exclusion", {}).get("category", "") if isinstance(rec.get("exclusion"), dict) else "",
            "dirText": rec.get("exclusion", {}).get("source_remark", "") if isinstance(rec.get("exclusion"), dict) else "",
            "hukou": False, "floor": None, "only": False, "unlim": False,
            "bm": _num_or(f.get("报名*")), "hg": _num_or(f.get("审查合格*")),
            "jf": _num_or(f.get("缴费*")),
            "adv": _num_or(f.get("有效笔试/达线") or f.get("有效笔试/达线/规模参考")),
            "line": _num_or(f.get("最低入围/线")), "top": _num_or(f.get("最高笔试")),
            "exam": "事业编" if exam == "事业单位" else exam,
            "cycle": "上半年",
            "source_note": "软件工程档案口径（华图职位库2026）",
        })
    return rows


def _clean_public_major_option(value: object) -> str:
    """返回候选控件可读专业名；不改变 allMajors 中保留的原始字段。"""
    text = re.sub(r"^[^\u4e00-\u9fffA-Za-z]+", "", str(value or "")).strip()
    if len(text) < 2 or not re.search(r"[\u4e00-\u9fffA-Za-z]", text):
        return ""
    if not re.sub(r"[\d\s()[\]{}._（）【】+\-*/、，,;；:.：?？]", "", text):
        return ""
    return text


def _public_major_options(values: object) -> list[str]:
    """去重排序公开专业候选；源岗位的 zy 原文仍完整留在数据层。"""
    if not isinstance(values, (list, tuple, set)):
        return []
    return sorted({cleaned for value in values if (cleaned := _clean_public_major_option(value))}, key=str.casefold)


def _jobs_map_content(allm: dict[str, object]) -> str:
    meta = allm.get("meta") or {}
    major_options = "".join(f'<option value="{html.escape(m, quote=True)}"></option>' for m in _public_major_options(meta.get("majors", [])))
    cat_options = "".join(f'<option value="{html.escape(m, quote=True)}"></option>' for m in _public_major_options(meta.get("cats", [])))
    return (
        '<main class="product-main shell" id="main-content">'
        '<section class="product-hero product-hero--compact"><div>'
        '<p class="eyebrow">POSITION MAP</p><h1>岗位地图</h1>'
        '<p class="hero-lead">16 市岗位分布一图看清：默认展示全部专业；可在下方输入专业（或大类，如 计算机类）按可报数着色；画像匹配生效后自动切换为“你的可报数”。点击任意市进入全岗位库检索。</p>'
        '</div></section>'
        '<section class="wyall-toolbar"><span class="wyall-note" id="wyall-map-mode">当前口径：全部专业</span>'
        '<span class="wyall-majorbar"><input id="wyall-map-major" list="wyall-map-major-list" placeholder="输入专业或大类过滤地图，如：会计学 / 计算机类" aria-label="地图专业过滤">'
        '<select id="wyall-map-floor" aria-label="学历口径" title="按“你的学历可报”口径过滤：与总览「按专业匹配」保持一致，默认本科">'
        '<option value="2">大专可报</option><option value="3" selected>本科可报</option><option value="4">硕士可报</option><option value="5">博士可报</option><option value="9">不限学历</option>'
        '</select>'
        '<button type="button" class="text-button" id="wyall-map-major-clear">全部专业</button>'
        f'<datalist id="wyall-map-major-list">{cat_options}{major_options}</datalist></span>'
        '<span class="wyall-legend" id="wyall-map-legend" aria-hidden="true"></span></section>'
        '<section class="wyall-mapgrid"><div class="wyall-panel wyall-mappanel" id="wyall-map" role="img" aria-label="安徽省各市岗位分布地图"></div>'
        '<aside class="wyall-panel wyall-mapside" id="wyall-mapside" aria-label="各市岗位计数"></aside></section>'
        '<p class="wyall-foot">地理边界仅作数据导航用途，不替代法定行政区划图；省直岗位不属地市，见侧栏芯片。</p>'
        '</main>'
    )


def _jobs_all_content(allm: dict[str, object]) -> str:
    meta = allm["meta"]
    city_opts = "".join(f'<option value="{city}">{city}</option>' for city in meta["cities"])
    cat_opts = "".join(f'<option value="{html.escape(c)}">{html.escape(c)}</option>' for c in _public_major_options(meta["cats"]))
    xl_opts = "".join(f'<option value="{v}"{" selected" if v == "benke" else ""}>{label}</option>' for v, label in
                      (("dazhuan", "大专"), ("benke", "本科"), ("shuoshi", "硕士"), ("boshi", "博士")))
    gender_opts = "".join(f'<option value="{v}">{label}</option>' for v, label in
                          (("", "不限"), ("male", "男"), ("female", "女")))
    hukou_opts = "".join(f'<option value="{c}">{c}</option>' for c in meta["cities"] if c != "省直")
    tag_opts = "".join(f'<option value="{v}">{label}</option>' for v, label in (
        ("", "全部标签"), ("directed", "身份定向"), ("hukou", "户籍限定"), ("fresh_only", "仅应届"),
        ("gender_male", "限男"), ("party", "党员"), ("cert_legal", "法律资格"),
        ("min_service", "服务期"), ("prof_test", "专业测试"), ("night_shift", "夜班")))
    checks = "".join(
        f'<label class="wyall-check"><input type="checkbox" id="wyall-p-{key}"><span>{label}</span></label>'
        for key, label in (("fresh", "我是应届毕业生"), ("party", "中共党员"), ("cert", "我有法律职业资格证"),
                           ("sp", "我是“服务基层项目”人员（四项目）"), ("vet", "我是退役士兵 / 退役军人"),
                           ("fam", "我是随军家属"))
    )
    exam_counts = meta.get("examCounts", {})
    exam_opts = "".join(f'<option value="{k}">{k}（{v}）</option>' for k, v in exam_counts.items())
    return (
        '<main class="product-main shell" id="main-content">'
        '<section class="product-hero product-hero--compact"><div>'
        '<p class="eyebrow">ALL POSITIONS</p><h1>全岗位库</h1>'
        f'<p class="hero-lead">多考试类别合并库 {meta["total"]} 岗（招录 {meta["recruits"]} 人）：省考全专业 {exam_counts.get("省考", 0)}（官方表）· 事业编 {exam_counts.get("事业编", 0)}（2026 上/下半年联考全量并入华图职位库快照，含报名/合格人数）· 国考 {exam_counts.get("国考", 0)}（档案口径）。先填画像自动匹配，再筛选精修；判定附原文可复核。</p>'
        '</div></section>'
        '<section class="wyall-panel wyall-profile" aria-label="报考画像">'
        '<div class="wyall-form">'
        '<div class="wyall-combo"><label class="wyall-label" for="wyall-p-major">我的专业（可搜可选）</label>'
        '<input class="wyall-input" type="text" id="wyall-p-major" placeholder="输入关键词搜索专业，如：软件 / 计算机 / 会计" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="wyall-major-list">'
        '<div class="wyall-combolist" id="wyall-major-list" hidden role="listbox"></div></div>'
        f'<div><label class="wyall-label" for="wyall-p-cat">所属大类 / 门类（留空自动推断）</label><select class="wyall-select" id="wyall-p-cat"><option value="">— 自动推断 —</option>{cat_opts}</select></div>'
        f'<div><label class="wyall-label" for="wyall-p-xl">学历</label><select class="wyall-select" id="wyall-p-xl">{xl_opts}</select></div>'
        f'<div><label class="wyall-label" for="wyall-p-gender">性别</label><select class="wyall-select" id="wyall-p-gender">{gender_opts}</select></div>'
        f'<div><label class="wyall-label" for="wyall-p-hukou">户籍所在市（户籍限定岗用）</label><select class="wyall-select" id="wyall-p-hukou"><option value="">—</option>{hukou_opts}</select></div>'
        '</div>'
        f'<div class="wyall-checks">{checks}</div>'
        '<div class="wyall-actions"><button type="button" class="wyall-btn" id="wyall-run">开始匹配</button>'
        '<button type="button" class="wyall-btn wyall-btn--ghost" id="wyall-reset">清空画像</button>'
        '<span class="wyall-note" id="wyall-profile-state"></span></div>'
        '</section>'
        '<section class="wyall-toolbar">'
        '<input type="search" class="wyall-input wyall-kw" id="wyall-kw" placeholder="搜索单位 / 职位 / 专业 / 代码 / 备注…">'
        f'<select class="wyall-select" id="wyall-exam"><option value="">全部考试</option>{exam_opts}</select>'
        f'<select class="wyall-select" id="wyall-city"><option value="">全部市</option>{city_opts}</select>'
        f'<select class="wyall-select" id="wyall-lb"><option value="">全部类别</option>{cat_opts}</select>'
        '<select class="wyall-select" id="wyall-xl"><option value="">全部学历</option><option>大专</option><option>本科</option><option>硕士研究生</option><option>博士研究生</option></select>'
        f'<select class="wyall-select" id="wyall-tag">{tag_opts}</select>'
        '<button type="button" class="wyall-btn wyall-btn--ghost" id="wyall-csv">导出 CSV</button>'
        '</section>'
        '<div class="wyall-matchsum" id="wyall-matchsum" hidden></div>'
        '<div class="wyall-count" id="wyall-count"></div>'
        '<div class="wyall-panel wyall-tablewrap" id="wyall-table"></div>'
        '<p class="wyall-foot">省考报名 / 审查合格 / 缴费 / 笔试分数线按官方逐岗汇编（' + str((meta.get("scoreCoverage") or {}).get("bm", 0)) + ' 岗有报名、' + str((meta.get("scoreCoverage") or {}).get("line", 0)) + ' 岗有入围线）；省直与事业编省直达线名单提供达线人数与最高分；2026 国考安徽 ' + str(meta.get("examCounts", {}).get("国考", 0)) + ' 岗含进面人数与最低进面分；达线人数明细其余岗位待名单发布后接入（竞争比回退报名人数并以 ≈ 标记）。标签由规则库自动解析（附匹配原文）；最终以招录机关与官方公告为准。本页不生成录用概率承诺。</p>'
        '</main>'
    )


def _wrap_view(view: str, content: str, active: bool = False) -> str:
    """Turn an existing product page into a hidden/visible in-site view."""
    body = content
    if body.startswith('<main '):
        body = '<section ' + body[len('<main '):]
        if body.endswith('</main>'):
            body = body[:-len('</main>')] + '</section>'
    # The unified template already owns the document-level main landmark.
    # Remove the old page root id so each file has one unambiguous skip target.
    body = body.replace(' id="main-content"', '', 1)
    return f'<div class="unified-view {"is-active" if active else ""}" data-view="{view}">{body}</div>'


def _unified_nav(kind: str) -> str:
    if kind == "jobs":
        tabs = [("jobs_dashboard", "岗位观测台"), ("jobs_ranking", "排名对比"), ("jobs_search", "岗位检索"), ("score_sim", "分数模拟"), ("jobs_insight", "机会洞察"), ("jobs_compare", "岗位对比"), ("jobs_saved", "我的岗位"), ("manual", "报考手册"), ("jobs_archive", "岗位档案")]
        other = (MASTER_HTML_NAME + "#overview", "进入综合总览")
    else:
        tabs = [("salary_dashboard", "待遇观测台"), ("salary_ranking", "待遇排名"), ("salary_archive", "待遇档案")]
        other = (MASTER_HTML_NAME + "#overview", "进入综合总览")
    links = "".join(f'<button type="button" class="product-nav__link {"is-current" if index == 0 else ""}" data-view-link="{key}">{label}</button>' for index, (key, label) in enumerate(tabs))
    return '<nav class="product-nav" aria-label="产品导航"><div class="product-nav__inner shell"><a class="product-brand" href="#dashboard"><span class="product-brand__mark">皖</span><span><strong>皖域择岗档案</strong><small>数据洞察 · 科学择岗</small></span></a><div class="product-nav__links">'+links+f'<a class="product-nav__link product-nav__switch" href="{other[0]}">{other[1]}</a>'+'</div><span class="product-nav__status" aria-label="数据状态" title="数据快照 2026-05 · 构建 '+DATA_SNAPSHOT+'"><i aria-hidden="true"></i><span>'+BUILD_VERSION.upper()+' · 离线数据</span></span><div class="product-nav__tools"><button type="button" data-action="theme" aria-label="切换纸张底色" title="切换主题（清爽 / 纸张 / 夜间）"><span aria-hidden="true">◐</span><small>主题</small></button><button type="button" data-action="print" aria-label="打印当前视图" title="打印当前视图"><span aria-hidden="true">⌁</span><small>打印</small></button></div><div class="product-progress" aria-hidden="true"><span></span></div></div></nav>'


def _master_nav() -> str:
    tabs = [("overview", "全省总览"), ("cycle_compare", "三年对照"), ("jobs_dashboard", "机会地图"), ("jobs_map", "岗位地图"), ("jobs_all", "全岗位库"), ("score_sim", "分数模拟"), ("jobs_insight", "机会洞察"), ("salary_dashboard", "待遇地图"), ("shortlist", "我的短名单"), ("manual", "报考手册"), ("archives", "原始档案")]
    links = "".join(f'<button type="button" class="product-nav__link {"is-current" if key == "overview" else ""}" data-view-link="{key}">{label}</button>' for key, label in tabs)
    # v9.9.3：跨周期切换器，与历史周期页（_cycle_nav）同构；主站位于 deliverables 根目录。
    switch_items = []
    for cy, href in (("2024", "2024/皖域择岗总览.html"), ("2025", "2025/皖域择岗总览.html")):
        switch_items.append(f'<a class="cycle-switch__item" href="{href}" title="{cy}年度（历史周期）">{cy}</a>')
    switch_items.append('<span class="cycle-switch__item is-current" title="2026年度（当前主站）" aria-current="true">2026</span>')
    switch = '<div class="cycle-switch" aria-label="切换数据周期">' + "".join(switch_items) + "</div>"
    return '<nav class="product-nav master-nav" aria-label="综合产品导航"><div class="product-nav__inner shell"><a class="product-brand" href="#overview"><span class="product-brand__mark">皖</span><span><strong>皖域择岗总览</strong><small>机会 × 待遇 · 科学择岗</small></span></a><div class="product-nav__links">'+links+f'</div>{switch}<span class="product-nav__status" aria-label="数据状态" title="数据快照 2026-05 · 构建 '+DATA_SNAPSHOT+'"><i aria-hidden="true"></i><span>'+BUILD_VERSION.upper()+' · 离线数据</span></span><div class="product-nav__tools"><button type="button" data-action="theme" aria-label="切换纸张底色" title="切换主题（清爽 / 纸张 / 夜间）"><span aria-hidden="true">◐</span><small>主题</small></button><button type="button" data-action="print" aria-label="打印当前视图" title="打印当前视图"><span aria-hidden="true">⌁</span><small>打印</small></button></div><div class="product-progress" aria-hidden="true"><span></span></div></div></nav>'


def _unifiedize_links(kind: str, content: str) -> str:
    """Point links inside a unified file at hash views or the other main file."""
    if kind == "jobs":
        replacements = {
            'href="岗位观测台.html"': 'href="#jobs_dashboard"',
            'href="岗位排名对比.html"': 'href="#jobs_ranking"',
            'href="岗位检索.html"': 'href="#jobs_search"',
            'href="岗位档案.html"': 'href="#jobs_archive"',
            'href="岗位档案.html?city=合肥#city-合肥"': 'href="#jobs_archive"',
            'href="待遇观测台.html"': 'href="安徽全省16市本科普通岗全包分析.html#salary_dashboard"',
        }
    else:
        replacements = {
            'href="待遇观测台.html"': 'href="#salary_dashboard"',
            'href="待遇排名.html"': 'href="#salary_ranking"',
            'href="待遇档案.html"': 'href="#salary_archive"',
            'href="待遇档案.html?city=合肥#salary-city-合肥"': 'href="#salary_archive"',
            'href="岗位观测台.html"': 'href="安徽十六市2026软件工程可报岗位.html#jobs_dashboard"',
        }
    for old, new in replacements.items():
        content = content.replace(old, new)
    return content


def _masterize_links(content: str) -> str:
    replacements = {
        'href="岗位观测台.html"': 'href="#jobs_dashboard"',
        'href="岗位排名对比.html"': 'href="#jobs_ranking"',
        'href="岗位检索.html"': 'href="#jobs_search"',
        'href="岗位对比.html"': 'href="#jobs_compare"',
        'href="岗位档案.html"': 'href="#archives"',
        'href="岗位档案.html?city=合肥#city-合肥"': 'href="#archives"',
        'href="待遇观测台.html"': 'href="#salary_dashboard"',
        'href="待遇排名.html"': 'href="#salary_ranking"',
        'href="待遇档案.html"': 'href="#archives"',
        'href="待遇档案.html?city=合肥#salary-city-合肥"': 'href="#archives"',
    }
    for old, new in replacements.items():
        content = content.replace(old, new)
    return content


def _unified_context(kind: str, title: str, content: str, data: object, script: str) -> dict[str, str]:
    return {"PAGE_TITLE": html.escape(title, quote=True), "PAGE_DESCRIPTION": "安徽公考数据产品页，离线可用。", "ACTIVE_ROUTE": kind, "COMMON_CSS": _template_text("common.css"), "PAGE_CSS": _template_text("product-shell.css") + _template_text("unified.css") + _template_text("polish.css"), "PAGE_CONTENT": content, "PAGE_DATA": _page_data(data), "SCORE_LISTS_SCRIPT": "", "PAGE_JS": _template_text("product-shell.js") + "\n" + _template_text("product-enhance.js") + "\n" + script + "\n" + _template_text("unified.js"), "PRODUCT_NAV": _unified_nav(kind), "ARCHIVE_NOTICE": ""}


def _score_lists_script() -> str:
    """v9.8：逐岗考生成绩名单（省考笔试/面试总成绩、事业编各单位名单）注入为独立全局变量。"""
    if not SCORE_LISTS_JSON.is_file():
        return ""
    raw = SCORE_LISTS_JSON.read_text(encoding="utf-8").strip()
    return "<script>window.__SCORE_LISTS__=" + raw + ";</script>"


def _load_three_year_audit() -> dict[str, object]:
    """Load the read-only three-cycle audit summary for page rendering."""
    try:
        payload = json.loads(THREE_YEAR_AUDIT_JSON.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def _archive_notice() -> str:
    '''归档定位提示条（方案 A）：单文件视觉冻结，维护站是唯一演进入口。'''
    style = 'background:#eef5ff;border-bottom:1px solid #c7dcf5;color:#33567e;'
    style += "font:12px/1.7 'Microsoft YaHei','PingFang SC',sans-serif;text-align:center;padding:8px 14px;"
    line = '<div style='' + style + ''>'
    line += '本页为<strong>数据归档快照</strong>，界面已冻结；最新双主题交互、命令面板与离线缓存请使用长期维护入口 '
    line += '<strong>maintainable/index.html</strong>（<code>python tools/anhui_web/serve_maintainable.py</code> 后访问）。'
    line += '</div>'
    return line


def _master_context(title: str, content: str, data: object, script: str) -> dict[str, str]:
    return {"PAGE_TITLE": html.escape(title, quote=True), "PAGE_DESCRIPTION": "安徽公考机会与待遇综合决策页，离线可用。", "ACTIVE_ROUTE": "master", "COMMON_CSS": _template_text("common.css"), "PAGE_CSS": _template_text("product-shell.css") + _template_text("unified.css") + _template_text("polish.css") + _template_text("master.css") + _template_text("product-all.css"), "PAGE_CONTENT": content, "PAGE_DATA": _page_data(data), "SCORE_LISTS_SCRIPT": _score_lists_script(), "PAGE_JS": _template_text("product-shell.js") + "\n" + _template_text("product-enhance.js") + "\n" + script + "\n" + _template_text("unified.js"), "PRODUCT_NAV": _master_nav(), "ARCHIVE_NOTICE": _archive_notice()}


MAJOR_CATALOG_JSON = Path(__file__).resolve().parent / "data" / "major_catalog.json"
_CATALOG_CACHE: dict | None = None


def _major_catalog() -> dict:
    """华图 2026 专业分类目录（专业名 → 专业类列表），用于前端大类命中，消除漏报。"""
    global _CATALOG_CACHE
    if _CATALOG_CACHE is None:
        try:
            payload = json.loads(MAJOR_CATALOG_JSON.read_text(encoding="utf-8"))
            _CATALOG_CACHE = payload.get("map", {})
        except Exception:  # noqa: BLE001
            _CATALOG_CACHE = {}
    return _CATALOG_CACHE


def _all_cities_agg(allm: dict) -> list[dict]:
    """全岗位库按市聚合（含省直），供总览 KPI 的全库口径：jobs/recruits + 分考试类别。"""
    agg: dict[str, dict] = {}
    for r in allm["rows"]:
        city = str(r["city"])
        num = int(r.get("num") or 0)
        a = agg.setdefault(city, {"city": city, "jobs": 0, "recruits": 0, "exam": {}})
        a["jobs"] += 1
        a["recruits"] += num
        ex = str(r.get("exam") or "其他")
        e = a["exam"].setdefault(ex, {"jobs": 0, "recruits": 0})
        e["jobs"] += 1
        e["recruits"] += num
    return sorted(agg.values(), key=lambda x: (-x["jobs"], x["city"]))


def _master_cycle_compare_content(audit: dict[str, object]) -> str:
    """三周期对照页：只消费审计摘要，不重新计算岗位主数据。"""
    cycles = [item for item in (audit.get("cycles") or []) if isinstance(item, dict)]
    cycles_by_year = {str(item.get("cycle")): item for item in cycles}
    status_definitions = audit.get("status_definitions") or {}
    status_order = ("verified", "source_bundle", "unpublished_or_unavailable", "ambiguous_join")
    status_labels = {
        "verified": "内部对账",
        "source_bundle": "源包记录",
        "unpublished_or_unavailable": "官方未取得",
        "ambiguous_join": "安全留空",
    }

    def number(value: object) -> str:
        if value is None or value == "":
            return "—"
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return html.escape(str(value))

    def audit_value(cycle: str, field: str, value: object) -> str:
        return f'<strong data-audit-value="{cycle}:{field}">{number(value)}</strong>'

    def cycle_href(cycle: str) -> str:
        return "#overview" if cycle == "2026" else f"{cycle}/皖域择岗总览.html"

    trend_values = {
        field: {cycle: int((cycles_by_year.get(cycle, {}).get(field) or 0)) for cycle in ("2024", "2025", "2026")}
        for field in ("posts", "recruits")
    }
    trend_max = {field: max(values.values() or [1]) or 1 for field, values in trend_values.items()}

    def trend_pct(cycle: str, field: str) -> str:
        return f"{trend_values[field][cycle] / trend_max[field] * 100:.2f}%"

    cards = []
    for cycle in ("2024", "2025", "2026"):
        item = cycles_by_year.get(cycle, {})
        statuses = item.get("statuses") or {}
        gap_count = len(item.get("gaps") or [])
        status_note = f"{number(statuses.get('verified', 0))} 项内部核对 · {gap_count} 个已登记边界"
        current = " 当前" if cycle == "2026" else " 历史"
        cards.append(
            '<article class="cycle-compare-card" data-cycle-card="' + cycle + '">'
            '<div class="cycle-compare-card__top"><span class="cycle-compare-card__year">' + cycle + '</span>'
            '<span class="cycle-compare-card__tag">' + current.strip() + '</span></div>'
            '<p class="cycle-compare-card__label">' + html.escape(str(item.get("label") or f"{cycle}年度")) + '</p>'
            '<div class="cycle-compare-card__metrics">'
            '<div><span>岗位</span>' + audit_value(cycle, "posts", item.get("posts")) + '</div>'
            '<div><span>招录</span>' + audit_value(cycle, "recruits", item.get("recruits")) + '</div>'
            '</div><p class="cycle-compare-card__note">' + html.escape(status_note) + '</p>'
            '<a class="cycle-compare-card__link" href="' + cycle_href(cycle) + '">'
            + ("打开当前工作台 ↗" if cycle == "2026" else "打开周期档案 ↗") + '</a></article>'
        )

    exam_rows = []
    for exam in ("省考", "事业编", "国考"):
        cells = []
        for cycle in ("2024", "2025", "2026"):
            exam_data = (cycles_by_year.get(cycle, {}).get("exams") or {}).get(exam) or {}
            cells.append('<td><b>' + number(exam_data.get("posts")) + '</b><small>' + number(exam_data.get("recruits")) + ' 人</small></td>')
        exam_rows.append('<tr><th scope="row">' + exam + '</th>' + ''.join(cells) + '</tr>')

    status_cards = []
    for key in status_order:
        label = status_labels[key]
        description = status_definitions.get(key, "")
        status_cards.append(
            '<article class="cycle-status-card cycle-status-card--' + key + '" data-audit-status="' + key + '" title="' + html.escape(str(description), quote=True) + '">'
            '<span>' + label + '</span><strong data-audit-status-total="' + key + '">—</strong>'
            '<small>' + html.escape(str(description)) + '</small></article>'
        )

    gap_cards = []
    for cycle in ("2024", "2025", "2026"):
        for gap in (cycles_by_year.get(cycle, {}).get("gaps") or []):
            if not isinstance(gap, dict):
                continue
            kind = str(gap.get("kind") or "unpublished_or_unavailable")
            gap_cards.append(
                '<article class="cycle-gap-card cycle-gap-card--' + html.escape(kind, quote=True) + '" data-audit-gap-kind="' + html.escape(kind, quote=True) + '">'
                '<div class="cycle-gap-card__head"><span>' + cycle + ' · ' + html.escape(kind) + '</span><small>' + html.escape(str(gap.get("severity") or "medium")) + '</small></div>'
                '<strong>' + html.escape(str(gap.get("title") or "未命名边界")) + '</strong>'
                '<p>' + html.escape(str(gap.get("detail") or "")) + '</p>'
                '<code>' + html.escape(str(gap.get("evidence") or "")) + '</code></article>'
            )

    resolved_cards = []
    for cycle in ("2024", "2025", "2026"):
        for adjustment in (cycles_by_year.get(cycle, {}).get("resolved_adjustments") or []):
            if not isinstance(adjustment, dict):
                continue
            resolved_cards.append(
                '<article class="cycle-adjustment-card" data-audit-adjustment-kind="' + html.escape(str(adjustment.get("kind") or "source_bundle"), quote=True) + '">'
                '<div class="cycle-adjustment-card__head"><span>' + cycle + ' · 已核验调整</span><small>' + html.escape(str(adjustment.get("severity") or "medium")) + '</small></div>'
                '<strong>' + html.escape(str(adjustment.get("title") or "已登记调整")) + '</strong>'
                '<p>' + html.escape(str(adjustment.get("detail") or "")) + '</p>'
                '<code>' + html.escape(str(adjustment.get("evidence") or "")) + '</code></article>'
            )

    source_rows = []
    for cycle in ("2024", "2025", "2026"):
        item = cycles_by_year.get(cycle, {})
        source_rows.append(
            '<tr><th scope="row">' + cycle + '</th><td>' + number((item.get("source_totals") or {}).get("posts")) + '</td>'
            '<td>' + number((item.get("source_totals") or {}).get("recruits")) + '</td>'
            '<td>' + number((item.get("score_lists") or {}).get("by_key")) + '</td>'
            '<td>' + number((item.get("score_lists") or {}).get("unresolved")) + '</td></tr>'
        )

    return (
        '<main class="product-main shell cycle-compare-main" id="main-content">'
        '<section class="cycle-compare-hero"><div><p class="eyebrow">ARCHIVE INDEX · 2024—2026</p>'
        '<h1>三年数据，放在同一张时间轴上。</h1>'
        '<p class="hero-lead">先看周期规模，再看考试结构与证据边界。这里展示的是当前交接包已经核对到的事实；没有官方逐项证据的地方，会明确留在边界里。</p></div>'
        '<div class="cycle-compare-hero__stamp"><span>DATA STATUS</span><strong data-audit-total-checks="passed">' + number((audit.get("checks") or {}).get("passed")) + '</strong><small>项内部核对通过</small></div></section>'
        '<section class="cycle-compare-timeline" aria-label="三年周期卡片">' + ''.join(cards) + '</section>'
        '<section class="cycle-compare-section cycle-compare-section--trend"><header><div><p class="eyebrow">SCALE / TREND</p><h2>规模变化</h2><p>按岗位库总量比较，保留周期口径；不把年度差异解读成政策趋势。</p></div><span class="cycle-compare-section__rule" aria-hidden="true"></span></header>'
        '<div class="cycle-compare-trend-grid"><article class="cycle-trend-card"><span>岗位总量</span><div class="cycle-trend-bars" data-trend="posts">'
        + ''.join('<div class="cycle-trend-bar"><span>' + cycle + '</span><i style="--trend-pct:' + trend_pct(cycle, "posts") + '" data-audit-trend="' + cycle + ':posts"></i><b>' + number(cycles_by_year.get(cycle, {}).get("posts")) + '</b></div>' for cycle in ("2024", "2025", "2026"))
        + '</div></article><article class="cycle-trend-card"><span>招录人数</span><div class="cycle-trend-bars" data-trend="recruits">'
        + ''.join('<div class="cycle-trend-bar"><span>' + cycle + '</span><i style="--trend-pct:' + trend_pct(cycle, "recruits") + '" data-audit-trend="' + cycle + ':recruits"></i><b>' + number(cycles_by_year.get(cycle, {}).get("recruits")) + '</b></div>' for cycle in ("2024", "2025", "2026"))
        + '</div></article></div></section>'
        '<section class="cycle-compare-section"><header><div><p class="eyebrow">EXAM MIX</p><h2>考试结构对照</h2><p>岗位数为页面统一岗位行口径，人数为对应岗位招录人数合计。</p></div></header>'
        '<div class="table-shell cycle-compare-table"><table class="data-table"><thead><tr><th>类别</th><th>2024</th><th>2025</th><th>2026</th></tr></thead><tbody>' + ''.join(exam_rows) + '</tbody></table></div></section>'
        '<section class="cycle-compare-section"><header><div><p class="eyebrow">EVIDENCE LAYERS</p><h2>证据状态</h2><p>状态是对资料边界的描述，不是对未来数据的承诺。鼠标悬停可见定义。</p></div></header>'
        '<div class="cycle-status-grid">' + ''.join(status_cards) + '</div></section>'
        '<section class="cycle-compare-section"><header><div><p class="eyebrow">LINEAGE / COVERAGE</p><h2>成绩清单与安全匹配</h2><p>无城市字段且代码重复时，记录留空并进入安全留空，不复制到候选岗位。</p></div></header>'
        '<div class="table-shell cycle-compare-table"><table class="data-table"><thead><tr><th>周期</th><th>源包岗位</th><th>源包人数</th><th>成绩 by_key</th><th>无法唯一匹配</th></tr></thead><tbody>' + ''.join(source_rows) + '</tbody></table></div></section>'
        '<section class="cycle-compare-section cycle-compare-section--gaps"><header><div><p class="eyebrow">BOUNDARIES / GAPS</p><h2>已知缺口</h2><p>公开缺口是数据可信度的一部分；取得官方公告后再通过构建链路补入。</p></div><span class="cycle-gap-count">' + number(len(gap_cards)) + ' 项</span></header>'
        '<div class="cycle-gap-grid">' + (''.join(gap_cards) if gap_cards else '<p class="cycle-empty">当前没有登记缺口。</p>') + '</div></section>'
        '<section class="cycle-compare-section cycle-compare-section--resolved"><header><div><p class="eyebrow">RECONCILED / REGISTERED</p><h2>已核验调整</h2><p>这些是构建口径与源组件之间已完成对账的差异，单独展示，不计入未核验缺口。</p></div><span class="cycle-gap-count cycle-gap-count--resolved">' + number(len(resolved_cards)) + ' 项</span></header>'
        '<div class="cycle-adjustment-grid">' + (''.join(resolved_cards) if resolved_cards else '<p class="cycle-empty">当前没有登记调整。</p>') + '</div></section>'
        '<p class="cycle-compare-footnote">' + html.escape(str(audit.get("conclusion") or "")) + '</p></main>'
    )


def _build_master_site(jobs: dict[str, object], salary: dict[str, object]) -> str:
    allm = _all_majors_dataset(jobs.get("all_records") or jobs["records"])
    jobs_core = {"metrics": jobs["metrics"], "cities": jobs["cities"], "all_cities": _all_cities_agg(allm)}
    salary_core = {"series": salary["series"], "stages": salary["stages"], "cities": salary["cities"]}
    audit = _load_three_year_audit()
    views = "".join([
        _wrap_view("overview", _master_overview_content(jobs, salary), True),
        _wrap_view("cycle_compare", _master_cycle_compare_content(audit)),
        _wrap_view("jobs_dashboard", _jobs_dashboard_content(jobs)),
        _wrap_view("jobs_map", _jobs_map_content(allm)),
        _wrap_view("jobs_all", _jobs_all_content(allm)),
        _wrap_view("jobs_ranking", _jobs_ranking_content_v3(jobs)),
        _wrap_view("jobs_search", _jobs_search_content(jobs)),
        _wrap_view("score_sim", _jobs_score_sim_content(jobs)),
        _wrap_view("jobs_insight", _jobs_insight_content(jobs, salary)),
        _wrap_view("jobs_compare", _jobs_compare_content(jobs)),
        _wrap_view("salary_dashboard", _salary_dashboard_content_v3(salary)),
        _wrap_view("salary_ranking", _salary_ranking_content_v3(salary, jobs)),
        _wrap_view("shortlist", _master_shortlist_content(jobs)),
        _wrap_view("manual", _jobs_manual_content(jobs, salary)),
        _wrap_view("archives", _master_archive_content(jobs, salary)),
        _wrap_view("jobs_archive", '<main class="product-main shell master-archive-alias" id="main-content"><section class="product-hero product-hero--compact"><div><p class="eyebrow">SOURCE ARCHIVE</p><h1>正在打开原始档案库</h1><p class="hero-lead">请稍候，综合档案入口会自动定位到岗位源档案。</p></div></section></main>'),
        _wrap_view("salary_archive", '<main class="product-main shell master-archive-alias" id="main-content"><section class="product-hero product-hero--compact"><div><p class="eyebrow">SOURCE ARCHIVE</p><h1>正在打开原始档案库</h1><p class="hero-lead">请稍候，综合档案入口会自动定位到待遇源档案。</p></div></section></main>'),
    ])
    views = _masterize_links(views)
    data = {"kind": "master-unified", "jobs": jobs_core, "salary": salary_core, "records": jobs.get("all_records") or jobs["records"], "active_count": len(jobs["records"]), "glossary": GLOSSARY_TERMS, "allMajors": allm, "threeYearAudit": audit}
    script = "\n".join(_template_text(name) for name in ("product-core.js", "product-jobs.js", "product-jobs-ranking.js", "product-jobs-search.js", "product-jobs-detail.js", "score-metrics.js", "product-score-sim.js", "product-insight.js", "product-decision.js", "product-salary.js", "product-salary-ranking.js", "product-all.js", "master.js"))
    return assemble_page("product-unified.html", _master_context("皖域择岗总览｜机会 × 待遇综合工作台", views, data, script))


def _build_unified_site(kind: str, jobs: dict[str, object], salary: dict[str, object]) -> str:
    jobs_core = {"metrics": jobs["metrics"], "cities": jobs["cities"]}
    salary_core = {"series": salary["series"], "stages": salary["stages"], "cities": salary["cities"]}
    if kind == "jobs":
        views = "".join([
            _wrap_view("jobs_dashboard", _jobs_dashboard_content(jobs), True),
            _wrap_view("jobs_ranking", _jobs_ranking_content_v3(jobs)),
            _wrap_view("jobs_search", _jobs_search_content(jobs)),
            _wrap_view("score_sim", _jobs_score_sim_content(jobs)),
            _wrap_view("jobs_insight", _jobs_insight_content(jobs, salary)),
            _wrap_view("jobs_compare", _jobs_compare_content(jobs)),
            _wrap_view("jobs_saved", _jobs_saved_content(jobs)),
            _wrap_view("manual", _jobs_manual_content(jobs, salary)),
            _wrap_view("jobs_archive", _jobs_archive_content(jobs)),
        ])
        views = _unifiedize_links(kind, views)
        data = {"kind": "jobs-unified", **jobs_core, "records": jobs.get("all_records") or jobs["records"], "active_count": len(jobs["records"]), "salary": salary_core, "glossary": GLOSSARY_TERMS}
        script = "\n".join(_template_text(name) for name in ("product-core.js", "product-jobs.js", "product-jobs-ranking.js", "product-jobs-search.js", "product-jobs-detail.js", "score-metrics.js", "product-score-sim.js", "product-insight.js", "product-decision.js"))
        title = "安徽软件工程岗位工作台｜皖域择岗档案"
    else:
        views = "".join([
            _wrap_view("salary_dashboard", _salary_dashboard_content_v3(salary), True),
            _wrap_view("salary_ranking", _salary_ranking_content_v3(salary, jobs)),
            _wrap_view("salary_archive", _salary_archive_content(salary)),
        ])
        views = _unifiedize_links(kind, views)
        data = {"kind": "salary-unified", **salary_core, "glossary": GLOSSARY_TERMS}
        script = "\n".join(_template_text(name) for name in ("product-core.js", "product-salary.js", "product-salary-ranking.js"))
        title = "安徽本科普通岗待遇工作台｜皖域择岗档案"
    return assemble_page("product-unified.html", _unified_context(kind, title, views, data, script))


def _cycle_nav(cycle: str, label: str) -> str:
    """历史周期页导航：与主站同构，附周期切换链接（相对路径，deliverables/{cycle}/ 下）。"""
    tabs = [("overview", "周期总览"), ("jobs_map", "岗位地图"), ("jobs_all", "全岗位库"),
            ("jobs_search", "岗位检索"), ("jobs_compare", "岗位对比"), ("shortlist", "我的短名单")]
    links = "".join(
        f'<button type="button" class="product-nav__link {"is-current" if key == "overview" else ""}" data-view-link="{key}">{lab}</button>'
        for key, lab in tabs)
    switch_items = []
    for cy, href in (("2024", "../2024/皖域择岗总览.html"), ("2025", "../2025/皖域择岗总览.html"),
                     ("2026", "../皖域择岗总览.html")):
        cur = " is-current" if cy == cycle else ""
        tip = "（当前主站）" if cy == "2026" else "（历史周期）"
        switch_items.append(f'<a class="cycle-switch__item{cur}" href="{href}" title="{cy}年度{tip}">{cy}</a>')
    switch = '<div class="cycle-switch" aria-label="切换数据周期">' + "".join(switch_items) + "</div>"
    compare = '<a class="product-nav__link product-nav__compare" href="../皖域择岗总览.html#cycle_compare" title="打开三年对照">三年对照</a>'
    return ('<nav class="product-nav master-nav" aria-label="历史周期导航"><div class="product-nav__inner shell">'
            '<a class="product-brand" href="#overview"><span class="product-brand__mark">皖</span><span>'
            f'<strong>皖域择岗总览</strong><small>{label} · 历史周期</small></span></a>'
            f'<div class="product-nav__links">{links}{compare}</div>{switch}</div></nav>')


def _cycle_overview_content(cycle: str, info: dict, allm: dict, audit: dict[str, object] | None = None) -> str:
    """历史周期首页：周期 KPI + 口径说明 + 已知缺口，档案/待遇板块不纳入。"""
    stats = info.get("stats") or {}
    label = info.get("label") or f"{cycle}年度"
    meta = allm.get("meta") or {}
    per = (meta.get("scoreCoverage") or {}).get("perExam") or {}
    audit_cycle = next((item for item in (audit or {}).get("cycles", []) if str(item.get("cycle")) == cycle), {})
    audit_status = (audit_cycle.get("statuses") or {}) if isinstance(audit_cycle, dict) else {}
    status_line = (
        '<section class="cycle-state-bar" aria-label="周期数据状态"><div><span>数据状态</span>'
        f'<strong>{audit_status.get("verified", "—")} 项内部核对通过</strong>'
        f'<small>{len(audit_cycle.get("gaps") or []) if isinstance(audit_cycle, dict) else "—"} 个边界已登记 · 页面离线可复核</small></div>'
        '<a href="../皖域择岗总览.html#cycle_compare">查看三年对照 →</a></section>'
    )

    def _kpi(name: str, value: object, note: str) -> str:
        return (f'<div><span>{name}</span><strong>{value}</strong><small>{note}</small></div>')

    kpis = "".join([
        _kpi("全库岗位", stats.get("total_posts", meta.get("total", 0)), "省考+国考+事业编"),
        _kpi("招录人数", stats.get("total_recruits", meta.get("recruits", 0)), "公告口径合计"),
        _kpi("省考", f"{stats.get('shengkao_posts', '—')}岗/{stats.get('shengkao_recruits', '—')}人",
             f"报名 {stats.get('bm_total', '—')} 人"),
        _kpi("国考（安徽）", f"{stats.get('guokao_posts', '—')}岗/{stats.get('guokao_recruits', '—')}人",
             f"进面 {stats.get('guokao_jinmian_people', '—')} 人"),
        _kpi("事业编", f"{stats.get('syb_posts', '—')}岗/{stats.get('syb_recruits', '—')}人",
             f"成绩覆盖 {stats.get('syb_score_joined', '—')} 岗"),
        _kpi("省考达线名单", f"{stats.get('daxian_people', '—')}人",
             f"覆盖 {stats.get('daxian_posts', '—')} 岗"),
    ])
    gaps = info.get("gaps") or []
    gap_html = "".join(f'<li class="doc-list-item">{g}</li>' for g in gaps)
    per_rows = "".join(
        f'<tr><th scope="row">{ex}</th><td>{d.get("total", 0)}</td><td>{d.get("bm", 0)}</td>'
        f'<td>{d.get("adv", 0)}</td><td>{d.get("line", 0)}</td></tr>'
        for ex, d in per.items())
    css = ("<style>"
           ".cycle-switch{display:flex;gap:6px;align-items:center}.cycle-switch__item{padding:5px 11px;border:1px solid var(--line);border-radius:999px;color:#60728d;font:600 12px var(--sans);text-decoration:none;background:#fff}.cycle-switch__item.is-current{background:var(--blue);border-color:var(--blue);color:#fff}"
           ".cycle-gaps{margin-top:18px;padding:16px 18px;border:1px solid var(--line);border-radius:14px;background:#fff}.cycle-gaps h3{margin:0 0 8px;font:700 15px var(--display);color:var(--blue-deep)}.cycle-gaps ul{margin:0;padding-left:18px;color:#5f718b;font-size:12px}"
           ".cycle-table-note{margin-top:16px}.cycle-table-note .data-table{min-width:480px}"
           "</style>")
    return (f'<main class="product-main shell" id="main-content">{css}'
            '<section class="product-hero"><div>'
            f'<p class="eyebrow">ANHUI EXAM ARCHIVE · {cycle} HISTORICAL CYCLE</p>'
            f'<h1>皖域择岗总览 <span style="color:var(--blue)">{label}</span></h1>'
            f'<p class="hero-lead">安徽省{cycle}年度公考全岗位历史数据工作台：省考、国考（安徽）、事业编三库合一，'
            '支持地图、检索、对比与短名单。待遇估算与 2026 档案板块为主站（2026）专属，未纳入本页。</p>'
            '</div><div class="hero-note"><span>历史周期数据包</span>'
            f'<strong>{info.get("generated_on", "")}</strong><small>build_cycle_data.py 汇编 · 同构 2026 数据链路</small></div></section>'
            + status_line
            + f'<div class="kpi-strip">{kpis}</div>'
            '<section class="cycle-gaps"><h3>口径与已知缺口</h3><ul>' + gap_html + '</ul>'
            '<p class="doc-paragraph" style="font-size:12px;color:#79899d">逐层成绩覆盖（岗位数）：报名 bm / 达线人数 adv / 入围线 line。</p>'
            '<div class="table-shell cycle-table-note"><table class="data-table"><thead><tr>'
            '<th>考试类别</th><th>岗位</th><th>报名覆盖</th><th>达线覆盖</th><th>线覆盖</th></tr></thead>'
            f'<tbody>{per_rows}</tbody></table></div></section></main>')


def _cycle_context(title: str, content: str, data: object, script: str, nav: str) -> dict[str, str]:
    return {"PAGE_TITLE": html.escape(title, quote=True),
            "PAGE_DESCRIPTION": "安徽公考历史周期数据页，离线可用。",
            "ACTIVE_ROUTE": "master", "COMMON_CSS": _template_text("common.css"),
            "PAGE_CSS": _template_text("product-shell.css") + _template_text("unified.css") + _template_text("polish.css") + _template_text("product-all.css"),
            "PAGE_CONTENT": content, "PAGE_DATA": _page_data(data), "SCORE_LISTS_SCRIPT": _score_lists_script(),
            "PAGE_JS": _template_text("product-shell.js") + "\n" + _template_text("product-enhance.js") + "\n" + script + "\n" + _template_text("unified.js"),
            "PRODUCT_NAV": nav,
            "ARCHIVE_NOTICE": ""}


def _build_cycle_site(cycle: str) -> str:
    """历史周期（2025/2024）总览页：同构 allMajors 全库 + 缩减视图集，无 2026 档案/待遇板块。"""
    allm = _all_majors_dataset([])  # 历史周期：无 2026 档案记录，避免跨年混入
    info: dict = {}
    try:
        info = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info = {}
    label = info.get("label") or f"{cycle}年度"
    meta = allm["meta"]
    audit = _load_three_year_audit()
    jobs_core = {"metrics": {"totals": {"jobs": meta["total"], "recruits": meta["recruits"]}},
                 "cities": [], "all_cities": _all_cities_agg(allm)}
    # 周期页视图壳的最小 jobs 数据集：records 恒为空（历史周期无 2026 档案行）
    jobs_synth = {**jobs_core, "all_records": [], "records": []}
    views = "".join([
        _wrap_view("overview", _cycle_overview_content(cycle, info, allm, audit), True),
        _wrap_view("jobs_map", _jobs_map_content(allm)),
        _wrap_view("jobs_all", _jobs_all_content(allm)),
        _wrap_view("jobs_search", _jobs_search_content(jobs_synth)),
        _wrap_view("jobs_compare", _jobs_compare_content(jobs_synth)),
        _wrap_view("shortlist", _master_shortlist_content(jobs_synth)),
    ])
    data = {"kind": "master-unified", "jobs": jobs_core, "salary": {}, "records": [],
            "active_count": 0, "glossary": GLOSSARY_TERMS, "allMajors": allm,
            "cycleInfo": {"cycle": cycle, "label": label, "stats": info.get("stats") or {},
                          "gaps": info.get("gaps") or []}, "threeYearAudit": audit}
    script = "\n".join(_template_text(name) for name in (
        "product-core.js", "product-jobs.js", "product-jobs-search.js", "product-jobs-detail.js",
        "product-jobs-ranking.js", "product-all.js", "master.js"))
    title = f"皖域择岗总览（{label}）｜历史周期数据工作台"
    return assemble_page("product-unified.html", _cycle_context(title, views, data, script, _cycle_nav(cycle, label)))


def build_all(
    output_dir: Path = OUTPUT_DIR,
    jobs_docx: Path = JOBS_DOCX,
    salary_docx: Path = SALARY_DOCX,
    cycle: str = "2026",
    include_legacy: bool = True,
) -> tuple[Path, ...]:
    """Build the v12 single-file site, optionally retaining v11 compatibility pages.

    ``include_legacy=True`` is kept for the older parser/unit-test contract and
    writes the prior split pages alongside the new master. The release entrypoint
    passes ``False`` so the formal output contains only the single master HTML.
    ``cycle != "2026"`` remains an explicit historical source-package builder.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    if cycle != "2026":
        out = output_dir / cycle
        out.mkdir(parents=True, exist_ok=True)
        path = out / MASTER_HTML_NAME
        path.write_text(_build_cycle_site(cycle), encoding="utf-8")
        return (path,)
    if not include_legacy:
        path = output_dir / MASTER_HTML_NAME
        path.write_text(build_single_file_html(ROOT), encoding="utf-8")
        return (path,)
    jobs_model = parse_docx(jobs_docx)
    salary_model = parse_docx(salary_docx)
    jobs_dataset, salary_dataset = build_jobs_dataset(jobs_model), build_salary_dataset(salary_model)
    # Remove only generated split-page artifacts and the previous master entry.
    for filename in [*PRODUCT_PAGE_NAMES.values(), MASTER_HTML_NAME]:
        stale = output_dir / filename
        if stale.exists():
            stale.unlink()
    built: list[Path] = []
    master_path = output_dir / MASTER_HTML_NAME
    master_path.write_text(_build_master_site(jobs_dataset, salary_dataset), encoding="utf-8")
    built.append(master_path)
    for key, filename in (("jobs", JOBS_HTML_NAME), ("salary", SALARY_HTML_NAME)):
        path = output_dir / filename
        path.write_text(_build_unified_site(key, jobs_dataset, salary_dataset), encoding="utf-8")
        built.append(path)
    return tuple(built)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="把两份安徽公考 Word 报告构建为离线 HTML 页面。")
    parser.add_argument("--jobs-docx", type=Path, default=JOBS_DOCX, help="软件工程岗位 Word 文件")
    parser.add_argument("--salary-docx", type=Path, default=SALARY_DOCX, help="年度全包分析 Word 文件")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="HTML 输出目录")
    parser.add_argument("--cycle", default="2026", help="数据周期：2026（主站）或历史周期年份（2025/2024）")
    parser.add_argument("--include-legacy", action="store_true", help="额外生成 v11 分拆兼容页（正式发布默认关闭）")
    arguments = parser.parse_args()
    _apply_cycle_paths(arguments.cycle)
    for built_path in build_all(arguments.output_dir, arguments.jobs_docx, arguments.salary_docx, arguments.cycle, arguments.include_legacy):
        print(built_path)
