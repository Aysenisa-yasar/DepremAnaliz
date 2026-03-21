import os
import pickle
import sys
from datetime import datetime

import numpy as np

try:
    import torch
    from torch import nn, optim
    from torch.utils.data import DataLoader, TensorDataset
except Exception:
    torch = None
    nn = None
    optim = None
    DataLoader = None
    TensorDataset = None

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import EARTHQUAKE_HISTORY_FILE, MODEL_DIR
from forecast.features import haversine_km
from forecast.lstm_stub import lstm_sequence_score
from forecast.targets import build_binary_target


LSTM_MODEL_PATH = os.path.join(MODEL_DIR, "lstm_latest.pt")
LSTM_META_PATH = os.path.join(MODEL_DIR, "lstm_latest_meta.pkl")
_LSTM_CACHE = {
    "model": None,
    "meta": None,
    "path_mtime": None,
}


if nn is not None:
    class EarthquakeLSTM(nn.Module):
        def __init__(self, input_size: int = 6, hidden_size: int = 32, num_layers: int = 2):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=0.2 if num_layers > 1 else 0.0,
            )
            self.head = nn.Sequential(
                nn.Linear(hidden_size, 32),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(32, 1),
            )

        def forward(self, x):
            _, (hidden, _) = self.lstm(x)
            logits = self.head(hidden[-1])
            return torch.sigmoid(logits)
else:
    class EarthquakeLSTM:
        def __init__(self, *args, **kwargs):
            _require_torch()


def _require_torch():
    if torch is None or nn is None or optim is None:
        raise RuntimeError(
            "Gercek LSTM egitimi icin torch gerekli. "
            "Kurulum: python -m pip install torch"
        )


def _sorted_events(events):
    return sorted(
        [event for event in events if (event.get("timestamp") or 0) > 0],
        key=lambda event: float(event.get("timestamp") or 0),
    )


