from __future__ import annotations

import unittest


class ScoresContractTests(unittest.TestCase):
    def test_build_scores_preserves_cycle_scoped_indexes_and_unknowns(self) -> None:
        from tools.anhui_web.build_scores import build_scores

        payload = build_scores(
            {
                "cycle": "2026",
                "generated_on": "2026-08-31",
                "bs": {"010001": {"line": 70}},
                "ms": {"010001": {"line": 72}},
                "by_key": {"省考|合肥|010001|1": {"line": 70}},
                "keyed": {"bs": 1, "ms": 1, "unresolved": [{"code": "0901001"}]},
            },
            "2026",
        )

        self.assertEqual(payload["schema"], "wanyu-maintainable-scores/v1")
        self.assertEqual(payload["cycle"], "2026")
        self.assertEqual(payload["source_module"], "cycle score list source")
        self.assertIn("bs", payload)
        self.assertIn("ms", payload)
        self.assertIn("by_key", payload)
        self.assertEqual(payload["keyed"]["unresolved"], [{"code": "0901001"}])
        self.assertEqual(payload["summary"]["unresolved"], 1)

    def test_build_scores_does_not_turn_missing_or_unresolved_into_zero(self) -> None:
        from tools.anhui_web.build_scores import build_scores

        payload = build_scores({"cycle": "2024", "keyed": {"unresolved": [{"code": "x"}]}}, "2024")
        self.assertEqual(payload["summary"]["unresolved"], 1)
        self.assertIsNone(payload["summary"].get("missing"))
        self.assertEqual(payload["keyed"]["unresolved"], [{"code": "x"}])

    def test_build_scores_rejects_cycle_mismatch(self) -> None:
        from tools.anhui_web.build_scores import build_scores

        with self.assertRaises(ValueError):
            build_scores({"cycle": "2025", "keyed": {"unresolved": []}}, "2026")


if __name__ == "__main__":
    unittest.main()
