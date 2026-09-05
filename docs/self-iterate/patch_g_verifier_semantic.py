# -*- coding: utf-8 -*-
"""v17.8.5 阶段 E：verifier 语义不变式层。

新增四类强制校验（任一不符 = FAIL，非 warning）：
  E-A unresolved 跨位置一致：manifest == overview.auditSummary == audit.audit.coverage
                            == audit.scoreLists.keyed == review_queue.summary（缺位置 = FAIL，不再默认 0）
  E-B record 生命周期：raw = active + excluded（2026=8511=8401+110）；overview.meta.total == active
  E-C 版本链：release.json.release/asset_version/sw VERSION == manifest == index ?v == SW PRECACHE ?v
  E-D 移除历史硬编码：review_queue 116 期望值改为对齐 manifest
"""
from pathlib import Path

p = Path("项目源码/tools/anhui_web/verify_maintainable_site.py")
t = p.read_text(encoding="utf-8")

# ---- E-D：去掉 review_queue 硬编码 116 ----
old = '_check(checks, "review_queue.unresolved_scores", 116, review_summary.get("unresolved_score_count"), "unresolved score count")'
new = '''manifest_unresolved_total = sum(int(item.get("score_unresolved") or 0) for item in cycle_entries)
        _check(checks, "review_queue.unresolved_scores", manifest_unresolved_total, review_summary.get("unresolved_score_count"), "unresolved score count matches manifest (no hardcoded history values)")'''
assert t.count(old) == 1
t = t.replace(old, new)

# ---- E-A/E-B/E-C：周期循环尾部追加语义不变式 ----
old_tail = """    failed = sum(item["status"] == "fail" for item in checks)"""
new_tail = """    # ===== E：语义不变式层（v17.8.5）=====
    release_json_path = Path(__file__).resolve().parents[2] / "release.json"
    release_doc = {}
    try:
        release_doc = json.loads(release_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _check(checks, "release.version_file", True, False, "release.json exists and parses")
    if release_doc:
        _check(checks, "release.version_file.release_matches_manifest", manifest.get("release"), release_doc.get("release"), "release.json release == manifest release")
        asset_versions = set(re.findall(r"\\?v=([0-9A-Za-z.\\-]+)", (site_dir / "index.html").read_text(encoding="utf-8")))
        _check(checks, "release.version_file.asset_version_matches_index", sorted(asset_versions), [release_doc.get("asset_version")], "release.json asset_version == index ?v (uniform)")
        sw_text = (site_dir / "sw.js").read_text(encoding="utf-8")
        sw_version = re.search(r'wanyu-shell-v(\\d+)', sw_text)
        _check(checks, "release.version_file.sw_matches", release_doc.get("service_worker_version"), f"wanyu-shell-v{sw_version.group(1)}" if sw_version else None, "release.json sw version == sw.js VERSION")
        precache_versions = set(re.findall(r"\\?v=([0-9A-Za-z.\\-]+)", sw_text))
        _check(checks, "release.version_file.asset_version_matches_sw_precache", sorted(precache_versions), [release_doc.get("asset_version")], "release.json asset_version == sw PRECACHE ?v (uniform)")

    for cycle_entry in cycle_entries:
        cycle = str(cycle_entry.get("cycle"))
        cyc_dir = site_dir / "data" / "cycles" / cycle
        jobs_path_c = cyc_dir / "jobs.json"
        if not jobs_path_c.is_file():
            continue
        rows_c = (json.loads(jobs_path_c.read_text(encoding="utf-8")).get("allMajors") or {}).get("rows") or []
        raw_posts = len(rows_c)
        excluded = sum(1 for r in rows_c if str(r.get("record_status") or "") not in ("", "active"))
        active = raw_posts - excluded
        _check(checks, f"{cycle}.records.raw_eq_active_plus_excluded", raw_posts, active + excluded, f"raw_posts = active + excluded ({raw_posts} = {active} + {excluded})")
        mp_raw = int(cycle_entry.get("raw_posts") or 0)
        mp_act = int(cycle_entry.get("active_posts") or 0)
        mp_exc = int(cycle_entry.get("excluded_posts") or 0)
        _check(checks, f"{cycle}.records.manifest_counts_consistent", [mp_raw, mp_act, mp_exc], [raw_posts, active, excluded], "manifest raw/active/excluded match jobs.json rows")
        ov_path = cyc_dir / "overview.json"
        if ov_path.is_file():
            ov_meta = ((json.loads(ov_path.read_text(encoding="utf-8")).get("allMajors") or {}).get("meta") or {})
            _check(checks, f"{cycle}.overview.meta_total_is_active", active, int(ov_meta.get("total") or -1), "overview meta.total == active posts")
            _check(checks, f"{cycle}.overview.meta_raw_total", raw_posts, int(ov_meta.get("raw_total") or -1), "overview meta.raw_total == raw posts")
        if cycle == "2026":
            # E-A：unresolved 跨位置强一致（缺位置 = FAIL）
            audit_p = cyc_dir / "audit.json"
            ov_p = cyc_dir / "overview.json"
            rq_p = site_dir / "data" / "audit" / "review-queue.json"
            expected = int(cycle_entry.get("score_unresolved") or 0)
            locations = {}
            if audit_p.is_file():
                a_doc = json.loads(audit_p.read_text(encoding="utf-8"))
                cov = ((a_doc.get("audit") or {}).get("coverage") or {}).get("score_unresolved")
                keyed = ((a_doc.get("scoreLists") or {}).get("keyed") or {}).get("unresolved")
                sl_scalar = (a_doc.get("scoreLists") or {}).get("unresolved")
                locations["audit.coverage"] = cov
                locations["audit.scoreLists.keyed"] = len(keyed) if isinstance(keyed, list) else keyed
                if sl_scalar is not None:
                    locations["audit.scoreLists.scalar"] = sl_scalar
            if ov_p.is_file():
                locations["overview.auditSummary"] = (json.loads(ov_p.read_text(encoding="utf-8")).get("auditSummary") or {}).get("score_unresolved")
            if rq_p.is_file():
                locations["review_queue.summary"] = (json.loads(rq_p.read_text(encoding="utf-8")).get("summary") or {}).get("unresolved_score_count")
            bad = {k: v for k, v in locations.items() if v is None or int(v) != expected}
            _check(checks, "2026.unresolved.all_locations_consistent", [], bad, f"unresolved == {expected} in every projection (missing/inconsistent = fail)")

    failed = sum(item["status"] == "fail" for item in checks)"""
assert t.count(old_tail) == 1
t = t.replace(old_tail, new_tail)

# _unresolved：缺位置不再默认 0（audit 模块无 keyed 时显式 None，交由 E-A 处置）
old_unres = """def _unresolved(audit_payload: dict[str, Any]) -> int:
    value = ((audit_payload.get("scoreLists") or {}).get("keyed") or {}).get("unresolved")
    if isinstance(value, list):
        return len(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):"""
new_unres = """def _unresolved(audit_payload: dict[str, Any]) -> int:
    value = ((audit_payload.get("scoreLists") or {}).get("keyed") or {}).get("unresolved")
    if isinstance(value, list):
        return len(value)
    if value is None:
        raise ValueError("audit.scoreLists.keyed.unresolved missing (E1: no silent default to 0)")
    try:
        return int(value)
    except (TypeError, ValueError):"""
assert t.count(old_unres) == 1
t = t.replace(old_unres, new_unres)

# 头部 import 检查（json/re 已有？确保）
assert "import re" in t and "import json" in t
p.write_bytes(t.encode("utf-8"))
print("OK verifier 语义层（E-A/B/C/D）")
