import time

from forecast.regional_graph_temporal import get_pilot_forecast, load_regional_pilot_model
from services.data_service import load_events

_REGIONAL_PILOT_CACHE = {"payload": None, "timestamp": 0.0, "ttl": 300.0}


def _read_cache():
    if _REGIONAL_PILOT_CACHE["payload"] is None:
        return None
    if (time.time() - _REGIONAL_PILOT_CACHE["timestamp"]) >= _REGIONAL_PILOT_CACHE["ttl"]:
        return None
    return _REGIONAL_PILOT_CACHE["payload"]


def _write_cache(payload: dict) -> dict:
    _REGIONAL_PILOT_CACHE["payload"] = payload
    _REGIONAL_PILOT_CACHE["timestamp"] = time.time()
    return payload


def get_regional_pilot_map_payload() -> dict:
    cached_payload = _read_cache()
    if cached_payload is not None:
        return cached_payload

    model_data = load_regional_pilot_model()
    if model_data is None:
        return {
            "status": "no_model",
            "message": "Provincial graph-temporal pilot model is not trained yet.",
            "nodes": [],
        }

    events = load_events(use_api=True, use_file_fallback=True, prefer_file=True, api_timeout=5)
    return _write_cache(get_pilot_forecast(events, model_data=model_data))
