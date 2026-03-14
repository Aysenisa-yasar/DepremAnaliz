# routes/forecast_routes.py - Forecast harita + grid API (explain, ETAS, çok şehir)
from flask import Blueprint, jsonify

from services.data_service import load_events
from services.forecast_service import forecast_city
from services.anomaly_service import anomaly_score
from services.grid_forecast_service import forecast_grid

forecast_bp = Blueprint("forecast", __name__)

CITIES = {
    "İstanbul": {"lat": 41.0082, "lon": 28.9784},
    "Ankara": {"lat": 39.9334, "lon": 32.8597},
    "İzmir": {"lat": 38.4237, "lon": 27.1428},
    "Bursa": {"lat": 40.1826, "lon": 29.0665},
    "Antalya": {"lat": 36.8969, "lon": 30.7133},
    "Adana": {"lat": 36.9914, "lon": 35.3308},
    "Konya": {"lat": 37.8746, "lon": 32.4932},
    "Gaziantep": {"lat": 37.0662, "lon": 37.3833},
    "Kocaeli": {"lat": 40.8533, "lon": 29.8815},
    "Kayseri": {"lat": 38.7312, "lon": 35.4787},
    "Erzurum": {"lat": 39.9043, "lon": 41.2679},
    "Van": {"lat": 38.5012, "lon": 43.3722},
    "Malatya": {"lat": 38.3552, "lon": 38.3095},
    "Kahramanmaraş": {"lat": 37.5858, "lon": 36.9371},
    "Denizli": {"lat": 37.7765, "lon": 29.0864},
}


@forecast_bp.route("/api/v2/forecast-map", methods=["GET"])
def forecast_map_v2():
    try:
        events = load_events()
        points = []
        for name, city in CITIES.items():
            pred = forecast_city(events, city, explain=True)
            ano = anomaly_score(events, city["lat"], city["lon"])
            risk_score = pred["risk_score"]
            risk_level = "Yüksek" if risk_score >= 5.5 else "Orta" if risk_score >= 3.5 else "Düşük"
            points.append({
                "city": name,
                "lat": city["lat"],
                "lon": city["lon"],
                "risk_score": risk_score,
                "probability": pred["probability"],
                "ml_probability": pred["ml_probability"],
                "etas_probability": pred["etas_probability"],
                "risk_level": risk_level,
                "anomaly_score": round(ano, 2),
                "anomaly_detected": ano > 0.5,
                "top_features": pred.get("top_features", []),
                "model_type": pred.get("model_type", "forecast_hybrid_v2_faultaware"),
                "fault_distance": pred.get("fault_distance", 999.0),
                "fault_proximity_score": pred.get("fault_proximity_score", 0.0),
                "stress_transfer": pred.get("stress_transfer", 0.0),
                "energy_release": pred.get("energy_release", 0.0),
                "foreshock_count": pred.get("foreshock_count", 0),
                "spatial_density": pred.get("spatial_density", 0.0),
                "mag_trend": pred.get("mag_trend", 0.0),
                "depth_variance": pred.get("depth_variance", 0.0),
                "nearest_fault_segment": pred.get("nearest_fault_segment", "unknown"),
            })
        return jsonify({
            "status": "success",
            "model_type": "forecast_hybrid_v1",
            "analysis_window": "past_48h",
            "points": points,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "points": []}), 500


@forecast_bp.route("/api/v2/forecast-grid", methods=["GET"])
def forecast_grid_v2():
    try:
        events = load_events()
        points = forecast_grid(events, step=0.5)
        return jsonify({
            "status": "success",
            "model_type": "forecast_hybrid_v2_faultaware",
            "grid_step": 0.5,
            "points": points,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "points": []}), 500
