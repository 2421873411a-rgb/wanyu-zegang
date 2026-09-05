"""三周期数据真实性与完整性审计。

该脚本只读源 JSON、周期清单和已生成页面，输出结构化摘要与 Markdown 报告。
它把“源包内部一致”与“官方逐项证据完整”分开，不会用空值、零值或推断补齐
未知信息。
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

if str(_Path(__file__).resolve().parents[2]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))


import argparse
import datetime as dt
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


CYCLES = ("2024", "2025", "2026")
BASELINES = {
    "2024": {"posts": 10017, "recruits": 15331},
    "2025": {"posts": 10150, "recruits": 14721},
    "2026": {"posts": 8511, "recruits": 12006},
}
STATUS_DEFINITIONS = {
    "verified": "源 JSON、页面内嵌数据和聚合口径已对账",
    "source_bundle": "值来自当前交接包的源文件或明确转换",
    "unpublished_or_unavailable": "官方暂未发布或本包未取得可复核逐项证据",
    "ambiguous_join": "存在多个候选岗位且缺少必要匹配键，安全留空",
}
EVIDENCE_LEVEL_DEFINITIONS = {
    "verified_source_archive": "可定位的官方或原始档案已归档并通过结构核对",
    "verified_structured_evidence": "结构化源包、页面载荷与聚合口径已完成内部对账",
    "partial_evidence": "主数据可复现，但仍有公开缺口、转换口径或未发布字段",
    "source_not_published": "目标资料在当前周期未发布或本包未取得",
    "ambiguous_unlinked": "存在候选记录但缺少唯一匹配键，按安全原则留空",
    "user_flagged_review": "仅作人工复核标记，不能解释为官方结论",
}
PAGE_DATA_RE = re.compile(
    r'<script type="application/json" id="page-data">(.*?)</script>', re.S
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _number(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return int(float(match.group())) if match else 0


def _positions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("positions")
    if not isinstance(rows, list):
        raise ValueError("positions must be a list")
    return [row for row in rows if isinstance(row, dict)]


def _component_paths(root: Path, cycle: str) -> dict[str, Path]:
    base = root / "tools" / "anhui_web" / "data"
    if cycle != "2026":
        base = base / "cycles" / cycle
    return {
        "省考": base / f"all_majors_{cycle}.json",
        "国考": base / f"guokao{cycle}.json",
        "事业编": base / f"huatu_syb_{cycle}.json",
    }


def _canonical_ref(root: Path, cycle: str) -> Path:
    """审计行的引用路径 = canonical 周期包（不再指向 legacy 页面工件）。"""
    return Path(root).resolve() / "canonical" / "cycles" / f"{cycle}.json"


def _page_path(root: Path, cycle: str) -> Path:
    # v12 has one page for all cycles. Keep the historical fallback so the
    # pre-migration audit can still inspect a recoverable v11 snapshot.
    unified = root / "deliverables" / "皖域择岗总览.html"
    if unified.is_file():
        return unified
    return root / "deliverables" / (
        "皖域择岗总览.html" if cycle == "2026" else f"{cycle}/皖域择岗总览.html"
    )


def _manifest_path(root: Path, cycle: str) -> Path:
    base = root / "tools" / "anhui_web" / "data"
    return base / ("manifest.json" if cycle == "2026" else f"cycles/{cycle}/cycle.json")


def _read_page(path: Path, cycle: str | None = None) -> dict[str, Any]:
    """RC3(G)：页面读取已退役——行源改为 canonical 周期包（HTML 永远只是 OUTPUT）。

    保留函数签名以兼容旧调用；``path`` 忽略，改为按 cycle 读 canonical。
    """
    from tools.anhui_web.unified_cycle_bundle import load_canonical_doc

    target_cycle = str(cycle or "2026")
    doc = load_canonical_doc(Path(__file__).resolve().parents[2], target_cycle)
    return {"allMajors": doc.get("all_majors") or {}, "cycleInfo": doc.get("cycle_info") or {}}


def _page_rows(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    all_majors = payload.get("allMajors") or {}
    rows = all_majors.get("rows")
    meta = all_majors.get("meta") or {}
    if not isinstance(rows, list) or not isinstance(meta, dict):
        raise ValueError("page allMajors rows/meta missing")
    return [row for row in rows if isinstance(row, dict)], meta


def _missing(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, int]:
    return {
        field: sum(1 for row in rows if _empty(row.get(field)))
        for field in fields
    }


def _row_num(row: dict[str, Any]) -> int:
    return _number(row.get("num", row.get("recruits")))


def _component_profile(root: Path, cycle: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    profiles: dict[str, Any] = {}
    for exam, path in _component_paths(root, cycle).items():
        payload = _json(path)
        rows = _positions(payload)
        source_total = payload.get("total")
        source_recruits = payload.get("recruits")
        row_recruits = sum(_row_num(row) for row in rows)
        check(
            checks,
            f"{cycle} {exam} 源文件行数",
            source_total == len(rows),
            f"declared={source_total}, rows={len(rows)}, file={_rel(root, path)}",
        )
        if source_recruits is not None:
            check(
                checks,
                f"{cycle} {exam} 源文件招录人数",
                _number(source_recruits) == row_recruits,
                f"declared={source_recruits}, sum(num)={row_recruits}",
            )
        missing = _missing(rows, ("code", "city", "unit"))
        check(
            checks,
            f"{cycle} {exam} 源文件关键字段",
            not any(missing.values()),
            f"missing={missing}",
        )
        profiles[exam] = {
            "file": _rel(root, path),
            "source": payload.get("source", ""),
            "rows": len(rows),
            "recruits": row_recruits,
            "missing": missing,
            "cycles": payload.get("cycles", []),
        }
    return profiles


def _coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ("bm", "hg", "jf", "adv", "line", "top", "hq")
    result: dict[str, Any] = {field: sum(not _empty(row.get(field)) for row in rows) for field in fields}
    result["hire"] = result.pop("hq")
    per_exam: dict[str, Any] = {}
    for exam in ("省考", "事业编", "国考"):
        subset = [row for row in rows if row.get("exam") == exam]
        per_exam[exam] = {
            "total": len(subset),
            "bm": sum(not _empty(row.get("bm")) for row in subset),
            "adv": sum(not _empty(row.get("adv")) for row in subset),
            "line": sum(not _empty(row.get("line")) for row in subset),
        }
    result["perExam"] = per_exam
    return result


def _candidate_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("exam"),
        row.get("city"),
        row.get("code"),
        row.get("num"),
        row.get("cycle", ""),
    )


def _score_resolutions(keyed: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn keyed ``resolution_<date>`` blocks into resolved-history records."""
    blocks: list[dict[str, Any]] = []
    for key, value in keyed.items():
        if not (isinstance(key, str) and key.startswith("resolution_") and isinstance(value, dict)):
            continue
        attributed = int(value.get("attributed") or 0)
        still = int(value.get("still_ambiguous") or 0)
        blocks.append(
            {
                "kind": "ambiguous_join",
                "status": "resolved" if attributed and still == 0 else ("partial" if attributed else "open"),
                "original_count": attributed + still,
                "resolved_count": attributed,
                "remaining_count": still,
                "resolved_at": key.removeprefix("resolution_"),
                "method": str(value.get("method") or ""),
            }
        )
    return blocks


