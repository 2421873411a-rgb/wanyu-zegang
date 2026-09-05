"""Small deterministic contracts mirrored by the maintainable UI."""

from __future__ import annotations

from typing import Any


def paginate_rows(rows: list[dict[str, Any]], page: int, page_size: int = 120) -> dict[str, Any]:
    """Return a bounded zero-based page without mutating the source list."""
    values = list(rows) if isinstance(rows, list) else []
    size = max(1, int(page_size))
    page_count = max(1, (len(values) + size - 1) // size)
    index = min(max(0, int(page)), page_count - 1)
    start = index * size
    return {"page": index, "page_size": size, "page_count": page_count, "total": len(values), "rows": values[start:start + size]}


def escape_csv_cell(value: object) -> str:
    text = str(value if value is not None else "")
    if text[:1] in "=+-@":
        text = "'" + text
    if any(character in text for character in ',"\r\n'):
        return '"' + text.replace('"', '""') + '"'
    return text


def announce(message: object) -> str:
    return str(message if message is not None else "").strip()


__all__ = ["announce", "escape_csv_cell", "paginate_rows"]
