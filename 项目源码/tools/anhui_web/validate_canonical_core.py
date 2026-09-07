# -*- coding: utf-8 -*-
"""GitHub CI 可独立执行的 canonical 核心门禁。

只依赖仓库内 canonical/schema.json + canonical/cycles/*.json，不依赖未入 Git 的
source_data/ 或 score_lists 等外部原始源。外部源完整 sha/rollup 仍由
verify_sources.py 在发布机执行；本门禁负责证明提交到 Git 的 canonical bundle
本身 schema、守恒、ID、排除证据和引用元数据没有被破坏。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
CYCLES = ("2024", "2025", "2026")
ACTIVE = (None, "active")
JOB_ID_RE = re.compile(r"^job-(\d{4})-[0-9a-f]{20}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_2026 = {
    "raw_posts": 8511,
    "active_posts": 8401,
    "excluded_posts": 110,
    "raw_recruits": 12006,
    "recruits": 11883,
}


def _int(value, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label}: bool 不是人数")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}: 不是整数 {value!r}") from exc
    if number < 0:
        raise ValueError(f"{label}: 不能为负数")
    return number


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_cycle(cycle: str, schema: dict) -> list[str]:
    path = ROOT / "canonical" / "cycles" / f"{cycle}.json"
    if not path.is_file():
        return [f"{cycle}: canonical bundle 缺失"]
    doc = _load(path)
    errors: list[str] = []

    schema_errors = sorted(
        Draft202012Validator(schema).iter_errors(doc),
        key=lambda e: list(e.absolute_path),
    )
    for err in schema_errors[:20]:
        where = ".".join(map(str, err.absolute_path)) or "<root>"
        errors.append(f"{cycle}: schema @ {where}: {err.message}")

    group = doc.get("all_majors") or {}
    rows = group.get("rows") or []
    meta = group.get("meta") or {}
    metrics = doc.get("metrics") or {}
    if not isinstance(rows, list):
        return errors + [f"{cycle}: all_majors.rows 不是数组"]

    ids: set[str] = set()
    raw_recruits = 0
    active_posts = 0
    recruits = 0
    excluded_posts = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"{cycle}: rows[{index}] 不是对象")
            continue
        job_id = row.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            errors.append(f"{cycle}: rows[{index}] job_id 缺失")
        elif job_id in ids:
            errors.append(f"{cycle}: job_id 重复 {job_id}")
        else:
            ids.add(job_id)
            match = JOB_ID_RE.fullmatch(job_id)
            if not match or match.group(1) != cycle:
                errors.append(f"{cycle}: job_id 格式/周期非法 {job_id}")

        try:
            num = _int(row.get("num"), f"{cycle}.rows[{index}].num")
        except ValueError as exc:
            errors.append(str(exc))
            num = 0
        raw_recruits += num
        status = row.get("record_status")
        if status in ACTIVE:
            active_posts += 1
            recruits += num
        else:
            excluded_posts += 1
            for field in ("exclusion_reason", "exclusion_evidence", "excluded_at"):
                value = row.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{cycle}: 排除行 {job_id} 缺 {field}")

    facts = {
        "raw_posts": len(rows),
        "active_posts": active_posts,
        "excluded_posts": excluded_posts,
        "raw_recruits": raw_recruits,
        "recruits": recruits,
    }
    for name, actual in facts.items():
        if metrics.get(name) != actual:
            errors.append(f"{cycle}: metrics.{name}={metrics.get(name)!r}, 行级={actual}")
    if meta.get("raw_total") != facts["raw_posts"]:
        errors.append(f"{cycle}: meta.raw_total 与行数不一致")
    if meta.get("excluded") != excluded_posts:
        errors.append(f"{cycle}: meta.excluded 与排除行数不一致")
    if cycle == "2026" and any(metrics.get(k) != v for k, v in EXPECTED_2026.items()):
        errors.append(f"2026: 回归锁定失败，期望 {EXPECTED_2026}")

    score_state = doc.get("score_state") or {}
    if score_state.get("mode") != "reference" or score_state.get("cycle") != cycle:
        errors.append(f"{cycle}: score_state mode/cycle 非法")
    score_sha = score_state.get("sha256")
    if not isinstance(score_sha, str) or not SHA_RE.fullmatch(score_sha):
        errors.append(f"{cycle}: score_state.sha256 非法")
    score_file = score_state.get("file")
    if not isinstance(score_file, str) or not score_file.strip():
        errors.append(f"{cycle}: score_state.file 缺失")

    provenance = doc.get("provenance") or {}
    set_sha = provenance.get("job_id_set_sha256")
    if not isinstance(set_sha, str) or not SHA_RE.fullmatch(set_sha):
        errors.append(f"{cycle}: provenance.job_id_set_sha256 非法")
    for entry in provenance.get("seed_inputs") or []:
        if not isinstance(entry, dict):
            errors.append(f"{cycle}: provenance.seed_inputs 含非对象")
            continue
        for field in ("path", "role", "sha256"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                errors.append(f"{cycle}: seed_input 缺 {field}")
        if isinstance(entry.get("sha256"), str) and not SHA_RE.fullmatch(entry["sha256"]):
            errors.append(f"{cycle}: seed_input sha256 非法")

    # 额外锁一个可复算的 canonical 本体指纹，便于 CI 日志追踪实际验证了哪个文件。
    print(
        f"{cycle}: posts={facts['raw_posts']} active={active_posts} recruits={recruits} "
        f"bundle_sha256={hashlib.sha256(path.read_bytes()).hexdigest()}"
    )
    return errors


def main() -> int:
    schema_path = ROOT / "canonical" / "schema.json"
    if not schema_path.is_file():
        print("canonical/schema.json 缺失", file=sys.stderr)
        return 1
    actual_cycles = tuple(sorted(p.stem for p in (ROOT / "canonical" / "cycles").glob("*.json")))
    if actual_cycles != CYCLES:
        print(f"周期集合异常: {actual_cycles} != {CYCLES}", file=sys.stderr)
        return 1

    schema = _load(schema_path)
    failures: list[str] = []
    for cycle in CYCLES:
        failures.extend(_validate_cycle(cycle, schema))
    if failures:
        for failure in failures[:50]:
            print("VIOLATION:", failure, file=sys.stderr)
        print(f"canonical core: FAIL ({len(failures)} violations)", file=sys.stderr)
        return 1
    print("canonical core: PASS (schema + conservation + ids + exclusion evidence + reference metadata)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
