import os
import pickle
import sys
from datetime import datetime

import numpy as np

try:
    import torch
    from torch import nn, optim
    from torch_geometric.loader import DataLoader
except Exception as exc:
    raise RuntimeError(
        "GNN egitimi icin torch ve torch-geometric gerekli. "
        "Kurulum: python -m pip install torch torch-geometric "
        "veya install_research_dependencies.ps1"
    ) from exc

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import EARTHQUAKE_HISTORY_FILE, MODEL_DIR
from forecast.gnn.dataset import EarthquakeGraphDataset
from forecast.gnn.model import EarthquakeGNN
from forecast.targets import build_binary_target
from services.data_service import load_events_from_file


GNN_MODEL_PATH = os.path.join(MODEL_DIR, "gnn_latest.pt")
GNN_META_PATH = os.path.join(MODEL_DIR, "gnn_latest_meta.pkl")


def create_gnn_records(events, history_window=48, future_hours=24):
    events = sorted(events, key=lambda event: event["timestamp"])
    records = []

    for i in range(100, len(events) - 100):
        ref = events[i]
        ref_ts = ref["timestamp"]
        center_lat = ref["lat"]
        center_lon = ref["lon"]

        history = [
            event
            for event in events
            if event["timestamp"] <= ref_ts and (ref_ts - event["timestamp"]) <= history_window * 3600
        ]

        if len(history) < 5:
            continue

        label = build_binary_target(
            events,
            center_lat,
            center_lon,
            ref_ts,
            horizon_hours=future_hours,
            dist_km=100,
            min_mag=4.0,
        )

        records.append({
            "events": history,
            "label": label,
        })

    return records


def train_gnn():
    events = load_events_from_file(EARTHQUAKE_HISTORY_FILE)
    if len(events) < 500:
        raise ValueError("GNN egitimi icin yeterli event yok")

    records = create_gnn_records(events)
    if len(records) < 50:
        raise ValueError("GNN egitimi icin yeterli graph record olusmadi")

    split = int(len(records) * 0.8)
    train_records = records[:split]
    test_records = records[split:]

    train_ds = EarthquakeGraphDataset(train_records)
    test_ds = EarthquakeGraphDataset(test_records)

    train_loader = DataLoader(train_ds, batch_size=16, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=16, shuffle=False)

    model = EarthquakeGNN(in_channels=6, hidden_channels=32)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    for epoch in range(15):
        model.train()
        total_loss = 0.0

        for batch in train_loader:
            optimizer.zero_grad()
            out = model(batch.x, batch.edge_index, batch.batch, edge_weight=batch.edge_weight).squeeze()
            loss = criterion(out, batch.y.squeeze())
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())

        print(f"[gnn] epoch={epoch} loss={total_loss:.4f}")

    model.eval()
    probs = []
    labels = []

    with torch.no_grad():
        for batch in test_loader:
            out = model(batch.x, batch.edge_index, batch.batch, edge_weight=batch.edge_weight).squeeze()
            probs.extend(out.cpu().numpy().tolist() if out.ndim > 0 else [float(out.cpu().item())])

            y = batch.y.squeeze()
            labels.extend(y.cpu().numpy().tolist() if y.ndim > 0 else [float(y.cpu().item())])

    probs = np.array(probs, dtype=np.float64)
    labels = np.array(labels, dtype=np.float64)

    if len(np.unique(labels)) > 1:
        from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

        roc = roc_auc_score(labels, probs)
        pr = average_precision_score(labels, probs)
        brier = brier_score_loss(labels, probs)
    else:
        roc = 0.0
        pr = 0.0
        brier = 0.0

    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(model.state_dict(), GNN_MODEL_PATH)

    meta = {
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "model_type": "gnn_spatiotemporal_v1",
        "roc_auc": float(roc),
        "pr_auc": float(pr),
        "brier": float(brier),
        "samples_train": len(train_records),
        "samples_test": len(test_records),
    }

    with open(GNN_META_PATH, "wb") as f:
        pickle.dump(meta, f)

    print("[gnn] ROC-AUC:", roc)
    print("[gnn] PR-AUC:", pr)
    print("[gnn] Brier:", brier)


if __name__ == "__main__":
    train_gnn()
