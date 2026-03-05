#!/usr/bin/env python3
"""
earthquake_features.py
App'ten bağımsız feature engineering modülü.
Scheduler standalone çalıştığında da şehir bazlı eğitim verisi oluşturur.
"""

import time
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

try:
    from sklearn.cluster import DBSCAN
    HAS_DBSCAN = True
except ImportError:
    HAS_DBSCAN = False

# TÜRKİYE FAY HATLARI
TURKEY_FAULT_LINES = [
    {"name": "Kuzey Anadolu Fay Hattı (KAF)", "coords": [
        [40.0, 26.0], [40.2, 27.0], [40.5, 28.0], [40.7, 29.0],
        [40.9, 30.0], [41.0, 31.0], [41.2, 32.0], [41.4, 33.0],
        [41.6, 34.0], [41.8, 35.0], [42.0, 36.0], [42.2, 37.0]
    ]},
    {"name": "Doğu Anadolu Fay Hattı (DAF)", "coords": [
        [37.0, 38.0], [37.5, 39.0], [38.0, 40.0], [38.5, 41.0],
        [39.0, 42.0], [39.5, 43.0], [40.0, 44.0]
    ]},
    {"name": "Ege Graben Sistemi", "coords": [
        [38.0, 26.0], [38.5, 27.0], [39.0, 28.0], [39.5, 29.0]
    ]},
    {"name": "Batı Anadolu Fay Sistemi", "coords": [
        [38.5, 27.0], [39.0, 28.5], [39.5, 30.0], [40.0, 31.5]
    ]}
]

# TÜRKİYE İLLERİ (özet - 81 il)
TURKEY_CITIES = {
    "İstanbul": {"lat": 41.0082, "lon": 28.9784},
    "Ankara": {"lat": 39.9334, "lon": 32.8597},
    "İzmir": {"lat": 38.4237, "lon": 27.1428},
    "Bursa": {"lat": 40.1826, "lon": 29.0665},
    "Antalya": {"lat": 36.8969, "lon": 30.7133},
    "Adana": {"lat": 36.9914, "lon": 35.3308},
    "Konya": {"lat": 37.8746, "lon": 32.4932},
    "Gaziantep": {"lat": 37.0662, "lon": 37.3833},
    "Şanlıurfa": {"lat": 37.1674, "lon": 38.7955},
    "Kocaeli": {"lat": 40.8533, "lon": 29.8815},
    "Kayseri": {"lat": 38.7312, "lon": 35.4787},
    "Eskişehir": {"lat": 39.7767, "lon": 30.5206},
    "Diyarbakır": {"lat": 37.9144, "lon": 40.2306},
    "Samsun": {"lat": 41.2867, "lon": 36.3300},
    "Denizli": {"lat": 37.7765, "lon": 29.0864},
    "Kahramanmaraş": {"lat": 37.5858, "lon": 36.9371},
    "Malatya": {"lat": 38.3552, "lon": 38.3095},
    "Van": {"lat": 38.4891, "lon": 43.4089},
    "Erzurum": {"lat": 39.9043, "lon": 41.2679},
    "Batman": {"lat": 37.8812, "lon": 41.1351},
    "Elazığ": {"lat": 38.6748, "lon": 39.2225},
    "Hatay": {"lat": 36.4018, "lon": 36.3498},
    "Manisa": {"lat": 38.6191, "lon": 27.4289},
    "Sivas": {"lat": 39.7477, "lon": 37.0179},
    "Balıkesir": {"lat": 39.6484, "lon": 27.8826},
    "Trabzon": {"lat": 41.0015, "lon": 39.7178},
    "Ordu": {"lat": 40.9839, "lon": 37.8764},
    "Afyonkarahisar": {"lat": 38.7638, "lon": 30.5403},
    "Aydın": {"lat": 37.8444, "lon": 27.8458},
    "Muğla": {"lat": 37.2153, "lon": 28.3636},
    "Tekirdağ": {"lat": 40.9833, "lon": 27.5167},
    "Sakarya": {"lat": 40.7569, "lon": 30.3781},
    "Mersin": {"lat": 36.8000, "lon": 34.6333},
    "Zonguldak": {"lat": 41.4564, "lon": 31.7987},
    "Kütahya": {"lat": 39.4167, "lon": 29.9833},
    "Osmaniye": {"lat": 37.0742, "lon": 36.2478},
    "Çorum": {"lat": 40.5506, "lon": 34.9556},
    "Edirne": {"lat": 41.6772, "lon": 26.5556},
    "Giresun": {"lat": 40.9128, "lon": 38.3895},
    "Aksaray": {"lat": 38.3686, "lon": 34.0364},
    "Niğde": {"lat": 37.9667, "lon": 34.6833},
    "Nevşehir": {"lat": 38.6244, "lon": 34.7239},
    "Bolu": {"lat": 40.7333, "lon": 31.6000},
    "Yozgat": {"lat": 39.8200, "lon": 34.8044},
    "Düzce": {"lat": 40.8439, "lon": 31.1565},
    "Bingöl": {"lat": 38.8847, "lon": 40.4981},
    "Bitlis": {"lat": 38.4000, "lon": 42.1000},
    "Muş": {"lat": 38.7333, "lon": 41.4833},
    "Hakkari": {"lat": 37.5744, "lon": 43.7408},
    "Siirt": {"lat": 37.9333, "lon": 41.9500},
    "Şırnak": {"lat": 37.5167, "lon": 42.4500},
    "Iğdır": {"lat": 39.9167, "lon": 44.0333},
    "Ardahan": {"lat": 41.1167, "lon": 42.7000},
    "Artvin": {"lat": 41.1833, "lon": 41.8167},
    "Rize": {"lat": 41.0201, "lon": 40.5234},
    "Gümüşhane": {"lat": 40.4603, "lon": 39.5081},
    "Bayburt": {"lat": 40.2553, "lon": 40.2247},
    "Erzincan": {"lat": 39.7500, "lon": 39.5000},
    "Tunceli": {"lat": 39.1083, "lon": 39.5333},
    "Adıyaman": {"lat": 37.7639, "lon": 38.2789},
    "Kilis": {"lat": 36.7167, "lon": 37.1167},
    "Kırıkkale": {"lat": 39.8333, "lon": 33.5000},
    "Kırşehir": {"lat": 39.1500, "lon": 34.1667},
    "Karabük": {"lat": 41.2000, "lon": 32.6333},
    "Bartın": {"lat": 41.6333, "lon": 32.3333},
    "Kastamonu": {"lat": 41.3667, "lon": 33.7667},
    "Sinop": {"lat": 42.0167, "lon": 35.1500},
    "Çanakkale": {"lat": 40.1553, "lon": 26.4142},
    "Bilecik": {"lat": 40.1419, "lon": 29.9792},
    "Burdur": {"lat": 37.7167, "lon": 30.2833},
    "Isparta": {"lat": 37.7667, "lon": 30.5500},
    "Uşak": {"lat": 38.6833, "lon": 29.4000},
    "Kırklareli": {"lat": 41.7333, "lon": 27.2167},
    "Yalova": {"lat": 40.6500, "lon": 29.2667},
    "Kars": {"lat": 40.6000, "lon": 43.0833},
    "Ağrı": {"lat": 39.7167, "lon": 43.0500},
    "Amasya": {"lat": 40.6500, "lon": 35.8333},
    "Tokat": {"lat": 40.3167, "lon": 36.5500},
    "Mardin": {"lat": 37.3131, "lon": 40.7356},
}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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
    return float(R * c)


