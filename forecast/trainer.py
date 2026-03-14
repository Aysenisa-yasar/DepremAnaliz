import os
import sys
import pickle
import numpy as np
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from datetime import datetime

# Proje kökünü path'e ekle (python forecast/trainer.py ile çalıştırıldığında config bulunsun)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import FORECAST_MODEL
from forecast.features import extract_features
from forecast.targets import build_binary_target


FEATURE_ORDER = [
    "count",
    "max_mag",
    "mean_mag",
    "mag_std",
    "min_distance",
    "mean_distance",
    "recency_energy",
    "mean_depth",
    "recent_6h_count",
    "recent_24h_count",
    "swarm_ratio",
    "fault_distance",
    "fault_proximity_score",
    "stress_transfer",
    "energy_release",
    "foreshock_count",
    "spatial_density",
    "mag_trend",
    "depth_variance",
]


def _events_sorted(events: list) -> list:
    return sorted(
        [e for e in events if (e.get("timestamp") or 0) > 0],
        key=lambda e: float(e.get("timestamp") or 0),
    )


def train_forecast(events: list, time_window_hours: int = 48) -> dict:
    sorted_events = _events_sorted(events)
    if len(sorted_events) < 200:
        raise ValueError("En az 200 event gerekli.")

    X = []
    y = []

    for i in range(100, len(sorted_events) - 100):
        ref = sorted_events[i]
        ref_ts = float(ref.get("timestamp") or 0)
        lat = float(ref.get("lat", 0))
        lon = float(ref.get("lon", 0))

        past = sorted_events[: i + 1]
        feats = extract_features(past, lat, lon, time_window_hours=time_window_hours)
        X.append([feats.get(k, 0) for k in FEATURE_ORDER])

        target = build_binary_target(
            sorted_events,
            lat,
            lon,
            ref_ts,
            horizon_hours=24,
            dist_km=100,
            min_mag=4.0,
        )
        y.append(target)

    X = np.array(X, dtype=np.float64)
    y = np.array(y, dtype=np.int32)

    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    pos = max(1, int(np.sum(y_train == 1)))
    neg = max(1, int(np.sum(y_train == 0)))
    scale_pos_weight = neg / pos

    clf = XGBClassifier(
        n_estimators=250,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=scale_pos_weight,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        eval_metric="logloss",
    )

    model = CalibratedClassifierCV(clf, method="sigmoid", cv=3)
    model.fit(X_train, y_train)

    probs = model.predict_proba(X_test)[:, 1]

    roc = roc_auc_score(y_test, probs) if len(np.unique(y_test)) > 1 else 0.0
    pr_auc = average_precision_score(y_test, probs) if len(np.unique(y_test)) > 1 else 0.0
    brier = brier_score_loss(y_test, probs) if len(np.unique(y_test)) > 1 else 0.0

    model_data = {
        "model": model,
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "model_type": "forecast_hybrid_v2_faultaware",
        "feature_order": FEATURE_ORDER,
        "metrics": {
            "roc_auc": float(roc),
            "pr_auc": float(pr_auc),
            "brier": float(brier),
            "positive_rate_train": float(np.mean(y_train)),
            "positive_rate_test": float(np.mean(y_test)),
            "samples_train": int(len(y_train)),
            "samples_test": int(len(y_test)),
        },
    }

    os.makedirs(os.path.dirname(FORECAST_MODEL), exist_ok=True)
    with open(FORECAST_MODEL, "wb") as f:
        pickle.dump(model_data, f)

    print("[forecast] ROC-AUC:", roc)
    print("[forecast] PR-AUC:", pr_auc)
    print("[forecast] Brier:", brier)
    print("[forecast] Model kaydedildi:", FORECAST_MODEL)

    return model_data


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from services.data_service import load_events_from_file
    from config import EARTHQUAKE_HISTORY_FILE

    events = load_events_from_file(EARTHQUAKE_HISTORY_FILE)
    if len(events) < 200:
        print("En az 200 event gerekli. earthquake_history.json dolu olmalı. Mevcut:", len(events))
    else:
        train_forecast(events)
