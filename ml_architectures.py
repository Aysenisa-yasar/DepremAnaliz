#!/usr/bin/env python3
"""
ml_architectures.py
Deprem analizi için araştırma seviyesi ML model mimarileri.
1. Ensemble Stacking - XGBoost + RandomForest + LightGBM
2. LSTM Time-Series - Şehir/bölge aktivite dizisi
3. ETAS-Inspired - Omori/Utsu aftershock decay (deprem biliminde yaygın)
"""

import os
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

# Temel modeller
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, accuracy_score, f1_score
from sklearn.preprocessing import StandardScaler

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

# LSTM için opsiyonel
FEATURE_NAMES = [
    'count', 'max_magnitude', 'mean_magnitude', 'std_magnitude',
    'min_distance', 'mean_distance', 'mean_depth', 'mean_interval',
    'min_interval', 'mag_above_4', 'mag_above_5', 'within_50km',
    'within_100km', 'nearest_fault_distance', 'activity_density',
    'magnitude_distance_ratio', 'magnitude_trend', 'neighbor_activity',
    'cluster_count', 'in_cluster', 'nearest_cluster_distance',
    'cluster_density', 'max_cluster_size', 'nearest_cluster_max_mag'
]

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.callbacks import EarlyStopping
    HAS_LSTM = True
except ImportError:
    HAS_LSTM = False


def _risk_to_class(risk: float) -> int:
    if risk < 2.5: return 0
    elif risk < 5.0: return 1
    elif risk < 7.5: return 2
    else: return 3


# =============================================================================
# 1. ENSEMBLE STACKING
# =============================================================================

def train_ensemble_stacking(
    X: np.ndarray, y: np.ndarray,
    test_size: float = 0.2, random_state: int = 42
) -> Tuple[Any, Dict]:
    """
    XGBoost + RandomForest + LightGBM stacking ensemble.
    Deprem risk tahmininde tabular veri için güçlü performans.
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    base_models = []
    if HAS_XGB:
        m1 = xgb.XGBRegressor(n_estimators=80, max_depth=5, learning_rate=0.1, random_state=42)
        m1.fit(X_train_s, y_train, verbose=False)
        base_models.append(('xgb', m1))
    m2 = RandomForestRegressor(n_estimators=80, max_depth=8, random_state=42)
    m2.fit(X_train_s, y_train)
    base_models.append(('rf', m2))
    if HAS_LGB:
        m3 = lgb.LGBMRegressor(n_estimators=80, max_depth=5, learning_rate=0.1, random_state=42, verbose=-1)
        m3.fit(np.asarray(X_train_s), y_train)
        base_models.append(('lgb', m3))

    # Stacking: base model tahminlerinin ortalaması
    def predict_ensemble(models, X_s):
        X_arr = np.asarray(X_s)
        preds = [m.predict(X_arr) for _, m in models]
        return np.mean(preds, axis=0)

    y_pred = predict_ensemble(base_models, X_test_s)
    mse = mean_squared_error(y_test, y_pred)
    y_cls_true = np.array([_risk_to_class(r) for r in y_test])
    y_cls_pred = np.array([_risk_to_class(p) for p in y_pred])
    acc = accuracy_score(y_cls_true, y_cls_pred)
    f1 = f1_score(y_cls_true, y_cls_pred, average='weighted', zero_division=0)

    return {
        'models': base_models,
        'scaler': scaler,
        'predict_fn': predict_ensemble
    }, {
        'mse': round(float(mse), 4),
        'accuracy': round(float(acc), 4),
        'f1_score': round(float(f1), 4),
        'architecture': 'ensemble_stacking'
    }


# =============================================================================
# 2. LSTM TIME-SERIES (şehir × t1..t5 sequence)
# =============================================================================

def build_lstm_sequence_dataset(records: List[Dict]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    create_sequence_records_for_lstm çıktısından LSTM için X, y oluşturur.
    X: (n_samples, seq_len, n_features) - şehir × zaman penceresi
    """
    try:
        from earthquake_features import create_sequence_records_for_lstm
    except ImportError:
        return None, None
    if not records or not any(r.get('geojson') for r in records):
        return None, None
    seq_records = create_sequence_records_for_lstm(records)
    if not seq_records:
        return None, None
    X_list, y_list = [], []
    for rec in seq_records:
        seq = rec.get('sequence', [])
        if len(seq) < 2:
            continue
        # Pad to same length
        max_len = max(len(s) for s in seq)
        padded = []
        for s in seq:
            v = list(s) if hasattr(s, '__iter__') and not isinstance(s, (str, dict)) else [s]
            v = v + [0.0] * (max_len - len(v))
            padded.append(v[:max_len])
        X_list.append(padded)
        y_list.append(rec.get('risk_score', 2.0))
    if not X_list:
        return None, None
    X = np.array(X_list, dtype=np.float64)
    y = np.array(y_list)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    return X, y


