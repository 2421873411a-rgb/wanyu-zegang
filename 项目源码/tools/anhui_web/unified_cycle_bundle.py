"""Load the audited three-cycle payloads used by the v12 single-file site.

The v11 pages are treated as immutable build inputs for this migration step:
they already contain the audited, cycle-specific all-position payload,
score-list payload, and rendered archive views.  This module deliberately does
not import or mutate ``build_pages`` globals, so loading one cycle cannot leak
paths or data from another cycle.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .city_norm import normalize_source_city
    from .data_quality import annotate_position_row, competition_observations
except ImportError:  # pragma: no cover - supports direct script imports
    from city_norm import normalize_source_city
    from data_quality import annotate_position_row, competition_observations


SUPPORTED_CYCLES = ("2024", "2025", "2026")
BASELINE_NAME = "single_file_baseline_v12.json"
AUDIT_NAME = "three_year_audit.json"
MASTER_NAME = "皖域择岗总览.html"


@dataclass(frozen=True)
class CycleBundle:
    """All cycle-specific inputs needed to render one view of the workbench."""

    cycle: str
    label: str
    source_file: Path
    all_majors: dict[str, Any]
    jobs: dict[str, Any]
    records: list[dict[str, Any]]
    score_lists: dict[str, Any]
    cycle_info: dict[str, Any]
    audit: dict[str, Any]
    payload: dict[str, Any]
    page_content: str

    @property
    def audit_cycle(self) -> dict[str, Any]:
        """Backward-compatible name used by the first loader tests."""
        return self.audit


class CycleBundleError(ValueError):
    """Raised when a cycle cannot be loaded without silently losing data."""


def global_record_id(cycle: str, record_id: str) -> str:
    """Return a cycle-scoped record ID with an intentionally strict shape."""
    cycle_text = str(cycle).strip()
    record_text = str(record_id).strip()
    if not re.fullmatch(r"\d{4}", cycle_text):
        raise ValueError(f"invalid cycle for global record id: {cycle!r}")
    if not record_text or ":" in record_text:
        raise ValueError(f"invalid record id for global record id: {record_id!r}")
    return f"{cycle_text}:{record_text}"



def _load_audit(root: Path) -> dict[str, Any]:
    path = root / "tools" / "anhui_web" / "data" / AUDIT_NAME
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: audit must be an object")
    return value


def _load_baseline(root: Path) -> dict[str, Any]:
    path = root / "tools" / "anhui_web" / "data" / BASELINE_NAME
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: baseline must be an object")
    return value


def _normalise_payload(payload: dict[str, Any], cycle: str) -> dict[str, Any]:
    """Add deterministic IDs and conservative quality annotations to a copy."""
    result = copy.deepcopy(payload)
    all_majors = result.get("allMajors")
    if not isinstance(all_majors, dict) or not isinstance(all_majors.get("rows"), list):
        raise ValueError(f"{cycle}: page payload has no allMajors.rows")
    def normalize_rows(rows: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise ValueError(f"{cycle}: position rows[{index - 1}] is not an object")
            item = annotate_position_row(cycle, row)
            item["competition_metric_type"] = (item.get("competition_observations") or {}).get("preferred_type")
            if "city" in item:
                item["city"] = normalize_source_city(item.get("city"))
            normalized.append(item)
        return normalized

    all_majors["rows"] = normalize_rows(all_majors["rows"])
    records = result.get("records")
    if isinstance(records, list):
        result["records"] = normalize_rows(records)
    _enrich_job_rollups(result)
    payload_cycle = str((all_majors.get("meta") or {}).get("cycle") or "")
    result.setdefault("cycleInfo", {"cycle": cycle, "label": payload_cycle or f"{cycle}年度"})
    return result


def _quality_rollup(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """Aggregate row-level denominator observations without mixing their types."""
    rollup: dict[str, dict[str, dict[str, Any]]] = {}
    for record in records:
        if record.get("exclusion"):
            continue
        city = str(record.get("city") or "")
        exam = str(record.get("exam") or "")
        if not city or not exam:
            continue
        observations = record.get("competition_observations")
        if not isinstance(observations, dict):
            observations = competition_observations(record)
        metric_type = str(record.get("competition_metric_type") or observations.get("preferred_type") or "")
        observation_key = "examinees" if metric_type in {"examinees", "interview_shortlisted"} else metric_type
        observation = observations.get(observation_key) if isinstance(observations.get(observation_key), dict) else {}
        value = observation.get("value")
        if observation.get("status") != "observed" or not isinstance(value, (int, float)) or value <= 0:
            continue
        recruits = record.get("recruits") if record.get("recruits") is not None else record.get("num")
        item = rollup.setdefault(city, {}).setdefault(exam, {"row_count": 0, "metrics": {}})
        item["row_count"] += 1
        metric = item["metrics"].setdefault(metric_type, {"base": 0, "recruits": 0, "coverage_rows": 0})
        metric["base"] += int(value)
        metric["recruits"] += int(recruits or 0)
        metric["coverage_rows"] += 1
    return rollup


def _quality_state(metrics: dict[str, dict[str, Any]], row_count: int) -> tuple[str, bool]:
    types = [key for key, value in metrics.items() if int(value.get("coverage_rows", 0) or 0) > 0]
    if len(types) > 1:
        return "mixed_denominators", False
    if not types:
        return "unavailable", False
    if int(metrics[types[0]].get("coverage_rows", 0) or 0) < row_count:
        return "partial_coverage", False
    return "single_denominator", True


def _enrich_job_rollups(payload: dict[str, Any]) -> None:
    """Attach denominator quality states to the existing 2026 job rollups."""
    jobs = payload.get("jobs")
    records = payload.get("records")
    if not isinstance(jobs, dict) or not isinstance(records, list):
        return
    rollup = _quality_rollup([row for row in records if isinstance(row, dict)])

    def update_city_items(city_items: Any) -> None:
        if not isinstance(city_items, list):
            return
        for city_item in city_items:
            if not isinstance(city_item, dict):
                continue
            city = str(city_item.get("city") or "")
            city_rollup = rollup.get(city, {})
            exam_stats = city_item.get("exam") if isinstance(city_item.get("exam"), dict) else {}
            competition = city_item.get("competition")
            if not isinstance(competition, dict):
                competition = {}
                city_item["competition"] = competition
            aggregate_metrics: dict[str, dict[str, Any]] = {}
            aggregate_rows = 0
            exam_names = set(city_rollup) | set(exam_stats) | set(competition)
            for exam in sorted(exam_names):
                exam_rollup = city_rollup.get(exam, {"metrics": {}, "row_count": 0})
                metrics = copy.deepcopy(exam_rollup.get("metrics") or {})
                exam_stat = exam_stats.get(exam) if isinstance(exam_stats.get(exam), dict) else {}
                row_count = int(exam_stat.get("jobs") or exam_rollup.get("row_count") or 0)
                status, comparable = _quality_state(metrics, row_count)
                exam_comp = competition.setdefault(exam, {})
                if not isinstance(exam_comp, dict):
                    exam_comp = {}
                    competition[exam] = exam_comp
                exam_comp["competition_metrics"] = metrics
                exam_comp["ratio_status"] = status
                exam_comp["ratio_comparable"] = comparable
                types = [key for key, value in metrics.items() if int(value.get("coverage_rows", 0) or 0) > 0]
                if comparable and types:
                    exam_comp["competition_metric_type"] = types[0]
                    exam_comp["ratio"] = metrics[types[0]].get("ratio")
                for metric_name, metric_value in metrics.items():
                    aggregate = aggregate_metrics.setdefault(metric_name, {"base": 0, "recruits": 0, "coverage_rows": 0})
                    aggregate["base"] += int(metric_value.get("base") or 0)
                    aggregate["recruits"] += int(metric_value.get("recruits") or 0)
                    aggregate["coverage_rows"] += int(metric_value.get("coverage_rows") or 0)
                aggregate_rows += row_count
            for metric_value in aggregate_metrics.values():
                base = int(metric_value.get("base") or 0)
                metric_value["ratio"] = round(int(metric_value.get("recruits") or 0) / base, 8) if base else None
            city_status, city_comparable = _quality_state(aggregate_metrics, int(city_item.get("jobs") or aggregate_rows or 0))
            city_item["competition_metrics"] = aggregate_metrics
            city_item["ratio_status"] = city_status
            city_item["ratio_comparable"] = city_comparable
            if city_comparable:
                types = [key for key, value in aggregate_metrics.items() if int(value.get("coverage_rows", 0) or 0) > 0]
                if types:
                    city_item["competition_metric_type"] = types[0]
                    city_item["ratio"] = aggregate_metrics[types[0]].get("ratio")

    update_city_items(jobs.get("cities"))
    metrics = jobs.get("metrics")
    if isinstance(metrics, dict):
        update_city_items(metrics.get("cities"))
        competition = metrics.get("competition")
        if isinstance(competition, dict):
            for city_item in jobs.get("cities") or []:
                if isinstance(city_item, dict) and isinstance(city_item.get("competition"), dict):
                    competition[str(city_item.get("city") or "")] = copy.deepcopy(city_item["competition"])



# ============ v17.8.5-RC3 阶段 G/H：canonical 正式数据源 ============
# HTML 永远只是 OUTPUT。旧 HTML 反向读取已整体移至 archive/legacy_html_loader.py，
# 仅限迁移与回归对照，正式 release 禁止调用。

CANONICAL_SCHEMA = "wanyu-cycle-bundle/v1"
_CANONICAL_COLUMNS = ("job_id", "code", "city", "exam", "num")


def canonical_path(root: Path, cycle: str) -> Path:
    return Path(root).resolve() / "canonical" / "cycles" / f"{cycle}.json"


def load_canonical_doc(root: Path, cycle: str) -> dict[str, Any]:
    """读取并结构化校验 canonical 周期包（fail-closed，禁止静默降级）。"""
    from .invariants import BuildInvariantError, require_int
    from .record_lifecycle import record_status_of

    path = canonical_path(root, cycle)
    if not path.is_file():
        raise CycleBundleError(f"{path}: canonical 周期包缺失；先运行 tools/anhui_web/gen_canonical_bundles.py")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != CANONICAL_SCHEMA:
        raise BuildInvariantError(f"{path}: schema 必须是 {CANONICAL_SCHEMA}（got {doc.get('schema')!r}）")
    if str(doc.get("cycle")) != str(cycle):
        raise BuildInvariantError(f"{path}: cycle 字段 {doc.get('cycle')!r} 与文件名不符")
    all_majors = doc.get("all_majors")
    if not isinstance(all_majors, dict) or not isinstance(all_majors.get("rows"), list):
        raise BuildInvariantError(f"{path}: all_majors.rows 缺失")
    rows = all_majors["rows"]
    for row in rows:
        if not isinstance(row, dict):
            raise BuildInvariantError(f"{path}: rows 存在非对象行")
        record_status_of(row)  # 严格枚举：未知状态直接抛错
        missing = [key for key in _CANONICAL_COLUMNS if row.get(key) is None]
        if missing:
            raise BuildInvariantError(f"{path}: 行 {row.get('job_id') or '?'} 缺少必填列 {missing}")
    ids = [str(row.get("job_id") or "") for row in rows]
    if len(ids) != len(set(ids)):
        raise BuildInvariantError(f"{path}: job_id 存在重复")
    metrics = doc.get("metrics") or {}
    excluded = sum(1 for row in rows if str(row.get("record_status") or "") not in ("", "active"))
    if require_int(metrics.get("raw_posts"), "metrics.raw_posts") != len(rows):
        raise BuildInvariantError(f"{path}: metrics.raw_posts != len(rows)")
    if require_int(metrics.get("excluded_posts"), "metrics.excluded_posts") != excluded:
        raise BuildInvariantError(f"{path}: metrics.excluded_posts != 行内排除数")
    if require_int(metrics.get("active_posts"), "metrics.active_posts") != len(rows) - excluded:
        raise BuildInvariantError(f"{path}: metrics.active_posts != active 行数")
    score_state = doc.get("score_state") or {}
    score_file = Path(root).resolve() / str(score_state.get("file") or "")
    if not score_file.is_file():
        raise BuildInvariantError(f"{path}: score_state 文件缺失 {score_file}")
    return doc


def _score_lists_for(root: Path, doc: dict[str, Any]) -> dict[str, Any]:
    """按 canonical score_state 引用加载分数清单，并校验冻结 sha256。"""
    import hashlib

    from .invariants import BuildInvariantError

    score_state = doc.get("score_state") or {}
    path = Path(root).resolve() / str(score_state.get("file") or "")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != str(score_state.get("sha256") or ""):
        raise BuildInvariantError(
            f"{path}: 分数清单 sha256 与 canonical 冻结值不符"
            f"（{digest[:12]} != {str(score_state.get('sha256'))[:12]}）——先重锁 sources"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _audit_envelope(audit: dict[str, Any]) -> dict[str, Any]:
    """三年审计的顶层信封（builder 只需要定义与生成日期，cycles 走 bundle.audit）。"""
    keys = ("version", "generated_on", "status_definitions", "evidence_level_definitions")
    return {key: copy.deepcopy(audit.get(key)) for key in keys if audit.get(key) is not None}


def _validate_canonical_bundle(bundle: CycleBundle, baseline: dict[str, Any]) -> None:
    from .invariants import BuildInvariantError

    expected = (baseline.get("cycles") or {}).get(bundle.cycle)
    if not isinstance(expected, dict):
        raise BuildInvariantError(f"{bundle.cycle}: 冻结基线缺少该周期")
    meta = bundle.all_majors.get("meta") or {}
    if int(meta.get("total", -1)) != int(expected["posts"]):
        raise BuildInvariantError(
            f"{bundle.cycle}: canonical meta.total 与冻结基线不符（{meta.get('total')} != {expected['posts']}）"
        )
    if int(meta.get("recruits", -1)) != int(expected["recruits"]):
        raise BuildInvariantError(
            f"{bundle.cycle}: canonical meta.recruits 与冻结基线不符（{meta.get('recruits')} != {expected['recruits']}）"
        )
    if len(bundle.records) != int(expected["posts"]):
        raise BuildInvariantError(
            f"{bundle.cycle}: canonical 行数与冻结基线不符（{len(bundle.records)} != {expected['posts']}）"
        )
    if bundle.score_lists and str(bundle.score_lists.get("cycle")) != bundle.cycle:
        raise BuildInvariantError(f"{bundle.cycle}: score-list cycle mismatch")
    if bundle.audit.get("cycle") != bundle.cycle:
        raise BuildInvariantError(f"{bundle.cycle}: audit cycle mismatch")


def build_unified_bundles(root: Path) -> dict[str, CycleBundle]:
    """从 canonical 周期包加载三年数据（RC3 起为唯一正式入口）。

    与 legacy 版本的关键差异：rows 已是归一化+注记后的审计事实，不再重复
    _normalise_payload；page_content 恒为空串（HTML 只是输出，单文件重建引擎
    列入 v17.9）；分数清单按 canonical 引用加载并校验冻结 sha。
    """
    root = Path(root).resolve()
    baseline = _load_baseline(root)
    audit = _load_audit(root)
    audit_by_cycle = {
        str(item.get("cycle")): item
        for item in audit.get("cycles", [])
        if isinstance(item, dict) and item.get("cycle")
    }
    audit_envelope = _audit_envelope(audit)
    bundles: dict[str, CycleBundle] = {}
    for cycle in SUPPORTED_CYCLES:
        doc = load_canonical_doc(root, cycle)
        score_lists = _score_lists_for(root, doc)
        audit_cycle = audit_by_cycle.get(cycle)
        if audit_cycle is None:
            raise CycleBundleError(f"{cycle}: audit entry missing")
        source_file = canonical_path(root, cycle)
        payload = {
            "allMajors": copy.deepcopy(doc.get("all_majors") or {}),
            "cycleInfo": copy.deepcopy(doc.get("cycle_info") or {}),
            "threeYearAudit": copy.deepcopy(audit_envelope),
        }
        bundle = CycleBundle(
            cycle=cycle,
            label=str(doc.get("label") or f"{cycle}年度"),
            source_file=source_file,
            all_majors=payload["allMajors"],
            jobs={},
            records=copy.deepcopy(payload["allMajors"].get("rows") or []),
            payload=payload,
            score_lists=score_lists,
            cycle_info=payload.get("cycleInfo") or {},
            audit=audit_cycle,
            page_content="",
        )
        _validate_canonical_bundle(bundle, baseline)
        bundles[cycle] = bundle
    return bundles
