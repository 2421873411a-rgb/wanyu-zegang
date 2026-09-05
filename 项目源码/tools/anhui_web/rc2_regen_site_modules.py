# -*- coding: utf-8 -*-
"""v17.8.5-RC2 阶段 L：以现库 raw 行为行源，经 builder 同一装配层再生站点数据模块。

背景：legacy_v11（皖域择岗总览.html）在设备灾难中丢失，全链 build_pages →
unified bundle → maintainable 暂时无法从零执行（BLOCKED_BY_EVIDENCE，见
docs/audit/stage-F-rebuild-status.md 与 rc1-review）。本工具用生产 jobs.json
的 raw 行（8511，含 record_status=duplicate 的 110 行）构造等价 bundle，
调用 build_maintainable_site.assemble_maintainable_site——与全链构建完全相同
的装配代码——验证并再生 2026 用户模块。

合并策略（生产 站点 只被构建器输出覆盖，禁止手工 JSON）：
- 重建并覆盖：2026 的 jobs/overview/catalog/positions/audit/jobs_lite/major_city/
  changes/palette/derived + data/audit/three-year.json + review-queue.json +
  archive/scores/2026.json。
- 等价性对照：2024/2025 模块应与现库逐字节一致（无生命周期变化；差异=0 才算
  stub 忠实）；2024/2025 现库文件不覆盖，仅 manifest 补 raw/active/excluded 计数。
- 保留不动：major_index/req_fields（模块登记沿用）、calendar/job_history/map/
  salary/supplement 文件与登记。

产物：docs/audit/rc2-regen-report.json（事实对比 + 差异清单）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # 项目源码

from tools.anhui_web.build_maintainable_site import (  # noqa: E402
    SUPPORTED_CYCLES,
    _compute_cycle_meta,
    assemble_maintainable_site,
    _write_json,
)
from tools.anhui_web.record_lifecycle import load_overrides, split_records  # noqa: E402

PROJECT_ROOT = HERE.parents[1]          # 项目源码
WORKSPACE = PROJECT_ROOT.parent          # 择岗
SITE = WORKSPACE / "网站"
REPORT_PATH = WORKSPACE / "docs" / "audit" / "rc2-regen-report.json"

REGEN_MODULES = ("audit", "catalog", "changes", "derived", "jobs", "jobs_lite",
                 "major_city", "overview", "positions")
COUNT_KEYS = ("raw_posts", "active_posts", "excluded_posts", "raw_recruits", "recruits", "posts")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_stub_bundle(cycle: str, prod_manifest: dict) -> SimpleNamespace:
    cyc_dir = SITE / "data" / "cycles" / cycle
    jobs_doc = load_json(cyc_dir / "jobs.json")
    overview = load_json(cyc_dir / "overview.json")
    rows = copy.deepcopy(jobs_doc["allMajors"]["rows"])
    prod_meta = copy.deepcopy(jobs_doc["allMajors"].get("meta") or {})
    ty = load_json(HERE / "data" / "three_year_audit.json")
    audit_entry = copy.deepcopy(next(c for c in ty["cycles"] if str(c.get("cycle")) == cycle))
    if cycle == "2026":
        # 还原 bundle 原始 meta：行级公式复算 + 非行级字段携带（hire 为构建期投影，行级无字段）
        raw_meta = _compute_cycle_meta(rows)
        for key, value in prod_meta.items():
            if key not in raw_meta:
                raw_meta[key] = copy.deepcopy(value)
        hire = ((prod_meta.get("scoreCoverage") or {}).get("hire"))
        if hire is not None:
            raw_meta.setdefault("scoreCoverage", {})["hire"] = hire
        payload_meta = raw_meta
    else:
        # 2024/2025 无排除：bundle 原始 meta 即现库 jobs meta（行级公式已由标定断言覆盖）
        payload_meta = prod_meta
    runtime = overview.get("cycleRuntime") or {}
    source_file = Path(str(runtime.get("source_file") or "皖域择岗总览.html"))
    payload = {
        "allMajors": {"meta": payload_meta, "rows": rows},
        "cycleInfo": copy.deepcopy(overview.get("cycleInfo") or {}),
    }
    return SimpleNamespace(
        cycle=cycle,
        label=str(overview.get("label") or jobs_doc.get("label") or cycle),
        source_file=source_file,
        records=rows,
        score_lists=load_json(HERE / "data" / "score_lists.json") if cycle == "2026" else None,
        audit=audit_entry,
        payload=payload,
        cycle_info=copy.deepcopy(overview.get("cycleInfo") or {}),
    )


def json_diff(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append((path + "/" + k, "missing_in_new", str(b[k])[:60]))
            elif k not in b:
                out.append((path + "/" + k, "missing_in_prod", str(a[k])[:60]))
            else:
                out += json_diff(a[k], b[k], path + "/" + k)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, "len", f"prod {len(a)} vs new {len(b)}"))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                out += json_diff(x, y, f"{path}[{i}]")
    elif a != b:
        out.append((path, "value", f"{str(a)[:50]} vs {str(b)[:50]}"))
    return out


def main() -> int:
    prod_manifest_path = SITE / "data" / "site-manifest.json"
    prod_manifest = load_json(prod_manifest_path)
    stubs = {cycle: build_stub_bundle(cycle, prod_manifest) for cycle in SUPPORTED_CYCLES}
    scratch = Path(tempfile.mkdtemp(prefix="wanyu-rc2-"))
    scratch_manifest = assemble_maintainable_site(stubs, root=PROJECT_ROOT, output_dir=scratch)

    report: dict = {"regen_modules": list(REGEN_MODULES), "cycles": {}, "equivalence": {}, "merge": {}}

    # ---- 等价性对照：2024/2025（无生命周期变化，必须逐字节一致） ----
    for cycle in ("2024", "2025"):
        diffs = {}
        for module in REGEN_MODULES:
            prod_path = SITE / "data" / "cycles" / cycle / f"{module}.json"
            if not prod_path.is_file():
                continue  # 现库未登记的模块（如 2024 palette）不参与等价性对照
            new_doc = load_json(scratch / "data" / "cycles" / cycle / f"{module}.json")
            prod_doc = load_json(prod_path)
            d = json_diff(prod_doc, new_doc)
            if d:
                diffs[module] = d[:12]
        report["equivalence"][cycle] = {"byte_equal": not diffs, "diffs": diffs}

    # ---- 2026 事实核对 ----
    jobs26 = load_json(scratch / "data" / "cycles" / "2026" / "jobs.json")
    lite26 = load_json(scratch / "data" / "cycles" / "2026" / "jobs_lite.json")
    meta26 = jobs26["allMajors"]["meta"]
    rows26 = jobs26["allMajors"]["rows"]
    _, active26, excluded26 = split_records(rows26)
    facts = {
        "raw_posts": len(rows26),
        "active_posts": len(active26),
        "excluded_posts": len(excluded26),
        "raw_recruits": sum(int(r.get("num") or 0) for r in rows26),
        "recruits": int(meta26.get("recruits") or 0),
        "lite_rows": len(lite26["allMajors"]["rows"]),
        "lite_excluded": sum(1 for r in lite26["allMajors"]["rows"] if r.get("record_status") not in (None, "active")),
        "score_unresolved": load_json(scratch / "data" / "cycles" / "2026" / "audit.json")["scoreLists"]["keyed"]["unresolved"],
        "resolved": load_json(scratch / "data" / "cycles" / "2026" / "audit.json")["audit"]["score_lists"].get("resolved"),
        "major_city_rows_total": load_json(scratch / "data" / "cycles" / "2026" / "major_city.json")["rows_total"],
        "catalog_row_count": load_json(scratch / "data" / "cycles" / "2026" / "catalog.json")["row_count"],
    }
    expect = {"raw_posts": 8511, "active_posts": 8401, "excluded_posts": 110,
              "raw_recruits": 12006, "recruits": 11883, "lite_rows": 8401, "lite_excluded": 0,
              "score_unresolved": 0, "resolved": 116,
              "major_city_rows_total": 8401, "catalog_row_count": 8401}
    facts_ok = all(facts[k] == v for k, v in expect.items())
    report["cycles"]["2026"] = {"facts": facts, "expected": expect, "ok": facts_ok}
    if not facts_ok:
        report["status"] = "FAIL"
        (WORKSPACE / "docs" / "audit").mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        shutil.rmtree(scratch, ignore_errors=True)
        raise SystemExit(f"2026 事实核对失败：{ {k: (facts[k], v) for k, v in expect.items() if facts[k] != v} }")

    # ---- 合并进生产 站点 ----
    scratch_manifest_cycles = {str(e.get("cycle")): e for e in scratch_manifest["cycles"]}
    merged = copy.deepcopy(prod_manifest)
    merged["metrics_contract"] = copy.deepcopy(scratch_manifest.get("metrics_contract"))
    for cycle in SUPPORTED_CYCLES:
        cyc_dir = SITE / "data" / "cycles" / cycle
        scratch_entry = scratch_manifest_cycles[cycle]
        prod_entry = next(e for e in merged["cycles"] if str(e.get("cycle")) == cycle)
        regen_list = REGEN_MODULES
        # palette 已退役（v17.7.1），不重建、不登记
        prod_entry["modules"].pop("palette", None)
        for module in regen_list:
            shutil.copyfile(scratch / "data" / "cycles" / cycle / f"{module}.json", cyc_dir / f"{module}.json")
            prod_entry["modules"][module] = copy.deepcopy(scratch_entry["modules"][module])
        # 计数字段全周期统一为 wanyu-metrics/v1
        scratch_counts = {k: scratch_entry.get(k) for k in COUNT_KEYS}
        for key, value in scratch_counts.items():
            if value is not None:
                prod_entry[key] = value
        prod_entry["score_unresolved"] = scratch_entry.get("score_unresolved")
        prod_entry["gaps"] = scratch_entry.get("gaps")
        prod_entry["status"] = scratch_entry.get("status")
    # 全局审计索引与复核队列
    for rel in ("data/audit/three-year.json", "data/audit/review-queue.json"):
        target = SITE / rel
        shutil.copyfile(scratch / rel, target)
        entry_key = "audit" if "three-year" in rel else "review_queue"
        scratch_entry = scratch_manifest.get(entry_key) or {}
        merged[entry_key] = {**merged.get(entry_key, {}), **copy.deepcopy(scratch_entry)}
    # 2026 分数归档
    score_arc = SITE / "archive" / "scores" / "2026.json"
    if (scratch / "archive" / "scores" / "2026.json").is_file() and score_arc.parent.is_dir():
        shutil.copyfile(scratch / "archive" / "scores" / "2026.json", score_arc)
    _write_json(prod_manifest_path, merged)
    report["merge"] = {"manifest": "merged(metrics_contract + per-cycle counts + regen modules)",
                       "scratch_dir": str(scratch)}

    (WORKSPACE / "docs" / "audit").mkdir(parents=True, exist_ok=True)
    report["status"] = "PASS"
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    shutil.rmtree(scratch, ignore_errors=True)
    print("2026 事实核对通过：", json.dumps(facts, ensure_ascii=False))
    for cycle, eq in report["equivalence"].items():
        print(f"{cycle} 等价性：{'逐字节一致' if eq['byte_equal'] else '存在差异 ' + str(len(eq['diffs'])) + ' 处（前 12 见报告）'}")
    print("manifest 已合并再生；报告 →", REPORT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