def _create_sequences(X: np.ndarray, y: np.ndarray, seq_len: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """X,y'den (samples, seq_len, features) ve (samples,) oluşturur (fallback)."""
    seqs, targets = [], []
    for i in range(len(X) - seq_len):
        seqs.append(X[i:i+seq_len])
        targets.append(y[i+seq_len-1])
    return np.array(seqs), np.array(targets)


def train_lstm_sequence(
    X: np.ndarray, y: np.ndarray,
    seq_len: int = 5, epochs: int = 50, test_size: float = 0.2,
    raw_earthquakes: Optional[List[Dict]] = None
) -> Tuple[Optional[Dict], Dict]:
    """
    LSTM ile zaman serisi modeli.
    raw_earthquakes verilirse: şehir × time_window sequence kullanır.
    Verilmezse: X,y'den sliding window sequence (fallback).
    """
    if not HAS_LSTM:
        return None, {'architecture': 'lstm', 'error': 'tensorflow not installed'}

    # Öncelik: raw deprem verisinden sequence dataset
    if raw_earthquakes:
        X_seq, y_seq = build_lstm_sequence_dataset(raw_earthquakes)
        if X_seq is not None and len(X_seq) >= 20:
            pass  # use X_seq, y_seq
        else:
            X_seq, y_seq = None, None
    else:
        X_seq, y_seq = None, None

    if X_seq is None or y_seq is None:
        if len(X) < 50:
            return None, {'architecture': 'lstm', 'error': 'insufficient data for sequences'}
        X_seq, y_seq = _create_sequences(X, y, seq_len)
    X_train, X_test, y_train, y_test = train_test_split(X_seq, y_seq, test_size=test_size, random_state=42)

    scaler = StandardScaler()
    n_samples, n_steps, n_feat = X_train.shape
    X_train_flat = X_train.reshape(-1, n_feat)
    scaler.fit(X_train_flat)
    X_train_s = scaler.transform(X_train_flat).reshape(n_samples, n_steps, n_feat)
    n_test = X_test.shape[0]
    X_test_s = scaler.transform(X_test.reshape(-1, n_feat)).reshape(n_test, n_steps, n_feat)

    from tensorflow.keras.layers import Input
    model = Sequential([
        Input(shape=(n_steps, n_feat)),
        LSTM(32, return_sequences=True),
        Dropout(0.2),
        LSTM(16),
        Dropout(0.2),
        Dense(8, activation='relu'),
        Dense(1)
    ])
    model.compile(optimizer='adam', loss='mse')
    model.fit(
        X_train_s, y_train,
        epochs=min(epochs, 30),
        batch_size=16,
        validation_split=0.1,
        callbacks=[EarlyStopping(patience=5, restore_best_weights=True)],
        verbose=0
    )

    y_pred = model.predict(X_test_s, verbose=0).flatten()
    mse = mean_squared_error(y_test, y_pred)
    y_cls_true = np.array([_risk_to_class(r) for r in y_test])
    y_cls_pred = np.array([_risk_to_class(p) for p in y_pred])
    acc = accuracy_score(y_cls_true, y_cls_pred)
    f1 = f1_score(y_cls_true, y_cls_pred, average='weighted', zero_division=0)

    return {
        'model': model,
        'scaler': scaler,
        'seq_len': seq_len
    }, {
        'mse': round(float(mse), 4),
        'accuracy': round(float(acc), 4),
        'f1_score': round(float(f1), 4),
        'architecture': 'lstm_timeseries'
    }


# =============================================================================
# 3. ETAS-INSPIRED (Epidemic Type Aftershock Sequence)
# =============================================================================

# Omori yasası parametreleri (deprem biliminde tipik değerler)
OMORI_P = 1.1  # Aftershock decay üssü (genelde 1.0–1.5)
OMORI_C = 0.01  # Zaman offset (saniye, sıfıra bölmeyi önler)


def add_etas_features(X: np.ndarray, feature_names: List[str]) -> np.ndarray:
    """
    ETAS/Omori tarzı feature'lar ekler.
    Omori yasası: N(t) = K/(t+c)^p — artçı deprem aktivite azalması
    """
    def _idx(name: str, fallback: int) -> int:
        return feature_names.index(name) if name in feature_names else fallback

    idx_count = _idx('count', 0)
    idx_mean_int = _idx('mean_interval', min(6, X.shape[1] - 1))
    idx_min_int = _idx('min_interval', min(8, X.shape[1] - 1))
    idx_max_mag = _idx('max_magnitude', 1)
    idx_mag4 = _idx('mag_above_4', 9)

    extra = []
    for i in range(len(X)):
        row = X[i]
        c = max(1, float(row[idx_count]))
        mi = max(1, float(row[idx_mean_int]))
        mn = max(1, float(row[idx_min_int]))
        max_mag = max(0.1, float(row[idx_max_mag]))
        mag4 = float(row[idx_mag4]) if idx_mag4 < len(row) else 0

        # Omori: N(t) ~ 1/(t+c)^p
        t_sec = mi  # ortalama aralık (saniye)
        omori_decay = 1.0 / ((t_sec / 3600 + OMORI_C) ** OMORI_P)

        # Aktivite yoğunluğu × decay
        omori_like = c * omori_decay

        # Son depremden geçen süre etkisi (min_interval)
        time_decay = 1.0 / (np.log1p(mn / 60) + 1)  # dakikaya çevir

        # Büyüklük ağırlıklı aktivite (M≥4 sayısı)
        mag_weighted = (c + mag4 * 2) * omori_decay

        extra.append([omori_like, time_decay, mag_weighted])
    return np.hstack([X, np.array(extra)])


def train_etas_inspired(
    X: np.ndarray, y: np.ndarray,
    feature_names: List[str], test_size: float = 0.2
) -> Tuple[Any, Dict]:
    """
    ETAS-tarzı feature'lar + XGBoost/RandomForest.
    Deprem projelerinde yaygın kullanılan aftershock decay mantığı.
    """
    X_etas = add_etas_features(X.copy(), feature_names)
    X_train, X_test, y_train, y_test = train_test_split(
        X_etas, y, test_size=test_size, random_state=42
    )
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    if HAS_XGB:
        model = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.08, random_state=42)
    else:
        model = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
    model.fit(X_train_s, y_train, verbose=False) if HAS_XGB else model.fit(X_train_s, y_train)

    y_pred = model.predict(X_test_s)
    mse = mean_squared_error(y_test, y_pred)
    y_cls_true = np.array([_risk_to_class(r) for r in y_test])
    y_cls_pred = np.array([_risk_to_class(p) for p in y_pred])
    acc = accuracy_score(y_cls_true, y_cls_pred)
    f1 = f1_score(y_cls_true, y_cls_pred, average='weighted', zero_division=0)

    return {
        'model': model,
        'scaler': scaler,
        'use_etas_features': True,
        'feature_names': feature_names + ['omori_decay', 'time_decay', 'mag_weighted_omori']
    }, {
        'mse': round(float(mse), 4),
        'accuracy': round(float(acc), 4),
        'f1_score': round(float(f1), 4),
        'architecture': 'etas_inspired'
    }