def haversine_vectorized(lat1: float, lon1: float, lat2_arr: np.ndarray, lon2_arr: np.ndarray) -> np.ndarray:
    """Tek nokta → N nokta mesafe (km). 26k+ deprem için hızlı."""
    R = 6371
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2_arr)
    lon2_rad = np.radians(lon2_arr)
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c


# Seismic cluster detection parametreleri
CLUSTER_EPS_KM = 25  # DBSCAN: 25km içindeki depremler aynı küme
CLUSTER_MIN_SAMPLES = 2  # En az 2 deprem = küme


def detect_seismic_clusters(recent_eqs: List[Dict]) -> List[Dict]:
    """
    Deprem kümelerini tespit eder (DBSCAN).
    Her küme: centroid (lat, lon), size, max_mag.
    Deprem kümelenmesi = artçı / aktivite yoğunlaşması sinyali.
    """
    if not recent_eqs or len(recent_eqs) < 2:
        return []
    if not HAS_DBSCAN:
        return []
    points = np.array([[e['lat'], e['lon']] for e in recent_eqs])
    # eps: derece cinsinden (~0.0025 rad ≈ 0.14° ≈ 15km), 0.25° ≈ 25km
    eps_deg = CLUSTER_EPS_KM / 111.0  # 1° lat ≈ 111km
    clustering = DBSCAN(eps=eps_deg, min_samples=CLUSTER_MIN_SAMPLES, metric='euclidean').fit(points)
    labels = clustering.labels_
    clusters = []
    for lid in set(labels):
        if lid == -1:
            continue
        mask = labels == lid
        cluster_eqs = [recent_eqs[i] for i in range(len(recent_eqs)) if mask[i]]
        lats = [e['lat'] for e in cluster_eqs]
        lons = [e['lon'] for e in cluster_eqs]
        mags = [e['mag'] for e in cluster_eqs]
        clusters.append({
            'centroid_lat': float(np.mean(lats)),
            'centroid_lon': float(np.mean(lons)),
            'size': len(cluster_eqs),
            'max_mag': float(np.max(mags)),
            'mean_mag': float(np.mean(mags))
        })
    return clusters


