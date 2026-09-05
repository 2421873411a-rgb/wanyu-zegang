from __future__ import annotations

import unittest
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.anhui_web import audit_three_years


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "tools" / "anhui_web" / "data"


class ThreeYearAuditContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary = audit_three_years.build_audit(ROOT, OUTPUT_DIR)

    def test_summary_has_three_cycles_and_baselines(self) -> None:
        cycles = self.summary["cycles"]
        self.assertEqual([item["cycle"] for item in cycles], ["2024", "2025", "2026"])
        self.assertEqual(
            [(item["posts"], item["recruits"]) for item in cycles],
            [(10017, 15331), (10150, 14721), (8511, 12006)],
        )

    def test_statuses_use_only_explicit_evidence_states(self) -> None:
        allowed = {"verified", "source_bundle", "unpublished_or_unavailable", "ambiguous_join"}
        self.assertEqual(set(self.summary["status_definitions"]), allowed)
        for item in self.summary["cycles"]:
            self.assertTrue(set(item["statuses"]).issubset(allowed))

    def test_known_unresolved_2026_join_is_resolved_history(self) -> None:
        # RC3：116 撞码已全部归属（公告来源定市）——active gap 归零、进入 resolution_history。
        current = next(item for item in self.summary["cycles"] if item["cycle"] == "2026")
        self.assertEqual(current["coverage"]["score_unresolved"], 0)
        self.assertEqual(current["score_lists"]["unresolved"], 0)
        self.assertEqual(current["score_lists"]["resolved"], 116)
        history = next((r for r in current.get("resolution_history") or [] if r.get("kind") == "ambiguous_join"), None)
        self.assertIsNotNone(history)
        self.assertEqual((history["original_count"], history["resolved_count"], history["remaining_count"]), (116, 116, 0))
        self.assertFalse(any("无法唯一匹配" in str(g.get("title") or "") for g in current["gaps"]))

    def test_internal_cross_layer_checks_are_green(self) -> None:
        self.assertGreater(self.summary["checks"]["passed"], 0)
        self.assertEqual(self.summary["checks"]["failed"], 0)

    def test_audit_build_stamp_follows_source_snapshot(self) -> None:
        self.assertEqual(self.summary["generated_on"], "2026-08-31")

    def test_cli_is_safe_when_windows_console_uses_gbk(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "gbk"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "anhui_web" / "audit_three_years.py"),
                    "--root", str(ROOT),
                    "--output-json", str(folder / "审计摘要.json"),
                    "--report", str(folder / "三年审计报告\ue178.md"),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                check=False,
            )
            stdout = result.stdout.decode("utf-8", errors="replace")
            stderr = result.stderr.decode("utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, stdout + stderr)
        self.assertIn("three-year audit", stdout)


if __name__ == "__main__":
    unittest.main()
