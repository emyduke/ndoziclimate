from datetime import datetime, timezone
import logging
import math

import requests

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def get_infrastructure_data(lat: float, lng: float) -> dict:
    try:
        query = f"""
[out:json][timeout:10];
(
  way[\"waterway\"~\"drain|canal|ditch|river|stream\"](around:1000,{lat},{lng});
  node[\"waterway\"~\"drain|canal\"](around:500,{lat},{lng});
);
out body center;
"""
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers={
                "User-Agent": "NdoziClimate/1.0 (+ndoziclimate.org)",
                "Accept": "application/json",
            },
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()

        drains = []
        rivers = []
        for element in data.get("elements", []):
            tags = element.get("tags", {})
            waterway = tags.get("waterway", "")
            e_lat = element.get("lat", element.get("center", {}).get("lat"))
            e_lng = element.get("lon", element.get("center", {}).get("lon"))
            if e_lat is None or e_lng is None:
                continue
            d = _haversine_m(lat, lng, e_lat, e_lng)
            if waterway in {"river", "stream"}:
                rivers.append(d)
            else:
                drains.append(d)

        nearest_drain_m = min(drains) if drains else None
        nearest_river_m = min(rivers) if rivers else None

        density_count = len(drains)
        if density_count >= 12:
            drainage_density = "high"
            score = 20
        elif density_count >= 5:
            drainage_density = "medium"
            score = 38
        elif density_count >= 1:
            drainage_density = "low"
            score = 58
        else:
            drainage_density = "none"
            score = 74

        if nearest_river_m is not None and nearest_river_m < 200:
            score += 15
        score = max(0, min(100, score))

        return {
            "nearest_drain_m": round(nearest_drain_m, 1) if nearest_drain_m else None,
            "nearest_river_m": round(nearest_river_m, 1) if nearest_river_m else None,
            "drainage_density": drainage_density,
            "infra_score": score,
            "source": {
                "name": "OpenStreetMap Overpass",
                "url": OVERPASS_URL,
                "retrieval_date": datetime.now(timezone.utc).isoformat(),
                "notes": "Drainage density from mapped waterways within 1 km.",
                "status": "ok",
            },
        }
    except Exception as exc:
        logger.warning("Overpass infrastructure fetch failed for %s,%s: %s", lat, lng, exc)
        return {
            "nearest_drain_m": None,
            "nearest_river_m": None,
            "drainage_density": "unknown",
            "infra_score": 50,
            "data_notes": "Drainage infrastructure data unavailable for this coordinate; neutral drainage risk applied.",
            "source": {
                "name": "OpenStreetMap Overpass",
                "url": OVERPASS_URL,
                "retrieval_date": datetime.now(timezone.utc).isoformat(),
                "notes": "Fallback used due to source error.",
                "status": "unavailable",
            },
        }
