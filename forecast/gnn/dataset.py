import math

import torch
from torch_geometric.data import Data, Dataset

from forecast.faults import nearest_fault_distance_km


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _local_density(events, event_index, radius_km=50.0):
    if len(events) <= 1:
        return 0.0

    event = events[event_index]
    count = 0
    for other_index, other in enumerate(events):
        if other_index == event_index:
            continue
        dist = haversine_km(
            float(event.get("lat", 0) or 0),
            float(event.get("lon", 0) or 0),
            float(other.get("lat", 0) or 0),
            float(other.get("lon", 0) or 0),
        )
        if dist <= radius_km:
            count += 1

    return float(count / max(len(events) - 1, 1))


def build_graph_from_events(events, max_dist_km=100, max_dt_hours=48):
    if not events:
        return None

    ref_ts = max(float(event.get("timestamp") or 0) for event in events)
    x = []

    for index, event in enumerate(events):
        mag = float(event.get("mag", 0) or 0)
        lat = float(event.get("lat", 0) or 0)
        lon = float(event.get("lon", 0) or 0)
        age_hours = max((ref_ts - float(event.get("timestamp") or 0)) / 3600.0, 0.0)
        energy = math.log10((10 ** (1.5 * mag)) + 1.0)
        local_density = _local_density(events, index)
        fault_distance = float(nearest_fault_distance_km(lat, lon))

        x.append([
            mag,
            float(event.get("depth", 10) or 10),
            age_hours,
            energy,
            local_density,
            fault_distance,
        ])

    edge_index = [[], []]
    edge_weight = []

    for i in range(len(events)):
        for j in range(i + 1, len(events)):
            dt_hours = abs(float(events[j]["timestamp"]) - float(events[i]["timestamp"])) / 3600.0
            if dt_hours > max_dt_hours:
                continue

            dist = haversine_km(
                float(events[i]["lat"]),
                float(events[i]["lon"]),
                float(events[j]["lat"]),
                float(events[j]["lon"]),
            )

            if dist <= max_dist_km:
                weight = 1.0 / (1.0 + dist + dt_hours)
                edge_index[0].extend([i, j])
                edge_index[1].extend([j, i])
                edge_weight.extend([weight, weight])

    if len(edge_index[0]) == 0:
        edge_index = torch.empty((2, 0), dtype=torch.long)
        edge_weight = torch.empty((0,), dtype=torch.float32)
    else:
        edge_index = torch.tensor(edge_index, dtype=torch.long)
        edge_weight = torch.tensor(edge_weight, dtype=torch.float32)

    x = torch.tensor(x, dtype=torch.float32)

    return x, edge_index, edge_weight


class EarthquakeGraphDataset(Dataset):
    def __init__(self, records):
        super().__init__()
        self.records = records

    def len(self):
        return len(self.records)

    def get(self, idx):
        record = self.records[idx]
        events = record["events"]
        label = record["label"]

        graph = build_graph_from_events(events)
        if graph is None:
            x = torch.zeros((1, 6), dtype=torch.float32)
            edge_index = torch.empty((2, 0), dtype=torch.long)
            edge_weight = torch.empty((0,), dtype=torch.float32)
        else:
            x, edge_index, edge_weight = graph

        y = torch.tensor([float(label)], dtype=torch.float32)
        return Data(x=x, edge_index=edge_index, edge_weight=edge_weight, y=y)
