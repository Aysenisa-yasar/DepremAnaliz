import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from forecast.lstm_model import train_lstm


if __name__ == "__main__":
    train_lstm()
