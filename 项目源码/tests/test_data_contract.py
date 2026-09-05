from __future__ import annotations

import unittest
from pathlib import Path


class DataContractTests(unittest.TestCase):
    def test_unknown_is_not_serialized_as_zero(self) -> None:
        from tools.anhui_web.data_contract import validate_unknown_semantics

        with self.assertRaises(ValueError):
            validate_unknown_semantics(0, "unpublished_or_unavailable")
        with self.assertRaises(ValueError):
            validate_unknown_semantics("推断值", "ambiguous_join")

    def test_same_normalized_row_has_same_record_id(self) -> None:
        from tools.anhui_web.data_contract import make_record_id

        row = {"exam": "省考", "city": "合肥", "code": "010009", "unit": "示例单位", "post_name": "综合管理"}
        self.assertEqual(make_record_id("2026", row), make_record_id("2026", dict(row)))
        self.assertTrue(make_record_id("2026", row).startswith("job-2026-"))

    def test_record_id_changes_for_different_cycle_or_position(self) -> None:
        from tools.anhui_web.data_contract import make_record_id

        row = {"exam": "省考", "city": "合肥", "code": "010009", "unit": "示例单位", "post_name": "综合管理"}
        other = {**row, "post_name": "财务管理"}
        self.assertNotEqual(make_record_id("2025", row), make_record_id("2026", row))
        self.assertNotEqual(make_record_id("2026", row), make_record_id("2026", other))

    def test_evidence_requires_status_and_source(self) -> None:
        from tools.anhui_web.data_contract import evidence

        result = evidence("verified", "source.xlsx", "row:3/专业", "official_page", "2026-08-28", "原始值")
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["source_ref"], "source.xlsx")
        with self.assertRaises(ValueError):
            evidence("not-a-status", "source.xlsx", "row:3", "official_page", "2026-08-28")
        with self.assertRaises(ValueError):
            evidence("verified", "", "row:3", "official_page", "2026-08-28")


if __name__ == "__main__":
    unittest.main()
