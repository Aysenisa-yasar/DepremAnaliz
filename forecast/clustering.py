import numpy as np
from sklearn.cluster import DBSCAN


def detect_clusters(events, eps_km=50, min_samples=5):
    valid_events = []
    for event in events or []:
        if event.get("lat") is None or event.get("lon") is None:
            continue
        valid_events.append(event)

    if len(valid_events) < min_samples:
        return []

    coords = np.array(
        [[float(event["lat"]), float(event["lon"])] for event in valid_events],
        dtype=np.float64,
    )

    kms_per_radian = 6371.0088
    epsilon = eps_km / kms_per_radian

    labels = DBSCAN(
        eps=epsilon,
        min_samples=min_samples,
        metric="haversine",
    ).fit_predict(np.radians(coords))

    clusters = {}
    for index, label in enumerate(labels):
        if label == -1:
            continue
        clusters.setdefault(label, []).append(valid_events[index])

    return list(clusters.values())
