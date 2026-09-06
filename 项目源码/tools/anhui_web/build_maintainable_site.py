"""Build the long-lived HTTP site from the same audited cycle bundles.

The single-file workbench remains the offline snapshot.  This builder keeps
the maintainable site's HTML small and writes one versioned JSON payload per
cycle, so data refreshes do not require hand-editing the application shell.
"""

from __future__ import annotations

import argparse
import collections
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
    from .build_major_index import build as build_major_index_index
    from .build_map import build_map_payload
    from .build_position_index import _source_status, build_position_index
    from .build_review_queue import build_review_queue
    from .build_scores import build_scores
    from .build_supplement_evidence import build_supplement_evidence
    from .invariants import BuildInvariantError, require_int
    from .record_lifecycle import RECORD_STATUS_MODEL, apply_overrides, load_overrides, split_records
    from .single_file_site import _payload_for
    from .unified_cycle_bundle import SUPPORTED_CYCLES, build_unified_bundles
except ImportError:  # pragma: no cover - supports direct script execution
    from tools.anhui_web.build_catalog import build_catalog, extract_major_keywords
    from tools.anhui_web.build_changes import build_change_payload
    from tools.anhui_web.build_major_index import build as build_major_index_index
    from tools.anhui_web.build_map import build_map_payload
    from tools.anhui_web.build_position_index import _source_status, build_position_index
    from tools.anhui_web.build_review_queue import build_review_queue
    from tools.anhui_web.build_scores import build_scores
    from tools.anhui_web.build_supplement_evidence import build_supplement_evidence
    from tools.anhui_web.invariants import BuildInvariantError, require_int
    from tools.anhui_web.record_lifecycle import RECORD_STATUS_MODEL, apply_overrides, load_overrides, split_records
    from tools.anhui_web.single_file_site import _payload_for
    from tools.anhui_web.unified_cycle_bundle import SUPPORTED_CYCLES, build_unified_bundles


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
# RC3：builder 的默认输出=部署树（OUTPUT 侧，O-ALLOWED-OUTPUT 标记豁免）；
# 正式发布走 release.py 显式传参。
DEFAULT_OUTPUT = ROOT.parent / "网站"  # O:OUTPUT-SIDE
SCHEMA = "wanyu-maintainable-site/v3"
# D(2026-09-05)+RC2(H): 版本唯一真源 = 项目源码/release.json，三字段各用各的，
# 禁止从 release 推导 asset 版本（不得 RELEASE.lstrip("v")）。
_RELEASE_DOC = json.loads((Path(__file__).resolve().parents[2] / "release.json").read_text(encoding="utf-8"))
RELEASE = _RELEASE_DOC["release"]
ASSET_VERSION = _RELEASE_DOC["asset_version"]
SW_VERSION = _RELEASE_DOC["service_worker_version"]

# 学历（xl）口径归一：源表同义表述收敛为规范值（2026-09-06 数据质量修复）。
# 仅做等义归一（大专→专科、硕士研究生及以上→研究生等），不改变门槛语义。
_XL_NORMALIZE_MAP = {
    "本科及以上": "本科及以上", "大学本科及以上": "本科及以上",
    "本科（学士）及以上": "本科及以上", "本科": "本科及以上",
    "仅限本科": "仅限本科", "研究生": "研究生",
    "硕士研究生及以上": "研究生", "仅限硕士研究生": "仅限硕士研究生",
    "研究生及以上": "研究生", "仅限研究生": "仅限研究生",
    "专科及以上": "专科及以上", "大专及以上": "专科及以上",
    "大专及本科": "专科及以上", "大专": "专科及以上",
    "高中（中专）及以上": "高中（中专）及以上", "博士研究生": "博士研究生",
}


def normalize_xl(value: Any) -> str:
    """归一学历表述；未登记的原样返回（宁缺勿错，绝不臆测）。"""
    raw = str(value or "").strip()
    if not raw:
        return ""
    return _XL_NORMALIZE_MAP.get(raw.replace(" ", ""), raw)


