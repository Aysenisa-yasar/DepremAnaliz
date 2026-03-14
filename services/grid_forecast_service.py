# services/grid_forecast_service.py - Grid bazlı tahmin (Türkiye grid)
from forecast.grid import generate_turkey_grid
from forecast.predictor import predict


def forecast_grid(events, step=0.5):
    grid = generate_turkey_grid(step=step)
    results = []
    for p in grid:
        pred = predict(events, p["lat"], p["lon"], explain=False)
        prob = pred["probability"]
        results.append({
            "id": p["id"],
            "lat": p["lat"],
            "lon": p["lon"],
            "probability": float(prob),
            "ml_probability": float(pred.get("ml_probability", prob)),
            "etas_probability": float(pred.get("etas_probability", 0.0)),
            "risk_score": float(prob * 10.0),
            "model_type": pred.get("model_type", "forecast_hybrid_v2_faultaware"),
            "fault_distance": float(pred.get("fault_distance", 999.0)),
            "fault_proximity_score": float(pred.get("fault_proximity_score", 0.0)),
            "stress_transfer": float(pred.get("stress_transfer", 0.0)),
            "nearest_fault_segment": pred.get("nearest_fault_segment", "unknown"),
        })
    return results