def get_cluster_features(clusters: List[Dict], target_lat: float, target_lon: float) -> Dict:
    """
    Hedef nokta için küme feature'ları.
    """
    if not clusters:
        return {
            'cluster_count': 0,
            'in_cluster': 0,
            'nearest_cluster_distance': 300,
            'cluster_density': 0,
            'max_cluster_size': 0,
            'nearest_cluster_max_mag': 0
        }
    distances = [haversine(target_lat, target_lon, c['centroid_lat'], c['centroid_lon']) for c in clusters]
    nearest_idx = int(np.argmin(distances))
    nearest_dist = distances[nearest_idx]
    nearest_cluster = clusters[nearest_idx]
    # in_cluster: hedef 50km içinde mi bir kümenin
    in_cluster = 1 if nearest_dist < 50 else 0
    # cluster_density: 150km içindeki kümelerin toplam deprem sayısı
    within_150 = [c for c, d in zip(clusters, distances) if d < 150]
    cluster_density = sum(c['size'] for c in within_150) / (len(within_150) + 1)
    max_cluster_size = max(c['size'] for c in clusters) if clusters else 0
    return {
        'cluster_count': len([d for d in distances if d < 150]),
        'in_cluster': in_cluster,
        'nearest_cluster_distance': float(nearest_dist),
        'cluster_density': float(cluster_density),
        'max_cluster_size': max_cluster_size,
        'nearest_cluster_max_mag': float(nearest_cluster['max_mag'])
    }


# ETAS (Epidemic Type Aftershock Sequence) parametreleri
ETAS_ALPHA = 1.0   # Magnitude etkisi: exp(α(M-M0))
ETAS_M0 = 2.5      # Referans büyüklük
ETAS_C = 0.01      # Zaman offset (saat) - sıfıra bölmeyi önler
ETAS_P = 1.1      # Omori decay üssü: 1/(t+c)^p


def compute_etas_features(recent_eqs: List[Dict], target_lat: float, target_lon: float,
                          reference_time: float) -> Dict[str, float]:
    """
    Gerçek ETAS modeli: Her deprem başka depremler doğurabilir.
    influence = mag_effect × time_decay × distance_decay
    """
    if not recent_eqs:
        return {'etas_score': 0.0, 'etas_max_influence': 0.0, 'etas_event_count': 0}
    influences = []
    for eq in recent_eqs:
        mag = float(eq.get('mag', 0) or 0)
        dist_km = float(eq.get('distance', 300) or 300)
        eq_ts = float(eq.get('timestamp', 0) or 0)
        dt_sec = max(0, reference_time - eq_ts)
        dt_hours = dt_sec / 3600.0
        # Omori: 1/(t+c)^p
        time_decay = 1.0 / ((dt_hours + ETAS_C) ** ETAS_P)
        # Büyük deprem daha çok artçı üretir
        mag_effect = np.exp(ETAS_ALPHA * (mag - ETAS_M0))
        # Yakın deprem daha önemli
        distance_decay = 1.0 / (dist_km + 1.0)
        influence = mag_effect * time_decay * distance_decay
        influences.append(influence)
    return {
        'etas_score': float(np.sum(influences)),
        'etas_max_influence': float(np.max(influences)) if influences else 0.0,
        'etas_event_count': len(recent_eqs)
    }


def _get_eq_timestamp(eq: Dict) -> float:
    """Deprem timestamp'ini al (created_at veya date_time)."""
    if 'created_at' in eq:
        return float(eq['created_at'])
    if 'timestamp' in eq:
        return float(eq['timestamp'])
    return time.time()


