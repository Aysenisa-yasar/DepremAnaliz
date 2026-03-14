# forecast/faults.py - Gerçek fay geometrisi (GeoJSON/SHP); yoksa 999.0 / unknown
import os
from functools import lru_cache

from shapely.geometry import Point

from config import FAULTS_GEOJSON, FAULTS_SHP


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

    gdf = gpd.read_file(path)
    if gdf.empty:
        return None

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    return gdf


def nearest_fault_distance_km(lat: float, lon: float) -> float:
    gdf = load_fault_geometries()
    if gdf is None:
        return 999.0

    gpd = _load_geopandas()
    point = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")

    gdf_m = gdf.to_crs(epsg=3857)
    point_m = point.to_crs(epsg=3857)

    distances = gdf_m.distance(point_m.iloc[0])
    if distances.empty:
        return 999.0

    return float(distances.min() / 1000.0)


def nearest_fault_segment_info(lat: float, lon: float) -> dict:
    gdf = load_fault_geometries()
    if gdf is None:
        return {"distance_km": 999.0, "segment_name": "unknown"}

    gpd = _load_geopandas()
    point = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")

    gdf_m = gdf.to_crs(epsg=3857)
    point_m = point.to_crs(epsg=3857)

    distances = gdf_m.distance(point_m.iloc[0])
    if distances.empty:
        return {"distance_km": 999.0, "segment_name": "unknown"}

    idx = distances.idxmin()
    row = gdf.iloc[idx]

    seg_name = None
    for col in ("name", "fault_name", "segment", "segment_name", "id"):
        if col in row.index and row[col] not in (None, ""):
            seg_name = str(row[col])
            break

    if not seg_name:
        seg_name = f"segment_{idx}"

    return {
        "distance_km": float(distances.loc[idx] / 1000.0),
        "segment_name": seg_name,
    }
