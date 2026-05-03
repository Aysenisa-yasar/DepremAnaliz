import os
import pickle
from datetime import datetime

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

from config import EARTHQUAKE_HISTORY_FILE, MODEL_DIR
from forecast.features import haversine_km
from services.data_service import load_events_from_file


MODEL_TYPE = "provincial_graph_temporal_pilot_v2"
MODEL_PATH = os.path.join(MODEL_DIR, "regional_graph_temporal_latest.pkl")
FEATURE_NAMES = ["weekly_count", "mean_magnitude", "max_magnitude"]
WINDOW_SIZE = 4
NEIGHBOR_COUNT = 5
MIN_MAGNITUDE = 2.5
WEEK_SECONDS = 7 * 24 * 3600
_REGIONAL_MODEL_CACHE = {"model_data": None, "path_mtime": None}
_PILOT_FORECAST_CACHE = {"payload": None, "signature": None}

REGIONAL_NODES = [
    {"name": "Adana", "lat": 36.9914, "lon": 35.3308},
    {"name": "Adıyaman", "lat": 37.7639, "lon": 38.2789},
    {"name": "Afyonkarahisar", "lat": 38.7638, "lon": 30.5403},
    {"name": "Ağrı", "lat": 39.7167, "lon": 43.05},
    {"name": "Amasya", "lat": 40.65, "lon": 35.8333},
    {"name": "Ankara", "lat": 39.9334, "lon": 32.8597},
    {"name": "Antalya", "lat": 36.8969, "lon": 30.7133},
    {"name": "Artvin", "lat": 41.1833, "lon": 41.8167},
    {"name": "Aydın", "lat": 37.8444, "lon": 27.8458},
    {"name": "Balıkesir", "lat": 39.6484, "lon": 27.8826},
    {"name": "Bilecik", "lat": 40.1419, "lon": 29.9792},
    {"name": "Bingöl", "lat": 38.8847, "lon": 40.4981},
    {"name": "Bitlis", "lat": 38.4, "lon": 42.1},
    {"name": "Bolu", "lat": 40.7333, "lon": 31.6},
    {"name": "Burdur", "lat": 37.7167, "lon": 30.2833},
    {"name": "Bursa", "lat": 40.1826, "lon": 29.0665},
    {"name": "Çanakkale", "lat": 40.1553, "lon": 26.4142},
    {"name": "Çankırı", "lat": 40.6013, "lon": 33.6134},
    {"name": "Çorum", "lat": 40.5506, "lon": 34.9556},
    {"name": "Denizli", "lat": 37.7765, "lon": 29.0864},
    {"name": "Diyarbakır", "lat": 37.9144, "lon": 40.2306},
    {"name": "Edirne", "lat": 41.6772, "lon": 26.5556},
    {"name": "Elazığ", "lat": 38.6748, "lon": 39.2225},
    {"name": "Erzincan", "lat": 39.75, "lon": 39.5},
    {"name": "Erzurum", "lat": 39.9043, "lon": 41.2679},
    {"name": "Eskişehir", "lat": 39.7767, "lon": 30.5206},
    {"name": "Gaziantep", "lat": 37.0662, "lon": 37.3833},
    {"name": "Giresun", "lat": 40.9128, "lon": 38.3895},
    {"name": "Gümüşhane", "lat": 40.4603, "lon": 39.5081},
    {"name": "Hakkari", "lat": 37.5744, "lon": 43.7408},
    {"name": "Hatay", "lat": 36.4018, "lon": 36.3498},
    {"name": "Isparta", "lat": 37.7667, "lon": 30.55},
    {"name": "Mersin", "lat": 36.8, "lon": 34.6333},
    {"name": "İstanbul", "lat": 41.0082, "lon": 28.9784},
    {"name": "İzmir", "lat": 38.4237, "lon": 27.1428},
    {"name": "Kars", "lat": 40.6, "lon": 43.0833},
    {"name": "Kastamonu", "lat": 41.3667, "lon": 33.7667},
    {"name": "Kayseri", "lat": 38.7312, "lon": 35.4787},
    {"name": "Kırklareli", "lat": 41.7333, "lon": 27.2167},
    {"name": "Kırşehir", "lat": 39.15, "lon": 34.1667},
    {"name": "Kocaeli", "lat": 40.8533, "lon": 29.8815},
    {"name": "Konya", "lat": 37.8746, "lon": 32.4932},
    {"name": "Kütahya", "lat": 39.4167, "lon": 29.9833},
    {"name": "Malatya", "lat": 38.3552, "lon": 38.3095},
    {"name": "Manisa", "lat": 38.6191, "lon": 27.4289},
    {"name": "Kahramanmaraş", "lat": 37.5858, "lon": 36.9371},
    {"name": "Mardin", "lat": 37.3131, "lon": 40.7356},
    {"name": "Muğla", "lat": 37.2153, "lon": 28.3636},
    {"name": "Muş", "lat": 38.7333, "lon": 41.4833},
    {"name": "Nevşehir", "lat": 38.6244, "lon": 34.7239},
    {"name": "Niğde", "lat": 37.9667, "lon": 34.6833},
    {"name": "Ordu", "lat": 40.9839, "lon": 37.8764},
    {"name": "Rize", "lat": 41.0201, "lon": 40.5234},
    {"name": "Sakarya", "lat": 40.7569, "lon": 30.3781},
    {"name": "Samsun", "lat": 41.2867, "lon": 36.33},
    {"name": "Siirt", "lat": 37.9333, "lon": 41.95},
    {"name": "Sinop", "lat": 42.0167, "lon": 35.15},
    {"name": "Sivas", "lat": 39.7477, "lon": 37.0179},
    {"name": "Tekirdağ", "lat": 40.9833, "lon": 27.5167},
    {"name": "Tokat", "lat": 40.3167, "lon": 36.55},
    {"name": "Trabzon", "lat": 41.0015, "lon": 39.7178},
    {"name": "Tunceli", "lat": 39.1083, "lon": 39.5333},
    {"name": "Şanlıurfa", "lat": 37.1674, "lon": 38.7955},
    {"name": "Uşak", "lat": 38.6833, "lon": 29.4},
    {"name": "Van", "lat": 38.4891, "lon": 43.4089},
    {"name": "Yozgat", "lat": 39.82, "lon": 34.8044},
    {"name": "Zonguldak", "lat": 41.4564, "lon": 31.7987},
    {"name": "Aksaray", "lat": 38.3686, "lon": 34.0364},
    {"name": "Bayburt", "lat": 40.2553, "lon": 40.2247},
    {"name": "Karaman", "lat": 37.1811, "lon": 33.215},
    {"name": "Kırıkkale", "lat": 39.8333, "lon": 33.5},
    {"name": "Batman", "lat": 37.8812, "lon": 41.1351},
    {"name": "Şırnak", "lat": 37.5167, "lon": 42.45},
    {"name": "Bartın", "lat": 41.6333, "lon": 32.3333},
    {"name": "Ardahan", "lat": 41.1167, "lon": 42.7},
    {"name": "Iğdır", "lat": 39.9167, "lon": 44.0333},
    {"name": "Yalova", "lat": 40.65, "lon": 29.2667},
    {"name": "Karabük", "lat": 41.2, "lon": 32.6333},
    {"name": "Kilis", "lat": 36.7167, "lon": 37.1167},
    {"name": "Osmaniye", "lat": 37.0742, "lon": 36.2478},
    {"name": "Düzce", "lat": 40.8439, "lon": 31.1565},
]


