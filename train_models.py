#!/usr/bin/env python3
"""
train_models.py
ML model eğitimi modülü.
- Veri seti yükleme
- Feature engineering
- XGBoost risk tahmin modeli
- IsolationForest anomaly detection
- Model versiyonlama (models/model_v1.pkl, model_v2.pkl, ...)
- Metrikler: accuracy, f1 score, feature importance
- feature_importance.json kaydetme
"""

import os
import json
import pickle
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# sklearn
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, mean_squared_error
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest

# XGBoost
import xgboost as xgb

# Proje modülleri
from dataset_manager import get_training_records, DEFAULT_DATASET_FILE
from data_collector import generate_synthetic_data

# Sabitler
MODEL_DIR = 'models'
FEATURE_NAMES = [
    'count', 'max_magnitude', 'mean_magnitude', 'std_magnitude',
    'min_distance', 'mean_distance', 'mean_depth', 'mean_interval',
    'min_interval', 'mag_above_4', 'mag_above_5', 'within_50km',
    'within_100km', 'nearest_fault_distance', 'activity_density',
    'magnitude_distance_ratio', 'magnitude_trend'
]
MIN_TRAINING_SAMPLES = 50


def _build_feature_vector(record: Dict) -> Optional[List[float]]:
    """Kayıttan feature vektörü oluşturur."""
    if 'features' not in record or 'risk_score' not in record:
        return None
    features = record['features']
    vector = [
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
    return vector


def _risk_to_class(risk: float) -> int:
    """Risk skorunu sınıf etiketine çevirir (0-3)."""
    if risk < 2.5:
        return 0  # Düşük
    elif risk < 5.0:
        return 1  # Orta
    elif risk < 7.5:
        return 2  # Yüksek
    else:
        return 3  # Çok Yüksek


def get_next_model_version() -> int:
    """models/ klasöründeki mevcut versiyonlara göre bir sonraki versiyon numarasını döndürür."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    max_v = 0
    for f in os.listdir(MODEL_DIR):
        if f.startswith('model_v') and f.endswith('.pkl'):
            try:
                v = int(f.replace('model_v', '').replace('.pkl', ''))
                max_v = max(max_v, v)
            except ValueError:
                pass
    return max_v + 1


def load_and_prepare_data(
    dataset_path: str = DEFAULT_DATASET_FILE,
    add_synthetic_if_needed: bool = True
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Veri setini yükler, feature engineering uygular.
    
    Returns:
        (X, y_regression, y_classification)
    """
    records = get_training_records(dataset_path)
    
    # Yetersiz veri varsa sentetik ekle
    if len(records) < MIN_TRAINING_SAMPLES and add_synthetic_if_needed:
        print(f"[TRAIN] Veri yetersiz ({len(records)}), sentetik veri ekleniyor...")
        synthetic = generate_synthetic_data(num_samples=MIN_TRAINING_SAMPLES - len(records) + 100)
        records.extend(synthetic)
    
    if len(records) < MIN_TRAINING_SAMPLES:
        raise ValueError(f"En az {MIN_TRAINING_SAMPLES} eğitim örneği gerekli. Mevcut: {len(records)}")
    
    X = []
    y_reg = []
    for r in records:
        vec = _build_feature_vector(r)
        if vec is not None:
            X.append(vec)
            y_reg.append(r['risk_score'])
    
    X = np.array(X, dtype=np.float64)
    y_reg = np.array(y_reg)
    y_cls = np.array([_risk_to_class(r) for r in y_reg])
    
    # NaN/Inf temizleme
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    
    print(f"[TRAIN] Veri hazır: {len(X)} örnek, {X.shape[1]} özellik")
    return X, y_reg, y_cls


def train_xgboost(X_train, y_train_reg, X_test, y_test_reg, y_test_cls) -> Tuple[Any, Dict]:
    """
    XGBoost modeli eğitir.
    Regression için eğitilir, classification metrikleri risk sınıflarına çevrilerek hesaplanır.
    
    Returns:
        (model, metrics_dict)
    """
    print("[TRAIN] XGBoost modeli eğitiliyor...")
    
    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=42
    )
    model.fit(X_train, y_train_reg, verbose=False)
    
    # Tahminler
    y_pred_reg = model.predict(X_test)
    y_pred_cls = np.array([_risk_to_class(p) for p in y_pred_reg])
    
    # Metrikler
    mse = mean_squared_error(y_test_reg, y_pred_reg)
    accuracy = accuracy_score(y_test_cls, y_pred_cls)
    f1 = f1_score(y_test_cls, y_pred_cls, average='weighted', zero_division=0)
    
    metrics = {
        'accuracy': round(float(accuracy), 4),
        'f1_score': round(float(f1), 4),
        'mse': round(float(mse), 4),
        'samples_train': len(X_train),
        'samples_test': len(X_test)
    }
    print(f"[TRAIN] XGBoost - Accuracy: {metrics['accuracy']}, F1: {metrics['f1_score']}, MSE: {metrics['mse']}")
    return model, metrics


