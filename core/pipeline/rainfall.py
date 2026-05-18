from datetime import datetime, timezone
import logging

from .gee import initialize_ee

logger = logging.getLogger(__name__)


def get_rainfall_data(lat: float, lng: float) -> dict:
    if initialize_ee():
        try:
            import ee

            point = ee.Geometry.Point([lng, lat])
            end = ee.Date(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            start = end.advance(-10, "year")

            daily = (
                ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
                .filterDate(start, end)
                .filterBounds(point)
                .select("precipitation")
            )

            annual_total = ee.Number(
                daily.sum().reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=point,
                    scale=5000,
                    maxPixels=10_000_000,
                ).get("precipitation")
            )
            max_daily = ee.Number(
                daily.max().reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=point,
                    scale=5000,
                    maxPixels=10_000_000,
                ).get("precipitation")
            )

            annual_mean_mm = float(annual_total.divide(10).getInfo())
            max_3day_event_mm = float(max_daily.multiply(3).getInfo())

            if annual_mean_mm >= 2000 or max_3day_event_mm >= 170:
                intensity = "extreme"
                score = 85
            elif annual_mean_mm >= 1500 or max_3day_event_mm >= 140:
                intensity = "high"
                score = 68
            elif annual_mean_mm >= 900 or max_3day_event_mm >= 100:
                intensity = "moderate"
                score = 48
            else:
                intensity = "low"
                score = 30

            return {
                "annual_mean_mm": round(annual_mean_mm, 1),
                "max_3day_event_mm": round(max_3day_event_mm, 1),
                "wet_season_intensity": intensity,
                "rainfall_score": score,
                "source": {
                    "name": "CHIRPS v2.0 via Google Earth Engine",
                    "url": "https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY",
                    "retrieval_date": datetime.now(timezone.utc).isoformat(),
                    "notes": "10-year point-based daily rainfall aggregation.",
                    "status": "ok",
                },
            }
        except Exception as exc:
            logger.warning("CHIRPS GEE query failed for %s,%s: %s", lat, lng, exc)

    logger.warning("CHIRPS rainfall source unavailable for %s,%s; applying neutral fallback", lat, lng)
    return {
        "annual_mean_mm": None,
        "max_3day_event_mm": None,
        "wet_season_intensity": "moderate",
        "rainfall_score": 50,
        "data_notes": "Rainfall data unavailable for this coordinate; neutral rainfall score applied.",
        "source": {
            "name": "CHIRPS v2.0",
            "url": "https://data.chc.ucsb.edu/products/CHIRPS-2.0/",
            "retrieval_date": datetime.now(timezone.utc).isoformat(),
            "notes": "Fallback used due to source unavailability.",
            "status": "unavailable",
        },
    }
