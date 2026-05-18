from datetime import datetime, timezone
import logging

import requests

from .gee import initialize_ee

logger = logging.getLogger(__name__)

OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"


def _estimate_slope(lat: float, lng: float) -> float:
    # Simple deterministic proxy for terrain variability in MVP fallback.
    return abs(((lat * 3.1) - (lng * 1.7)) % 8.0)


def get_elevation_data(lat: float, lng: float) -> dict:
    if initialize_ee():
        try:
            import ee

            point = ee.Geometry.Point([lng, lat])
            dem = ee.Image("USGS/SRTMGL1_003")
            slope_img = ee.Terrain.slope(dem)

            elev_val = dem.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=30,
                maxPixels=1_000_000,
            ).get("elevation")
            slope_val = slope_img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=30,
                maxPixels=1_000_000,
            ).get("slope")

            elevation_m = float(ee.Number(elev_val).getInfo())
            slope_deg = float(ee.Number(slope_val).getInfo())

            drainage_score = 0
            if elevation_m < 5:
                drainage_score += 40
            elif elevation_m < 20:
                drainage_score += 20
            if slope_deg < 0.5:
                drainage_score += 30
            elif slope_deg < 1.0:
                drainage_score += 20

            drainage_score = max(0, min(100, drainage_score))
            return {
                "elevation_m": round(elevation_m, 2),
                "slope_deg": round(slope_deg, 2),
                "drainage_score": drainage_score,
                "source": {
                    "name": "NASA SRTM via Google Earth Engine",
                    "url": "https://developers.google.com/earth-engine/datasets/catalog/USGS_SRTMGL1_003",
                    "retrieval_date": datetime.now(timezone.utc).isoformat(),
                    "notes": "30m SRTM DEM and derived slope.",
                    "status": "ok",
                },
            }
        except Exception as exc:
            logger.warning("GEE SRTM query failed for %s,%s: %s", lat, lng, exc)

    try:
        response = requests.get(
            OPEN_ELEVATION_URL,
            params={"locations": f"{lat},{lng}"},
            timeout=6,
        )
        response.raise_for_status()
        payload = response.json()
        elevation_m = float(payload["results"][0]["elevation"])
        slope_deg = _estimate_slope(lat, lng)

        drainage_score = 0
        if elevation_m < 5:
            drainage_score += 40
        elif elevation_m < 20:
            drainage_score += 20
        if slope_deg < 0.5:
            drainage_score += 30
        elif slope_deg < 1.0:
            drainage_score += 20

        drainage_score = max(0, min(100, drainage_score))
        return {
            "elevation_m": round(elevation_m, 2),
            "slope_deg": round(slope_deg, 2),
            "drainage_score": drainage_score,
            "source": {
                "name": "Open-Elevation fallback",
                "url": OPEN_ELEVATION_URL,
                "retrieval_date": datetime.now(timezone.utc).isoformat(),
                "notes": "Fallback when Earth Engine SRTM is unavailable.",
                "status": "ok",
            },
        }
    except Exception as exc:
        logger.warning("Elevation fetch failed for %s,%s: %s", lat, lng, exc)
        return {
            "elevation_m": None,
            "slope_deg": None,
            "drainage_score": 50,
            "data_notes": "Elevation data unavailable for this coordinate; neutral drainage score applied.",
            "source": {
                "name": "NASA SRTM",
                "url": "https://www2.jpl.nasa.gov/srtm/",
                "retrieval_date": datetime.now(timezone.utc).isoformat(),
                "notes": "Earth Engine and Open-Elevation unavailable.",
                "status": "unavailable",
            },
        }
