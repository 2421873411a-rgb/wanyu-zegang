"""Verify the disk output of the long-lived external-data site.

This verifier intentionally reads the generated files back from disk instead
of trusting the builder's in-memory objects. It checks module boundaries,
hashes, row/recruit totals, stable IDs, audit counts, and local-only assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


CYCLES = ("2024", "2025", "2026")
MAP_CITIES = ("合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城")
MODULES = ("overview", "jobs", "jobs_lite", "catalog", "positions", "changes", "audit", "derived", "major_city")
# P0-9③(2026-09-05): palette.json 退役（命令面板改由 jobs_lite 派生）——已登记 palette 的旧包仍按原口径校验
OPTIONAL_MODULES = ("palette", "major_index")
MODULE_SCHEMAS = {
    "overview": "wanyu-maintainable-overview/v1",
    "jobs": "wanyu-maintainable-jobs/v1",
    "catalog": "wanyu-maintainable-catalog/v1",
    "positions": "wanyu-maintainable-position-index/v1",
    "scores": "wanyu-maintainable-scores/v1",
    "changes": "wanyu-maintainable-changes/v1",
    "audit": "wanyu-maintainable-audit/v1",
    "derived": "wanyu-maintainable-derived/v1",
    "palette": "wanyu-maintainable-palette/v1",
    "jobs_lite": "wanyu-maintainable-jobs-lite/v1",
    "major_city": "wanyu-maintainable-major-city/v1",
    "major_index": "wanyu-major-index/v1",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(checks: list[dict[str, Any]], check_id: str, expected: Any, actual: Any, message: str) -> None:
    checks.append({
        "id": check_id,
        "status": "pass" if expected == actual else "fail",
        "expected": expected,
        "actual": actual,
        "message": message,
    })


def _unresolved(audit_payload: dict[str, Any]) -> int:
    value = ((audit_payload.get("scoreLists") or {}).get("keyed") or {}).get("unresolved")
    if isinstance(value, list):
        return len(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def verify_maintainable_site(site_dir: Path) -> dict[str, Any]:
    """Return a machine-readable report for one generated maintainable site."""
    site_dir = Path(site_dir).resolve()
    checks: list[dict[str, Any]] = []
    manifest_path = site_dir / "data" / "site-manifest.json"
    index_path = site_dir / "index.html"
    if not manifest_path.is_file():
        _check(checks, "manifest.present", True, False, "site manifest exists")
        return {"status": "fail", "passed": 0, "failed": 1, "checks": checks}
    manifest = _read_json(manifest_path)
    _check(checks, "manifest.schema", "wanyu-maintainable-site/v3", manifest.get("schema"), "manifest schema")
    cycle_entries = manifest.get("cycles") if isinstance(manifest.get("cycles"), list) else []
    _check(checks, "manifest.cycles", list(CYCLES), [str(item.get("cycle")) for item in cycle_entries], "manifest contains all cycles in order")
    audit_entry = manifest.get("audit") if isinstance(manifest.get("audit"), dict) else {}
    audit_path = site_dir / str(audit_entry.get("data") or "")
    audit = _read_json(audit_path)
    _check(checks, "audit.sha256", audit_entry.get("sha256"), _sha256(audit_path), "global audit hash")
    _check(checks, "audit.schema", "wanyu-maintainable-audit/v1", audit.get("schema"), "global audit schema")
    audit_cycles = audit.get("cycles") if isinstance(audit.get("cycles"), list) else []
    _check(checks, "audit.cycles", list(CYCLES), [str(item.get("cycle")) for item in audit_cycles], "global audit contains all cycles")
    review_entry = manifest.get("review_queue") if isinstance(manifest.get("review_queue"), dict) else {}
    review_path = site_dir / str(review_entry.get("data") or "")
    review_queue = _read_json(review_path) if review_path.is_file() else {}
    _check(checks, "review_queue.present", True, review_path.is_file(), "review queue exists")
    if review_path.is_file():
        _check(checks, "review_queue.sha256", review_entry.get("sha256"), _sha256(review_path), "review queue hash")
        _check(checks, "review_queue.schema", "wanyu-maintainable-review-queue/v1", review_queue.get("schema"), "review queue schema")
        review_summary = review_queue.get("summary") if isinstance(review_queue.get("summary"), dict) else {}
        _check(checks, "review_queue.public_boundaries", 8, review_summary.get("public_boundary_count"), "public boundary count")
        _check(checks, "review_queue.unresolved_scores", 116, review_summary.get("unresolved_score_count"), "unresolved score count")
    map_entry = manifest.get("map") if isinstance(manifest.get("map"), dict) else {}
    map_path = site_dir / str(map_entry.get("data") or "")
    map_present = map_path.is_file()
    _check(checks, "map.present", True, map_present, "external map module exists")
    if map_present:
        map_payload = _read_json(map_path)
        _check(checks, "map.sha256", map_entry.get("sha256"), _sha256(map_path), "external map hash")
        _check(checks, "map.bytes", map_entry.get("bytes"), map_path.stat().st_size, "external map byte count")
        _check(checks, "map.schema", "wanyu-maintainable-map/v1", map_payload.get("schema"), "external map schema")
        _check(checks, "map.source", "tools/anhui_web/data/anhui_340000_full.json", map_payload.get("source_module"), "external map source")
        features = map_payload.get("features") if isinstance(map_payload.get("features"), list) else []
        _check(checks, "map.feature_count", 16, map_payload.get("feature_count"), "map feature count")
        _check(checks, "map.cities", sorted(MAP_CITIES), sorted(str(item.get("city")) for item in features if isinstance(item, dict)), "map contains the sixteen prefecture cities")
        _check(checks, "map.paths", 16, sum(bool(item.get("d")) for item in features if isinstance(item, dict)), "map features have projected paths")
        _check(checks, "map.centroids", 16, sum(isinstance(item.get("x"), (int, float)) and isinstance(item.get("y"), (int, float)) for item in features if isinstance(item, dict)), "map features have projected label coordinates")
    salary_entry = manifest.get("salary") if isinstance(manifest.get("salary"), dict) else {}
    salary_path = site_dir / str(salary_entry.get("data") or "")
    salary_present = salary_path.is_file()
    _check(checks, "salary.present", True, salary_present, "external salary module exists")
    if salary_present:
        salary_payload = _read_json(salary_path)
        _check(checks, "salary.sha256", salary_entry.get("sha256"), _sha256(salary_path), "external salary hash")
        _check(checks, "salary.bytes", salary_entry.get("bytes"), salary_path.stat().st_size, "external salary byte count")
        _check(checks, "salary.schema", "wanyu-maintainable-salary/v1", salary_payload.get("schema"), "external salary schema")
        salary_series = salary_payload.get("series") if isinstance(salary_payload.get("series"), dict) else {}
        _check(checks, "salary.types", sorted(["公务员", "事业编"]), sorted(str(key) for key in salary_series), "salary employment types")
        _check(checks, "salary.cities", 16, len(salary_payload.get("cities") or []), "salary covers the sixteen prefecture cities")
    history_entry = manifest.get("job_history") if isinstance(manifest.get("job_history"), dict) else {}
    history_path = site_dir / str(history_entry.get("data") or "")
    history_present = history_path.is_file()
    _check(checks, "job_history.present", True, history_present, "external job history module exists")
    if history_present:
        history_payload = _read_json(history_path)
        _check(checks, "job_history.sha256", history_entry.get("sha256"), _sha256(history_path), "external job history hash")
        _check(checks, "job_history.bytes", history_entry.get("bytes"), history_path.stat().st_size, "external job history byte count")
        _check(checks, "job_history.schema", "wanyu-maintainable-job-history/v1", history_payload.get("schema"), "external job history schema")
        history_jobs = history_payload.get("jobs") if isinstance(history_payload.get("jobs"), dict) else {}
        _check(checks, "job_history.coverage", True, len(history_jobs) >= 500, "job history covers a meaningful number of job families")
        sources = history_payload.get("sources") if isinstance(history_payload.get("sources"), dict) else {}
        provenance_ok = True
        for cycle, source in sources.items():
            cycle_entry = next((item for item in cycle_entries if str(item.get("cycle")) == str(cycle)), {})
            lite_entry = (cycle_entry.get("modules") or {}).get("jobs") if isinstance(cycle_entry.get("modules"), dict) else {}
            if not source or lite_entry.get("sha256") != source.get("sha256"):
                provenance_ok = False
        _check(checks, "job_history.provenance", True, provenance_ok and len(sources) >= 2, "job history binds to jobs.json sha256 per cycle")
    for cycle_entry in cycle_entries:
        cycle = str(cycle_entry.get("cycle"))
        modules = cycle_entry.get("modules") if isinstance(cycle_entry.get("modules"), dict) else {}
        missing_core = [m for m in MODULES if m not in modules]
        _check(checks, f"{cycle}.modules.core", [], missing_core, f"{cycle} core modules all registered")
        unknown = [m for m in modules if m not in MODULES and m not in OPTIONAL_MODULES]
        _check(checks, f"{cycle}.modules.known", [], unknown, f"{cycle} registered modules are known (palette optional)")
        loadable = MODULES + tuple(m for m in OPTIONAL_MODULES if m in modules)
        loaded: dict[str, dict[str, Any]] = {}
        for module in loadable:
            module_entry = modules.get(module) if isinstance(modules.get(module), dict) else {}
            path = site_dir / str(module_entry.get("data") or "")
            present = path.is_file()
            _check(checks, f"{cycle}.{module}.present", True, present, f"{cycle} {module} file exists")
            if not present:
                continue
            actual_hash = _sha256(path)
            _check(checks, f"{cycle}.{module}.sha256", module_entry.get("sha256"), actual_hash, f"{cycle} {module} hash")
            payload = _read_json(path)
            loaded[module] = payload
            _check(checks, f"{cycle}.{module}.schema", MODULE_SCHEMAS[module], payload.get("schema"), f"{cycle} {module} schema")
        score_path = site_dir / "archive" / "scores" / f"{cycle}.json"
        score_archive: dict[str, Any] = {}
        score_present = score_path.is_file()
        _check(checks, f"{cycle}.scores_archive.present", True, score_present, f"{cycle} archived score attachment exists")
        if score_present:
            score_archive = _read_json(score_path)
            _check(checks, f"{cycle}.scores_archive.schema", MODULE_SCHEMAS["scores"], score_archive.get("schema"), f"{cycle} archived score schema")
            _check(checks, f"{cycle}.scores_archive.cycle", cycle, str(score_archive.get("cycle")), f"{cycle} archived score cycle")
        jobs = loaded.get("jobs") or {}
        rows = ((jobs.get("allMajors") or {}).get("rows") if isinstance(jobs.get("allMajors"), dict) else [])
        rows = rows if isinstance(rows, list) else []
        _check(checks, f"{cycle}.jobs.rows", int(cycle_entry.get("posts") or 0), len(rows), f"{cycle} jobs row count")
        recruits = sum(int(row.get("num") or 0) for row in rows if isinstance(row, dict))
        _check(checks, f"{cycle}.jobs.recruits", int(cycle_entry.get("recruits") or 0), recruits, f"{cycle} jobs recruit sum")
        row_ids = [str(row.get("job_id") or "") for row in rows if isinstance(row, dict)]
        _check(checks, f"{cycle}.jobs.ids", len(row_ids), len(set(row_ids)), f"{cycle} stable job IDs are unique")
        major_city = loaded.get("major_city") or {}
        lite_entry = modules.get("jobs_lite") if isinstance(modules.get("jobs_lite"), dict) else {}
        _check(checks, f"{cycle}.major_city.provenance", lite_entry.get("sha256"), major_city.get("source_sha256"), f"{cycle} major_city binds to jobs_lite sha256")
        _check(checks, f"{cycle}.major_city.keywords", True, len(major_city.get("keywords") or {}) >= 100, f"{cycle} major_city keyword coverage")
        overview = loaded.get("overview") or {}
        audit_module = loaded.get("audit") or {}
        overview_has_rows = isinstance((overview.get("allMajors") or {}), dict) and "rows" in (overview.get("allMajors") or {})
        audit_has_rows = isinstance((audit_module.get("allMajors") or {}), dict) and "rows" in (audit_module.get("allMajors") or {})
        _check(checks, f"{cycle}.overview.no_rows", False, overview_has_rows, f"{cycle} overview has no job rows")
        _check(checks, f"{cycle}.audit.no_rows", False, audit_has_rows, f"{cycle} audit has no job rows")
        audit_cycle = audit_module.get("audit") if isinstance(audit_module.get("audit"), dict) else {}
        _check(checks, f"{cycle}.audit.cycle", cycle, str(audit_cycle.get("cycle")), f"{cycle} audit cycle matches")
        _check(checks, f"{cycle}.audit.unresolved", int(cycle_entry.get("score_unresolved") or 0), _unresolved(audit_module), f"{cycle} unresolved score count")
        catalog = loaded.get("catalog") or {}
        _check(checks, f"{cycle}.catalog.no_rows", False, "rows" in catalog, f"{cycle} catalog has no full rows")
        _check(checks, f"{cycle}.catalog.readable_majors", True, all(bool(re.search(r"[A-Za-z\u4e00-\u9fff]", str(value))) for value in (catalog.get("majors") or [])), f"{cycle} catalog majors are readable")
        positions = loaded.get("positions") or {}
        _check(checks, f"{cycle}.positions.rows", len(rows), int(positions.get("row_count") or 0), f"{cycle} position index row count")
        _check(checks, f"{cycle}.positions.list", len(rows), len(positions.get("rows") or []), f"{cycle} position index entries")
        _check(checks, f"{cycle}.scores_archive.unresolved", int(cycle_entry.get("score_unresolved") or 0), int((score_archive.get("summary") or {}).get("unresolved") or 0), f"{cycle} archived score unresolved count")
        changes = loaded.get("changes") or {}
        _check(checks, f"{cycle}.changes.target_cycle", cycle, str(changes.get("target_cycle")), f"{cycle} changes target cycle")
        _check(checks, f"{cycle}.changes.policy", True, bool(changes.get("matching_policy")), f"{cycle} changes matching policy")
        derived = loaded.get("derived") or {}
        vs_prev = derived.get("vs_prev") if isinstance(derived.get("vs_prev"), dict) else {}
        cycle_index = CYCLES.index(cycle)
        posts_total = int(cycle_entry.get("posts") or 0)
        recruits_total = int(cycle_entry.get("recruits") or 0)
        if cycle_index > 0:
            prev_entry = cycle_entries[cycle_index - 1]
            _check(checks, f"{cycle}.derived.vs_prev.base", str(prev_entry.get("cycle")), str(vs_prev.get("base_cycle")), f"{cycle} derived base cycle")
            _check(checks, f"{cycle}.derived.vs_prev.jobs_delta", posts_total - int(prev_entry.get("posts") or 0), vs_prev.get("jobs_delta"), f"{cycle} derived jobs delta recomputes")
            _check(checks, f"{cycle}.derived.vs_prev.recruits_delta", recruits_total - int(prev_entry.get("recruits") or 0), vs_prev.get("recruits_delta"), f"{cycle} derived recruits delta recomputes")
        else:
            _check(checks, f"{cycle}.derived.vs_prev.null_base", True, vs_prev.get("base_cycle") is None and vs_prev.get("jobs_delta") is None, f"{cycle} first cycle has no fabricated previous")
        mix = derived.get("mix") if isinstance(derived.get("mix"), list) else []
        _check(checks, f"{cycle}.derived.mix_posts", posts_total, sum(int(item.get("posts") or 0) for item in mix), f"{cycle} derived mix post sum equals cycle posts")
        trend = derived.get("city_trend") if isinstance(derived.get("city_trend"), dict) else {}
        unmapped = derived.get("unmapped_cities") if isinstance(derived.get("unmapped_cities"), dict) else {}
        mapped_sum = sum(int((slot.get("posts") or {}).get(cycle) or 0) for slot in trend.values())
        unmapped_sum = sum(int(unmapped.get(city) or 0) for city in unmapped)
        _check(checks, f"{cycle}.derived.city_trend_sum", posts_total, mapped_sum + unmapped_sum, f"{cycle} derived city trend plus unmapped equals posts")
        review = derived.get("review_progress") if isinstance(derived.get("review_progress"), dict) else {}
        _check(checks, f"{cycle}.derived.review_progress", (int(cycle_entry.get("gaps") or 0), int(cycle_entry.get("score_unresolved") or 0)), (int(review.get("gaps") or 0), int(review.get("score_unresolved") or 0)), f"{cycle} derived review progress matches manifest")
        palette = loaded.get("palette") or {}
        if palette:
            palette_entries = palette.get("entries") if isinstance(palette.get("entries"), list) else []
            _check(checks, f"{cycle}.palette.rows", len(rows), len(palette_entries), f"{cycle} palette entry count equals job rows")
            palette_ids = [str(item.get("id") or "") for item in palette_entries]
            _check(checks, f"{cycle}.palette.ids_unique", len(palette_ids), len(set(palette_ids)), f"{cycle} palette stable IDs are unique")
            _check(checks, f"{cycle}.palette.ids_known", True, all(job_id in set(row_ids) for job_id in palette_ids), f"{cycle} palette IDs reference job rows")
        lite = loaded.get("jobs_lite") or {}
        lite_rows = lite.get("allMajors", {}).get("rows", []) if isinstance(lite.get("allMajors"), dict) else []
        _check(checks, f"{cycle}.jobs_lite.rows", len(rows), len(lite_rows), f"{cycle} lite index row count equals jobs rows")
        lite_ids = [str(item.get("job_id") or "") for item in lite_rows]
        _check(checks, f"{cycle}.jobs_lite.ids", sorted(row_ids), sorted(lite_ids), f"{cycle} lite index ID set equals jobs rows")
        _check(checks, f"{cycle}.jobs_lite.recruits", recruits_total, sum(int(item.get("num") or item.get("recruits") or 0) for item in lite_rows), f"{cycle} lite index recruits sum equals cycle recruits")
        source_by_id = {str(row.get("job_id") or ""): row for row in rows}
        _check(checks, f"{cycle}.jobs_lite.values_match_source", True, all(all(source_by_id.get(str(item.get("job_id") or ""), {}).get(key) == value for key, value in item.items()) for item in lite_rows), f"{cycle} lite row values are copied verbatim from jobs rows")

    expected_summary = {
        "cycle_count": 3,
        "post_count": sum(int(item.get("posts") or 0) for item in cycle_entries),
        "recruit_count": sum(int(item.get("recruits") or 0) for item in cycle_entries),
        "gap_count": sum(int(item.get("gaps") or 0) for item in cycle_entries),
        "unresolved_score_count": sum(int(item.get("score_unresolved") or 0) for item in cycle_entries),
    }
    actual_summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    for key, expected in expected_summary.items():
        _check(checks, f"audit.summary.{key}", expected, actual_summary.get(key), f"global audit summary {key}")
    if index_path.is_file():
        index = index_path.read_text(encoding="utf-8")
        _check(checks, "index.no_embedded_rows", 0, index.count("data-cycle-payload"), "index keeps job rows external")
        _check(checks, "index.local_assets", 0, len(re.findall(r"(?:src|href)=['\"]https?://", index, re.I)), "index has no remote assets")
        for asset in ("maintainable-tokens.css", "maintainable-site.css", "maintainable-data.js", "maintainable-user-store.js", "maintainable-site.js"):
            _check(checks, f"asset.{asset}", True, (site_dir / "assets" / asset).is_file(), f"local asset {asset} exists")
        _check(checks, "pwa.index_registration", True, "serviceWorker" in index and "manifest.webmanifest" in index, "index registers service worker and web manifest")
        _check(checks, "pwa.offline_badge", True, 'id="maintain-offline-badge"' in index, "index declares offline badge")
        workspace_js = (site_dir / "assets" / "maintainable-site.js").read_text(encoding="utf-8")
        _check(checks, "workspace.export_import_wired", True, "data-maint-export-workspace" in workspace_js and "data-maint-import-workspace" in workspace_js, "saved view wires workspace export/import")
        _check(checks, "workspace.update_checklist", True, "data-maint-check-step" in workspace_js and "wanyu.update.checklist.v1" in workspace_js, "help view persists update checklist")
        _check(checks, "workspace.copy_cmd", True, "data-maint-copy-cmd" in workspace_js, "help view offers copyable commands")
    else:
        _check(checks, "index.present", True, False, "maintenance index exists")
    sw_path = site_dir / "sw.js"
    if sw_path.is_file():
        sw_text = sw_path.read_text(encoding="utf-8")
        _check(checks, "pwa.sw_network_first_data", True, "/data/" in sw_text and "caches.match" in sw_text, "service worker serves data network-first with cache fallback")
        for precache in ("index.html", "assets/maintainable-site.js", "assets/maintainable-tokens.css", "assets/wanyu-icon.svg"):
            _check(checks, f"pwa.precache.{precache}", True, precache in sw_text, f"precache covers {precache}")
    else:
        _check(checks, "pwa.sw_present", True, False, "service worker exists at site root")
    webmanifest_path = site_dir / "manifest.webmanifest"
    app_manifest = None
    if webmanifest_path.is_file():
        try:
            app_manifest = json.loads(webmanifest_path.read_text(encoding="utf-8"))
            icon_src = (app_manifest.get("icons") or [{}])[0].get("src", "")
            _check(checks, "pwa.webmanifest", True, bool(app_manifest.get("start_url")) and (site_dir / icon_src).is_file(), "web manifest start_url and icon file exist")
        except (json.JSONDecodeError, OSError):
            _check(checks, "pwa.webmanifest_json", True, False, "web manifest parses as JSON")
    else:
        _check(checks, "pwa.webmanifest_present", True, False, "web manifest exists")
    failed = sum(item["status"] == "fail" for item in checks)
    passed = sum(item["status"] == "pass" for item in checks)
    return {"status": "fail" if failed else "pass", "passed": passed, "failed": failed, "checks": checks}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify the external JSON maintainable site")
    parser.add_argument("site_dir", nargs="?", type=Path, default=Path("deliverables/maintainable"))
    args = parser.parse_args()
    result = verify_maintainable_site(args.site_dir)
    print(f"maintainable: {result['passed']} passed, {result['failed']} failed")
    raise SystemExit(1 if result["failed"] else 0)
