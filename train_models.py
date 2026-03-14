#!/usr/bin/env python3
# LEGACY TRAINING FILE
# Yeni forecast pipeline için: python forecast/trainer.py
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
import sys
# TensorFlow log azaltma (--architectures ile)
if len(sys.argv) > 1 and sys.argv[1] == '--architectures':
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import json
import pickle
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# sklearn
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, mean_squared_error, roc_auc_score, average_precision_score, brier_score_loss
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.calibration import CalibratedClassifierCV

# XGBoost
import xgboost as xgb
from xgboost import XGBClassifier, XGBRegressor

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
    'magnitude_distance_ratio', 'magnitude_trend', 'neighbor_activity',
    'cluster_count', 'in_cluster', 'nearest_cluster_distance',
    'cluster_density', 'max_cluster_size', 'nearest_cluster_max_mag',
    'etas_score', 'etas_max_influence', 'etas_event_count',
    'recency_weighted_energy', 'b_value_proxy', 'swarm_intensity',
]
MIN_TRAINING_SAMPLES = 50


def build_feature_vector_for_prediction(features: Dict) -> np.ndarray:
    """
    Tahmin için feature vektörü (app ve servislerde kullanılır).
    neighbor_activity + ETAS dahil.
    """
    base = [
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
        features.get('magnitude_trend', 0),
        features.get('neighbor_activity', 0),
        features.get('cluster_count', 0),
        features.get('in_cluster', 0),
        features.get('nearest_cluster_distance', 300),
        features.get('cluster_density', 0),
        features.get('max_cluster_size', 0),
        features.get('nearest_cluster_max_mag', 0),
        features.get('etas_score', 0),
        features.get('etas_max_influence', 0),
        features.get('etas_event_count', 0),
        features.get('recency_weighted_energy', 0),
        features.get('b_value_proxy', 1.0),
        features.get('swarm_intensity', 0),
    ]
    X = np.array([base], dtype=np.float64)
    try:
        from ml_architectures import add_etas_features
        base_names = [n for n in FEATURE_NAMES if n not in ('omori_decay', 'time_decay', 'mag_weighted_omori')]
        X = add_etas_features(X, base_names)
    except Exception:
        pass
    return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)


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
        features.get('magnitude_trend', 0),
        features.get('neighbor_activity', 0),
        features.get('cluster_count', 0),
        features.get('in_cluster', 0),
        features.get('nearest_cluster_distance', 300),
        features.get('cluster_density', 0),
        features.get('max_cluster_size', 0),
        features.get('nearest_cluster_max_mag', 0),
        features.get('etas_score', 0),
        features.get('etas_max_influence', 0),
        features.get('etas_event_count', 0),
        features.get('recency_weighted_energy', 0),
        features.get('b_value_proxy', 1.0),
        features.get('swarm_intensity', 0),
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
    
    # Yetersiz veri varsa sentetik ekle (bootstrap+noise tercih edilir)
    if len(records) < MIN_TRAINING_SAMPLES and add_synthetic_if_needed:
        print(f"[TRAIN] Veri yetersiz ({len(records)}), sentetik veri ekleniyor...")
        synthetic = generate_synthetic_data(
            num_samples=MIN_TRAINING_SAMPLES - len(records) + 100,
            real_records=records
        )
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
    
    # ETAS feature'ları ana modele ekle (Omori decay) - daha stabil
    try:
        from ml_architectures import add_etas_features
        X = add_etas_features(X, FEATURE_NAMES)
        if 'omori_decay' not in FEATURE_NAMES:
            FEATURE_NAMES.extend(['omori_decay', 'time_decay', 'mag_weighted_omori'])
    except Exception:
        pass
    
    print(f"[TRAIN] Veri hazır: {len(X)} örnek, {X.shape[1]} özellik")
    print(f"[TRAIN] Toplam eğitim kaydı: {len(X)}")
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
    print(f"[TRAIN] Train metrics: accuracy={metrics['accuracy']}, f1={metrics['f1_score']}, mse={metrics['mse']}")
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