def _apply_xl_normalization(rows: list) -> int:
    changed = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        old = row.get("xl")
        new = normalize_xl(old)
        if new != old:
            row["xl"] = new
            changed += 1
    return changed


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
    """Read the authoritative unresolved score count without binding rows.

    v17.8.5-RC3(B3)：fail-closed。scoreLists.keyed.unresolved 缺失时才允许回退
    bundle.audit.coverage.score_unresolved；两条路径都缺失或值非法 → 直接抛错，
    绝不静默回退成 0。
    """
    source = payload if isinstance(payload, dict) else getattr(bundle, "payload", {})
    score_lists = source.get("scoreLists") if isinstance(source, dict) else {}
    keyed = score_lists.get("keyed") if isinstance(score_lists, dict) else {}
    unresolved = keyed.get("unresolved") if isinstance(keyed, dict) else None
    fallback_path = "scoreLists.keyed.unresolved"
    if unresolved is None:
        audit = getattr(bundle, "audit", {})
        coverage = audit.get("coverage") if isinstance(audit, dict) else {}
        unresolved = coverage.get("score_unresolved")
        fallback_path = "audit.coverage.score_unresolved"
    if unresolved is None:
        raise BuildInvariantError(
            f"{getattr(bundle, 'cycle', '?')}: unresolved 成绩计数缺失（{fallback_path} 与审计覆盖层都无值），拒绝构建"
        )
    if isinstance(unresolved, list):
        return len(unresolved)
    return require_int(unresolved, f"{getattr(bundle, 'cycle', '?')} {fallback_path}")


def _score_resolution_total(bundle: Any) -> int:
    """Total resolved score collisions recorded in the cycle's keyed score lists.

    Resolution blocks are written as ``resolution_<date>`` entries by the D2
    resolution pipeline; each carries ``attributed``/``still_ambiguous`` counts.
    """
    keyed = (getattr(bundle, "score_lists", {}) or {}).get("keyed") or {}
    cycle = getattr(bundle, "cycle", "?")
    total = 0
    for key, value in keyed.items():
        if isinstance(key, str) and key.startswith("resolution_") and isinstance(value, dict):
            # v17.8.6-H：resolution 块缺 attributed 字段必须 fail-closed，
            # 禁止 int(x or 0) 把缺失/None 静默计成 0（fail-open）。
            total += require_int(value.get("attributed"), f"{cycle} {key}.attributed")
    return total


