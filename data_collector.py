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

# API URL'leri - Multi-source
KANDILLI_LIVE_API = 'https://api.orhanaydogdu.com.tr/deprem/kandilli/live'
KANDILLI_ARCHIVE_API = 'https://api.orhanaydogdu.com.tr/deprem/kandilli/archive'
# orhanaydogdu /deprem/ ana endpoint: Kandilli + AFAD birleşik
ORHANAYDOGDU_ALL_API = 'https://api.orhanaydogdu.com.tr/deprem/'  # Kandilli + AFAD
ARCHIVE_LIMIT = 2000  # Tek istekte max (API ~1000-2000 destekler)
ARCHIVE_FULL_YEARS_BACK = 36  # 1990→2026 tam arşiv (USGS destekler)

# USGS - Türkiye bbox (lat 36-42, lon 26-45)
USGS_BASE = (
    'https://earthquake.usgs.gov/fdsnws/event/1/query'
    '?format=geojson&minmagnitude=2&minlatitude=36&maxlatitude=42'
    '&minlongitude=26&maxlongitude=45'
)
USGS_API = USGS_BASE + '&limit=500'
# EMSC/SeismicPortal - Türkiye bölgesi
EMSC_BASE = (
    'https://www.seismicportal.eu/fdsnws/event/1/query'
    '?format=json&minmag=2&minlat=36&maxlat=42&minlon=26&maxlon=45'
)
EMSC_API = EMSC_BASE + '&limit=500'


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


def fetch_archive_data(limit: int = ARCHIVE_LIMIT) -> List[Dict]:
    """
    Kandilli Archive API'den tarihsel deprem verilerini çeker.
    limit parametresi ile daha fazla veri alınabilir (max ~500).
    
    Returns:
        Arşiv deprem verileri listesi
    """
    print(f"[DATA_COLLECTOR] Kandilli Archive API'den veri çekiliyor (limit={limit})...")
    url = f"{KANDILLI_ARCHIVE_API}?limit={limit}" if limit else KANDILLI_ARCHIVE_API
    earthquakes = fetch_from_api(url, max_retries=2, timeout=60)
    print(f"[DATA_COLLECTOR] Archive API: {len(earthquakes)} deprem verisi alındı")
    return earthquakes


def _normalize_usgs_feature(feat: Dict) -> Optional[Dict]:
    """USGS GeoJSON feature'ı bizim formata çevirir."""
    try:
        geom = feat.get('geometry', {})
        coords = geom.get('coordinates', [])
        if len(coords) < 2:
            return None
        lon, lat = coords[0], coords[1]
        depth = coords[2] if len(coords) > 2 else 10
        props = feat.get('properties', {})
        mag = props.get('mag') or 0
        ts_ms = props.get('time') or 0
        ts = ts_ms / 1000.0 if ts_ms > 1e12 else ts_ms
        eq_id = feat.get('id') or f"usgs_{lat:.4f}_{lon:.4f}_{ts:.0f}"
        return {
            'earthquake_id': eq_id,
            'eventID': eq_id,
            'mag': mag,
            'depth': abs(float(depth)),
            'geojson': {'type': 'Point', 'coordinates': [lon, lat]},
            'timestamp': ts,
            'created_at': ts,
            'source': 'usgs'
        }
    except Exception:
        return None


def _normalize_emsc_feature(feat: Dict) -> Optional[Dict]:
    """EMSC/SeismicPortal feature'ı bizim formata çevirir (depth negatif olabilir)."""
    try:
        geom = feat.get('geometry', {})
        coords = geom.get('coordinates', [])
        if len(coords) < 2:
            return None
        lon, lat = coords[0], coords[1]
        depth_raw = coords[2] if len(coords) > 2 else -10
        depth = abs(float(depth_raw))
        props = feat.get('properties', {})
        mag = props.get('mag') or 0
        time_str = props.get('time', '')
        ts = time.time()
        if time_str:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                ts = dt.timestamp()
            except Exception:
                pass
        eq_id = feat.get('id') or props.get('unid') or f"emsc_{lat:.4f}_{lon:.4f}_{ts:.0f}"
        return {
            'earthquake_id': eq_id,
            'eventID': eq_id,
            'mag': mag,
            'depth': depth,
            'geojson': {'type': 'Point', 'coordinates': [lon, lat]},
            'timestamp': ts,
            'created_at': ts,
            'source': 'emsc'
        }
    except Exception:
        return None