def extract_features(earthquakes: List[Dict], target_lat: float, target_lon: float,
                    time_window_hours: int = 168) -> Optional[Dict]:
    """
    Deprem verilerinden özellik çıkarır.
    depth, magnitude, time difference, regional frequency dahil.
    """
    if not earthquakes:
        return None

    current_time = time.time()
    window_start = current_time - (time_window_hours * 3600)

    recent_eqs = []
    for eq in earthquakes:
        if not eq.get('geojson') or not eq['geojson'].get('coordinates'):
            continue
        lon, lat = eq['geojson']['coordinates']
        mag = eq.get('mag', 0)
        depth = eq.get('depth', 10)
        ts = _get_eq_timestamp(eq)
        distance = haversine(target_lat, target_lon, lat, lon)

        if distance < 300 and mag >= 1.5:
            recent_eqs.append({
                'mag': mag, 'distance': distance, 'depth': depth,
                'lat': lat, 'lon': lon, 'timestamp': ts
            })
        elif distance < 300 and mag >= 1.0:
            recent_eqs.append({
                'mag': mag, 'distance': distance, 'depth': depth,
                'lat': lat, 'lon': lon, 'timestamp': ts
            })

    if not recent_eqs:
        all_eqs = []
        for eq in earthquakes:
            if eq.get('geojson') and eq['geojson'].get('coordinates'):
                lon, lat = eq['geojson']['coordinates']
                mag = eq.get('mag', 0)
                depth = eq.get('depth', 10)
                ts = _get_eq_timestamp(eq)
                distance = haversine(target_lat, target_lon, lat, lon)
                if mag >= 1.0:
                    all_eqs.append({'mag': mag, 'distance': distance, 'depth': depth,
                                   'lat': lat, 'lon': lon, 'timestamp': ts})
        recent_eqs = all_eqs if all_eqs else []

    nearest_fault = float('inf')
    for fault in TURKEY_FAULT_LINES:
        for coord in fault['coords']:
            fault_lat, fault_lon = coord
            dist = haversine(target_lat, target_lon, fault_lat, fault_lon)
            nearest_fault = min(nearest_fault, dist)

    if not recent_eqs:
        empty = {
            'count': 0, 'max_magnitude': 0, 'mean_magnitude': 0, 'std_magnitude': 0,
            'min_distance': 300, 'mean_distance': 300, 'mean_depth': 10,
            'mean_interval': 3600, 'min_interval': 3600,
            'mag_above_4': 0, 'mag_above_5': 0, 'mag_above_6': 0,
            'within_50km': 0, 'within_100km': 0, 'within_150km': 0,
            'nearest_fault_distance': nearest_fault, 'activity_density': 0,
            'magnitude_distance_ratio': 0, 'magnitude_trend': 0,
            'shallow_quakes': 0, 'deep_quakes': 0,
            'time_since_last': 86400, 'regional_frequency': 0,
            'cluster_count': 0, 'in_cluster': 0, 'nearest_cluster_distance': 300,
            'cluster_density': 0, 'max_cluster_size': 0, 'nearest_cluster_max_mag': 0,
            'etas_score': 0.0, 'etas_max_influence': 0.0, 'etas_event_count': 0
        }
        return empty

    magnitudes = [e['mag'] for e in recent_eqs]
    distances = [e['distance'] for e in recent_eqs]
    depths = [e['depth'] for e in recent_eqs]

    features = {
        'count': len(recent_eqs),
        'max_magnitude': float(np.max(magnitudes)),
        'mean_magnitude': float(np.mean(magnitudes)),
        'std_magnitude': float(np.std(magnitudes)) if len(magnitudes) > 1 else 0,
        'min_distance': float(np.min(distances)),
        'mean_distance': float(np.mean(distances)),
        'mean_depth': float(np.mean(depths)),
        'mag_above_4': sum(1 for m in magnitudes if m >= 4.0),
        'mag_above_5': sum(1 for m in magnitudes if m >= 5.0),
        'mag_above_6': sum(1 for m in magnitudes if m >= 6.0),
        'within_50km': sum(1 for d in distances if d <= 50),
        'within_100km': sum(1 for d in distances if d <= 100),
        'within_150km': sum(1 for d in distances if d <= 150),
        'nearest_fault_distance': nearest_fault,
        'shallow_quakes': sum(1 for d in depths if d <= 10),
        'deep_quakes': sum(1 for d in depths if d > 30),
    }

    if len(recent_eqs) > 1:
        timestamps = sorted([e['timestamp'] for e in recent_eqs])
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        features['mean_interval'] = float(np.mean(intervals))
        features['min_interval'] = float(np.min(intervals))
        features['time_since_last'] = current_time - timestamps[-1]
    else:
        features['mean_interval'] = 3600
        features['min_interval'] = 3600
        features['time_since_last'] = current_time - recent_eqs[0]['timestamp'] if recent_eqs else 86400

    features['activity_density'] = features['count'] / (np.pi * (features['mean_distance'] ** 2) + 1)
    features['magnitude_distance_ratio'] = features['max_magnitude'] / (features['min_distance'] + 1)
    features['regional_frequency'] = features['count'] / (time_window_hours / 24) if time_window_hours > 0 else 0

    # Seismic cluster detection - deprem kümelenmesi sinyali
    clusters = detect_seismic_clusters(recent_eqs)
    features.update(get_cluster_features(clusters, target_lat, target_lon))

    # ETAS (Epidemic Type Aftershock Sequence) - her deprem başka depremler doğurabilir
    etas = compute_etas_features(recent_eqs, target_lat, target_lon, current_time)
    features.update(etas)

    # Komşu aktivite: en yakın şehri bul, onun komşularının aktivitesi
    try:
        min_d = float('inf')
        closest_city = None
        for cname, cdata in TURKEY_CITIES.items():
            d = haversine(target_lat, target_lon, cdata['lat'], cdata['lon'])
            if d < min_d:
                min_d, closest_city = d, cname
        if closest_city and min_d < 200:
            features['neighbor_activity'] = _get_neighbor_activity(earthquakes, closest_city, 168)  # 7 gün
        else:
            features['neighbor_activity'] = 0.0
    except Exception:
        features['neighbor_activity'] = 0.0

    if len(recent_eqs) >= 3:
        sorted_by_time = sorted(recent_eqs, key=lambda x: x['timestamp'])
        mid = len(sorted_by_time) // 2
        first_avg = np.mean([e['mag'] for e in sorted_by_time[:mid]])
        second_avg = np.mean([e['mag'] for e in sorted_by_time[mid:]])
        features['magnitude_trend'] = float(second_avg - first_avg)
    else:
        features['magnitude_trend'] = 0

    return features


