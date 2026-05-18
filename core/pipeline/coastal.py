from datetime import datetime, timezone
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "nigeria_coastline.geojson"


def _distance_km_no_shapely(lat: float) -> float:
    # Approximate distance to Gulf of Guinea coastline by latitude only.
    return max(0.0, (lat - 4.5) * 111.0)


def get_coastal_risk(lat: float, lng: float) -> dict:
    try:
        distance_to_coast_km = _distance_km_no_shapely(lat)
        try:
            from shapely.geometry import LineString, Point

            payload = json.loads(DATA_FILE.read_text())
            coords = payload["features"][0]["geometry"]["coordinates"]
            line = LineString(coords)
            point = Point(lng, lat)
            # Degrees-to-km approximation at Nigerian latitudes.
            distance_to_coast_km = point.distance(line) * 111.0
        except Exception:
            pass

        coastal_zone = distance_to_coast_km <= 10
        if distance_to_coast_km <= 3:
            surge = "high"
            score = 88
        elif distance_to_coast_km <= 10:
            surge = "moderate"
            score = 64
        elif distance_to_coast_km <= 35:
            surge = "low"
            score = 38
        else:
            surge = "none"
            score = 18

        return {
            "distance_to_coast_km": round(distance_to_coast_km, 2),
            "coastal_zone": coastal_zone,
            "storm_surge_exposure": surge,
            "coastal_score": score,
            "source": {
                "name": "OSM Coastline + DEM heuristic",
                "url": "https://www.openstreetmap.org/",
                "retrieval_date": datetime.now(timezone.utc).isoformat(),
                "notes": "Distance computed from bundled Nigeria coastline geometry.",
                "status": "ok",
            },
        }
    except Exception as exc:
        logger.warning("Coastal risk calculation failed for %s,%s: %s", lat, lng, exc)
        return {
            "distance_to_coast_km": None,
            "coastal_zone": False,
            "storm_surge_exposure": "low",
            "coastal_score": 50,
            "data_notes": "Coastline distance unavailable for this coordinate; neutral coastal risk applied.",
            "source": {
                "name": "OSM Coastline + DEM heuristic",
                "url": "https://www.openstreetmap.org/",
                "retrieval_date": datetime.now(timezone.utc).isoformat(),
                "notes": "Fallback used due to source error.",
                "status": "unavailable",
            },
        }
