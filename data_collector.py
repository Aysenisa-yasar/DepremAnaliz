#!/usr/bin/env python3
"""
data_collector.py
Kandilli Rasathanesi API'lerinden deprem verisi çekme modülü.
Live ve Archive API'lerini kullanır, sentetik veri üretimi destekler.
"""

import requests
import time
import numpy as np
from typing import List, Dict, Any, Optional

# API URL'leri
KANDILLI_LIVE_API = 'https://api.orhanaydogdu.com.tr/deprem/kandilli/live'
KANDILLI_ARCHIVE_API = 'https://api.orhanaydogdu.com.tr/deprem/kandilli/archive'


def fetch_from_api(url: str, max_retries: int = 3, timeout: int = 60) -> List[Dict]:
    """
    Belirtilen API URL'inden deprem verisi çeker.
    Retry mekanizması ile hata toleransı sağlar.
    
    Args:
        url: API endpoint URL'i
        max_retries: Maksimum deneme sayısı
        timeout: İstek zaman aşımı (saniye)
    
    Returns:
        Deprem verileri listesi
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            })
            response.raise_for_status()
            data = response.json().get('result', [])
            return data if isinstance(data, list) else []
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"[DATA_COLLECTOR] API timeout, {wait_time}s bekleniyor... (Deneme {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print("[DATA_COLLECTOR] API timeout: Tüm denemeler başarısız")
                return []
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"[DATA_COLLECTOR] API hatası: {e}, {wait_time}s bekleniyor...")
                time.sleep(wait_time)
            else:
                print(f"[DATA_COLLECTOR] API hatası: {e}")
                return []
    return []


def fetch_live_data() -> List[Dict]:
    """
    Kandilli Live API'den canlı deprem verilerini çeker.
    Her 30 dakikada bir çağrılmalıdır.
    
    Returns:
        Canlı deprem verileri listesi
    """
    print("[DATA_COLLECTOR] Kandilli Live API'den veri çekiliyor...")
    earthquakes = fetch_from_api(KANDILLI_LIVE_API, max_retries=2, timeout=60)
    print(f"[DATA_COLLECTOR] Live API: {len(earthquakes)} deprem verisi alındı")
    return earthquakes


def fetch_archive_data() -> List[Dict]:
    """
    Kandilli Archive API'den tarihsel deprem verilerini çeker.
    Daha geniş veri seti için kullanılır.
    
    Returns:
        Arşiv deprem verileri listesi
    """
    print("[DATA_COLLECTOR] Kandilli Archive API'den veri çekiliyor...")
    earthquakes = fetch_from_api(KANDILLI_ARCHIVE_API, max_retries=2, timeout=60)
    print(f"[DATA_COLLECTOR] Archive API: {len(earthquakes)} deprem verisi alındı")
    return earthquakes


def fetch_all_kandilli_data() -> List[Dict]:
    """
    Hem Live hem Archive API'den veri çeker ve birleştirir.
    Duplicate kontrolü yapılmaz (dataset_manager'da yapılır).
    
    Returns:
        Birleştirilmiş deprem verileri listesi
    """
    live_data = fetch_live_data()
    time.sleep(1)  # API'ye yük bindirmemek için
    archive_data = fetch_archive_data()
    
    # Geçici ID seti ile duplicate'leri burada da filtreleyebiliriz
    all_earthquakes = []
    seen_ids = set()
    
    for eq in live_data + archive_data:
        eq_id = eq.get('earthquake_id') or eq.get('eventID') or _generate_eq_id(eq)
        if eq_id not in seen_ids:
            seen_ids.add(eq_id)
            # Timestamp ekle (API'de created_at varsa kullan)
            if 'timestamp' not in eq and 'created_at' in eq:
                eq = eq.copy()
                eq['timestamp'] = eq['created_at']
            all_earthquakes.append(eq)
    
    print(f"[DATA_COLLECTOR] Toplam {len(all_earthquakes)} benzersiz deprem verisi")
    return all_earthquakes


def _generate_eq_id(eq: Dict) -> str:
    """eventID yoksa lat/lon/timestamp ile ID oluşturur."""
    if eq.get('geojson') and eq['geojson'].get('coordinates'):
        lon, lat = eq['geojson']['coordinates']
        mag = eq.get('mag', 0)
        ts = eq.get('created_at', eq.get('timestamp', eq.get('date_time', '')))
        return f"{mag}_{lat:.4f}_{lon:.4f}_{ts}"
    return str(id(eq))


def generate_synthetic_data(num_samples: int = 500) -> List[Dict]:
    """
    Gerçek veri az olduğunda sentetik eğitim verisi üretir.
    Türkiye koordinat aralıklarında gerçekçi senaryolar oluşturur.
    
    Args:
        num_samples: Üretilecek örnek sayısı
    
    Returns:
        Şehir bazlı sentetik eğitim verileri (features + risk_score formatında)
    """
    print(f"[DATA_COLLECTOR] {num_samples} sentetik örnek üretiliyor...")
    
    # app modülünden TURKEY_CITIES ve extract_features gerekli
    try:
        from app import TURKEY_CITIES, TURKEY_FAULT_LINES
    except ImportError:
        print("[DATA_COLLECTOR] app modülü yüklenemedi, basit sentetik veri üretiliyor")
        return _generate_simple_synthetic(num_samples)
    
    synthetic_data = []
    lat_range = (36.0, 42.0)
    lon_range = (26.0, 45.0)
    
    scenarios = [
        {'name': 'normal', 'prob': 0.5, 'mag_range': (2.0, 4.5), 'count_range': (0, 15)},
        {'name': 'active', 'prob': 0.3, 'mag_range': (3.0, 5.5), 'count_range': (10, 30)},
        {'name': 'high_risk', 'prob': 0.15, 'mag_range': (4.0, 6.5), 'count_range': (20, 50)},
        {'name': 'critical', 'prob': 0.05, 'mag_range': (5.0, 7.0), 'count_range': (30, 80)}
    ]
    
    cities = list(TURKEY_CITIES.keys())
    
    for i in range(min(num_samples, len(cities) * 3)):  # Şehir sayısının 3 katı kadar
        city_name = cities[i % len(cities)]
        city_data = TURKEY_CITIES[city_name]
        lat = city_data['lat']
        lon = city_data['lon']
        
        rand = np.random.random()
        cumsum = 0
        scenario = scenarios[0]
        for s in scenarios:
            cumsum += s['prob']
            if rand <= cumsum:
                scenario = s
                break
        
        count = np.random.randint(scenario['count_range'][0], scenario['count_range'][1] + 1)
        max_magnitude = np.random.uniform(scenario['mag_range'][0], scenario['mag_range'][1])
        mean_magnitude = max_magnitude * np.random.uniform(0.65, 0.85)
        std_magnitude = mean_magnitude * np.random.uniform(0.15, 0.35)
        
        if scenario['name'] in ['high_risk', 'critical']:
            min_distance = np.random.uniform(5, 50)
            mean_distance = min_distance * np.random.uniform(1.5, 3.0)
        else:
            min_distance = np.random.uniform(20, 200)
            mean_distance = min_distance * np.random.uniform(1.8, 2.8)
        
        nearest_fault = float('inf')
        for fault in TURKEY_FAULT_LINES:
            for coord in fault['coords']:
                fault_lat, fault_lon = coord
                dist = _haversine(lat, lon, fault_lat, fault_lon)
                nearest_fault = min(nearest_fault, dist)
        
        features = {
            'count': count,
            'max_magnitude': max_magnitude,
            'mean_magnitude': mean_magnitude,
            'std_magnitude': std_magnitude,
            'min_distance': min_distance,
            'mean_distance': mean_distance,
            'mean_depth': np.random.uniform(5, 35),
            'mean_interval': np.random.uniform(200, 7200),
            'min_interval': np.random.uniform(60, 1800),
            'mag_above_4': int(count * 0.2) if max_magnitude >= 4 else 0,
            'mag_above_5': int(count * 0.1) if max_magnitude >= 5 else 0,
            'mag_above_6': 0,
            'within_50km': int(count * 0.3),
            'within_100km': int(count * 0.5),
            'within_150km': int(count * 0.7),
            'nearest_fault_distance': nearest_fault,
            'activity_density': count / (np.pi * (mean_distance ** 2) + 1),
            'magnitude_distance_ratio': max_magnitude / (min_distance + 1),
            'magnitude_trend': np.random.uniform(-0.5, 0.5)
        }
        
        # Risk skoru hesapla (0-10)
        risk_score = min(10, max(0, 
            max_magnitude * 0.5 + (1 / (min_distance + 1)) * 50 + 
            count * 0.05 + (1 / (nearest_fault + 1)) * 30
        ))
        
        synthetic_data.append({
            'city': city_name,
            'lat': lat,
            'lon': lon,
            'features': features,
            'risk_score': round(risk_score, 1),
            'timestamp': time.time(),
            'source': 'synthetic'
        })
    
    print(f"[DATA_COLLECTOR] {len(synthetic_data)} sentetik örnek üretildi")
    return synthetic_data


def _generate_simple_synthetic(num_samples: int) -> List[Dict]:
    """app yoksa basit sentetik veri."""
    synthetic_data = []
    for i in range(num_samples):
        synthetic_data.append({
            'city': f'Synthetic_{i}',
            'lat': np.random.uniform(36, 42),
            'lon': np.random.uniform(26, 45),
            'features': {
                'count': np.random.randint(0, 30),
                'max_magnitude': np.random.uniform(2, 6),
                'mean_magnitude': np.random.uniform(1, 5),
                'std_magnitude': np.random.uniform(0, 1),
                'min_distance': np.random.uniform(10, 200),
                'mean_distance': np.random.uniform(50, 250),
                'mean_depth': np.random.uniform(5, 35),
                'mean_interval': 3600,
                'min_interval': 600,
                'mag_above_4': np.random.randint(0, 5),
                'mag_above_5': np.random.randint(0, 2),
                'mag_above_6': 0,
                'within_50km': np.random.randint(0, 10),
                'within_100km': np.random.randint(0, 20),
                'within_150km': np.random.randint(0, 30),
                'nearest_fault_distance': np.random.uniform(20, 150),
                'activity_density': np.random.uniform(0, 0.01),
                'magnitude_distance_ratio': np.random.uniform(0, 0.1),
                'magnitude_trend': np.random.uniform(-0.5, 0.5)
            },
            'risk_score': round(np.random.uniform(1, 8), 1),
            'timestamp': time.time(),
            'source': 'synthetic'
        })
    return synthetic_data


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki nokta arası mesafe (km)."""
    R = 6371
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2)
    lon2_rad = np.radians(lon2)
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c


if __name__ == "__main__":
    # Test
    live = fetch_live_data()
    print(f"Live: {len(live)} kayıt")
    if live:
        print(f"Örnek: {live[0].get('earthquake_id', 'N/A')}")
