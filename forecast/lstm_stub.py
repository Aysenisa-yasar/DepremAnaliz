def lstm_sequence_score(events):
    if len(events or []) < 20:
        return 0.0

    recent = events[-20:]
    mags = [float(event.get("mag", 0) or 0) for event in recent]

    trend = mags[-1] - mags[0] if len(mags) > 1 else 0.0
    avg_mag = sum(mags) / len(mags) if mags else 0.0

    score = 0.0
    score += min(max(trend, 0.0), 1.0) * 0.5
    score += min(avg_mag / 5.0, 1.0) * 0.5

    return float(min(max(score, 0.0), 1.0))