def train_isolation_forest(X: np.ndarray) -> Any:
    """Anomaly detection için IsolationForest eğitir."""
    print("[TRAIN] IsolationForest (anomaly detection) eğitiliyor...")
    model = IsolationForest(
        n_estimators=100,
        contamination=0.1,
        random_state=42
    )
    model.fit(X)
    return model


def get_feature_importance(model: Any) -> Dict[str, float]:
    """XGBoost modelinden feature importance alır."""
    if hasattr(model, 'feature_importances_'):
        imp = model.feature_importances_
        return {name: float(imp[i]) for i, name in enumerate(FEATURE_NAMES) if i < len(imp)}
    return {}


def save_models(
    xgb_model: Any,
    iso_model: Any,
    metrics: Dict,
    feature_importance: Dict
) -> str:
    """
    Modelleri ve metrikleri kaydeder.
    models/model_vN.pkl, models/anomaly_vN.pkl, feature_importance.json
    
    Returns:
        Kaydedilen model versiyonu (örn: "v3")
    """
    os.makedirs(MODEL_DIR, exist_ok=True)
    version = get_next_model_version()
    v_str = f"v{version}"
    
    # XGBoost model
    model_path = os.path.join(MODEL_DIR, f'model_{v_str}.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump({
            'model': xgb_model,
            'version': version,
            'metrics': metrics,
            'feature_names': FEATURE_NAMES,
            'trained_at': datetime.now().isoformat()
        }, f)
    print(f"[TRAIN] Model kaydedildi: {model_path}")
    
    # IsolationForest
    anomaly_path = os.path.join(MODEL_DIR, f'anomaly_{v_str}.pkl')
    with open(anomaly_path, 'wb') as f:
        pickle.dump({
            'model': iso_model,
            'version': version,
            'trained_at': datetime.now().isoformat()
        }, f)
    print(f"[TRAIN] Anomaly modeli kaydedildi: {anomaly_path}")
    
    # feature_importance.json
    fi_data = {
        'version': v_str,
        'trained_at': datetime.now().isoformat(),
        'feature_importance': feature_importance,
        'metrics': metrics
    }
    fi_path = os.path.join(MODEL_DIR, 'feature_importance.json')
    with open(fi_path, 'w', encoding='utf-8') as f:
        json.dump(fi_data, f, ensure_ascii=False, indent=2)
    print(f"[TRAIN] Feature importance kaydedildi: {fi_path}")
    
    return v_str


def train_all(
    dataset_path: str = DEFAULT_DATASET_FILE
) -> Optional[str]:
    """
    Tüm eğitim pipeline'ını çalıştırır:
    1. Veri yükle
    2. Feature engineering
    3. XGBoost eğit
    4. IsolationForest eğit
    5. Modelleri kaydet
    6. feature_importance.json kaydet
    
    Returns:
        Model versiyonu (örn: "v2") veya None (hata durumunda)
    """
    print("="*60)
    print("ML MODEL EĞİTİMİ BAŞLATILDI")
    print("="*60)
    
    try:
        # 1. Veri yükle
        X, y_reg, y_cls = load_and_prepare_data(dataset_path)
        
        # 2. Train-test split
        X_train, X_test, y_train_reg, y_test_reg = train_test_split(
            X, y_reg, test_size=0.2, random_state=42
        )
        y_test_cls = np.array([_risk_to_class(r) for r in y_test_reg])
        
        # 3. XGBoost eğit
        xgb_model, metrics = train_xgboost(
            X_train, y_train_reg, X_test, y_test_reg, y_test_cls
        )
        
        # 4. IsolationForest eğit
        iso_model = train_isolation_forest(X_train)
        
        # 5. Feature importance
        fi = get_feature_importance(xgb_model)
        
        # 6. Kaydet
        v_str = save_models(xgb_model, iso_model, metrics, fi)
        
        print("="*60)
        print(f"EĞİTİM TAMAMLANDI - Model {v_str}")
        print(f"Accuracy: {metrics['accuracy']}, F1: {metrics['f1_score']}")
        print("="*60)
        return v_str
        
    except Exception as e:
        print(f"[TRAIN] HATA: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_latest_model_path() -> Optional[str]:
    """models/ klasöründeki en son model dosyasının yolunu döndürür."""
    if not os.path.exists(MODEL_DIR):
        return None
    max_v = 0
    path = None
    for f in os.listdir(MODEL_DIR):
        if f.startswith('model_v') and f.endswith('.pkl'):
            try:
                v = int(f.replace('model_v', '').replace('.pkl', ''))
                if v > max_v:
                    max_v = v
                    path = os.path.join(MODEL_DIR, f)
            except ValueError:
                pass
    return path


def load_latest_model() -> Optional[Dict]:
    """
    En son eğitilmiş modeli yükler.
    app.py predict için uyumlu format: {'xgboost': model} veya None
    """
    path = get_latest_model_path()
    if not path:
        return None
    try:
        with open(path, 'rb') as f:
            data = pickle.load(f)
        model = data.get('model')
        if model is not None:
            return {'xgboost': model}  # app uyumluluğu
        return None
    except Exception:
        return None


if __name__ == "__main__":
    train_all()
