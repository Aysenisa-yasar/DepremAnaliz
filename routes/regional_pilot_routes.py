from flask import Blueprint, jsonify

from services.regional_pilot_service import get_regional_pilot_map_payload


regional_pilot_bp = Blueprint("regional_pilot", __name__)


@regional_pilot_bp.route("/api/v2/regional-pilot-map", methods=["GET"])
def regional_pilot_map_v2():
    try:
        return jsonify(get_regional_pilot_map_payload())
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc),
            "nodes": [],
        }), 500