def _build_sequence(events, center_lat, center_lon, ref_ts, seq_len=32, radius_km=200.0, history_window_hours=72.0):
    relevant = []
    max_age_hours = max(history_window_hours, 1.0)
    max_radius = max(radius_km, 1.0)

    for event in events:
        ts = float(event.get("timestamp") or 0)
        if ts <= 0 or ts > ref_ts:
            continue

        age_hours = (ref_ts - ts) / 3600.0
        if age_hours > history_window_hours:
            continue

        lat = float(event.get("lat", 0) or 0)
        lon = float(event.get("lon", 0) or 0)
        distance = haversine_km(center_lat, center_lon, lat, lon)
        if distance > radius_km:
            continue

        mag = float(event.get("mag", 0) or 0)
        depth = float(event.get("depth", 10) or 10)

        relevant.append([
            mag / 8.0,
            depth / 100.0,
            min(age_hours / max_age_hours, 1.0),
            min(np.log10((10 ** (1.5 * mag)) + 1.0) / 10.0, 1.0),
            min(distance / max_radius, 1.0),
            min(max(len(relevant) / max(seq_len, 1), 0.0), 1.0),
        ])

    if not relevant:
        return np.zeros((seq_len, 6), dtype=np.float32), False

    relevant = relevant[-seq_len:]
    seq = np.zeros((seq_len, 6), dtype=np.float32)
    seq[-len(relevant):] = np.array(relevant, dtype=np.float32)
    return seq, len(relevant) >= max(8, seq_len // 4)


def create_lstm_records(
    events,
    seq_len=32,
    history_window_hours=72,
    future_hours=24,
    radius_km=200,
    sample_stride=3,
):
    sorted_events = _sorted_events(events)
    X = []
    y = []

    for index in range(100, len(sorted_events) - 100, max(1, sample_stride)):
        ref = sorted_events[index]
        ref_ts = float(ref.get("timestamp") or 0)
        center_lat = float(ref.get("lat", 0) or 0)
        center_lon = float(ref.get("lon", 0) or 0)

        seq, is_valid = _build_sequence(
            sorted_events[: index + 1],
            center_lat,
            center_lon,
            ref_ts,
            seq_len=seq_len,
            radius_km=radius_km,
            history_window_hours=history_window_hours,
        )
        if not is_valid:
            continue

        label = build_binary_target(
            sorted_events,
            center_lat,
            center_lon,
            ref_ts,
            horizon_hours=future_hours,
            dist_km=100,
            min_mag=4.0,
        )

        X.append(seq)
        y.append(int(label))

    if not X:
        return np.zeros((0, seq_len, 6), dtype=np.float32), np.zeros((0,), dtype=np.float32)

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def train_lstm(
    events=None,
    epochs=8,
    batch_size=64,
    learning_rate=1e-3,
    seq_len=32,
):
    _require_torch()

    if events is None:
        from services.data_service import load_events_from_file

        events = load_events_from_file(EARTHQUAKE_HISTORY_FILE)
    if len(events) < 500:
        raise ValueError("LSTM egitimi icin yeterli event yok")

    X, y = create_lstm_records(events, seq_len=seq_len)
    if len(X) < 100:
        raise ValueError("LSTM egitimi icin yeterli sequence olusmadi")

    split = int(len(X) * 0.8)
    if split <= 0 or split >= len(X):
        raise ValueError("LSTM train/test split olusturulamadi")

    X_train = torch.tensor(X[:split], dtype=torch.float32)
    y_train = torch.tensor(y[:split], dtype=torch.float32)
    X_test = torch.tensor(X[split:], dtype=torch.float32)
    y_test = torch.tensor(y[split:], dtype=torch.float32)

    train_loader = DataLoader(TensorDataset(X_train, y_train), batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(TensorDataset(X_test, y_test), batch_size=batch_size, shuffle=False)

    model = EarthquakeLSTM(input_size=X.shape[-1], hidden_size=32, num_layers=2)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            out = model(batch_x).squeeze(-1)
            loss = criterion(out, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())

        print(f"[lstm] epoch={epoch} loss={total_loss:.4f}")

    probs = []
    labels = []
    model.eval()
    with torch.no_grad():
        for batch_x, batch_y in test_loader:
            out = model(batch_x).squeeze(-1)
            probs.extend(out.cpu().numpy().tolist())
            labels.extend(batch_y.cpu().numpy().tolist())

    probs = np.array(probs, dtype=np.float64)
    labels = np.array(labels, dtype=np.float64)

    if len(np.unique(labels)) > 1:
        from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

        roc = float(roc_auc_score(labels, probs))
        pr = float(average_precision_score(labels, probs))
        brier = float(brier_score_loss(labels, probs))
    else:
        roc = 0.0
        pr = 0.0
        brier = 0.0

    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(model.state_dict(), LSTM_MODEL_PATH)

    meta = {
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "model_type": "lstm_sequence_v1",
        "seq_len": int(seq_len),
        "roc_auc": roc,
        "pr_auc": pr,
        "brier": brier,
        "samples_train": int(len(X_train)),
        "samples_test": int(len(X_test)),
        "sample_stride": 3,
    }

    with open(LSTM_META_PATH, "wb") as f:
        pickle.dump(meta, f)

    print("[lstm] ROC-AUC:", roc)
    print("[lstm] PR-AUC:", pr)
    print("[lstm] Brier:", brier)
    print("[lstm] Model kaydedildi:", LSTM_MODEL_PATH)
    return meta


def load_lstm():
    if torch is None or not os.path.exists(LSTM_MODEL_PATH):
        _LSTM_CACHE["model"] = None
        _LSTM_CACHE["meta"] = None
        _LSTM_CACHE["path_mtime"] = None
        return None, None

    current_mtime = os.path.getmtime(LSTM_MODEL_PATH)
    if _LSTM_CACHE["model"] is not None and _LSTM_CACHE["path_mtime"] == current_mtime:
        return _LSTM_CACHE["model"], _LSTM_CACHE["meta"]

    meta = {}
    if os.path.exists(LSTM_META_PATH):
        try:
            with open(LSTM_META_PATH, "rb") as f:
                meta = pickle.load(f)
        except Exception:
            meta = {}

    seq_len = int(meta.get("seq_len", 32))
    model = EarthquakeLSTM(input_size=6, hidden_size=32, num_layers=2)
    try:
        state_dict = torch.load(LSTM_MODEL_PATH, map_location="cpu")
        model.load_state_dict(state_dict)
        model.eval()
    except Exception:
        return None, None

    _LSTM_CACHE["model"] = model
    _LSTM_CACHE["meta"] = meta | {"seq_len": seq_len}
    _LSTM_CACHE["path_mtime"] = current_mtime
    return _LSTM_CACHE["model"], _LSTM_CACHE["meta"]


def predict_lstm_sequence(events, lat, lon):
    model, meta = load_lstm()
    if model is None or torch is None:
        return float(lstm_sequence_score(events))

    sorted_events = _sorted_events(events)
    if not sorted_events:
        return 0.0

    ref_ts = float(sorted_events[-1].get("timestamp") or 0)
    seq_len = int((meta or {}).get("seq_len", 32))
    sequence, is_valid = _build_sequence(
        sorted_events,
        float(lat),
        float(lon),
        ref_ts,
        seq_len=seq_len,
    )
    if not is_valid:
        return float(lstm_sequence_score(sorted_events))

    x = torch.tensor(sequence, dtype=torch.float32).unsqueeze(0)
    with torch.no_grad():
        prob = model(x).item()
    return float(prob)


if __name__ == "__main__":
    train_lstm()
