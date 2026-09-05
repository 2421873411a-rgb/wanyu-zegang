# -*- coding: utf-8 -*-
"""RC3-Q：文档门禁——README 不再抄关键数字，current-status 与真源逐字一致。"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent


class DocTruthGateTests(unittest.TestCase):
    def test_current_status_matches_truth_source(self):
        result = subprocess.run(
            [sys.executable, "tools/anhui_web/generate_status_doc.py", "--check"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_readme_carries_current_release_and_no_stale_claims(self):
        readme = (WORKSPACE / "README_先看这里.md").read_text(encoding="utf-8")
        release = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
        self.assertIn(release["release"], readme, "README 必须携带当前 release 字符串")
        for stale in ("116 条成绩仍待", '"v17.6.4"', "8,511 岗 / 12,006 人", "8511 个岗位（2026 口径）"):
            self.assertNotIn(stale, readme, f"README 含过期表述：{stale}")
        self.assertIn("current-status.md", readme, "README 必须引用自动生成的状态文档")


if __name__ == "__main__":
    unittest.main()
