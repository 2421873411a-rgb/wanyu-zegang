"""Build a cycle-scoped, independently replaceable score module.

Score indexes are kept outside ``jobs.json`` so that a later score harvest can
be replaced without rebuilding the position catalog.  The builder copies the
source keys verbatim and only adds a machine-readable envelope and summary;
missing or ambiguous values remain missing/ambiguous.
"""

from __future__ import annotations

import copy
from typing import Any


def _count(value: object) -> int | None:
    if isinstance(value, (dict, list, tuple, set)):
        return len(value)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _unresolved(value: object) -> int | None:
    if isinstance(value, list):
        return len(value)
    return _count(value)


def build_scores(score_lists: dict[str, Any] | None, cycle: str) -> dict[str, Any]:
    """Return the score source with a stable schema and truthful summary."""
    source = copy.deepcopy(score_lists) if isinstance(score_lists, dict) else {}
    declared_cycle = source.get("cycle")
    if declared_cycle not in (None, "", cycle):
        raise ValueError(f"score list cycle mismatch: expected {cycle}, got {declared_cycle}")

    keyed = source.get("keyed") if isinstance(source.get("keyed"), dict) else {}
    payload: dict[str, Any] = {
        **source,
        "schema": "wanyu-maintainable-scores/v1",
        "cycle": str(cycle),
        "source_module": "cycle score list source",
        "unknown_policy": "未发布、未收割或无法唯一匹配的成绩保持空值/待复核，不推断为零",
        "summary": {
            "bs": _count(source.get("bs")),
            "ms": _count(source.get("ms")),
            "by_key": _count(source.get("by_key")),
            "unresolved": _unresolved(keyed.get("unresolved")),
        },
    }
    return payload


__all__ = ["build_scores"]
