#!/usr/bin/env python3
# Gelişmiş ML Model Eğitimi - En Mükemmel Performans İçin

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import (
    KANDILLI_API, extract_features, train_risk_prediction_model,
    predict_earthquake_risk, TURKEY_CITIES, ISTANBUL_COORDS,
    EARTHQUAKE_HISTORY_FILE, RISK_PREDICTION_MODEL_FILE,
    ANOMALY_DETECTION_MODEL_FILE
)
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.model_selection import GridSearchCV, cross_val_score, KFold
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import xgboost as xgb
import lightgbm as lgb
import numpy as np
import json
import time
import pickle
import requests

def collect_real_data(num_attempts=5):
    """Gerçek deprem verilerini toplar (birden fazla deneme)"""
    print("Gercek deprem verileri toplaniyor...")
    all_earthquakes = []
    
    for attempt in range(num_attempts):
        try:
            response = requests.get(KANDILLI_API, timeout=15)
            response.raise_for_status()
            earthquakes = response.json().get('result', [])
            if earthquakes:
                all_earthquakes.extend(earthquakes)
                print(f"[OK] Deneme {attempt+1}: {len(earthquakes)} deprem verisi")
        except Exception as e:
            print(f"[WARNING] Deneme {attempt+1} basarisiz: {e}")
        time.sleep(1)
    
    # Tekrarları kaldır
    unique_earthquakes = []
    seen = set()
    for eq in all_earthquakes:
        eq_id = f"{eq.get('mag', 0)}_{eq.get('geojson', {}).get('coordinates', [0,0])}"
        if eq_id not in seen:
            seen.add(eq_id)
            unique_earthquakes.append(eq)
    
    print(f"[OK] Toplam {len(unique_earthquakes)} benzersiz deprem verisi")
    return unique_earthquakes

