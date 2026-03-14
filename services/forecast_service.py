# services/forecast_service.py - Şehir bazlı forecast (predictor dict kullanır)
from forecast.predictor import predict


def forecast_city(events: list, city: dict, explain: bool = False) -> dict:
    lat = city["lat"]
    lon = city["lon"]
    pred = predict(events, lat, lon, explain=explain)
    prob = pred["probability"]
    risk = min(10.0, max(0.0, prob * 10.0))
    return {
        "probability": float(prob),
        "ml_probability": float(pred.get("ml_probability", prob)),
        "etas_probability": float(pred.get("etas_probability", 0.0)),
        "risk_score": round(risk, 2),
        "top_features": pred.get("top_features", []),
        "features": pred.get("features", {}),
        "model_type": pred.get("model_type", "forecast_hybrid_v2_faultaware"),
        "fault_distance": float(pred.get("fault_distance", 999.0)),
        "fault_proximity_score": float(pred.get("fault_proximity_score", 0.0)),
        "stress_transfer": float(pred.get("stress_transfer", 0.0)),
        "energy_release": float(pred.get("energy_release", 0.0)),
        "foreshock_count": int(pred.get("foreshock_count", 0)),
        "spatial_density": float(pred.get("spatial_density", 0.0)),
        "mag_trend": float(pred.get("mag_trend", 0.0)),
        "depth_variance": float(pred.get("depth_variance", 0.0)),
        "nearest_fault_segment": pred.get("nearest_fault_segment", "unknown"),
    }
