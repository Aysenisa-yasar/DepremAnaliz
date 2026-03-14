# forecast/predictor.py - Hibrit tahmin (ML + ETAS-benzeri), dict döner, SHAP opsiyonel
import os
import pickle
import numpy as np

from config import FORECAST_MODEL
from forecast.features import extract_features
from forecast.etas_like import etas_like_score
from forecast.explain import explain_prediction

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


def load_model():
    if not os.path.exists(FORECAST_MODEL):
        return None
    try:
        with open(FORECAST_MODEL, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def predict(
    events: list,
    lat: float,
    lon: float,
    time_window_hours: int = 48,
    explain: bool = False,
) -> dict:
    model_data = load_model()
    feats = extract_features(events, lat, lon, time_window_hours=time_window_hours)
    X = np.array([[feats.get(k, 0) for k in FEATURE_ORDER]], dtype=np.float64)

    if not model_data or "model" not in model_data:
        etas_prob = float(etas_like_score(feats))
        return {
            "probability": etas_prob,
            "ml_probability": 0.0,
            "etas_probability": etas_prob,
            "features": feats,
            "top_features": [],
            "model_type": "no_forecast_model",
            "fault_distance": float(feats.get("fault_distance", 999.0)),
            "fault_proximity_score": float(feats.get("fault_proximity_score", 0.0)),
            "stress_transfer": float(feats.get("stress_transfer", 0.0)),
            "energy_release": float(feats.get("energy_release", 0.0)),
            "foreshock_count": int(feats.get("foreshock_count", 0)),
            "spatial_density": float(feats.get("spatial_density", 0.0)),
            "mag_trend": float(feats.get("mag_trend", 0.0)),
            "depth_variance": float(feats.get("depth_variance", 0.0)),
            "nearest_fault_segment": feats.get("nearest_fault_segment", "unknown"),
        }

    ml_prob = float(model_data["model"].predict_proba(X)[0, 1])
    etas_prob = float(etas_like_score(feats))
    final_prob = 0.75 * ml_prob + 0.25 * etas_prob

    result = {
        "probability": float(final_prob),
        "ml_probability": float(ml_prob),
        "etas_probability": float(etas_prob),
        "features": feats,
        "top_features": [],
        "model_type": "forecast_hybrid_v2_faultaware",
        "fault_distance": float(feats.get("fault_distance", 999.0)),
        "fault_proximity_score": float(feats.get("fault_proximity_score", 0.0)),
        "stress_transfer": float(feats.get("stress_transfer", 0.0)),
        "energy_release": float(feats.get("energy_release", 0.0)),
        "foreshock_count": int(feats.get("foreshock_count", 0)),
        "spatial_density": float(feats.get("spatial_density", 0.0)),
        "mag_trend": float(feats.get("mag_trend", 0.0)),
        "depth_variance": float(feats.get("depth_variance", 0.0)),
        "nearest_fault_segment": feats.get("nearest_fault_segment", "unknown"),
    }

    if explain:
        try:
            result["top_features"] = explain_prediction(
                model_data["model"], X, FEATURE_ORDER
            )
        except Exception:
            result["top_features"] = []

    return result
