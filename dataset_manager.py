#!/usr/bin/env python3
"""
dataset_manager.py
earthquake_history.json dosyasının yönetimi.
Veri ekleme, duplicate kontrolü (eventID, timestamp, lat/lon), veri yükleme.
Multi-source spatio-temporal dedup: distance<10km, time<60s, mag<0.2
"""

import os
import json
import time
import math
from typing import List, Dict, Any, Set, Tuple, Optional

# Varsayılan veri seti dosyası
DEFAULT_DATASET_FILE = 'earthquake_history.json'
MAX_RECORDS = 200000  # 100k+ archive için (collect_large_dataset.py)

# Multi-source dedup eşikleri (aynı deprem = tek event)
DEDUP_DISTANCE_KM = 10.0
DEDUP_TIME_SEC = 60
DEDUP_MAG_DIFF = 0.2


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki nokta arası mesafe (km)."""
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def _get_eq_coords_ts_mag(eq: Dict) -> Tuple[Optional[float], Optional[float], float, float]:
    """(lat, lon, timestamp, mag) döndürür."""
    if not eq.get('geojson') or not eq['geojson'].get('coordinates'):
        return None, None, 0.0, 0.0
    lon, lat = eq['geojson']['coordinates']
    ts = eq.get('timestamp') or eq.get('created_at') or 0
    if isinstance(ts, str):
        ts = 0
    mag = float(eq.get('mag', 0) or 0)
    return lat, lon, float(ts), mag


def _is_same_event(eq1: Dict, eq2: Dict) -> bool:
    """
    Aynı deprem mi? Spatio-temporal threshold:
    distance < 10km, time_diff < 60s, magnitude_diff < 0.2
    """
    lat1, lon1, ts1, mag1 = _get_eq_coords_ts_mag(eq1)
    lat2, lon2, ts2, mag2 = _get_eq_coords_ts_mag(eq2)
    if lat1 is None or lat2 is None:
        return False
    dist = _haversine_km(lat1, lon1, lat2, lon2)
    time_diff = abs(ts1 - ts2) if ts1 and ts2 else 999
    mag_diff = abs(mag1 - mag2)
    return dist < DEDUP_DISTANCE_KM and time_diff < DEDUP_TIME_SEC and mag_diff < DEDUP_MAG_DIFF


def deduplicate_earthquakes(earthquakes: List[Dict]) -> List[Dict]:
    """
    Multi-source listesinden duplicate'leri kaldırır.
    Aynı event (distance<10km, time<60s, mag_diff<0.2) tek kayıt olarak tutulur.
    """
    if not earthquakes:
        return []
    unique = []
    for eq in earthquakes:
        merged = False
        for u in unique:
            if _is_same_event(eq, u):
                # Kaynakları birleştir
                if 'sources' not in u:
                    u['sources'] = [u.get('source', 'unknown')]
                u['sources'] = list(set(u['sources'] + [eq.get('source', 'unknown')]))
                merged = True
                break
        if not merged:
            eq = eq.copy()
            eq.setdefault('sources', [eq.get('source', 'unknown')])
            unique.append(eq)
    return unique


def _get_earthquake_id(eq: Dict) -> str:
    """
    Deprem kaydı için benzersiz ID oluşturur.
    eventID, earthquake_id veya lat/lon/timestamp kullanır.
    """
    # Öncelik: earthquake_id (Kandilli API) veya eventID
    eq_id = eq.get('earthquake_id') or eq.get('eventID')
    if eq_id:
        return str(eq_id)
    
    # Fallback: lat, lon, timestamp
    if eq.get('geojson') and eq['geojson'].get('coordinates'):
        lon, lat = eq['geojson']['coordinates']
        mag = eq.get('mag', 0)
        ts = eq.get('created_at', eq.get('timestamp', eq.get('date_time', '')))
        return f"{mag}_{lat:.4f}_{lon:.4f}_{ts}"
    
    # Şehir bazlı kayıtlar için
    if 'city' in eq and 'features' in eq:
        lat = eq.get('lat', 0)
        lon = eq.get('lon', 0)
        ts = eq.get('timestamp', 0)
        return f"city_{eq['city']}_{lat:.4f}_{lon:.4f}_{ts:.0f}"
    
    return str(id(eq))


def _get_record_id(record: Dict) -> str:
    """Herhangi bir kayıt için ID döndürür."""
    if 'geojson' in record:
        return _get_earthquake_id(record)
    if 'features' in record:
        return f"city_{record.get('city','')}_{record.get('lat',0):.4f}_{record.get('lon',0):.4f}_{record.get('timestamp',0):.0f}"
    return str(id(record))


def load_dataset(filepath: str = DEFAULT_DATASET_FILE) -> List[Dict]:
    """
    Veri seti dosyasını yükler.
    
    Args:
        filepath: JSON dosya yolu
    
    Returns:
        Veri seti listesi (dosya yoksa boş liste)
    """
    if not os.path.exists(filepath):
        print(f"[DATASET_MANAGER] Dosya bulunamadı: {filepath}")
        return []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            print(f"[DATASET_MANAGER] {len(data)} kayıt yüklendi")
            return data
        print("[DATASET_MANAGER] Geçersiz veri formatı")
        return []
    except Exception as e:
        print(f"[DATASET_MANAGER] Yükleme hatası: {e}")
        return []


def get_existing_ids(data: List[Dict]) -> Set[str]:
    """
    Mevcut verideki tüm kayıt ID'lerini döndürür.
    Duplicate kontrolü için kullanılır.
    """
    seen = set()
    for record in data:
        rid = _get_record_id(record)
        seen.add(rid)
    return seen


def is_duplicate(record: Dict, existing_ids: Set[str]) -> bool:
    """eventID/earthquake_id bazlı duplicate kontrolü."""
    rid = _get_record_id(record)
    return rid in existing_ids


def is_duplicate_spatiotemporal(record: Dict, existing_data: List[Dict]) -> bool:
    """
    Spatio-temporal duplicate: distance<10km, time<60s, mag_diff<0.2.
    Aynı deprem farklı kaynaklarda farklı ID ile gelebilir.
    """
    if not record.get('geojson') or not record['geojson'].get('coordinates'):
        return False
    for ex in existing_data:
        if ex.get('geojson') and ex['geojson'].get('coordinates'):
            if _is_same_event(record, ex):
                return True
    return False


def add_earthquakes(
    earthquakes: List[Dict],
    filepath: str = DEFAULT_DATASET_FILE,
    source: str = 'kandilli'
) -> Tuple[int, int]:
    """
    Yeni deprem verilerini veri setine ekler.
    Duplicate: eventID + spatio-temporal (distance<10km, time<60s, mag<0.2)
    
    Returns:
        (eklenen_sayisi, toplam_kayit)
    """
    # Önce gelen listeyi multi-source dedup ile temizle
    earthquakes = deduplicate_earthquakes(earthquakes)
    
    existing_data = load_dataset(filepath)
    existing_ids = get_existing_ids(existing_data)
    
    added = 0
    newly_added = []
    for eq in earthquakes:
        if not eq.get('geojson') or not eq['geojson'].get('coordinates'):
            continue
        
        # Duplicate: ID veya spatio-temporal
        if is_duplicate(eq, existing_ids):
            continue
        if is_duplicate_spatiotemporal(eq, existing_data):
            continue
        
        record = eq.copy()
        record['source'] = eq.get('source', source) if source == 'multi' else source
        record['collected_at'] = time.time()
        if 'timestamp' not in record and 'created_at' in record:
            record['timestamp'] = record['created_at']
        
        existing_data.append(record)
        existing_ids.add(_get_record_id(record))
        newly_added.append(record)
        added += 1
    
    if added > 0:
        # Opsiyonel: PostgreSQL'e de yaz (DATABASE_URL varsa)
        try:
            from db_store import is_db_available, add_earthquakes_db
            if is_db_available():
                add_earthquakes_db(newly_added)
        except ImportError:
            pass

        # Maksimum kayıt limiti
        if len(existing_data) > MAX_RECORDS:
            existing_data = existing_data[-MAX_RECORDS:]
            print(f"[DATASET_MANAGER] Veri seti {MAX_RECORDS} kayıtla sınırlandırıldı")
        
        save_dataset(existing_data, filepath)
        print(f"[DATASET_MANAGER] {added} yeni deprem verisi eklendi. Toplam: {len(existing_data)}")
    
    return added, len(existing_data)


def add_training_records(
    records: List[Dict],
    filepath: str = DEFAULT_DATASET_FILE
) -> Tuple[int, int]:
    """
    Şehir bazlı eğitim kayıtlarını (features + risk_score) ekler.
    
    Args:
        records: Eğitim kayıtları listesi
        filepath: Veri seti dosyası
    
    Returns:
        (eklenen_sayisi, toplam_kayit)
    """
    existing_data = load_dataset(filepath)
    existing_ids = get_existing_ids(existing_data)
    
    added = 0
    for rec in records:
        if 'features' not in rec or 'risk_score' not in rec:
            continue
        if is_duplicate(rec, existing_ids):
            continue
        
        rec['timestamp'] = rec.get('timestamp', time.time())
        existing_data.append(rec)
        existing_ids.add(_get_record_id(rec))
        added += 1
    
    if added > 0:
        if len(existing_data) > MAX_RECORDS:
            existing_data = existing_data[-MAX_RECORDS:]
        save_dataset(existing_data, filepath)
        print(f"[DATASET_MANAGER] {added} eğitim kaydı eklendi. Toplam: {len(existing_data)}")
    
    return added, len(existing_data)


def save_dataset(data: List[Dict], filepath: str = DEFAULT_DATASET_FILE) -> bool:
    """
    Veri setini dosyaya kaydeder.
    
    Returns:
        Başarılı ise True
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[DATASET_MANAGER] Kaydetme hatası: {e}")
        return False


