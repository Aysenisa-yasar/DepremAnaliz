#!/usr/bin/env python3
# ML Modellerini Eğitmek İçin Script

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import (
    KANDILLI_API, extract_features, train_risk_prediction_model,
    predict_earthquake_risk, TURKEY_CITIES, ISTANBUL_COORDS,
    EARTHQUAKE_HISTORY_FILE, RISK_PREDICTION_MODEL_FILE,
    ANOMALY_DETECTION_MODEL_FILE
)
from sklearn.ensemble import IsolationForest
import numpy as np
import requests
import json
import time
from datetime import datetime

def collect_training_data():
    """Eğitim verisi toplar - mevcut deprem verilerini kullanarak"""
    print("Egitim verisi toplaniyor...")
    
    try:
        response = requests.get(KANDILLI_API, timeout=10)
        response.raise_for_status()
        earthquakes = response.json().get('result', [])
    except Exception as e:
        print(f"[ERROR] Veri cekilemedi: {e}")
        return []
    
    if not earthquakes:
        print("[ERROR] Deprem verisi bulunamadi")
        return []
    
    print(f"[OK] {len(earthquakes)} deprem verisi cekildi")
    
    # Farklı şehirler için veri topla
    training_data = []
    cities_to_use = list(TURKEY_CITIES.keys())[:20]  # İlk 20 şehir (hızlı eğitim için)
    
    print(f"{len(cities_to_use)} sehir icin ozellik cikariliyor...")
    
    for city_name in cities_to_use:
        city_data = TURKEY_CITIES[city_name]
        lat = city_data['lat']
        lon = city_data['lon']
        
        # Özellik çıkar
        features = extract_features(earthquakes, lat, lon, time_window_hours=24)
        
        if features:
            # Risk skoru hesapla (geleneksel yöntemle)
            risk_result = predict_earthquake_risk(earthquakes, lat, lon)
            risk_score = risk_result.get('risk_score', 2.0)
            
            training_data.append({
                'city': city_name,
                'lat': lat,
                'lon': lon,
                'features': features,
                'risk_score': risk_score,
                'timestamp': time.time()
            })
    
    # İstanbul için ekstra veri
    istanbul_features = extract_features(earthquakes, ISTANBUL_COORDS['lat'], ISTANBUL_COORDS['lon'], time_window_hours=24)
    if istanbul_features:
        istanbul_risk = predict_earthquake_risk(earthquakes, ISTANBUL_COORDS['lat'], ISTANBUL_COORDS['lon'])
        training_data.append({
            'city': 'Istanbul',
            'lat': ISTANBUL_COORDS['lat'],
            'lon': ISTANBUL_COORDS['lon'],
            'features': istanbul_features,
            'risk_score': istanbul_risk.get('risk_score', 2.0),
            'timestamp': time.time()
        })
    
    print(f"[OK] {len(training_data)} egitim ornegi olusturuldu")
    return training_data

def generate_synthetic_data(num_samples=100):
    """Sentetik veri üretir (gerçekçi deprem senaryoları)"""
    print(f"{num_samples} sentetik ornek uretiliyor...")
    
    import numpy as np
    synthetic_data = []
    
    # Türkiye koordinat aralıkları
    lat_range = (36.0, 42.0)
    lon_range = (26.0, 45.0)
    
    for i in range(num_samples):
        # Rastgele konum
        lat = np.random.uniform(lat_range[0], lat_range[1])
        lon = np.random.uniform(lon_range[0], lon_range[1])
        
        # Gerçekçi özellikler üret
        count = np.random.randint(0, 30)
        max_magnitude = np.random.uniform(2.0, 6.5)
        mean_magnitude = max_magnitude * np.random.uniform(0.6, 0.9)
        std_magnitude = mean_magnitude * np.random.uniform(0.1, 0.3)
        min_distance = np.random.uniform(5, 200)
        mean_distance = min_distance * np.random.uniform(1.2, 2.5)
        mean_depth = np.random.uniform(5, 30)
        mean_interval = np.random.uniform(300, 7200)
        min_interval = np.random.uniform(60, 1800)
        
        # Risk skorunu hesapla (basitleştirilmiş formül)
        risk_score = (
            max_magnitude * 0.4 +
            (count / 10) * 0.3 +
            (1 / (min_distance / 50 + 1)) * 0.2 +
            (1 / (mean_interval / 3600 + 1)) * 0.1
        )
        risk_score = min(10, max(0, risk_score))
        
        features = {
            'count': count,
            'max_magnitude': max_magnitude,
            'mean_magnitude': mean_magnitude,
            'std_magnitude': std_magnitude,
            'min_distance': min_distance,
            'mean_distance': mean_distance,
            'mean_depth': mean_depth,
            'mean_interval': mean_interval,
            'min_interval': min_interval,
            'mag_above_4': int(count * np.random.uniform(0.1, 0.3)),
            'mag_above_5': int(count * np.random.uniform(0.0, 0.1)),
            'mag_above_6': 0,
            'within_50km': int(count * np.random.uniform(0.1, 0.4)),
            'within_100km': int(count * np.random.uniform(0.3, 0.7)),
            'within_150km': int(count * np.random.uniform(0.5, 0.9)),
            'shallow_quakes': int(count * np.random.uniform(0.3, 0.7)),
            'deep_quakes': int(count * np.random.uniform(0.1, 0.3)),
            'nearest_fault_distance': np.random.uniform(10, 150),
            'activity_density': count / (np.pi * (mean_distance ** 2)) if mean_distance > 0 else 0,
            'magnitude_distance_ratio': max_magnitude / (min_distance + 1),
            'magnitude_trend': np.random.uniform(-0.5, 0.5)
        }
        
        synthetic_data.append({
            'city': f"Synthetic_{i}",
            'lat': lat,
            'lon': lon,
            'features': features,
            'risk_score': risk_score,
            'timestamp': time.time()
        })
    
    print(f"[OK] {len(synthetic_data)} sentetik ornek olusturuldu")
    return synthetic_data

