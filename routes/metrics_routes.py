import os
import pickle

from flask import Blueprint, jsonify

from config import FORECAST_MODEL

metrics_bp = Blueprint("metrics", __name__)


def _load_model_data():
    if not os.path.exists(FORECAST_MODEL):
        return None

    with open(FORECAST_MODEL, "rb") as f:
        return pickle.load(f)


@metrics_bp.route("/api/v2/forecast-metrics", methods=["GET"])
def forecast_metrics_v2():
    try:
        data = _load_model_data()
        if data is None:
            return jsonify({
                "status": "no_model",
                "message": "Forecast modeli bulunamadi.",
            })

        return jsonify({
            "status": "success",
            "trained_at": data.get("trained_at"),
            "model_type": data.get("model_type", "forecast_hybrid_v3_timeseriescv"),
            "feature_order": data.get("feature_order", []),
            "metrics": data.get("metrics", {}),
            "targets": data.get("targets", {}),
            "calibration": data.get("calibration", {}),
            "backtest": data.get("backtest", {}),
            "feature_importance": data.get("feature_importance", []),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@metrics_bp.route("/api/v2/feature-importance", methods=["GET"])
def feature_importance_v2():
    try:
        data = _load_model_data()
        if data is None:
            return jsonify({
                "status": "no_model",
                "message": "Forecast modeli bulunamadi.",
                "items": [],
            })

        return jsonify({
            "status": "success",
            "model_type": data.get("model_type", "forecast_hybrid_v3_timeseriescv"),
            "items": data.get("feature_importance", []),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "items": []}), 500


@metrics_bp.route("/api/v2/backtest", methods=["GET"])
def backtest_v2():
    try:
        data = _load_model_data()
        if data is None:
            return jsonify({
                "status": "no_model",
                "message": "Forecast modeli bulunamadi.",
                "backtest": {},
            })

        return jsonify({
            "status": "success",
            "model_type": data.get("model_type", "forecast_hybrid_v3_timeseriescv"),
            "backtest": data.get("backtest", {}),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "backtest": {}}), 500
