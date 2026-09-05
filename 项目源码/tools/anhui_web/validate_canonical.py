# -*- coding: utf-8 -*-
"""v17.8.6 阶段 G：canonical 唯一正式数据输入的独立验证器（fail-closed）。

三层验证，任何一项失败 → exit 1（不修复、不落盘）：
  1. 真 JSON Schema：jsonschema Draft 2020-12 对照 canonical/schema.json；
  2. 业务守恒：raw_posts = 行数 = active + excluded；raw_recruits = Σ 全部 num；
     recruits = Σ active num；meta.raw_total/excluded 与 metrics 对账；
  3. 严格性：job_id 非空/唯一/格式/周期前缀；排除行证据三元组
     （exclusion_reason/exclusion_evidence/excluded_at）；provenance sha 格式；
     score_state（mode=reference、文件存在、磁盘 sha256 匹配、周期一致）；
     2026 回归锁定（8511/8401/110/12006/11883）。

用法：python tools/anhui_web/validate_canonical.py --root .
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from jsonschema import Draft202012Validator  # noqa: E402

from tools.anhui_web.invariants import require_int  # noqa: E402

CYCLES = ("2024", "2025", "2026")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
JOB_ID_RE = re.compile(r"^job-(\d{4})-[0-9a-f]{20}$")
ACTIVE_STATUSES = (None, "active")
# RC3 审计收口后的 2026 回归锁定值（2024/2025 由守恒公式约束，无历史锁定）。
EXPECTED_2026 = {
    "raw_posts": 8511, "active_posts": 8401, "excluded_posts": 110,
    "raw_recruits": 12006, "recruits": 11883,
}
MAX_REPORT = 12


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_schema(doc: dict, schema: dict, violations: list[str], cycle: str) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    for err in errors[:MAX_REPORT]:
        path = ".".join(str(p) for p in err.absolute_path) or "<root>"
        violations.append(f"{cycle}: schema 违规 @ {path}: {err.message}")
    if len(errors) > MAX_REPORT:
        violations.append(f"{cycle}: schema 违规共 {len(errors)} 处（仅报告前 {MAX_REPORT} 条）")


def _require_str(value: object, field: str, violations: list[str], cycle: str) -> str:
    if not isinstance(value, str) or not value.strip():
        violations.append(f"{cycle}: {field} 必须为非空字符串")
        return ""
    return value


def validate_cycle(root: Path, cycle: str, schema: dict) -> dict[str, object]:
    doc = json.loads((root / "canonical" / "cycles" / f"{cycle}.json").read_text(encoding="utf-8"))
    violations: list[str] = []
    _validate_schema(doc, schema, violations, cycle)

    rows = doc["all_majors"]["rows"]
    metrics = doc["metrics"]
    meta = doc["all_majors"]["meta"]

    raw_posts = len(rows)
    raw_recruits = 0
    active_posts = 0
    recruits = 0
    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []
    for index, row in enumerate(rows):
        num = require_int(row.get("num"), f"rows[{index}].num")
        raw_recruits += num
        status = row.get("record_status")
        job_id = row.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            violations.append(f"{cycle}: rows[{index}] job_id 非空字符串缺失")
        elif job_id in seen_ids:
            duplicate_ids.append(job_id)
        else:
            seen_ids.add(job_id)
            match = JOB_ID_RE.match(job_id)
            if not match:
                violations.append(f"{cycle}: job_id 格式非法：{job_id}")
            elif match.group(1) != cycle:
                violations.append(f"{cycle}: job_id 周期前缀不匹配：{job_id}")
        if status in ACTIVE_STATUSES:
            active_posts += 1
            recruits += num
        else:
            for field in ("exclusion_reason", "exclusion_evidence", "excluded_at"):
                value = row.get(field)
                if not isinstance(value, str) or not value.strip():
                    violations.append(f"{cycle}: 排除行 {job_id} 缺证据字段 {field}")

    if raw_posts != active_posts + len([r for r in rows if r.get("record_status") not in ACTIVE_STATUSES]):
        violations.append(f"{cycle}: raw_posts != active + excluded（行层守恒破坏）")
    for name, actual, expected in (
        ("raw_posts", raw_posts, metrics.get("raw_posts")),
        ("active_posts", active_posts, metrics.get("active_posts")),
        ("raw_recruits", raw_recruits, metrics.get("raw_recruits")),
        ("recruits", recruits, metrics.get("recruits")),
        ("excluded_posts", raw_posts - active_posts, metrics.get("excluded_posts")),
        ("meta.raw_total", raw_posts, meta.get("raw_total")),
        ("meta.excluded", raw_posts - active_posts, meta.get("excluded")),
    ):
        if actual != expected:
            violations.append(f"{cycle}: 守恒失败 {name}: 行级={actual} 声明={expected}")
    if duplicate_ids:
        violations.append(f"{cycle}: job_id 重复 {len(duplicate_ids)} 个：{duplicate_ids[:3]}")
    if cycle == "2026" and {k: metrics.get(k) for k in EXPECTED_2026} != EXPECTED_2026:
        violations.append(f"{cycle}: 2026 回归锁定失败：{metrics} != {EXPECTED_2026}")

    score_state = doc.get("score_state") or {}
    if score_state.get("mode") != "reference":
        violations.append(f"{cycle}: score_state.mode 必须 = reference")
    score_file = _require_str(score_state.get("file"), "score_state.file", violations, cycle)
    score_sha = _require_str(score_state.get("sha256"), "score_state.sha256", violations, cycle)
    if score_sha and not SHA_RE.match(score_sha):
        violations.append(f"{cycle}: score_state.sha256 非 64 位小写十六进制")
    if score_file:
        score_path = root / score_file
        if not score_path.is_file():
            violations.append(f"{cycle}: score_state 文件不存在：{score_file}")
        elif score_sha and _sha256(score_path) != score_sha:
            violations.append(f"{cycle}: score_state sha256 与磁盘不符：{score_file}")
    if score_state.get("cycle") != cycle:
        violations.append(f"{cycle}: score_state.cycle = {score_state.get('cycle')!r} 与周期不符")

    provenance = doc.get("provenance") or {}
    for entry in provenance.get("seed_inputs") or []:
        path_value = _require_str(entry.get("path"), "provenance.seed_inputs[].path", violations, cycle)
        _require_str(entry.get("role"), "provenance.seed_inputs[].role", violations, cycle)
        entry_sha = _require_str(entry.get("sha256"), "provenance.seed_inputs[].sha256", violations, cycle)
        if entry_sha and not SHA_RE.match(entry_sha):
            violations.append(f"{cycle}: provenance.seed_inputs sha256 非法：{path_value}")
    job_set_sha = str(provenance.get("job_id_set_sha256") or "")
    if not SHA_RE.match(job_set_sha):
        violations.append(f"{cycle}: provenance.job_id_set_sha256 非法")
    if not isinstance(provenance.get("recovery_attempted"), str) or not provenance.get("recovery_attempted"):
        violations.append(f"{cycle}: provenance.recovery_attempted 缺失")
    for field in ("verified_facts", "unverifiable_without_legacy"):
        if not isinstance(provenance.get(field), list):
            violations.append(f"{cycle}: provenance.{field} 必须为数组")

    audit_ref = doc.get("audit_ref") or {}
    _require_str(audit_ref.get("file"), "audit_ref.file", violations, cycle)
    _require_str(audit_ref.get("cycle_entry"), "audit_ref.cycle_entry", violations, cycle)
    return {"violations": violations, "facts": {
        "raw_posts": raw_posts, "active_posts": active_posts, "excluded_posts": raw_posts - active_posts,
        "raw_recruits": raw_recruits, "recruits": recruits,
    }}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate canonical cycle bundles (schema + conservation + strictness)")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    root = args.root.resolve()
    schema = json.loads((root / "canonical" / "schema.json").read_text(encoding="utf-8"))
    violations: list[str] = []
    found_cycles = sorted(p.stem for p in (root / "canonical" / "cycles").glob("*.json"))
    if tuple(found_cycles) != CYCLES:
        violations.append(f"canonical/cycles 周期集合异常：{found_cycles} != {list(CYCLES)}")
    all_facts: dict[str, dict[str, object]] = {}
    for cycle in CYCLES:
        result = validate_cycle(root, cycle, schema)
        violations.extend(result["violations"])
        all_facts[cycle] = result["facts"]
    print("canonical 验证：", json.dumps(all_facts, ensure_ascii=False))
    if violations:
        for item in violations[:MAX_REPORT]:
            print("VIOLATION:", item, file=sys.stderr)
        if len(violations) > MAX_REPORT:
            print(f"VIOLATION: 共 {len(violations)} 项（仅报告前 {MAX_REPORT} 条）", file=sys.stderr)
        print(f"validate_canonical: FAIL（{len(violations)} 项违规）", file=sys.stderr)
        return 1
    print("validate_canonical: PASS（schema + 守恒 + 溯源 + score_state + 2026 回归锁定）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