def _utc_iso(timestamp):
    return datetime.utcfromtimestamp(float(timestamp)).strftime("%Y-%m-%d")


def _coerce_timestamp(value):
    timestamp = float(value or 0)
    if timestamp > 1e11:
        timestamp = timestamp / 1000.0
    return timestamp


def build_normalized_adjacency(nodes=None, neighbor_count=NEIGHBOR_COUNT):
    nodes = nodes or REGIONAL_NODES
    node_count = len(nodes)
    distances = np.zeros((node_count, node_count), dtype=np.float64)

    for i, source in enumerate(nodes):
        for j, target in enumerate(nodes):
            if i == j:
                continue
            distances[i, j] = haversine_km(
                float(source["lat"]),
                float(source["lon"]),
                float(target["lat"]),
                float(target["lon"]),
            )

    adjacency = np.zeros((node_count, node_count), dtype=np.float64)
    for i in range(node_count):
        neighbor_idx = np.argsort(distances[i])[1: neighbor_count + 1]
        adjacency[i, neighbor_idx] = 1.0

    adjacency = np.maximum(adjacency, adjacency.T)
    adjacency += np.eye(node_count, dtype=np.float64)

    degrees = adjacency.sum(axis=1)
    inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(degrees, 1e-8)))
    return inv_sqrt @ adjacency @ inv_sqrt


