# -*- coding: utf-8 -*-
"""record_lifecycle 单元测试（wanyu-record-status/v1）+ 2026 生命周期事实回归。"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.anhui_web.record_lifecycle import (  # noqa: E402
    EXCLUDED_STATUSES,
    RECORD_STATUS_MODEL,
    apply_overrides,
    is_active_record,
    load_overrides,
    record_status_of,
    split_records,
)

SITE = ROOT.parent / "网站"


class LifecycleSemanticsTests(unittest.TestCase):
    def test_missing_status_is_active(self):
        self.assertEqual(record_status_of({}), "active")
        self.assertTrue(is_active_record({}))

    def test_active_status(self):
        self.assertTrue(is_active_record({"record_status": "active"}))

    def test_excluded_statuses(self):
        for status in sorted(EXCLUDED_STATUSES):
            self.assertFalse(is_active_record({"record_status": status}), status)
        self.assertTrue(EXCLUDED_STATUSES == {"duplicate", "invalid_source", "withdrawn", "superseded", "needs_review"})

    def test_unknown_status_is_excluded(self):
        self.assertFalse(is_active_record({"record_status": "mystery"}))

    def test_split_records(self):
        raw = [{"job_id": "a"}, {"job_id": "b", "record_status": "duplicate"}, {"job_id": "c", "record_status": "active"}]
        raw_out, active, excluded = split_records(raw)
        self.assertEqual(len(raw_out), 3)
        self.assertEqual([r["job_id"] for r in active], ["a", "c"])
        self.assertEqual([r["job_id"] for r in excluded], ["b"])

    def test_overrides_missing_file_is_empty(self):
        self.assertEqual(load_overrides(Path(ROOT / "does-not-exist")), {})

    def test_overrides_require_evidence(self):
        bad = {"cycles": {"2026": {"duplicate_job_ids": ["x"]}}}
        with self.assertRaises(ValueError):
            apply_overrides([{"job_id": "x"}], bad, "2026")

    def test_apply_overrides_marks_and_is_idempotent(self):
        overrides = load_overrides(ROOT)
        rows = [
            {"job_id": "job-2026-x1", "num": 1},
            {"job_id": "job-2026-x2", "num": 2},
        ]
        overrides["cycles"]["2026"] = {
            "duplicate_job_ids": ["job-2026-x1"],
            "exclusion_reason": "cross_city_source_duplication",
            "exclusion_evidence": "evidence.txt",
            "excluded_at": "2026-09-05",
        }
        apply_overrides(rows, overrides, "2026")
        self.assertEqual(rows[0]["record_status"], "duplicate")
        self.assertEqual(rows[0]["exclusion_reason"], "cross_city_source_duplication")
        apply_overrides(rows, overrides, "2026")  # 幂等
        self.assertEqual(rows[0]["record_status"], "duplicate")

    def test_apply_overrides_rejects_conflicting_marks(self):
        overrides = load_overrides(ROOT)
        overrides["cycles"]["2026"] = {
            "duplicate_job_ids": ["job-2026-x1"],
            "exclusion_reason": "cross_city_source_duplication",
            "exclusion_evidence": "evidence.txt",
            "excluded_at": "2026-09-05",
        }
        rows = [{"job_id": "job-2026-x1", "record_status": "withdrawn"}]
        with self.assertRaises(ValueError):
            apply_overrides(rows, overrides, "2026")


class Lifecycle2026FactTests(unittest.TestCase):
    """2026 现库事实回归：8511 = 8401 + 110；lite 天然 active-only。"""

    @classmethod
    def setUpClass(cls):
        cls.jobs = json.loads((SITE / "data" / "cycles" / "2026" / "jobs.json").read_text(encoding="utf-8"))
        cls.lite = json.loads((SITE / "data" / "cycles" / "2026" / "jobs_lite.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((SITE / "data" / "site-manifest.json").read_text(encoding="utf-8"))
        cls.overrides = load_overrides(ROOT)

    def test_raw_equals_active_plus_excluded(self):
        rows = self.jobs["allMajors"]["rows"]
        raw, active, excluded = split_records(rows)
        self.assertEqual(len(raw), 8511)
        self.assertEqual(len(active), 8401)
        self.assertEqual(len(excluded), 110)

    def test_excluded_rows_carry_evidence(self):
        _, _, excluded = split_records(self.jobs["allMajors"]["rows"])
        for row in excluded:
            self.assertEqual(row.get("exclusion_reason"), "cross_city_source_duplication")
            self.assertTrue(row.get("exclusion_evidence"))
            self.assertTrue(row.get("excluded_at"))

    def test_overrides_match_current_duplicates(self):
        rule = self.overrides["cycles"]["2026"]
        _, _, excluded = split_records(self.jobs["allMajors"]["rows"])
        self.assertEqual(sorted(rule["duplicate_job_ids"]), sorted(str(r["job_id"]) for r in excluded))
        self.assertEqual(len(rule["duplicate_job_ids"]), 110)

    def test_lite_is_active_only(self):
        lite_rows = self.lite["allMajors"]["rows"]
        self.assertEqual(len(lite_rows), 8401)
        _, _, excluded = split_records(self.jobs["allMajors"]["rows"])
        excluded_ids = {str(r["job_id"]) for r in excluded}
        self.assertFalse(excluded_ids & {str(r.get("job_id")) for r in lite_rows})

    def test_manifest_metrics_contract(self):
        entry = next(e for e in self.manifest["cycles"] if str(e["cycle"]) == "2026")
        self.assertEqual(entry["raw_posts"], 8511)
        self.assertEqual(entry["active_posts"], 8401)
        self.assertEqual(entry["excluded_posts"], 110)
        self.assertEqual(entry["raw_recruits"], 12006)
        self.assertEqual(entry["recruits"], 11883)
        self.assertEqual(entry["posts"], 8401)
        self.assertEqual(self.manifest["metrics_contract"]["name"], "wanyu-metrics/v1")


if __name__ == "__main__":
    unittest.main()
