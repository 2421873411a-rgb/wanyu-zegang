"""Build the external, static Anhui prefecture map used by the maintainable site.

The map geometry is deliberately produced from the same GeoJSON that powered
the earlier workbench.  It contains no job counts: the browser joins this
stable geometry to the selected cycle's jobs module at render time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GEOJSON_PATH = Path(__file__).resolve().parent / "data" / "anhui_340000_full.json"
SCHEMA = "wanyu-maintainable-map/v1"
WIDTH = 640.0
HEIGHT = 660.0
PADDING = 30.0


def _geometry_rings(geometry: dict[str, Any]) -> list[list[list[float]]]:
    coordinates = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        return list(coordinates)
    if geometry.get("type") == "MultiPolygon":
        return [ring for polygon in coordinates for ring in polygon]
    return []


def _city_name(feature: dict[str, Any]) -> str:
    name = str((feature.get("properties") or {}).get("name") or "").strip()
    return name[:-1] if name.endswith("市") else name


def build_map_payload(root: Path = ROOT) -> dict[str, object]:
    """Project the source GeoJSON into a compact browser-ready map payload."""
    source_path = Path(root).resolve() / "tools" / "anhui_web" / "data" / "anhui_340000_full.json"
    if not source_path.is_file():
        raise FileNotFoundError(f"缺少安徽省地图数据：{source_path}")
    geojson = json.loads(source_path.read_text(encoding="utf-8"))
    if geojson.get("type") != "FeatureCollection":
        raise ValueError("安徽地图 GeoJSON 不是 FeatureCollection")
    source_features = geojson.get("features")
    if not isinstance(source_features, list) or not source_features:
        raise ValueError("安徽地图 GeoJSON 没有 features")

    all_points = [
        point
        for feature in source_features
        for ring in _geometry_rings(feature.get("geometry") or {})
        for point in ring
        if isinstance(point, (list, tuple)) and len(point) >= 2
    ]
    if not all_points:
        raise ValueError("安徽地图 GeoJSON 没有可投影坐标")
    min_lon = min(float(point[0]) for point in all_points)
    max_lon = max(float(point[0]) for point in all_points)
    min_lat = min(float(point[1]) for point in all_points)
    max_lat = max(float(point[1]) for point in all_points)
    scale = min(
        (WIDTH - PADDING * 2) / (max_lon - min_lon),
        (HEIGHT - PADDING * 2) / (max_lat - min_lat),
    )
    draw_width = (max_lon - min_lon) * scale
    draw_height = (max_lat - min_lat) * scale
    offset_x = (WIDTH - draw_width) / 2
    offset_y = (HEIGHT - draw_height) / 2

    def project(point: list[float] | tuple[float, ...]) -> tuple[float, float]:
        lon, lat = float(point[0]), float(point[1])
        return offset_x + (lon - min_lon) * scale, offset_y + (max_lat - lat) * scale

    def path_for(feature: dict[str, Any]) -> str:
        chunks: list[str] = []
        for ring in _geometry_rings(feature.get("geometry") or {}):
            projected = [project(point) for point in ring if len(point) >= 2]
            if not projected:
                continue
            chunks.append("M" + ",".join(f"{x:.1f} {y:.1f}" for x, y in projected) + " Z")
        return " ".join(chunks)

    features: list[dict[str, object]] = []
    seen: set[str] = set()
    for source_feature in source_features:
        city = _city_name(source_feature)
        properties = source_feature.get("properties") or {}
        center = properties.get("centroid") or properties.get("center")
        path = path_for(source_feature)
        if not city or city in seen or not path or not isinstance(center, (list, tuple)) or len(center) < 2:
            raise ValueError(f"安徽地图 feature 无法形成唯一城市几何：{city or 'unknown'}")
        x, y = project(center)
        seen.add(city)
        features.append({
            "city": city,
            "name": str(properties.get("name") or f"{city}市"),
            "adcode": properties.get("adcode"),
            "d": path,
            "x": round(x, 1),
            "y": round(y, 1),
        })
    return {
        "schema": SCHEMA,
        "source_module": "tools/anhui_web/data/anhui_340000_full.json",
        "projection": {"width": int(WIDTH), "height": int(HEIGHT), "padding": int(PADDING)},
        "feature_count": len(features),
        "features": features,
    }


if __name__ == "__main__":
    payload = build_map_payload()
    print(json.dumps({"schema": payload["schema"], "feature_count": payload["feature_count"]}, ensure_ascii=False))
