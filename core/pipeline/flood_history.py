from datetime import datetime, timezone
import logging

from .gee import initialize_ee

logger = logging.getLogger(__name__)


def get_flood_history(lat: float, lng: float) -> dict:
    if initialize_ee():
        try:
            import ee

            point = ee.Geometry.Point([lng, lat])
            area = point.buffer(200)
            gsw = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")

            occurrence = ee.Number(
                gsw.select("occurrence").reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=area,
                    scale=30,
                    maxPixels=10_000_000,
                ).get("occurrence")
            )
            max_extent = ee.Number(
                gsw.select("max_extent").reduceRegion(
                    reducer=ee.Reducer.max(),
                    geometry=area,
                    scale=30,
                    maxPixels=10_000_000,
                ).get("max_extent")
            )

            occurrence_pct = int(round(float(occurrence.getInfo() or 0)))
            max_extent_overlap = int(max_extent.getInfo() or 0) > 0

            if occurrence_pct >= 60:
                recurrence = "permanent"
                score = 90
            elif occurrence_pct >= 30:
                recurrence = "seasonal"
                score = 72
            elif occurrence_pct >= 12:
                recurrence = "rare"
                score = 48
            else:
                recurrence = "none"
                score = 24

            return {
                "max_extent_overlap": max_extent_overlap,
                "occurrence_pct": occurrence_pct,
                "flood_recurrence": recurrence,
                "flood_history_score": score,
                "source": {
                    "name": "JRC Global Surface Water via Google Earth Engine",
                    "url": "https://developers.google.com/earth-engine/datasets/catalog/JRC_GSW1_4_GlobalSurfaceWater",
                    "retrieval_date": datetime.now(timezone.utc).isoformat(),
                    "notes": "200m buffered occurrence and max extent query.",
                    "status": "ok",
                },
            }
        except Exception as exc:
            logger.warning("JRC GEE query failed for %s,%s: %s", lat, lng, exc)

    logger.warning("JRC flood history source unavailable for %s,%s; applying neutral fallback", lat, lng)
    return {
        "max_extent_overlap": False,
        "occurrence_pct": 0,
        "flood_recurrence": "rare",
        "flood_history_score": 50,
        "data_notes": "Surface water history unavailable for this coordinate; neutral flood history score applied.",
        "source": {
            "name": "JRC Global Surface Water",
            "url": "https://global-surface-water.appspot.com/",
            "retrieval_date": datetime.now(timezone.utc).isoformat(),
            "notes": "Fallback used due to source unavailability.",
            "status": "unavailable",
        },
    }
