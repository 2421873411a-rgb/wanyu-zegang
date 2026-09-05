"""Build the long-lived HTTP site from the same audited cycle bundles.

The single-file workbench remains the offline snapshot.  This builder keeps
the maintainable site's HTML small and writes one versioned JSON payload per
cycle, so data refreshes do not require hand-editing the application shell.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from .build_catalog import build_catalog, extract_major_keywords
    from .build_changes import build_change_payload
    from .build_map import build_map_payload
    from .build_position_index import build_position_index
    from .build_review_queue import build_review_queue
    from .build_scores import build_scores
    from .build_supplement_evidence import build_supplement_evidence
    from .single_file_site import _payload_for
    from .unified_cycle_bundle import SUPPORTED_CYCLES, build_unified_bundles
except ImportError:  # pragma: no cover - supports direct script execution
    from tools.anhui_web.build_catalog import build_catalog, extract_major_keywords
    from tools.anhui_web.build_changes import build_change_payload
    from tools.anhui_web.build_map import build_map_payload
    from tools.anhui_web.build_position_index import build_position_index
    from tools.anhui_web.build_review_queue import build_review_queue
    from tools.anhui_web.build_scores import build_scores
    from tools.anhui_web.build_supplement_evidence import build_supplement_evidence
    from tools.anhui_web.single_file_site import _payload_for
    from tools.anhui_web.unified_cycle_bundle import SUPPORTED_CYCLES, build_unified_bundles


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_OUTPUT = ROOT / "deliverables" / "maintainable"
SCHEMA = "wanyu-maintainable-site/v3"
# D(2026-09-05): 版本唯一真源 = 项目源码/release.json，禁止此处硬编码
RELEASE = json.loads((Path(__file__).resolve().parents[2] / "release.json").read_text(encoding="utf-8"))["release"]


def _stable_snapshot_date(bundles: dict[str, Any]) -> str:
    """Return the audited source snapshot date, never today's build date."""
    audit = bundles.get("2026").payload.get("threeYearAudit") if bundles.get("2026") else {}
    candidates = []
    if isinstance(audit, dict):
        candidates.extend([audit.get("generated_on"), audit.get("verified_on")])
        summary = audit.get("summary")
        if isinstance(summary, dict):
            candidates.extend([summary.get("generated_on"), summary.get("verified_on")])
    for bundle in bundles.values():
        candidates.extend([bundle.cycle_info.get("generated_on"), bundle.cycle_info.get("snapshot_date")])
    for value in candidates:
        match = re.search(r"\d{4}-\d{2}-\d{2}", str(value or ""))
        if match:
            return match.group(0)
    return "undated-source"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: Path, value: object) -> bytes:
    encoded = _json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return encoded


def _salary_payload() -> dict[str, object]:
    """Build the 待遇(年度全包估算中位数) module powering the city heat map.

    待遇是 2026 快照的全包估算中位数，来自与离线单文件同源的 source_docs 分析
    Word；它不是官方逐岗工资，也不代表 2024/2025。缺失值保持 None，绝不推断为零。
    这份数据很小（16 市 × 2 身份 × 5 工龄），作为顶层全局模块外置，不进 per-cycle
    modules，以免破坏维护站按周期懒加载与磁盘校验的模块集合等值约束。
    """
    try:
        from .build_pages import SALARY_DOCX, parse_docx, extract_salary_series
    except ImportError:  # pragma: no cover - supports direct script execution
        from tools.anhui_web.build_pages import SALARY_DOCX, parse_docx, extract_salary_series

    stages = ["刚入职", "1年", "3年", "5年", "10年"]
    employment_types = ["公务员", "事业编"]
    if not Path(SALARY_DOCX).is_file():
        raise FileNotFoundError(
            f"待遇数据源缺失，无法生成 salary 模块：{SALARY_DOCX}（可用环境变量 WANYU_SALARY_DOCX 覆盖）"
        )
    series = extract_salary_series(parse_docx(Path(SALARY_DOCX)))
    return {
        "schema": "wanyu-maintainable-salary/v1",
        "snapshot": "2026",
        "metric": "年度全包估算中位数",
        "unit": "万元/年",
        "note": "待遇为 2026 快照的全包估算中位数（应发 + 津补贴 + 公积金 + 年终折算），"
                "非官方逐岗工资、不代表 2024/2025，也不是个人收入或录用承诺；缺失保持空值不推断为零。",
        "employment_types": employment_types,
        "stages": stages,
        "cities": sorted(series["公务员"].keys()),
        "series": series,
        "source_module": "source_docs/安徽全省16市本科普通岗全包分析_完善版(1).docx",
    }


