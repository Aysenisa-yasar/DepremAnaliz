from forecast.features import haversine_km


def build_multi_targets(events, lat, lon, ref_ts, radius_km=100.0):
    targets = {
        "m4_24h": 0,
        "m5_72h": 0,
        "max_mag_7d": 0.0,
    }

    for event in events:
        ts = float(event.get("timestamp") or 0)
        if ts <= ref_ts:
            continue

        dt_hours = (ts - ref_ts) / 3600.0
        if dt_hours > 168.0:
            continue

        dist = haversine_km(
            lat,
            lon,
            float(event.get("lat", 0) or 0),
            float(event.get("lon", 0) or 0),
        )
        if dist > radius_km:
            continue

        mag = float(event.get("mag", 0) or 0)

        if dt_hours <= 24.0 and mag >= 4.0:
            targets["m4_24h"] = 1

        if dt_hours <= 72.0 and mag >= 5.0:
            targets["m5_72h"] = 1

        targets["max_mag_7d"] = max(targets["max_mag_7d"], mag)

    return targets
