# services/data_service.py - Veri fusion (Kandilli + USGS + AFAD + dosya), dedup, cache, kalite filtresi
import json
import time
from datetime import datetime

import requests

from config import (
    KANDILLI_API,
    USGS_API,
    AFAD_API,
    EARTHQUAKE_HISTORY_FILE,
)

_EVENTS_CACHE = {
    "data": None,
    "timestamp": 0.0,
    "ttl": 300.0,
}


def _parse_timestamp(eq: dict) -> float:
    for key in ("timestamp", "created_at", "_parsed_timestamp"):
        v = eq.get(key)
        if v is None:
            continue
        try:
            t = float(v)
            if t > 1e12:
                t = t / 1000.0
            return t
        except (TypeError, ValueError):
            pass
    date_str = eq.get("date") or ""
    time_str = eq.get("time") or ""
    if date_str:
        s = f"{date_str} {time_str}".strip()
        for fmt in ("%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y.%m.%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).timestamp()
            except Exception:
                continue
    return 0.0


def _normalize_event(eq: dict) -> dict | None:
    coords = None
    if eq.get("geojson") and eq["geojson"].get("coordinates"):
        coords = eq["geojson"]["coordinates"]
    if not coords:
        lat, lon = eq.get("lat"), eq.get("lon") or eq.get("lng")
        if lat is not None and lon is not None:
            coords = [float(lon), float(lat)]
    if not coords:
        return None
    lon, lat = float(coords[0]), float(coords[1])
    mag = float(eq.get("mag", eq.get("magnitude", 0)) or 0)
    depth = float(eq.get("depth", 10) or 10)
    ts = _parse_timestamp(eq)
    if ts <= 0:
        return None
    return {"lat": lat, "lon": lon, "mag": mag, "depth": depth, "timestamp": ts}


def _normalize_usgs_feature(feature: dict) -> dict | None:
    try:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            return None
        lon, lat = float(coords[0]), float(coords[1])
        depth = float(coords[2]) if len(coords) > 2 else 10.0
        mag = float(props.get("mag", 0) or 0)
        ts_ms = props.get("time")
        ts = float(ts_ms) / 1000.0 if ts_ms else 0.0
        if ts <= 0:
            return None
        return {"lat": lat, "lon": lon, "mag": mag, "depth": depth, "timestamp": ts}
    except Exception:
        return None


def _quality_filter(events: list, min_mag: float = 1.5) -> list:
    out = []
    for e in events:
        if float(e.get("mag", 0) or 0) < min_mag:
            continue
        out.append(e)
    return out


def _dedup_events(events: list) -> list:
    seen = set()
    out = []
    for e in events:
        key = (
            round(e["lat"], 3),
            round(e["lon"], 3),
            round(e["mag"], 1),
            int(round(e["timestamp"] / 60.0)),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    out.sort(key=lambda x: x["timestamp"])
    return out


def load_events_from_kandilli(timeout: int = 30) -> list:
    try:
        r = requests.get(KANDILLI_API, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    items = data.get("result", data.get("data", [])) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    events = []
    for eq in items:
        e = _normalize_event(eq)
        if e:
            events.append(e)
    return events


def load_events_from_usgs(timeout: int = 30) -> list:
    try:
        r = requests.get(USGS_API, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    features = data.get("features", []) if isinstance(data, dict) else []
    events = []
    for f in features:
        e = _normalize_usgs_feature(f)
        if e:
            events.append(e)
    return events


def load_events_from_afad(timeout: int = 30) -> list:
    if not AFAD_API:
        return []
    try:
        r = requests.get(AFAD_API, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    items = data if isinstance(data, list) else data.get("result", [])
    events = []
    for eq in items:
        e = _normalize_event(eq)
        if e:
            events.append(e)
    return events


def load_events_from_file(filepath: str | None = None) -> list:
    path = filepath or EARTHQUAKE_HISTORY_FILE
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    events = []
    for item in data:
        e = _normalize_event(item)
        if e:
            events.append(e)
    return events


def load_events(use_api: bool = True, use_file_fallback: bool = True) -> list:
    now = time.time()
    if (
        _EVENTS_CACHE["data"] is not None
        and (now - _EVENTS_CACHE["timestamp"]) < _EVENTS_CACHE["ttl"]
    ):
        return _EVENTS_CACHE["data"]

    events = []
    if use_api:
        events.extend(load_events_from_kandilli())
        events.extend(load_events_from_usgs())
        events.extend(load_events_from_afad())
    if use_file_fallback:
        events.extend(load_events_from_file())

    final_events = _dedup_events(_quality_filter(events, min_mag=1.5))
    _EVENTS_CACHE["data"] = final_events
    _EVENTS_CACHE["timestamp"] = now
    return final_events


def load_events_from_api(timeout: int = 30) -> list:
    return load_events_from_kandilli(timeout=timeout)
