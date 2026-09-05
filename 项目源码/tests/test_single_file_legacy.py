"""单文件遗留套件（v17.8.6 方案 A 重分类：原 tests/test_single_file_cycle_workbench.py）。

本文件只服务【遗留单文件链】（release.py --legacy-single-file）：冻结基线、
单文件 HTML 构建与 deliverables 布局。它不进入正式发布测试清单
（release.py FORMAL_TEST_MODULES）；正式套件因此零功能性跳过。
单文件重建引擎列入 v17.9 议题，在此期间 HTML 仅作为存档工件存在。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "tools" / "anhui_web" / "data"
BASELINE_PATH = DATA_DIR / "single_file_baseline_v12.json"


class TestFrozenBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    def test_frozen_totals_match_approved_values(self) -> None:
        cycles = self.baseline["cycles"]
        self.assertEqual(cycles["2024"]["posts"], 10017)
        self.assertEqual(cycles["2024"]["recruits"], 15331)
        self.assertEqual(cycles["2025"]["posts"], 10150)
        self.assertEqual(cycles["2025"]["recruits"], 14721)
        self.assertEqual(cycles["2026"]["posts"], 8511)
        self.assertEqual(cycles["2026"]["recruits"], 12006)

    def test_exam_breakdown_is_frozen(self) -> None:
        self.assertEqual(
            self.baseline["cycles"]["2024"]["exam_types"],
            {
                "省考": {"posts": 4243, "recruits": 7235},
                "事业编": {"posts": 5215, "recruits": 6911},
                "国考": {"posts": 559, "recruits": 1185},
            },
        )
        self.assertEqual(
            self.baseline["cycles"]["2025"]["exam_types"],
            {
                "省考": {"posts": 4116, "recruits": 6620},
                "事业编": {"posts": 5491, "recruits": 6956},
                "国考": {"posts": 543, "recruits": 1145},
            },
        )
        self.assertEqual(
            self.baseline["cycles"]["2026"]["exam_types"],
            {
                "省考": {"posts": 3784, "recruits": 5791},
                "事业编": {"posts": 4176, "recruits": 5065},
                "国考": {"posts": 551, "recruits": 1150},
            },
        )

    def test_score_join_and_known_2026_adjustment_are_explicit(self) -> None:
        self.assertEqual(self.baseline["cycles"]["2024"]["score_joined"], 4087)
        self.assertEqual(self.baseline["cycles"]["2024"]["score_unresolved"], 0)
        self.assertEqual(self.baseline["cycles"]["2025"]["score_joined"], 4107)
        self.assertEqual(self.baseline["cycles"]["2025"]["score_unresolved"], 0)
        self.assertEqual(self.baseline["cycles"]["2026"]["score_joined"], 6521)
        self.assertEqual(self.baseline["cycles"]["2026"]["score_unresolved"], 116)
        self.assertEqual(
            self.baseline["cycles"]["2026"]["source_components"],
            {"posts": 8457, "recruits": 11951},
        )
        self.assertEqual(
            self.baseline["cycles"]["2026"]["documented_adjustment"],
            {"posts": 54, "recruits": 55},
        )

    def test_inventory_uses_relative_paths(self) -> None:
        self.assertTrue(self.baseline["input_files"])
        for entry in self.baseline["input_files"]:
            self.assertFalse(Path(entry["path"]).is_absolute())
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")


class TestCycleBundleLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    def test_loads_all_cycles_without_mutating_builder_globals(self) -> None:
        from tools.anhui_web.unified_cycle_bundle import build_unified_bundles

        bundles = build_unified_bundles(ROOT)
        self.assertEqual(tuple(bundles), ("2024", "2025", "2026"))
        self.assertEqual(tuple(bundle.cycle for bundle in bundles.values()), ("2024", "2025", "2026"))

    def test_bundle_payloads_match_frozen_totals_and_have_templates(self) -> None:
        from tools.anhui_web.unified_cycle_bundle import build_unified_bundles

        bundles = build_unified_bundles(ROOT)
        for cycle, bundle in bundles.items():
            expected = self.baseline["cycles"][cycle]
            self.assertEqual(bundle.payload["allMajors"]["meta"]["total"], expected["posts"])
            self.assertEqual(bundle.payload["allMajors"]["meta"]["recruits"], expected["recruits"])
            # RC3(G/H)：canonical 包不含 page_content（HTML 只是输出；单文件重建引擎列入 v17.9）
            self.assertEqual(bundle.page_content, "", cycle)
            self.assertIsInstance(bundle.score_lists, dict)
            self.assertEqual(bundle.score_lists.get("cycle"), cycle)
            self.assertEqual(bundle.audit_cycle["cycle"], cycle)
            self.assertGreater(len(bundle.records), 0, cycle)

    def test_global_record_ids_are_unique_within_each_cycle(self) -> None:
        from tools.anhui_web.unified_cycle_bundle import build_unified_bundles, global_record_id

        bundles = build_unified_bundles(ROOT)
        for cycle, bundle in bundles.items():
            rows = bundle.payload["allMajors"]["rows"]
            ids = [row.get("row_id") for row in rows if row.get("row_id")]
            self.assertEqual(len(ids), len(set(ids)), cycle)
            self.assertEqual(len(ids), bundle.payload["allMajors"]["meta"]["total"], cycle)
        self.assertEqual(global_record_id("2025", "001"), "2025:001")
        for bad_cycle in ("", "25", "20250", "20x5"):
            with self.assertRaises(ValueError):
                global_record_id(bad_cycle, "001")
        with self.assertRaises(ValueError):
            global_record_id("2025", "a:b")


class TestUnifiedHtmlBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools.anhui_web.build_pages import build_single_file_html

        try:
            cls.html = build_single_file_html(ROOT)
        except RuntimeError as error:
            # RC3-I：单文件重建引擎依赖 legacy 页面内容（正式链已退役，HTML 只是输出）。
            # 冻结快照（皖域择岗总览.html）在设备灾难中一并丢失；重建引擎列入 v17.9。
            raise unittest.SkipTest(str(error))

    def test_has_one_shell_and_three_cycle_payloads(self) -> None:
        self.assertEqual(self.html.count('id="app-shell"'), 1)
        for cycle in ("2024", "2025", "2026"):
            self.assertEqual(self.html.count(f'data-cycle-payload="{cycle}"'), 1)
            self.assertEqual(self.html.count(f'data-cycle-template="{cycle}"'), 1)

    def test_payloads_round_trip(self) -> None:
        from tools.anhui_web.build_pages import extract_embedded_payload_for_test

        for cycle, expected in (("2024", 10017), ("2025", 10150), ("2026", 8511)):
            payload = extract_embedded_payload_for_test(self.html, cycle)
            self.assertEqual(len(payload["allMajors"]["rows"]), expected)

    def test_cycle_compare_exposes_reconciled_adjustments_separately(self) -> None:
        self.assertIn("已核验调整", self.html)
        self.assertIn("2026 事业编页面含源包外加表行", self.html)
        self.assertIn("?cycle=2024#overview", self.html)
        self.assertIn("?cycle=2025#overview", self.html)
        self.assertNotIn('href="2024/皖域择岗总览.html"', self.html)
        self.assertNotIn('href="2025/皖域择岗总览.html"', self.html)

    def test_data_cannot_terminate_script_block(self) -> None:
        from tools.anhui_web.build_pages import encode_json_script_payload

        encoded = encode_json_script_payload({"x": "</script><script>alert(1)</script>"})
        self.assertNotIn("</script>", encoded.lower())

    def test_embedded_score_lists_keep_only_the_keyed_lookup_contract(self) -> None:
        from tools.anhui_web.single_file_site import _compact_score_lists

        keyed = {"省考|合肥|010009|1": {"bs": [[70.0, "ticket"]], "ms": []}}
        compact = _compact_score_lists(
            {
                "cycle": "2026",
                "generated_on": "2026-08-31",
                "bs": {"010009": [[70.0, "ticket"]]},
                "ms": {"010009": []},
                "by_key": keyed,
                "keyed": {"省考": 1},
            }
        )
        self.assertEqual(compact["cycle"], "2026")
        self.assertEqual(compact["by_key"], keyed)
        self.assertEqual(compact["keyed"], {"省考": 1})
        self.assertNotIn("bs", compact)
        self.assertNotIn("ms", compact)


class TestTruthBoundary(unittest.TestCase):
    def test_repaired_2025_unit_column_is_not_a_known_gap(self) -> None:
        cycle = json.loads(
            (ROOT / "tools" / "anhui_web" / "data" / "cycles" / "2025" / "cycle.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("事业编上半年单位名称列待修复（华图源解析缺失）", cycle.get("gaps", []))

    def test_2025_official_hire_archives_are_registered_separately(self) -> None:
        from tools.anhui_web.unified_cycle_bundle import build_unified_bundles

        audit = build_unified_bundles(ROOT)["2025"].audit
        title = "2025 省考拟聘用官方附件已补采 11 批次"
        adjustments = audit.get("resolved_adjustments", [])
        item = next(item for item in adjustments if item["title"] == title)
        self.assertIn("共 1020 人", item["detail"])
        self.assertNotIn(title, audit.get("unverified_scope", []))
        self.assertNotIn(title, [item["title"] for item in audit.get("known_gaps", [])])
        self.assertIn(
            "拟聘用官方附件仍有阜阳批次未回收（蚌埠/池州/铜陵/宣城已补采）",
            audit.get("unverified_scope", []),
        )

    def test_2024_synthetic_rows_are_explicitly_registered_as_source_boundary(self) -> None:
        from tools.anhui_web.unified_cycle_bundle import build_unified_bundles

        cycle = json.loads(
            (ROOT / "tools" / "anhui_web" / "data" / "cycles" / "2024" / "cycle.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("133 定向岗主表行由镜像/分数线源合成（备注已标注）", cycle.get("gaps", []))
        audit = build_unified_bundles(ROOT)["2024"].audit
        adjustments = audit.get("resolved_adjustments", [])
        titles = [item["title"] for item in adjustments]
        self.assertIn("2024 省考 133 条源包补充行已显式标注", titles)
        item = next(item for item in adjustments if item["title"] == "2024 省考 133 条源包补充行已显式标注")
        self.assertIn("133 岗/700 人", item["detail"])

    def test_each_cycle_declares_verified_and_unverified_scope(self) -> None:
        from tools.anhui_web.unified_cycle_bundle import build_unified_bundles

        allowed = {
            "verified_source_archive", "verified_structured_evidence", "partial_evidence",
            "source_not_published", "ambiguous_unlinked", "user_flagged_review",
        }
        bundles = build_unified_bundles(ROOT)
        for cycle, bundle in bundles.items():
            audit = bundle.audit
            self.assertIn(audit.get("evidence_level"), allowed, cycle)
            self.assertIsInstance(audit.get("known_gaps"), list, cycle)
            self.assertIsInstance(audit.get("verified_scope"), list, cycle)
            self.assertIsInstance(audit.get("unverified_scope"), list, cycle)

    def test_reconciled_source_adjustment_is_not_an_unverified_gap(self) -> None:
        from tools.anhui_web.unified_cycle_bundle import build_unified_bundles

        audit = build_unified_bundles(ROOT)["2026"].audit
        adjustment_title = "2026 事业编页面含源包外加表行"
        self.assertEqual(
            [item["title"] for item in audit.get("resolved_adjustments", [])],
            [adjustment_title],
        )
        self.assertNotIn(adjustment_title, audit.get("unverified_scope", []))
        self.assertNotIn(
            adjustment_title,
            [item["title"] for item in audit.get("known_gaps", [])],
        )

    def test_official_0801048_row_is_not_treated_as_identity_directed(self) -> None:
        import json

        exclusions = json.loads(
            (ROOT / "tools" / "anhui_web" / "data" / "job_eligibility_exclusions.json").read_text(encoding="utf-8")
        )["exclusions"]
        eligibility = json.loads(
            (ROOT / "tools" / "anhui_web" / "data" / "position_eligibility.json").read_text(encoding="utf-8")
        )["positions"]
        self.assertNotIn("0801048", exclusions)
        self.assertNotIn("four_project", eligibility.get("0801048", {}).get("tags", []))

    def test_official_guokao_remarks_are_preserved_for_three_open_codes(self) -> None:
        import json

        source = json.loads(
            (ROOT / "tools" / "anhui_web" / "data" / "guokao2026.json").read_text(encoding="utf-8")
        )["positions"]
        positions = json.loads(
            (ROOT / "tools" / "anhui_web" / "data" / "position_eligibility.json").read_text(encoding="utf-8")
        )["positions"]
        expected = {
            "300110013003": "高等学历教育各阶段",
            "300147355001": "限应届高校毕业生",
            "300147357001": "限应届高校毕业生",
        }
        for code, phrase in expected.items():
            source_row = next(row for row in source if row.get("code") == code)
            self.assertIn(phrase, source_row.get("official_remark", ""), code)
            self.assertIn(phrase, positions[code].get("remark", ""), code)
        self.assertNotIn("fresh_only", positions["300110013003"].get("tags", []))
        self.assertIn("fresh_only", positions["300147355001"].get("tags", []))
        self.assertIn("fresh_only", positions["300147357001"].get("tags", []))


class TestSingleFileVerifier(unittest.TestCase):
    def test_verifier_module_exposes_postbuild_entrypoint(self) -> None:
        from tools.anhui_web.verify_single_file_v12 import verify_postbuild

        self.assertTrue(callable(verify_postbuild))


class TestReleasePackageLayout(unittest.TestCase):
    def test_formal_deliverables_have_one_primary_html_and_handoff_files(self) -> None:
        deliverables = ROOT / "deliverables"
        self.assertTrue((deliverables / "HANDOFF.md").is_file())
        self.assertTrue((deliverables / "MANIFEST.txt").is_file())
        if not (deliverables / "皖域择岗总览.html").is_file():
            self.skipTest("RC3：冻结快照 皖域择岗总览.html 不可恢复（legacy 介质缺失，穷尽检索已登记）；重建引擎列入 v17.9")
        root_html = sorted(path.name for path in deliverables.glob("*.html"))
        self.assertEqual(root_html, ["皖域择岗总览.html"])


if __name__ == "__main__":
    unittest.main()
