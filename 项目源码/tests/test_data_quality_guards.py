from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StableIdentityTests(unittest.TestCase):
    def test_stable_job_id_uses_position_identity_not_row_order(self) -> None:
        from tools.anhui_web.data_quality import annotate_position_row, stable_job_id

        first = {
            "exam": "事业编",
            "city": "合肥",
            "code": "400110112001",
            "unit": "国家统计局安徽调查总队",
            "zw": "合肥调查队业务科室四级主任科员",
            "num": 1,
        }
        second = {
            **first,
            "unit": "安徽省地震局",
            "zw": "震害防御处四级主任科员",
        }
        self.assertEqual(stable_job_id("2024", first), stable_job_id("2024", dict(first)))
        self.assertNotEqual(stable_job_id("2024", first), stable_job_id("2024", second))
        self.assertEqual(stable_job_id("2024", first), stable_job_id("2024", {**first, "num": 2}))
        self.assertTrue(stable_job_id("2024", first).startswith("job-2024-"))
        annotated = annotate_position_row("2024", {**first, "zw": ""})
        self.assertEqual(annotated["title_status"], "not_separately_published")
        self.assertEqual(annotated["display_title"], "源表未单列披露")


class ScoreObservationTests(unittest.TestCase):
    def test_zero_and_mixed_scale_scores_are_not_comparable(self) -> None:
        from tools.anhui_web.data_quality import classify_score_observation

        zero = classify_score_observation({"exam": "事业编", "line": 0})
        self.assertEqual(zero["status"], "suspected_sentinel")
        self.assertIsNone(zero["scale_id"])

        syb = classify_score_observation({"exam": "事业编", "line": 215})
        self.assertEqual(syb["status"], "comparable")
        self.assertEqual(syb["scale_id"], "syb_300")

        province = classify_score_observation({"exam": "省考", "line": 128})
        self.assertEqual(province["status"], "incompatible_scale")
        self.assertIsNone(province["scale_id"])

    def test_missing_score_is_explicit_not_zero(self) -> None:
        from tools.anhui_web.data_quality import classify_score_observation

        result = classify_score_observation({"exam": "事业编", "line": None})
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["value"])
        self.assertNotEqual(result["value"], 0)


