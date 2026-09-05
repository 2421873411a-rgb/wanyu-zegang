# -*- coding: utf-8 -*-
"""v17.8.5-RC3 阶段 H1：legacy HTML 加载器（归档隔离）。

正式构建链禁止调用本模块（HTML 永远只是 OUTPUT）。仅用于：
- legacy_v11 恢复后的 canonical 重播种对账（gen_canonical_bundles --legacy）；
- 回归测试对照。

入口：build_unified_bundles_from_legacy(root)——原 unified_cycle_bundle 的
HTML 反向读取实现，逐字节保留（_refresh_historical_cycle_fields /
_validate_bundle 只在此路径生效）。
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

try:
    from ..unified_cycle_bundle import (
        SUPPORTED_CYCLES,
        CycleBundle,
        CycleBundleError,
        _load_audit,
        _load_baseline,
        _normalise_payload,
    )
except ImportError:  # pragma: no cover - direct script execution
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.anhui_web.unified_cycle_bundle import (
        SUPPORTED_CYCLES,
        CycleBundle,
        CycleBundleError,
        _load_audit,
        _load_baseline,
        _normalise_payload,
    )


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


def build_unified_bundles_from_legacy(root: Path) -> dict[str, CycleBundle]:
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