def _compute_cycle_meta(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Row-derived cycle meta (single source of the projection formulas).

    标定纪律（v17.8.5-RC2）：这些公式必须先在「含排除行的全量行」上复现 bundle
    原始 meta，才允许切换 active 口径（见 _lifecycle_meta 的断言）。
    """
    return {
        "total": len(rows),
        "recruits": sum(int(r.get("num") or 0) for r in rows),
        "examCounts": dict(collections.Counter(str(r.get("exam")) for r in rows)),
        "compJoined": sum(1 for r in rows if r.get("jf") is not None),
        "directed": sum(1 for r in rows if (r.get("dir") or r.get("dirText"))),
        "hukou": sum(1 for r in rows if r.get("hukou")),
        "scoreCoverage": {
            "adv": sum(1 for r in rows if (r.get("competition_observations") or {}).get("examinees", {}).get("value") is not None),
            "bm": sum(1 for r in rows if r.get("bm") is not None),
            "hg": sum(1 for r in rows if r.get("hg") is not None),
            "jf": sum(1 for r in rows if r.get("jf") is not None),
            "hire": sum(1 for r in rows if r.get("hire") is not None),
            "line": sum(1 for r in rows if isinstance(r.get("line"), (int, float)) and r.get("line", 0) > 0),
            "perExam": {
                exam: {
                    "total": sum(1 for r in rows if str(r.get("exam")) == exam),
                    "adv": sum(1 for r in rows if str(r.get("exam")) == exam and (r.get("competition_observations") or {}).get("examinees", {}).get("value") is not None),
                    "bm": sum(1 for r in rows if str(r.get("exam")) == exam and r.get("bm") is not None),
                    "line": sum(1 for r in rows if str(r.get("exam")) == exam and isinstance(r.get("line"), (int, float)) and r.get("line", 0) > 0),
                } for exam in ("省考", "国考", "事业编")
            },
        },
    }


_LIFECYCLE_CALIBRATION_KEYS = ("examCounts", "directed", "hukou", "recruits", "compJoined")
_LIFECYCLE_EXAMS = ("省考", "国考", "事业编")


def _lifecycle_meta(
    raw_rows: list[dict[str, Any]],
    active_rows: list[dict[str, Any]],
    excluded_rows: list[dict[str, Any]],
    carryover_meta: dict[str, Any],
    calibration_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Active-scope meta derived from rows; pass-through when a cycle has no exclusions.

    - carryover_meta：cities/categories/cycle/scoreSources 等非行级字段的来源
      （= bundle 原始 meta；RC2 再生路径已随方案 A 退役）。
    - calibration_meta：bundle 原始 meta。排除集非空时，行级公式必须先在 raw
      全量行上复现它（否则中止构建），再切换 active 口径。
    """
    if not excluded_rows:
        passed = _summary_meta(carryover_meta)
        # 无排除周期同样统一 wanyu-record-status/v1 形状（raw==active），
        # 与 2026 形状一致，避免overview 读到无口径的裸 total。
        passed["raw_total"] = len(raw_rows)
        passed["excluded"] = len(excluded_rows)
        passed["record_status_model"] = RECORD_STATUS_MODEL
        return passed
    if calibration_meta is not None:
        raw_meta = _compute_cycle_meta(raw_rows)
        for key in _LIFECYCLE_CALIBRATION_KEYS:
            if raw_meta[key] != calibration_meta.get(key):
                raise BuildInvariantError(
                    f"生命周期标定失败：{key} 公式在全量行上未能复现 bundle 原始 meta "
                    f"({raw_meta[key]!r} != {calibration_meta.get(key)!r})"
                )
        raw_cov = raw_meta["scoreCoverage"]
        base_cov = calibration_meta.get("scoreCoverage") or {}
        for key in ("adv", "bm", "hg", "jf"):
            if raw_cov[key] != base_cov.get(key):
                raise BuildInvariantError(
                    f"生命周期标定失败：scoreCoverage.{key} 在全量行上不符 "
                    f"({raw_cov[key]!r} != {base_cov.get(key)!r})"
                )
        for exam in _LIFECYCLE_EXAMS:
            expected = (base_cov.get("perExam") or {}).get(exam, {}).get("total")
            if raw_cov["perExam"][exam]["total"] != expected:
                raise BuildInvariantError(
                    f"生命周期标定失败：perExam[{exam}].total 在全量行上不符 "
                    f"({raw_cov['perExam'][exam]['total']!r} != {expected!r})"
                )
    active_meta = _compute_cycle_meta(active_rows)
    hire_source = (calibration_meta or carryover_meta).get("scoreCoverage") or {}
    # hire 是构建期录用名单投影（行级无此字段），排除集不改变它：保留现值并留痕。
    active_meta["scoreCoverage"]["hire"] = hire_source.get("hire")
    active_meta["raw_total"] = len(raw_rows)
    active_meta["excluded"] = len(excluded_rows)
    active_meta["record_status_model"] = RECORD_STATUS_MODEL
    merged = dict(active_meta)
    for key, value in (carryover_meta or {}).items():
        if key not in merged:
            merged[key] = copy.deepcopy(value)
    return merged


def _module_payloads(bundle: Any) -> dict[str, dict[str, object]]:
    """Project one audited bundle into independently replaceable data modules.

    v17.8.5-RC2 纪律：进入业务派生前先完成 record_status 生命周期应用与
    raw/active/excluded 三分；**所有用户口径模块一律只吃 active_rows**，
    jobs.json 保留 raw 行（审计真源，含排除行）。
    """
    payload = _payload_for(bundle)
    all_majors = payload.get("allMajors") if isinstance(payload.get("allMajors"), dict) else {}
    base_meta = all_majors.get("meta") if isinstance(all_majors.get("meta"), dict) else {}
    raw_rows = [row for row in (all_majors.get("rows") if isinstance(all_majors.get("rows"), list) else []) if isinstance(row, dict)]
    rows = apply_overrides(raw_rows, load_overrides(ROOT), bundle.cycle)
    _apply_xl_normalization(rows)
    raw_rows, active_rows, excluded_rows = split_records(rows)
    meta = _lifecycle_meta(raw_rows, active_rows, excluded_rows, base_meta, calibration_meta=base_meta if excluded_rows else None)
    runtime = copy.deepcopy(payload.get("cycleRuntime") or {})
    # RC3-L：三周期统一行数结构（2024: 10017/10017、2025: 10150/10150、2026: 8401/8511）。
    runtime["row_count"] = len(active_rows)
    runtime["raw_row_count"] = len(raw_rows)
    runtime["score_unresolved"] = _unresolved_score_count(bundle, payload)
    cycle_info = copy.deepcopy(payload.get("cycleInfo") or {})
    audit_cycle = copy.deepcopy(bundle.audit) if isinstance(bundle.audit, dict) else {}
    unresolved = _unresolved_score_count(bundle, payload)
    audit_summary = {
        "status": audit_cycle.get("status") or audit_cycle.get("dominant_status") or "verified",
        "evidence_level": audit_cycle.get("evidence_level") or "partial_evidence",
        "gap_count": len(audit_cycle.get("gaps") or []),
        "score_unresolved": int(unresolved or 0),
    }
    resolved_total = _score_resolution_total(bundle)
    if resolved_total:
        audit_summary["resolved_score_count"] = resolved_total
    overview = {
        "schema": "wanyu-maintainable-overview/v1",
        "cycle": bundle.cycle,
        "label": bundle.label,
        "cycleRuntime": runtime,
        "cycleInfo": cycle_info,
        "allMajors": {"meta": copy.deepcopy(meta)},
        "auditSummary": audit_summary,
    }
    jobs = {
        "schema": "wanyu-maintainable-jobs/v1",
        "cycle": bundle.cycle,
        "label": bundle.label,
        "cycleRuntime": copy.deepcopy(runtime),
        "allMajors": {
            "meta": copy.deepcopy(meta),
            "rows": raw_rows,
        },
    }
    audit = {
        "schema": "wanyu-maintainable-audit/v1",
        "cycle": bundle.cycle,
        "label": bundle.label,
        "cycleRuntime": copy.deepcopy(runtime),
        "cycleInfo": cycle_info,
        "audit": audit_cycle,
        "scoreLists": {"keyed": {"unresolved": int(unresolved or 0)}},
    }
    catalog = build_catalog({"allMajors": {"meta": meta, "rows": active_rows}}, bundle.cycle)
    catalog["source_module"] = "jobs.json"
    source_candidates = audit_cycle.get("sources") if isinstance(audit_cycle.get("sources"), list) else []
    source_ref = next((str(value) for value in source_candidates if str(value).strip()), f"cycle-{bundle.cycle}-jobs.json")
    observed_at_value = audit_cycle.get("snapshot_date") or cycle_info.get("snapshot_date")
    observed_at = str(observed_at_value).strip() if observed_at_value else None
    positions = build_position_index(
        active_rows,
        {"cycle": bundle.cycle, "source_ref": source_ref, "observed_at": observed_at},
    )
    scores = build_scores(bundle.score_lists, bundle.cycle)
    lite_source = _lite_payload(
        bundle.cycle,
        active_rows,
        meta,
        job_index={str(r.get("job_id") or r.get("row_id")): i for i, r in enumerate(raw_rows)},
        source_info={
            "source_ref": source_ref,
            "observed_at": observed_at,
            "evidence_note": "详情展示源字段；目录清洗不覆盖原始岗位文本",
        },
    )
    major_city = _major_city_payload(
        bundle.cycle,
        active_rows,
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
    # A4-B1：详情抽屉所需列并入 lite（打开详情零整包下载；来源证据为周期级登记）。
    # source_note 全文不进 lite（抽屉只做官方/非官方分类），行上仅带一位分类码 ss：
    # v=verified(官方) / b=source_bundle(有来源说明) / d=derived(无)——镜像 _source_status。
    "xw", "xz", "age", "score_observation", "title_status", "bm",
)
_LITE_SOURCE_CODE = {"verified": "v", "source_bundle": "b", "derived": "d"}
_LITE_META_KEYS = ("cycle", "total", "recruits", "examCounts", "cities", "categories")


def _lite_payload(
    cycle: str,
    rows: list[dict[str, Any]],
    source_meta: dict[str, Any],
    job_index: dict[str, int] | None = None,
    source_info: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Build the compact search/ranking index; heavy evidence fields stay in jobs.json.

    v17.8.5-RC2：调用方必须传 active 行（jobs_lite 天然 active-only）；
    生命周期元数据（raw_total/excluded/record_status_model）随源 meta 透传。
    A4-B1：行级补 xw/xz/age/score_observation/title_status/bm/source_note 与
    ji（jobs.json 行号，供前端重建来源定位）；周期级来源登记（source_ref/
    observed_at/evidence_note）经 source_info 进 meta，避免每行复制证据对象。
    """
    lite_rows: list[dict[str, Any]] = []
    for row in rows:
        lite = {key: row[key] for key in _LITE_ROW_KEYS if key in row}
        if job_index is not None:
            ji = job_index.get(str(row.get("job_id") or row.get("row_id")))
            if ji is not None:
                lite["ji"] = ji
        lite["ss"] = _LITE_SOURCE_CODE[_source_status(row)[0]]
        lite_rows.append(lite)
    meta = {key: source_meta[key] for key in _LITE_META_KEYS if key in source_meta}
    for key in ("raw_total", "excluded", "record_status_model"):
        if key in source_meta:
            meta[key] = source_meta[key]
    if source_info:
        for key in ("source_ref", "observed_at", "evidence_note"):
            if source_info.get(key) is not None:
                meta[key] = source_info[key]
    return {
        "schema": "wanyu-maintainable-jobs-lite/v1",
        "source_module": "jobs.json",
        "cycle": cycle,
        "allMajors": {"meta": meta, "rows": lite_rows},
        "boundary_note": "轻索引保留检索、榜单、地图与详情抽屉所需列；来源证据为周期级登记（source_ref/材料取得日期），行级 ss=来源分类码（v/b/d）、locator=ji（jobs.json 行号），排除行走整包回退。",
    }


def _global_audit_payload(bundles: dict[str, Any], active_totals: dict[str, int] | None = None) -> dict[str, object]:
    """Create a compact, source-backed three-year audit index.

    summary 的 post_count/recruit_count 是审计口径（raw，含排除行）；
    active_post_count/active_recruit_count 是用户口径（wanyu-metrics/v1），
    由调用方从 manifest 周期条目汇总传入，供首页 CTA 与用户视图使用。
    """
    first_bundle = bundles[SUPPORTED_CYCLES[0]]
    audit_source = first_bundle.payload.get("threeYearAudit") or {}
    cycle_items = []
    for cycle in SUPPORTED_CYCLES:
        item = copy.deepcopy(bundles[cycle].audit)
        item["score_unresolved"] = _unresolved_score_count(bundles[cycle])
        cycle_items.append(item)
    active_totals = active_totals or {}
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
            "active_post_count": int(active_totals.get("active_post_count") or 0),
            "active_recruit_count": int(active_totals.get("active_recruit_count") or 0),
            "scope_note": "post_count/recruit_count 为含排除行（record_status≠active）的 raw 审计口径；active_* 为用户口径（wanyu-metrics/v1）",
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
        var tc = document.querySelector('meta[name="theme-color"]');
        if (tc) tc.content = theme === 'dark' ? '#0f1829' : '#3a83f7';
      } catch (error) { document.documentElement.dataset.theme = 'light'; }
    })();
  </script>"""


SW_BOOT = """<script>
  if ('serviceWorker' in navigator) {
    addEventListener('load', function () { navigator.serviceWorker.register('sw.js').catch(function () {}); });
  }
</script>"""


def _index_html(three_year: dict[str, object] | None = None) -> str:
    """Render the app shell; three-year totals are computed at build time, never hand-written.

    v17.8.5-RC2(H)：与现役 index.html 逐字对齐（og 六件套/考生视角导航/CTA 信任行），
    资产版本全部取 release.json 的 asset_version，禁止从 release 推导。
    """
    summary = three_year if isinstance(three_year, dict) else {}
    # 首页 CTA/og 是用户口径：优先 active 总数，缺失时退回 raw 审计总数
    posts = int(summary.get("active_post_count") or summary.get("post_count") or 0)
    band_stats = f"{posts:,} 岗 · 来源均可本地核对" if posts else "三年岗位行与证据边界 · 按周期加载"
    return f"""<!doctype html>
<html lang="zh-CN" data-site="wanyu-maintainable" data-schema="{SCHEMA}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="description" content="安徽三年公考/事业编岗位数据：按专业、城市、学历找岗位，看竞争比、入围线与各地待遇。数据来自官方公告，来源可核对。">
  <title>皖域择岗 · 安徽公考岗位查询</title>
  {THEME_BOOT}
  <link rel="manifest" href="manifest.webmanifest">
  <meta name="theme-color" content="#3a83f7">
  <meta property="og:type" content="website">
  <meta property="og:title" content="皖域择岗 · 安徽公考岗位查询">
  <meta property="og:description" content="三年 {posts:,} 岗逐岗可溯源：专业匹配亮依据、官方竞争与入围线、报考日历盯节点。未公布不显示，推导亮明依据。">
  <meta property="og:image" content="assets/og-card.png">
  <meta property="og:url" content="https://wan.kaogong.art/maintainable/">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="assets/wanyu-icon.svg?v={ASSET_VERSION}" type="image/svg+xml">
  <link rel="stylesheet" href="assets/maintainable-tokens.css?v={ASSET_VERSION}">
  <link rel="stylesheet" href="assets/maintainable-site.css?v={ASSET_VERSION}">
  <link rel="stylesheet" href="assets/v17-ui-upgrade.css?v={ASSET_VERSION}">
  <link rel="stylesheet" href="assets/v17-search.css?v={ASSET_VERSION}">
  <link rel="stylesheet" href="assets/v17-tools.css?v={ASSET_VERSION}">
  <link rel="stylesheet" href="assets/v17-exam-picker.css?v={ASSET_VERSION}">
</head>
<body>
  <div id="maintainable-app" class="maintainable-app">
    <a class="maintain-skip-link" href="#maintain-main">跳到主内容</a>
    <header class="maintain-header">
      <div class="maintain-header__inner">
        <a class="maintain-brand" href="#overview" aria-label="返回全省总览">
          <span class="maintain-brand__mark">皖</span>
          <span><strong>皖域择岗</strong><small>安徽公考岗位查询</small></span>
        </a>
        <div class="maintain-cycle-picker" id="maintain-cycle-picker" aria-label="选择数据周期"></div>
        <div class="maintain-header__tools">
          <span id="maintain-offline-badge" class="maintain-offline-badge" hidden>离线缓存</span>
          <button id="maintain-theme-toggle" class="maintain-theme-toggle" type="button" aria-label="切换深浅主题">◐</button>
        </div>
      </div>
      <div class="maintain-header__sub">
        <nav class="maintain-nav" aria-label="维护站导航">
          <a href="#overview" data-maintain-view="overview">总览</a>
          <a href="#jobs_search" data-maintain-view="jobs_search">找岗位</a>
          <a href="#match" data-maintain-view="match">为我匹配</a>
          <a href="#jobs_map" data-maintain-view="jobs_map">岗位地图</a>
          <a href="#salary_map" data-maintain-view="salary_map">待遇对比</a>
          <a href="#jobs_ranking" data-maintain-view="jobs_ranking">城市排行</a>
          <a href="#cycle_compare" data-maintain-view="cycle_compare">三年趋势</a>
          <a href="#calendar" data-maintain-view="calendar">报考日历</a>
          <a href="#saved" data-maintain-view="saved">我的收藏</a>
          <a href="#help" data-maintain-view="help">使用说明</a>
          <a href="#changelog" data-maintain-view="changelog">更新日志</a>
        </nav>
        <span id="maintain-status" class="maintain-status" role="status" aria-live="polite">正在读取数据清单…</span>
      </div>
      <span class="maintain-scroll-progress" aria-hidden="true"></span>
    </header>
    <main id="maintain-main" class="maintain-main"></main>
    <section class="maint-cta" aria-labelledby="maint-cta-title">
      <span class="maint-cta__glow" aria-hidden="true"></span>
      <div class="maint-cta__inner">
        <p class="maint-eyebrow"><span class="maint-eyebrow__index">下一步</span>从这里开始</p>
        <h2 id="maint-cta-title">拿不准就先看数据说明，<br>想好了就直接查岗位。</h2>
        <div class="maint-cta__actions">
          <a class="maint-cta__primary" href="#jobs_search" data-maintain-view="jobs_search">打开岗位检索 <i class="maint-cta__arrow">→</i></a>
          <a class="maint-cta__ghost" href="#calendar" data-maintain-view="calendar">查看报考日历</a>
        </div>
        <p class="maint-cta__trust">本站三条铁律：未公布不显示 · 推导亮明依据 · 来源可核对</p>
        <p class="maint-cta__stats">2024—2026 · {band_stats}</p>
      </div>
    </section>
    <footer class="maintain-footer">
      <span>数据来自官方公告，来源可核对 · <a href="#data_boundary" data-maintain-view="data_boundary">数据说明</a></span>
      <span>第一次使用？请看导航里的「使用说明」</span>
    </footer>
  </div>
  <script src="assets/maintainable-data.js?v={ASSET_VERSION}"></script>
  <script src="assets/maintainable-major-city.js?v={ASSET_VERSION}"></script>
  <script src="assets/maintainable-user-store.js?v={ASSET_VERSION}"></script>
  <script src="assets/v17-tools.js?v={ASSET_VERSION}"></script>
  <script type="module" src="assets/maintainable-site.js?v={ASSET_VERSION}"></script>
  {SW_BOOT}
</body>
</html>
"""


def build_maintainable_site(root: Path = ROOT, output_dir: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    """Build and return the manifest for the external-data maintenance site.

    全链入口：canonical bundles → 维护站（HTML 零输入）。canonical 缺失或
    校验失败会抛 CycleBundleError，发布链 fail-closed；不存在任何"以现库
    raw 行再生"的旁路（RC2 再生工具已随方案 A 退役）。
    """
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    bundles = build_unified_bundles(root)
    return assemble_maintainable_site(bundles, root=root, output_dir=output_dir)


def assemble_maintainable_site(
    bundles: dict[str, Any],
    root: Path = ROOT,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, object]:
    """Assemble the site from cycle bundles (唯一正式装配入口，canonical 输入)."""
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    # RC3(N)：job_history 由 builder 原生构建（行源=canonical；绑定 canonical sha）
    from .gen_job_history import build_payload as build_job_history_payload

    job_history_payload = build_job_history_payload()
    job_history_path = output_dir / "data" / "job_history.json"
    job_history_encoded = _write_json(job_history_path, job_history_payload)
    # RC3(N)：精选静态输入（curated）从 canonical 复制进产物并登记
    curated_specs = (
        ("req_fields", "canonical/curated/req-fields-2026.json", "data/req-fields-2026.json", "2026"),
        ("calendar", "canonical/curated/calendar.json", "data/calendar.json", None),
    )
    curated_payloads: dict[str, dict[str, object]] = {
        "job_history": {
            "data": "data/job_history.json",
            "bytes": len(job_history_encoded),
            "sha256": hashlib.sha256(job_history_encoded).hexdigest(),
            "schema": job_history_payload.get("schema"),
        },
    }
    for name, source_rel, output_rel, only_cycle in curated_specs:
        source_path = root / source_rel
        if not source_path.is_file():
            raise BuildInvariantError(f"精选输入缺失：{source_path}")
        target = output_dir / output_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        payload_doc = json.loads(target.read_text(encoding="utf-8"))
        curated_payloads[name] = {
            "data": output_rel,
            "bytes": target.stat().st_size,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "schema": payload_doc.get("schema"),
            **({"cycle": only_cycle} if only_cycle else {}),
        }

    data_entries: list[dict[str, object]] = []
    snapshot_date = _stable_snapshot_date(bundles)
    previous_cycle: str | None = None
    previous_rows: list[dict[str, object]] = []
    rows_by_cycle: dict[str, list[dict[str, object]]] = {}
    meta_by_cycle: dict[str, dict[str, object]] = {}
    raw_rows_by_cycle: dict[str, list[dict[str, object]]] = {}
    source_info_by_cycle: dict[str, dict[str, object]] = {}
    for cycle in SUPPORTED_CYCLES:
        bundle = bundles[cycle]
        modules = _module_payloads(bundle)
        score_payload = modules.pop("scores", None)
        current_rows = modules["jobs"].get("allMajors", {}).get("rows", []) if isinstance(modules["jobs"].get("allMajors"), dict) else []
        current_rows = [row for row in current_rows if isinstance(row, dict)]
        # 用户口径模块（changes/trend/palette/lite/derived）一律只吃 active 行；
        # jobs 模块自身保留 raw 行（含排除行，审计真源）。
        _, active_rows_cycle, excluded_rows_cycle = split_records(current_rows)
        rows_by_cycle[cycle] = active_rows_cycle
        raw_rows_by_cycle[cycle] = current_rows
        pos_rows_cycle = (modules.get("positions", {}) or {}).get("rows") or []
        src0_cycle = (pos_rows_cycle[0].get("source") or {}) if pos_rows_cycle else {}
        source_info_by_cycle[cycle] = {
            "source_ref": src0_cycle.get("source_ref"),
            "observed_at": src0_cycle.get("observed_at"),
            "evidence_note": src0_cycle.get("note"),
        }
        modules["changes"] = build_change_payload(previous_cycle, cycle, previous_rows, active_rows_cycle)
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
            # wanyu-metrics/v1：recruits=有效（active）招录数；raw_* 为含排除行口径；
            # posts 仅作 active_posts 的兼容别名保留。
            "raw_posts": len(current_rows),
            "active_posts": len(active_rows_cycle),
            "excluded_posts": len(excluded_rows_cycle),
            "raw_recruits": sum(int(row.get("num") or 0) for row in current_rows),
            "recruits": int(meta.get("recruits") or 0),
            "posts": int(meta.get("total") or 0),
            "status": audit_cycle.get("dominant_status") or audit_cycle.get("status") or "verified",
            "gaps": len(audit_cycle.get("gaps") or []),
            "score_unresolved": int(unresolved or 0),
            "bytes": module_entries["jobs"]["bytes"],
            "sha256": module_entries["jobs"]["sha256"],
        })
        previous_cycle = cycle
        previous_rows = active_rows_cycle

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
        # palette 已退役（v17.7.1）：命令面板由 jobs_lite 内存派生，builder 不再产出/登记。
        lite = _lite_payload(
            cycle,
            rows_by_cycle[cycle],
            meta_by_cycle.get(cycle, {}),
            job_index={
                str(r.get("job_id") or r.get("row_id")): i
                for i, r in enumerate(raw_rows_by_cycle.get(cycle, []))
            },
            source_info=source_info_by_cycle.get(cycle),
        )
        lite_path = output_dir / "data" / "cycles" / cycle / "jobs_lite.json"
        lite_encoded = _write_json(lite_path, lite)
        cycle_entries_by_cycle[cycle]["modules"]["jobs_lite"] = {
            "data": f"data/cycles/{cycle}/jobs_lite.json",
            "bytes": len(lite_encoded),
            "sha256": hashlib.sha256(lite_encoded).hexdigest(),
            "schema": lite.get("schema"),
        }
        # RC3(N)：major_index 由 builder 原生构建（行源=canonical active 行，输入图零产物）
        major_catalog_path = root / "tools" / "anhui_web" / "data" / "major_catalog.json"
        major_catalog = json.loads(major_catalog_path.read_text(encoding="utf-8"))
        major_index = build_major_index_index(major_catalog.get("map") or {}, rows_by_cycle[cycle])
        major_index["cycle"] = str(cycle)
        canonical_file = root / "canonical" / "cycles" / f"{cycle}.json"
        major_index["computed_from"] = {
            "jobs_sha256": hashlib.sha256(canonical_file.read_bytes()).hexdigest(),
            "source": "canonical/cycles",
        }
        major_index_path = output_dir / "data" / "cycles" / cycle / "major-index.json"
        major_index_encoded = _write_json(major_index_path, major_index)
        cycle_entries_by_cycle[cycle]["modules"]["major_index"] = {
            "data": f"data/cycles/{cycle}/major-index.json",
            "bytes": len(major_index_encoded),
            "sha256": hashlib.sha256(major_index_encoded).hexdigest(),
            "schema": major_index.get("schema"),
        }
        if str(cycle) == "2026":
            cycle_entries_by_cycle[cycle]["modules"]["req_fields"] = curated_payloads["req_fields"]

    audit_path = output_dir / "data" / "audit" / "three-year.json"
    audit_payload = _global_audit_payload(
        bundles,
        active_totals={
            "active_post_count": sum(int(entry.get("active_posts") or entry.get("posts") or 0) for entry in data_entries),
            "active_recruit_count": sum(int(entry.get("recruits") or 0) for entry in data_entries),
        },
    )
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
        "metrics_contract": {
            "name": "wanyu-metrics/v1",
            "recruits": "active（有效岗位）招录人数",
            "raw_posts": "含排除行的原始收录行数",
            "active_posts": "排除 record_status≠active 后的用户口径岗位数",
            "excluded_posts": "被生命周期排除的行数（raw_posts = active_posts + excluded_posts）",
            "raw_recruits": "含排除行的招录人数",
            "posts": "deprecated：active_posts 的兼容别名，禁止按 raw 语义解读",
        },
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
        "job_history": curated_payloads["job_history"],
        "calendar": curated_payloads["calendar"],
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
    (output_dir / "index.html").write_text(_index_html(audit_payload.get("summary")), encoding="utf-8", newline="\n")
    assets = output_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("maintainable-site.js", "maintainable-site.css", "v17-ui-upgrade.css", "maintainable-tokens.css", "maintainable-data.js", "maintainable-major-city.js", "maintainable-user-store.js", "v17-exam-picker.css", "v17-search.css", "v17-tools.css", "v17-tools.js", "og-card.png"):
        shutil.copyfile(TEMPLATE_DIR / name, assets / name)
    # PWA 离线层：SW 与应用清单位于站点根（作用域即站点根）。
    # SW 的 VERSION/PRECACHE 版本号由 release.json 在构建期注入（占位符替换）。
    sw_template = (TEMPLATE_DIR / "maintainable-sw.js").read_text(encoding="utf-8")
    for token, value in (("__SW_VERSION__", SW_VERSION), ("__ASSET_VERSION__", ASSET_VERSION)):
        if token not in sw_template:
            raise RuntimeError(f"maintainable-sw.js 模板缺少 {token} 占位符，版本注入失效")
        sw_template = sw_template.replace(token, value)
    (output_dir / "sw.js").write_text(sw_template, encoding="utf-8", newline="\n")
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