def main():
    print("="*60)
    print("ML MODELLERI EGITIM SURECI")
    print("="*60)
    
    # 1. Eğitim verisi topla
    training_data = collect_training_data()
    
    if len(training_data) < 20:
        print("Yeterli veri yok, sentetik veri uretiliyor...")
        synthetic_data = generate_synthetic_data(num_samples=100)
        training_data.extend(synthetic_data)
    
    if len(training_data) < 20:
        print("Yeterli egitim verisi toplanamadi!")
        return
    
    # 2. Veriyi kaydet
    print(f"\n{len(training_data)} ornek kaydediliyor...")
    try:
        # Mevcut veriyi yükle ve birleştir
        if os.path.exists(EARTHQUAKE_HISTORY_FILE):
            with open(EARTHQUAKE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            training_data.extend(existing_data)
        
        with open(EARTHQUAKE_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)
        print(f"[OK] Veri kaydedildi: {EARTHQUAKE_HISTORY_FILE}")
    except Exception as e:
        print(f"[ERROR] Veri kaydedilemedi: {e}")
        return
    
    # 3. Risk tahmin modellerini eğit
    print(f"\nRisk tahmin modelleri egitiliyor ({len(training_data)} ornek ile)...")
    models = train_risk_prediction_model(training_data)
    
    if models:
        print("\n[OK] Risk tahmin modelleri egitildi!")
        print(f"Egitilen modeller: {list(models.keys())}")
        print(f"Model dosyasi: {RISK_PREDICTION_MODEL_FILE}")
    else:
        print("\n[ERROR] Risk tahmin modeli egitilemedi!")
    
    # 4. Anomali tespiti modelini eğit
    print(f"\nAnomali tespiti modeli egitiliyor...")
    try:
        # Özellik vektörlerini hazırla
        X_anomaly = []
        for record in training_data:
            if 'features' in record:
                features = record['features']
                feature_vector = [
                    features.get('count', 0),
                    features.get('max_magnitude', 0),
                    features.get('mean_magnitude', 0),
                    features.get('min_distance', 300),
                    features.get('activity_density', 0)
                ]
                X_anomaly.append(feature_vector)
        
        if len(X_anomaly) >= 20:
            X_anomaly = np.array(X_anomaly)
            
            # Isolation Forest modeli eğit
            isolation_model = IsolationForest(
                contamination=0.1,  # %10 anomali bekleniyor
                random_state=42,
                n_estimators=100
            )
            isolation_model.fit(X_anomaly)
            
            # Modeli kaydet
            import pickle
            with open(ANOMALY_DETECTION_MODEL_FILE, 'wb') as f:
                pickle.dump(isolation_model, f)
            
            print("[OK] Anomali tespiti modeli egitildi ve kaydedildi!")
            print(f"Model dosyasi: {ANOMALY_DETECTION_MODEL_FILE}")
        else:
            print("[WARNING] Anomali modeli icin yeterli veri yok")
    except Exception as e:
        print(f"[ERROR] Anomali modeli egitilemedi: {e}")
    
    print("\n" + "="*60)
    print("[OK] TUM MODELLER BASARIYLA EGITILDI!")
    print("="*60)

if __name__ == "__main__":
    main()