def generate_advanced_synthetic_data(num_samples=500):
    """Gelişmiş sentetik veri üretimi - gerçekçi senaryolar"""
    print(f"{num_samples} gelismis sentetik ornek uretiliyor...")
    
    synthetic_data = []
    
    # Türkiye koordinat aralıkları
    lat_range = (36.0, 42.0)
    lon_range = (26.0, 45.0)
    
    # Senaryo tipleri
    scenarios = [
        {'name': 'normal', 'prob': 0.5, 'mag_range': (2.0, 4.5), 'count_range': (0, 15)},
        {'name': 'active', 'prob': 0.3, 'mag_range': (3.0, 5.5), 'count_range': (10, 30)},
        {'name': 'high_risk', 'prob': 0.15, 'mag_range': (4.0, 6.5), 'count_range': (20, 50)},
        {'name': 'critical', 'prob': 0.05, 'mag_range': (5.0, 7.0), 'count_range': (30, 80)}
    ]
    
    for i in range(num_samples):
        # Senaryo seç
        rand = np.random.random()
        cumsum = 0
        scenario = scenarios[0]
        for s in scenarios:
            cumsum += s['prob']
            if rand <= cumsum:
                scenario = s
                break
        
        # Rastgele konum
        lat = np.random.uniform(lat_range[0], lat_range[1])
        lon = np.random.uniform(lon_range[0], lon_range[1])
        
        # Senaryoya göre özellikler
        count = np.random.randint(scenario['count_range'][0], scenario['count_range'][1])
        max_magnitude = np.random.uniform(scenario['mag_range'][0], scenario['mag_range'][1])
        mean_magnitude = max_magnitude * np.random.uniform(0.65, 0.85)
        std_magnitude = mean_magnitude * np.random.uniform(0.15, 0.35)
        
        # Mesafe dağılımı (senaryoya göre)
        if scenario['name'] in ['high_risk', 'critical']:
            min_distance = np.random.uniform(5, 50)
            mean_distance = min_distance * np.random.uniform(1.5, 3.0)
        else:
            min_distance = np.random.uniform(20, 200)
            mean_distance = min_distance * np.random.uniform(1.8, 2.8)
        
        mean_depth = np.random.uniform(5, 35)
        mean_interval = np.random.uniform(200, 7200)
        min_interval = np.random.uniform(60, 1800)
        
        # Büyüklük dağılımı
        mag_above_4 = int(count * np.random.uniform(0.1, 0.4)) if max_magnitude >= 4 else 0
        mag_above_5 = int(count * np.random.uniform(0.0, 0.2)) if max_magnitude >= 5 else 0
        mag_above_6 = int(count * np.random.uniform(0.0, 0.1)) if max_magnitude >= 6 else 0
        
        # Mesafe dağılımı
        within_50km = int(count * np.random.uniform(0.1, 0.5))
        within_100km = int(count * np.random.uniform(0.3, 0.7))
        within_150km = int(count * np.random.uniform(0.5, 0.9))
        
        # Derinlik dağılımı
        shallow_quakes = int(count * np.random.uniform(0.3, 0.7))
        deep_quakes = int(count * np.random.uniform(0.1, 0.3))
        
        # Fay hattı mesafesi
        nearest_fault_distance = np.random.uniform(5, 150)
        
        # Aktivite yoğunluğu
        activity_density = count / (np.pi * (mean_distance ** 2)) if mean_distance > 0 else 0
        
        # Büyüklük-mesafe oranı
        magnitude_distance_ratio = max_magnitude / (min_distance + 1)
        
        # Zaman trendi
        magnitude_trend = np.random.uniform(-0.8, 0.8)
        
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
            'mag_above_4': mag_above_4,
            'mag_above_5': mag_above_5,
            'mag_above_6': mag_above_6,
            'within_50km': within_50km,
            'within_100km': within_100km,
            'within_150km': within_150km,
            'shallow_quakes': shallow_quakes,
            'deep_quakes': deep_quakes,
            'nearest_fault_distance': nearest_fault_distance,
            'activity_density': activity_density,
            'magnitude_distance_ratio': magnitude_distance_ratio,
            'magnitude_trend': magnitude_trend
        }
        
        # Gelişmiş risk skoru hesaplama
        risk_score = (
            max_magnitude * 0.35 +
            (count / 20) * 0.25 +
            (1 / (min_distance / 30 + 1)) * 0.25 +
            (1 / (mean_interval / 3600 + 1)) * 0.10 +
            (1 / (nearest_fault_distance / 50 + 1)) * 0.05
        )
        risk_score = min(10, max(0, risk_score))
        
        synthetic_data.append({
            'city': f"{scenario['name']}_{i}",
            'lat': lat,
            'lon': lon,
            'features': features,
            'risk_score': risk_score,
            'timestamp': time.time(),
            'scenario': scenario['name']
        })
    
    print(f"[OK] {len(synthetic_data)} gelismis sentetik ornek olusturuldu")
    return synthetic_data