def _summary_meta(meta: object) -> dict[str, object]:
    """Keep only overview-safe metadata out of the large jobs module."""
    if not isinstance(meta, dict):
        return {}
    allowed = (
        "cycle", "total", "recruits", "compJoined", "directed", "hukou",
        "cities", "categories", "examCounts", "scoreCoverage", "scoreSources",
    )
    return {key: copy.deepcopy(meta[key]) for key in allowed if key in meta}


def _unresolved_score_count(bundle: Any, payload: dict[str, object] | None = None) -> int:
    """Read the authoritative unresolved score count without binding rows."""
    source = payload if isinstance(payload, dict) else getattr(bundle, "payload", {})
    score_lists = source.get("scoreLists") if isinstance(source, dict) else {}
    keyed = score_lists.get("keyed") if isinstance(score_lists, dict) else {}
    unresolved = keyed.get("unresolved") if isinstance(keyed, dict) else None
    if unresolved is None:
        audit = getattr(bundle, "audit", {})
        coverage = audit.get("coverage") if isinstance(audit, dict) else {}
        unresolved = coverage.get("score_unresolved") if isinstance(coverage, dict) else 0
    if isinstance(unresolved, list):
        return len(unresolved)
    try:
        return int(unresolved or 0)
    except (TypeError, ValueError):
        return 0


def _module_payloads(bundle: Any) -> dict[str, dict[str, object]]:
    """Project one audited bundle into independently replaceable data modules."""
    payload = _payload_for(bundle)
    all_majors = payload.get("allMajors") if isinstance(payload.get("allMajors"), dict) else {}
    meta = all_majors.get("meta") if isinstance(all_majors, dict) else {}
    rows = all_majors.get("rows") if isinstance(all_majors, dict) else []
    runtime = copy.deepcopy(payload.get("cycleRuntime") or {})
    cycle_info = copy.deepcopy(payload.get("cycleInfo") or {})
    audit_cycle = copy.deepcopy(bundle.audit) if isinstance(bundle.audit, dict) else {}
    unresolved = _unresolved_score_count(bundle, payload)
    overview = {
        "schema": "wanyu-maintainable-overview/v1",
        "cycle": bundle.cycle,
        "label": bundle.label,
        "cycleRuntime": runtime,
        "cycleInfo": cycle_info,
        "allMajors": {"meta": _summary_meta(meta)},
        "auditSummary": {
            "status": audit_cycle.get("status") or audit_cycle.get("dominant_status") or "verified",
            "evidence_level": audit_cycle.get("evidence_level") or "partial_evidence",
            "gap_count": len(audit_cycle.get("gaps") or []),
            "score_unresolved": int(unresolved or 0),
        },
    }
    jobs = {
        "schema": "wanyu-maintainable-jobs/v1",
        "cycle": bundle.cycle,
        "label": bundle.label,
        "cycleRuntime": runtime,
        "allMajors": {
            "meta": _summary_meta(meta),
            "rows": copy.deepcopy(rows if isinstance(rows, list) else []),
        },
    }
    audit = {
        "schema": "wanyu-maintainable-audit/v1",
        "cycle": bundle.cycle,
        "label": bundle.label,
        "cycleRuntime": runtime,
        "cycleInfo": cycle_info,
        "audit": audit_cycle,
        "scoreLists": {"keyed": {"unresolved": int(unresolved or 0)}},
    }
    catalog = build_catalog(jobs, bundle.cycle)
    catalog["source_module"] = "jobs.json"
    source_candidates = audit_cycle.get("sources") if isinstance(audit_cycle.get("sources"), list) else []
    source_ref = next((str(value) for value in source_candidates if str(value).strip()), f"cycle-{bundle.cycle}-jobs.json")
    observed_at_value = audit_cycle.get("snapshot_date") or cycle_info.get("snapshot_date")
    observed_at = str(observed_at_value).strip() if observed_at_value else None
    positions = build_position_index(
        rows if isinstance(rows, list) else [],
        {"cycle": bundle.cycle, "source_ref": source_ref, "observed_at": observed_at},
    )
    scores = build_scores(bundle.score_lists, bundle.cycle)
    lite_source = _lite_payload(bundle.cycle, rows if isinstance(rows, list) else [], meta if isinstance(meta, dict) else {})
    major_city = _major_city_payload(
        bundle.cycle,
        rows if isinstance(rows, list) else [],
        hashlib.sha256(_json_bytes(lite_source)).hexdigest(),
    )
    return {
        "overview": overview,
        "jobs": jobs,
        "catalog": catalog,
        "positions": positions,
        "audit": audit,
        "scores": scores,
        "major_city": major_city,
    }


