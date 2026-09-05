from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "tools" / "anhui_web" / "templates"
FULL = ROOT.parent / "网站"
LITE = ROOT.parent / "网站-lite"
ASSET = "v17-ui-upgrade.css"


class UiUpgradeContractTests(unittest.TestCase):
    def test_upgrade_asset_is_copied_and_linked_everywhere(self) -> None:
        template_asset = TEMPLATE / ASSET
        self.assertTrue(template_asset.is_file())
        template_bytes = template_asset.read_bytes()
        for site in (FULL, LITE):
            self.assertEqual((site / "assets" / ASSET).read_bytes(), template_bytes, str(site))
            self.assertIn(ASSET, (site / "index.html").read_text(encoding="utf-8"))
        builder = (ROOT / "tools" / "anhui_web" / "build_maintainable_site.py").read_text(encoding="utf-8")
        self.assertIn(ASSET, builder)

    def test_upgrade_asset_is_precached(self) -> None:
        sw = (TEMPLATE / "maintainable-sw.js").read_text(encoding="utf-8")
        self.assertIn(ASSET, sw)
        # 2026-09-05 P0-5/P0-6: 版本断言改单调（>= v30），不再钉死历史版本号
        version = re.search(r"wanyu-shell-v(\d+)", sw)
        self.assertIsNotNone(version)
        self.assertGreaterEqual(int(version.group(1)), 30)
        self.assertRegex(sw, r"v17-tools\.js\?v=[0-9A-Za-z.\-]+")
        self.assertRegex(sw, r"maintainable-site\.js\?v=[0-9A-Za-z.\-]+")

    def test_mobile_navigation_contract(self) -> None:
        js = (TEMPLATE / "maintainable-site.js").read_text(encoding="utf-8")
        for marker in ("renderMobileNav", "maint-mobile-nav", "data-maint-mobile-more-toggle", "data-maint-mobile-more"):
            self.assertIn(marker, js, marker)

    def test_decision_rail_contract(self) -> None:
        js = (TEMPLATE / "maintainable-site.js").read_text(encoding="utf-8")
        for marker in ("ui-search-flow", "缩小范围", "核对原文", "保存或对比"):
            self.assertIn(marker, js, marker)

    def test_visual_system_and_mobile_cards_contract(self) -> None:
        css = (TEMPLATE / ASSET).read_text(encoding="utf-8")
        for marker in ("--ui-ink", "--ui-teal", ".maint-mobile-nav", ".ui-search-flow", ".maint-table--search tbody", ".maint-detail-drawer", "prefers-reduced-motion"):
            self.assertIn(marker, css, marker)

    def test_palette_is_blue_not_green(self) -> None:
        css = (TEMPLATE / ASSET).read_text(encoding="utf-8").lower()
        for marker in ("#3a83f7", "#e5efff", "--ui-blue"):
            self.assertIn(marker, css, marker)
        for marker in ("#2f9a91", "#ddf0ec"):
            self.assertNotIn(marker, css, marker)

    def test_header_is_light_blue_not_dark(self) -> None:
        css = (TEMPLATE / ASSET).read_text(encoding="utf-8").lower()
        self.assertIn("linear-gradient(180deg, #ffffff 0%, #f3f7ff 100%)", css)
        self.assertIn("background: #3a83f7", css)
        self.assertNotIn("background: rgba(15, 29, 51, .96)", css)

    def test_syb_exam_batch_filters_are_clickable_and_data_backed(self) -> None:
        js = (TEMPLATE / "maintainable-site.js").read_text(encoding="utf-8")
        self.assertIn("String(row?.cycle || '') === sub", js)
        self.assertNotIn("const isBatch = currentExam === '事业编' && value !== '';", js)
        builder = (ROOT / "tools" / "anhui_web" / "build_maintainable_site.py").read_text(encoding="utf-8")
        self.assertIn('"cycle",', builder)
        for site in (FULL, LITE):
            for cycle in ("2024", "2025", "2026"):
                payload = json.loads((site / "data" / "cycles" / cycle / "jobs_lite.json").read_text(encoding="utf-8"))
                rows = payload["allMajors"]["rows"]
                counts = Counter(str(row.get("cycle") or "") for row in rows if row.get("exam") == "事业编")
                self.assertGreater(counts["上半年"], 0, f"{site}: {cycle} 上半年联考")
                self.assertGreater(counts["下半年"], 0, f"{site}: {cycle} 下半年联考")

    def test_release_wires_ui_browser_smoke(self) -> None:
        release = (ROOT / "tools" / "anhui_web" / "release.py").read_text(encoding="utf-8")
        self.assertIn("tests/ui_upgrade_browser_smoke.cjs", release)


if __name__ == "__main__":
    unittest.main()
