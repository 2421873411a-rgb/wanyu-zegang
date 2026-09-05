"""Source snapshot registration for reproducible, auditable releases."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def register_source(
    path: Path,
    cycle: str,
    source_type: str,
    publisher: str,
    observed_at: str,
) -> dict[str, Any]:
    """Return a source record without copying the source contents."""
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    cycle_text = str(cycle).strip()
    if not re.fullmatch(r"\d{4}", cycle_text):
        raise ValueError(f"invalid cycle: {cycle!r}")
    date_text = str(observed_at).strip()
    if not _DATE_RE.fullmatch(date_text):
        raise ValueError(f"invalid observed_at date: {observed_at!r}")
    if not str(source_type).strip() or not str(publisher).strip():
        raise ValueError("source_type and publisher are required")
    digest = hashlib.sha256()
    with source_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "source_ref": source_path.resolve().as_posix(),
        "cycle": cycle_text,
        "source_type": str(source_type).strip(),
        "publisher": str(publisher).strip(),
        "observed_at": date_text,
        "bytes": source_path.stat().st_size,
        "sha256": digest.hexdigest(),
    }
