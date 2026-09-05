from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "tools" / "anhui_web" / "templates"


def _block(text: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{(.*?)\}", text, re.S)
    return match.group(1) if match else ""


def _decl(block: str, name: str) -> str:
    match = re.search(re.escape(name) + r"\s*:\s*([^;]+);", block)
    return match.group(1).strip() if match else ""


def _hex_value(block: str, name: str) -> str:
    match = re.search(re.escape(name) + r"\s*:\s*(#[0-9a-fA-F]{6})", block)
    return match.group(1) if match else ""


def _lum(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ratio(fg: str, bg: str) -> float:
    a, b = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


class UiV15ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tokens = (TEMPLATES / "maintainable-tokens.css").read_text(encoding="utf-8")
        self.css = (TEMPLATES / "maintainable-site.css").read_text(encoding="utf-8")
        self.js = (TEMPLATES / "maintainable-site.js").read_text(encoding="utf-8")
        from tools.anhui_web.build_maintainable_site import _index_html

        self.html = _index_html()

    def test_dual_theme_tokens_exist(self) -> None:
        for token in (
            "--grad-display", "--accent-2", "--pos", "--warn", "--unknown", "--danger",
            "--font-display", "--dur-fast", "--dur-med", "--dur-slow", "--ease",
            "--glass-bg", "--radius-pill", "--grid-line", "--viz-1", "--map-stop-0", "--map-stop-5",
        ):
            self.assertIn(token, self.tokens)
        self.assertIn(':root[data-theme="dark"]', self.tokens)
        dark = _block(self.tokens, ':root[data-theme="dark"]')
        for token in ("--bg-canvas", "--bg-surface", "--text-body", "--accent-primary", "--border-subtle", "--map-stop-5"):
            self.assertIn(token, dark)
        self.assertIn("var(--grad-display)", self.css)

    def test_dark_theme_avoids_banned_palette_and_keeps_text_readable(self) -> None:
        self.assertNotIn("#0b1220", self.tokens.lower())
        dark = _block(self.tokens, ':root[data-theme="dark"]')
        body = _hex_value(dark, "--text-body")
        canvas = _hex_value(dark, "--bg-canvas")
        strong = _hex_value(dark, "--text-strong")
        surface = _hex_value(dark, "--bg-surface")
        self.assertTrue(body and canvas and strong and surface)
        self.assertGreaterEqual(_ratio(body, canvas), 4.5)
        self.assertGreaterEqual(_ratio(strong, surface), 4.5)

    def test_light_theme_text_stays_readable(self) -> None:
        light = _block(self.tokens, ":root")
        body = _hex_value(light, "--text-body")
        canvas = _hex_value(light, "--bg-canvas")
        self.assertTrue(body and canvas)
        self.assertGreaterEqual(_ratio(body, canvas), 4.5)

    def test_theme_bootstrap_toggle_and_persistence(self) -> None:
        self.assertIn("wanyu.v15.theme", self.html)
        self.assertIn("maintain-theme-toggle", self.html)
        self.assertIn("color-scheme", self.tokens)
        self.assertIn("wanyu.v15.theme", self.js)
        for marker in ("dataset.theme", "prefers-color-scheme: dark"):
            self.assertIn(marker, self.js)

    def test_site_css_shell_is_token_driven_and_motion_ready(self) -> None:
        self.assertIn(".maintain-theme-toggle", self.css)
        self.assertIn("font-variant-numeric:tabular-nums", self.css)
        self.assertIn('[data-theme="dark"] .maintain-header', self.css)
        self.assertIn('[data-theme="dark"] .maint-panel', self.css)
        self.assertIn("var(--dur-fast)", self.css)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn("backdrop-filter", self.css)

    def test_legacy_v14_gate_strings_survive(self) -> None:
        for token in ("--bg-context", "--bg-surface", "--text-strong", "--text-muted", "--status-warning", "--focus-ring"):
            self.assertIn(token, self.tokens)
        self.assertIn("--accent-primary: #3a83f7", self.tokens)
        self.assertIn("--accent-primary-soft: #eef5ff", self.tokens)
        self.assertIn("--accent-teal: #b7d1f8", self.tokens)
        self.assertIn("/* v14.3: reference blue calibration", self.css)
        self.assertIn("background:rgba(251,253,255,.98)", self.css)
        self.assertIn("var(--map-fill,#e7f0ff)", self.css)

    def test_v15_1_accessibility_and_narrow_nav(self) -> None:
        self.assertIn("maintain-skip-link", self.html)
        self.assertIn('href="#maintain-main"', self.html)
        self.assertIn(".maintain-skip-link", self.css)
        self.assertIn(".maintain-skip-link:focus", self.css)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn("@media(max-width:820px){.maintain-nav{flex-wrap:wrap;overflow:visible}}", self.css)

    def test_v16_pwa_offline_layer(self) -> None:
        self.assertIn("navigator.serviceWorker.register('sw.js')", self.html)
        self.assertIn('rel="manifest"', self.html)
        self.assertIn('id="maintain-offline-badge"', self.html)
        self.assertIn("maintain-offline-badge", self.css)
        self.assertIn("addEventListener('offline'", self.js)
        sw = (TEMPLATES / "maintainable-sw.js").read_text(encoding="utf-8")
        self.assertIn("network-first", sw)
        self.assertIn("/data/", sw)
        self.assertIn("caches.match", sw)

    def test_v16_1_cta_band_tokens_paired_and_readable(self) -> None:
        for theme_name, block in (("light", _block(self.tokens, ":root")), ("dark", _block(self.tokens, ':root[data-theme="dark"]'))):
            bg = _hex_value(block, "--band-bg")
            fg = _hex_value(block, "--band-fg")
            muted = _hex_value(block, "--band-muted")
            self.assertTrue(bg and fg and muted, f"{theme_name} band tokens must be 6-digit hex pairs")
            self.assertGreaterEqual(_ratio(fg, bg), 4.5)
            self.assertGreaterEqual(_ratio(muted, bg), 4.5)
        self.assertIn("maint-cta", self.html)
        self.assertIn("maint-cta__primary", self.css)
        self.assertIn('href="#jobs_search" data-maintain-view="jobs_search"', self.html)
        self.assertIn("2024—2026 ·", self.html)
        self.assertNotIn('href="http', self.html)
        self.assertIn("maint-eyebrow__index", self.css)
        self.assertIn("reveal-ready", self.css)
        self.assertIn("reveal-ready", self.js)
        self.assertIn("prefers-reduced-motion: reduce", self.js)
        self.assertIn("data-countup", self.js)

    def test_v16_2_motion_contract(self) -> None:
        for token in ("--dur-reveal", "--dur-reveal-x", "--ease-pop"):
            self.assertIn(token, self.tokens)
        # 显现初始态必须 scoped 在 .reveal-ready 下:reduced-motion/无 JS 时直出终态
        for selector in (
            ".reveal-ready .maint-hero .maint-eyebrow",
            ".reveal-ready .bento__cell",
            ".reveal-ready .maint-grid>.maint-panel",
            ".reveal-ready .city-row i em",
            ".reveal-ready .mixbar__seg",
            ".reveal-ready .sparkline polyline",
            ".reveal-ready .maint-map-region",
            ".reveal-ready .rank-med",
        ):
            self.assertIn(selector, self.css)
        # 显现初始态必须 scoped 在 .reveal-ready 下:reduced-motion/无 JS 时直出终态。
        # 对每个目标选择器定点检查:若其规则体出现隐藏态,紧邻其前的 13 字符必须恰好是 "reveal-ready "。
        for target, hidden in (
            (".maint-hero", "opacity:0"),
            (".bento__cell", "opacity:0"),
            (".city-row i em", "scaleX(0)"),
            (".mixbar__seg", "scaleX(0)"),
            (".maint-map-region", "opacity:0"),
            (".rank-med", "opacity:0"),
        ):
            for match in re.finditer(r"(?<!reveal-ready )" + re.escape(target) + r"\{[^{}]*", self.css):
                segment = match.group(0)
                self.assertNotIn(hidden, segment, f"hidden state leaks outside reveal-ready: {segment[:80]}")
        # 数据生长动效接线:既有 --map-delay 被消费、sparkline pathLength、抽屉/面板入场
        self.assertIn("var(--map-delay", self.css)
        self.assertIn('pathLength="1"', self.js)
        self.assertIn(".maint-detail-drawer{animation", self.css)
        self.assertIn(".maint-palette__panel{animation", self.css)
        # 滚动进度线三件套 + CTA 微交互
        self.assertIn("maintain-scroll-progress", self.html)
        self.assertIn(".maintain-scroll-progress", self.css)
        self.assertIn("maintain-scroll-progress", self.js)
        self.assertIn("maint-cta__arrow", self.html)
        self.assertIn(".maint-cta__arrow", self.css)
        self.assertIn("maint-cta__glow", self.html)
        self.assertIn(".maint-cta__glow", self.css)
        # 容器级终态必须存在且晚于其初始声明(specificity 同级后胜,防"is-in 已加仍隐藏")
        for container in (".maint-hero", ".maint-panel", ".maint-kpis", ".maint-callout"):
            initial = ".reveal-ready " + container + "{"
            final = ".reveal-ready " + container + ".is-in"
            self.assertIn(final, self.css, f"{container} 缺少容器级 .is-in 终态")
            self.assertGreater(self.css.rindex(final), self.css.rindex(initial), f"{container} 终态必须先于/晚于初始声明之后")


if __name__ == "__main__":
    unittest.main()
