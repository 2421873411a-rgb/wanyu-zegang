"""Shared, conservative data semantics for the maintainable site build chain."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any


ALLOWED_STATUSES = frozenset(
    {
        "verified",
        "source_bundle",
        "derived",
        "unpublished_or_unavailable",
        "ambiguous_join",
        "needs_review",
    }
)
_UNKNOWN_STATUSES = frozenset({"unpublished_or_unavailable", "ambiguous_join"})
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_text(value: object) -> str:
    """Normalize matching input without replacing the source value."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", text).strip().casefold()


def _row_value(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = normalize_text(row.get(name))
        if value:
            return value
    return ""


def make_record_id(cycle: str, row: dict[str, object]) -> str:
    """Create a deterministic cycle-scoped ID from position identity fields."""
    cycle_text = str(cycle).strip()
    if not re.fullmatch(r"\d{4}", cycle_text):
        raise ValueError(f"invalid cycle: {cycle!r}")
    parts = (
        _row_value(row, "exam"),
        _row_value(row, "city", "reg"),
        _row_value(row, "code"),
        _row_value(row, "unit"),
        _row_value(row, "post_name", "zw", "display_title"),
    )
    if not any(parts):
        raise ValueError("position row has no identity fields")
    identity = "\x1f".join((cycle_text, *parts))
    digest = hashlib.sha256(f"wanyu-record-v1\x1f{identity}".encode("utf-8")).hexdigest()[:20]
    return f"job-{cycle_text}-{digest}"


def evidence(
    status: str,
    source_ref: str,
    source_locator: str,
    method: str,
    observed_at: str | None,
    note: str = "",
) -> dict[str, object]:
    """Build a non-optional evidence envelope for a user-visible value."""
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"unsupported evidence status: {status!r}")
    if not str(source_ref).strip():
        raise ValueError("evidence source_ref is required")
    if not str(source_locator).strip():
        raise ValueError("evidence source_locator is required")
    if observed_at not in (None, "") and not _DATE_RE.fullmatch(str(observed_at).strip()):
        raise ValueError(f"invalid observed_at date: {observed_at!r}")
    if not str(method).strip():
        raise ValueError("evidence method is required")
    result = {
        "status": status,
        "source_ref": str(source_ref).strip(),
        "source_locator": str(source_locator).strip(),
        "method": str(method).strip(),
        "observed_at": str(observed_at).strip() if observed_at not in (None, "") else None,
    }
    if str(note).strip():
        result["note"] = str(note).strip()
    return result


def validate_unknown_semantics(value: object, status: str) -> None:
    """Reject a non-null value when the evidence explicitly says it is unknown."""
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"unsupported status: {status!r}")
    if status in _UNKNOWN_STATUSES and value not in (None, ""):
        raise ValueError(f"{status} values must remain null or empty, got {value!r}")


def ensure_unique_record_ids(cycle: str, rows: list[dict[str, object]]) -> list[str]:
    """Return IDs or fail loudly instead of allowing a silent overwrite."""
    ids = [make_record_id(cycle, row) for row in rows]
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        raise ValueError(f"duplicate record IDs for {cycle}: {duplicates[:5]}")
    return ids