_TREND_CITIES = ("合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城")


def _trend_city_key(city: str) -> str | None:
    """Mirror the frontend mapCityFor navigation merge; never mutates source rows."""
    value = str(city or "").strip()
    if not value:
        return None
    if value == "省直":
        return "省直"
    if value == "宿松":
        return "安庆"
    if value == "广德":
        return "宣城"
    for candidate in _TREND_CITIES:
        if value == candidate or value.startswith(candidate):
            return candidate
    return None


def _recruits_of(row: dict[str, Any]) -> int:
    try:
        return int(row.get("num") or row.get("recruits") or 0)
    except (TypeError, ValueError):
        return 0


def _major_city_payload(cycle: str, rows: list[dict[str, Any]], source_sha256: str = "") -> dict[str, object]:
    """Build the exact-key city index from readable ``zy`` candidates.

    The source row and its original major text remain in ``jobs.json``.  This
    derived index only stores counts for the map fast path; every readable
    catalog keyword is retained, and raw city values that cannot be mapped to
    the sixteen prefectures or 省直 stay in ``unmapped``.
    """
    keywords: dict[str, dict[str, object]] = {}
    keyword_labels: dict[str, str] = {}
    typed_rows = [row for row in rows if isinstance(row, dict)]
    for row in typed_rows:
        city_value = str(row.get("city") or row.get("reg") or "").strip() or "未标注"
        city_key = _trend_city_key(city_value)
        recruits = _recruits_of(row)
        readable_keywords = []
        for candidate in extract_major_keywords(row.get("zy")):
            normalized = re.sub(r"\s+", "", candidate).casefold()
            keyword = keyword_labels.setdefault(normalized, candidate)
            readable_keywords.append(keyword)
        for keyword in readable_keywords:
            entry = keywords.setdefault(keyword, {"jobs": 0, "recruits": 0, "cities": {}})
            entry["jobs"] = int(entry.get("jobs") or 0) + 1
            entry["recruits"] = int(entry.get("recruits") or 0) + recruits
            cities = entry["cities"]
            if city_key in _TREND_CITIES or city_key == "省直":
                city = cities.setdefault(city_key, {"jobs": 0, "recruits": 0})
                city["jobs"] += 1
                city["recruits"] += recruits
            else:
                unmapped = entry.setdefault("unmapped", {})
                city = unmapped.setdefault(city_value, {"jobs": 0, "recruits": 0})
                city["jobs"] += 1
                city["recruits"] += recruits
    return {
        "schema": "wanyu-maintainable-major-city/v1",
        "cycle": str(cycle),
        "source_module": f"data/cycles/{cycle}/jobs_lite.json",
        "source_sha256": str(source_sha256 or ""),
        "rows_total": len(typed_rows),
        "keyword_count": len(keywords),
        "semantics": "keywords[k].cities counts source rows matching readable keyword k; unmapped preserves raw city values",
        "unknown_policy": "无法归入十六市或省直的城市值保留在关键词级 unmapped，不静默丢弃",
        "keywords": {key: keywords[key] for key in sorted(keywords, key=lambda value: (value.casefold(), value))},
    }


def _city_trend(rows_by_cycle: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, dict[str, dict[str, int]]], dict[str, dict[str, int]]]:
    """Aggregate three-year city trends; rows that cannot be mapped stay in unmapped, never dropped."""
    trend: dict[str, dict[str, dict[str, int]]] = {}
    unmapped: dict[str, dict[str, int]] = {}
    for cycle, rows in rows_by_cycle.items():
        mapped: dict[str, dict[str, int]] = {}
        raw: dict[str, int] = {}
        for row in rows:
            city_value = str(row.get("city") or row.get("reg") or "").strip() or "未标注"
            key = _trend_city_key(city_value)
            if key is None:
                raw[city_value] = raw.get(city_value, 0) + 1
                continue
            slot = mapped.setdefault(key, {"posts": 0, "recruits": 0})
            slot["posts"] += 1
            slot["recruits"] += _recruits_of(row)
        for city, slot in mapped.items():
            bucket = trend.setdefault(city, {"posts": {}, "recruits": {}})
            bucket["posts"][cycle] = slot["posts"]
            bucket["recruits"][cycle] = slot["recruits"]
        if raw:
            unmapped[cycle] = dict(sorted(raw.items()))
    return trend, unmapped


