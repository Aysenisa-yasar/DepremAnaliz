from forecast.regional_graph_temporal import load_regional_pilot_model, predict_next_week
from services.data_service import load_events_from_file


def get_regional_pilot_map_payload() -> dict:
    model_data = load_regional_pilot_model()
    if model_data is None:
        return {
            "status": "no_model",
            "message": "Regional graph-temporal pilot model is not trained yet.",
            "nodes": [],
        }

    events = load_events_from_file()
    return predict_next_week(events, model_data=model_data)
