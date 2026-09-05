# -*- coding: utf-8 -*-
"""record_status 生命周期的唯一 Python 实现（wanyu-record-status/v1）。

规则（与 docs/data-contract/record-status.md 及前端 isActiveRow 防御层一致）：
- 行缺失 record_status 或等于 "active" => active（进入所有用户口径模块）。
- duplicate / invalid_source / withdrawn / superseded / needs_review => 排除出用户口径。
- 排除行保留在 jobs raw 层（canonical 行源，审计真源），只从用户模块消失。
- 生命周期标记来自构建输入 record_status_overrides.json（证据外置），builder 在进入
  业务派生前统一应用；禁止对站点产物做外科手术（v17.8.5-RC2 纪律）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .invariants import RecordLifecycleError
except ImportError:  # pragma: no cover - supports direct script imports
    from invariants import RecordLifecycleError

RECORD_STATUS_MODEL = "wanyu-record-status/v1"
STATUS_ACTIVE = "active"
EXCLUDED_STATUSES = frozenset({"duplicate", "invalid_source", "withdrawn", "superseded", "needs_review"})
ALLOWED_STATUSES = frozenset({STATUS_ACTIVE, *EXCLUDED_STATUSES})
OVERRIDES_SCHEMA = "wanyu-record-status-overrides/v1"

_EXCLUSION_FIELDS = ("record_status", "exclusion_reason", "exclusion_evidence", "excluded_at")


def overrides_path(root: Path | None = None) -> Path:
    base = Path(root) if root else Path(__file__).resolve().parents[2]
    return base / "tools" / "anhui_web" / "data" / "record_status_overrides.json"


def load_overrides(root: Path | None = None) -> dict[str, Any]:
    """Load the lifecycle input; missing file means no cycle carries exclusions."""
    path = overrides_path(root)
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != OVERRIDES_SCHEMA:
        raise ValueError(f"{path}: 生命周期输入 schema 必须是 {OVERRIDES_SCHEMA}")
    cycles = value.get("cycles")
    if not isinstance(cycles, dict):
        raise ValueError(f"{path}: 缺少 cycles 对象")
    return value


def record_status_of(row: Any) -> str:
    """生命周期状态读取（RC3-C：严格枚举）。

    缺失/空 => active；已知值原样返回；**未知值（含拼写错误）抛
    RecordLifecycleError**——禁止拼错的状态被静默当作排除处理。
    扩展枚举必须先改 docs/data-contract/record-status.md 与 ALLOWED_STATUSES。
    """
    if not isinstance(row, dict):
        raise TypeError("record_status_of 需要 dict 行")
    status = row.get("record_status")
    if not status:
        return STATUS_ACTIVE
    status = str(status)
    if status not in ALLOWED_STATUSES:
        raise RecordLifecycleError(
            f"未知 record_status {status!r}（job_id={row.get('job_id') or '?'}）；"
            f"允许值 {sorted(ALLOWED_STATUSES)}。扩展前必须先修订生命周期契约。"
        )
    return status


def is_active_record(row: Any) -> bool:
    return record_status_of(row) == STATUS_ACTIVE


def split_records(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Split into (raw, active, excluded); raw keeps every row including the excluded ones."""
    active = [row for row in rows if is_active_record(row)]
    excluded = [row for row in rows if not is_active_record(row)]
    return list(rows), active, excluded


def _cycle_rule(overrides: dict[str, Any], cycle: str) -> dict[str, Any]:
    rules = overrides.get("cycles") or {}
    rule = rules.get(str(cycle))
    if rule is None:
        return {}
    if not isinstance(rule, dict) or not isinstance(rule.get("duplicate_job_ids"), list):
        raise ValueError(f"生命周期输入 {cycle} 规则缺少 duplicate_job_ids 列表")
    for field in ("exclusion_reason", "exclusion_evidence", "excluded_at"):
        if not rule.get(field):
            raise ValueError(f"生命周期输入 {cycle} 规则缺少 {field}（禁止无证据排除）")
    return rule


def apply_overrides(rows: list[dict[str, Any]], overrides: dict[str, Any], cycle: str) -> list[dict[str, Any]]:
    """Apply the cycle's lifecycle input to raw rows in place; returns the same list.

    Idempotent: rows already carrying the exact assignment are left untouched so
    the builder can run over either a pristine bundle or a previously marked one.
    """
    rule = _cycle_rule(overrides, cycle)
    if not rule:
        return rows
    wanted = {str(job_id) for job_id in rule["duplicate_job_ids"]}
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        job_id = str(row.get("job_id") or "")
        if job_id:
            by_id[job_id] = row
    missing = sorted(wanted - set(by_id))
    if missing:
        raise ValueError(f"{cycle}: 生命周期输入引用了 {len(missing)} 个不存在的 job_id，例如 {missing[:5]}")
    assignment = {
        "record_status": "duplicate",
        "exclusion_reason": rule["exclusion_reason"],
        "exclusion_evidence": rule["exclusion_evidence"],
        "excluded_at": rule["excluded_at"],
    }
    for job_id in wanted:
        row = by_id[job_id]
        current = {field: row.get(field) for field in _EXCLUSION_FIELDS}
        if any(current.values()) and current != assignment:
            raise ValueError(
                f"{cycle}: job_id {job_id} 已带不一致的生命周期标记 {current}，与 overrides 冲突"
            )
        row.update(assignment)
    return rows