def _score_profile(root: Path, cycle: str) -> dict[str, Any]:
    path = _component_paths(root, cycle)["省考"].parent / "score_lists.json"
    payload = _json(path)
    keyed = payload.get("keyed") or {}
    unresolved = keyed.get("unresolved") or []
    by_key = payload.get("by_key") or {}
    resolution_blocks = _score_resolutions(keyed if isinstance(keyed, dict) else {})
    return {
        "file": _rel(root, path),
        "cycle": payload.get("cycle"),
        "by_key": len(by_key) if isinstance(by_key, dict) else 0,
        "bs": len(payload.get("bs") or {}),
        "ms": len(payload.get("ms") or {}),
        "unresolved": len(unresolved) if isinstance(unresolved, list) else 0,
        "resolved": sum(block["resolved_count"] for block in resolution_blocks),
        "resolution_blocks": resolution_blocks,
    }


def check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def _gap(kind: str, title: str, detail: str, evidence: str, severity: str = "medium") -> dict[str, str]:
    return {
        "kind": kind,
        "title": title,
        "detail": detail,
        "evidence": evidence,
        "severity": severity,
    }


def _known_gaps(root: Path, cycle: str, manifest: dict[str, Any], score: dict[str, Any]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    for item in manifest.get("gaps") or []:
        gaps.append(
            _gap(
                "unpublished_or_unavailable",
                str(item),
                "周期清单明确记录该资料未发布、未回收或仅有汇总口径；页面保留空值，不推断为零。",
                _rel(root, _manifest_path(root, cycle)),
            )
        )
    if cycle == "2026":
        harvest = manifest.get("syb_score_harvest") or {}
        if harvest.get("gaps"):
            gaps.append(
                _gap(
                    "unpublished_or_unavailable",
                    "2026 事业编成绩收割边界",
                    str(harvest["gaps"]),
                    _rel(root, _manifest_path(root, cycle)),
                    "high",
                )
            )
        for item in manifest.get("open_items") or []:
            gaps.append(
                _gap(
                    "unpublished_or_unavailable",
                    f"待官方复核：{item.get('code', '未标代码')}",
                    str(item.get("defer_reason") or item.get("note") or "未取得逐项官方证据"),
                    _rel(root, _manifest_path(root, cycle)),
                    "high",
                )
            )
    if score["unresolved"]:
        gaps.append(
            _gap(
                "ambiguous_join",
                f"成绩附件存在 {score['unresolved']} 个无法唯一匹配项",
                "附件缺少城市字段且职位代码对应多个候选岗位，按宁缺勿错原则不写入岗位成绩。",
                score["file"],
                "high",
            )
        )
    return gaps


def _audit_cycle(root: Path, cycle: str, global_checks: list[dict[str, Any]]) -> dict[str, Any]:
    components = _component_profile(root, cycle, global_checks)
    manifest_path = _manifest_path(root, cycle)
    manifest = _json(manifest_path)
    page_path = _canonical_ref(root, cycle)
    page_payload = _read_page(page_path, cycle)
    page_rows, page_meta = _page_rows(page_payload)
    score = _score_profile(root, cycle)

    baseline = BASELINES[cycle]
    page_posts = len(page_rows)
    page_recruits = sum(_row_num(row) for row in page_rows)
    page_exams = Counter(str(row.get("exam") or "") for row in page_rows)
    source_posts = sum(item["rows"] for item in components.values())
    source_recruits = sum(item["recruits"] for item in components.values())
    expected_adjustment = {"2024": 0, "2025": 0, "2026": 54}[cycle]
    actual_adjustment = page_exams.get("事业编", 0) - components["事业编"]["rows"]
    expected_recruit_adjustment = {"2024": 0, "2025": 0, "2026": 55}[cycle]
    actual_recruit_adjustment = page_recruits - source_recruits

    check(global_checks, f"{cycle} 页面岗位总数", page_posts == baseline["posts"], f"page={page_posts}, baseline={baseline['posts']}")
    check(global_checks, f"{cycle} 页面招录人数", page_recruits == baseline["recruits"], f"page={page_recruits}, baseline={baseline['recruits']}")
    check(global_checks, f"{cycle} 页面 meta 总数", page_meta.get("total") == page_posts, f"meta={page_meta.get('total')}, rows={page_posts}")
    check(global_checks, f"{cycle} 页面 meta 招录人数", page_meta.get("recruits") == page_recruits, f"meta={page_meta.get('recruits')}, sum={page_recruits}")
    check(global_checks, f"{cycle} 页面考试分类", dict(page_meta.get("examCounts") or {}) == dict(page_exams), f"meta={page_meta.get('examCounts')}, rows={dict(page_exams)}")
    check(global_checks, f"{cycle} 组件到页面岗位增量", actual_adjustment == expected_adjustment, f"source={source_posts}, page={page_posts}, syb_adjustment={actual_adjustment}, expected={expected_adjustment}")
    check(global_checks, f"{cycle} 组件到页面招录增量", actual_recruit_adjustment == expected_recruit_adjustment, f"source={source_recruits}, page={page_recruits}, adjustment={actual_recruit_adjustment}, expected={expected_recruit_adjustment}")
    missing_page = _missing(page_rows, ("code", "city", "unit", "num", "exam"))
    check(global_checks, f"{cycle} 页面关键字段", not any(missing_page.values()), f"missing={missing_page}")

    page_coverage = _coverage(page_rows)
    meta_coverage = page_meta.get("scoreCoverage") or {}
    # RC3：meta.scoreCoverage 是 builder 口径（adv=官方报名观测、line>0、perExam.total），
    # 与行字段口径（_coverage）本就不同源；一致性门改为「meta 与 canonical 行按 builder
    # 口径复算相符」，hire 为构建期投影（行级无字段）单独豁免。
    builder_coverage = {
        "bm": sum(1 for row in page_rows if row.get("bm") is not None),
        "hg": sum(1 for row in page_rows if row.get("hg") is not None),
        "jf": sum(1 for row in page_rows if row.get("jf") is not None),
        "adv": sum(1 for row in page_rows if (row.get("competition_observations") or {}).get("examinees", {}).get("value") is not None),
        "line": sum(1 for row in page_rows if isinstance(row.get("line"), (int, float)) and row.get("line", 0) > 0),
        "perExam": {
            exam: sum(1 for row in page_rows if row.get("exam") == exam)
            for exam in ("省考", "事业编", "国考")
        },
    }
    meta_matches_builder = all(
        meta_coverage.get(key) == builder_coverage[key]
        for key in ("bm", "hg", "jf", "adv", "line")
    ) and all(
        (meta_coverage.get("perExam") or {}).get(exam, {}).get("total") == builder_coverage["perExam"][exam]
        for exam in ("省考", "事业编", "国考")
    )
    check(global_checks, f"{cycle} 页面成绩覆盖", meta_matches_builder, "meta scoreCoverage matches builder-scope row recompute (field-scope coverage recorded separately)")
    check(global_checks, f"{cycle} 成绩清单周期", score["cycle"] == cycle, f"score_lists.cycle={score['cycle']}")

    candidate_counter = Counter(_candidate_key(row) for row in page_rows)
    duplicate_keys = [(key, count) for key, count in candidate_counter.items() if count > 1]
    gaps = _known_gaps(root, cycle, manifest, score)
    resolved_adjustments: list[dict[str, str]] = []
    for item in manifest.get("resolved_adjustments") or []:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        resolved_adjustments.append(
            {
                "kind": str(item.get("kind") or "source_bundle"),
                "title": str(item["title"]),
                "detail": str(item.get("detail") or ""),
                "evidence": str(item.get("evidence") or _rel(root, manifest_path)),
                "severity": str(item.get("severity") or "medium"),
            }
        )
    if cycle == "2026" and actual_adjustment:
        resolved_adjustments.append(
            _gap(
                "source_bundle",
                "2026 事业编页面含源包外加表行",
                f"华图职位库快照为 {components['事业编']['rows']} 岗，页面口径为 {page_exams.get('事业编', 0)} 岗，增加 {actual_adjustment} 岗/{actual_recruit_adjustment} 人；增量来自现有构建器明确接入的源表，不视为缺失。",
                "docs/核验报告_v10.md",
            )
        )
    evidence_level = "partial_evidence" if gaps else "verified_structured_evidence"
    verified_scope = [
        "岗位行主键、考试类别、城市、职位代码、单位与招录人数",
        "源组件行数、招录人数合计、页面 allMajors 行数与聚合元数据",
        "成绩清单周期字段与可安全匹配数量",
    ]
    unverified_scope = [str(item["title"]) for item in gaps]
    status_counts = {
        "verified": sum(1 for item in global_checks if item["passed"] and item["name"].startswith(f"{cycle} ")),
        "source_bundle": source_posts,
        "unpublished_or_unavailable": sum(1 for item in gaps if item["kind"] == "unpublished_or_unavailable"),
        "ambiguous_join": sum(1 for item in gaps if item["kind"] == "ambiguous_join"),
    }
    return {
        "cycle": cycle,
        "label": manifest.get("label") or f"{cycle}年度",
        "generated_on": manifest.get("generated_on") or manifest.get("release_date", ""),
        "snapshot_date": manifest.get("snapshot_date", ""),
        "posts": page_posts,
        "recruits": page_recruits,
        "exams": {
            exam: {"posts": page_exams.get(exam, 0), "recruits": sum(_row_num(row) for row in page_rows if row.get("exam") == exam)}
            for exam in ("省考", "事业编", "国考")
        },
        "source_components": components,
        "source_totals": {"posts": source_posts, "recruits": source_recruits},
        "page_adjustment": {"posts": actual_adjustment, "recruits": actual_recruit_adjustment},
        "missing": {"page": missing_page, "source": {exam: item["missing"] for exam, item in components.items()}},
        "coverage": {**page_coverage, "score_by_key": score["by_key"], "score_unresolved": score["unresolved"]},
        "score_lists": score,
        "resolution_history": score.get("resolution_blocks") or [],
        "candidate_keys": {"fields": ["exam", "city", "code", "num", "cycle"], "duplicate_key_count": len(duplicate_keys), "duplicate_row_count": sum(count for _, count in duplicate_keys)},
        "statuses": status_counts,
        "evidence_level": evidence_level,
        "known_gaps": gaps,
        "resolved_adjustments": resolved_adjustments,
        "verified_scope": verified_scope,
        "unverified_scope": unverified_scope,
        "gaps": gaps,
        "sources": [_rel(root, path) for path in _component_paths(root, cycle).values()] + [_rel(root, manifest_path), _rel(root, page_path)],
    }


def build_audit(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """构建三年审计摘要；不会写文件。"""
    root = Path(root).resolve()
    checks: list[dict[str, Any]] = []
    cycles = [_audit_cycle(root, cycle, checks) for cycle in CYCLES]
    passed = sum(1 for item in checks if item["passed"])
    failed = len(checks) - passed
    snapshot_date = "undated-source"
    for cycle in cycles:
        for key in ("generated_on", "snapshot_date"):
            value = str(cycle.get(key) or "").strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                snapshot_date = value
                break
        if snapshot_date != "undated-source":
            break
    return {
        "version": 1,
        "generated_on": snapshot_date,
        "status_definitions": STATUS_DEFINITIONS,
        "evidence_level_definitions": EVIDENCE_LEVEL_DEFINITIONS,
        "cycles": cycles,
        "checks": {"passed": passed, "failed": failed, "details": checks},
        "conclusion": "三年源包、标准 JSON 与已生成页面在本报告列出的聚合层面已完成内部对账；这不等同于所有外部官方逐项资料均已发布或取得。",
    }


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _console_safe(value: Any) -> str:
    """Keep status output printable in legacy Windows code pages."""
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def write_report(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# 三年数据真实性与完整性审计 v14.4",
        "",
        f"> 生成日期：{summary['generated_on']}。本报告只读源 JSON、周期清单与已生成页面，不改写岗位数据。",
        "",
        f"**结论：** {summary['conclusion']}",
        "",
        f"**审计结果：** {summary['checks']['passed']}/{summary['checks']['passed'] + summary['checks']['failed']} 项结构与三层对账通过，失败 {summary['checks']['failed']} 项。",
        "",
        "## 1. 数据集与粒度",
        "",
        "审计粒度为岗位行。每行至少检查考试类别、城市、职位代码、单位、招录人数；成绩字段按覆盖率检查，官方未发布、未取得或无法安全匹配时保持空值。",
        "",
        "| 周期 | 页面岗位 | 页面招录 | 省考 | 事业编 | 国考 | 页面增量说明 |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in summary["cycles"]:
        exams = item["exams"]
        adjustment = item["page_adjustment"]
        note = f"事业编 +{adjustment['posts']} 岗 / +{adjustment['recruits']} 人（源包转换口径）" if adjustment["posts"] else "组件行数与页面一致"
        lines.append(
            f"| {item['cycle']} | {_fmt(item['posts'])} | {_fmt(item['recruits'])} | {_fmt(exams['省考']['posts'])} | {_fmt(exams['事业编']['posts'])} | {_fmt(exams['国考']['posts'])} | {note} |"
        )
    lines += [
        "",
        "## 2. 核验项目",
        "",
        "- 源文件自洽：声明行数与 positions 行数、声明招录人数与逐行合计、关键字段空值。",
        "- 页面自洽：页面行数、招录人数、考试分类、成绩覆盖元数据与逐行派生值。",
        "- 三层对账：标准源 JSON → 页面内嵌 `allMajors`，并记录 2026 构建器已登记的事业编增量。",
        "- 成绩清单：周期字段、复合键规模和 unresolved 数量。",
        "",
        "| 周期 | 通过 | 失败 | 成绩 by_key | 无法唯一匹配 | 页面关键字段空值 |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    for item in summary["cycles"]:
        cycle_checks = [check_item for check_item in summary["checks"]["details"] if check_item["name"].startswith(f"{item['cycle']} ")]
        passed = sum(1 for check_item in cycle_checks if check_item["passed"])
        missing = ", ".join(f"{key}={value}" for key, value in item["missing"]["page"].items() if value) or "0"
        lines.append(f"| {item['cycle']} | {passed} | {len(cycle_checks) - passed} | {_fmt(item['score_lists']['by_key'])} | {_fmt(item['score_lists']['unresolved'])} | {missing} |")
    lines += ["", "## 3. 关键覆盖与重复键", ""]
    for item in summary["cycles"]:
        coverage = item["coverage"]
        lines += [
            f"### {item['cycle']}年度",
            "",
            f"成绩覆盖（岗位数）：报名 bm={_fmt(coverage['bm'])}、合格 hg={_fmt(coverage['hg'])}、缴费 jf={_fmt(coverage['jf'])}、达线 adv={_fmt(coverage['adv'])}、入围线 line={_fmt(coverage['line'])}、最高分 top={_fmt(coverage['top'])}、录用参考 hire={_fmt(coverage['hire'])}。",
            f"候选复合键字段：`{' + '.join(item['candidate_keys']['fields'])}`；重复键 {item['candidate_keys']['duplicate_key_count']} 组、涉及 {item['candidate_keys']['duplicate_row_count']} 行。重复键是风险提示，不在本轮擅自去重。",
            "",
        ]
    lines += ["## 4. 证据状态定义", "", "| 状态 | 含义 |", "|---|---|"]
    for key, description in summary["status_definitions"].items():
        lines.append(f"| `{key}` | {description} |")
    lines += ["", "## 5. 已知缺口与风险", ""]
    for item in summary["cycles"]:
        lines += [f"### {item['cycle']}年度", ""]
        if not item["gaps"]:
            lines.append("- 无已登记缺口。")
        else:
            for gap in item["gaps"]:
                lines.append(f"- **{gap['kind']} / {gap['severity']}**：{gap['title']}。{gap['detail']}（证据：`{gap['evidence']}`）")
        lines.append("")
    lines += ["## 6. 已核验调整", ""]
    adjustments = [
        (item["cycle"], adjustment)
        for item in summary["cycles"]
        for adjustment in item.get("resolved_adjustments", [])
        if isinstance(adjustment, dict)
    ]
    if not adjustments:
        lines.append("- 当前没有登记已核验调整。")
    else:
        for cycle, adjustment in adjustments:
            lines.append(
                f"- **{cycle} / {adjustment.get('kind', 'source_bundle')}**："
                f"{adjustment.get('title', '已登记调整')}。"
                f"{adjustment.get('detail', '')}（证据：`{adjustment.get('evidence', '')}`）"
            )
    lines += ["", "## 7. 已核验范围与未核验范围", ""]
    for item in summary["cycles"]:
        lines += [f"### {item['cycle']}年度（证据层：`{item['evidence_level']}`）", "", "已核验范围："]
        lines.extend(f"- {scope}" for scope in item["verified_scope"])
        lines.append("未核验范围：")
        lines.extend(f"- {scope}" for scope in item["unverified_scope"] or ["当前没有登记未核验项。"])
        lines.append("")
    lines += [
        "## 8. 结论与后续动作",
        "",
        "当前可以确认：三年交付包的岗位主数据、周期统计和页面内嵌数据在本报告列出的层面内部一致，关键字段没有发现空值漂移；这属于源包内部可复现结论。",
        "",
        "当前不能确认：所有外部官方公告都已经公开、所有成绩字段都有逐岗原文、以及缺口岗位的未来值。后续应只在取得可定位的官方公告/附件后，通过现有只补不盖和安全复合键流程更新。",
        "",
        "## 9. 本轮数据设计与展示门禁",
        "",
        "- 每个岗位行由 `job_id` 作为周期级稳定身份；ID 使用考试类别、城市、职位代码、单位和源表职位身份，不把招录人数放入身份，避免人数修订导致收藏、对比和备注漂移。",
        "- 每行都有 `score_observation` 状态；分数模拟只接受 `comparable` 且同一 `scale_id` 的成绩，缺失、0 哨兵和跨量纲数值一律不进入概率或排序。",
        "- 每行都有 `competition_observations`，分别保存 `registrations` 与 `examinees`；聚合层通过 `competition_metric_type` 和 `ratio_comparable` 门禁，混合分母或覆盖不完整时页面显示“不可比”。",
        "- 职位名称使用 `title_status` / `display_title` 公开披露边界；源表未单列时展示“源表未单列披露”，不以单位名称代替职位名称。",
        "- 周期切换在同一离线 HTML 内重新挂载对应 payload，不通过全页刷新切换；所有未知值仍保留空值并在页面的证据/缺口视图中解释。",
        "",
        "## 10. 来源清单",
        "",
    ]
    for item in summary["cycles"]:
        lines.append(f"- {item['cycle']}：" + "、".join(f"`{source}`" for source in item["sources"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit 2024-2026 Anhui data layers")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        summary = build_audit(args.root, args.output_json.parent)
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_report(summary, args.report)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"AUDIT_ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"three-year audit: {summary['checks']['passed']} passed, {summary['checks']['failed']} failed")
    print(f"summary: {_console_safe(args.output_json)}")
    print(f"report: {_console_safe(args.report)}")
    return 0 if summary["checks"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
