import numpy as np

from forecast.targets import build_binary_target


def _extract_probability(prediction):
    if isinstance(prediction, dict):
        return float(prediction.get("probability", prediction.get("ml_probability", 0.0)))
    return float(prediction)


def rolling_backtest(
    predict_fn,
    events,
    min_history=200,
    horizon_hours=24,
    radius_km=100,
    min_mag=4.0,
):
    sorted_events = sorted(
        [event for event in events if (event.get("timestamp") or 0) > 0],
        key=lambda event: float(event.get("timestamp") or 0),
    )

    results = []

    for index in range(min_history, len(sorted_events) - 1):
        ref = sorted_events[index]
        ref_ts = float(ref.get("timestamp") or 0)
        if ref_ts <= 0:
            continue

        past = sorted_events[: index + 1]
        prob = _extract_probability(
            predict_fn(
                past,
                float(ref.get("lat", 0) or 0),
                float(ref.get("lon", 0) or 0),
            )
        )

        label = build_binary_target(
            sorted_events,
            float(ref.get("lat", 0) or 0),
            float(ref.get("lon", 0) or 0),
            ref_ts,
            horizon_hours=horizon_hours,
            dist_km=radius_km,
            min_mag=min_mag,
        )
        results.append((prob, label))

    if not results:
        return {
            "mean_prob": 0.0,
            "hit_rate": 0.0,
            "positive_rate": 0.0,
            "samples": 0,
            "threshold": 0.5,
        }

    probs = np.array([item[0] for item in results], dtype=np.float64)
    labels = np.array([item[1] for item in results], dtype=np.int32)

    return {
        "mean_prob": float(np.mean(probs)),
        "hit_rate": float(np.mean((probs >= 0.5) == labels)),
        "positive_rate": float(np.mean(labels)),
        "samples": int(len(results)),
        "threshold": 0.5,
    }
