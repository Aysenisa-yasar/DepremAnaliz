#!/usr/bin/env python3
"""
dataset_manager.py
earthquake_history.json dosyasının yönetimi.
Veri ekleme, duplicate kontrolü (eventID, timestamp, lat/lon), veri yükleme.
"""

import os
import json
import time
from typing import List, Dict, Any, Set, Tuple

# Varsayılan veri seti dosyası
DEFAULT_DATASET_FILE = 'earthquake_history.json'
MAX_RECORDS = 50000  # Maksimum kayıt sayısı (en eski silinir)


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
    """
    Kayıt duplicate mi kontrol eder.
    eventID/earthquake_id, timestamp, lat/lon bazlı kontrol.
    
    Args:
        record: Kontrol edilecek kayıt
        existing_ids: Mevcut ID'ler seti
    
    Returns:
        True ise duplicate
    """
    rid = _get_record_id(record)
    return rid in existing_ids


def add_earthquakes(
    earthquakes: List[Dict],
    filepath: str = DEFAULT_DATASET_FILE,
    source: str = 'kandilli'
) -> Tuple[int, int]:
    """
    Yeni deprem verilerini veri setine ekler.
    Duplicate kontrolü: eventID/earthquake_id, timestamp, lat/lon
    
    Args:
        earthquakes: Eklenecek deprem listesi (Kandilli API formatında)
        filepath: Veri seti dosyası
        source: Veri kaynağı etiketi
    
    Returns:
        (eklenen_sayisi, toplam_kayit)
    """
    existing_data = load_dataset(filepath)
    existing_ids = get_existing_ids(existing_data)
    
    added = 0
    for eq in earthquakes:
        if not eq.get('geojson') or not eq['geojson'].get('coordinates'):
            continue
        
        # Duplicate kontrolü
        if is_duplicate(eq, existing_ids):
            continue
        
        record = eq.copy()
        record['source'] = source
        record['collected_at'] = time.time()
        if 'timestamp' not in record and 'created_at' in record:
            record['timestamp'] = record['created_at']
        
        existing_data.append(record)
        existing_ids.add(_get_record_id(record))
        added += 1
    
    if added > 0:
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


def get_training_records(filepath: str = DEFAULT_DATASET_FILE) -> List[Dict]:
    """
    Sadece eğitim için kullanılabilir kayıtları döndürür.
    (features ve risk_score içeren kayıtlar)
    """
    data = load_dataset(filepath)
    training = [r for r in data if 'features' in r and 'risk_score' in r]
    print(f"[DATASET_MANAGER] {len(training)} eğitim kaydı hazır")
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
