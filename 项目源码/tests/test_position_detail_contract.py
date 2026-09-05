from __future__ import annotations

import unittest


class PositionDetailContractTests(unittest.TestCase):
    def test_position_index_has_stable_id_and_evidence_envelope(self) -> None:
        from tools.anhui_web.build_position_index import build_position_index

        row = {
            "exam": "省考",
            "city": "合肥",
            "code": "010009",
            "unit": "示例单位",
            "post_name": "综合管理",
            "zy": "软件工程",
        }
        sources = {"source_ref": "tools/anhui_web/data/all_majors_2026.json", "observed_at": "2026-08-28"}
        index = build_position_index([row], sources)
        item = index["rows"][0]
        self.assertTrue(item["record_id"])
        self.assertIn(item["source"]["status"], {"verified", "source_bundle", "derived", "needs_review"})
        self.assertEqual(item["source"]["source_ref"], sources["source_ref"])
        self.assertEqual(item["detail_ref"], {"module": "jobs", "row_index": 0})

    def test_position_index_does_not_mutate_source_row(self) -> None:
        from tools.anhui_web.build_position_index import build_position_index

        row = {"job_id": "job-2026-existing", "zy": "软件工程", "source_note": "官方职位表"}
        before = dict(row)
        build_position_index([row], {"source_ref": "cycle.json", "observed_at": "2026-08-28"})
        self.assertEqual(row, before)

    def test_find_position_matches_existing_job_id(self) -> None:
        from tools.anhui_web.build_position_index import find_position

        rows = [{"job_id": "job-2026-existing", "code": "010009"}]
        self.assertEqual(find_position(rows, "job-2026-existing"), rows[0])
        self.assertIsNone(find_position(rows, "job-2026-missing"))

    def test_missing_source_value_explains_why(self) -> None:
        from tools.anhui_web.build_position_index import render_evidence_panel

        html = render_evidence_panel(
            {"salary": None, "salary_status": "unpublished_or_unavailable"},
            {},
        )
        self.assertIn("未发布", html)

    def test_missing_source_date_is_explicitly_unknown_not_a_fake_date(self) -> None:
        from tools.anhui_web.build_position_index import build_position_index

        index = build_position_index(
            [{"job_id": "job-2024-undated", "zy": "软件工程"}],
            {"source_ref": "cycle.json", "observed_at": None},
        )
        self.assertIsNone(index["rows"][0]["source"]["observed_at"])


if __name__ == "__main__":
    unittest.main()