def train_and_compare_architectures(dataset_path: str = DEFAULT_DATASET_FILE) -> Optional[Dict]:
    """
    Tüm ML mimarilerini eğitir ve karşılaştırır.
    Çıktı: XGBoost accuracy, IsolationForest anomaly, LSTM accuracy, ETAS accuracy
    """
    print("="*60)
    print("ML MİMARİ KARŞILAŞTIRMASI")
    print("="*60)
    try:
        X, y_reg, _ = load_and_prepare_data(dataset_path)
    except Exception as e:
        print(f"[TRAIN] Veri yükleme hatası: {e}")
        return None

    from dataset_manager import load_dataset, get_raw_earthquakes
    from ml_architectures import train_all_architectures
    data = load_dataset(dataset_path)
    raw_eqs = get_raw_earthquakes(data)

    results = train_all_architectures(X, y_reg, FEATURE_NAMES, raw_earthquakes=raw_eqs)

    print("\n  Model              | Accuracy | F1      | MSE")
    print("  " + "-"*50)
    for name, r in results.items():
        m = r.get('metrics', r)
        if 'error' in m:
            print(f"  {name:<18} | HATA: {m['error']}")
        else:
            acc = m.get('accuracy', 0)
            f1 = m.get('f1_score', 0)
            mse = m.get('mse', 0)
            print(f"  {name:<18} | {acc:.4f}   | {f1:.4f}  | {mse:.4f}")
    print("="*60)
    return results


# --- Gerçek olasılıksal forecast pipeline (geleceğe dönük hedefler) ---

def build_feature_matrix_from_forecast_records(records: List[Dict]) -> Tuple:
    """Forecast kayıtlarından X ve hedef vektörlerini üretir."""
    X_list = []
    y_m4_24h = []
    y_m5_72h = []
    y_count_24h = []
    y_maxmag_7d = []
    timestamps = []

    for r in records:
        features = r.get("features", {})
        vec = build_feature_vector_for_prediction(features)
        if vec.ndim == 2:
            vec = vec[0]
        X_list.append(vec)
        y_m4_24h.append(r["y_m4_24h"])
        y_m5_72h.append(r["y_m5_72h"])
        y_count_24h.append(r["y_count_24h"])
        y_maxmag_7d.append(r["y_maxmag_7d"])
        timestamps.append(r["timestamp"])

    X = np.array(X_list, dtype=np.float64)
    return (
        np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0),
        np.array(y_m4_24h),
        np.array(y_m5_72h),
        np.array(y_count_24h, dtype=np.float64),
        np.array(y_maxmag_7d, dtype=np.float64),
        np.array(timestamps, dtype=np.float64),
    )


def time_ordered_split(X, y1, y2, y3, y4, timestamps, test_ratio=0.2):
    """Zaman sıralı train/test split (leakage önleme)."""
    order = np.argsort(timestamps)
    X = X[order]
    y1 = y1[order]
    y2 = y2[order]
    y3 = y3[order]
    y4 = y4[order]
    timestamps = timestamps[order]
    split_idx = int(len(X) * (1 - test_ratio))
    return (
        X[:split_idx], X[split_idx:],
        y1[:split_idx], y1[split_idx:],
        y2[:split_idx], y2[split_idx:],
        y3[:split_idx], y3[split_idx:],
        y4[:split_idx], y4[split_idx:],
    )


