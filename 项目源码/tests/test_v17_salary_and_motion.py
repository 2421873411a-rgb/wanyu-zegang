"""v17 契约：独立待遇地图视图、工龄梯度曲线、动效降级、性能预算脚本、无远程资源。

读取源码模板与构建/校验脚本（不读构建产物，因其在发布链中于测试前尚未重建），
锁定本次移植与升级的关键不变量，纳入 release.py 门禁。
"""
from __future__ import annotations

import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "tools" / "anhui_web" / "templates"
# RC3-D2：设备特定路径清零——统一指向标准部署树 网站/（存在性校验，两设备布局兼容）
SITE = ROOT.parent / "网站"
if not SITE.is_dir():
    SITE = ROOT.parent / "site"


class V17SalaryViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.js = (TPL / "maintainable-site.js").read_text(encoding="utf-8")
        self.css = (TPL / "maintainable-site.css").read_text(encoding="utf-8")
        self.sw = (TPL / "maintainable-sw.js").read_text(encoding="utf-8")
        self.builder = (ROOT / "tools" / "anhui_web" / "build_maintainable_site.py").read_text(encoding="utf-8")
        self.verifier = (ROOT / "tools" / "anhui_web" / "verify_maintainable_site.py").read_text(encoding="utf-8")

    def test_salary_is_external_global_module(self) -> None:
        self.assertIn("_salary_payload", self.builder)
        self.assertIn("data/salary/anhui.json", self.builder)
        self.assertIn("salary", self.builder.split('manifest: dict[str, object] = {')[1])
        self.assertIn("salary.present", self.verifier)
        self.assertIn("wanyu-maintainable-salary/v1", self.verifier)

    def test_salary_view_is_dedicated_nav_and_rendered(self) -> None:
        # 独立视图：路由集合、渲染函数、命令面板条目、身份/工龄子切换、排行、曲线
        # RC3-D3：'SALARY RANKING' 文案已在后续批次考生化为「待遇排行」。
        for marker in ("'salary_map'", "const renderSalaryMap", "data-maint-salary-type",
                       "data-maint-salary-stage", "待遇排行", "maint-salary-curve"):
            self.assertIn(marker, self.js, marker)
        self.assertIn("data-maintain-view=\"salary_map\"", self.builder)
        self.assertIn(".maint-salary-curve", self.css)

    def test_salary_unknowns_never_zero(self) -> None:
        # 缺失一律“未取得/—”，不把 null 转成 0
        self.assertIn("'未取得'", self.js)
        self.assertIn("salaryOf", self.js)

    def test_jobs_map_major_filter(self) -> None:
        # 岗位地图可按专业关键词筛选，命中口径复用岗位源文本 + 可读专业；待遇是地市级口径不可按专业拆分
        for marker in ("state.mapMajor", "const majorHit", "aggregateMapCities(jobs, majorQuery)",
                       "maint-map-major", "data-maint-map-quick-major", "data-maint-map-clear-major"):
            self.assertIn(marker, self.js, marker)
        self.assertIn(".maint-map-major", self.css)

    def test_major_city_index_covers_readable_keywords_and_conserves_totals(self) -> None:
        # A2: 索引来自同一份岗位轻索引，覆盖全部可读关键词；城市与招录人数不能在派生时丢失。
        for cycle in ("2024", "2025", "2026"):
            jobs = json.loads((SITE / "data" / "cycles" / cycle / "jobs_lite.json").read_text(encoding="utf-8"))
            index = json.loads((SITE / "data" / "cycles" / cycle / "major_city.json").read_text(encoding="utf-8"))
            manifest = json.loads((SITE / "data" / "site-manifest.json").read_text(encoding="utf-8"))
            manifest_cycle = next(item for item in manifest["cycles"] if str(item["cycle"]) == cycle)
            self.assertEqual(index["schema"], "wanyu-maintainable-major-city/v1")
            self.assertEqual(index["rows_total"], len(jobs["allMajors"]["rows"]))
            self.assertGreaterEqual(len(index["keywords"]), 2500, cycle)
            self.assertEqual(index["source_sha256"], manifest_cycle["modules"]["jobs_lite"]["sha256"], cycle)
            normalized_keys = ["".join(key.split()).casefold() for key in index["keywords"]]
            self.assertEqual(len(normalized_keys), len(set(normalized_keys)), cycle)
            entry = index["keywords"].get("法学类")
            self.assertIsNotNone(entry, cycle)
            self.assertEqual(sum(item["jobs"] for item in entry["cities"].values()), entry["jobs"], cycle)
            self.assertEqual(sum(item["recruits"] for item in entry["cities"].values()), entry["recruits"], cycle)

    def test_major_city_index_is_validated_and_wired(self) -> None:
        for marker in (
            "wanyu-maintainable-major-city/v1",
            "maintainable-major-city.js",
            "majorIndexKey",
            "aggregateIndexedMajorCities",
            "loadModule(state.cycle, 'major_city')",
            "renderMap(map, examJobs, majorIndex)",
        ):
            self.assertIn(marker, self.js + self.builder, marker)
        self.assertIn("major_city", (TPL / "maintainable-data.js").read_text(encoding="utf-8"))

    def test_scores_are_archive_attachments_not_cycle_modules(self) -> None:
        for cycle in ("2024", "2025", "2026"):
            manifest = json.loads((SITE / "data" / "site-manifest.json").read_text(encoding="utf-8"))
            cycle_entry = next(item for item in manifest["cycles"] if str(item["cycle"]) == cycle)
            self.assertNotIn("scores", cycle_entry["modules"], cycle)
            archive_path = SITE / "archive" / "scores" / f"{cycle}.json"
            self.assertTrue(archive_path.is_file(), cycle)
            archive = json.loads(archive_path.read_text(encoding="utf-8"))
            self.assertEqual(archive["schema"], "wanyu-maintainable-scores/v1")
            self.assertEqual(str(archive["cycle"]), cycle)

    def test_motion_still_reduced_motion_guarded(self) -> None:
        self.assertIn("prefers-reduced-motion: reduce", self.js)
        self.assertIn("reveal-ready", self.css)
        self.assertIn("reveal-ready", self.js)

    def test_no_remote_resources_in_shell(self) -> None:
        for name, text in (("js", self.js), ("css", self.css), ("sw", self.sw)):
            self.assertNotIn("http://", text, name)
            self.assertNotIn("https://cdn", text, name)


