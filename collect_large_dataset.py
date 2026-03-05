#!/usr/bin/env python3
"""
collect_large_dataset.py
Tek komutla 100k+ deprem verisi indirir (USGS 1990-2026).
Türkiye çevresi filtre: lat 34-43, lon 25-45.
dataset_manager ile uyumlu format + spatio-temporal dedup.
"""

import requests
import time
import sys
from typing import List, Dict, Optional, Tuple

# Türkiye bbox (Ayşenisa önerisi)
LAT_MIN = 34
LAT_MAX = 43
LON_MIN = 25
LON_MAX = 45

START_YEAR = 1990
END_YEAR = 2026

USGS_BASE = "https://earthquake.usgs.gov/fdsnws/event/1/query"
LIMIT_PER_YEAR = 10000  # USGS max 20k, 10k daha güvenli


def _normalize_usgs_feature(feat: Dict) -> Optional[Dict]:
    """USGS GeoJSON feature → dataset_manager format."""
    try:
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            return None
        lon, lat = coords[0], coords[1]
        depth = abs(float(coords[2])) if len(coords) > 2 else 10
        props = feat.get("properties", {})
        mag = props.get("mag") or 0
        ts_ms = props.get("time") or 0
        ts = ts_ms / 1000.0 if ts_ms > 1e12 else ts_ms
        eq_id = feat.get("id") or f"usgs_{lat:.4f}_{lon:.4f}_{ts:.0f}"
        return {
            "earthquake_id": eq_id,
            "eventID": eq_id,
            "mag": float(mag),
            "depth": depth,
            "geojson": {"type": "Point", "coordinates": [lon, lat]},
            "timestamp": ts,
            "created_at": ts,
            "source": "usgs",
            "place": props.get("place", ""),
        }
    except Exception:
        return None


def fetch_usgs_year(year: int) -> List[Dict]:
    """USGS'ten tek yıl verisi çeker."""
    url = (
        f"{USGS_BASE}?format=geojson"
        f"&starttime={year}-01-01"
        f"&endtime={year}-12-31"
        f"&minlatitude={LAT_MIN}"
        f"&maxlatitude={LAT_MAX}"
        f"&minlongitude={LON_MIN}"
        f"&maxlongitude={LON_MAX}"
        f"&minmagnitude=2"
        f"&limit={LIMIT_PER_YEAR}"
        f"&orderby=time"
    )
    print(f"[USGS] {year} verisi çekiliyor...", end=" ", flush=True)
    try:
        r = requests.get(url, timeout=120, headers={"User-Agent": "DepremAnaliz/1.0"})
        r.raise_for_status()
        data = r.json()
        features = data.get("features", [])
        out = []
        for f in features:
            if isinstance(f, dict) and f.get("type") == "Feature":
                norm = _normalize_usgs_feature(f)
                if norm:
                    out.append(norm)
        print(f"{len(out)} deprem")
        return out
    except Exception as e:
        print(f"HATA: {e}")
        return []


def _dedup_grid_key(eq: dict) -> Optional[Tuple[float, float, int]]:
    """10km/60s grid key - hızlı bulk dedup için."""
    g = eq.get("geojson") or {}
    coords = g.get("coordinates") or []
    if len(coords) < 2:
        return None
    lon, lat = coords[0], coords[1]
    ts = eq.get("timestamp") or eq.get("created_at") or 0
    if isinstance(ts, str):
        ts = 0
    ts = float(ts)
    return (round(lat, 1), round(lon, 1), int(ts / 60))


def collect_and_save(use_dataset_manager: bool = True, start_year: int = START_YEAR, end_year: int = END_YEAR):
    """
    USGS verisini çeker ve dataset'e ekler.
    use_dataset_manager=True: hızlı bulk merge (O(n)) - 100k+ için optimize
    use_dataset_manager=False: add_earthquakes (küçük batch için)
    """
    from dataset_manager import (
        load_dataset,
        add_earthquakes,
        DEFAULT_DATASET_FILE,
        save_dataset,
    )

    existing = load_dataset(DEFAULT_DATASET_FILE)
    raw_count = sum(1 for r in existing if r.get("geojson") and r["geojson"].get("coordinates"))
    print(f"Mevcut ham deprem: {raw_count}")
    print(f"Hedef: {start_year}-{end_year} USGS (Türkiye bbox)")
    print("=" * 50)

    all_new = []
    for year in range(start_year, end_year + 1):
        eqs = fetch_usgs_year(year)
        all_new.extend(eqs)
        time.sleep(0.5)

    if not all_new:
        print("Veri alınamadı.")
        return

    # Gelen listede dedup (USGS tek kaynak, nadiren duplicate)
    from dataset_manager import deduplicate_earthquakes
    unique_new = deduplicate_earthquakes(all_new)
    print(f"Toplam çekilen: {len(all_new)} → dedup sonrası: {len(unique_new)}")

    if use_dataset_manager and len(unique_new) > 1000:
        # Hızlı bulk merge: O(n) grid-based dedup
        existing_keys = set()
        for r in existing:
            if r.get("geojson") and r["geojson"].get("coordinates"):
                k = _dedup_grid_key(r)
                if k:
                    existing_keys.add(k)
        added = 0
        for eq in unique_new:
            k = _dedup_grid_key(eq)
            if k and k not in existing_keys:
                existing_keys.add(k)
                rec = eq.copy()
                rec["source"] = rec.get("source", "usgs")
                rec["collected_at"] = time.time()
                if "timestamp" not in rec and rec.get("created_at"):
                    rec["timestamp"] = rec["created_at"]
                existing.append(rec)
                added += 1
        if added > 0:
            try:
                from db_store import is_db_available, add_earthquakes_db
                if is_db_available():
                    add_earthquakes_db([r for r in existing[-added:]])
            except ImportError:
                pass
        save_dataset(existing, DEFAULT_DATASET_FILE)
        print("=" * 50)
        print(f"Eklenen: {added} | Toplam kayıt: {len(existing)}")
    elif use_dataset_manager:
        added, total = add_earthquakes(unique_new, source="usgs")
        print("=" * 50)
        print(f"Eklenen: {added} | Toplam kayıt: {total}")
    else:
        existing_keys = set()
        for r in existing:
            if r.get("geojson"):
                k = _dedup_grid_key(r)
                if k:
                    existing_keys.add(k)
        for eq in unique_new:
            k = _dedup_grid_key(eq)
            if k and k not in existing_keys:
                existing_keys.add(k)
                rec = eq.copy()
                rec.setdefault("source", "usgs")
                rec["collected_at"] = time.time()
                if "timestamp" not in rec and rec.get("created_at"):
                    rec["timestamp"] = rec["created_at"]
                existing.append(rec)
        save_dataset(existing, DEFAULT_DATASET_FILE)
        print("=" * 50)
        print(f"Toplam kayıt: {len(existing)}")


if __name__ == "__main__":
    use_dm = "--no-dm" not in sys.argv
    sy, ey = START_YEAR, END_YEAR
    if "--test" in sys.argv:
        sy, ey = 2024, 2025
        print("[TEST] Sadece 2024-2025 çekiliyor...")
    if not use_dm:
        print("UYARI: --no-dm ile dataset_manager dedup atlanır (hızlı bulk)")
    collect_and_save(use_dataset_manager=use_dm, start_year=sy, end_year=ey)
