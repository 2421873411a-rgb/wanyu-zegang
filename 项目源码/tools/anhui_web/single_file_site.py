"""Build the v12 offline single-file three-cycle workbench."""

from __future__ import annotations

import copy
import html
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .unified_cycle_bundle import CycleBundle, build_unified_bundles


MASTER_NAME = "皖域择岗总览.html"
RELEASE = "v12.1"


def encode_json_script_payload(value: object) -> str:
    """Serialize JSON so untrusted strings cannot close an HTML script tag."""
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return (
        encoded.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _compact_score_lists(score_lists: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the single-file lookup index without duplicating legacy code maps.

    ``product-all.js`` resolves rows through ``by_key``.  The older ``bs`` and
    ``ms`` maps are retained in the standalone compatibility pages, but
    embedding both representations three times makes the unified artifact much
    larger and creates two possible sources of truth.
    """
    if not isinstance(score_lists, Mapping):
        return {}
    by_key = score_lists.get("by_key")
    if not isinstance(by_key, Mapping):
        return copy.deepcopy(dict(score_lists))
    compact: dict[str, Any] = {"by_key": copy.deepcopy(dict(by_key))}
    for key in ("cycle", "generated_on", "keyed"):
        if key in score_lists:
            compact[key] = copy.deepcopy(score_lists[key])
    return compact


def _payload_for(bundle: CycleBundle) -> dict[str, Any]:
    payload = copy.deepcopy(bundle.payload)
    payload["cycleRuntime"] = {
        "cycle": bundle.cycle,
        "label": bundle.label,
        "source_file": bundle.source_file.name,
        "row_count": len(bundle.records),
        "score_unresolved": (bundle.audit.get("score_unresolved") if isinstance(bundle.audit, dict) else None),
    }
    # Keep score lists cycle-scoped and lazy with the page data. This is a
    # technical envelope; source fields in allMajors/records remain unchanged.
    payload["scoreLists"] = _compact_score_lists(bundle.score_lists)
    return payload


def render_cycle_payload_scripts(bundles: Mapping[str, CycleBundle]) -> str:
    blocks: list[str] = []
    for cycle in ("2024", "2025", "2026"):
        bundle = bundles[cycle]
        blocks.append(
            f'<script type="application/json" data-cycle-payload="{html.escape(cycle, quote=True)}">'
            f"{encode_json_script_payload(_payload_for(bundle))}</script>"
        )
    return "\n  ".join(blocks)


def extract_embedded_payload_for_test(html_text: str, cycle: str) -> dict[str, Any]:
    match = re.search(
        rf'<script[^>]*data-cycle-payload=["\']{re.escape(str(cycle))}["\'][^>]*>(.*?)</script>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"embedded cycle payload not found: {cycle}")
    value = json.loads(match.group(1))
    if not isinstance(value, dict):
        raise ValueError(f"embedded cycle payload is not an object: {cycle}")
    return value


def _find_scaffold(root: Path) -> Path:
    candidates = (
        root / "deliverables" / "legacy_v11" / MASTER_NAME,
        root / "安徽公考数据网页" / MASTER_NAME,
        root / "deliverables" / MASTER_NAME,
    )
    for path in candidates:
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if "data-cycle-payload" not in text:
                return path
    # A v12 file is also a valid deterministic scaffold: it already contains
    # the head and the bundled application scripts. The loader above extracts
    # its cycle data separately, so this fallback keeps rebuilds repeatable
    # after the old split pages have been archived.
    v12_path = root / "deliverables" / MASTER_NAME
    if v12_path.is_file():
        return v12_path
    searched = "、".join(str(path) for path in candidates)
    raise FileNotFoundError(f"v11 HTML scaffold not found; searched {searched}")


def _extract_head(scaffold: str) -> str:
    match = re.search(r"<head\b.*?</head>", scaffold, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("v11 scaffold has no complete <head>")
    head = match.group(0)
    head = re.sub(
        r'<meta\s+name=["\']description["\'][^>]*>',
        '<meta name="description" content="安徽公考三年周期统一工作台，离线可用。">',
        head,
        count=1,
        flags=re.IGNORECASE,
    )
    head = re.sub(
        r"<title>.*?</title>",
        f"<title>皖域择岗总览｜三年周期统一工作台 {RELEASE}</title>",
        head,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Rebuilds use a previously generated HTML as a scaffold. Remove the
    # named style blocks first, otherwise every build appends another copy of
    # the same cycle/master CSS and the single-file artifact grows forever.
    for marker in ("data-v12-cycle-style", "data-v12-master-style", "data-v13-visual-style"):
        head = re.sub(
            rf'<style\b[^>]*\b{re.escape(marker)}\b[^>]*>.*?</style\s*>',
            "",
            head,
            flags=re.IGNORECASE | re.DOTALL,
        )
    template_dir = Path(__file__).resolve().parent / "templates"
    cycle_css = (template_dir / "cycle-unified.css").read_text(encoding="utf-8")
    master_css = (template_dir / "master.css").read_text(encoding="utf-8")
    visual_css = (template_dir / "ui-v13.css").read_text(encoding="utf-8")
    # The scaffold is an input snapshot. Re-inject the current compare styles so
    # a rebuilt single file cannot silently retain an older master.css bundle.
    styles = (
        f"<style data-v12-cycle-style>\n{cycle_css}\n</style>\n"
        f"<style data-v12-master-style>\n{master_css}\n</style>\n"
        f"<style data-v13-visual-style>\n{visual_css}\n</style>\n"
    )
    return head.replace("</head>", f"{styles}</head>")


def _extract_function_scripts(scaffold: str) -> str:
    scripts: list[str] = []
    for match in re.finditer(r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>", scaffold, flags=re.IGNORECASE | re.DOTALL):
        attrs = match.group("attrs")
        body = match.group("body").strip()
        if not body or re.search(r"\bid=[\"']page-data[\"']", attrs, flags=re.IGNORECASE):
            continue
        if re.search(r"data-v12-runtime|data-cycle-payload", attrs, flags=re.IGNORECASE):
            continue
        if re.match(r"^window\.__SCORE_LISTS__\s*=", body):
            continue
        if "src=" in attrs.lower():
            continue
        scripts.append(body)
    if not scripts:
        raise ValueError("v11 scaffold has no inline application scripts")
    return "\n\n".join(scripts)


def _template_function_scripts() -> str:
    """Use source templates for rebuilds so a v12 scaffold cannot freeze old JS."""
    template_dir = Path(__file__).resolve().parent / "templates"
    names = (
        "product-record-adapter.js", "product-user-store.js", "product-shell.js", "product-enhance.js", "product-core.js", "product-jobs.js",
        "product-jobs-ranking.js", "product-jobs-search.js", "product-jobs-detail.js",
        "score-metrics.js", "product-score-sim.js", "product-insight.js", "product-decision.js",
        "product-salary.js", "product-salary-ranking.js", "product-all.js", "master.js", "unified.js",
    )
    return "\n\n".join((template_dir / name).read_text(encoding="utf-8").strip() for name in names)


def _cycle_tab(cycle: str, selected: str) -> str:
    is_selected = cycle == selected
    return (
        f'<button type="button" class="wy-cycle-tab" role="tab" data-cycle-tab="{cycle}" '
        f'aria-selected="{"true" if is_selected else "false"}" aria-controls="cycle-context" '
        f'tabindex="{"0" if is_selected else "-1"}"><span>{cycle}</span><small>{"当前" if is_selected else "周期"}</small></button>'
    )


def _app_shell(default_cycle: str) -> str:
    tabs = "".join(_cycle_tab(cycle, default_cycle) for cycle in ("2024", "2025", "2026"))
    return (
        '<header id="app-shell" class="wy-app-shell" data-active-cycle="2026">'
        '<div class="wy-app-shell__top shell">'
        '<a class="wy-brand" href="#overview"><span class="wy-brand__mark">皖</span><span>'
        '<strong>皖域择岗档案</strong><small>THREE-CYCLE WORKBENCH · OFFLINE EDITION</small></span></a>'
        '<div class="wy-cycle-picker"><span class="wy-cycle-picker__label">数据周期</span>'
        f'<div id="cycle-picker" class="wy-cycle-picker__tabs" role="tablist" aria-label="选择数据周期">{tabs}</div></div>'
        '</div>'
        '<section id="cycle-context" class="wy-context" data-active-cycle="2026" aria-live="polite">'
        '<div class="wy-context__name"><span>CURRENT DATA CONTEXT</span><strong data-cycle-name>2026 · 快照</strong>'
        '<small data-cycle-state>正在读取周期审计状态</small></div>'
        '<div class="wy-context__metric"><span>全库岗位</span><strong data-cycle-posts>—</strong><small>岗位行</small></div>'
        '<div class="wy-context__metric"><span>招录人数</span><strong data-cycle-recruits>—</strong><small>公告口径合计</small></div>'
        '<div class="wy-context__metric"><span>成绩关联</span><strong data-cycle-joined>—</strong><small>安全关联岗位</small></div>'
        '<a class="wy-context__audit" href="#cycle_compare">打开数据审计 →</a>'
        '</section></header>'
    )


def _main_nav() -> str:
    links = (
        ("overview", "全省总览", ""),
        ("cycle_compare", "三年对照", ""),
        ("jobs_dashboard", "机会地图", "2024,2025"),
        ("jobs_ranking", "岗位榜单", "2024,2025"),
        ("jobs_map", "岗位地图", ""),
        ("jobs_all", "全岗位库", ""),
        ("jobs_search", "岗位检索", ""),
        ("score_sim", "分数模拟", "2024,2025"),
        ("jobs_insight", "机会洞察", "2024,2025"),
        ("salary_dashboard", "待遇地图", "2024,2025"),
        ("shortlist", "我的短名单", ""),
        ("manual", "报考手册", "2024,2025"),
        ("archives", "原始档案", "2024,2025"),
    )
    rendered: list[str] = []
    for key, label, unavailable in links:
        extra = f' data-cycle-unavailable="{unavailable}"' if unavailable else ""
        rendered.append(
            f'<button type="button" class="wy-main-nav__link" data-view-link="{key}"{extra}>{label}</button>'
        )
    return '<nav class="wy-main-nav" aria-label="主导航"><div class="wy-main-nav__inner shell">' + "".join(rendered) + "</div></nav>"


def _limited_views(content: str, cycle: str) -> str:
    available = set(re.findall(r'data-view=["\']([^"\']+)', content))
    missing = (
        ("jobs_dashboard", "机会地图", "该历史周期没有 2026 档案口径的逐市成绩分母，已保留岗位地图和全岗位库作为可复核入口。"),
        ("jobs_ranking", "岗位榜单", "该历史周期未封装 2026 岗位榜单所需的同口径排名统计；岗位明细仍可在全岗位库与岗位检索中复核。"),
        ("score_sim", "分数模拟", "历史周期成绩清单已封装，但当前包没有可安全绑定到岗位明细的统一样本，暂不生成模拟结果。"),
        ("jobs_insight", "机会洞察", "洞察需要可比的逐岗竞争分母；本周期公开材料存在登记缺口，保留边界说明，不下结论。"),
        ("salary_dashboard", "待遇地图", "待遇 Word 只提供 2026 快照，未提供 2024/2025 同口径源表；这里不冒充历史待遇。"),
        ("salary_ranking", "待遇排名", "待遇 Word 只提供 2026 快照，未提供 2024/2025 同口径源表；这里不冒充历史待遇。"),
        ("manual", "报考手册", "本周期使用全岗位库、岗位检索和数据审计；手册内容以当前主站口径为准。"),
        ("archives", "原始档案", "历史周期已封装岗位数据和来源状态；原始 Word 档案仍按交付包说明提供。"),
    )
    blocks: list[str] = []
    for key, title, reason in missing:
        if key in available:
            continue
        blocks.append(
            f'<div class="unified-view" data-view="{key}"><section class="wy-cycle-limited">'
            f'<span class="wy-cycle-limited__badge">{cycle} · DATA BOUNDARY</span>'
            f'<h1>{html.escape(title)}</h1><p>{html.escape(reason)}</p>'
            '<div class="wy-cycle-limited__actions"><a href="#jobs_all">去全岗位库</a>'
            '<a href="#jobs_search">去岗位检索</a><a href="#cycle_compare">看三年审计</a></div>'
            '</section></div>'
        )
    return content + "".join(blocks)


def _replace_single_file_view(content: str, view_key: str, rendered: str) -> str:
    if rendered.startswith("<main "):
        rendered = "<section " + rendered[len("<main "):]
        if rendered.endswith("</main>"):
            rendered = rendered[: -len("</main>")] + "</section>"
    rendered = rendered.replace(' id="main-content"', "", 1)
    replacement = f'<div class="unified-view is-active" data-view="{view_key}">{rendered}</div>'
    if not re.search(rf'data-view=["\']{re.escape(view_key)}["\']', content, flags=re.IGNORECASE):
        return content + replacement
    view_pattern = re.compile(
        r'<div\b(?=[^>]*\bclass=["\']unified-view[^"\']*["\'])'
        rf'(?=[^>]*\bdata-view=["\']{re.escape(view_key)}["\'])[^>]*>.*?'
        r'(?=<div\b(?=[^>]*\bclass=["\']unified-view[^"\']*["\'])'
        r'(?=[^>]*\bdata-view=)|\Z)',
        flags=re.IGNORECASE | re.DOTALL,
    )
    updated, count = view_pattern.subn(replacement, content, count=1)
    if count != 1:
        raise ValueError(f"single-file scaffold has no replaceable {view_key} view")
    return updated


def _refresh_master_hero(content: str) -> str:
    """Refresh the shared 2026 hero when the existing HTML is used as scaffold."""
    replacement = (
        '<section class="master-hero">'
        '<div class="master-evidence-rail" aria-label="证据索引">'
        '<span>01 · SOURCE</span><i aria-hidden="true"></i>'
        '<span>02 · METRIC</span><i aria-hidden="true"></i>'
        '<span>03 · DECISION</span></div>'
        '<div><p class="eyebrow">00 · ANHUI DECISION DESK</p>'
        '<h1>把岗位与待遇，放进同一张决策桌。</h1>'
        '<p class="hero-lead">从全省总览开始，选定条件、聚焦城市，再把机会、竞争与长期待遇放进同一个判断闭环。</p></div>'
        '<div class="master-hero__stamp"><span>ARCHIVE STATUS · OFFLINE</span>'
        '<strong>2024—26</strong><small>3 个周期 · 16 座城市</small>'
        '<em>数据边界公开 · 可回到原表复核</em></div></section>'
    )
    refreshed, count = re.subn(
        r'<section\b[^>]*\bclass=["\']master-hero["\'][^>]*>.*?</section\s*>',
        replacement,
        content,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return refreshed if count == 1 else content


def _single_file_cycle_overview(content: str, cycle: str, bundle: CycleBundle, audit: Mapping[str, Any]) -> str:
    """Refresh historical overview copy from the current cycle sidecars."""
    if cycle not in ("2024", "2025"):
        return content
    try:
        from .build_pages import _cycle_overview_content
    except ImportError:
        from tools.anhui_web.build_pages import _cycle_overview_content
    info = bundle.payload.get("cycleInfo") if isinstance(bundle.payload.get("cycleInfo"), dict) else {}
    rendered = _cycle_overview_content(cycle, dict(info), copy.deepcopy(bundle.all_majors), dict(audit))
    return _replace_single_file_view(content, "overview", rendered)


def _single_file_cycle_compare(content: str, audit: Mapping[str, Any]) -> str:
    """Refresh the compare view from the current audit inside every template.

    The single-file builder intentionally reuses the existing rendered views as
    its scaffold. That is useful for preserving the large archive sections, but
    it also means a stale compare view can survive a rebuild. The compare view
    is generated from the audit source instead, and historical links are kept
    inside this same HTML file through the cycle query parameter.
    """
    try:
        from .build_pages import _master_cycle_compare_content
    except ImportError:
        from tools.anhui_web.build_pages import _master_cycle_compare_content

    rendered = _master_cycle_compare_content(dict(audit))
    rendered = rendered.replace(
        'href="2024/皖域择岗总览.html"', 'href="?cycle=2024#overview"'
    ).replace(
        'href="2025/皖域择岗总览.html"', 'href="?cycle=2025#overview"'
    )
    return _replace_single_file_view(content, "cycle_compare", rendered)


def _single_file_jobs_ranking(content: str, bundle: CycleBundle) -> str:
    """Refresh the current-cycle ranking view from the source data payload.

    The formal single file uses its previous HTML as a scaffold so the large
    archive sections remain stable.  Ranking is an interactive surface that
    has changed since the scaffold was created, so regenerate only that view
    from the validated bundle instead of allowing an old toolbar to survive a
    rebuild.
    """
    if bundle.cycle != "2026":
        return content
    try:
        from .build_pages import _jobs_ranking_content_v3
    except ImportError:
        from tools.anhui_web.build_pages import _jobs_ranking_content_v3
    jobs = copy.deepcopy(bundle.payload.get("jobs") or {})
    rows = bundle.payload.get("records")
    if not isinstance(rows, list):
        rows = (bundle.payload.get("allMajors") or {}).get("rows") or []
    jobs["records"] = rows
    jobs["all_records"] = rows
    rendered = _jobs_ranking_content_v3(jobs)
    return _replace_single_file_view(content, "jobs_ranking", rendered)


def _single_file_jobs_catalog(content: str, bundle: CycleBundle) -> str:
    """Refresh map/profile catalog views so display options follow the source bundle.

    The scaffold is intentionally retained for large archive sections, but the
    map and all-positions controls are generated views. Re-rendering them on
    every cycle keeps public major candidates human-readable without changing
    the raw ``zy`` values inside the embedded JSON payload.
    """
    try:
        from .build_pages import _jobs_all_content, _jobs_map_content
    except ImportError:
        from tools.anhui_web.build_pages import _jobs_all_content, _jobs_map_content
    allm = copy.deepcopy(bundle.payload.get("allMajors") or {})
    if not isinstance(allm, dict):
        return content
    for view_key, renderer in (("jobs_map", _jobs_map_content), ("jobs_all", _jobs_all_content)):
        content = _replace_single_file_view(content, view_key, renderer(allm))
    return content


def _archive_notice_html() -> str:
    try:
        from .build_pages import _archive_notice
    except ImportError:
        from tools.anhui_web.build_pages import _archive_notice
    return _archive_notice()


def build_single_file_html(root: Path) -> str:
    """Return the complete v12 HTML without writing it to disk."""
    root = Path(root).resolve()
    bundles = build_unified_bundles(root)
    scaffold_path = _find_scaffold(root)
    scaffold = scaffold_path.read_text(encoding="utf-8")
    head = _extract_head(scaffold)
    runtime = (Path(__file__).resolve().parent / "templates" / "cycle-runtime.js").read_text(encoding="utf-8")
    scripts = _template_function_scripts()
    templates: list[str] = []
    audit = bundles["2026"].payload.get("threeYearAudit")
    if not isinstance(audit, dict):
        raise ValueError("validated cycle bundle has no three-year audit payload")
    for cycle in ("2024", "2025", "2026"):
        content = _single_file_cycle_overview(bundles[cycle].page_content, cycle, bundles[cycle], audit)
        content = _refresh_master_hero(content)
        content = _single_file_cycle_compare(content, audit)
        content = _single_file_jobs_ranking(content, bundles[cycle])
        content = _single_file_jobs_catalog(content, bundles[cycle])
        content = _limited_views(content, cycle)
        templates.append(
            f'<template data-cycle-template="{cycle}">{content}</template>'
        )
    body = (
        '<body class="product-page unified-site unified-site--master v12-single-file v13-visual">'
        '<a class="skip-link" href="#main-content">跳到正文</a>'
        + _archive_notice_html()
        + _app_shell("2026")
        + _main_nav()
        + '<main id="main-content"><div id="cycle-view-container" data-active-cycle="2026"></div></main>'
        '<footer class="wy-footer"><div class="wy-footer__line"><strong>皖域择岗总览 · 三年单文件工作台</strong>'
        '<span>版本 v12.1 · v13 视觉层 · <span data-cycle-source>源页已封装</span></span></div>'
        '<div>数据状态：源字段、审计缺口与安全留空均随周期载荷保留。待遇基准（2026 快照）仅代表待遇 Word 的 2026 口径，不能解释为 2024/2025 历史值。</div></footer>'
        + render_cycle_payload_scripts(bundles)
        + "\n  "
        + "\n  ".join(templates)
        + f'\n  <script data-v12-runtime>\n{runtime}\n  </script>'
        + f'\n  <script data-v12-app>\n{scripts}\n  </script>'
        + "</body>\n</html>"
    )
    document = '<!doctype html>\n<html lang="zh-CN" data-release="v12.1" data-default-cycle="2026">\n' + head + "\n" + body
    return document