def _derived_payload(
    cycle: str,
    rows_by_cycle: dict[str, list[dict[str, Any]]],
    cycle_entries_by_cycle: dict[str, dict[str, object]],
    trend: dict[str, dict[str, dict[str, int]]],
    unmapped: dict[str, dict[str, int]],
) -> dict[str, object]:
    entry = cycle_entries_by_cycle[cycle]
    posts = int(entry.get("posts") or 0)
    recruits = int(entry.get("recruits") or 0)
    cycles = list(rows_by_cycle)
    index = cycles.index(cycle)
    if index > 0:
        prev_cycle = cycles[index - 1]
        prev = cycle_entries_by_cycle[prev_cycle]
        prev_posts = int(prev.get("posts") or 0)
        prev_recruits = int(prev.get("recruits") or 0)
        jobs_delta = posts - prev_posts
        recruits_delta = recruits - prev_recruits
        vs_prev: dict[str, object] = {
            "base_cycle": prev_cycle,
            "jobs": posts,
            "jobs_prev": prev_posts,
            "jobs_delta": jobs_delta,
            "jobs_delta_pct": round(jobs_delta * 100 / prev_posts, 1) if prev_posts else None,
            "recruits": recruits,
            "recruits_prev": prev_recruits,
            "recruits_delta": recruits_delta,
            "recruits_delta_pct": round(recruits_delta * 100 / prev_recruits, 1) if prev_recruits else None,
        }
    else:
        vs_prev = {
            "base_cycle": None, "jobs": posts, "jobs_prev": None, "jobs_delta": None, "jobs_delta_pct": None,
            "recruits": recruits, "recruits_prev": None, "recruits_delta": None, "recruits_delta_pct": None,
        }
    mix_map: dict[str, dict[str, Any]] = {}
    for row in rows_by_cycle[cycle]:
        exam = str(row.get("exam") or "未标注")
        slot = mix_map.setdefault(exam, {"exam": exam, "posts": 0, "recruits": 0})
        slot["posts"] += 1
        slot["recruits"] += _recruits_of(row)
    mix = [
        {**slot, "post_share": round(slot["posts"] * 100 / posts, 1)}
        for slot in sorted(mix_map.values(), key=lambda item: (-item["posts"], item["exam"]))
    ] if posts else []
    return {
        "schema": "wanyu-maintainable-derived/v1",
        "cycle": cycle,
        "computed_from": ["jobs.json", "site-manifest.json"],
        "source_policy": "派生值全部可由当前源包重算复现;缺失前周期或无法归并的城市保持 null/未归类,不推断为零",
        "vs_prev": vs_prev,
        "mix": mix,
        "city_trend": trend,
        "unmapped_cities": unmapped.get(cycle, {}),
        "review_progress": {"gaps": int(entry.get("gaps") or 0), "score_unresolved": int(entry.get("score_unresolved") or 0)},
    }


def _palette_payload(cycle: str, rows: list[dict[str, Any]]) -> dict[str, object]:
    """Compact command-palette index; references stable IDs, copies no narrative fields."""
    entries = [
        {
            "id": str(row.get("job_id") or row.get("row_id") or row.get("code") or ""),
            "code": str(row.get("code") or ""),
            "unit": str(row.get("unit") or "")[:60],
            "title": str(row.get("zw") or row.get("display_title") or "")[:60],
            "city": str(row.get("city") or row.get("reg") or ""),
            "exam": str(row.get("exam") or ""),
        }
        for row in rows
    ]
    return {
        "schema": "wanyu-maintainable-palette/v1",
        "cycle": cycle,
        "entries": entries,
        "search_policy": "命令面板仅做本地文本匹配;索引引用稳定 ID,岗位原文仍在 jobs.json",
    }


_LITE_ROW_KEYS = (
    "job_id", "code", "city", "reg", "exam", "cycle", "unit", "zw", "zy", "bz", "lb",
    "num", "recruits", "xl", "display_title", "competition_observations",
)
_LITE_META_KEYS = ("cycle", "total", "recruits", "examCounts", "cities", "categories")