def get_raw_earthquakes(data: List[Dict]) -> List[Dict]:
    """Ham deprem verilerini (geojson) döndürür."""
    return [r for r in data if r.get('geojson') and r['geojson'].get('coordinates')]


def get_training_records(filepath: str = DEFAULT_DATASET_FILE,
                        expand_raw_to_training: bool = True) -> List[Dict]:
    """
    Tüm eğitim için kullanılabilir kayıtları döndürür.
    - features + risk_score içeren kayıtlar
    - expand_raw_to_training: Ham deprem verisinden şehir bazlı eğitim kaydı üret
    """
    data = load_dataset(filepath)
    training = [r for r in data if 'features' in r and 'risk_score' in r]

    # Ham deprem verisinden ek eğitim kaydı oluştur - TÜM VERİYİ KULLAN (zaman pencereli)
    raw_eqs = get_raw_earthquakes(data)
    if expand_raw_to_training and raw_eqs:
        try:
            from earthquake_features import create_training_records_from_earthquakes
            extra = create_training_records_from_earthquakes(raw_eqs)
            training.extend(extra)
        except ImportError:
            pass

    # Profesyonel log
    print(f"[DATASET_MANAGER] Toplam ham kayıt: {len(raw_eqs)}")
    print(f"[DATASET_MANAGER] Toplam eğitim kaydı: {len(training)}")
    return training


def get_dataset_stats(filepath: str = DEFAULT_DATASET_FILE) -> Dict[str, Any]:
    """Veri seti istatistiklerini döndürür."""
    data = load_dataset(filepath)
    training_count = sum(1 for r in data if 'features' in r)
    earthquake_count = sum(1 for r in data if 'geojson' in r or r.get('source') == 'kandilli')
    synthetic_count = sum(1 for r in data if r.get('source') == 'synthetic')
    
    file_size = 0
    if os.path.exists(filepath):
        file_size = os.path.getsize(filepath) / 1024  # KB
    
    return {
        'total_records': len(data),
        'training_records': training_count,
        'earthquake_raw': earthquake_count,
        'synthetic': synthetic_count,
        'file_size_kb': round(file_size, 2),
        'filepath': filepath
    }


if __name__ == "__main__":
    stats = get_dataset_stats()
    print("Veri seti istatistikleri:", stats)
