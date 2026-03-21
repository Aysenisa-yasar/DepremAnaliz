import numpy as np


def compute_b_value(events):
    mags = []
    for event in events or []:
        try:
            mag = float(event.get("mag", 0) or 0)
        except (TypeError, ValueError):
            mag = 0.0
        if mag > 0:
            mags.append(mag)

    if len(mags) < 10:
        return 1.0

    mags = np.array(mags, dtype=np.float64)
    mean_mag = float(np.mean(mags))
    m_min = float(np.min(mags))

    if mean_mag <= m_min:
        return 1.0

    b_value = np.log10(np.e) / (mean_mag - m_min)
    return float(b_value)
