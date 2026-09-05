from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MaintainableSiteContractTests(unittest.TestCase):
    # RC3：overview meta = active 口径（wanyu-metrics/v1）；raw 事实由 verifier 单独把守
    CYCLE_EXPECT = {
        "2024": (10017, 15331),
        "2025": (10150, 14721),
        "2026": (8401, 11883),
    }

    def test_external_build_keeps_job_rows_out_of_html_and_versions_each_cycle(self) -> None:
        from tools.anhui_web.build_maintainable_site import build_maintainable_site

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "maintainable"
            manifest = build_maintainable_site(ROOT, output)
            index = (output / "index.html").read_text(encoding="utf-8")
            self.assertNotIn("data-cycle-payload", index)
            self.assertLess(len(index), 100_000)
            self.assertIn("assets/maintainable-user-store.js", index)
            self.assertIn("assets/maintainable-data.js", index)
            self.assertTrue((output / "assets" / "maintainable-user-store.js").is_file())
            self.assertTrue((output / "assets" / "maintainable-data.js").is_file())
            self.assertEqual(manifest["default_cycle"], "2026")
            self.assertEqual([item["cycle"] for item in manifest["cycles"]], ["2024", "2025", "2026"])
            for cycle, (posts, recruits) in self.CYCLE_EXPECT.items():
                item = next(entry for entry in manifest["cycles"] if entry["cycle"] == cycle)
                data_path = output / item["data"]
                payload = json.loads(data_path.read_text(encoding="utf-8"))
                meta = payload["allMajors"]["meta"]
                self.assertEqual((meta["total"], meta["recruits"]), (posts, recruits))
                self.assertEqual(
                    hashlib.sha256(data_path.read_bytes()).hexdigest(),
                    item["sha256"],
                )

    def test_external_build_splits_cycle_modules_and_writes_global_audit_index(self) -> None:
        from tools.anhui_web.build_maintainable_site import build_maintainable_site

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "maintainable"
            manifest = build_maintainable_site(ROOT, output)
            self.assertEqual(manifest["map"]["data"], "data/map/anhui.json")
            map_path = output / manifest["map"]["data"]
            map_payload = json.loads(map_path.read_text(encoding="utf-8"))
            self.assertEqual(map_payload["schema"], "wanyu-maintainable-map/v1")
            self.assertEqual(map_payload["feature_count"], 16)
            self.assertEqual(hashlib.sha256(map_path.read_bytes()).hexdigest(), manifest["map"]["sha256"])
            audit_path = output / manifest["audit"]["data"]
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertEqual(audit["schema"], "wanyu-maintainable-audit/v1")
            self.assertEqual([item["cycle"] for item in audit["cycles"]], ["2024", "2025", "2026"])
            # RC3：审计 summary=raw 口径；116 已进 resolution_history（open=0）
            self.assertEqual(audit["summary"]["post_count"], 28678)
            self.assertEqual(audit["summary"]["recruit_count"], 42058)
            self.assertEqual(audit["summary"]["gap_count"], 7)
            self.assertEqual(audit["summary"]["unresolved_score_count"], 0)
            self.assertEqual(audit["summary"]["active_post_count"], 28568)
            self.assertEqual(
                hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                manifest["audit"]["sha256"],
            )
            for item in manifest["cycles"]:
                # RC3：palette 退役；major_index 三周期原生；req_fields 2026 精选输入
                expected_modules = {"overview", "jobs", "jobs_lite", "catalog", "positions", "changes", "audit", "derived", "major_city", "major_index"}
                if str(item["cycle"]) == "2026":
                    expected_modules.add("req_fields")
                self.assertEqual(set(item["modules"]), expected_modules)
                self.assertEqual(item["data"], item["modules"]["jobs"]["data"])
                module_payloads = {
                    name: json.loads((output / entry["data"]).read_text(encoding="utf-8"))
                    for name, entry in item["modules"].items()
                }
                for name, entry in item["modules"].items():
                    path = output / entry["data"]
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"], name)
                self.assertIn("allMajors", module_payloads["jobs"])
                # RC3：jobs.json 保留 raw 行（审计真源）→ 行数=raw_posts；positions/lite 等用户模块=active。
                self.assertEqual(len(module_payloads["jobs"]["allMajors"]["rows"]), item["raw_posts"])
                self.assertEqual(len(module_payloads["jobs_lite"]["allMajors"]["rows"]), item["active_posts"])
                self.assertNotIn("rows", module_payloads["overview"].get("allMajors", {}))
                self.assertNotIn("rows", module_payloads["audit"].get("allMajors", {}))
                self.assertIn("known_gaps", module_payloads["audit"]["audit"])
                self.assertEqual(module_payloads["positions"]["row_count"], item["posts"])
                self.assertEqual(len(module_payloads["positions"]["rows"]), item["posts"])
                self.assertIn("source", module_payloads["positions"]["rows"][0])
                self.assertEqual(module_payloads["changes"]["target_cycle"], item["cycle"])
                self.assertIn("matching_policy", module_payloads["changes"])
                score_archive = json.loads((output / "archive" / "scores" / f"{item['cycle']}.json").read_text(encoding="utf-8"))
                self.assertEqual(score_archive["cycle"], item["cycle"])
                self.assertEqual(score_archive["schema"], "wanyu-maintainable-scores/v1")
                self.assertIn("by_key", score_archive)

    def test_release_and_handoff_describe_modular_maintenance_and_audit_center(self) -> None:
        release = (ROOT / "tools" / "anhui_web" / "release.py").read_text(encoding="utf-8")
        handoff = (ROOT / "deliverables" / "HANDOFF.md").read_text(encoding="utf-8")
        for marker in ("data/audit/three-year.json", "overview.json", "jobs.json", "audit.json"):
            self.assertIn(marker, release + handoff)
        self.assertIn("verify_maintainable_site.py", release)
        self.assertIn("数据审计", handoff)

    def test_disk_verifier_reconciles_every_external_module(self) -> None:
        from tools.anhui_web.verify_maintainable_site import verify_maintainable_site

        # RC3：磁盘校验器对齐部署树（deliverables 镜像随 RC3 构建图退役）
        report = verify_maintainable_site(ROOT.parent / "网站")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["failed"], 0)
        self.assertGreaterEqual(report["passed"], 20)
        self.assertTrue(any(item["id"] == "2026.scores_archive.present" for item in report["checks"]))
        self.assertTrue(any(item["id"] == "review_queue.sha256" for item in report["checks"]))

    def test_v14_manifest_contains_derived_catalog_module(self) -> None:
        from tools.anhui_web.build_maintainable_site import build_maintainable_site

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "maintainable"
            manifest = build_maintainable_site(ROOT, output)
            for item in manifest["cycles"]:
                self.assertIn("catalog", item["modules"])
                catalog_path = output / item["modules"]["catalog"]["data"]
                catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
                self.assertEqual(catalog["cycle"], item["cycle"])
                self.assertTrue(catalog["majors"])
                self.assertTrue(all(any(char.isalpha() or "\u4e00" <= char <= "\u9fff" for char in value) for value in catalog["majors"]))
                self.assertNotIn("rows", catalog)

    def test_v14_manifest_contains_detailed_review_queue(self) -> None:
        from tools.anhui_web.build_maintainable_site import build_maintainable_site

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "maintainable"
            manifest = build_maintainable_site(ROOT, output)
            self.assertIn("review_queue", manifest)
            queue_path = output / manifest["review_queue"]["data"]
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            self.assertEqual(queue["schema"], "wanyu-maintainable-review-queue/v1")
            self.assertEqual(queue["summary"]["public_boundary_count"], 7)  # RC3：116 迁 resolved_history，公开边界 8→7
            # RC3：116 全部归属 → open unresolved=0；resolved_history 记 116/116/0。
            self.assertEqual(queue["summary"]["unresolved_score_count"], 0)
            self.assertEqual(queue["summary"]["resolved_score_count"], 116)
            self.assertGreaterEqual(queue["summary"]["event_count"], 7)

    def test_jobs_ranking_markup_exposes_major_filter_hooks(self) -> None:
        from tools.anhui_web import build_pages

        rendered = build_pages._jobs_ranking_content(
            {
                "cities": [
                    {"city": "合肥", "jobs": 2, "recruits": 2, "share": 50, "ratio": 0.1},
                    {"city": "芜湖", "jobs": 2, "recruits": 2, "share": 50, "ratio": 0.1},
                ],
                "all_records": [],
            }
        )
        for marker in (
            'id="ranking-major-input"',
            'id="ranking-major-options"',
            "data-ranking-major",
            'id="ranking-filter-count"',
        ):
            self.assertIn(marker, rendered)

    def test_release_pipeline_invokes_external_site_builder(self) -> None:
        # v17.8.6：release.py 编排交由共享流水线；构建入口 = release_pipeline.build_site
        # （import build_maintainable_site 的 assemble_maintainable_site）。
        release = (ROOT / "tools" / "anhui_web" / "release.py").read_text(encoding="utf-8")
        pipeline = (ROOT / "tools" / "anhui_web" / "release_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("run_pipeline", release)
        self.assertIn("外置 JSON 维护站", pipeline + release)
        self.assertIn("build_maintainable_site", pipeline)


if __name__ == "__main__":
    unittest.main()
