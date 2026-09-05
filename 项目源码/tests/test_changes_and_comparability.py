from __future__ import annotations

import unittest


class ChangesAndComparabilityTests(unittest.TestCase):
    def test_exact_code_match_is_comparable(self) -> None:
        from tools.anhui_web.build_changes import classify_change

        base = {"record_id": "2025:a", "exam": "省考", "city": "合肥", "code": "010009", "recruits": 1, "status": "verified"}
        target = {"record_id": "2026:a", "exam": "省考", "city": "合肥", "code": "010009", "recruits": 2, "status": "verified"}
        result = classify_change(base, target, "exact_code")
        self.assertIn(result["status"], {"unchanged", "revised"})
        self.assertTrue(result["comparable"])
        self.assertEqual(result["match_method"], "exact_code")

    def test_semantic_candidate_is_not_published_as_same_position(self) -> None:
        from tools.anhui_web.build_changes import classify_change

        base = {"record_id": "2025:a", "unit": "甲单位", "post_name": "综合管理", "status": "verified"}
        target = {"record_id": "2026:a", "unit": "甲单位", "post_name": "综合管理", "status": "verified"}
        result = classify_change(base, target, "semantic_candidate")
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["comparable"])

    def test_match_positions_reports_added_and_withdrawn(self) -> None:
        from tools.anhui_web.build_changes import match_positions

        base = [{"record_id": "old", "exam": "省考", "city": "合肥", "code": "010009", "unit": "甲", "post_name": "综合"}]
        target = [{"record_id": "new", "exam": "省考", "city": "合肥", "code": "010010", "unit": "乙", "post_name": "财务"}]
        result = match_positions(base, target)
        self.assertEqual({item["status"] for item in result}, {"added", "withdrawn"})

    def test_different_denominator_blocks_percentage(self) -> None:
        from tools.anhui_web.build_changes import comparable_metric

        result = comparable_metric("competition_rate", {"denominator": "paid"}, {"denominator": "registered"})
        self.assertFalse(result["comparable"])
        self.assertIn("分母", result["reason"])

    def test_build_change_payload_has_explicit_comparability(self) -> None:
        from tools.anhui_web.build_changes import build_change_payload

        payload = build_change_payload("2025", "2026", [], [])
        self.assertEqual(payload["schema"], "wanyu-maintainable-changes/v1")
        self.assertFalse(payload["comparable"])
        self.assertEqual(payload["changes"], [])


if __name__ == "__main__":
    unittest.main()