class V17PerfBudgetTests(unittest.TestCase):
    def test_perf_budget_tool_present_and_wired(self) -> None:
        self.assertTrue((ROOT / "tools" / "anhui_web" / "perf_budget.py").is_file())
        release = (ROOT / "tools" / "anhui_web" / "release.py").read_text(encoding="utf-8")
        self.assertIn("perf_budget.py", release)

    def test_release_version_is_canonical(self) -> None:
        # RC3-D1：release 版本必须来自 release.json 单一真源，禁止硬编码任何具体版本号。
        import re as _re

        release = (ROOT / "tools" / "anhui_web" / "release.py").read_text(encoding="utf-8")
        self.assertIn('release.json', release)
        self.assertIsNone(_re.search(r'BUILD_VERSION\s*=\s*"v\d', release), "release.py 不得硬编码版本号")
        release_doc = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
        self.assertEqual(release_doc["release"], "v17.8.6")

    def test_release_checks_template_asset_parity_and_view_smoke(self) -> None:
        import sys as _sys

        _sys.path.insert(0, str(ROOT))
        from tools.anhui_web.release import verify_template_asset_parity

        report = verify_template_asset_parity(SITE)
        self.assertEqual(report["status"], "pass")
        # RC3-D3：palette 退役后模板资产清单变化，parity 全集=13（11 资产 + webmanifest + sw）。
        self.assertGreaterEqual(report["checked"], 13)
        self.assertEqual(report["mismatches"], [])


if __name__ == "__main__":
    unittest.main()