def train_forecast_models_from_earthquakes(earthquakes: List[Dict]) -> Dict:
    """
    Geleceğe dönük hedeflerle forecast modelleri eğitir.
    Döner: clf_m4_24h, clf_m5_72h, reg_count_24h, reg_maxmag_7d, metrics.
    """
    from earthquake_features import create_forecast_training_records

    records = create_forecast_training_records(earthquakes, time_window_hours=48)
    if not records:
        raise ValueError("Forecast eğitimi için kayıt üretilemedi")

    X, y_m4_24h, y_m5_72h, y_count_24h, y_maxmag_7d, timestamps = build_feature_matrix_from_forecast_records(records)

    (X_train, X_test, y1_train, y1_test, y2_train, y2_test, y3_train, y3_test, y4_train, y4_test) = time_ordered_split(
        X, y_m4_24h, y_m5_72h, y_count_24h, y_maxmag_7d, timestamps, test_ratio=0.2
    )

    pos1 = max(1, int(np.sum(y1_train == 1)))
    neg1 = max(1, int(np.sum(y1_train == 0)))
    scale_pos_weight_m4 = neg1 / pos1
    pos2 = max(1, int(np.sum(y2_train == 1)))
    neg2 = max(1, int(np.sum(y2_train == 0)))
    scale_pos_weight_m5 = neg2 / pos2
    print(f"  [forecast] scale_pos_weight M4: {scale_pos_weight_m4:.2f}")
    print(f"  [forecast] scale_pos_weight M5: {scale_pos_weight_m5:.2f}")

    import time as _time
    t0 = _time.time()
    print("  [forecast] Model eğitimi başlıyor (M4 24h, M5 72h, count, maxmag)...")

    clf_m4_base = XGBClassifier(
        n_estimators=250,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        scale_pos_weight=scale_pos_weight_m4,
        reg_lambda=1.0,
        random_state=42,
    )
    clf_m5_base = XGBClassifier(
        n_estimators=250,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        scale_pos_weight=scale_pos_weight_m5,
        reg_lambda=1.0,
        random_state=42,
    )

    clf_m4 = CalibratedClassifierCV(clf_m4_base, method="sigmoid", cv=3)
    clf_m5 = CalibratedClassifierCV(clf_m5_base, method="sigmoid", cv=3)

    reg_count = XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
    )
    reg_maxmag = XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
    )

    t1 = _time.time()
    clf_m4.fit(X_train, y1_train)
    print(f"  [forecast] clf_m4_24h eğitildi. Geçen: {int(_time.time() - t1)} sn")
    t1 = _time.time()
    clf_m5.fit(X_train, y2_train)
    print(f"  [forecast] clf_m5_72h eğitildi. Geçen: {int(_time.time() - t1)} sn")
    t1 = _time.time()
    reg_count.fit(X_train, y3_train)
    print(f"  [forecast] reg_count_24h eğitildi. Geçen: {int(_time.time() - t1)} sn")
    t1 = _time.time()
    reg_maxmag.fit(X_train, y4_train)
    print(f"  [forecast] reg_maxmag_7d eğitildi. Geçen: {int(_time.time() - t1)} sn")
    print(f"  [forecast] Tüm modeller bitti. Toplam model eğitim süresi: {int(_time.time() - t0)} sn")

    p1 = clf_m4.predict_proba(X_test)[:, 1]
    p2 = clf_m5.predict_proba(X_test)[:, 1]
    pred_count = reg_count.predict(X_test)
    pred_maxmag = reg_maxmag.predict(X_test)

    metrics = {
        "m4_24h": {
            "roc_auc": float(roc_auc_score(y1_test, p1)) if len(np.unique(y1_test)) > 1 else None,
            "pr_auc": float(average_precision_score(y1_test, p1)),
            "brier": float(brier_score_loss(y1_test, p1)),
        },
        "m5_72h": {
            "roc_auc": float(roc_auc_score(y2_test, p2)) if len(np.unique(y2_test)) > 1 else None,
            "pr_auc": float(average_precision_score(y2_test, p2)),
            "brier": float(brier_score_loss(y2_test, p2)),
        },
        "count_24h": {"rmse": float(np.sqrt(mean_squared_error(y3_test, pred_count)))},
        "maxmag_7d": {"rmse": float(np.sqrt(mean_squared_error(y4_test, pred_maxmag)))},
    }

    return {
        "clf_m4_24h": clf_m4,
        "clf_m5_72h": clf_m5,
        "reg_count_24h": reg_count,
        "reg_maxmag_7d": reg_maxmag,
        "metrics": metrics,
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "feature_names": FEATURE_NAMES.copy(),
        "model_type": "probabilistic_forecast",
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--architectures":
        train_and_compare_architectures()
    elif len(sys.argv) > 1 and sys.argv[1] == "--forecast":
        import time as _t
        from dataset_manager import load_dataset, get_raw_earthquakes, DEFAULT_DATASET_FILE
        data = load_dataset(DEFAULT_DATASET_FILE)
        raw = get_raw_earthquakes(data)
        if not raw:
            print("Forecast eğitimi için ham deprem verisi yok. earthquake_history.json dolu olmalı.")
            sys.exit(1)
        print("Forecast modelleri eğitiliyor (zaman bazlı split, calibrated classifier)...")
        total_start = _t.time()
        result = train_forecast_models_from_earthquakes(raw)
        path = os.path.join(MODEL_DIR, "forecast_latest.pkl")
        with open(path, "wb") as f:
            pickle.dump(result, f)
        total_elapsed = _t.time() - total_start
        print("[forecast] Eğitim tamamlandı.")
        print("Forecast model kaydedildi:", path)
        print(f"  Toplam süre: {int(total_elapsed)} sn ({total_elapsed / 60:.1f} dk)")
        metrics = result.get("metrics") or {}
        m4 = metrics.get("m4_24h") or {}
        m5 = metrics.get("m5_72h") or {}
        c24 = metrics.get("count_24h") or {}
        m7 = metrics.get("maxmag_7d") or {}
        print(f"[forecast] M4 24h ROC-AUC: {m4.get('roc_auc')}")
        print(f"[forecast] M5 72h ROC-AUC: {m5.get('roc_auc')}")
        print(f"[forecast] 24h Count RMSE: {c24.get('rmse')}")
        print(f"[forecast] 7g MaxMag RMSE: {m7.get('rmse')}")
    else:
        print("Legacy eğitim modu çalışıyor...")
        train_all()