def _lite_payload(cycle: str, rows: list[dict[str, Any]], source_meta: dict[str, Any]) -> dict[str, object]:
    """Build the compact search/ranking index; heavy evidence fields stay in jobs.json."""
    lite_rows = [{key: row[key] for key in _LITE_ROW_KEYS if key in row} for row in rows]
    meta = {key: source_meta[key] for key in _LITE_META_KEYS if key in source_meta}
    return {
        "schema": "wanyu-maintainable-jobs-lite/v1",
        "source_module": "jobs.json",
        "cycle": cycle,
        "allMajors": {"meta": meta, "rows": lite_rows},
        "boundary_note": "轻索引只保留检索/榜单/地图所需列;资格、成绩与来源证据字段以 jobs.json 原文为准,详情抽屉按需加载。",
    }


def _global_audit_payload(bundles: dict[str, Any]) -> dict[str, object]:
    """Create a compact, source-backed three-year audit index."""
    first_bundle = bundles[SUPPORTED_CYCLES[0]]
    audit_source = first_bundle.payload.get("threeYearAudit") or {}
    cycle_items = []
    for cycle in SUPPORTED_CYCLES:
        item = copy.deepcopy(bundles[cycle].audit)
        item["score_unresolved"] = _unresolved_score_count(bundles[cycle])
        cycle_items.append(item)
    return {
        "schema": "wanyu-maintainable-audit/v1",
        "generated_on": audit_source.get("generated_on") if isinstance(audit_source, dict) else None,
        "status_definitions": copy.deepcopy((audit_source or {}).get("status_definitions") or {}),
        "evidence_level_definitions": copy.deepcopy((audit_source or {}).get("evidence_level_definitions") or {}),
        "cycles": cycle_items,
        "summary": {
            "cycle_count": len(cycle_items),
            "post_count": sum(int(item.get("posts") or 0) for item in cycle_items),
            "recruit_count": sum(int(item.get("recruits") or 0) for item in cycle_items),
            "gap_count": sum(len(item.get("gaps") or []) for item in cycle_items),
            "unresolved_score_count": sum(int(item.get("score_unresolved") or 0) for item in cycle_items),
            "partial_cycle_count": sum(item.get("evidence_level") == "partial_evidence" for item in cycle_items),
        },
    }


THEME_BOOT = """<script>
    /* 主题引导:先于样式执行,读取持久化选择,避免首帧闪烁。 */
    (function () {
      var theme = 'light';
      try {
        var stored = localStorage.getItem('wanyu.v15.theme');
        var query = new URLSearchParams(location.search).get('theme');
        if (query === 'dark' || query === 'light') theme = query;
        else if (stored === 'dark' || stored === 'light') theme = stored;
        else if (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches) theme = 'dark';
        document.documentElement.dataset.theme = theme;
      } catch (error) { document.documentElement.dataset.theme = 'light'; }
    })();
  </script>"""


SW_BOOT = """<script>
  if ('serviceWorker' in navigator) {
    addEventListener('load', function () { navigator.serviceWorker.register('sw.js').catch(function () {}); });
  }
</script>"""


