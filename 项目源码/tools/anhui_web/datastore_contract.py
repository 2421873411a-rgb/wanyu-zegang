"""Python-side checks shared by the maintainable-site verifier and release gates."""

from __future__ import annotations

import hashlib
import json
from typing import Any


MODULE_SCHEMAS = {
    "overview": "wanyu-maintainable-overview/v1",
    "jobs": "wanyu-maintainable-jobs/v1",
    "catalog": "wanyu-maintainable-catalog/v1",
    "positions": "wanyu-maintainable-position-index/v1",
    "scores": "wanyu-maintainable-scores/v1",
    "changes": "wanyu-maintainable-changes/v1",
    "audit": "wanyu-maintainable-audit/v1",
}


def module_path(manifest: dict[str, Any], cycle: str, module: str) -> str | None:
    """Resolve a module only through the manifest, never through a path guess."""
    if cycle == "audit" and module == "three-year":
        entry = manifest.get("audit")
        return str(entry.get("data")) if isinstance(entry, dict) and entry.get("data") else None
    if cycle == "review_queue" and module == "queue":
        entry = manifest.get("review_queue")
        return str(entry.get("data")) if isinstance(entry, dict) and entry.get("data") else None
    entries = manifest.get("cycles") if isinstance(manifest.get("cycles"), list) else []
    cycle_entry = next((item for item in entries if str(item.get("cycle")) == str(cycle) and isinstance(item, dict)), None)
    if not isinstance(cycle_entry, dict):
        return None
    modules = cycle_entry.get("modules") if isinstance(cycle_entry.get("modules"), dict) else {}
    entry = modules.get(module) if isinstance(modules.get(module), dict) else {}
    if entry.get("data"):
        return str(entry["data"])
    if module == "jobs" and cycle_entry.get("data"):
        return str(cycle_entry["data"])
    return None


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def verify_module_payload(
    module: str,
    payload: dict[str, Any],
    manifest_entry: dict[str, Any],
    *,
    encoded: bytes | None = None,
) -> None:
    """Validate schema and, when available, the exact manifest byte contract."""
    expected_schema = MODULE_SCHEMAS.get(module)
    if not expected_schema:
        raise ValueError(f"unknown module: {module}")
    if not isinstance(payload, dict):
        raise ValueError(f"{module}: payload must be an object")
    if payload.get("schema") != expected_schema:
        raise ValueError(f"{module}: schema mismatch")
    if not isinstance(manifest_entry, dict):
        raise ValueError(f"{module}: manifest entry must be an object")
    bytes_to_check = encoded if encoded is not None else _canonical_bytes(payload)
    expected_bytes = manifest_entry.get("bytes")
    if expected_bytes is not None and int(expected_bytes) != len(bytes_to_check):
        raise ValueError(f"{module}: byte count mismatch")
    expected_hash = manifest_entry.get("sha256")
    if expected_hash and hashlib.sha256(bytes_to_check).hexdigest() != str(expected_hash):
        raise ValueError(f"{module}: sha256 mismatch")


__all__ = ["MODULE_SCHEMAS", "module_path", "verify_module_payload"]
