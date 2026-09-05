from __future__ import annotations

import unittest
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V14BaselineTests(unittest.TestCase):
    def test_v13_4_baseline_contains_verified_cycle_totals(self) -> None:
        from tools.anhui_web.v14_baseline import load_baseline

        baseline = load_baseline(ROOT / "tools/anhui_web/data/v13_4_baseline.json")
        self.assertEqual(baseline["release"], "v13.4")
        self.assertEqual(
            baseline["cycles"],
            {
                "2024": {"posts": 10017, "recruits": 15331, "score_unresolved": 0},
                "2025": {"posts": 10150, "recruits": 14721, "score_unresolved": 0},
                "2026": {"posts": 8511, "recruits": 12006, "score_unresolved": 116},
            },
        )
        self.assertEqual(
            baseline["summary"],
            {"posts": 28678, "recruits": 42058, "gaps": 8, "score_unresolved": 116},
        )

    def test_snapshot_site_reads_current_manifest_and_audit(self) -> None:
        from tools.anhui_web.v14_baseline import snapshot_site

        snapshot = snapshot_site(ROOT)
        # RC3：断言改为“快照与 release 单一真源 + 当前部署树一致”（不再钉历史版本/旧模块集）。
        release_doc = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot["release"], release_doc["release"])
        self.assertEqual(snapshot["summary"], {"posts": 28678, "recruits": 42058, "gaps": 7, "score_unresolved": 0})
        self.assertEqual(set(snapshot["cycles"]), {"2024", "2025", "2026"})
        self.assertNotIn("scores", snapshot["cycles"]["2026"]["modules"])
        self.assertIn("jobs_lite", snapshot["cycles"]["2026"]["modules"])


if __name__ == "__main__":
    unittest.main()
