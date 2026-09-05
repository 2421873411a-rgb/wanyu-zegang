from __future__ import annotations

import unittest


def _event(title: str, cycle: str = "2026", kind: str = "unpublished_or_unavailable") -> dict[str, str]:
    return {
        "cycle": cycle,
        "kind": kind,
        "evidence": "tools/anhui_web/data/manifest.json",
        "title": title,
        "scope": title,
        "severity": "high",
        "detail": "需要官方材料后重新构建",
    }


class ReviewQueueTests(unittest.TestCase):
    def test_duplicate_detail_events_share_one_public_boundary(self) -> None:
        from tools.anhui_web.build_review_queue import dedupe_audit_events

        events = [_event("成绩收割边界"), _event("成绩收割边界")]
        result = dedupe_audit_events(events)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["occurrences"], 2)

    def test_current_summary_preserves_unresolved_116_and_public_8(self) -> None:
        from tools.anhui_web.build_review_queue import build_review_queue

        bundles = {"2024": {}, "2025": {}, "2026": {"score_unresolved": 116}}
        audit_snapshot = {
            "summary": {"gap_count": 8, "unresolved_score_count": 116},
            "cycles": [{"cycle": "2026", "gaps": [_event("成绩收割边界")] }],
        }
        queue = build_review_queue(bundles, audit_snapshot)
        self.assertEqual(queue["summary"]["unresolved_score_count"], 116)
        self.assertEqual(queue["summary"]["public_boundary_count"], 8)

    def test_queue_keeps_high_risk_detail_and_status(self) -> None:
        from tools.anhui_web.build_review_queue import build_review_queue

        audit_snapshot = {"summary": {"gap_count": 1, "unresolved_score_count": 0}, "cycles": [{"cycle": "2026", "gaps": [_event("待官方复核", kind="needs_review")]}]}
        queue = build_review_queue({"2026": {"score_unresolved": 0}}, audit_snapshot)
        self.assertEqual(queue["items"][0]["severity"], "high")
        self.assertEqual(queue["items"][0]["kind"], "needs_review")
        self.assertTrue(queue["items"][0]["detail"])

    def test_summary_function_counts_queue_items(self) -> None:
        from tools.anhui_web.build_review_queue import summarize_review_queue

        summary = summarize_review_queue({"items": [_event("A"), _event("B", kind="needs_review")]})
        self.assertEqual(summary["high_risk_count"], 2)
        self.assertEqual(summary["needs_review_count"], 1)


if __name__ == "__main__":
    unittest.main()