def train_optimized_models(training_data):
    """Hiperparametre optimizasyonu ile modelleri eğitir"""
    print("\n" + "="*60)
    print("GELISMIS MODEL EGITIMI - HIPERPARAMETRE OPTIMIZASYONU")
    print("="*60)
    
    if not training_data or len(training_data) < 50:
        print("[ERROR] Yeterli veri yok!")
        return None
    
    # Veriyi hazırla
    X = []
    y = []
    
    for record in training_data:
        if 'features' in record and 'risk_score' in record:
            features = record['features']
            risk = record['risk_score']
            
            feature_vector = [
                features.get('count', 0),
                features.get('max_magnitude', 0),
                features.get('mean_magnitude', 0),
                features.get('std_magnitude', 0),
                features.get('min_distance', 300),
                features.get('mean_distance', 300),
                features.get('mean_depth', 10),
                features.get('mean_interval', 3600),
                features.get('min_interval', 3600),
                features.get('mag_above_4', 0),
                features.get('mag_above_5', 0),
                features.get('within_50km', 0),
                features.get('within_100km', 0),
                features.get('nearest_fault_distance', 200),
                features.get('activity_density', 0),
                features.get('magnitude_distance_ratio', 0),
                features.get('magnitude_trend', 0)
            ]
            
            X.append(feature_vector)
            y.append(risk)
    
    if len(X) < 50:
        return None
    
    X = np.array(X)
    y = np.array(y)
    
    # Train-test split
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"\nEgitim seti: {len(X_train)} ornek")
    print(f"Test seti: {len(X_test)} ornek")
    print(f"Feature sayisi: {X.shape[1]}")
    
    # Cross-validation için KFold
    kfold = KFold(n_splits=5, shuffle=True, random_state=42)
    
    trained_models = {}
    predictions = {}
    cv_scores = {}
    
    # 1. Random Forest - Grid Search
    print("\n[1/3] Random Forest - Grid Search optimizasyonu...")
    rf_param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [8, 10, 12, 15],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4]
    }
    
    rf_base = RandomForestRegressor(random_state=42, n_jobs=-1)
    rf_grid = GridSearchCV(rf_base, rf_param_grid, cv=kfold, scoring='r2', n_jobs=-1, verbose=0)
    rf_grid.fit(X_train, y_train)
    
    print(f"  En iyi parametreler: {rf_grid.best_params_}")
    print(f"  En iyi CV skoru: {rf_grid.best_score_:.4f}")
    
    rf_model = rf_grid.best_estimator_
    rf_pred = rf_model.predict(X_test)
    rf_mse = mean_squared_error(y_test, rf_pred)
    rf_r2 = r2_score(y_test, rf_pred)
    rf_mae = mean_absolute_error(y_test, rf_pred)
    
    print(f"  Test MSE: {rf_mse:.4f}, R²: {rf_r2:.4f}, MAE: {rf_mae:.4f}")
    
    trained_models['random_forest'] = rf_model
    predictions['random_forest'] = rf_pred
    cv_scores['random_forest'] = rf_grid.best_score_
    
    # 2. XGBoost - Grid Search
    print("\n[2/3] XGBoost - Grid Search optimizasyonu...")
    xgb_param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [4, 6, 8],
        'learning_rate': [0.05, 0.1, 0.15],
        'subsample': [0.8, 0.9, 1.0],
        'colsample_bytree': [0.8, 0.9, 1.0]
    }
    
    xgb_base = xgb.XGBRegressor(random_state=42, n_jobs=-1)
    xgb_grid = GridSearchCV(xgb_base, xgb_param_grid, cv=kfold, scoring='r2', n_jobs=-1, verbose=0)
    xgb_grid.fit(X_train, y_train)
    
    print(f"  En iyi parametreler: {xgb_grid.best_params_}")
    print(f"  En iyi CV skoru: {xgb_grid.best_score_:.4f}")
    
    xgb_model = xgb_grid.best_estimator_
    xgb_pred = xgb_model.predict(X_test)
    xgb_mse = mean_squared_error(y_test, xgb_pred)
    xgb_r2 = r2_score(y_test, xgb_pred)
    xgb_mae = mean_absolute_error(y_test, xgb_pred)
    
    print(f"  Test MSE: {xgb_mse:.4f}, R²: {xgb_r2:.4f}, MAE: {xgb_mae:.4f}")
    
    trained_models['xgboost'] = xgb_model
    predictions['xgboost'] = xgb_pred
    cv_scores['xgboost'] = xgb_grid.best_score_
    
    # 3. LightGBM - Grid Search
    print("\n[3/3] LightGBM - Grid Search optimizasyonu...")
    lgb_param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [4, 6, 8, 10],
        'learning_rate': [0.05, 0.1, 0.15],
        'num_leaves': [31, 50, 70],
        'subsample': [0.8, 0.9, 1.0]
    }
    
    lgb_base = lgb.LGBMRegressor(random_state=42, n_jobs=-1, verbose=-1)
    lgb_grid = GridSearchCV(lgb_base, lgb_param_grid, cv=kfold, scoring='r2', n_jobs=-1, verbose=0)
    lgb_grid.fit(X_train, y_train)
    
    print(f"  En iyi parametreler: {lgb_grid.best_params_}")
    print(f"  En iyi CV skoru: {lgb_grid.best_score_:.4f}")
    
    lgb_model = lgb_grid.best_estimator_
    lgb_pred = lgb_model.predict(X_test)
    lgb_mse = mean_squared_error(y_test, lgb_pred)
    lgb_r2 = r2_score(y_test, lgb_pred)
    lgb_mae = mean_absolute_error(y_test, lgb_pred)
    
    print(f"  Test MSE: {lgb_mse:.4f}, R²: {lgb_r2:.4f}, MAE: {lgb_mae:.4f}")
    
    trained_models['lightgbm'] = lgb_model
    predictions['lightgbm'] = lgb_pred
    cv_scores['lightgbm'] = lgb_grid.best_score_
    
    # Ensemble tahmin (ağırlıklı ortalama - CV skorlarına göre)
    print("\nEnsemble model hesaplaniyor...")
    total_cv_score = sum(cv_scores.values())
    weights = {k: v / total_cv_score for k, v in cv_scores.items()}
    
    print(f"  Model agirliklari:")
    for name, weight in weights.items():
        print(f"    {name}: {weight:.3f}")
    
    ensemble_pred = (
        weights['random_forest'] * predictions['random_forest'] +
        weights['xgboost'] * predictions['xgboost'] +
        weights['lightgbm'] * predictions['lightgbm']
    )
    
    ensemble_mse = mean_squared_error(y_test, ensemble_pred)
    ensemble_r2 = r2_score(y_test, ensemble_pred)
    ensemble_mae = mean_absolute_error(y_test, ensemble_pred)
    
    print(f"\nEnsemble Sonuclari:")
    print(f"  MSE: {ensemble_mse:.4f}")
    print(f"  R²: {ensemble_r2:.4f}")
    print(f"  MAE: {ensemble_mae:.4f}")
    
    # Feature importance analizi
    print("\nFeature Importance Analizi:")
    rf_importance = rf_model.feature_importances_
    xgb_importance = xgb_model.feature_importances_
    lgb_importance = lgb_model.feature_importances_
    
    feature_names = [
        'count', 'max_magnitude', 'mean_magnitude', 'std_magnitude',
        'min_distance', 'mean_distance', 'mean_depth', 'mean_interval',
        'min_interval', 'mag_above_4', 'mag_above_5', 'within_50km',
        'within_100km', 'nearest_fault_distance', 'activity_density',
        'magnitude_distance_ratio', 'magnitude_trend'
    ]
    
    avg_importance = (rf_importance + xgb_importance + lgb_importance) / 3
    importance_sorted = sorted(zip(feature_names, avg_importance), key=lambda x: x[1], reverse=True)
    
    print("  En onemli 5 feature:")
    for i, (name, imp) in enumerate(importance_sorted[:5], 1):
        print(f"    {i}. {name}: {imp:.4f}")
    
    # Modeli kaydet
    try:
        os.makedirs(os.path.dirname(RISK_PREDICTION_MODEL_FILE), exist_ok=True)
        with open(RISK_PREDICTION_MODEL_FILE, 'wb') as f:
            pickle.dump({
                'models': trained_models,
                'weights': weights,
                'feature_names': feature_names,
                'cv_scores': cv_scores,
                'performance': {
                    'ensemble_r2': ensemble_r2,
                    'ensemble_mse': ensemble_mse,
                    'ensemble_mae': ensemble_mae
                }
            }, f)
        print(f"\n[OK] Optimize edilmis modeller kaydedildi: {RISK_PREDICTION_MODEL_FILE}")
    except Exception as e:
        print(f"[ERROR] Model kaydedilemedi: {e}")
    
    return trained_models, weights