def predict_earthquake_risk(earthquakes: List[Dict], target_lat: float, target_lon: float) -> Dict:
    """Risk skoru hesaplar (0-10)."""
    nearest_fault = float('inf')
    for fault in TURKEY_FAULT_LINES:
        for coord in fault['coords']:
            dist = haversine(target_lat, target_lon, coord[0], coord[1])
            nearest_fault = min(nearest_fault, dist)

    if not earthquakes:
        base = 3.5 if nearest_fault < 20 else (2.5 if nearest_fault < 50 else 1.0)
        return {'risk_score': base}

    recent = []
    seven_days_ago = time.time() - (7 * 24 * 3600)
    for eq in earthquakes:
        if eq.get('geojson') and eq['geojson'].get('coordinates'):
            lon, lat = eq['geojson']['coordinates']
            mag = eq.get('mag', 0)
            ts = _get_eq_timestamp(eq)
            dist = haversine(target_lat, target_lon, lat, lon)
            if dist < 300 and ts >= seven_days_ago:
                recent.append({'mag': mag, 'distance': dist, 'depth': eq.get('depth', 10)})

    if not recent:
        base = 2.0 if nearest_fault < 50 else 1.0
        return {'risk_score': base}

    mags = [e['mag'] for e in recent]
    dists = [e['distance'] for e in recent]
    max_mag = max(mags)
    min_dist = min(dists)
    count = len(recent)

    risk = 0
    if max_mag >= 6: risk += 3.5
    elif max_mag >= 5: risk += 2.5
    elif max_mag >= 4.5: risk += 1.8
    elif max_mag >= 4: risk += 1.2
    else: risk += max_mag * 0.3

    if count >= 50: risk += 2.5
    elif count >= 20: risk += 2.0
    elif count >= 10: risk += 1.5
    elif count >= 5: risk += 1.0
    else: risk += count * 0.15

    if min_dist < 10: risk += 2.0
    elif min_dist < 25: risk += 1.5
    elif min_dist < 50: risk += 1.0
    elif min_dist < 100: risk += 0.5

    if nearest_fault < 10: risk += 1.5
    elif nearest_fault < 25: risk += 1.2
    elif nearest_fault < 50: risk += 0.8
    elif nearest_fault < 100: risk += 0.4

    risk = min(10, max(0, risk))
    return {'risk_score': round(risk, 1)}


def _risk_from_features(features: Dict, nearest_fault: float = 50) -> float:
    """Feature dict'ten risk skoru (batch modda hızlı)."""
    max_mag = features.get('max_magnitude', 0) or 0
    min_dist = features.get('min_distance', 300) or 300
    count = features.get('count', 0) or 0
    nf = features.get('nearest_fault_distance', nearest_fault) or nearest_fault
    risk = 0
    if max_mag >= 6: risk += 3.5
    elif max_mag >= 5: risk += 2.5
    elif max_mag >= 4.5: risk += 1.8
    elif max_mag >= 4: risk += 1.2
    else: risk += max_mag * 0.3
    if count >= 50: risk += 2.5
    elif count >= 20: risk += 2.0
    elif count >= 10: risk += 1.5
    elif count >= 5: risk += 1.0
    else: risk += count * 0.15
    if min_dist < 10: risk += 2.0
    elif min_dist < 25: risk += 1.5
    elif min_dist < 50: risk += 1.0
    elif min_dist < 100: risk += 0.5
    if nf < 10: risk += 1.5
    elif nf < 25: risk += 1.2
    elif nf < 50: risk += 0.8
    elif nf < 100: risk += 0.4
    return round(min(10, max(0, risk)), 1)


# Zaman pencereleri (saat): 1h, 6h, 24h, 7d, 30d (Ayşenisa mimarisi)
TIME_WINDOWS_HOURS = [1, 6, 24, 168, 720]  # 1h, 6h, 24h, 7d, 30d

