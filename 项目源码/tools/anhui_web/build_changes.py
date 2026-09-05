"""Conservative adjacent-cycle matching and comparability rules."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .data_contract import normalize_text


def _value(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = normalize_text(row.get(name))
        if value:
            return value
    return ""


def _exact_key(row: dict[str, Any]) -> tuple[str, ...] | None:
    code = _value(row, "code")
    if not code:
        return None
    return (_value(row, "exam"), _value(row, "city", "reg"), code)


def _composite_key(row: dict[str, Any]) -> tuple[str, ...] | None:
    parts = (
        _value(row, "exam"),
        _value(row, "city", "reg"),
        _value(row, "unit"),
        _value(row, "post_name", "zw", "display_title"),
    )
    return parts if any(parts) else None


def _record_id(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    return str(row.get("record_id") or row.get("job_id") or row.get("row_id") or row.get("code") or "") or None


def _row_status(row: dict[str, Any]) -> str:
    return str(row.get("evidence_status") or row.get("status") or "verified")


def classify_change(base: dict[str, Any] | None, target: dict[str, Any] | None, match_method: str) -> dict[str, Any]:
    """Classify one match while keeping uncertain matches out of conclusions."""
    if match_method == "semantic_candidate":
        return {
            "status": "needs_review",
            "comparable": False,
            "match_method": match_method,
            "base_record_id": _record_id(base),
            "target_record_id": _record_id(target),
            "changed_fields": [],
        }
    if base is None and target is not None:
        return {"status": "added", "comparable": False, "match_method": match_method, "base_record_id": None, "target_record_id": _record_id(target), "changed_fields": []}
    if target is None and base is not None:
        return {"status": "withdrawn", "comparable": False, "match_method": match_method, "base_record_id": _record_id(base), "target_record_id": None, "changed_fields": []}
    if base is None or target is None:
        return {"status": "needs_review", "comparable": False, "match_method": match_method, "base_record_id": _record_id(base), "target_record_id": _record_id(target), "changed_fields": []}
    comparable = match_method in {"exact_code", "composite_exact"} and _row_status(base) not in {"unpublished_or_unavailable", "ambiguous_join", "needs_review"} and _row_status(target) not in {"unpublished_or_unavailable", "ambiguous_join", "needs_review"}
    pairs = (
        ("code", "code"),
        ("city", "city"),
        ("unit", "unit"),
        ("post_name", "post_name"),
        ("post_name", "zw"),
        ("major", "zy"),
        ("category", "lb"),
        ("recruits", "recruits"),
        ("recruits", "num"),
    )
    changed: list[str] = []
    seen: set[str] = set()
    for label, field in pairs:
        if label in seen:
            continue
        left = _value(base, field) if field != "recruits" else _value(base, "recruits", "num")
        right = _value(target, field) if field != "recruits" else _value(target, "recruits", "num")
        if left != right:
            changed.append(label)
            seen.add(label)
    return {
        "status": "revised" if changed else "unchanged",
        "comparable": comparable,
        "match_method": match_method,
        "base_record_id": _record_id(base),
        "target_record_id": _record_id(target),
        "changed_fields": changed,
    }


def match_positions(base_rows: list[dict[str, Any]], target_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base_exact: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    base_composite: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in base_rows:
        if not isinstance(row, dict):
            continue
        if (key := _exact_key(row)) is not None:
            base_exact[key].append(row)
        if (key := _composite_key(row)) is not None:
            base_composite[key].append(row)
    used: set[int] = set()
    changes: list[dict[str, Any]] = []
    for target in target_rows:
        if not isinstance(target, dict):
            continue
        base: dict[str, Any] | None = None
        method = "added"
        exact = base_exact.get(_exact_key(target)) if _exact_key(target) is not None else None
        if exact and len(exact) == 1:
            base = exact[0]
            method = "exact_code"
        else:
            composite = (base_composite.get(_composite_key(target)) or []) if _composite_key(target) is not None else []
            if len(composite) == 1:
                base = composite[0]
                method = "composite_exact"
            elif len(composite) > 1:
                changes.append({**classify_change(composite[0], target, "semantic_candidate"), "candidate_record_ids": [_record_id(item) for item in composite]})
                continue
        if base is None:
            changes.append(classify_change(None, target, "added"))
        else:
            used.add(id(base))
            changes.append(classify_change(base, target, method))
    for base in base_rows:
        if isinstance(base, dict) and id(base) not in used:
            changes.append(classify_change(base, None, "withdrawn"))
    return changes


def comparable_metric(metric: str, base_meta: dict[str, Any], target_meta: dict[str, Any]) -> dict[str, Any]:
    if metric == "competition_rate" and base_meta.get("denominator") != target_meta.get("denominator"):
        return {"metric": metric, "comparable": False, "reason": "分母类型不同，不能直接比较"}
    if base_meta.get("evidence_level") and target_meta.get("evidence_level") and base_meta.get("evidence_level") != target_meta.get("evidence_level"):
        return {"metric": metric, "comparable": False, "reason": "证据层不同，不能直接比较"}
    if base_meta.get("status") in {"unpublished_or_unavailable", "ambiguous_join"} or target_meta.get("status") in {"unpublished_or_unavailable", "ambiguous_join"}:
        return {"metric": metric, "comparable": False, "reason": "至少一个周期数据未取得或无法唯一关联"}
    return {"metric": metric, "comparable": True, "reason": "口径和证据状态允许比较"}


def build_change_payload(base_cycle: str | None, target_cycle: str, base_rows: list[dict[str, Any]], target_rows: list[dict[str, Any]]) -> dict[str, Any]:
    changes = match_positions(base_rows, target_rows) if base_cycle else []
    comparable_changes = [item for item in changes if item.get("status") in {"unchanged", "revised"}]
    summary = {status: sum(1 for item in changes if item.get("status") == status) for status in ("added", "withdrawn", "revised", "unchanged", "needs_review")}
    return {
        "schema": "wanyu-maintainable-changes/v1",
        "base_cycle": base_cycle,
        "target_cycle": str(target_cycle),
        "comparable": bool(comparable_changes) and all(bool(item.get("comparable")) for item in comparable_changes),
        "summary": summary,
        "changes": changes,
        "matching_policy": ["exact_code", "composite_exact", "semantic_candidate_requires_review"],
    }
