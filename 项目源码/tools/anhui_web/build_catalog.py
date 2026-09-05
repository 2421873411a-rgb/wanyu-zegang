"""Build derived, readable lookup data without rewriting source job rows."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import json


def _text(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def _match_text(value: object) -> str:
    return re.sub(r"\s+", "", _text(value)).casefold()


def clean_major_label(raw: str) -> str | None:
    """Return a readable display candidate, or None for a code-only value."""
    text = _text(raw)
    if not text:
        return None
    if not re.search(r"[\u4e00-\u9fffA-Za-z]", text):
        return None
    # Some source tables prepend category letters and embed six/seven-digit
    # major codes in otherwise readable lists.  Remove only those presentation
    # tokens; the original ``zy`` remains untouched in jobs.json.
    text = re.sub(r"^[A-Za-z](?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<![A-Za-z0-9])[A-Za-z]?\d{4,8}(?![A-Za-z0-9])", "", text)
    text = re.sub(r"\s*[/\\|,，;；]+\s*", "、", text)
    text = re.sub(r"、{2,}", "、", text).strip(" /\\|,，;；:：._-—()（）[]【】、")
    if not text or not re.search(r"[\u4e00-\u9fffA-Za-z]", text):
        return None
    return text


_MAJOR_DIRECTORY_PATH = Path(__file__).resolve().parent / "data" / "major_catalog.json"
_GENERIC_DIRECTORY_TERMS = frozenset({"专业", "工程", "管理", "技术", "科学", "学", "理", "类", "其他"})
_DIRECTORY_TERMS: tuple[str, ...] | None = None
_DIRECTORY_TERM_MATCHES: tuple[tuple[str, str], ...] | None = None


def _directory_terms() -> tuple[str, ...]:
    """Load readable directory names used only for derived UI suggestions."""
    global _DIRECTORY_TERMS
    if _DIRECTORY_TERMS is not None:
        return _DIRECTORY_TERMS
    values: set[str] = set()
    try:
        payload = json.loads(_MAJOR_DIRECTORY_PATH.read_text(encoding="utf-8"))
        mapping = payload.get("map") if isinstance(payload, dict) else {}
        if isinstance(mapping, dict):
            values.update(str(key).strip() for key in mapping)
            for groups in mapping.values():
                if isinstance(groups, list):
                    values.update(str(value).strip() for value in groups)
    except (OSError, json.JSONDecodeError, TypeError):
        values = set()
    _DIRECTORY_TERMS = tuple(sorted(
        (value for value in values if len(value) >= 2 and value not in _GENERIC_DIRECTORY_TERMS),
        key=lambda value: (-len(value), _match_text(value), value),
    ))
    return _DIRECTORY_TERMS


def _directory_term_matches() -> tuple[tuple[str, str], ...]:
    """Cache normalized directory needles for repeated row-level matching."""
    global _DIRECTORY_TERM_MATCHES
    if _DIRECTORY_TERM_MATCHES is None:
        _DIRECTORY_TERM_MATCHES = tuple((term, _match_text(term)) for term in _directory_terms())
    return _DIRECTORY_TERM_MATCHES


def extract_major_keywords(raw: object) -> list[str]:
    """Return readable keyword candidates without rewriting the source field.

    Composite degree-level source text is not a useful datalist option.  The
    directory terms are only display/filter suggestions; qualification still
    uses the untouched ``zy`` source text and the detail view keeps it intact.
    """
    text = _text(raw)
    if not text:
        return []
    normalized = _match_text(text)
    candidates = {term for term, needle in _directory_term_matches() if needle in normalized}
    if "不限" in text:
        candidates.add("不限")
    if "不限专业" in text or "专业不限" in text:
        candidates.add("不限专业")
    cleaned = clean_major_label(text)
    if cleaned and len(cleaned) <= 32 and not re.search(r"(?:本科|专科|研究生|学历|学位|专业要求)", cleaned):
        candidates.add(cleaned)
    return sorted(candidates, key=lambda value: (_match_text(value), value))


def _values(rows: list[dict[str, Any]], field: str) -> list[str]:
    return sorted(
        {_text(row.get(field)) for row in rows if _text(row.get(field))},
        key=lambda value: (_match_text(value), value),
    )


def build_facets(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        "cities": _values(rows, "city") or _values(rows, "reg"),
        "exams": _values(rows, "exam"),
        "categories": _values(rows, "lb"),
    }


def build_catalog(cycle_payload: dict[str, Any], cycle: str) -> dict[str, Any]:
    all_majors = cycle_payload.get("allMajors") if isinstance(cycle_payload, dict) else {}
    rows = all_majors.get("rows") if isinstance(all_majors, dict) else []
    if not isinstance(rows, list):
        raise ValueError(f"{cycle}: allMajors.rows must be a list")
    typed_rows = [row for row in rows if isinstance(row, dict)]
    major_counts: Counter[str] = Counter()
    raw_by_major: dict[str, Counter[str]] = {}
    keyword_cache: dict[str, list[str]] = {}
    for row in typed_rows:
        raw = _text(row.get("zy"))
        if raw not in keyword_cache:
            keyword_cache[raw] = extract_major_keywords(raw)
        readable_keywords = keyword_cache[raw]
        for readable in readable_keywords:
            major_counts[readable] += 1
            raw_by_major.setdefault(readable, Counter())[raw] += 1
    majors = sorted(major_counts, key=lambda value: (_match_text(value), value))
    return {
        "schema": "wanyu-maintainable-catalog/v1",
        "cycle": str(cycle),
        "row_count": len(typed_rows),
        "source_fields": {"major": "zy", "city": "city", "exam": "exam", "category": "lb"},
        "majors": majors,
        "major_counts": dict(sorted(major_counts.items(), key=lambda item: (_match_text(item[0]), item[0]))),
        "major_raw_values": {
            major: dict(sorted(values.items(), key=lambda item: (_match_text(item[0]), item[0])))
            for major, values in sorted(raw_by_major.items(), key=lambda item: (_match_text(item[0]), item[0]))
        },
        "major_options_mode": "readable_keywords",
        "major_keyword_source": "derived_from_major_directory_and_source_zy",
        "facets": build_facets(typed_rows),
        "build_method": "derived_from_jobs_rows_without_overwriting_source_zy",
    }


def filter_rows(rows: list[dict[str, Any]], filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Apply an AND filter to the original row fields."""
    filters = filters or {}
    major_filter = _match_text(filters.get("major"))
    city_filter = _text(filters.get("city"))
    exam_filter = _text(filters.get("exam"))
    category_filter = _text(filters.get("category"))
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        city = _text(row.get("city") or row.get("reg"))
        raw_major = _match_text(row.get("zy"))
        readable_major = _match_text(clean_major_label(_text(row.get("zy"))) or "")
        if major_filter and major_filter not in raw_major and major_filter not in readable_major:
            continue
        if city_filter and city != city_filter:
            continue
        if exam_filter and _text(row.get("exam")) != exam_filter:
            continue
        if category_filter and _text(row.get("lb")) != category_filter:
            continue
        result.append(row)
    return result
