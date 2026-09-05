from __future__ import annotations

import unittest


class CatalogTests(unittest.TestCase):
    def test_catalog_filters_code_only_major_labels(self) -> None:
        from tools.anhui_web.build_catalog import build_catalog

        rows = [{"zy": "0801048"}, {"zy": "软件工程"}, {"zy": ""}, {"zy": "0801048 软件工程"}]
        catalog = build_catalog({"allMajors": {"rows": rows}}, "2026")
        self.assertIn("软件工程", catalog["majors"])
        self.assertNotIn("0801048", catalog["majors"])
        self.assertTrue(all(any(ch.isalpha() or "\u4e00" <= ch <= "\u9fff" for ch in value) for value in catalog["majors"]))

    def test_catalog_keeps_source_value_and_exposes_counts(self) -> None:
        from tools.anhui_web.build_catalog import build_catalog

        rows = [
            {"zy": "软件工程", "city": "合肥", "exam": "省考", "lb": "行政执法"},
            {"zy": "软件工程", "city": "芜湖", "exam": "省考", "lb": "行政执法"},
        ]
        catalog = build_catalog({"allMajors": {"rows": rows}}, "2026")
        self.assertEqual(catalog["major_counts"]["软件工程"], 2)
        self.assertEqual(catalog["facets"]["cities"], ["合肥", "芜湖"])
        self.assertEqual(catalog["source_fields"]["major"], "zy")

    def test_filter_intersection_uses_source_fields(self) -> None:
        from tools.anhui_web.build_catalog import filter_rows

        rows = [
            {"zy": "软件工程", "city": "合肥", "exam": "省考", "lb": "行政执法"},
            {"zy": "软件工程", "city": "芜湖", "exam": "省考", "lb": "综合管理"},
        ]
        self.assertEqual(filter_rows(rows, {"major": "软件", "city": "合肥", "exam": "省考"}), [rows[0]])
        self.assertEqual(filter_rows(rows, {"category": "不存在"}), [])

    def test_filter_uses_cleaned_major_candidate_against_raw_code_mixed_value(self) -> None:
        from tools.anhui_web.build_catalog import filter_rows

        row = {"zy": "K会计学、120204财务管理、120207审计", "city": "合肥", "exam": "省考"}
        self.assertEqual(filter_rows([row], {"major": "会计学、财务管理、审计"}), [row])

    def test_clean_major_label_returns_none_for_pure_code(self) -> None:
        from tools.anhui_web.build_catalog import clean_major_label

        self.assertIsNone(clean_major_label("0801048"))
        self.assertEqual(clean_major_label("0801048 / 软件工程"), "软件工程")
        self.assertEqual(clean_major_label("  软件工程  "), "软件工程")
        self.assertEqual(clean_major_label("K会计学、120204财务管理、120207审计"), "会计学、财务管理、审计")

    def test_catalog_exposes_readable_keywords_for_composite_source_text(self) -> None:
        from tools.anhui_web.build_catalog import build_catalog

        raw = "本科：软件工程专业（080901）；研究生：计算机科学与技术类（0812）。"
        catalog = build_catalog({"allMajors": {"rows": [{"zy": raw}]}}, "2026")

        self.assertIn("软件工程", catalog["majors"])
        self.assertIn("计算机科学与技术", catalog["majors"])
        self.assertNotIn(raw, catalog["majors"])
        self.assertTrue(all(len(value) <= 32 for value in catalog["majors"]))
        self.assertEqual(catalog["major_options_mode"], "readable_keywords")


if __name__ == "__main__":
    unittest.main()
