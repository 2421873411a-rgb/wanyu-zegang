"""Shared, conservative quality annotations for the three-cycle workbench.

This module does not repair source facts.  It adds derived metadata to a copied
row so the UI can distinguish an observed value from an unavailable value and
can refuse comparisons whose scale or denominator is not comparable.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any


EXAM_ALIASES = {
    "事业编": "事业单位",
    "事业单位": "事业单位",
    "省考": "省考",
    "国考": "国考",
}


def normalise_exam(value: Any) -> str:
    text = str(value or "").strip()
    return EXAM_ALIASES.get(text, text)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
    else:
        text = _text(value).replace(",", "").replace("，", ",")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None
        numeric = float(match.group(0))
    return numeric if math.isfinite(numeric) else None


def _row_value(row: dict[str, Any], key: str, *field_names: str) -> Any:
    for candidate in (key, *field_names):
        if candidate in row and row.get(candidate) not in (None, ""):
            return row.get(candidate)
    fields = row.get("fields")
    if isinstance(fields, dict):
        for name in field_names:
            if fields.get(name) not in (None, "", "—"):
                return fields.get(name)
    return None


def stable_job_id(cycle: str, row: dict[str, Any]) -> str:
    """Return an order-independent identity for a published position row.

    The unit and position title are intentionally part of the identity: a
    reused position code is not sufficient to distinguish two agencies.  The
    result is a deterministic hash, so inserting or reordering rows does not
    detach user-local state.  Truly identical duplicate source rows remain a
    quality issue and are not silently de-duplicated here.
    """

    identity = {
        "cycle": _text(cycle),
        "exam": normalise_exam(row.get("exam")),
        "batch": _text(row.get("cycle")),
        "city": _text(row.get("city")),
        "code": _text(row.get("code")),
        "unit": _text(row.get("unit") or row.get("unit_position")),
        "title": _text(row.get("zw") or row.get("title")),
    }
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]
    return f"job-{_text(cycle)}-{digest}"


def classify_score_observation(row: dict[str, Any]) -> dict[str, Any]:
    """Classify a row's cutoff value without guessing an absent scale."""

    exam = normalise_exam(row.get("exam"))
    raw = _row_value(row, "line", "最低入围/线", "最低面试线")
    value = _number(raw)
    base = {
        "metric_type": "cutoff",
        "stage": "cutoff",
        "unit": "分",
        "value": value,
        "scale_id": None,
    }
    if exam not in {"事业单位", "省考"}:
        return {**base, "status": "not_applicable", "reason": "当前模拟器不覆盖该考试类别"}
    if value is None:
        return {**base, "status": "unavailable", "reason": "来源没有可解析的入围线"}
    if value <= 0:
        return {**base, "status": "suspected_sentinel", "reason": "非正数按缺失哨兵处理，不参与比较"}
    if exam == "事业单位" and 120 <= value <= 300:
        return {**base, "status": "comparable", "scale_id": "syb_300", "reason": "事业单位笔试合成分范围"}
    if exam == "省考" and 30 <= value <= 100:
        return {**base, "status": "comparable", "scale_id": "province_100", "reason": "省考笔试合成分范围"}
    return {**base, "status": "incompatible_scale", "reason": "数值存在，但不符合当前模拟器的已知量纲"}


def _count_observation(value: Any) -> dict[str, Any]:
    numeric = _number(value)
    if numeric is None:
        return {"value": None, "status": "unavailable"}
    if numeric == 0:
        return {"value": 0, "status": "suspected_sentinel"}
    if numeric < 0 or int(numeric) != numeric:
        return {"value": numeric, "status": "invalid"}
    return {"value": int(numeric), "status": "observed"}


def competition_observations(row: dict[str, Any]) -> dict[str, Any]:
    """Keep registration and examinee denominators as separate observations."""

    registration_raw = _row_value(row, "bm", "registrations", "报名*", "报名")
    examinee_raw = _row_value(row, "adv", "examinees", "有效笔试/达线/规模参考", "有效笔试/达线")
    registrations = _count_observation(registration_raw)
    examinees = _count_observation(examinee_raw)
    preferred = None
    observed_examinee_type = "interview_shortlisted" if normalise_exam(row.get("exam")) == "国考" else "examinees"
    if examinees["status"] == "observed" and examinees["value"] > 0:
        preferred = observed_examinee_type
    elif registrations["status"] == "observed" and registrations["value"] > 0:
        preferred = "registrations"
    return {
        "registrations": registrations,
        "examinees": examinees,
        "preferred_type": preferred,
    }


def annotate_position_row(cycle: str, row: dict[str, Any]) -> dict[str, Any]:
    """Return a copied row with conservative, machine-readable quality facts."""

    result = dict(row)
    job_id = stable_job_id(cycle, result)
    legacy_id = result.get("row_id")
    if legacy_id and str(legacy_id) != job_id:
        result["legacy_row_id"] = str(legacy_id)
    result["job_id"] = job_id
    result["row_id"] = job_id
    recruits = _number(result.get("num") if result.get("num") is not None else result.get("recruits"))
    result["job_status"] = "active" if recruits is not None and recruits > 0 else "recruit_count_review"
    result["title_status"] = "published" if _text(result.get("zw")) else "not_separately_published"
    result["display_title"] = _text(result.get("zw")) or "源表未单列披露"
    result["score_observation"] = classify_score_observation(result)
    result["competition_observations"] = competition_observations(result)
    return result
