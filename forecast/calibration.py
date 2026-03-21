import numpy as np
from sklearn.calibration import calibration_curve


def compute_calibration(y_true, y_prob, bins=10):
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)

    if y_true.size == 0 or y_prob.size == 0:
        return {"prob_true": [], "prob_pred": [], "bins": int(bins)}

    try:
        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=bins)
    except Exception:
        return {"prob_true": [], "prob_pred": [], "bins": int(bins)}

    return {
        "prob_true": prob_true.tolist(),
        "prob_pred": prob_pred.tolist(),
        "bins": int(bins),
    }
