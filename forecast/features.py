# forecast/features.py - Güçlü feature seti (swarm, fay, recency energy, stress proxy)
import numpy as np

from forecast.faults import nearest_fault_distance_km, nearest_fault_segment_info


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    return 2 * R * np.arcsin(np.sqrt(a))


def extract_features(earthquakes: list, lat: float, lon: float, time_window_hours: int = 48) -> dict:
    empty_fault = nearest_fault_segment_info(lat, lon)
    default = {
        "count": 0,
        "max_mag": 0.0,
        "mean_mag": 0.0,
        "mag_std": 0.0,
        "min_distance": 999.0,
        "mean_distance": 999.0,
        "recency_energy": 0.0,
        "mean_depth": 10.0,
        "recent_6h_count": 0,
        "recent_24h_count": 0,
        "swarm_ratio": 0.0,
        "fault_distance": empty_fault["distance_km"],
        "fault_proximity_score": 0.0,
        "stress_transfer": 0.0,
        "energy_release": 0.0,
        "foreshock_count": 0,
        "spatial_density": 0.0,
        "mag_trend": 0.0,
        "depth_variance": 0.0,
        "nearest_fault_segment": empty_fault["segment_name"],
    }

    if not earthquakes:
        return default

    now = max(e.get("timestamp", 0) or 0 for e in earthquakes)
    recent = [
        e for e in earthquakes
        if (e.get("timestamp") or 0) > 0
        and (now - (e.get("timestamp") or 0)) <= time_window_hours * 3600
    ]

    fault_info = nearest_fault_segment_info(lat, lon)
    if not recent:
        return {
            **default,
            "fault_distance": fault_info["distance_km"],
            "fault_proximity_score": max(0.0, 1.0 - fault_info["distance_km"] / 100.0),
            "nearest_fault_segment": fault_info["segment_name"],
        }

    mags = [float(e.get("mag", 0) or 0) for e in recent]
    depths = [float(e.get("depth", 10) or 10) for e in recent]
    distances = [
        haversine_km(lat, lon, float(e.get("lat", 0)), float(e.get("lon", 0)))
        for e in recent
    ]

    energy = 0.0
    energy_sum = 0.0
    for e in recent:
        dt_hours = max((now - float(e.get("timestamp", 0) or 0)) / 3600.0, 1e-6)
        mag = float(e.get("mag", 0) or 0)
        ev_energy = 10 ** (1.5 * mag)
        energy += ev_energy / (1.0 + dt_hours)
        energy_sum += ev_energy

    recent_6h = [e for e in recent if now - (e.get("timestamp") or 0) <= 6 * 3600]
    recent_24h = [e for e in recent if now - (e.get("timestamp") or 0) <= 24 * 3600]
    foreshock_count = sum(1 for e in recent if 2.0 <= float(e.get("mag", 0) or 0) <= 4.0)

    mag_trend = float(mags[-1] - mags[0]) if len(mags) > 1 else 0.0
    spatial_density = float(len(recent) / (time_window_hours + 1))
    depth_variance = float(np.var(depths)) if len(depths) > 1 else 0.0

    stress_score = 0.0
    for e in recent:
        mag = float(e.get("mag", 0) or 0)
        dist = haversine_km(lat, lon, float(e.get("lat", 0)), float(e.get("lon", 0)))
        if mag >= 5.0:
            stress_score += (mag - 4.0) / (1.0 + dist)
    stress_score = float(np.tanh(stress_score / 5.0))

    fault_distance = float(fault_info["distance_km"])
    fault_proximity_score = max(0.0, 1.0 - fault_distance / 100.0)

    return {
        "count": int(len(recent)),
        "max_mag": float(np.max(mags)) if mags else 0.0,
        "mean_mag": float(np.mean(mags)) if mags else 0.0,
        "mag_std": float(np.std(mags)) if len(mags) > 1 else 0.0,
        "min_distance": float(np.min(distances)) if distances else 999.0,
        "mean_distance": float(np.mean(distances)) if distances else 999.0,
        "recency_energy": float(np.log10(energy + 1.0)),
        "mean_depth": float(np.mean(depths)) if depths else 10.0,
        "recent_6h_count": int(len(recent_6h)),
        "recent_24h_count": int(len(recent_24h)),
        "swarm_ratio": float(len(recent_6h) / len(recent_24h)) if len(recent_24h) > 0 else 0.0,
        "fault_distance": fault_distance,
        "fault_proximity_score": fault_proximity_score,
        "stress_transfer": stress_score,
        "energy_release": float(np.log10(energy_sum + 1.0)),
        "foreshock_count": int(foreshock_count),
        "spatial_density": spatial_density,
        "mag_trend": mag_trend,
        "depth_variance": depth_variance,
        "nearest_fault_segment": fault_info["segment_name"],
    }