class CompetitionObservationTests(unittest.TestCase):
    def test_competition_observations_keep_denominators_separate(self) -> None:
        from tools.anhui_web.data_quality import competition_observations

        result = competition_observations({"bm": 80, "adv": 20})
        self.assertEqual(result["registrations"], {"value": 80, "status": "observed"})
        self.assertEqual(result["examinees"], {"value": 20, "status": "observed"})
        self.assertEqual(result["preferred_type"], "examinees")
        self.assertNotIn("competition_base", result)

    def test_missing_denominator_is_not_an_observed_zero(self) -> None:
        from tools.anhui_web.data_quality import competition_observations

        result = competition_observations({"bm": None, "adv": None})
        self.assertIsNone(result["registrations"]["value"])
        self.assertIsNone(result["examinees"]["value"])
        self.assertEqual(result["preferred_type"], None)

    def test_zero_denominator_is_marked_as_a_suspected_sentinel(self) -> None:
        from tools.anhui_web.data_quality import competition_observations

        result = competition_observations({"bm": 0, "adv": 0})
        self.assertEqual(result["registrations"]["status"], "suspected_sentinel")
        self.assertEqual(result["examinees"]["status"], "suspected_sentinel")
        self.assertIsNone(result["preferred_type"])

    def test_rollup_does_not_merge_registration_and_examinee_denominators(self) -> None:
        from tools.anhui_web.build_pages import build_job_metrics

        records = [
            {
                "city": "甲",
                "exam": "省考",
                "recruits": 1,
                "examinees": 100,
                "registrations": 120,
                "competition_base": 100,
                "competition_source": "考试人数",
                "competition_metric_type": "examinees",
            },
            {
                "city": "甲",
                "exam": "省考",
                "recruits": 1,
                "examinees": 0,
                "registrations": 80,
                "competition_base": 80,
                "competition_source": "报名人数",
                "competition_metric_type": "registrations",
            },
        ]
        result = build_job_metrics(records, [{"city": "甲", "jobs": 2, "recruits": 2, "reference": ""}])
        item = result["cities"][0]
        self.assertEqual(item["ratio_status"], "mixed_denominators")
        self.assertFalse(item["ratio_comparable"])
        self.assertEqual(item["competition_metrics"]["examinees"]["base"], 100)
        self.assertEqual(item["competition_metrics"]["registrations"]["base"], 80)

    def test_national_interview_shortlisted_is_a_distinct_metric(self) -> None:
        from tools.anhui_web.build_pages import build_job_metrics

        result = build_job_metrics(
            [{
                "city": "乙",
                "exam": "国考",
                "recruits": 2,
                "examinees": 12,
                "registrations": 90,
                "competition_base": 12,
                "competition_source": "考试人数",
                "competition_metric_type": "interview_shortlisted",
            }],
            [{"city": "乙", "jobs": 1, "recruits": 2, "reference": ""}],
        )
        metric = result["cities"][0]["competition_metrics"]["interview_shortlisted"]
        self.assertEqual(metric["base"], 12)
        self.assertEqual(metric["recruits"], 2)
        self.assertNotIn("examinees", result["cities"][0]["competition_metrics"])

    def test_bundle_normalization_enriches_job_rollups_with_quality_state(self) -> None:
        from tools.anhui_web.unified_cycle_bundle import _normalise_payload

        payload = {
            "allMajors": {"rows": [{"exam": "省考", "city": "甲", "code": "1", "unit": "单位", "zw": "职位", "num": 1}]},
            "records": [
                {"city": "甲", "exam": "省考", "recruits": 1, "examinees": 100, "registrations": 120, "competition_base": 100, "competition_metric_type": "examinees"},
                {"city": "甲", "exam": "省考", "recruits": 1, "examinees": 0, "registrations": 80, "competition_base": 80, "competition_metric_type": "registrations"},
            ],
            "jobs": {
                "cities": [{"city": "甲", "jobs": 2, "recruits": 2, "exam": {"省考": {"jobs": 2, "recruits": 2}}, "competition": {"省考": {"competition_base": 180, "ratio": 0.011}}}],
                "metrics": {"cities": [{"city": "甲", "jobs": 2, "recruits": 2, "exam": {"省考": {"jobs": 2, "recruits": 2}}, "competition": {"省考": {"competition_base": 180, "ratio": 0.011}}}]},
            },
        }
        normalized = _normalise_payload(payload, "2026")
        self.assertTrue(normalized["records"][0]["job_id"].startswith("job-2026-"))
        city = normalized["jobs"]["cities"][0]
        self.assertEqual(city["ratio_status"], "mixed_denominators")
        self.assertFalse(city["ratio_comparable"])
        self.assertEqual(city["competition_metrics"]["examinees"]["base"], 100)
        self.assertEqual(city["competition_metrics"]["registrations"]["base"], 80)

    def test_bundle_normalization_marks_an_entirely_missing_denominator_unavailable(self) -> None:
        from tools.anhui_web.unified_cycle_bundle import _normalise_payload

        payload = {
            "allMajors": {"rows": [{"exam": "省考", "city": "乙", "code": "2", "unit": "单位", "zw": "职位", "num": 1}]},
            "records": [{"city": "乙", "exam": "省考", "recruits": 1, "examinees": None, "registrations": None}],
            "jobs": {"cities": [{"city": "乙", "jobs": 1, "recruits": 1, "exam": {"省考": {"jobs": 1, "recruits": 1}}, "competition": {"省考": {"ratio": 0}}}]},
        }
        normalized = _normalise_payload(payload, "2026")
        city = normalized["jobs"]["cities"][0]
        self.assertEqual(city["ratio_status"], "unavailable")
        self.assertFalse(city["ratio_comparable"])
        self.assertEqual(city["competition"]["省考"]["ratio_status"], "unavailable")


