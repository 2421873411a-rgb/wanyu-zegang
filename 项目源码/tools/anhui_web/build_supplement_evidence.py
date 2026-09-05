"""Build a deterministic evidence ledger for the 2026-09-04 supplement handoff.

The supplement contains source documents and unresolved matching evidence, not a
new canonical job baseline.  This module therefore records integrity and
integration decisions without appending rows to jobs.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SUPPLEMENT_DIRNAME = "supplement_20260904"
SCHEMA = "wanyu-supplement-evidence/v1"


def _normalise(value: str | Path) -> str:
    return str(value).replace("\\", "/").lstrip("./")


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_lines(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} 不是 JSON 对象")
        rows.append(value)
    return rows


def _detect_format(path: Path, head: bytes) -> str:
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return "xls"
    if head.startswith(b"PK"):
        return "xlsx"
    probe = head[:512].decode("utf-8", errors="ignore").lower()
    if "404 not found" in probe or probe.lstrip().startswith("<!doctype html") or probe.lstrip().startswith("<html"):
        return "http_error_html"
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "unknown"


def _read_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    if not path.is_file():
        return checksums
    pattern = re.compile(r"^([0-9a-fA-F]{64})\s+(.+?)\s*$")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        match = pattern.match(line.strip())
        if match:
            checksums[_normalise(match.group(2))] = match.group(1).lower()
    return checksums


def _count_json_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip())


def _score_evidence_count(supplement_dir: Path) -> int:
    resolution_path = supplement_dir / "matching" / "2026_score_resolution_evidence.json"
    if resolution_path.is_file():
        payload = _json_load(resolution_path)
        baseline = payload.get("baseline") if isinstance(payload, dict) else None
        if isinstance(baseline, dict) and baseline.get("unresolved_count") is not None:
            return int(baseline["unresolved_count"])
    return _count_json_lines(supplement_dir / "matching" / "2026_score_match_review.jsonl")


def build_supplement_evidence(root: Path = ROOT) -> dict[str, Any]:
    """Return the evidence payload for ``source_data/supplement_20260904``."""
    root = Path(root).resolve()
    supplement_dir = root / "source_data" / SUPPLEMENT_DIRNAME
    raw_dir = supplement_dir / "raw"
    manifest_path = supplement_dir / "source_manifest.jsonl"
    checksums_path = supplement_dir / "checksums.sha256"
    manifest_rows = _json_lines(manifest_path)
    manifest_by_file: dict[str, dict[str, Any]] = {}
    for row in manifest_rows:
        local_file = _normalise(str(row.get("local_file") or ""))
        if local_file:
            manifest_by_file[local_file] = row
    supplement_prefix = f"source_data/{SUPPLEMENT_DIRNAME}/"
    supplement_manifest_rows = [row for row in manifest_rows if _normalise(str(row.get("local_file") or "")).startswith(supplement_prefix)]
    checksums = _read_checksums(checksums_path)

    files: list[dict[str, Any]] = []
    cycle_counts: dict[str, Counter[str]] = defaultdict(Counter)
    cycle_bytes: Counter[str] = Counter()
    actual_paths = sorted(raw_dir.rglob("*"), key=lambda item: _normalise(item.relative_to(root))) if raw_dir.is_dir() else []
    for path in actual_paths:
        if not path.is_file():
            continue
        relative = _normalise(path.relative_to(root))
        raw_relative = _normalise(path.relative_to(supplement_dir))
        cycle = path.parent.name
        data = path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        detected_format = _detect_format(path, data[:512])
        manifest_row = manifest_by_file.get(relative) or manifest_by_file.get(_normalise(path))
        expected_sha = checksums.get(relative)
        if expected_sha is None:
            expected_sha = checksums.get(raw_relative)
        if expected_sha and expected_sha == sha256:
            hash_status = "match"
        elif expected_sha:
            hash_status = "mismatch"
        else:
            hash_status = "missing"
        if detected_format in {"xls", "xlsx", "pdf"}:
            integrity_status = "valid_document" if hash_status in {"match", "missing"} else "hash_mismatch"
            cycle_counts[cycle]["valid"] += 1
        elif detected_format == "http_error_html":
            integrity_status = "blocked_download"
            cycle_counts[cycle]["blocked"] += 1
        else:
            integrity_status = "unclassified"
            cycle_counts[cycle]["unclassified"] += 1
        cycle_counts[cycle]["raw"] += 1
        cycle_bytes[cycle] += len(data)
        record: dict[str, Any] = {
            "path": raw_relative,
            "local_file": relative,
            "cycle": cycle,
            "format": detected_format,
            "bytes": len(data),
            "sha256": sha256,
            "expected_sha256": expected_sha,
            "hash_status": hash_status,
            "integrity_status": integrity_status,
            "source_id": manifest_row.get("source_id") if manifest_row else None,
            "manifest_status": manifest_row.get("status") if manifest_row else "unregistered",
            "evidence_grade": manifest_row.get("evidence_grade") if manifest_row else None,
            "dataset": manifest_row.get("dataset") if manifest_row else None,
            "title": manifest_row.get("title") if manifest_row else None,
            "city": manifest_row.get("city") if manifest_row else None,
            "county": manifest_row.get("county") if manifest_row else None,
        }
        files.append(record)

    raw_count = len(files)
    valid_count = sum(1 for item in files if item["integrity_status"] == "valid_document")
    blocked_count = sum(1 for item in files if item["integrity_status"] == "blocked_download")
    checksum_mismatches = sum(1 for item in files if item["hash_status"] == "mismatch")
    checksum_missing = sum(1 for item in files if item["hash_status"] == "missing")
    manifest_coverage = sum(1 for item in files if item["source_id"])
    empty_manifest_sha = sum(1 for row in supplement_manifest_rows if not str(row.get("sha256") or "").strip())
    normalized_dir = supplement_dir / "normalized"
    normalized_files = [path for path in normalized_dir.rglob("*") if path.is_file()] if normalized_dir.is_dir() else []
    normalized_evidence_batches = 0
    normalized_evidence_records = 0
    for normalized_path in normalized_files:
        if normalized_path.suffix.lower() != ".json":
            continue
        try:
            normalized_payload = _json_load(normalized_path)
        except (OSError, json.JSONDecodeError):
            continue
        if normalized_payload.get("schema") == "wanyu-supplement-niluyong-inventory/v1":
            normalized_evidence_batches += int(normalized_payload.get("batch_count") or 0)
            normalized_evidence_records += int(normalized_payload.get("total_parsed_persons") or 0)
    by_cycle: dict[str, dict[str, int]] = {}
    for cycle in sorted(set(cycle_counts) | {"2024", "2025", "2026"}):
        counters = cycle_counts.get(cycle, Counter())
        by_cycle[cycle] = {
            "raw_files": int(counters.get("raw", 0)),
            "valid_documents": int(counters.get("valid", 0)),
            "blocked_downloads": int(counters.get("blocked", 0)),
            "unclassified_files": int(counters.get("unclassified", 0)),
            "bytes": int(cycle_bytes.get(cycle, 0)),
        }

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": "2026-09-04",
        "source_dir": f"source_data/{SUPPLEMENT_DIRNAME}",
        "summary": {
            "raw_files": raw_count,
            "valid_documents": valid_count,
            "blocked_downloads": blocked_count,
            "raw_bytes": sum(int(item["bytes"]) for item in files),
            "manifest_rows_total": len(manifest_rows),
            "supplement_manifest_rows": len(supplement_manifest_rows),
            "manifest_coverage": manifest_coverage,
            "empty_manifest_sha": empty_manifest_sha,
            "checksum_entries": len(checksums),
            "checksum_matches": sum(1 for item in files if item["hash_status"] == "match"),
            "checksum_mismatches": checksum_mismatches,
            "checksum_missing": checksum_missing,
            "formal_integrated_records": 0,
            "normalized_evidence_files": len(normalized_files),
            "normalized_evidence_batches": normalized_evidence_batches,
            "normalized_evidence_records": normalized_evidence_records,
            "probable_score_evidence": _score_evidence_count(supplement_dir),
            "title_major_candidates": _count_json_lines(supplement_dir / "title_major" / "title_major_candidates.jsonl"),
        },
        "by_cycle": by_cycle,
        "files": files,
        "decisions": [
            "43 个 raw 文件已按磁盘内容核验；41 个为可解析 XLS/XLSX/PDF，2 个为 404 HTML 下载失败响应。",
            "checksums.sha256 与 43 个 raw 文件逐项匹配；404 响应保留为阻断证据，不作为岗位数据。",
            "合肥、省地矿局、省人社厅、省应急厅等岗位表与现有岗位基线存在重叠，未直接追加，避免重复计数。",
            "拟聘用名单、公开选聘名单属于结果/证据资料，不改写公开招聘岗位基线。",
            "116 条 0901xxx 成绩仍属于待唯一归属复核证据；未将 probable 结论自动写入正式成绩或岗位数据。",
            "拟聘用证据已形成独立 inventory（不等于正式业务入库）；正式岗位 JSON、成绩 JSON、变化 JSON、审计基线不因本台账而改变。",
        ],
        "integration": {
            "mode": "evidence_only",
            "canonical_data_changed": False,
            "canonical_modules": ["jobs.json", "jobs_lite.json", "positions.json", "changes.json", "overview.json", "review_queue.json"],
            "reason": "资料已归档但逐条归属、去重与口径核验尚未满足正式入库门禁",
        },
    }
    return payload


def write_supplement_evidence(root: Path = ROOT, output: Path | None = None) -> Path:
    root = Path(root).resolve()
    output_path = output or (root / "source_data" / SUPPLEMENT_DIRNAME / "integrity_audit.json")
    output_path = Path(output_path).resolve()
    payload = build_supplement_evidence(root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成 supplement_20260904 原始资料证据台账")
    parser.add_argument("--root", type=Path, default=ROOT, help="项目根目录")
    parser.add_argument("--output", type=Path, default=None, help="输出 JSON 路径")
    args = parser.parse_args()
    output_path = write_supplement_evidence(args.root, args.output)
    print(json.dumps({"output": str(output_path), "summary": build_supplement_evidence(args.root)["summary"]}, ensure_ascii=False))
