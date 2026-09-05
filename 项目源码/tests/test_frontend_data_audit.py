from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT.parent / "site"
LITE = ROOT.parent.parent / "wan-lite" / "site"
CYCLES = ("2024", "2025", "2026")
PREFECTURES = (
    "合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆",
    "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城",
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(payload: dict) -> list[dict]:
    return list(((payload.get("allMajors") or {}).get("rows") or []))


def _job_id(row: dict) -> str:
    return str(row.get("job_id") or row.get("row_id") or row.get("code") or "")


def _recruits(row: dict) -> int:
    return int(row.get("num") or row.get("recruits") or 0)


def _trend_city(value: object) -> str | None:
    city = str(value or "").strip()
    if city == "省直":
        return "省直"
    if city == "宿松":
        return "安庆"
    if city == "广德":
        return "宣城"
    return next((candidate for candidate in PREFECTURES if city == candidate or city.startswith(candidate)), None)


class FrontendDataAuditTests(unittest.TestCase):
    def test_frontend_scope_contract_covers_all_job_views_and_auxiliary_tools(self) -> None:
        js = (ROOT / "tools" / "anhui_web" / "templates" / "maintainable-site.js").read_text(encoding="utf-8")
        tools = (ROOT / "tools" / "anhui_web" / "templates" / "v17-tools.js").read_text(encoding="utf-8")
        self.assertIn("const scopedJobs = scopeExamPayload(jobs);", js)
        self.assertIn("renderOverview(overview, scopedJobs, derived)", js)
        self.assertIn("renderRanking(scopedJobs, catalog)", js)
        self.assertIn("renderSearch(scopedJobs, catalog, positions)", js)
        self.assertIn("mapCityFor(city) || city", js)
        self.assertIn("data-maint-cycle-summary", js)
        self.assertIn("row.zw || row.display_title || '源表未单列披露'", js)
        self.assertIn("filterRowsByExam(jobs?.allMajors?.rows || [], examFilter, examSub)", tools)
        self.assertIn("examSub = ''", tools)

    def test_all_generated_modules_conserve_rows_recruits_ids_and_hashes(self) -> None:
        manifest = _json(FULL / "data" / "site-manifest.json")
        lite_manifest = _json(LITE / "data" / "site-manifest.json")
        self.assertEqual(manifest["release"], lite_manifest["release"])
        self.assertEqual([str(item["cycle"]) for item in manifest["cycles"]], list(CYCLES))
        self.assertEqual(manifest["cycles"], lite_manifest["cycles"])

        for site in (FULL, LITE):
            site_manifest = _json(site / "data" / "site-manifest.json")
            ids_by_cycle = {
                str(item["cycle"]): {
                    _job_id(row)
                    for row in _rows(_json(site / "data" / "cycles" / str(item["cycle"]) / "jobs.json"))
                }
                for item in site_manifest["cycles"]
            }
            for entry in site_manifest["cycles"]:
                cycle = str(entry["cycle"])
                modules = entry["modules"]
                self.assertEqual(
                    set(modules),
                    {"overview", "jobs", "jobs_lite", "catalog", "positions", "changes", "audit", "derived", "palette", "major_city"},
                )
                loaded = {}
                for name, module_entry in modules.items():
                    path = site / module_entry["data"]
                    encoded = path.read_bytes()
                    self.assertEqual(len(encoded), module_entry["bytes"], f"{site} {cycle} {name} bytes")
                    self.assertEqual(hashlib.sha256(encoded).hexdigest(), module_entry["sha256"], f"{site} {cycle} {name} hash")
                    loaded[name] = json.loads(encoded.decode("utf-8"))

                rows = _rows(loaded["jobs"])
                lite_rows = _rows(loaded["jobs_lite"])
                ids = [_job_id(row) for row in rows]
                self.assertEqual(len(ids), len(set(ids)), f"{site} {cycle} job IDs")
                self.assertEqual(sorted(ids), sorted(_job_id(row) for row in lite_rows), f"{site} {cycle} lite IDs")
                source_by_id = {_job_id(row): row for row in rows}
                for lite_row in lite_rows:
                    source = source_by_id[_job_id(lite_row)]
                    self.assertTrue(all(source.get(key) == value for key, value in lite_row.items()), f"{site} {cycle} lite value drift")
                self.assertEqual(len(rows), loaded["positions"]["row_count"])
                self.assertEqual(set(ids), {str(row["record_id"]) for row in loaded["positions"]["rows"]})
                self.assertEqual(set(ids), {str(row["id"]) for row in loaded["palette"]["entries"]})
                self.assertEqual(len(rows), loaded["major_city"]["rows_total"])

                meta = (loaded["overview"].get("allMajors") or {}).get("meta") or {}
                self.assertEqual(meta["total"], len(rows))
                self.assertEqual(meta["recruits"], sum(_recruits(row) for row in rows))
                self.assertEqual(dict(meta["examCounts"]), dict(Counter(str(row.get("exam") or "") for row in rows)))
                mix = loaded["derived"]["mix"]
                self.assertEqual(sum(int(item.get("posts") or 0) for item in mix), len(rows))
                trend = loaded["derived"]["city_trend"]
                unmapped = loaded["derived"].get("unmapped_cities") or {}
                mapped_sum = sum(int((item.get("posts") or {}).get(cycle) or 0) for item in trend.values())
                unmapped_sum = sum(int(value or 0) for value in (unmapped.get(cycle) or {}).values())
                self.assertEqual(mapped_sum + unmapped_sum, len(rows), f"{site} {cycle} trend conservation")

                for change in loaded["changes"]["changes"]:
                    if change.get("base_record_id"):
                        self.assertIn(str(change["base_record_id"]), ids_by_cycle[str(loaded["changes"]["base_cycle"])])
                    if change.get("target_record_id"):
                        self.assertIn(str(change["target_record_id"]), set(ids))

    def test_three_year_filter_counts_are_source_recomputable(self) -> None:
        expected = {}
        for cycle in CYCLES:
            rows = _rows(_json(FULL / "data" / "cycles" / cycle / "jobs.json"))
            for label, predicate in {
                "事业编": lambda row: "事业" in str(row.get("exam") or ""),
                "事业编/上半年": lambda row: "事业" in str(row.get("exam") or "") and row.get("cycle") == "上半年",
                "事业编/下半年": lambda row: "事业" in str(row.get("exam") or "") and row.get("cycle") == "下半年",
                "公务员": lambda row: any(token in str(row.get("exam") or "") for token in ("省考", "国考")),
            }.items():
                selected = [row for row in rows if predicate(row)]
                expected[(cycle, label)] = (len(selected), sum(_recruits(row) for row in selected))
            syb_rows = [row for row in rows if "事业" in str(row.get("exam") or "")]
            self.assertTrue(all(str(row.get("cycle") or "") in {"上半年", "下半年"} for row in syb_rows), cycle)
        self.assertEqual(expected[("2024", "事业编/上半年")], (4819, 6345))
        self.assertEqual(expected[("2025", "事业编/上半年")], (4840, 6028))
        self.assertEqual(expected[("2026", "事业编/上半年")], (3521, 4323))
        self.assertEqual(expected[("2024", "事业编/下半年")], (396, 566))
        self.assertEqual(expected[("2025", "事业编/下半年")], (651, 928))
        self.assertEqual(expected[("2026", "事业编/下半年")], (655, 742))

    def test_source_city_granularity_is_conserved_by_prefecture_trend(self) -> None:
        for cycle in CYCLES:
            rows = _rows(_json(FULL / "data" / "cycles" / cycle / "jobs.json"))
            selected = [row for row in rows if "事业" in str(row.get("exam") or "") and row.get("cycle") == "上半年"]
            raw = Counter(str(row.get("city") or row.get("reg") or "") for row in selected)
            canonical = Counter(_trend_city(row.get("city") or row.get("reg")) for row in selected)
            self.assertEqual(sum(raw.values()), sum(canonical.values()), cycle)
            self.assertGreater(len(raw), len(canonical) if cycle == "2024" else 0)
            self.assertNotIn(None, canonical)


if __name__ == "__main__":
    unittest.main()
