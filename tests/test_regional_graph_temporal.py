from forecast.regional_graph_temporal import (
    FEATURE_NAMES,
    REGIONAL_NODES,
    build_normalized_adjacency,
    build_supervised_sequences,
    build_weekly_region_panel,
    get_location_pilot_signal,
    load_regional_pilot_model,
    predict_next_week,
)


def test_regional_adjacency_shape():
    adjacency = build_normalized_adjacency()
    assert adjacency.shape == (len(REGIONAL_NODES), len(REGIONAL_NODES))
    assert len(REGIONAL_NODES) == 81


def test_weekly_region_panel_builds_tensor():
    events = [
        {"lat": 41.0, "lon": 29.0, "mag": 3.2, "timestamp": 1_700_000_000.0},
        {"lat": 38.4, "lon": 27.1, "mag": 4.1, "timestamp": 1_700_300_000.0},
        {"lat": 37.5, "lon": 37.0, "mag": 3.8, "timestamp": 1_700_900_000.0},
    ]
    panel = build_weekly_region_panel(events)
    assert panel["features"].shape[1] == len(REGIONAL_NODES)
    assert panel["features"].shape[2] == len(FEATURE_NAMES)


def test_supervised_sequences_return_expected_shapes():
    events = []
    base_timestamp = 1_700_000_000.0
    for week in range(8):
        events.append({
            "lat": 41.0,
            "lon": 29.0,
            "mag": 3.0 + (week % 3) * 0.1,
            "timestamp": base_timestamp + week * 7 * 24 * 3600,
        })

    panel = build_weekly_region_panel(events)
    X, y, target_weeks = build_supervised_sequences(panel)
    assert X.shape[0] == y.shape[0] == len(target_weeks)
    assert X.shape[1] == 4


def test_load_regional_model_returns_none_or_dict():
    model = load_regional_pilot_model()
    assert model is None or isinstance(model, dict)


def test_predict_next_week_uses_snapshot_when_live_history_short():
    if load_regional_pilot_model() is None:
        return

    payload = predict_next_week([], model_data=load_regional_pilot_model())
    assert payload["status"] in {"success", "insufficient_history"}


def test_get_location_pilot_signal_returns_expected_shape():
    if load_regional_pilot_model() is None:
        return

    signal = get_location_pilot_signal([], 39.93, 32.86, model_data=load_regional_pilot_model())
    assert "pilot_available" in signal
    assert "pilot_probability" in signal
    assert "pilot_region_name" in signal
