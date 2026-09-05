from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "tools" / "anhui_web" / "data"
PAGE_DATA_PATTERN = re.compile(
    r'<script\b[^>]*\bid="page-data"[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    evidence: str


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_page(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = PAGE_DATA_PATTERN.search(text)
    if not match:
        raise ValueError(f"page-data missing: {path}")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError(f"page-data is not an object: {path}")
    return payload


def _rows_and_meta(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    all_majors = payload.get("allMajors")
    if not isinstance(all_majors, dict):
        raise ValueError("allMajors is missing")
    rows = all_majors.get("rows")
    meta = all_majors.get("meta")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("allMajors.rows is invalid")
    if not isinstance(meta, dict):
        raise ValueError("allMajors.meta is invalid")
    return rows, meta


def _count_field(rows: list[dict[str, Any]], field: str) -> int:
    return sum(row.get(field) is not None for row in rows)


def _exam_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {exam: sum(row.get("exam") == exam for row in rows) for exam in ("省考", "事业编", "国考")}


def _city_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for row in rows:
        city = str(row.get("city") or "")
        item = result.setdefault(city, {"jobs": 0, "recruits": 0, "exam": {}})
        item["jobs"] += 1
        item["recruits"] += int(row.get("num") or 0)
        exam = str(row.get("exam") or "")
        exam_item = item["exam"].setdefault(exam, {"jobs": 0, "recruits": 0})
        exam_item["jobs"] += 1
        exam_item["recruits"] += int(row.get("num") or 0)
    return result


def _add(checks: list[Check], name: str, condition: bool, evidence: str) -> None:
    checks.append(Check(name, bool(condition), evidence))


def verify() -> list[Check]:
    checks: list[Check] = []
    main_path = ROOT / "deliverables" / "皖域择岗总览.html"
    main_payload = _load_page(main_path)
    main_rows, main_meta = _rows_and_meta(main_payload)
    main_cities = _city_summary(main_rows)

    expected_exam_counts = {"省考": 3784, "事业编": 4176, "国考": 551}
    # v10 composite-key joins intentionally leave ambiguous city-less score
    # attachments unbound; the baseline records the resulting honest
    # coverage rather than silently copying one list to multiple positions.
    expected_coverage = {"bm": 8379, "hg": 8379, "jf": 3784, "adv": 7455, "line": 7381, "top": 6907}
    _add(checks, "主站岗位总数", len(main_rows) == 8511 and main_meta.get("total") == 8511, f"rows={len(main_rows)}, meta.total={main_meta.get('total')}")
    _add(checks, "主站招录人数", sum(int(row.get("num") or 0) for row in main_rows) == 12006 and main_meta.get("recruits") == 12006, f"sum(num)={sum(int(row.get('num') or 0) for row in main_rows)}, meta.recruits={main_meta.get('recruits')}")
    _add(checks, "主站分考试岗位数", main_meta.get("examCounts") == expected_exam_counts and _exam_counts(main_rows) == expected_exam_counts, f"meta={main_meta.get('examCounts')}, rows={_exam_counts(main_rows)}")
    actual_coverage = {key: _count_field(main_rows, key) for key in expected_coverage}
    _add(checks, "主站成绩覆盖率", {key: (main_meta.get("scoreCoverage") or {}).get(key) for key in expected_coverage} == expected_coverage and actual_coverage == expected_coverage, f"meta={ {key: (main_meta.get('scoreCoverage') or {}).get(key) for key in expected_coverage} }, rows={actual_coverage}")
    _add(checks, "主站城市汇总", len(main_cities) == 17 and sum(item["jobs"] for item in main_cities.values()) == 8511 and sum(item["recruits"] for item in main_cities.values()) == 12006, f"cities={len(main_cities)}, jobs={sum(item['jobs'] for item in main_cities.values())}, recruits={sum(item['recruits'] for item in main_cities.values())}")
    per_exam_actual: dict[str, dict[str, int]] = {}
    for exam in expected_exam_counts:
        exam_rows = [row for row in main_rows if row.get("exam") == exam]
        per_exam_actual[exam] = {"total": len(exam_rows), "bm": _count_field(exam_rows, "bm"), "adv": _count_field(exam_rows, "adv"), "line": _count_field(exam_rows, "line")}
    per_exam_expected = (main_meta.get("scoreCoverage") or {}).get("perExam")
    _add(checks, "主站分考试覆盖率", per_exam_expected == per_exam_actual, f"meta={per_exam_expected}, rows={per_exam_actual}")

    all_majors = _load_json(DATA / "all_majors_2026.json")
    all_majors_rows = all_majors["positions"]
    source_city_counts = {str(city): int(count) for city, count in all_majors["city_counts"].items()}
    page_provincial_cities = {city: item["exam"].get("省考", {}).get("jobs", 0) for city, item in main_cities.items()}
    _add(checks, "省考源库到页面", all_majors.get("total") == 3784 and len(all_majors_rows) == 3784 and page_provincial_cities == source_city_counts, f"source.total={all_majors.get('total')}, rows={len(all_majors_rows)}, city_diff={sorted(set(page_provincial_cities) ^ set(source_city_counts))}")

    guokao = _load_json(DATA / "guokao2026.json")
    guokao_rows = guokao["positions"]
    page_gk_rows = [row for row in main_rows if row.get("exam") == "国考"]
    _add(checks, "国考源库到页面", guokao.get("total") == 551 and len(guokao_rows) == 551 and len(page_gk_rows) == 551 and sum(int(row.get("num") or 0) for row in page_gk_rows) == sum(int(row.get("num") or 0) for row in guokao_rows), f"source={guokao.get('total')}, page={len(page_gk_rows)}, recruits source/page={sum(int(row.get('num') or 0) for row in guokao_rows)}/{sum(int(row.get('num') or 0) for row in page_gk_rows)}")

    huatu = _load_json(DATA / "huatu_syb_2026.json")
    syb_rows = [row for row in main_rows if row.get("exam") == "事业编"]
    _add(checks, "事业编职位表增量口径", huatu.get("total") == 4122 and len(huatu["positions"]) == 4122 and len(syb_rows) == 4176 and len(syb_rows) - huatu.get("total", 0) == 54, f"huatu={huatu.get('total')}, page={len(syb_rows)}, page_minus_huatu={len(syb_rows) - huatu.get('total', 0)}")

    scores = _load_json(DATA / "syb2026_daxian_all.json")
    score_rows = scores["positions"]
    score_by_code = {str(row.get("code")): row for row in score_rows}
    score_source = (scores.get("source") or "")
    _add(checks, "事业编成绩库总量", scores.get("total") == 3385 and len(score_rows) == 3385 and sum(int(row.get("adv") or 0) for row in score_rows) == 221259, f"total={scores.get('total')}, rows={len(score_rows)}, sum_adv={sum(int(row.get('adv') or 0) for row in score_rows)}")
    _add(checks, "成绩库审计链", _load_json(DATA / "manifest.json").get("syb_score_harvest", {}).get("audit_chain") == 15 and len(score_source) > 0, f"manifest.audit_chain={_load_json(DATA / 'manifest.json').get('syb_score_harvest', {}).get('audit_chain')}, source_length={len(score_source)}")
    sample_202606001 = score_by_code.get("202606001", {})
    sample_3010006 = score_by_code.get("3010006", {})
    _add(checks, "成绩库抽样断言", (sample_202606001.get("adv"), sample_202606001.get("top"), sample_202606001.get("line")) == (3, 239.6, 227.8) and (sample_3010006.get("adv"), sample_3010006.get("top"), sample_3010006.get("line")) == (None, None, 202.5), f"202606001={sample_202606001}, 3010006={sample_3010006}")

    eligibility = _load_json(DATA / "position_eligibility.json")
    exclusions = _load_json(DATA / "job_eligibility_exclusions.json")
    dedup = _load_json(DATA / "_dedup_2602_dongzhi.json")
    fuzzy = _load_json(DATA / "_dedup_fuzzy_pairs.json")
    _add(checks, "资格与核除审计件", len(eligibility.get("positions", [])) == 544 and len(exclusions.get("exclusions", [])) == 44 and len(dedup.get("removed_rows", [])) == 60 and len(fuzzy) == 109, f"eligibility={len(eligibility.get('positions', []))}, exclusions={len(exclusions.get('exclusions', []))}, dongzhi_removed={len(dedup.get('removed_rows', []))}, fuzzy_pairs={len(fuzzy)}")

    manifest = _load_json(DATA / "manifest.json")
    open_items = manifest.get("open_items", [])
    _add(checks, "open_items 已登记", len(open_items) == 2 and all(item.get("status") == "open" for item in open_items), f"items={len(open_items)}, statuses={[item.get('status') for item in open_items]}")

    for year, expected_posts, expected_recruits in (("2025", 10150, 14721), ("2024", 10017, 15331)):
        page_path = ROOT / "deliverables" / year / "皖域择岗总览.html"
        cycle_payload = _load_page(page_path)
        cycle_rows, cycle_meta = _rows_and_meta(cycle_payload)
        cycle_info = cycle_payload.get("cycleInfo") or {}
        page_stats = cycle_info.get("stats") or {}
        cycle_bundle = _load_json(DATA / "cycles" / year / "cycle.json")
        bundle_stats = cycle_bundle.get("stats") or {}
        _add(checks, f"{year} 周期岗位页与 cycle.json", page_stats == bundle_stats and page_stats.get("total_posts") == expected_posts and page_stats.get("total_recruits") == expected_recruits and len(cycle_rows) == expected_posts and cycle_meta.get("total") == expected_posts, f"page_rows={len(cycle_rows)}, page_stats={page_stats.get('total_posts')}/{page_stats.get('total_recruits')}, bundle_stats={bundle_stats.get('total_posts')}/{bundle_stats.get('total_recruits')}")

    for page in (main_path, ROOT / "deliverables" / "安徽十六市2026软件工程可报岗位.html", ROOT / "deliverables" / "安徽全省16市本科普通岗全包分析.html", ROOT / "deliverables" / "2025" / "皖域择岗总览.html", ROOT / "deliverables" / "2024" / "皖域择岗总览.html"):
        text = page.read_text(encoding="utf-8")
        has_remote_assets = re.search(r"https?://[^\"']+\.(?:js|css|woff2?)", text, flags=re.IGNORECASE) is not None
        _add(checks, f"离线资源 {page.relative_to(ROOT).as_posix()}", not has_remote_assets, "无远程 js/css/font" if not has_remote_assets else "检测到远程 js/css/font")

    return checks


def _report(checks: list[Check]) -> str:
    passed = sum(check.ok for check in checks)
    lines = [
        "# v10 全站数据核验报告",
        "",
        "> 生成方式：`python tools/anhui_web/verify_full_v10.py --report docs/核验报告_v10.md`。本报告只读取已生成页面和数据文件，不会改写数据。",
        "",
        f"汇总：{passed}/{len(checks)} PASS，{len(checks) - passed} FAIL。",
        "",
        "| # | 核验项 | 结果 | 证据 |\n|---:|---|---|---|",
    ]
    for index, check in enumerate(checks, 1):
        result = "PASS" if check.ok else "FAIL"
        evidence = check.evidence.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {index} | {check.name} | {result} | {evidence} |")
    lines.extend(["", "## 结论", "", "所有检查均通过。" if passed == len(checks) else "存在失败项，不能宣称 v10 数据核验完成。"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="核对 v10 源数据、页面内嵌数据、周期包和审计件。")
    parser.add_argument("--report", type=Path, default=ROOT / "docs" / "核验报告_v10.md", help="Markdown 报告路径")
    args = parser.parse_args(argv)
    try:
        checks = verify()
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"verification failed before checks: {exc}", file=sys.stderr)
        return 1
    report = _report(checks)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    passed = sum(check.ok for check in checks)
    print(f"{passed}/{len(checks)} PASS -> {args.report}")
    if passed != len(checks):
        for check in checks:
            if not check.ok:
                print(f"FAIL: {check.name}: {check.evidence}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
