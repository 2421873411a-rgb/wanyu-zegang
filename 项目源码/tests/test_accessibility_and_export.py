from __future__ import annotations

import unittest


class AccessibilityExportTests(unittest.TestCase):
    def test_pagination_never_renders_more_than_page_size_rows(self) -> None:
        from tools.anhui_web.ui_contract import paginate_rows

        result = paginate_rows([{}] * 10_000, 1, 120)
        self.assertEqual(len(result["rows"]), 120)
        self.assertEqual(result["total"], 10_000)
        self.assertEqual(result["page_count"], 84)

    def test_pagination_clamps_out_of_range_page(self) -> None:
        from tools.anhui_web.ui_contract import paginate_rows

        result = paginate_rows([{"id": 1}], 999, 120)
        self.assertEqual(result["page"], 0)
        self.assertEqual(result["rows"], [{"id": 1}])

    def test_export_escapes_formula_prefix_and_csv_delimiters(self) -> None:
        from tools.anhui_web.ui_contract import escape_csv_cell

        self.assertTrue(escape_csv_cell("+SUM(A1:A2)").startswith("'+"))
        self.assertEqual(escape_csv_cell('a,"b"'), '"a,""b"""')

    def test_announce_returns_trimmed_accessible_message(self) -> None:
        from tools.anhui_web.ui_contract import announce

        self.assertEqual(announce("  已加载  " ), "已加载")


if __name__ == "__main__":
    unittest.main()
