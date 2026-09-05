from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseV14ContractTests(unittest.TestCase):
    def test_release_script_runs_v14_gate_chain(self) -> None:
        source = (ROOT / "tools" / "anhui_web" / "release.py").read_text(encoding="utf-8")
        for marker in ("v14.4", "v16.2.1", "verify_maintainable_site.py", "maintainable_browser_smoke.js", "three_year_audit", "package"):
            self.assertIn(marker, source)

    def test_handoff_and_update_docs_cover_external_modules_and_rollback(self) -> None:
        handoff = (ROOT / "deliverables" / "HANDOFF.md").read_text(encoding="utf-8")
        update_doc = (ROOT / "docs" / "数据更新操作手册.md").read_text(encoding="utf-8")
        architecture = (ROOT / "docs" / "长期维护网站架构方案_v2.md").read_text(encoding="utf-8")
        changelog = (ROOT / "deliverables" / "CHANGELOG.md").read_text(encoding="utf-8")
        for text in (handoff, update_doc, architecture, changelog):
            self.assertIn("scores.json", text)
            self.assertIn("changes.json", text)
            self.assertIn("review-queue.json", text)
        self.assertIn("回滚", handoff + update_doc + architecture)
        self.assertIn("v14.4", handoff + architecture + changelog)
        self.assertIn("v15.0", handoff + changelog)

    def test_manifest_has_v14_release_and_split_modules(self) -> None:
        import json

        manifest = json.loads((ROOT.parent / "网站" / "data" / "site-manifest.json").read_text(encoding="utf-8"))
        # RC3-D1：release 单一真源=release.json（本测试改为“manifest 与真源一致”）。
        release_doc = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["release"], release_doc["release"])
        self.assertEqual(manifest["schema"], "wanyu-maintainable-site/v3")
        self.assertIn("metrics_contract", manifest)
        self.assertIn("review_queue", manifest)
        self.assertTrue(all("scores" not in item["modules"] and "changes" in item["modules"] for item in manifest["cycles"]))


if __name__ == "__main__":
    unittest.main()