def _nearest_region_index(event, nodes):
    lat = float(event.get("lat", 0) or 0)
    lon = float(event.get("lon", 0) or 0)
    best_index = 0
    best_distance = float("inf")

    for index, node in enumerate(nodes):
        distance = haversine_km(lat, lon, float(node["lat"]), float(node["lon"]))
        if distance < best_distance:
            best_index = index
            best_distance = distance

    return best_index


def build_weekly_region_panel(events, nodes=None, min_magnitude=MIN_MAGNITUDE):
    nodes = nodes or REGIONAL_NODES
    cleaned = []
    for event in events or []:
        timestamp = _coerce_timestamp(event.get("timestamp", 0) or 0)
        magnitude = float(event.get("mag", 0) or 0)
        lat = event.get("lat")
        lon = event.get("lon")
        if timestamp <= 0 or lat is None or lon is None:
            continue
        if magnitude < min_magnitude:
            continue
        cleaned.append({
            "timestamp": timestamp,
            "mag": magnitude,
            "lat": float(lat),
            "lon": float(lon),
        })

    cleaned.sort(key=lambda item: item["timestamp"])
    node_count = len(nodes)
    feature_count = len(FEATURE_NAMES)

    if not cleaned:
        return {
            "features": np.zeros((0, node_count, feature_count), dtype=np.float64),
            "week_starts": [],
            "event_count": 0,
            "region_nodes": nodes,
        }

    grouped = {}
    min_week = int(cleaned[0]["timestamp"] // WEEK_SECONDS)
    max_week = int(cleaned[-1]["timestamp"] // WEEK_SECONDS)

    for event in cleaned:
        week_index = int(event["timestamp"] // WEEK_SECONDS)
        region_index = _nearest_region_index(event, nodes)
        grouped.setdefault((week_index, region_index), []).append(event["mag"])

    week_starts = []
    features = np.zeros((max_week - min_week + 1, node_count, feature_count), dtype=np.float64)

    for offset, week_index in enumerate(range(min_week, max_week + 1)):
        week_starts.append(float(week_index * WEEK_SECONDS))
        for region_index in range(node_count):
            magnitudes = grouped.get((week_index, region_index), [])
            if not magnitudes:
                continue
            features[offset, region_index, 0] = float(len(magnitudes))
            features[offset, region_index, 1] = float(np.mean(magnitudes))
            features[offset, region_index, 2] = float(np.max(magnitudes))

    return {
        "features": features,
        "week_starts": week_starts,
        "event_count": len(cleaned),
        "region_nodes": nodes,
    }


def build_supervised_sequences(panel, window_size=WINDOW_SIZE):
    features = np.asarray(panel["features"], dtype=np.float64)
    week_starts = list(panel.get("week_starts", []))
    node_count = len(panel.get("region_nodes", REGIONAL_NODES))
    if len(features) <= window_size:
        return (
            np.zeros((0, window_size, node_count, len(FEATURE_NAMES)), dtype=np.float64),
            np.zeros((0, node_count), dtype=np.float64),
            [],
        )

    X = []
    y = []
    target_weeks = []

    for start_index in range(0, len(features) - window_size):
        end_index = start_index + window_size
        X.append(features[start_index:end_index])
        y.append(features[end_index, :, 0])
        target_weeks.append(float(week_starts[end_index]))

    return (
        np.asarray(X, dtype=np.float64),
        np.asarray(y, dtype=np.float64),
        target_weeks,
    )


class NumpyGraphTemporalRegressor:
    def __init__(
        self,
        hidden_dim=12,
        learning_rate=0.01,
        epochs=900,
        reg_lambda=1e-4,
        patience=80,
        random_state=42,
    ):
        self.hidden_dim = int(hidden_dim)
        self.learning_rate = float(learning_rate)
        self.epochs = int(epochs)
        self.reg_lambda = float(reg_lambda)
        self.patience = int(patience)
        self.random_state = int(random_state)
        self.fit_summary = {}

    def _init_params(self, node_count, input_dim, output_dim, window_size):
        rng = np.random.default_rng(self.random_state)
        flat_dim = window_size * self.hidden_dim
        self.Wg = rng.normal(0.0, 0.16, size=(input_dim, self.hidden_dim))
        self.bg = np.zeros((self.hidden_dim,), dtype=np.float64)
        self.Wo = rng.normal(0.0, 0.08, size=(flat_dim,))
        self.bo = np.zeros((output_dim,), dtype=np.float64)

    def _scaled_inputs(self, X):
        return (X - self.x_mean) / self.x_std

    def _scaled_targets(self, y):
        return (y - self.y_mean) / self.y_std

    def _forward_scaled(self, X_scaled, adjacency):
        aggregated = np.einsum("ij,btjf->btif", adjacency, X_scaled)
        z = np.einsum("btif,fh->btih", aggregated, self.Wg) + self.bg.reshape(1, 1, 1, -1)
        h = np.maximum(z, 0.0)
        if np.asarray(self.Wo).ndim == 2:
            flat = h.reshape(h.shape[0], -1)
            y_scaled = flat @ self.Wo + self.bo
            return y_scaled, {"aggregated": aggregated, "z": z, "h": h, "flat": flat, "legacy": True}
        node_flat = np.transpose(h, (0, 2, 1, 3)).reshape(h.shape[0], h.shape[2], -1)
        y_scaled = np.einsum("bnf,f->bn", node_flat, self.Wo) + self.bo.reshape(1, -1)
        return y_scaled, {"aggregated": aggregated, "z": z, "h": h, "node_flat": node_flat, "legacy": False}

    def fit(self, X_train, y_train, adjacency, X_val=None, y_val=None):
        X_train = np.asarray(X_train, dtype=np.float64)
        y_train = np.asarray(y_train, dtype=np.float64)
        adjacency = np.asarray(adjacency, dtype=np.float64)

        if X_train.ndim != 4 or y_train.ndim != 2:
            raise ValueError("Unexpected training shapes for graph-temporal model.")

        sample_count, window_size, node_count, input_dim = X_train.shape
        output_dim = y_train.shape[1]

        self.x_mean = X_train.mean(axis=(0, 1, 2), keepdims=True)
        self.x_std = X_train.std(axis=(0, 1, 2), keepdims=True)
        self.x_std[self.x_std < 1e-6] = 1.0
        self.y_mean = y_train.mean(axis=0, keepdims=True)
        self.y_std = y_train.std(axis=0, keepdims=True)
        self.y_std[self.y_std < 1e-6] = 1.0

        X_train_scaled = self._scaled_inputs(X_train)
        y_train_scaled = self._scaled_targets(y_train)
        X_val_scaled = self._scaled_inputs(X_val) if X_val is not None and len(X_val) else None
        y_val_scaled = self._scaled_targets(y_val) if y_val is not None and len(y_val) else None

        self._init_params(node_count=node_count, input_dim=input_dim, output_dim=output_dim, window_size=window_size)
        best_state = None
        best_loss = float("inf")
        epochs_without_improvement = 0

        params = {"Wg": self.Wg, "bg": self.bg, "Wo": self.Wo, "bo": self.bo}
        first = {name: np.zeros_like(value) for name, value in params.items()}
        second = {name: np.zeros_like(value) for name, value in params.items()}
        beta1 = 0.9
        beta2 = 0.999
        eps = 1e-8

        for epoch in range(1, self.epochs + 1):
            pred_scaled, cache = self._forward_scaled(X_train_scaled, adjacency)
            error = pred_scaled - y_train_scaled
            d_y = (2.0 / error.size) * error

            dWo = np.einsum("bnf,bn->f", cache["node_flat"], d_y) + (2.0 * self.reg_lambda * self.Wo)
            dbo = d_y.sum(axis=0)
            d_node_flat = d_y[:, :, None] * self.Wo.reshape(1, 1, -1)
            d_h = np.transpose(
                d_node_flat.reshape(cache["h"].shape[0], cache["h"].shape[2], cache["h"].shape[1], cache["h"].shape[3]),
                (0, 2, 1, 3),
            )
            d_z = d_h * (cache["z"] > 0.0)
            dWg = np.einsum("btif,btih->fh", cache["aggregated"], d_z) + (2.0 * self.reg_lambda * self.Wg)
            dbg = d_z.sum(axis=(0, 1, 2))

            grads = {"Wg": dWg, "bg": dbg, "Wo": dWo, "bo": dbo}
            for name, grad in grads.items():
                first[name] = beta1 * first[name] + (1.0 - beta1) * grad
                second[name] = beta2 * second[name] + (1.0 - beta2) * (grad * grad)
                first_hat = first[name] / (1.0 - (beta1 ** epoch))
                second_hat = second[name] / (1.0 - (beta2 ** epoch))
                params[name] -= self.learning_rate * first_hat / (np.sqrt(second_hat) + eps)

            reference_loss = float(np.mean(error * error))
            if X_val_scaled is not None and y_val_scaled is not None:
                val_pred_scaled, _ = self._forward_scaled(X_val_scaled, adjacency)
                val_error = val_pred_scaled - y_val_scaled
                reference_loss = float(np.mean(val_error * val_error))

            if reference_loss + 1e-8 < best_loss:
                best_loss = reference_loss
                best_state = {name: value.copy() for name, value in params.items()}
                epochs_without_improvement = 0
            else:
                epochs_without_improvement += 1
                if epochs_without_improvement >= self.patience:
                    break

        if best_state is not None:
            self.Wg = best_state["Wg"]
            self.bg = best_state["bg"]
            self.Wo = best_state["Wo"]
            self.bo = best_state["bo"]

        self.fit_summary = {
            "best_validation_loss": float(best_loss),
            "epochs_ran": int(epoch),
            "sample_count": int(sample_count),
        }
        return self

    def predict(self, X, adjacency):
        X = np.asarray(X, dtype=np.float64)
        adjacency = np.asarray(adjacency, dtype=np.float64)
        pred_scaled, _ = self._forward_scaled(self._scaled_inputs(X), adjacency)
        return pred_scaled * self.y_std + self.y_mean

    def to_dict(self):
        return {
            "hidden_dim": self.hidden_dim,
            "learning_rate": self.learning_rate,
            "epochs": self.epochs,
            "reg_lambda": self.reg_lambda,
            "patience": self.patience,
            "random_state": self.random_state,
            "fit_summary": self.fit_summary,
            "x_mean": self.x_mean,
            "x_std": self.x_std,
            "y_mean": self.y_mean,
            "y_std": self.y_std,
            "Wg": self.Wg,
            "bg": self.bg,
            "Wo": self.Wo,
            "bo": self.bo,
        }

    @classmethod
    def from_dict(cls, payload):
        model = cls(
            hidden_dim=payload["hidden_dim"],
            learning_rate=payload["learning_rate"],
            epochs=payload["epochs"],
            reg_lambda=payload["reg_lambda"],
            patience=payload["patience"],
            random_state=payload["random_state"],
        )
        model.fit_summary = dict(payload.get("fit_summary", {}))
        model.x_mean = np.asarray(payload["x_mean"], dtype=np.float64)
        model.x_std = np.asarray(payload["x_std"], dtype=np.float64)
        model.y_mean = np.asarray(payload["y_mean"], dtype=np.float64)
        model.y_std = np.asarray(payload["y_std"], dtype=np.float64)
        model.Wg = np.asarray(payload["Wg"], dtype=np.float64)
        model.bg = np.asarray(payload["bg"], dtype=np.float64)
        model.Wo = np.asarray(payload["Wo"], dtype=np.float64)
        model.bo = np.asarray(payload["bo"], dtype=np.float64)
        return model


def _slice_splits(sample_count):
    train_end = max(8, int(sample_count * 0.70))
    val_end = max(train_end + 1, int(sample_count * 0.85))
    train_end = min(train_end, sample_count - 2)
    val_end = min(val_end, sample_count - 1)
    return train_end, val_end


def _clamp_predictions(predictions):
    clipped = np.maximum(np.asarray(predictions, dtype=np.float64), 0.0)
    return clipped


def _rmse(y_true, y_pred):
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def _build_metric_block(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    totals_true = y_true.sum(axis=1)
    totals_pred = y_pred.sum(axis=1)
    return {
        "node_mae": float(mean_absolute_error(y_true.reshape(-1), y_pred.reshape(-1))),
        "node_rmse": _rmse(y_true.reshape(-1), y_pred.reshape(-1)),
        "total_mae": float(mean_absolute_error(totals_true, totals_pred)),
        "total_rmse": _rmse(totals_true, totals_pred),
    }


def _graph_feature_stack(X, adjacency):
    return np.einsum("ij,btjf->btif", adjacency, X).reshape(len(X), -1)


def _snapshot_window(panel, window_size):
    features = np.asarray(panel.get("features", []), dtype=np.float64)
    week_starts = list(panel.get("week_starts", []))
    if len(features) < window_size:
        return None
    return {
        "features": features[-window_size:],
        "week_starts": week_starts[-window_size:],
    }


def train_regional_pilot(
    events,
    window_size=WINDOW_SIZE,
    min_magnitude=MIN_MAGNITUDE,
    neighbor_count=NEIGHBOR_COUNT,
):
    panel = build_weekly_region_panel(events, min_magnitude=min_magnitude)
    X, y, target_weeks = build_supervised_sequences(panel, window_size=window_size)
    if len(X) < 16:
        raise ValueError("Regional pilot model requires at least 16 weekly samples.")

    train_end, val_end = _slice_splits(len(X))
    adjacency = build_normalized_adjacency(panel["region_nodes"], neighbor_count=neighbor_count)

    X_train, y_train = X[:train_end], y[:train_end]
    X_val, y_val = X[train_end:val_end], y[train_end:val_end]
    X_test, y_test = X[val_end:], y[val_end:]

    model = NumpyGraphTemporalRegressor()
    model.fit(X_train, y_train, adjacency, X_val=X_val, y_val=y_val)
    graph_predictions = _clamp_predictions(model.predict(X_test, adjacency))

    naive_predictions = _clamp_predictions(X_test[:, -1, :, 0])
    linear_baseline = Ridge(alpha=1.0)
    linear_baseline.fit(_graph_feature_stack(X_train, adjacency), y_train)
    linear_predictions = _clamp_predictions(
        linear_baseline.predict(_graph_feature_stack(X_test, adjacency))
    )

    graph_metrics = _build_metric_block(y_test, graph_predictions)
    naive_metrics = _build_metric_block(y_test, naive_predictions)
    linear_metrics = _build_metric_block(y_test, linear_predictions)

    model_data = {
        "model_type": MODEL_TYPE,
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "window_size_weeks": int(window_size),
        "min_magnitude": float(min_magnitude),
        "neighbor_count": int(neighbor_count),
        "feature_names": FEATURE_NAMES,
        "region_nodes": panel["region_nodes"],
        "adjacency": adjacency,
        "target_weeks": target_weeks[-len(y_test):],
        "data_summary": {
            "event_count": int(panel["event_count"]),
            "week_count": int(len(panel["week_starts"])),
            "sample_count": int(len(X)),
            "train_samples": int(len(X_train)),
            "validation_samples": int(len(X_val)),
            "test_samples": int(len(X_test)),
            "catalog_start": _utc_iso(panel["week_starts"][0]),
            "catalog_end": _utc_iso(panel["week_starts"][-1] + WEEK_SECONDS),
        },
        "metrics": {
            "graph_temporal": graph_metrics,
            "naive_last_week": naive_metrics,
            "linear_graph_baseline": linear_metrics,
        },
        "recent_window_snapshot": _snapshot_window(panel, window_size),
        "model": model.to_dict(),
    }

    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(MODEL_PATH, "wb") as handle:
        pickle.dump(model_data, handle)

    return model_data


def load_regional_pilot_model(path=MODEL_PATH):
    if not os.path.exists(path):
        _REGIONAL_MODEL_CACHE["model_data"] = None
        _REGIONAL_MODEL_CACHE["path_mtime"] = None
        return None

    current_mtime = os.path.getmtime(path)
    if _REGIONAL_MODEL_CACHE["model_data"] is not None and _REGIONAL_MODEL_CACHE["path_mtime"] == current_mtime:
        return _REGIONAL_MODEL_CACHE["model_data"]

    try:
        with open(path, "rb") as handle:
            payload = pickle.load(handle)
    except Exception:
        return None

    if not isinstance(payload, dict) or "model" not in payload:
        return None

    payload = dict(payload)
    payload["model"] = NumpyGraphTemporalRegressor.from_dict(payload["model"])
    payload["adjacency"] = np.asarray(payload.get("adjacency"), dtype=np.float64)
    _REGIONAL_MODEL_CACHE["model_data"] = payload
    _REGIONAL_MODEL_CACHE["path_mtime"] = current_mtime
    return payload


def _event_signature(events):
    timestamps = []
    for event in events or []:
        timestamp = _coerce_timestamp(event.get("timestamp", 0) or 0)
        if timestamp > 0:
            timestamps.append(timestamp)
    if not timestamps:
        return (0, 0, 0)
    return (len(timestamps), int(min(timestamps)), int(max(timestamps)))


def get_pilot_forecast(events, model_data=None):
    model_data = model_data or load_regional_pilot_model()
    if model_data is None:
        return {
            "status": "no_model",
            "message": "Provincial graph-temporal pilot model is not trained yet.",
            "nodes": [],
        }

    signature = (
        model_data.get("trained_at"),
        model_data.get("model_type"),
        _event_signature(events),
    )
    if _PILOT_FORECAST_CACHE["payload"] is not None and _PILOT_FORECAST_CACHE["signature"] == signature:
        return _PILOT_FORECAST_CACHE["payload"]

    payload = predict_next_week(events, model_data=model_data)
    if payload.get("status") == "success":
        _PILOT_FORECAST_CACHE["payload"] = payload
        _PILOT_FORECAST_CACHE["signature"] = signature
    return payload


def get_location_pilot_signal(events, lat, lon, model_data=None, max_distance_km=120.0):
    payload = get_pilot_forecast(events, model_data=model_data)
    if payload.get("status") != "success":
        return {
            "pilot_available": False,
            "pilot_probability": 0.0,
            "pilot_region_name": None,
            "pilot_region_distance_km": None,
            "pilot_weekly_count_prediction": 0.0,
            "pilot_last_week_count": 0.0,
            "pilot_rolling_mean": 0.0,
            "pilot_data_source": payload.get("data_source"),
        }

    best_node = None
    best_distance = float("inf")
    for node in payload.get("nodes", []):
        distance = haversine_km(float(lat), float(lon), float(node["lat"]), float(node["lon"]))
        if distance < best_distance:
            best_distance = distance
            best_node = node

    if best_node is None:
        return {
            "pilot_available": False,
            "pilot_probability": 0.0,
            "pilot_region_name": None,
            "pilot_region_distance_km": None,
            "pilot_weekly_count_prediction": 0.0,
            "pilot_last_week_count": 0.0,
            "pilot_rolling_mean": 0.0,
            "pilot_data_source": payload.get("data_source"),
        }

    rolling_mean = float(best_node.get("rolling_4w_mean", 0.0) or 0.0)
    last_week_count = float(best_node.get("last_week_count", 0.0) or 0.0)
    predicted_count = float(best_node.get("predicted_count", 0.0) or 0.0)
    normalized_intensity = float(best_node.get("normalized_intensity", 0.0) or 0.0)
    delta_ratio = max(predicted_count - last_week_count, 0.0) / max(last_week_count + 1.0, 1.0)
    trend_ratio = predicted_count / max(rolling_mean + 1.0, 1.0)
    proximity_score = max(0.0, 1.0 - (best_distance / max(max_distance_km, 1.0)))
    pilot_probability = min(
        max(
            0.50 * normalized_intensity
            + 0.25 * min(trend_ratio / 2.0, 1.0)
            + 0.15 * min(delta_ratio, 1.0)
            + 0.10 * proximity_score,
            0.0,
        ),
        1.0,
    )

    return {
        "pilot_available": True,
        "pilot_probability": float(pilot_probability),
        "pilot_region_name": best_node.get("name"),
        "pilot_region_distance_km": float(best_distance),
        "pilot_weekly_count_prediction": predicted_count,
        "pilot_last_week_count": last_week_count,
        "pilot_rolling_mean": rolling_mean,
        "pilot_data_source": payload.get("data_source"),
    }


def predict_next_week(events, model_data=None):
    model_data = model_data or load_regional_pilot_model()
    if model_data is None:
        return {
            "status": "no_model",
            "message": "Provincial graph-temporal pilot model is not trained yet.",
            "nodes": [],
        }

    panel = build_weekly_region_panel(
        events,
        nodes=model_data.get("region_nodes", REGIONAL_NODES),
        min_magnitude=model_data.get("min_magnitude", MIN_MAGNITUDE),
    )
    window_size = int(model_data.get("window_size_weeks", WINDOW_SIZE))
    features = np.asarray(panel["features"], dtype=np.float64)
    data_source = "live_history"
    if len(features) >= window_size:
        last_window = features[-window_size:][None, ...]
        predicted_week_start = float(panel["week_starts"][-1] + WEEK_SECONDS)
        recent_counts = features[-1, :, 0]
        rolling_mean = features[-window_size:, :, 0].mean(axis=0)
        event_count = int(panel.get("event_count", 0))
        week_count = int(len(panel.get("week_starts", [])))
        catalog_start = _utc_iso(panel["week_starts"][0]) if panel.get("week_starts") else None
        catalog_end = _utc_iso(panel["week_starts"][-1] + WEEK_SECONDS) if panel.get("week_starts") else None
    else:
        snapshot = model_data.get("recent_window_snapshot") or {}
        snapshot_features = np.asarray(snapshot.get("features", []), dtype=np.float64)
        snapshot_weeks = list(snapshot.get("week_starts", []))
        if len(snapshot_features) < window_size:
            return {
                "status": "insufficient_history",
                "message": "Not enough weekly history for the provincial pilot forecast.",
                "nodes": [],
            }
        last_window = snapshot_features[-window_size:][None, ...]
        predicted_week_start = float(snapshot_weeks[-1] + WEEK_SECONDS)
        recent_counts = snapshot_features[-1, :, 0]
        rolling_mean = snapshot_features[-window_size:, :, 0].mean(axis=0)
        data_source = "trained_snapshot"
        summary_meta = model_data.get("data_summary", {})
        event_count = int(summary_meta.get("event_count", 0))
        week_count = int(summary_meta.get("week_count", 0))
        catalog_start = summary_meta.get("catalog_start")
        catalog_end = summary_meta.get("catalog_end")

    raw_prediction = model_data["model"].predict(last_window, model_data["adjacency"])[0]
    prediction = _clamp_predictions(raw_prediction)

    predicted_total = float(np.sum(prediction))
    last_total = float(np.sum(recent_counts))
    max_prediction = float(np.max(prediction)) if len(prediction) else 0.0

    nodes = []
    for index, node in enumerate(model_data["region_nodes"]):
        predicted_count = float(prediction[index])
        last_count = float(recent_counts[index])
        four_week_mean = float(rolling_mean[index])
        share = predicted_count / predicted_total if predicted_total > 0 else 0.0
        normalized = predicted_count / max_prediction if max_prediction > 0 else 0.0
        nodes.append({
            "name": node["name"],
            "lat": float(node["lat"]),
            "lon": float(node["lon"]),
            "predicted_count": predicted_count,
            "predicted_count_rounded": int(round(predicted_count)),
            "last_week_count": last_count,
            "rolling_4w_mean": four_week_mean,
            "delta_vs_last_week": predicted_count - last_count,
            "share": float(share),
            "normalized_intensity": float(normalized),
        })

    nodes.sort(key=lambda item: item["predicted_count"], reverse=True)
    top_region = nodes[0]["name"] if nodes else "Unknown"

    return {
        "status": "success",
        "model_type": model_data["model_type"],
        "trained_at": model_data.get("trained_at"),
        "window_size_weeks": window_size,
        "min_magnitude": float(model_data.get("min_magnitude", MIN_MAGNITUDE)),
        "data_source": data_source,
        "predicted_week_start": _utc_iso(predicted_week_start),
        "nodes": nodes,
        "summary": {
            "top_region": top_region,
            "predicted_total_count": predicted_total,
            "last_week_total_count": last_total,
            "catalog_start": catalog_start,
            "catalog_end": catalog_end,
            "week_count": week_count,
            "event_count": event_count,
            "province_count": len(model_data.get("region_nodes", [])),
        },
        "metrics": model_data.get("metrics", {}),
    }


if __name__ == "__main__":
    default_events = load_events_from_file(EARTHQUAKE_HISTORY_FILE)
    if len(default_events) < 200:
        print("Regional pilot training needs a populated earthquake history file.")
    else:
        trained = train_regional_pilot(default_events)
        print("[regional-pilot] model saved:", MODEL_PATH)
        print(
            "[regional-pilot] graph total RMSE:",
            trained["metrics"]["graph_temporal"]["total_rmse"],
        )
