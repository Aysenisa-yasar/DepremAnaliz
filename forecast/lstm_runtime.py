import os

from forecast.lstm_stub import lstm_sequence_score


def predict_lstm_sequence(events, lat, lon):
    if os.getenv("ENABLE_TORCH_LSTM_RUNTIME", "").lower() not in {"1", "true", "yes"}:
        return float(lstm_sequence_score(events))

    try:
        from forecast.lstm_model import predict_lstm_sequence as real_predict_lstm_sequence
    except Exception:
        return float(lstm_sequence_score(events))

    try:
        return float(real_predict_lstm_sequence(events, lat, lon))
    except Exception:
        return float(lstm_sequence_score(events))