def _index_html(three_year: dict[str, object] | None = None) -> str:
    """Render the app shell; three-year totals are computed at build time, never hand-written."""
    summary = three_year if isinstance(three_year, dict) else {}
    posts = int(summary.get("post_count") or 0)
    recruits = int(summary.get("recruit_count") or 0)
    band_stats = f"{posts:,} 岗 · {recruits:,} 人 · 来源均可本地核对" if posts and recruits else "三年岗位行与证据边界 · 按周期加载"
    return f"""<!doctype html>
<html lang="zh-CN" data-site="wanyu-maintainable" data-schema="{SCHEMA}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="description" content="皖域择岗三年周期长期维护站，数据按周期外置并可回到审计边界。">
  <title>皖域择岗 · 长期维护站</title>
  {THEME_BOOT}
  <link rel="manifest" href="manifest.webmanifest">
  <meta name="theme-color" content="#3a83f7">
  <link rel="icon" href="assets/wanyu-icon.svg?v={RELEASE}" type="image/svg+xml">
  <link rel="stylesheet" href="assets/maintainable-tokens.css?v={RELEASE}">
  <link rel="stylesheet" href="assets/maintainable-site.css?v={RELEASE}">
  <link rel="stylesheet" href="assets/v17-ui-upgrade.css?v={RELEASE}">
  <link rel="stylesheet" href="assets/v17-search.css?v={RELEASE}">
  <link rel="stylesheet" href="assets/v17-tools.css?v={RELEASE}">
  <link rel="stylesheet" href="assets/v17-exam-picker.css?v={RELEASE}">
</head>
<body>
  <div id="maintainable-app" class="maintainable-app">
    <a class="maintain-skip-link" href="#maintain-main">跳到主内容</a>
    <header class="maintain-header">
      <div class="maintain-header__inner">
        <a class="maintain-brand" href="#overview" aria-label="返回全省总览">
          <span class="maintain-brand__mark">皖</span>
          <span><strong>皖域择岗</strong><small>LONG-LIVED DATA WORKBENCH</small></span>
        </a>
        <div class="maintain-cycle-picker" id="maintain-cycle-picker" aria-label="选择数据周期"></div>
        <div class="maintain-header__tools">
          <span id="maintain-offline-badge" class="maintain-offline-badge" hidden>离线缓存</span>
          <button id="maintain-theme-toggle" class="maintain-theme-toggle" type="button" aria-label="切换深浅主题">◐</button>
        </div>
      </div>
      <div class="maintain-header__sub">
        <nav class="maintain-nav" aria-label="维护站导航">
          <a href="#overview" data-maintain-view="overview">周期总览</a>
          <a href="#cycle_compare" data-maintain-view="cycle_compare">三年对照</a>
          <a href="#jobs_map" data-maintain-view="jobs_map">岗位地图</a>
          <a href="#salary_map" data-maintain-view="salary_map">待遇地图</a>
          <a href="#jobs_ranking" data-maintain-view="jobs_ranking">岗位榜单</a>
          <a href="#jobs_search" data-maintain-view="jobs_search">岗位检索</a>
          <a href="#saved" data-maintain-view="saved">收藏与快照</a>
          <a href="#data_boundary" data-maintain-view="data_boundary">数据审计</a>
          <a href="#help" data-maintain-view="help">使用说明</a>
          <a href="#changelog" data-maintain-view="changelog">更新日志</a>
        </nav>
        <span id="maintain-status" class="maintain-status" role="status" aria-live="polite">正在读取数据清单…</span>
      </div>
      <span class="maintain-scroll-progress" aria-hidden="true"></span>
    </header>
    <main id="maintain-main" class="maintain-main" aria-live="polite"></main>
    <section class="maint-cta" aria-labelledby="maint-cta-title">
      <span class="maint-cta__glow" aria-hidden="true"></span>
      <div class="maint-cta__inner">
        <p class="maint-eyebrow"><span class="maint-eyebrow__index">下一步</span>从这里开始</p>
        <h2 id="maint-cta-title">拿不准就先看数据边界，<br>想好了就直接查岗位。</h2>
        <div class="maint-cta__actions">
          <a class="maint-cta__primary" href="#jobs_search" data-maintain-view="jobs_search">打开岗位检索 <i class="maint-cta__arrow">→</i></a>
          <a class="maint-cta__ghost" href="#data_boundary" data-maintain-view="data_boundary">查看数据审计</a>
        </div>
        <p class="maint-cta__stats">2024—2026 · {band_stats}</p>
      </div>
    </section>
    <footer class="maintain-footer">
      <span>外置 JSON 维护站 · 数据与界面分离</span>
      <span>单文件离线快照：<a href="../皖域择岗总览.html">打开回退入口</a></span>
    </footer>
  </div>
  <script src="assets/maintainable-data.js?v={RELEASE}"></script>
  <script src="assets/maintainable-major-city.js?v={RELEASE}"></script>
  <script src="assets/maintainable-user-store.js?v={RELEASE}"></script>
  <script src="assets/v17-tools.js?v={RELEASE.lstrip('v')}-supplement-evidence"></script>
  <script type="module" src="assets/maintainable-site.js?v={RELEASE.lstrip('v')}-supplement-evidence"></script>
  {SW_BOOT}
</body>
</html>
"""


