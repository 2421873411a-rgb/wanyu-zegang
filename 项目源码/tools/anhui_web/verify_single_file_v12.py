"""Three-layer verifier for the v12 offline single-file workbench.

The verifier reads source inventories, re-parses the delivered HTML, and can
inspect the final ZIP without trusting build-time Python objects.  It reports
known evidence boundaries as warnings/data, while treating drift in totals,
structure, paths, or package layout as a hard failure.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html as html_lib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RELEASE = "v12.1"
MASTER = "皖域择岗总览.html"
CYCLES = ("2024", "2025", "2026")
BASELINE_PATH = ROOT / "tools" / "anhui_web" / "data" / "single_file_baseline_v12.json"
AUDIT_PATH = ROOT / "tools" / "anhui_web" / "data" / "three_year_audit.json"
REPORT_PATH = ROOT / "docs" / "三年单文件数据复核报告_v12.md"
VERIFICATION_PATH = ROOT / "tools" / "anhui_web" / "data" / "single_file_verification_v12.json"
DIFF_PATH = ROOT / "tools" / "anhui_web" / "data" / "single_file_diff_v12.json"
PAYLOAD_RE = re.compile(
    r'<script[^>]*data-cycle-payload=["\'](?P<cycle>\d{4})["\'][^>]*>(?P<body>.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


class VerificationError(ValueError):
    """Raised for a hard verification failure."""


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _check(checks: list[dict[str, Any]], check_id: str, layer: str, expected: Any, actual: Any, message: str, *, warning: bool = False) -> None:
    passed = expected == actual
    checks.append({
        "id": check_id,
        "layer": layer,
        "status": "warn" if warning and not passed else "pass" if passed else "fail",
        "expected": expected,
        "actual": actual,
        "evidence_path": "",
        "message": message,
    })


def _payloads(text: str) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for match in PAYLOAD_RE.finditer(text):
        cycle = match.group("cycle")
        if cycle in found:
            raise VerificationError(f"duplicate embedded payload: {cycle}")
        value = json.loads(html_lib.unescape(match.group("body")))
        if not isinstance(value, dict):
            raise VerificationError(f"payload is not an object: {cycle}")
        found[cycle] = value
    return found


def _expected(root: Path) -> dict[str, Any]:
    baseline = _read_json(root / "tools" / "anhui_web" / "data" / "single_file_baseline_v12.json")
    cycles = baseline.get("cycles") or {}
    if set(cycles) != set(CYCLES):
        raise VerificationError("frozen baseline does not contain exactly 2024/2025/2026")
    return baseline


def _verify_cycle_payloads(payloads: dict[str, dict[str, Any]], baseline: dict[str, Any], checks: list[dict[str, Any]], evidence_path: str) -> None:
    _check(checks, "html.payload_count", "html", 3, len(payloads), "HTML contains exactly three cycle payloads")
    for cycle in CYCLES:
        payload = payloads.get(cycle)
        expected = baseline["cycles"][cycle]
        if payload is None:
            checks.append({"id": f"payload.{cycle}.present", "layer": "html", "status": "fail", "expected": True, "actual": False, "evidence_path": evidence_path, "message": "cycle payload missing"})
            continue
        all_majors = payload.get("allMajors") or {}
        rows = all_majors.get("rows") if isinstance(all_majors, dict) else None
        rows = rows if isinstance(rows, list) else []
        meta = all_majors.get("meta") if isinstance(all_majors, dict) else {}
        meta = meta if isinstance(meta, dict) else {}
        posts = len(rows)
        recruits = sum(int(row.get("num") or 0) for row in rows if isinstance(row, dict))
        exam_counts: dict[str, dict[str, int]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            exam = str(row.get("exam") or "")
            item = exam_counts.setdefault(exam, {"posts": 0, "recruits": 0})
            item["posts"] += 1
            item["recruits"] += int(row.get("num") or 0)
        _check(checks, f"payload.{cycle}.posts", "payload", expected["posts"], posts, f"{cycle} allMajors row count")
        _check(checks, f"payload.{cycle}.recruits", "payload", expected["recruits"], recruits, f"{cycle} allMajors recruit sum")
        _check(checks, f"payload.{cycle}.meta", "payload", {"total": expected["posts"], "recruits": expected["recruits"]}, {"total": meta.get("total"), "recruits": meta.get("recruits")}, f"{cycle} meta matches rows")
        _check(checks, f"payload.{cycle}.exams", "payload", expected["exam_types"], {key: exam_counts.get(key, {"posts": 0, "recruits": 0}) for key in ("省考", "事业编", "国考")}, f"{cycle} exam breakdown")
        row_ids = [row.get("row_id") for row in rows if isinstance(row, dict)]
        _check(checks, f"payload.{cycle}.row_ids", "payload", posts, len(row_ids) if len(row_ids) == len(set(row_ids)) else -1, f"{cycle} technical row IDs are unique")
        mandatory_missing = {field: sum(1 for row in rows if not isinstance(row, dict) or row.get(field) in (None, "")) for field in ("code", "city", "unit", "num", "exam")}
        _check(checks, f"payload.{cycle}.mandatory", "payload", {field: 0 for field in mandatory_missing}, mandatory_missing, f"{cycle} mandatory fields are present")
        quality_rows = [row for row in rows if isinstance(row, dict)]
        job_ids = [str(row.get("job_id") or "") for row in quality_rows]
        job_id_valid = all(value.startswith(f"job-{cycle}-") for value in job_ids)
        _check(checks, f"payload.{cycle}.job_ids", "quality", posts, len(job_ids) if job_id_valid and len(job_ids) == len(set(job_ids)) else -1, f"{cycle} stable job IDs are present and unique")
        allowed_score_statuses = {"comparable", "unavailable", "suspected_sentinel", "incompatible_scale", "not_applicable"}
        invalid_score = sum(
            1
            for row in quality_rows
            if not isinstance(row.get("score_observation"), dict)
            or row["score_observation"].get("status") not in allowed_score_statuses
            or (row["score_observation"].get("status") == "comparable" and (row["score_observation"].get("value") in (None, 0) or not row["score_observation"].get("scale_id")))
        )
        _check(checks, f"payload.{cycle}.score_annotations", "quality", 0, invalid_score, f"{cycle} score observations have an explicit evidence state")
        allowed_competition_types = {None, "examinees", "registrations", "interview_shortlisted"}
        invalid_competition = sum(
            1
            for row in quality_rows
            if not isinstance(row.get("competition_observations"), dict)
            or not all(key in row["competition_observations"] for key in ("registrations", "examinees", "preferred_type"))
            or row["competition_observations"].get("preferred_type") not in allowed_competition_types
            or row.get("competition_metric_type") not in allowed_competition_types
            or row.get("competition_metric_type") != row["competition_observations"].get("preferred_type")
        )
        _check(checks, f"payload.{cycle}.competition_annotations", "quality", 0, invalid_competition, f"{cycle} competition denominators remain separated")
        allowed_title_statuses = {"published", "not_separately_published"}
        invalid_title = sum(
            1
            for row in quality_rows
            if row.get("title_status") not in allowed_title_statuses or not str(row.get("display_title") or "").strip()
        )
        _check(checks, f"payload.{cycle}.title_annotations", "quality", 0, invalid_title, f"{cycle} position-title disclosure state is explicit")
        job_cities = ((payload.get("jobs") or {}).get("cities") if isinstance(payload.get("jobs"), dict) else [])
        invalid_job_rollup = sum(
            1
            for item in (job_cities if isinstance(job_cities, list) else [])
            if not isinstance(item, dict)
            or item.get("ratio_status") not in {"single_denominator", "mixed_denominators", "partial_coverage", "unavailable"}
            or not isinstance(item.get("ratio_comparable"), bool)
        )
        _check(checks, f"payload.{cycle}.job_rollups", "quality", 0, invalid_job_rollup, f"{cycle} job rollups expose comparability state")
        audit = payload.get("threeYearAudit") or {}
        audit_cycle = next((item for item in audit.get("cycles", []) if str(item.get("cycle")) == cycle), {}) if isinstance(audit, dict) else {}
        _check(checks, f"payload.{cycle}.evidence_level", "truth", True, audit_cycle.get("evidence_level") in {"verified_source_archive", "verified_structured_evidence", "partial_evidence", "source_not_published", "ambiguous_unlinked", "user_flagged_review"}, f"{cycle} declares an allowed evidence level")
        _check(checks, f"payload.{cycle}.known_gaps", "truth", True, isinstance(audit_cycle.get("known_gaps"), list), f"{cycle} exposes known gaps")
        _check(checks, f"payload.{cycle}.verified_scope", "truth", True, isinstance(audit_cycle.get("verified_scope"), list), f"{cycle} exposes verified scope")
        _check(checks, f"payload.{cycle}.unverified_scope", "truth", True, isinstance(audit_cycle.get("unverified_scope"), list), f"{cycle} exposes unverified scope")


def _verify_html(root: Path, html_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not html_path.is_file():
        raise VerificationError(f"HTML not found: {html_path}")
    text = html_path.read_text(encoding="utf-8")
    baseline = _expected(root)
    checks: list[dict[str, Any]] = []
    _check(checks, "html.release", "html", RELEASE, re.search(r'data-release=["\']([^"\']+)', text, re.I).group(1) if re.search(r'data-release=["\']([^"\']+)', text, re.I) else None, "release marker")
    _check(checks, "html.shell_count", "html", 1, text.count('id="app-shell"'), "one application shell")
    _check(checks, "html.size_bytes", "html", True, html_path.stat().st_size < 80 * 1024 * 1024, "HTML stays below hard 80 MiB limit")
    _check(checks, "html.external_assets", "html", 0, len(re.findall(r'(?:src|href)=["\']https?://', text, re.I)), "no remote script, stylesheet, image, or font")
    _check(checks, "html.absolute_user_paths", "html", 0, len(re.findall(r'(?:[A-Za-z]:\\Users\\|/Users/|/home/)', text, re.I)), "no absolute user path in delivered HTML")
    payloads = _payloads(text)
    _verify_cycle_payloads(payloads, baseline, checks, str(html_path.relative_to(root)))
    report = {"release": RELEASE, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "html": str(html_path.relative_to(root)), "checks": checks, "payloads": payloads}
    return report, checks


def _verify_inventory(root: Path, checks: list[dict[str, Any]]) -> None:
    baseline = _expected(root)
    for entry in baseline.get("input_files", []):
        relative = Path(str(entry.get("path", "")))
        path = root / relative
        present = path.is_file()
        _check(checks, f"inventory.{relative.as_posix()}", "inventory", True, present, "input file exists")
        if not present:
            continue
        _check(checks, f"inventory.{relative.as_posix()}.bytes", "inventory", int(entry.get("bytes", -1)), path.stat().st_size, "input byte count remains frozen")
        _check(checks, f"inventory.{relative.as_posix()}.sha256", "inventory", str(entry.get("sha256", "")), _sha256(path), "input SHA-256 remains frozen")


def _write_outputs(root: Path, report: dict[str, Any], phase: str, diff: dict[str, Any]) -> None:
    verification_path = root / "tools" / "anhui_web" / "data" / "single_file_verification_v12.json"
    previous = _read_json(verification_path) if verification_path.is_file() else {"release": RELEASE, "phases": {}}
    previous["release"] = RELEASE
    previous["generated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    previous.setdefault("phases", {})[phase] = {key: value for key, value in report.items() if key != "payloads"}
    previous["checks"] = [item for phase_report in previous["phases"].values() for item in phase_report.get("checks", [])]
    previous["known_gaps"] = sorted({gap.get("title") for cycle in (_read_json(root / "tools" / "anhui_web" / "data" / "three_year_audit.json").get("cycles") or []) for gap in (cycle.get("gaps") or []) if gap.get("title")})
    previous["status"] = "fail" if any(item.get("status") == "fail" for item in previous["checks"]) else "pass"
    verification_path.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "tools" / "anhui_web" / "data" / "single_file_diff_v12.json").write_text(json.dumps(diff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _report_markdown(root: Path, report: dict[str, Any]) -> str:
    checks = report.get("checks", [])
    passed = sum(item.get("status") == "pass" for item in checks)
    failed = sum(item.get("status") == "fail" for item in checks)
    warned = sum(item.get("status") == "warn" for item in checks)
    lines = [
        "# 三年单文件数据复核报告 v12",
        "",
        f"> 生成时间：{report.get('generated_at')}。本报告从源清单和最终 HTML 重新计算，不把旧报告当作当前事实。",
        "",
        f"**当前阶段：** `{report.get('phase', 'postbuild')}`；通过 {passed} 项，警告 {warned} 项，失败 {failed} 项。",
        "",
        "## 1. 输入盘点",
        "",
        "基线文件固定相对路径、字节数和 SHA-256；不记录本机用户名或绝对目录。",
        "",
        "## 2. 冻结基线与逐年逐考试总量",
        "",
        "| 周期 | 岗位 | 招录 | 省考 | 事业编 | 国考 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    baseline = _expected(root)
    for cycle in CYCLES:
        item = baseline["cycles"][cycle]
        exams = item["exam_types"]
        lines.append(f"| {cycle} | {item['posts']:,} | {item['recruits']:,} | {exams['省考']['posts']:,}/{exams['省考']['recruits']:,} | {exams['事业编']['posts']:,}/{exams['事业编']['recruits']:,} | {exams['国考']['posts']:,}/{exams['国考']['recruits']:,} |")
    lines += [
        "",
        "## 3. 结构检查与 HTML 反解析",
        "",
        "| 检查层 | 通过 | 警告 | 失败 |",
        "|---|---:|---:|---:|",
        f"| 当前阶段 | {passed} | {warned} | {failed} |",
        "",
        "## 4. 成绩关联",
        "",
    ]
    audit = _read_json(root / "tools" / "anhui_web" / "data" / "three_year_audit.json")
    for item in audit.get("cycles", []):
        coverage = item.get("coverage", {})
        score_by_key = coverage.get("score_by_key")
        score_unresolved = coverage.get("score_unresolved")
        score_by_key_text = f"{score_by_key:,}" if isinstance(score_by_key, int) else str(score_by_key or "—")
        score_unresolved_text = f"{score_unresolved:,}" if isinstance(score_unresolved, int) else str(score_unresolved or "—")
        lines.append(f"- {item.get('cycle')}：安全关联 {score_by_key_text}；无法唯一匹配 {score_unresolved_text}。")
    lines += [
        "",
        "## 5. 已知缺口与证据边界",
        "",
        "完整性在本交付中定义为：已收集源包的结构与聚合完整；不能扩大为所有官方逐项原文都已发布或已取得。待遇数据只代表 2026 快照。",
        "",
    ]
    for item in audit.get("cycles", []):
        lines.append(f"### {item.get('cycle')}（证据层：`{item.get('evidence_level', '—')}`）")
        lines.append("")
        lines.append("已核验范围：" + "；".join(item.get("verified_scope") or ["—"]) + "。")
        lines.append("")
        lines.append("未核验范围：" + "；".join(item.get("unverified_scope") or ["—"]) + "。")
        lines.append("")
    lines += [
        "## 6. 浏览器复核、性能与离线",
        "",
        "浏览器冒烟和截图应以 `tests/browser_smoke_v12.js` 的最新输出为准；首屏采用周期懒解析和 120 行分页渲染，避免把全量岗位一次性写入 DOM。",
        "",
        "## 7. ZIP 复核",
        "",
        "最终 ZIP 由 `release.py --zip` 生成后，再用 `verify_single_file_v12.py package --zip ...` 检查唯一正式 HTML、归档路径、绝对路径和内嵌载荷。",
        "",
        "## 8. 结论与不能声明的事项",
        "",
        "可声明：最终单文件包含三个周期的全量岗位载荷，结构字段与冻结基线在机器检查范围内一致，缺口公开保留。",
        "",
        "不能声明：所有官方材料均已发布、所有字段均有逐岗官方原文、或数据达到 100% 无缺失。",
        "",
    ]
    return "\n".join(lines)


def verify_prebuild(root: Path = ROOT) -> dict[str, Any]:
    try:
        from .unified_cycle_bundle import build_unified_bundles
    except ImportError:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from tools.anhui_web.unified_cycle_bundle import build_unified_bundles

    root = Path(root).resolve()
    checks: list[dict[str, Any]] = []
    _verify_inventory(root, checks)
    bundles = build_unified_bundles(root)
    _check(checks, "bundle.cycles", "bundle", list(CYCLES), list(bundles), "all cycle bundles load")
    for cycle, bundle in bundles.items():
        expected = _expected(root)["cycles"][cycle]
        _check(checks, f"bundle.{cycle}.rows", "bundle", expected["posts"], len(bundle.records), "bundle record count")
        _check(checks, f"bundle.{cycle}.recruits", "bundle", expected["recruits"], sum(int(row.get("num") or 0) for row in bundle.records), "bundle recruit sum")
    report = {"release": RELEASE, "phase": "prebuild", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "checks": checks}
    diff = {"release": RELEASE, "unexpected": [item for item in checks if item["status"] == "fail"], "allowed_known_gaps": [], "resolved_since_v11": [], "status": "fail" if any(item["status"] == "fail" for item in checks) else "clean"}
    _write_outputs(root, report, "prebuild", diff)
    return report


def verify_postbuild(root: Path = ROOT, html_path: Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    html_path = Path(html_path or root / "deliverables" / MASTER).resolve()
    report, checks = _verify_html(root, html_path)
    report["phase"] = "postbuild"
    diff = {"release": RELEASE, "unexpected": [item for item in checks if item["status"] == "fail"], "allowed_known_gaps": [], "resolved_since_v11": [], "status": "fail" if any(item["status"] == "fail" for item in checks) else "clean"}
    _write_outputs(root, report, "postbuild", diff)
    (root / "docs" / "三年单文件数据复核报告_v12.md").write_text(_report_markdown(root, report), encoding="utf-8")
    return report


def verify_package(root: Path = ROOT, zip_path: Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    if not zip_path or not zip_path.is_file():
        raise VerificationError(f"ZIP not found: {zip_path}")
    checks: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        primary = f"deliverables/{MASTER}"
        root_html = sorted(name for name in names if re.fullmatch(r"deliverables/[^/]+\.html", name))
        _check(checks, "zip.primary", "zip", True, primary in names, "formal primary HTML is present")
        _check(checks, "zip.root_html_count", "zip", [primary], root_html, "formal deliverables root has one HTML entry")
        _check(checks, "zip.legacy_split_absent", "zip", 0, sum(name in names for name in ("deliverables/2024/皖域择岗总览.html", "deliverables/2025/皖域择岗总览.html", "deliverables/安徽十六市2026软件工程可报岗位.html", "deliverables/安徽全省16市本科普通岗全包分析.html")), "split pages are only retained under legacy_v11")
        unsafe = [name for name in names if "C:\\Users\\" in name or name.startswith("/") or "node_modules" in name or "__pycache__" in name]
        _check(checks, "zip.unsafe_names", "zip", 0, len(unsafe), "zip contains no unsafe path or cache member")
        if primary in names:
            text = archive.read(primary).decode("utf-8")
            payloads = _payloads(text)
            _verify_cycle_payloads(payloads, _expected(root), checks, primary)
    report = {"release": RELEASE, "phase": "package", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "zip": str(zip_path), "checks": checks}
    diff = {"release": RELEASE, "unexpected": [item for item in checks if item["status"] == "fail"], "allowed_known_gaps": [], "resolved_since_v11": [], "status": "fail" if any(item["status"] == "fail" for item in checks) else "clean"}
    _write_outputs(root, report, "package", diff)
    return report


def _finish(report: dict[str, Any]) -> int:
    failed = [item for item in report.get("checks", []) if item.get("status") == "fail"]
    print(f"{report.get('phase', 'verification')}: {len(report.get('checks', [])) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify v12 single-file three-cycle workbench")
    sub = parser.add_subparsers(dest="phase", required=True)
    sub.add_parser("prebuild")
    post = sub.add_parser("postbuild")
    post.add_argument("--html", type=Path, default=ROOT / "deliverables" / MASTER)
    package = sub.add_parser("package")
    package.add_argument("--zip", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.phase == "prebuild":
            return _finish(verify_prebuild(ROOT))
        if args.phase == "postbuild":
            return _finish(verify_postbuild(ROOT, args.html))
        return _finish(verify_package(ROOT, args.zip))
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile, ImportError) as exc:
        print(f"VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