# Komşu şehir mesafe eşiği (km)
NEIGHBOR_DISTANCE_KM = 120


def _build_city_neighbors() -> Dict[str, List[str]]:
    """Her şehir için 120km içindeki komşu illeri döndürür."""
    neighbors = {}
    cities = list(TURKEY_CITIES.items())
    for i, (c1, d1) in enumerate(cities):
        nb = []
        for j, (c2, d2) in enumerate(cities):
            if i == j:
                continue
            dist = haversine(d1['lat'], d1['lon'], d2['lat'], d2['lon'])
            if dist < NEIGHBOR_DISTANCE_KM:
                nb.append(c2)
        neighbors[c1] = nb
    return neighbors


CITY_NEIGHBORS = _build_city_neighbors()


def _get_neighbor_activity(earthquakes: List[Dict], city_name: str,
                           time_window_hours: int = 168) -> float:
    """
    Komşu illerin ortalama aktivitesi (count).
    Depremde komşu bölge etkisi önemli.
    """
    nb = CITY_NEIGHBORS.get(city_name, [])
    if not nb:
        return 0.0
    counts = []
    for n in nb:
        if n not in TURKEY_CITIES:
            continue
        lat, lon = TURKEY_CITIES[n]['lat'], TURKEY_CITIES[n]['lon']
        f = extract_features(earthquakes, lat, lon, time_window_hours)
        if f:
            counts.append(f.get('count', 0))
    return float(np.mean(counts)) if counts else 0.0


