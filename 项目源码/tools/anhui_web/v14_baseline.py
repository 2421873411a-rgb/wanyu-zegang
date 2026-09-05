"""Read-only v13.4 anchors used to explain every v14.0 data delta."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def load_baseline(path: Path) -> dict[str, Any]:
    """Load the frozen baseline and reject incomplete anchors."""
    value = _read_json(Path(path))
    required = {"release", "snapshot_date", "cycles", "summary", "sources"}
    missing = required - set(value)
    if missing:
        raise ValueError(f"baseline missing keys: {sorted(missing)}")
    if value["release"] != "v13.4":
        raise ValueError(f"baseline release must be v13.4, got {value['release']!r}")
    if set(value["cycles"]) != {"2024", "2025", "2026"}:
        raise ValueError("baseline must contain exactly 2024, 2025 and 2026")
    for cycle, item in value["cycles"].items():
        if not isinstance(item, dict) or not all(key in item for key in ("posts", "recruits", "score_unresolved")):
            raise ValueError(f"baseline cycle {cycle} is incomplete")
    return value


def snapshot_site(root: Path) -> dict[str, Any]:
    """Return current maintainable-site facts for a deterministic pre-upgrade diff."""
    root = Path(root)
    # RC3：快照读取部署树（deliverables 镜像随构建图退役）
    manifest_path = root.parent / "网站" / "data" / "site-manifest.json"
    audit_path = root.parent / "网站" / "data" / "audit" / "three-year.json"
    manifest = _read_json(manifest_path)
    audit = _read_json(audit_path)
    cycles: dict[str, Any] = {}
    for item in manifest.get("cycles", []):
        cycle = str(item.get("cycle"))
        cycles[cycle] = {
            "posts": int(item.get("posts") or 0),
            "recruits": int(item.get("recruits") or 0),
            "score_unresolved": int(item.get("score_unresolved") or 0),
            "modules": set((item.get("modules") or {}).keys()),
        }
    summary = audit.get("summary") or {}
    return {
        "release": manifest.get("release"),
        "snapshot_date": manifest.get("snapshot_date"),
        "cycles": cycles,
        "summary": {
            "posts": int(summary.get("post_count") or 0),
            "recruits": int(summary.get("recruit_count") or 0),
            "gaps": int(summary.get("gap_count") or 0),
            "score_unresolved": int(summary.get("unresolved_score_count") or 0),
        },
    }
