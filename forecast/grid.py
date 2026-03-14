# forecast/grid.py - Türkiye grid noktaları (harita tahmin için)
def generate_turkey_grid(step=0.5):
    min_lat = 35.5
    max_lat = 42.5
    min_lon = 25.5
    max_lon = 45.0
    points = []
    lat = min_lat
    while lat <= max_lat:
        lon = min_lon
        while lon <= max_lon:
            points.append({
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "id": f"{round(lat, 2)}_{round(lon, 2)}",
            })
            lon += step
        lat += step
    return points
