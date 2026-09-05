from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class SourceRegistryTests(unittest.TestCase):
    def test_source_registry_records_sha256_and_locator(self) -> None:
        from tools.anhui_web.source_registry import register_source

        with tempfile.NamedTemporaryFile("wb", delete=False) as handle:
            handle.write(b"source snapshot")
            temporary_path = Path(handle.name)
        self.addCleanup(lambda: temporary_path.unlink(missing_ok=True))
        record = register_source(temporary_path, "2026", "official_position_table", "发布机构", "2026-08-28")
        self.assertEqual(len(record["sha256"]), 64)
        self.assertEqual(record["cycle"], "2026")
        self.assertEqual(record["bytes"], len(b"source snapshot"))
        self.assertTrue(record["source_ref"])

    def test_missing_source_is_rejected(self) -> None:
        from tools.anhui_web.source_registry import register_source

        with self.assertRaises(FileNotFoundError):
            register_source(Path("does-not-exist.xlsx"), "2026", "official_position_table", "发布机构", "2026-08-28")

    def test_invalid_cycle_and_date_are_rejected(self) -> None:
        from tools.anhui_web.source_registry import register_source

        with tempfile.NamedTemporaryFile("wb", delete=False) as handle:
            handle.write(b"x")
            temporary_path = Path(handle.name)
        self.addCleanup(lambda: temporary_path.unlink(missing_ok=True))
        with self.assertRaises(ValueError):
            register_source(temporary_path, "26", "official_position_table", "发布机构", "2026-08-28")
        with self.assertRaises(ValueError):
            register_source(temporary_path, "2026", "official_position_table", "发布机构", "not-a-date")


if __name__ == "__main__":
    unittest.main()
