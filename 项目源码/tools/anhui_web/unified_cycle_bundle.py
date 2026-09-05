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


def _page_data(html_text: str, source_file: Path) -> dict[str, Any]:
    match = re.search(
        r"<script[^>]*\bid=[\"']page-data[\"'][^>]*>(.*?)</script>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"{source_file}: missing application/json #page-data")
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source_file}: invalid #page-data JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{source_file}: #page-data must be an object")
    return value


def _v12_page_data(html_text: str, cycle: str, source_file: Path) -> dict[str, Any] | None:
    """Read a cycle from an already-built v12 file when the v11 source is gone."""
    match = re.search(
        rf'<script[^>]*data-cycle-payload=["\']{re.escape(str(cycle))}["\'][^>]*>(.*?)</script>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise CycleBundleError(f"{source_file}: invalid v12 payload for {cycle}: {exc}") from exc
    if not isinstance(value, dict):
        raise CycleBundleError(f"{source_file}: v12 payload for {cycle} is not an object")
    return value


def _score_lists(html_text: str, source_file: Path) -> dict[str, Any]:
    match = re.search(
        r"<script[^>]*>\s*window\.__SCORE_LISTS__\s*=\s*(.*?);\s*</script>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return {}
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source_file}: invalid __SCORE_LISTS__ JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{source_file}: __SCORE_LISTS__ must be an object")
    return value


def _main_content(html_text: str, source_file: Path) -> str:
    match = re.search(
        r"<main\b(?=[^>]*\bid=[\"']main-content[\"'])[^>]*>(.*?)</main>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"{source_file}: missing #main-content")
    content = match.group(1).strip()
    if not content:
        raise ValueError(f"{source_file}: #main-content is empty")
    return content


def _v12_template_content(html_text: str, cycle: str, source_file: Path) -> str | None:
    match = re.search(
        rf'<template[^>]*data-cycle-template=["\']{re.escape(str(cycle))}["\'][^>]*>(.*?)</template>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    content = match.group(1).strip()
    if not content:
        raise CycleBundleError(f"{source_file}: v12 template for {cycle} is empty")
    return content


def _candidate_files(root: Path, cycle: str) -> tuple[Path, ...]:
    deliverables = root / "deliverables"
    if cycle == "2026":
        return (
            deliverables / "legacy_v11" / MASTER_NAME,
            root / "安徽公考数据网页" / MASTER_NAME,
            deliverables / MASTER_NAME,
        )
    return (
        deliverables / "legacy_v11" / cycle / MASTER_NAME,
        deliverables / cycle / MASTER_NAME,
        deliverables / MASTER_NAME,
    )


def _find_source(root: Path, cycle: str) -> Path:
    for candidate in _candidate_files(root, cycle):
        if candidate.is_file():
            return candidate
    searched = "、".join(str(path) for path in _candidate_files(root, cycle))
    raise CycleBundleError(f"{cycle}: no audited page artifact found; searched {searched}")


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


def _refresh_historical_cycle_fields(root: Path, payload: dict[str, Any], cycle: str) -> None:
    """Refresh generated historical sidecar fields before embedding the page.

    The archived v11 HTML remains the large rendering scaffold, but its older
    hire coverage can lag behind newly archived official attachments.  Apply
    only the generated cycle sidecars here: update cycle stats/gaps and join
    the safe ``(省考, 职位代码)`` hire reference fields.  Position rows and
    source text are otherwise left untouched.
    """
    cycle_dir = root / "tools" / "anhui_web" / "data" / "cycles" / cycle
    cycle_info_path = cycle_dir / "cycle.json"
    cycle_info: dict[str, Any] = {}
    try:
        raw_info = json.loads(cycle_info_path.read_text(encoding="utf-8"))
        if isinstance(raw_info, dict):
            cycle_info = raw_info
    except (OSError, ValueError):
        cycle_info = {}
    if cycle_info:
        info = payload.setdefault("cycleInfo", {})
        if isinstance(info, dict):
            if isinstance(cycle_info.get("stats"), dict):
                info["stats"] = copy.deepcopy(cycle_info["stats"])
            for key in ("cycle", "label", "status", "generated_on", "title_suffix", "snapshot_note", "gaps", "resolved_adjustments"):
                if key in cycle_info:
                    info[key] = copy.deepcopy(cycle_info[key])

    hire_path = cycle_dir / f"ahsk{cycle}_hire.json"
    if not hire_path.is_file():
        return
    try:
        hire_payload = json.loads(hire_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    hire_map: dict[str, list[dict[str, Any]]] = {}
    for item in hire_payload.get("positions", []) if isinstance(hire_payload, dict) else []:
        if isinstance(item, dict) and item.get("code") is not None:
            hire_map.setdefault(str(item["code"]), []).append(item)
    all_majors = payload.get("allMajors")
    if not isinstance(all_majors, dict) or not isinstance(all_majors.get("rows"), list):
        return
    rows = all_majors["rows"]
    for row in rows:
        if not isinstance(row, dict) or str(row.get("exam") or "") != "省考":
            continue
        entries = hire_map.get(str(row.get("code") or ""), [])
        hs_values = [item.get("hs") for item in entries if item.get("hs") is not None]
        ht_values = [item.get("ht") for item in entries if item.get("ht") is not None]
        if hs_values:
            row["hq"] = min(hs_values)
        if ht_values:
            row["ht"] = min(ht_values)
    meta = all_majors.setdefault("meta", {})
    if isinstance(meta, dict):
        score_coverage = meta.setdefault("scoreCoverage", {})
        if isinstance(score_coverage, dict):
            score_coverage["hire"] = sum(1 for row in rows if isinstance(row, dict) and row.get("hq") is not None)


def _validate_bundle(
    bundle: CycleBundle,
    baseline: dict[str, Any],
    audit: dict[str, Any],
) -> None:
    expected = (baseline.get("cycles") or {}).get(bundle.cycle)
    if not isinstance(expected, dict):
        raise ValueError(f"{bundle.cycle}: missing frozen baseline")
    meta = bundle.payload["allMajors"]["meta"]
    if int(meta.get("total", -1)) != int(expected["posts"]):
        raise ValueError(f"{bundle.cycle}: page total does not match frozen baseline")
    if int(meta.get("recruits", -1)) != int(expected["recruits"]):
        raise ValueError(f"{bundle.cycle}: page recruits does not match frozen baseline")
    rows = bundle.payload["allMajors"]["rows"]
    if len(rows) != int(expected["posts"]):
        raise ValueError(f"{bundle.cycle}: row count does not match frozen baseline")
    if bundle.score_lists and str(bundle.score_lists.get("cycle")) != bundle.cycle:
        raise ValueError(f"{bundle.cycle}: score-list cycle mismatch")
    if bundle.audit_cycle.get("cycle") != bundle.cycle:
        raise ValueError(f"{bundle.cycle}: audit cycle mismatch")
    if not bundle.page_content.startswith("<"):
        raise ValueError(f"{bundle.cycle}: rendered page content is not HTML")


def build_unified_bundles(root: Path) -> dict[str, CycleBundle]:
    """Load and validate 2024/2025/2026 without changing process-wide state."""
    root = Path(root).resolve()
    baseline = _load_baseline(root)
    audit = _load_audit(root)
    audit_by_cycle = {
        str(item.get("cycle")): item
        for item in audit.get("cycles", [])
        if isinstance(item, dict) and item.get("cycle")
    }
    bundles: dict[str, CycleBundle] = {}
    for cycle in SUPPORTED_CYCLES:
        source_file = _find_source(root, cycle)
        html_text = source_file.read_text(encoding="utf-8")
        payload = _v12_page_data(html_text, cycle, source_file) or _page_data(html_text, source_file)
        payload = _normalise_payload(payload, cycle)
        if cycle in ("2024", "2025"):
            _refresh_historical_cycle_fields(root, payload, cycle)
        # Refresh the audit envelope from the current read-only audit source;
        # embedded legacy page data must not freeze an older truth boundary.
        payload["threeYearAudit"] = copy.deepcopy(audit)
        score_lists = _score_lists(html_text, source_file) or (payload.get("scoreLists") if isinstance(payload.get("scoreLists"), dict) else {})
        audit_cycle = audit_by_cycle.get(cycle)
        if audit_cycle is None:
            raise ValueError(f"{cycle}: audit entry missing")
        bundle = CycleBundle(
            cycle=cycle,
            label=str((payload.get("cycleInfo") or {}).get("label") or (payload["allMajors"].get("meta") or {}).get("cycle") or f"{cycle}年度"),
            source_file=source_file,
            all_majors=payload["allMajors"],
            jobs=payload.get("jobs") or {},
            records=payload["allMajors"]["rows"],
            payload=payload,
            score_lists=score_lists,
            cycle_info=payload.get("cycleInfo") or {},
            audit=audit_cycle,
            page_content=_v12_template_content(html_text, cycle, source_file) or _main_content(html_text, source_file),
        )
        _validate_bundle(bundle, baseline, audit)
        bundles[cycle] = bundle
    return bundles