def train_optimized_anomaly_model(training_data):
    """Optimize edilmiş anomali tespiti modeli"""
    print("\n" + "="*60)
    print("ANOMALI TESPITI MODELI - OPTIMIZASYON")
    print("="*60)
    
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
    
    if len(X_anomaly) < 50:
        print("[ERROR] Yeterli veri yok!")
        return None
    
    X_anomaly = np.array(X_anomaly)
    
    # Contamination parametrelerini test et
    print("\nContamination parametresi optimizasyonu...")
    contamination_values = [0.05, 0.1, 0.15, 0.2]
    best_contamination = 0.1
    best_score = -1
    
    for cont in contamination_values:
        model = IsolationForest(contamination=cont, random_state=42, n_estimators=200)
        model.fit(X_anomaly)
        scores = model.score_samples(X_anomaly)
        # Anomali tespit oranı
        anomalies = (scores < np.percentile(scores, cont * 100)).sum()
        score = anomalies / len(X_anomaly)
        print(f"  Contamination {cont}: {anomalies}/{len(X_anomaly)} anomali ({score:.2%})")
        if abs(score - cont) < abs(best_score - cont):
            best_contamination = cont
            best_score = score
    
    print(f"\nEn iyi contamination: {best_contamination}")
    
    # Final model
    isolation_model = IsolationForest(
        contamination=best_contamination,
        random_state=42,
        n_estimators=200,
        max_samples='auto',
        n_jobs=-1
    )
    isolation_model.fit(X_anomaly)
    
    # Modeli kaydet
    try:
        with open(ANOMALY_DETECTION_MODEL_FILE, 'wb') as f:
            pickle.dump(isolation_model, f)
        print(f"[OK] Anomali modeli kaydedildi: {ANOMALY_DETECTION_MODEL_FILE}")
    except Exception as e:
        print(f"[ERROR] Anomali modeli kaydedilemedi: {e}")
    
    return isolation_model