class ScoreMetricsJavascriptTests(unittest.TestCase):
    def test_score_metrics_runtime_rejects_unannotated_rows(self) -> None:
        node = shutil_which_node()
        if node is None:
            self.skipTest("node is not available")
        script = ROOT / "tools" / "anhui_web" / "templates" / "score-metrics.js"
        probe = """
const fs = require('fs');
const vm = require('vm');
const context = { window: {}, console };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context, { filename: process.argv[1] });
const api = context.window.wanyuScoreMetrics;
if (!api || api.fromRecord({}) !== null) process.exit(2);
const row = { score_observation: { status: 'comparable', scale_id: 'syb_300', value: 215 } };
const observed = api.fromRecord(row);
if (!observed || observed.scale_id !== 'syb_300' || !api.isComparable(observed, 'syb_300')) process.exit(3);
if (api.isComparable({ status: 'suspected_sentinel', scale_id: null }, 'syb_300')) process.exit(4);
"""
        result = subprocess.run(
            [node, "-e", probe, str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class RuntimeSafetyTests(unittest.TestCase):
    def test_build_pages_direct_script_entrypoint_resolves_quality_module(self) -> None:
        result = subprocess.run(
            ["python", str(ROOT / "tools" / "anhui_web" / "build_pages.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_scaffold_head_does_not_accumulate_injected_style_blocks(self) -> None:
        from tools.anhui_web.single_file_site import _extract_head

        scaffold = (
            "<head><style data-v12-cycle-style>old cycle</style>"
            "<style data-v12-master-style>old master</style></head>"
        )
        rebuilt = _extract_head(scaffold)
        self.assertEqual(rebuilt.count('data-v12-cycle-style'), 1)
        self.assertEqual(rebuilt.count('data-v12-master-style'), 1)
        self.assertNotIn("old cycle", rebuilt)
        self.assertNotIn("old master", rebuilt)

    def test_cycle_runtime_switches_without_forcing_a_full_reload(self) -> None:
        runtime = (ROOT / "tools" / "anhui_web" / "templates" / "cycle-runtime.js").read_text(encoding="utf-8")
        self.assertNotIn("location.reload()", runtime)

    def test_score_simulator_is_wired_to_the_quality_gate(self) -> None:
        script = (ROOT / "tools" / "anhui_web" / "templates" / "product-score-sim.js").read_text(encoding="utf-8")
        self.assertIn("scoreMetrics.isComparable", script)
        self.assertIn("scoreExcludedCount", script)

    def test_search_substitutes_require_the_same_competition_denominator(self) -> None:
        script = (ROOT / "tools" / "anhui_web" / "templates" / "product-jobs-search.js").read_text(encoding="utf-8")
        self.assertIn("competition_metric_type", script)
        self.assertIn("competitionTypeOfV12(target)", script)

    def test_detail_adapter_surfaces_unpublished_position_title_state(self) -> None:
        script = (ROOT / "tools" / "anhui_web" / "templates" / "product-record-adapter.js").read_text(encoding="utf-8")
        self.assertIn("title_status", script)
        self.assertIn("职位名称", script)

    def test_ranking_runtime_uses_only_comparable_city_ratios(self) -> None:
        script = (ROOT / "tools" / "anhui_web" / "templates" / "product-jobs-ranking.js").read_text(encoding="utf-8")
        self.assertIn("ratio_comparable", script)
        self.assertIn("ratioIsComparable", script)

    def test_postbuild_verifier_checks_quality_annotations(self) -> None:
        script = (ROOT / "tools" / "anhui_web" / "verify_single_file_v12.py").read_text(encoding="utf-8")
        self.assertIn("job_id", script)
        self.assertIn("score_observation", script)
        self.assertIn("competition_observations", script)

    def test_all_ratio_consumers_have_a_comparability_gate(self) -> None:
        core = (ROOT / "tools" / "anhui_web" / "templates" / "product-core.js").read_text(encoding="utf-8")
        detail = (ROOT / "tools" / "anhui_web" / "templates" / "product-jobs-detail.js").read_text(encoding="utf-8")
        decision = (ROOT / "tools" / "anhui_web" / "templates" / "product-decision.js").read_text(encoding="utf-8")
        self.assertIn("competition_metric_type", core)
        self.assertIn("ratio_comparable", detail)
        self.assertIn("ratio_comparable", decision)

    def test_data_dictionary_generator_documents_three_year_quality_contract(self) -> None:
        script = (ROOT / "tools" / "anhui_web" / "gen_data_dict.py").read_text(encoding="utf-8")
        for marker in ("2024", "2025", "2026", "job_id", "score_observation", "competition_observations", "ratio_comparable"):
            self.assertIn(marker, script)

    def test_audit_report_generator_documents_quality_gate_contract(self) -> None:
        script = (ROOT / "tools" / "anhui_web" / "audit_three_years.py").read_text(encoding="utf-8")
        for marker in ("score_observation", "competition_observations", "ratio_comparable", "不可比"):
            self.assertIn(marker, script)


def shutil_which_node() -> str | None:
    import shutil

    return shutil.which("node")


if __name__ == "__main__":
    unittest.main()
