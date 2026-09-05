"""Build a detailed review queue while keeping public boundary counts stable."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


def _bundle_audit(bundle: Any) -> dict[str, Any]:
    if isinstance(bundle, dict):
        value = bundle.get("audit")
        return value if isinstance(value, dict) else bundle
    value = getattr(bundle, "audit", {})
    return value if isinstance(value, dict) else {}


def _bundle_unresolved(bundle: Any) -> int:
    if isinstance(bundle, dict):
        direct = bundle.get("score_unresolved")
        if direct is not None:
            return int(direct or 0)
        score_lists = bundle.get("scoreLists")
        if isinstance(score_lists, dict):
            keyed = score_lists.get("keyed")
            if isinstance(keyed, dict) and keyed.get("unresolved") is not None:
                return int(keyed.get("unresolved") or 0)
    audit = _bundle_audit(bundle)
    coverage = audit.get("coverage") if isinstance(audit.get("coverage"), dict) else {}
    return int(coverage.get("score_unresolved") or 0)


def _event_from_gap(cycle: str, gap: Any) -> dict[str, Any]:
    if isinstance(gap, str):
        return {
            "cycle": cycle,
            "kind": "unpublished_or_unavailable",
            "evidence": f"cycle:{cycle}",
            "title": gap,
            "scope": gap,
            "severity": "medium",
            "detail": gap,
        }
    item = dict(gap) if isinstance(gap, dict) else {"detail": str(gap)}
    title = str(item.get("title") or item.get("name") or item.get("detail") or "未命名审计事件")
    return {
        "cycle": cycle,
        "kind": str(item.get("kind") or item.get("status") or "needs_review"),
        "evidence": str(item.get("evidence") or item.get("source_ref") or f"cycle:{cycle}"),
        "title": title,
        "scope": str(item.get("scope") or title),
        "severity": str(item.get("severity") or "medium"),
        "detail": str(item.get("detail") or item.get("note") or title),
        "resolution_trigger": str(item.get("resolution_trigger") or "取得可复核官方材料后重新构建并通过门禁"),
    }


def dedupe_audit_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: OrderedDict[tuple[str, ...], dict[str, Any]] = OrderedDict()
    for event in events:
        if not isinstance(event, dict):
            continue
        normalized = {key: value for key, value in event.items()}
        key = tuple(str(normalized.get(field) or "").strip().casefold() for field in ("cycle", "kind", "evidence", "title", "scope"))
        if key not in grouped:
            normalized["occurrences"] = 1
            normalized["cycles"] = [str(normalized.get("cycle") or "")]
            grouped[key] = normalized
        else:
            grouped[key]["occurrences"] = int(grouped[key].get("occurrences") or 0) + 1
    return list(grouped.values())


def _cycle_events(audit_index: dict[str, Any], bundles: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    cycle_items = audit_index.get("cycles") if isinstance(audit_index, dict) else []
    if isinstance(cycle_items, list):
        for item in cycle_items:
            if not isinstance(item, dict):
                continue
            cycle = str(item.get("cycle") or "")
            gaps = item.get("gaps") or item.get("known_gaps") or []
            events.extend(_event_from_gap(cycle, gap) for gap in gaps)
    if not events:
        for cycle, bundle in (bundles or {}).items():
            audit = _bundle_audit(bundle)
            gaps = audit.get("gaps") or audit.get("known_gaps") or []
            events.extend(_event_from_gap(str(cycle), gap) for gap in gaps)
    return events


def summarize_review_queue(queue: dict[str, Any]) -> dict[str, int]:
    items = queue.get("items") if isinstance(queue, dict) else []
    items = items if isinstance(items, list) else []
    return {
        "event_count": len(items),
        "high_risk_count": sum(str(item.get("severity")) in {"high", "critical"} for item in items if isinstance(item, dict)),
        "needs_review_count": sum(str(item.get("kind")) in {"needs_review", "ambiguous_join"} for item in items if isinstance(item, dict)),
    }


def build_review_queue(bundles: dict[str, Any], audit_index: dict[str, Any]) -> dict[str, Any]:
    events = dedupe_audit_events(_cycle_events(audit_index, bundles))
    declared = audit_index.get("summary") if isinstance(audit_index, dict) else {}
    declared = declared if isinstance(declared, dict) else {}
    unresolved = declared.get("unresolved_score_count")
    if unresolved is None:
        unresolved = sum(_bundle_unresolved(bundle) for bundle in (bundles or {}).values())
    public_boundaries = declared.get("gap_count")
    if public_boundaries is None:
        public_boundaries = len(events)
    queue = {"schema": "wanyu-maintainable-review-queue/v1", "items": events}
    queue_summary = summarize_review_queue(queue)
    queue["summary"] = {
        **queue_summary,
        "public_boundary_count": int(public_boundaries or 0),
        "unresolved_score_count": int(unresolved or 0),
    }
    return queue
