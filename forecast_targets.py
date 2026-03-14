#!/usr/bin/env python3
"""
forecast_targets.py
Geleceğe dönük deprem hedefleri (binary, count, max magnitude).
Eğitimde gerçek forecast label üretmek için kullanılır.
"""
import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki nokta arası mesafe (km)."""
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def build_binary_target(
    events: list,
    center_lat: float,
    center_lon: float,
    ref_ts: float,
    horizon_hours: int = 24,
    radius_km: float = 100,
    min_mag: float = 4.0,
) -> int:
    """ref_ts sonrası horizon_hours içinde radius_km'de min_mag üstü deprem oldu mu? 0/1."""
    horizon_end = ref_ts + horizon_hours * 3600
    for eq in events:
        ts = eq.get("timestamp", 0)
        if ts <= ref_ts or ts > horizon_end:
            continue
        dist = haversine_km(center_lat, center_lon, eq["lat"], eq["lon"])
        if dist <= radius_km and eq.get("mag", 0) >= min_mag:
            return 1
    return 0


def build_count_target(
    events: list,
    center_lat: float,
    center_lon: float,
    ref_ts: float,
    horizon_hours: int = 24,
    radius_km: float = 100,
    min_mag: float = 2.5,
) -> int:
    """ref_ts sonrası horizon_hours içinde radius_km'de min_mag üstü deprem sayısı."""
    horizon_end = ref_ts + horizon_hours * 3600
    count = 0
    for eq in events:
        ts = eq.get("timestamp", 0)
        if ts <= ref_ts or ts > horizon_end:
            continue
        dist = haversine_km(center_lat, center_lon, eq["lat"], eq["lon"])
        if dist <= radius_km and eq.get("mag", 0) >= min_mag:
            count += 1
    return count


def build_maxmag_target(
    events: list,
    center_lat: float,
    center_lon: float,
    ref_ts: float,
    horizon_hours: int = 168,
    radius_km: float = 150,
) -> float:
    """ref_ts sonrası horizon_hours içinde radius_km'de maksimum büyüklük."""
    horizon_end = ref_ts + horizon_hours * 3600
    mags = []
    for eq in events:
        ts = eq.get("timestamp", 0)
        if ts <= ref_ts or ts > horizon_end:
            continue
        dist = haversine_km(center_lat, center_lon, eq["lat"], eq["lon"])
        if dist <= radius_km:
            mags.append(float(eq.get("mag", 0)))
    return max(mags) if mags else 0.0