def _parse_earthquakes_to_arrays(earthquakes: List[Dict]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Ham deprem listesini numpy array'lere çevirir (batch işlem için)."""
    lats, lons, mags, depths, timestamps = [], [], [], [], []
    for eq in earthquakes:
        if not eq.get('geojson') or not eq['geojson'].get('coordinates'):
            continue
        lon, lat = eq['geojson']['coordinates']
        mag = float(eq.get('mag', 0) or 0)
        depth = float(eq.get('depth', 10) or 10)
        ts = _get_eq_timestamp(eq)
        lats.append(lat)
        lons.append(lon)
        mags.append(mag)
        depths.append(depth)
        timestamps.append(ts)
    if not lats:
        return np.array([]), np.array([]), np.array([]), np.array([]), np.array([])
    return (np.array(lats), np.array(lons), np.array(mags), np.array(depths), np.array(timestamps))


def _extract_features_from_arrays(lats: np.ndarray, lons: np.ndarray, mags: np.ndarray,
                                  depths: np.ndarray, timestamps: np.ndarray,
                                  target_lat: float, target_lon: float,
                                  window_start: float, current_time: float) -> Optional[Dict]:
    """
    Vectorized feature extraction. neighbor_activity hariç tüm feature'lar.
    """
    if len(lats) == 0:
        return None
    dists = haversine_vectorized(target_lat, target_lon, lats, lons)
    mask = (dists < 300) & (mags >= 1.0) & (timestamps >= window_start) & (timestamps <= current_time)
    if not np.any(mask):
        nearest_fault = float('inf')
        for fault in TURKEY_FAULT_LINES:
            for coord in fault['coords']:
                d = haversine(target_lat, target_lon, coord[0], coord[1])
                nearest_fault = min(nearest_fault, d)
        return {
            'count': 0, 'max_magnitude': 0, 'mean_magnitude': 0, 'std_magnitude': 0,
            'min_distance': 300, 'mean_distance': 300, 'mean_depth': 10,
            'mean_interval': 3600, 'min_interval': 3600,
            'mag_above_4': 0, 'mag_above_5': 0, 'mag_above_6': 0,
            'within_50km': 0, 'within_100km': 0, 'within_150km': 0,
            'nearest_fault_distance': nearest_fault, 'activity_density': 0,
            'magnitude_distance_ratio': 0, 'magnitude_trend': 0,
            'shallow_quakes': 0, 'deep_quakes': 0,
            'time_since_last': 86400, 'regional_frequency': 0,
            'cluster_count': 0, 'in_cluster': 0, 'nearest_cluster_distance': 300,
            'cluster_density': 0, 'max_cluster_size': 0, 'nearest_cluster_max_mag': 0,
            'neighbor_activity': 0.0,
            'etas_score': 0.0, 'etas_max_influence': 0.0, 'etas_event_count': 0
        }
    d, m, dep, ts = dists[mask], mags[mask], depths[mask], timestamps[mask]
    la, lo = lats[mask], lons[mask]
    recent_eqs = [{'mag': float(m[i]), 'distance': float(d[i]), 'depth': float(dep[i]),
                  'lat': float(la[i]), 'lon': float(lo[i]), 'timestamp': float(ts[i])}
                 for i in range(len(d))]
    nearest_fault = float('inf')
    for fault in TURKEY_FAULT_LINES:
        for coord in fault['coords']:
            nearest_fault = min(nearest_fault, haversine(target_lat, target_lon, coord[0], coord[1]))
    features = {
        'count': len(recent_eqs),
        'max_magnitude': float(np.max(m)),
        'mean_magnitude': float(np.mean(m)),
        'std_magnitude': float(np.std(m)) if len(m) > 1 else 0,
        'min_distance': float(np.min(d)),
        'mean_distance': float(np.mean(d)),
        'mean_depth': float(np.mean(dep)),
        'mag_above_4': int(np.sum(m >= 4.0)),
        'mag_above_5': int(np.sum(m >= 5.0)),
        'mag_above_6': int(np.sum(m >= 6.0)),
        'within_50km': int(np.sum(d <= 50)),
        'within_100km': int(np.sum(d <= 100)),
        'within_150km': int(np.sum(d <= 150)),
        'nearest_fault_distance': nearest_fault,
        'shallow_quakes': int(np.sum(dep <= 10)),
        'deep_quakes': int(np.sum(dep > 30)),
    }
    if len(ts) > 1:
        ts_sorted = np.sort(ts)
        intervals = np.diff(ts_sorted)
        features['mean_interval'] = float(np.mean(intervals))
        features['min_interval'] = float(np.min(intervals))
        features['time_since_last'] = float(current_time - ts_sorted[-1])
    else:
        features['mean_interval'] = 3600
        features['min_interval'] = 3600
        features['time_since_last'] = float(current_time - ts[0]) if len(ts) else 86400
    features['activity_density'] = features['count'] / (np.pi * (features['mean_distance'] ** 2) + 1)
    features['magnitude_distance_ratio'] = features['max_magnitude'] / (features['min_distance'] + 1)
    time_window_hours = (current_time - window_start) / 3600
    features['regional_frequency'] = features['count'] / (time_window_hours / 24) if time_window_hours > 0 else 0
    clusters = detect_seismic_clusters(recent_eqs)
    features.update(get_cluster_features(clusters, target_lat, target_lon))
    etas = compute_etas_features(recent_eqs, target_lat, target_lon, current_time)
    features.update(etas)
    if len(recent_eqs) >= 3:
        mid = len(recent_eqs) // 2
        first_avg = np.mean([e['mag'] for e in sorted(recent_eqs, key=lambda x: x['timestamp'])[:mid]])
        second_avg = np.mean([e['mag'] for e in sorted(recent_eqs, key=lambda x: x['timestamp'])[mid:]])
        features['magnitude_trend'] = float(second_avg - first_avg)
    else:
        features['magnitude_trend'] = 0
    features['neighbor_activity'] = 0.0  # Sonra doldurulacak
    return features


# LSTM sequence için kullanılacak feature'lar
SEQUENCE_FEATURE_KEYS = [
    'count', 'max_magnitude', 'mean_magnitude', 'min_distance',
    'mag_above_4', 'within_50km', 'within_100km', 'time_since_last',
    'regional_frequency', 'activity_density'
]


def create_sequence_records_for_lstm(earthquakes: List[Dict]) -> List[Dict]:
    """
    LSTM için şehir × zaman dizisi: [t1, t2, t3, t4, t5] formatında.
    Her şehir için: last_7d, last_30d, last_90d feature'ları sıralı.
    """
    if not earthquakes:
        return []
    time_windows = [168, 720, 2160]  # 7d, 30d, 90d
    records = []
    for city_name, city_data in TURKEY_CITIES.items():
        lat, lon = city_data['lat'], city_data['lon']
        seq_features = []
        for tw in time_windows:
            features = extract_features(earthquakes, lat, lon, time_window_hours=tw)
            if not features:
                continue
            vec = [float(features.get(k, 0) or 0) for k in SEQUENCE_FEATURE_KEYS]
            if not vec:
                vec = [features.get('count', 0), features.get('max_magnitude', 0),
                       features.get('min_distance', 300), features.get('time_since_last', 86400)]
            seq_features.append(vec)
        if len(seq_features) >= 2:
            risk = predict_earthquake_risk(earthquakes, lat, lon)
            records.append({
                'city': city_name, 'lat': lat, 'lon': lon,
                'sequence': seq_features,
                'risk_score': risk.get('risk_score', 2.0),
                'time_windows': time_windows[:len(seq_features)]
            })
    return records


# Tarihsel referans genişletme: 26k deprem → 100k+ eğitim kaydı
HISTORICAL_MAX_REFERENCES = 300  # ~300 × 405 = 121k kayıt (500=202k, daha yavaş)


def _get_reference_times(earthquakes: List[Dict], max_refs: int = HISTORICAL_MAX_REFERENCES) -> List[float]:
    """Deprem timestamp'lerinden uniform örnekleme. Tarihsel eğitim için referans zamanları."""
    timestamps = []
    for eq in earthquakes:
        ts = _get_eq_timestamp(eq)
        if ts and ts > 0:
            timestamps.append(ts)
    if not timestamps:
        return []
    timestamps = sorted(set(timestamps))
    # En büyük pencere 30d - referans en az 30 gün sonra olsun (pencerede veri olsun)
    min_ref = timestamps[0] + 720 * 3600
    filtered = [t for t in timestamps if t >= min_ref]
    timestamps = filtered if filtered else timestamps
    if len(timestamps) <= max_refs:
        return timestamps
    step = max(1, len(timestamps) // max_refs)
    return [timestamps[i] for i in range(0, len(timestamps), step)][:max_refs]


def create_training_records_from_earthquakes(earthquakes: List[Dict],
                                             time_windows: List[int] = None,
                                             use_historical_expansion: bool = True) -> List[Dict]:
    """
    Ham deprem listesinden şehir × zaman penceresi eğitim kayıtları oluşturur.
    500+ depremde: vectorized batch + tarihsel referans genişletme (100k+ kayıt).
    use_historical_expansion=True: Her referans zamanı için 405 kayıt (26k deprem → ~200k).
    """
    if not earthquakes:
        return []
    time_windows = time_windows or TIME_WINDOWS_HOURS
    raw_eqs = [e for e in earthquakes if e.get('geojson') and e['geojson'].get('coordinates')]
    if not raw_eqs:
        return []

    # 500+ deprem: vectorized batch + tarihsel genişletme
    if len(raw_eqs) >= 500:
        ref_times = _get_reference_times(raw_eqs) if use_historical_expansion else None
        return _create_training_records_batch(raw_eqs, time_windows, reference_times=ref_times)

    records = []
    for city_name, city_data in TURKEY_CITIES.items():
        lat, lon = city_data['lat'], city_data['lon']
        for tw in time_windows:
            features = extract_features(raw_eqs, lat, lon, time_window_hours=tw)
            if features:
                risk = predict_earthquake_risk(raw_eqs, lat, lon)
                records.append({
                    'city': city_name, 'lat': lat, 'lon': lon,
                    'features': features, 'risk_score': risk.get('risk_score', 2.0),
                    'timestamp': time.time(),
                    'time_window_hours': tw
                })
    return records


def _create_training_records_batch(earthquakes: List[Dict], time_windows: List[int],
                                   reference_times: Optional[List[float]] = None) -> List[Dict]:
    """
    Vectorized batch. reference_times verilirse her biri için 405 kayıt (tarihsel genişletme).
    """
    lats, lons, mags, depths, timestamps = _parse_earthquakes_to_arrays(earthquakes)
    if len(lats) == 0:
        return []
    refs = reference_times if reference_times else [time.time()]
    city_list = list(TURKEY_CITIES.items())
    all_records = []
    n_refs = len(refs)
    if n_refs > 1:
        print(f"[EARTHQUAKE_FEATURES] Tarihsel genişletme: {n_refs} referans × 405 = ~{n_refs * 405} kayıt")
    for ref_idx, current_time in enumerate(refs):
        if n_refs > 5 and (ref_idx + 1) % max(1, n_refs // 5) == 0:
            print(f"[EARTHQUAKE_FEATURES] İlerleme: {ref_idx + 1}/{n_refs} referans")
        results = {}
        for city_name, city_data in city_list:
            lat, lon = city_data['lat'], city_data['lon']
            for tw in time_windows:
                window_start = current_time - (tw * 3600)
                f = _extract_features_from_arrays(lats, lons, mags, depths, timestamps,
                                                 lat, lon, window_start, current_time)
                if f:
                    results[(city_name, tw)] = f
        for (city_name, tw), f in results.items():
            nb = CITY_NEIGHBORS.get(city_name, [])
            if nb:
                counts = [results.get((n, tw), {}).get('count', 0) for n in nb if (n, tw) in results]
                f['neighbor_activity'] = float(np.mean(counts)) if counts else 0.0
        for (city_name, tw), features in results.items():
            city_data = TURKEY_CITIES.get(city_name, {})
            lat = city_data.get('lat', 0)
            lon = city_data.get('lon', 0)
            risk_f = results.get((city_name, 168), features)
            risk_score = _risk_from_features(risk_f) if risk_f else 2.0
            all_records.append({
                'city': city_name, 'lat': lat, 'lon': lon,
                'features': features, 'risk_score': risk_score,
                'timestamp': current_time,
                'time_window_hours': tw
            })
    return all_records
