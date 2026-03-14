# forecast/targets.py - Hedef değişkenleri (binary: sonraki pencerede M>=X, Y km içinde)
from forecast.features import haversine_km


def build_binary_target(
    events: list,
    lat: float,
    lon: float,
    ref_ts: float,
    horizon_hours: float,
    dist_km: float,
    min_mag: float,
) -> int:
    """
    ref_ts sonrası horizon_hours içinde, dist_km yarıçapta min_mag üstü deprem var mı? 0/1.
    """
    horizon_end = ref_ts + horizon_hours * 3600
    for e in events:
        ts = e.get("timestamp") or 0
        if ts <= ref_ts:
            continue
        if ts > horizon_end:
            continue
        if (e.get("mag") or 0) < min_mag:
            continue
        elat = float(e.get("lat", 0))
        elon = float(e.get("lon", 0))
        if haversine_km(lat, lon, elat, elon) > dist_km:
            continue
        return 1
    return 0