def _fetch_json(url: str, max_retries: int = 2, timeout: int = 60) -> Optional[Dict]:
    """Genel JSON API çağrısı (result key beklemez)."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout, headers={
                'User-Agent': 'Mozilla/5.0 DepremAnaliz/1.0',
                'Accept': 'application/json'
            })
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep((attempt + 1) * 2)
            else:
                print(f"[DATA_COLLECTOR] API hatası: {e}")
                return None
    return None


def fetch_usgs_data(limit: int = 500) -> List[Dict]:
    """USGS API'den Türkiye bölgesi deprem verilerini çeker."""
    print(f"[DATA_COLLECTOR] USGS API'den veri çekiliyor (limit={limit})...")
    url = f"{USGS_BASE}&limit={limit}"
    raw = _fetch_json(url)
    data = raw.get('features', []) if isinstance(raw, dict) else []
    earthquakes = []
    for feat in data:
        if isinstance(feat, dict) and feat.get('type') == 'Feature':
            norm = _normalize_usgs_feature(feat)
            if norm:
                earthquakes.append(norm)
    print(f"[DATA_COLLECTOR] USGS API: {len(earthquakes)} deprem verisi alındı")
    return earthquakes


def fetch_emsc_data(limit: int = 500) -> List[Dict]:
    """EMSC/SeismicPortal API'den Türkiye bölgesi deprem verilerini çeker."""
    print(f"[DATA_COLLECTOR] EMSC API'den veri çekiliyor (limit={limit})...")
    url = f"{EMSC_BASE}&limit={limit}"
    raw = _fetch_json(url)
    data = raw.get('features', []) if isinstance(raw, dict) else []
    earthquakes = []
    for feat in data:
        if isinstance(feat, dict) and (feat.get('type') == 'Feature' or 'geometry' in feat):
            norm = _normalize_emsc_feature(feat)
            if norm:
                earthquakes.append(norm)
    print(f"[DATA_COLLECTOR] EMSC API: {len(earthquakes)} deprem verisi alındı")
    return earthquakes


def fetch_usgs_archive_full(years_back: int = ARCHIVE_FULL_YEARS_BACK) -> List[Dict]:
    """
    USGS'ten yıllara bölerek tam arşiv çeker (10k+ deprem).
    starttime/endtime ile chunked istek.
    """
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    all_eq = []
    seen = set()
    for y in range(years_back):
        start = (now - timedelta(days=365 * (y + 1))).strftime('%Y-%m-%d')
        end = (now - timedelta(days=365 * y)).strftime('%Y-%m-%d')
        url = f"{USGS_BASE}&starttime={start}&endtime={end}&limit=10000&orderby=time"
        raw = _fetch_json(url, timeout=90)
        data = raw.get('features', []) if isinstance(raw, dict) else []
        for feat in data:
            if isinstance(feat, dict) and feat.get('type') == 'Feature':
                norm = _normalize_usgs_feature(feat)
                if norm and norm.get('earthquake_id') not in seen:
                    seen.add(norm['earthquake_id'])
                    all_eq.append(norm)
        print(f"[DATA_COLLECTOR] USGS arşiv {start}–{end}: +{len(data)} (toplam {len(all_eq)})")
        time.sleep(0.5)
    return all_eq