# =============================================================================
# Ana eğitim fonksiyonu
# =============================================================================

def train_all_architectures(
    X: np.ndarray, y: np.ndarray,
    feature_names: List[str],
    raw_earthquakes: Optional[List[Dict]] = None
) -> Dict[str, Dict]:
    """
    Üç mimariyi de eğitir ve metrikleri döndürür.
    raw_earthquakes: LSTM için şehir×zaman sequence (geojson içeren ham depremler)
    """
    results = {}
    # 1. Ensemble
    try:
        ens_obj, ens_metrics = train_ensemble_stacking(X, y)
        results['ensemble_stacking'] = {'metrics': ens_metrics, 'object': ens_obj}
    except Exception as e:
        results['ensemble_stacking'] = {'error': str(e)}

    # 2. LSTM (şehir × t1..t5 sequence veya fallback)
    try:
        lstm_obj, lstm_metrics = train_lstm_sequence(
            X, y, raw_earthquakes=raw_earthquakes
        )
        if lstm_obj:
            results['lstm_timeseries'] = {'metrics': lstm_metrics, 'object': lstm_obj}
        else:
            results['lstm_timeseries'] = lstm_metrics
    except Exception as e:
        results['lstm_timeseries'] = {'error': str(e)}

    # 3. ETAS-inspired
    try:
        etas_obj, etas_metrics = train_etas_inspired(X, y, feature_names)
        results['etas_inspired'] = {'metrics': etas_metrics, 'object': etas_obj}
    except Exception as e:
        results['etas_inspired'] = {'error': str(e)}

    return results


if __name__ == "__main__":
    from train_models import load_and_prepare_data, FEATURE_NAMES
    X, y_reg, _ = load_and_prepare_data()
    results = train_all_architectures(X, y_reg, FEATURE_NAMES)
    for name, r in results.items():
        print(f"{name}: {r.get('metrics', r)}")
