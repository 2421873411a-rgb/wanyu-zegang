from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "tests" / "expected_baseline.json"
PAGE_DATA_PATTERN = re.compile(
    r'<script\b[^>]*\bid="page-data"[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _read_page_data(page: Path) -> dict[str, Any]:
    text = page.read_text(encoding="utf-8")
    match = PAGE_DATA_PATTERN.search(text)
    if not match:
        raise ValueError(f"page-data script is missing: {page}")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError(f"page-data must be a JSON object: {page}")
    return payload


def _meta_snapshot(meta: dict[str, Any]) -> dict[str, Any]:
    keys = ("total", "recruits", "directed", "hukou", "compJoined", "scoreCoverage", "examCounts")
    return {key: meta.get(key) for key in keys}


def _city_summary(rows: list[dict[str, Any]], city_order: list[str]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        city = str(row.get("city") or "")
        exam = str(row.get("exam") or "")
        recruits = int(row.get("num") or 0)
        city_item = grouped.setdefault(city, {"city": city, "jobs": 0, "recruits": 0, "exam": {}})
        city_item["jobs"] += 1
        city_item["recruits"] += recruits
        exam_item = city_item["exam"].setdefault(exam, {"jobs": 0, "recruits": 0})
        exam_item["jobs"] += 1
        exam_item["recruits"] += recruits

    ordered_names = list(dict.fromkeys(city_order + sorted(set(grouped) - set(city_order))))
    return [grouped[name] for name in ordered_names if name in grouped]


def _page_snapshot(page: Path) -> dict[str, Any]:
    payload = _read_page_data(page)
    all_majors = payload.get("allMajors")
    if not isinstance(all_majors, dict):
        raise ValueError(f"allMajors payload is missing: {page}")
    rows = all_majors.get("rows")
    meta = all_majors.get("meta")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"allMajors.rows is invalid: {page}")
    if not isinstance(meta, dict):
        raise ValueError(f"allMajors.meta is invalid: {page}")

    snapshot: dict[str, Any] = {
        "page": page.relative_to(ROOT).as_posix(),
        "rows": len(rows),
        "meta": _meta_snapshot(meta),
        "cities": _city_summary(rows, [str(city) for city in meta.get("cities", [])]),
    }
    cycle_info = payload.get("cycleInfo")
    if isinstance(cycle_info, dict):
        snapshot["cycleInfo"] = cycle_info
    return snapshot


def build_snapshot() -> dict[str, Any]:
    main_page = ROOT / "deliverables" / "皖域择岗总览.html"
    snapshot: dict[str, Any] = {
        "schema": 1,
        "main": _page_snapshot(main_page),
        "cycles": {},
    }
    for year in ("2025", "2024"):
        page = ROOT / "deliverables" / year / "皖域择岗总览.html"
        page_snapshot = _page_snapshot(page)
        cycle_info = page_snapshot.get("cycleInfo")
        if not isinstance(cycle_info, dict) or not isinstance(cycle_info.get("stats"), dict):
            raise ValueError(f"cycleInfo.stats is missing: {page}")
        snapshot["cycles"][year] = {
            "page": page_snapshot["page"],
            "rows": page_snapshot["rows"],
            "meta": page_snapshot["meta"],
            "stats": cycle_info["stats"],
            "cities": page_snapshot["cities"],
        }
    return snapshot


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从交付 HTML 固化或核对 v10 数据基线。")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="基线 JSON 路径")
    parser.add_argument("--check", action="store_true", help="与现有基线比较，不改写文件")
    args = parser.parse_args(argv)

    try:
        actual_text = _canonical_json(build_snapshot())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"baseline extraction failed: {exc}", file=sys.stderr)
        return 1

    if args.check:
        try:
            expected_text = args.output.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"baseline read failed: {exc}", file=sys.stderr)
            return 1
        if actual_text != expected_text:
            diff = difflib.unified_diff(
                expected_text.splitlines(),
                actual_text.splitlines(),
                fromfile=str(args.output),
                tofile="current HTML snapshot",
                lineterm="",
            )
            print("baseline mismatch")
            print("\n".join(diff))
            return 1
        print(f"baseline OK: {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(actual_text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