def main():
    print("="*60)
    print("UST DUZEY ML MODEL EGITIMI - EN MUKEMMEL PERFORMANS")
    print("="*60)
    
    # 1. Gerçek veri topla
    print("\n[1/4] Gercek deprem verileri toplaniyor...")
    real_earthquakes = collect_real_data(num_attempts=3)
    
    # 2. Eğitim verisi oluştur
    print("\n[2/4] Egitim verisi olusturuluyor...")
    training_data = []
    
    if real_earthquakes:
        # Gerçek veri ile
        cities_to_use = list(TURKEY_CITIES.keys())[:30]  # 30 şehir
        
        for city_name in cities_to_use:
            city_data = TURKEY_CITIES[city_name]
            lat = city_data['lat']
            lon = city_data['lon']
            
            features = extract_features(real_earthquakes, lat, lon, time_window_hours=24)
            if features:
                risk_result = predict_earthquake_risk(real_earthquakes, lat, lon)
                training_data.append({
                    'city': city_name,
                    'lat': lat,
                    'lon': lon,
                    'features': features,
                    'risk_score': risk_result.get('risk_score', 2.0),
                    'timestamp': time.time()
                })
    
    # 3. Gelişmiş sentetik veri üret
    print("\n[3/4] Gelismis sentetik veri uretiliyor...")
    synthetic_data = generate_advanced_synthetic_data(num_samples=1000)
    training_data.extend(synthetic_data)
    
    print(f"\nToplam egitim verisi: {len(training_data)} ornek")
    
    # 4. Veriyi kaydet
    print("\n[4/4] Veri kaydediliyor...")
    try:
        if os.path.exists(EARTHQUAKE_HISTORY_FILE):
            with open(EARTHQUAKE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            # Sadece son 500 örneği tut (hafıza için)
            training_data.extend(existing_data[-500:] if len(existing_data) > 500 else existing_data)
        
        with open(EARTHQUAKE_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)
        print(f"[OK] {len(training_data)} ornek kaydedildi")
    except Exception as e:
        print(f"[ERROR] Veri kaydedilemedi: {e}")
        return
    
    # 5. Optimize edilmiş modelleri eğit
    print("\n" + "="*60)
    print("MODEL EGITIMI BASLIYOR...")
    print("="*60)
    
    models, weights = train_optimized_models(training_data)
    
    if models:
        # 6. Anomali modelini eğit
        train_optimized_anomaly_model(training_data)
        
        print("\n" + "="*60)
        print("[OK] TUM MODELLER BASARIYLA EGITILDI!")
        print("="*60)
        print(f"Egitim ornek sayisi: {len(training_data)}")
        print(f"Egitilen modeller: {list(models.keys())}")
        print(f"Model agirliklari: {weights}")
    else:
        print("\n[ERROR] Model egitilemedi!")

if __name__ == "__main__":
    main()

