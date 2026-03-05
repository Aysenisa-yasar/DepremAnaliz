#!/usr/bin/env python3
"""
db_store.py
PostgreSQL opsiyonel desteği - veri büyüyünce JSON yerine DB.
Tablo: earthquakes (id, timestamp, lat, lon, depth, mag, source)
Kullanım: DATABASE_URL env varsa DB, yoksa JSON (dataset_manager).
"""

import os
from typing import List, Dict, Any, Optional, Tuple

DATABASE_URL = os.environ.get('DATABASE_URL')
USE_DB = bool(DATABASE_URL)

# psycopg2 veya sqlalchemy
try:
    import psycopg2
    HAS_PG = True
except ImportError:
    HAS_PG = False


def _get_conn():
    """PostgreSQL bağlantısı."""
    if not HAS_PG or not DATABASE_URL:
        return None
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"[DB] Bağlantı hatası: {e}")
        return None


def init_schema(conn=None) -> bool:
    """earthquakes tablosunu oluşturur."""
    if not HAS_PG:
        return False
    conn = conn or _get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS earthquakes (
                    id SERIAL PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    lat DOUBLE PRECISION NOT NULL,
                    lon DOUBLE PRECISION NOT NULL,
                    depth DOUBLE PRECISION DEFAULT 10,
                    mag DOUBLE PRECISION DEFAULT 0,
                    source VARCHAR(50),
                    event_id VARCHAR(255) UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_eq_timestamp ON earthquakes(timestamp);
                CREATE INDEX IF NOT EXISTS idx_eq_lat_lon ON earthquakes(lat, lon);
            """)
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB] Schema hatası: {e}")
        return False
    finally:
        if conn:
            conn.close()


def add_earthquakes_db(earthquakes: List[Dict]) -> Tuple[int, int]:
    """
    Depremleri DB'ye ekler. Duplicate event_id atlanır.
    Returns: (eklenen, toplam)
    """
    if not HAS_PG or not DATABASE_URL:
        return 0, 0
    conn = _get_conn()
    if not conn:
        return 0, 0
    try:
        init_schema(conn)
        rows = []
        for eq in earthquakes:
            if not eq.get('geojson') or not eq['geojson'].get('coordinates'):
                continue
            lon, lat = eq['geojson']['coordinates']
            ts = eq.get('timestamp') or eq.get('created_at') or 0
            depth = float(eq.get('depth', 10) or 10)
            mag = float(eq.get('mag', 0) or 0)
            source = eq.get('source', 'unknown')
            eid = eq.get('earthquake_id') or eq.get('eventID') or f"{lat:.4f}_{lon:.4f}_{ts}"
            rows.append((ts, lat, lon, depth, mag, source, eid))
        if not rows:
            return 0, 0
        added = 0
        with conn.cursor() as cur:
            for r in rows:
                try:
                    cur.execute("""
                        INSERT INTO earthquakes (timestamp, lat, lon, depth, mag, source, event_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (event_id) DO NOTHING
                    """, r)
                    added += cur.rowcount
                except Exception:
                    pass
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM earthquakes")
            total = cur.fetchone()[0]
        return added, total
    except Exception as e:
        print(f"[DB] Insert hatası: {e}")
        return 0, 0
    finally:
        conn.close()


def get_raw_earthquakes_db(limit: int = 50000) -> List[Dict]:
    """DB'den ham deprem listesi (geojson formatında)."""
    if not HAS_PG or not DATABASE_URL:
        return []
    conn = _get_conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT timestamp, lat, lon, depth, mag, source, event_id
                FROM earthquakes ORDER BY timestamp DESC LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
        return [
            {
                'timestamp': r[0], 'created_at': r[0],
                'geojson': {'type': 'Point', 'coordinates': [r[2], r[1]]},
                'depth': r[3], 'mag': r[4],
                'source': r[5], 'earthquake_id': r[6], 'eventID': r[6]
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[DB] Select hatası: {e}")
        return []
    finally:
        conn.close()


def is_db_available() -> bool:
    """PostgreSQL kullanılabilir mi?"""
    return bool(HAS_PG and DATABASE_URL)
