import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.anhui_web.build_supplement_evidence import build_supplement_evidence, _normalise, _read_checksums


class SupplementIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.supplement_dir = ROOT / "source_data" / "supplement_20260904"
        cls.payload = build_supplement_evidence(ROOT)
        cls.manifest_rows = [
            json.loads(line)
            for line in (cls.supplement_dir / "source_manifest.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_raw_inventory_and_hashes(self):
        files = self.payload["files"]
        self.assertEqual(len(files), 43)
        self.assertEqual(self.payload["summary"]["raw_files"], 43)
        self.assertEqual(self.payload["summary"]["valid_documents"], 41)
        self.assertEqual(self.payload["summary"]["blocked_downloads"], 2)
        self.assertEqual(self.payload["summary"]["checksum_entries"], 43)
        self.assertEqual(self.payload["summary"]["checksum_matches"], 43)
        self.assertEqual(self.payload["summary"]["checksum_mismatches"], 0)
        self.assertEqual(self.payload["summary"]["checksum_missing"], 0)
        checksums = _read_checksums(self.supplement_dir / "checksums.sha256")
        for item in files:
            path = ROOT / item["local_file"]
            self.assertTrue(path.is_file(), item["local_file"])
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(actual, item["sha256"], item["local_file"])
            self.assertEqual(actual, checksums[_normalise(item["local_file"])], item["local_file"])

    def test_manifest_coverage_and_evidence_boundaries(self):
        supplement_rows = [
            row for row in self.manifest_rows
            if _normalise(row.get("local_file", "")).startswith("source_data/supplement_20260904/")
        ]
        self.assertEqual(len(self.manifest_rows), 245)
        self.assertEqual(len(supplement_rows), 43)
        self.assertTrue(all(row.get("sha256") for row in supplement_rows))
        self.assertEqual(self.payload["summary"]["manifest_coverage"], 43)
        self.assertEqual(self.payload["summary"]["empty_manifest_sha"], 0)
        self.assertEqual(self.payload["summary"]["probable_score_evidence"], 116)
        self.assertEqual(self.payload["summary"]["title_major_candidates"], 24)
        self.assertEqual(self.payload["summary"]["formal_integrated_records"], 0)
        self.assertEqual(self.payload["summary"]["normalized_evidence_records"], 835)

    def test_cycle_breakdown(self):
        self.assertEqual(
            self.payload["by_cycle"],
            {
                "2024": {"raw_files": 27, "valid_documents": 25, "blocked_downloads": 2, "unclassified_files": 0, "bytes": 9462683},
                "2025": {"raw_files": 7, "valid_documents": 7, "blocked_downloads": 0, "unclassified_files": 0, "bytes": 128496},
                "2026": {"raw_files": 9, "valid_documents": 9, "blocked_downloads": 0, "unclassified_files": 0, "bytes": 1234200},
            },
        )

    def test_canonical_baseline_unchanged_and_outputs_registered(self):
        expected = {"2024": (10017, 15331), "2025": (10150, 14721), "2026": (8511, 12006)}
        for cycle, (posts, recruits) in expected.items():
            path = ROOT / "deliverables" / "maintainable" / "data" / "cycles" / cycle / "jobs.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            meta = payload["allMajors"]["meta"]
            self.assertEqual((meta["total"], meta["recruits"]), (posts, recruits), cycle)
        expected_sha = self.payload["summary"]
        for output_dir in (
            ROOT / "deliverables" / "maintainable",
            ROOT.parent / "网站",
            ROOT.parent / "网站-lite",
        ):
            manifest = json.loads((output_dir / "data" / "site-manifest.json").read_text(encoding="utf-8"))
            entry = manifest.get("supplement")
            self.assertIsNotNone(entry, str(output_dir))
            evidence_path = output_dir / entry["data"]
            encoded = evidence_path.read_bytes()
            self.assertEqual(len(encoded), entry["bytes"], str(output_dir))
            self.assertEqual(hashlib.sha256(encoded).hexdigest(), entry["sha256"], str(output_dir))
            self.assertEqual(json.loads(encoded.decode("utf-8"))["summary"], expected_sha, str(output_dir))


if __name__ == "__main__":
    unittest.main()
