# -*- coding: utf-8 -*-
"""RC3 阶段 O：anti-circular-build——生成物不得成为正式构建输入。

静态扫描「正式输入侧模块」：任何对部署树（网站/）或生成产物目录的路径引用都
是红线（HTML 永远只是 OUTPUT，网站成品永远只是 OUTPUT）。

分类说明（诚实边界）：
- gen_canonical_bundles.py 是**种子迁移工具**（任务书 G 允许以审计生产快照为种子，
  provenance 见 docs/migrations/canonical-seed-20260905.md），不属于正式 builder，
  明确排除在本扫描之外；正式链没有任何模块依赖它。
- gen_job_history.py / build_major_index.py 的 build()/build_payload() 输入是
  canonical（本测试断言其 canonical 引用）；它们的 CLI 默认输出指向部署树，
  属 OUTPUT 侧，不在本扫描清单。
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INPUT_MODULES = (
    "tools/anhui_web/unified_cycle_bundle.py",
    "tools/anhui_web/build_maintainable_site.py",
    "tools/anhui_web/audit_three_years.py",
    "tools/anhui_web/build_review_queue.py",
    "tools/anhui_web/build_scores.py",
    "tools/anhui_web/build_catalog.py",
    "tools/anhui_web/build_changes.py",
    "tools/anhui_web/build_position_index.py",
    "tools/anhui_web/record_lifecycle.py",
    "tools/anhui_web/invariants.py",
)

CANONICAL_WIRED = (
    "tools/anhui_web/unified_cycle_bundle.py",
    "tools/anhui_web/audit_three_years.py",
    "tools/anhui_web/gen_job_history.py",
    "tools/anhui_web/build_major_index.py",
)


class NoGeneratedOutputAsInputTests(unittest.TestCase):
    def test_input_modules_never_reference_deployed_tree(self):
        offenders = []
        for rel in INPUT_MODULES:
            for lineno, line in enumerate((ROOT / rel).read_text(encoding="utf-8").splitlines(), start=1):
                if "O:OUTPUT-SIDE" in line:
                    continue  # 显式标注的输出侧引用（如 builder 默认输出目录）
                for token in ("网站", "deliverables/maintainable"):
                    if token in line:
                        offenders.append(f"{rel}:{lineno}: 含 {token!r}")
        self.assertEqual([], offenders, f"正式输入模块引用了部署树/生成物：{offenders}")

    def test_row_source_builders_are_canonical_wired(self):
        for rel in CANONICAL_WIRED:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("canonical", text, f"{rel} 未接入 canonical 行源")
            self.assertIn("load_canonical_doc", text, f"{rel} 未使用 canonical loader")

    def test_legacy_loader_not_imported_by_formal_chain(self):
        import re

        formal_importers = ("build_maintainable_site", "unified_cycle_bundle", "audit_three_years",
                            "build_review_queue", "gen_job_history", "build_major_index")
        for name in formal_importers:
            text = (ROOT / "tools/anhui_web" / f"{name}.py").read_text(encoding="utf-8")
            self.assertIsNone(
                re.search(r"(?:from|import)\s+\S*legacy_html_loader", text),
                f"{name} import 了 legacy HTML 加载器（注释提及不算违规）",
            )


if __name__ == "__main__":
    unittest.main()