def fetch_archive_full() -> List[Dict]:
    """
    Tam arşiv: Kandilli archive (limit artırılmış) + USGS yıllık chunk.
    10k–50k+ deprem potansiyeli.
    """
    all_eq = []
    seen = set()

    def _add(eq_list: List[Dict], default_source: str = 'kandilli'):
        for eq in eq_list:
            if not eq.get('geojson') or not eq['geojson'].get('coordinates'):
                continue
            eid = eq.get('earthquake_id') or eq.get('eventID') or _generate_eq_id(eq)
            if eid not in seen:
                seen.add(eid)
                eq = eq.copy()
                eq.setdefault('source', default_source)
                all_eq.append(eq)

    # Kandilli archive (maksimum limit)
    archive = fetch_archive_data(limit=ARCHIVE_LIMIT)
    _add(archive, 'kandilli')
    time.sleep(1)

    # USGS tam arşiv (yıllara bölünmüş)
    usgs_full = fetch_usgs_archive_full()
    _add(usgs_full, 'usgs')

    print(f"[DATA_COLLECTOR] Tam arşiv toplam: {len(all_eq)} deprem")
    return all_eq


def fetch_all_multi_source() -> List[Dict]:
    """
    Tüm kaynaklardan veri çeker: Kandilli+AFAD (orhanaydogdu), USGS, EMSC.
    Duplicate eventID ile birleştirilir.
    
    Returns:
        Birleştirilmiş deprem verileri listesi (500k+ potansiyel)
    """
    all_earthquakes = []
    seen_ids = set()

    def _merge(eq_list: List[Dict], source_tag: str):
        for eq in eq_list:
            if not eq.get('geojson') or not eq['geojson'].get('coordinates'):
                continue
            eq_id = eq.get('earthquake_id') or eq.get('eventID') or _generate_eq_id(eq)
            if eq_id not in seen_ids:
                seen_ids.add(eq_id)
                eq = eq.copy()
                eq.setdefault('source', source_tag)
                if 'timestamp' not in eq and 'created_at' in eq:
                    eq['timestamp'] = eq['created_at']
                all_earthquakes.append(eq)

    # 1. orhanaydogdu (Kandilli + AFAD birleşik)
    try:
        resp = _fetch_json(ORHANAYDOGDU_ALL_API)
        if resp and resp.get('result'):
            _merge(resp['result'], 'kandilli_afad')
        else:
            live = fetch_live_data()
            archive = fetch_archive_data()
            _merge(live + archive, 'kandilli')
    except Exception as e:
        print(f"[DATA_COLLECTOR] orhanaydogdu hatası: {e}")
        live = fetch_live_data()
        archive = fetch_archive_data()
        _merge(live + archive, 'kandilli')

    time.sleep(1)
    # 2. USGS
    try:
        usgs = fetch_usgs_data()
        _merge(usgs, 'usgs')
    except Exception as e:
        print(f"[DATA_COLLECTOR] USGS hatası: {e}")

    time.sleep(1)
    # 3. EMSC
    try:
        emsc = fetch_emsc_data()
        _merge(emsc, 'emsc')
    except Exception as e:
        print(f"[DATA_COLLECTOR] EMSC hatası: {e}")

    print(f"[DATA_COLLECTOR] Multi-source toplam: {len(all_earthquakes)} benzersiz deprem")
    return all_earthquakes


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


