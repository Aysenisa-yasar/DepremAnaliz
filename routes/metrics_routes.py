# routes/metrics_routes.py - Forecast model metrikleri API (feature_order, metrics)
import os
import pickle
from flask import Blueprint, jsonify

from config import FORECAST_MODEL

metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.route("/api/v2/forecast-metrics", methods=["GET"])
def forecast_metrics_v2():
    try:
        if not os.path.exists(FORECAST_MODEL):
            return jsonify({
                "status": "no_model",
                "message": "Forecast modeli bulunamadı.",
            })
        with open(FORECAST_MODEL, "rb") as f:
            data = pickle.load(f)
        return jsonify({
            "status": "success",
            "trained_at": data.get("trained_at"),
            "model_type": data.get("model_type", "forecast_hybrid_v2_faultaware"),
            "feature_order": data.get("feature_order", []),
            "metrics": data.get("metrics", {}),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
