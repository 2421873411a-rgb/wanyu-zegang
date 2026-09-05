from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V13VisualContractTests(unittest.TestCase):
    def test_visual_layer_exists_with_archive_tokens_and_signature_components(self) -> None:
        css_path = ROOT / "tools" / "anhui_web" / "templates" / "ui-v13.css"
        self.assertTrue(css_path.is_file(), f"missing visual layer: {css_path}")
        css = css_path.read_text(encoding="utf-8")
        for marker in (
            "/* v13 visual system: evidence archive desk */",
            "--archive-ink",
            "--archive-paper",
            "--archive-vermilion",
            ".master-hero__stamp",
            ".master-filterbar",
            ".master-evidence-rail",
            "@media (max-width: 760px)",
        ):
            self.assertIn(marker, css)

    def test_single_file_injects_one_current_v13_style_block(self) -> None:
        from tools.anhui_web.single_file_site import _extract_head

        scaffold = (
            "<head>"
            "<style data-v13-visual-style>old visual</style>"
            "</head>"
        )
        rebuilt = _extract_head(scaffold)
        self.assertEqual(rebuilt.count("data-v13-visual-style"), 1)
        self.assertNotIn("old visual", rebuilt)

    def test_master_hero_refresh_surfaces_the_three_year_evidence_spine(self) -> None:
        from tools.anhui_web.single_file_site import _refresh_master_hero

        source = '<section class="master-hero"><div>old hero</div></section>'
        refreshed = _refresh_master_hero(source)
        self.assertIn("master-evidence-rail", refreshed)
        self.assertIn("2024—26", refreshed)
        self.assertNotIn("old hero", refreshed)

    def test_visual_layer_has_focus_and_reduced_motion_guards(self) -> None:
        css = (ROOT / "tools" / "anhui_web" / "templates" / "ui-v13.css").read_text(encoding="utf-8")
        self.assertIn(":focus-visible", css)
        self.assertIn("prefers-reduced-motion: reduce", css)

    def test_visual_calibration_restores_cool_research_desk(self) -> None:
        css = (ROOT / "tools" / "anhui_web" / "templates" / "ui-v13.css").read_text(encoding="utf-8")
        for marker in (
            "/* v13.1 visual calibration: cool research desk */",
            "--research-blue",
            "--research-canvas",
            "background: var(--research-canvas)",
            "font-family: var(--research-sans)",
        ):
            self.assertIn(marker, css)

    def test_light_assistant_shell_and_human_major_options_are_contractual(self) -> None:
        css = (ROOT / "tools" / "anhui_web" / "templates" / "ui-v13.css").read_text(encoding="utf-8")
        product_all = (ROOT / "tools" / "anhui_web" / "templates" / "product-all.js").read_text(encoding="utf-8")
        for marker in (
            "/* v13.3 visual direction: a light assistant workspace",
            "--research-header: #f7f9fc",
            "background: #f7f9fc",
            ".wy-main-nav",
        ):
            self.assertIn(marker, css)
        for marker in ("cleanMajorOption", "isHumanMajor", "majorOptions", "mapList.innerHTML"):
            self.assertIn(marker, product_all)

    def test_cycle_runtime_ignores_hash_only_popstate(self) -> None:
        runtime = (ROOT / "tools" / "anhui_web" / "templates" / "cycle-runtime.js").read_text(encoding="utf-8")
        self.assertIn("/* v13: hash-only navigation must not remount a cycle */", runtime)
        self.assertIn("if (String(queryCycle()) === String(active)) return;", runtime)

    def test_cycle_runtime_lazily_reads_app_source_after_parser_reaches_it(self) -> None:
        runtime = (ROOT / "tools" / "anhui_web" / "templates" / "cycle-runtime.js").read_text(encoding="utf-8")
        self.assertIn("const appSourceForRun = () => document.querySelector('script[data-v12-app]')?.textContent || appSource;", runtime)
        self.assertIn("const source = appSourceForRun();", runtime)


if __name__ == "__main__":
    unittest.main()
