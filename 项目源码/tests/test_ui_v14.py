from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UiV14ContractTests(unittest.TestCase):
    def test_maintainable_shell_loads_design_tokens_and_data_store(self) -> None:
        from tools.anhui_web.build_maintainable_site import _index_html

        html = _index_html()
        self.assertIn('assets/maintainable-tokens.css', html)
        self.assertIn('assets/maintainable-data.js', html)
        self.assertIn('data-maintain-view="help"', html)
        self.assertIn('data-maintain-view="changelog"', html)

    def test_design_tokens_cover_context_surface_text_status_and_focus(self) -> None:
        path = ROOT / "tools" / "anhui_web" / "templates" / "maintainable-tokens.css"
        text = path.read_text(encoding="utf-8")
        for token in ("--bg-context", "--bg-surface", "--text-strong", "--text-muted", "--status-warning", "--focus-ring"):
            self.assertIn(token, text)
        self.assertNotIn("#0b1220", text.lower())

    def test_ui_has_detail_compare_review_saved_and_pagination_hooks(self) -> None:
        css = (ROOT / "tools" / "anhui_web" / "templates" / "maintainable-site.css").read_text(encoding="utf-8")
        js = (ROOT / "tools" / "anhui_web" / "templates" / "maintainable-site.js").read_text(encoding="utf-8")
        for marker in ("maint-detail-drawer", "change-card", "review-item", "saved-item", "maint-pagination"):
            self.assertIn(marker, css)
        for marker in ("data-maint-change-summary", "data-maint-pagination", "WanyuDataStore", "如何判断一个岗位", "state.manifest?.release"):
            self.assertIn(marker, js)

    def test_primary_surface_uses_light_blue_instead_of_teal(self) -> None:
        tokens = (ROOT / "tools" / "anhui_web" / "templates" / "maintainable-tokens.css").read_text(encoding="utf-8")
        css = (ROOT / "tools" / "anhui_web" / "templates" / "maintainable-site.css").read_text(encoding="utf-8")
        js = (ROOT / "tools" / "anhui_web" / "templates" / "maintainable-site.js").read_text(encoding="utf-8")
        self.assertIn("--accent-primary: #3a83f7", tokens)
        self.assertIn("--accent-primary-soft: #eef5ff", tokens)
        self.assertIn("--accent-teal: #b7d1f8", tokens)
        self.assertIn("/* v14.3: reference blue calibration", css)
        self.assertIn("background:rgba(251,253,255,.98)", css)
        self.assertIn("var(--map-fill,#e7f0ff)", css)
        # v15.0 起 JS 不再硬编码主色，地图色阶改为引用主题 token。
        self.assertIn("var(--map-stop-5)", js)
        self.assertNotIn("#5e88b8", css)
        self.assertNotIn("#5e88b8", js)

    def test_user_flow_contract_exposes_visible_filters_and_safe_source_date(self) -> None:
        js = (ROOT / "tools" / "anhui_web" / "templates" / "maintainable-site.js").read_text(encoding="utf-8")
        css = (ROOT / "tools" / "anhui_web" / "templates" / "maintainable-site.css").read_text(encoding="utf-8")
        for marker in (
            "data-maint-active-filter",
            "data-maint-clear-search",
            "data-maint-position-compare",
            "major_options_mode",
            "source.observed_at || '未提供'",
        ):
            self.assertIn(marker, js)
        self.assertIn("overflow-wrap:anywhere", css)
        self.assertNotIn("2000-01-01", js)


if __name__ == "__main__":
    unittest.main()
