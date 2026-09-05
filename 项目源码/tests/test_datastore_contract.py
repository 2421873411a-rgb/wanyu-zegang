from __future__ import annotations

import hashlib
import unittest


class DataStorePythonContractTests(unittest.TestCase):
    def test_module_path_is_manifest_driven(self) -> None:
        from tools.anhui_web.datastore_contract import module_path

        manifest = {"cycles": [{"cycle": "2026", "modules": {"catalog": {"data": "data/cycles/2026/catalog.json"}}}]}
        self.assertEqual(module_path(manifest, "2026", "catalog"), "data/cycles/2026/catalog.json")

    def test_verify_module_payload_rejects_hash_mismatch(self) -> None:
        from tools.anhui_web.datastore_contract import verify_module_payload

        payload = {"schema": "wanyu-maintainable-jobs/v1", "cycle": "2026"}
        with self.assertRaises(ValueError):
            verify_module_payload("jobs", payload, {"sha256": "0" * 64})

    def test_verify_module_payload_checks_schema_and_optional_bytes(self) -> None:
        from tools.anhui_web.datastore_contract import verify_module_payload

        payload = {"schema": "wanyu-maintainable-catalog/v1", "cycle": "2026", "majors": [], "facets": {}}
        encoded = b'{"facets":{},"majors":[],"schema":"wanyu-maintainable-catalog/v1","cycle":"2026"}'
        entry = {"schema": payload["schema"], "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()}
        # The helper accepts the exact serialized bytes when supplied by the disk verifier.
        self.assertIsNone(verify_module_payload("catalog", payload, entry, encoded=encoded))


if __name__ == "__main__":
    unittest.main()
