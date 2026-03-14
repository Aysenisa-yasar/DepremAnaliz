# tests/test_features.py
from forecast.features import extract_features


def test_feature_vector():
    events = [
        {"lat": 40.0, "lon": 29.0, "mag": 4.5, "timestamp": 1000.0},
    ]
    f = extract_features(events, 40.0, 29.0)
    assert "count" in f
    assert "max_mag" in f
    assert "mean_mag" in f
    assert "min_distance" in f
    assert "recency_energy" in f
    assert "swarm_ratio" in f
    assert "fault_distance" in f
    assert f["count"] == 1
    assert f["max_mag"] == 4.5
