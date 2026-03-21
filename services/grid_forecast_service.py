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
            "lstm_probability": float(pred.get("lstm_probability", 0.0)),
            "cluster_score": float(pred.get("cluster_score", 0.0)),
            "b_value": float(pred.get("b_value", 1.0)),
            "b_risk": float(pred.get("b_risk", 0.0)),
            "gnn_probability": float(pred.get("gnn_probability", 0.0)),
            "m5_72h_probability": float(pred.get("m5_72h_probability", 0.0)),
            "max_mag_7d_prediction": float(pred.get("max_mag_7d_prediction", 0.0)),
            "risk_score": float(prob * 10.0),
            "ensemble_weights": pred.get("ensemble_weights", {}),
            "model_type": pred.get("model_type", "forecast_hybrid_v3_timeseriescv"),
            "fault_distance": float(pred.get("fault_distance", 999.0)),
            "fault_proximity_score": float(pred.get("fault_proximity_score", 0.0)),
            "stress_transfer": float(pred.get("stress_transfer", 0.0)),
            "nearest_fault_segment": pred.get("nearest_fault_segment", "unknown"),
        })
    return results