def build_maintainable_site(root: Path = ROOT, output_dir: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    """Build and return the manifest for the external-data maintenance site."""
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    bundles = build_unified_bundles(root)
    data_entries: list[dict[str, object]] = []
    snapshot_date = _stable_snapshot_date(bundles)
    previous_cycle: str | None = None
    previous_rows: list[dict[str, object]] = []
    rows_by_cycle: dict[str, list[dict[str, object]]] = {}
    meta_by_cycle: dict[str, dict[str, object]] = {}
    for cycle in SUPPORTED_CYCLES:
        bundle = bundles[cycle]
        modules = _module_payloads(bundle)
        score_payload = modules.pop("scores", None)
        current_rows = modules["jobs"].get("allMajors", {}).get("rows", []) if isinstance(modules["jobs"].get("allMajors"), dict) else []
        rows_by_cycle[cycle] = [row for row in current_rows if isinstance(row, dict)]
        modules["changes"] = build_change_payload(previous_cycle, cycle, previous_rows, current_rows if isinstance(current_rows, list) else [])
        if isinstance(score_payload, dict):
            score_path = output_dir / "archive" / "scores" / f"{cycle}.json"
            _write_json(score_path, score_payload)
            legacy_score_path = output_dir / "data" / "cycles" / cycle / "scores.json"
            if legacy_score_path.is_file():
                legacy_score_path.unlink()
        module_entries: dict[str, dict[str, object]] = {}
        for module_name, module_payload in modules.items():
            data_path = output_dir / "data" / "cycles" / cycle / f"{module_name}.json"
            encoded = _write_json(data_path, module_payload)
            module_entries[module_name] = {
                "data": f"data/cycles/{cycle}/{module_name}.json",
                "bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "schema": module_payload.get("schema"),
            }
        jobs_payload = modules["jobs"]
        meta = jobs_payload.get("allMajors", {}).get("meta", {}) if isinstance(jobs_payload.get("allMajors"), dict) else {}
        meta_by_cycle[cycle] = meta if isinstance(meta, dict) else {}
        audit_cycle = bundle.audit if isinstance(bundle.audit, dict) else {}
        unresolved = _unresolved_score_count(bundle, modules["audit"])
        data_entries.append({
            "cycle": cycle,
            "label": bundle.label,
            "data": module_entries["jobs"]["data"],
            "modules": module_entries,
            "posts": int(meta.get("total") or 0),
            "recruits": int(meta.get("recruits") or 0),
            "status": audit_cycle.get("dominant_status") or audit_cycle.get("status") or "verified",
            "gaps": len(audit_cycle.get("gaps") or []),
            "score_unresolved": int(unresolved or 0),
            "bytes": module_entries["jobs"]["bytes"],
            "sha256": module_entries["jobs"]["sha256"],
        })
        previous_cycle = cycle
        previous_rows = current_rows if isinstance(current_rows, list) else []

    cycle_entries_by_cycle = {str(entry.get("cycle")): entry for entry in data_entries}
    trend, unmapped = _city_trend(rows_by_cycle)
    for cycle in SUPPORTED_CYCLES:
        derived = _derived_payload(cycle, rows_by_cycle, cycle_entries_by_cycle, trend, unmapped)
        derived_path = output_dir / "data" / "cycles" / cycle / "derived.json"
        derived_encoded = _write_json(derived_path, derived)
        cycle_entries_by_cycle[cycle]["modules"]["derived"] = {
            "data": f"data/cycles/{cycle}/derived.json",
            "bytes": len(derived_encoded),
            "sha256": hashlib.sha256(derived_encoded).hexdigest(),
            "schema": derived.get("schema"),
        }
        palette = _palette_payload(cycle, rows_by_cycle[cycle])
        palette_path = output_dir / "data" / "cycles" / cycle / "palette.json"
        palette_encoded = _write_json(palette_path, palette)
        cycle_entries_by_cycle[cycle]["modules"]["palette"] = {
            "data": f"data/cycles/{cycle}/palette.json",
            "bytes": len(palette_encoded),
            "sha256": hashlib.sha256(palette_encoded).hexdigest(),
            "schema": palette.get("schema"),
        }
        lite = _lite_payload(cycle, rows_by_cycle[cycle], meta_by_cycle.get(cycle, {}))
        lite_path = output_dir / "data" / "cycles" / cycle / "jobs_lite.json"
        lite_encoded = _write_json(lite_path, lite)
        cycle_entries_by_cycle[cycle]["modules"]["jobs_lite"] = {
            "data": f"data/cycles/{cycle}/jobs_lite.json",
            "bytes": len(lite_encoded),
            "sha256": hashlib.sha256(lite_encoded).hexdigest(),
            "schema": lite.get("schema"),
        }

    audit_path = output_dir / "data" / "audit" / "three-year.json"
    audit_payload = _global_audit_payload(bundles)
    audit_encoded = _write_json(audit_path, audit_payload)
    review_queue_path = output_dir / "data" / "audit" / "review-queue.json"
    review_queue_encoded = _write_json(review_queue_path, build_review_queue(bundles, audit_payload))
    map_path = output_dir / "data" / "map" / "anhui.json"
    map_payload = build_map_payload(root)
    map_encoded = _write_json(map_path, map_payload)
    salary_path = output_dir / "data" / "salary" / "anhui.json"
    salary_payload = _salary_payload()
    salary_encoded = _write_json(salary_path, salary_payload)
    supplement_payload: dict[str, Any] | None = None
    supplement_encoded: bytes | None = None
    supplement_dir = root / "source_data" / "supplement_20260904"
    if supplement_dir.is_dir():
        supplement_payload = build_supplement_evidence(root)
        supplement_path = output_dir / "data" / "audit" / "supplement-20260904.json"
        supplement_encoded = _write_json(supplement_path, supplement_payload)

    manifest: dict[str, object] = {
        "schema": SCHEMA,
        "release": RELEASE,
        "snapshot_date": snapshot_date,
        "default_cycle": "2026",
        "cycles": data_entries,
        "audit": {
            "data": "data/audit/three-year.json",
            "bytes": len(audit_encoded),
            "sha256": hashlib.sha256(audit_encoded).hexdigest(),
        },
        "review_queue": {
            "data": "data/audit/review-queue.json",
            "bytes": len(review_queue_encoded),
            "sha256": hashlib.sha256(review_queue_encoded).hexdigest(),
        },
        "map": {
            "data": "data/map/anhui.json",
            "bytes": len(map_encoded),
            "sha256": hashlib.sha256(map_encoded).hexdigest(),
            "schema": map_payload.get("schema"),
            "source": map_payload.get("source_module"),
        },
        "salary": {
            "data": "data/salary/anhui.json",
            "bytes": len(salary_encoded),
            "sha256": hashlib.sha256(salary_encoded).hexdigest(),
            "schema": salary_payload.get("schema"),
        },
        "source_chain": {
            "cycle_bundles": "tools/anhui_web/unified_cycle_bundle.py",
            "audit": "tools/anhui_web/data/three_year_audit.json",
            "map_geometry": "tools/anhui_web/data/anhui_340000_full.json",
            "salary": "source_docs/安徽全省16市本科普通岗全包分析_完善版(1).docx",
            "single_file_fallback": "../皖域择岗总览.html",
        },
        "maintenance": {
            "data_is_external": True,
            "load_policy": "按周期懒加载并缓存",
            "module_policy": "overview / jobs / catalog / positions / changes / audit 分层；scores 仅作为 archive/scores 随包归档，不进入 manifest 或客户端主数据池；岗位原文只在 jobs 模块；地图几何单独外置",
            "unknown_policy": "未发布或无法唯一匹配的值保持空值，不推断为零",
        },
    }
    if supplement_payload is not None and supplement_encoded is not None:
        manifest["supplement"] = {
            "data": "data/audit/supplement-20260904.json",
            "bytes": len(supplement_encoded),
            "sha256": hashlib.sha256(supplement_encoded).hexdigest(),
            "schema": supplement_payload.get("schema"),
            "source": "source_data/supplement_20260904",
        }
        manifest["source_chain"]["supplement_evidence"] = "tools/anhui_web/build_supplement_evidence.py"
    _write_json(output_dir / "data" / "site-manifest.json", manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(_index_html(audit_payload.get("summary")), encoding="utf-8")
    assets = output_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("maintainable-site.js", "maintainable-site.css", "v17-ui-upgrade.css", "maintainable-tokens.css", "maintainable-data.js", "maintainable-major-city.js", "maintainable-user-store.js", "v17-exam-picker.css", "v17-search.css", "v17-tools.css", "v17-tools.js"):
        shutil.copyfile(TEMPLATE_DIR / name, assets / name)
    # PWA 离线层：SW 与应用清单位于站点根（作用域即站点根）
    shutil.copyfile(TEMPLATE_DIR / "maintainable-sw.js", output_dir / "sw.js")
    shutil.copyfile(TEMPLATE_DIR / "maintainable.webmanifest", output_dir / "manifest.webmanifest")
    shutil.copyfile(TEMPLATE_DIR / "wanyu-icon.svg", assets / "wanyu-icon.svg")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="构建外置 JSON 驱动的皖域择岗长期维护站")
    parser.add_argument("--root", type=Path, default=ROOT, help="项目根目录")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="维护站输出目录")
    args = parser.parse_args()
    result = build_maintainable_site(args.root, args.output_dir)
    print(json.dumps({"output": str(args.output_dir.resolve()), "cycles": result["cycles"]}, ensure_ascii=False))
