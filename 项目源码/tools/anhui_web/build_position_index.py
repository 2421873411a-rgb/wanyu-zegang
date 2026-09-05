"""Build a compact lookup index for position details and evidence drawers."""

from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Any

from .data_contract import evidence, make_record_id


def _record_id(row: dict[str, Any], source_registry: dict[str, Any]) -> str:
    existing = str(row.get("job_id") or row.get("row_id") or "").strip()
    if existing:
        return existing
    cycle = str(row.get("cycle") or source_registry.get("cycle") or "").strip()
    if re.fullmatch(r"\d{4}", cycle):
        return make_record_id(cycle, row)
    encoded = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"position-{hashlib.sha256(encoded).hexdigest()[:20]}"


def _source_status(row: dict[str, Any]) -> tuple[str, str]:
    source_note = str(row.get("source_note") or "").strip()
    if "官方" in source_note:
        return "verified", "official_page"
    if source_note:
        return "source_bundle", "source_bundle"
    return "derived", "derived"


def build_position_index(rows: list[dict[str, Any]], source_registry: dict[str, Any]) -> dict[str, Any]:
    """Create lookup metadata while leaving the supplied source rows untouched."""
    source_registry = dict(source_registry or {})
    source_ref = str(source_registry.get("source_ref") or "jobs.json").strip()
    raw_observed_at = source_registry.get("observed_at")
    observed_at = str(raw_observed_at).strip() if raw_observed_at not in (None, "") else None
    if observed_at is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", observed_at):
        raise ValueError(f"invalid source registry observed_at: {observed_at!r}")
    result_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        record_id = _record_id(row, source_registry)
        if record_id in seen:
            raise ValueError(f"duplicate position index record_id: {record_id}")
        seen.add(record_id)
        status, method = _source_status(row)
        result_rows.append(
            {
                "record_id": record_id,
                "detail_ref": {"module": "jobs", "row_index": index},
                "lookup": {
                    "code": str(row.get("code") or ""),
                    "city": str(row.get("city") or row.get("reg") or ""),
                    "exam": str(row.get("exam") or ""),
                    "unit": str(row.get("unit") or ""),
                    "post_name": str(row.get("zw") or row.get("post_name") or row.get("display_title") or ""),
                    "major": str(row.get("zy") or ""),
                    "category": str(row.get("lb") or ""),
                },
                "source": evidence(
                    status,
                    source_ref,
                    f"jobs.json#allMajors.rows[{index}]",
                    method,
                    observed_at,
                    "详情展示源字段；目录清洗不覆盖原始岗位文本",
                ),
            }
        )
    return {
        "schema": "wanyu-maintainable-position-index/v1",
        "cycle": str(source_registry.get("cycle") or ""),
        "row_count": len(result_rows),
        "source_module": "jobs.json",
        "rows": result_rows,
    }


def find_position(rows: list[dict[str, Any]], record_id: str) -> dict[str, Any] | None:
    target = str(record_id or "").strip()
    for row in rows:
        if isinstance(row, dict) and str(row.get("job_id") or row.get("row_id") or "").strip() == target:
            return row
    return None


def render_evidence_panel(position: dict[str, Any], audit: dict[str, Any]) -> str:
    """Render a small, safe HTML evidence block for unit tests and server reports."""
    del audit
    labels = {
        "verified": "已核验",
        "source_bundle": "源包接入",
        "derived": "派生指标",
        "unpublished_or_unavailable": "未发布或未取得",
        "ambiguous_join": "无法唯一关联",
        "needs_review": "待复核",
    }
    fields: list[str] = []
    for key, value in position.items():
        if key.endswith("_status") and value in labels:
            base = key.removesuffix("_status")
            if position.get(base) in (None, ""):
                fields.append(f"<div>{html.escape(base)}：{html.escape(labels[value])}</div>")
    source = position.get("source") if isinstance(position.get("source"), dict) else {}
    if source:
        fields.append(f"<div>证据状态：{html.escape(labels.get(str(source.get('status')), str(source.get('status') or '未知')))}</div>")
        fields.append(f"<div>来源：{html.escape(str(source.get('source_ref') or '未提供'))}</div>")
    return "<section class=\"evidence-panel\">" + "".join(fields) + "</section>"