def generate_bootstrap_synthetic(
    real_records: List[Dict],
    num_samples: int,
    noise_std: float = 0.15
) -> List[Dict]:
    """
    Gerçek veriden bootstrap sampling + Gaussian noise ile sentetik veri üretir.
    Rastgele sentetik yerine gerçek veri dağılımına yakın örnekler oluşturur.
    
    Args:
        real_records: features + risk_score içeren gerçek eğitim kayıtları
        num_samples: Üretilecek örnek sayısı
        noise_std: Her feature'a eklenecek gürültü std (oran, 0.15 = %15)
    
    Returns:
        Bootstrap + noise ile üretilmiş eğitim kayıtları
    """
    if not real_records:
        return []
    
    # Numeric feature anahtarları
    numeric_keys = [
        'count', 'max_magnitude', 'mean_magnitude', 'std_magnitude',
        'min_distance', 'mean_distance', 'mean_depth', 'mean_interval',
        'min_interval', 'mag_above_4', 'mag_above_5', 'mag_above_6',
        'within_50km', 'within_100km', 'within_150km', 'nearest_fault_distance',
        'activity_density', 'magnitude_distance_ratio', 'magnitude_trend',
        'neighbor_activity', 'cluster_count', 'in_cluster', 'nearest_cluster_distance',
        'cluster_density', 'max_cluster_size', 'nearest_cluster_max_mag'
    ]
    
    synthetic = []
    n = len(real_records)
    for _ in range(num_samples):
        idx = np.random.randint(0, n)
        rec = real_records[idx].copy()
        if 'features' not in rec:
            continue
        features = rec['features'].copy()
        for k in numeric_keys:
            if k in features and isinstance(features[k], (int, float)):
                val = features[k]
                noise = np.random.normal(0, abs(val) * noise_std + 1e-6)
                features[k] = max(0, val + noise) if k not in ('magnitude_trend',) else val + noise
        rec['features'] = features
        # risk_score'u da gürültü ile güncelle
        risk = rec.get('risk_score', 2.0)
        rec['risk_score'] = round(min(10, max(0, risk + np.random.normal(0, risk * noise_std))), 1)
        rec['source'] = 'bootstrap_synthetic'
        rec['timestamp'] = time.time()
        synthetic.append(rec)
    
    print(f"[DATA_COLLECTOR] Bootstrap + noise: {len(synthetic)} örnek üretildi (gerçek veriden)")
    return synthetic


def generate_synthetic_data(
    num_samples: int = 500,
    real_records: Optional[List[Dict]] = None
) -> List[Dict]:
    """
    Sentetik eğitim verisi üretir.
    Gerçek veri varsa: bootstrap sampling + Gaussian noise (daha doğru).
    Yoksa: Türkiye koordinat aralıklarında rastgele senaryolar.
    
    Args:
        num_samples: Üretilecek örnek sayısı
        real_records: Varsa bootstrap+noise kullanılır
    
    Returns:
        Şehir bazlı sentetik eğitim verileri (features + risk_score formatında)
    """
    # Öncelik: gerçek veriden bootstrap + noise
    if real_records and len(real_records) >= 10:
        return generate_bootstrap_synthetic(real_records, num_samples)
    
    print(f"[DATA_COLLECTOR] {num_samples} sentetik örnek üretiliyor (rastgele)...")
    
    # earthquake_features (app'ten bağımsız) veya app
    try:
        from earthquake_features import TURKEY_CITIES, TURKEY_FAULT_LINES
    except ImportError:
        try:
            from app import TURKEY_CITIES, TURKEY_FAULT_LINES
        except ImportError:
            print("[DATA_COLLECTOR] earthquake_features/app yok, basit sentetik veri üretiliyor")
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
            'magnitude_trend': np.random.uniform(-0.5, 0.5),
            'neighbor_activity': np.random.uniform(0, count * 1.5),
            'cluster_count': int(count * 0.3) if count > 3 else 0,
            'in_cluster': 1 if count > 10 and min_distance < 50 else 0,
            'nearest_cluster_distance': min_distance * 1.5 if count > 2 else 300,
            'cluster_density': count / 10.0 if count > 5 else 0,
            'max_cluster_size': min(count, int(count * 0.6)) if count > 2 else 0,
            'nearest_cluster_max_mag': max_magnitude * 0.9 if count > 2 else 0
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
                'magnitude_trend': np.random.uniform(-0.5, 0.5),
                'neighbor_activity': np.random.uniform(0, 15),
                'cluster_count': np.random.randint(0, 5),
                'in_cluster': np.random.randint(0, 2),
                'nearest_cluster_distance': np.random.uniform(20, 200),
                'cluster_density': np.random.uniform(0, 5),
                'max_cluster_size': np.random.randint(0, 15),
                'nearest_cluster_max_mag': np.random.uniform(0, 5)
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
