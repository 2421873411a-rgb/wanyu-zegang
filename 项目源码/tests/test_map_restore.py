from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MaintainableMapRestoreTests(unittest.TestCase):
    def test_maintainable_template_exposes_the_restored_map_view_contract(self) -> None:
        source = (ROOT / "tools" / "anhui_web" / "templates" / "maintainable-site.js").read_text(encoding="utf-8")
        for marker in (
            "data-maintain-view=\"jobs_map\"",
            "renderMap",
            "data-maint-map-region",
            "data-maint-map-city",
            "data/map/anhui.json",
        ):
            self.assertIn(marker, source, marker)

    def test_map_builder_projects_the_source_geojson_without_job_data(self) -> None:
        from tools.anhui_web.build_map import build_map_payload

        payload = build_map_payload(ROOT)
        expected = {"合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城"}
        self.assertEqual(payload["schema"], "wanyu-maintainable-map/v1")
        self.assertEqual(payload["source_module"], "tools/anhui_web/data/anhui_340000_full.json")
        self.assertEqual(payload["feature_count"], 16)
        self.assertEqual({item["city"] for item in payload["features"]}, expected)
        self.assertTrue(all(item["d"].startswith("M") and item["x"] > 0 and item["y"] > 0 for item in payload["features"]))


if __name__ == "__main__":
    unittest.main()
