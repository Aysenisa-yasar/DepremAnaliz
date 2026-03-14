# forecast/etas_like.py - ETAS-benzeri hibrit skor (aktivite + büyüklük + mesafe + recency + swarm)
def etas_like_score(features: dict) -> float:
    score = 0.0
    score += min(features.get("count", 0) / 20.0, 1.0) * 0.20
    score += min(features.get("max_mag", 0) / 6.5, 1.0) * 0.20
    score += (1.0 - min(features.get("min_distance", 999.0) / 200.0, 1.0)) * 0.20
    score += min(features.get("recency_energy", 0.0) / 8.0, 1.0) * 0.20
    score += min(features.get("swarm_ratio", 0.0), 1.0) * 0.20
    return max(0.0, min(score, 1.0))
