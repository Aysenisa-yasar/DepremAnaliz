import math
import os
from functools import lru_cache

try:
    from shapely.geometry import Point
except Exception:
    Point = None

from config import FAULTS_GEOJSON, FAULTS_SHP

FALLBACK_FAULT_SEGMENTS = [
    {
        "name": "North Anatolian Fault",
        "coords": [
            (40.0, 26.0),
            (40.2, 27.0),
            (40.5, 28.0),
            (40.7, 29.0),
            (40.9, 30.0),
            (41.0, 31.0),
            (41.2, 32.0),
            (41.4, 33.0),
            (41.6, 34.0),
            (41.8, 35.0),
            (42.0, 36.0),
            (42.2, 37.0),
        ],
    },
    {
        "name": "East Anatolian Fault",
        "coords": [
            (37.0, 38.0),
            (37.5, 39.0),
            (38.0, 40.0),
            (38.5, 41.0),
            (39.0, 42.0),
            (39.5, 43.0),
            (40.0, 44.0),
        ],
    },
    {
        "name": "Aegean Graben System",
        "coords": [
            (38.0, 26.0),
            (38.5, 27.0),
            (39.0, 28.0),
            (39.5, 29.0),
        ],
    },
    {
        "name": "Western Anatolia Fault System",
        "coords": [
            (38.5, 27.0),
            (39.0, 28.5),
            (39.5, 30.0),
            (40.0, 31.5),
        ],
    },
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * radius * math.asin(math.sqrt(a))


def _polyline_distance_km(lat: float, lon: float, coords: list[tuple[float, float]]) -> float:
    if not coords:
        return 999.0

    best = float("inf")
    if len(coords) == 1:
        c_lat, c_lon = coords[0]
        return _haversine_km(lat, lon, c_lat, c_lon)

    for idx in range(len(coords) - 1):
        lat1, lon1 = coords[idx]
        lat2, lon2 = coords[idx + 1]
        for step in range(17):
            t = step / 16.0
            probe_lat = lat1 + (lat2 - lat1) * t
            probe_lon = lon1 + (lon2 - lon1) * t
            best = min(best, _haversine_km(lat, lon, probe_lat, probe_lon))

    return float(best if math.isfinite(best) else 999.0)


def _fallback_fault_info(lat: float, lon: float) -> dict:
    best_name = "unknown"
    best_distance = 999.0

    for segment in FALLBACK_FAULT_SEGMENTS:
        distance = _polyline_distance_km(lat, lon, segment["coords"])
        if distance < best_distance:
            best_distance = distance
            best_name = segment["name"]

    return {
        "distance_km": float(best_distance),
        "segment_name": best_name,
    }


@lru_cache(maxsize=1)
def _load_geopandas():
    try:
        import geopandas as gpd
        return gpd
    except Exception:
        return None


@lru_cache(maxsize=1)
def load_fault_geometries():
    gpd = _load_geopandas()
    if gpd is None:
        return None

    path = None
    if os.path.exists(FAULTS_GEOJSON):
        path = FAULTS_GEOJSON
    elif os.path.exists(FAULTS_SHP):
        path = FAULTS_SHP

    if path is None:
        return None

    try:
        gdf = gpd.read_file(path)
    except Exception:
        return None

    if gdf.empty:
        return None

    try:
        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=4326)
        else:
            gdf = gdf.to_crs(epsg=4326)
    except Exception:
        return None

    return gdf


def nearest_fault_distance_km(lat: float, lon: float) -> float:
    return float(nearest_fault_segment_info(lat, lon)["distance_km"])


def nearest_fault_segment_info(lat: float, lon: float) -> dict:
    gdf = load_fault_geometries()
    gpd = _load_geopandas()

    if gdf is None or gpd is None or Point is None:
        return _fallback_fault_info(lat, lon)

    try:
        point = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
        gdf_m = gdf.to_crs(epsg=3857)
        point_m = point.to_crs(epsg=3857)
        distances = gdf_m.distance(point_m.iloc[0])
    except Exception:
        return _fallback_fault_info(lat, lon)

    if distances.empty:
        return _fallback_fault_info(lat, lon)

    idx = distances.idxmin()
    row = gdf.loc[idx]

    seg_name = None
    for col in ("name", "fault_name", "segment", "segment_name", "id"):
        value = row[col] if col in row.index else None
        if value not in (None, ""):
            seg_name = str(value)
            break

    if not seg_name:
        seg_name = f"segment_{idx}"

    return {
        "distance_km": float(distances.loc[idx] / 1000.0),
        "segment_name": seg_name,
    }
