from datetime import datetime, timezone
import logging

from .gee import initialize_ee

logger = logging.getLogger(__name__)

WORLDCOVER_LABELS = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse vegetation",
    70: "Snow and ice",
    80: "Permanent water bodies",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}


def get_land_cover(lat: float, lng: float) -> dict:
    if initialize_ee():
        try:
            import ee

            point = ee.Geometry.Point([lng, lat])
            buffer_500m = point.buffer(500)

            worldcover = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")

            class_val = ee.Number(
                worldcover.reduceRegion(
                    reducer=ee.Reducer.mode(),
                    geometry=point,
                    scale=10,
                    maxPixels=10_000_000,
                ).get("Map")
            )

            built_mask = worldcover.eq(50)
            impervious_pct = float(
                ee.Number(
                    built_mask.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=buffer_500m,
                        scale=10,
                        maxPixels=10_000_000,
                    ).get("Map")
                )
                .multiply(100)
                .getInfo()
            )

            wetland_mask = worldcover.eq(90).Or(worldcover.eq(95)).Or(worldcover.eq(80))
            wetland_present = bool(
                ee.Number(
                    wetland_mask.reduceRegion(
                        reducer=ee.Reducer.max(),
                        geometry=buffer_500m,
                        scale=10,
                        maxPixels=10_000_000,
                    ).get("Map")
                ).getInfo()
            )

            class_code = int(class_val.getInfo())
            cover_class = WORLDCOVER_LABELS.get(class_code, "Unknown")
            wetland_proximity_m = 250.0 if wetland_present else 1500.0

            score = 25
            if wetland_proximity_m <= 500:
                score += 30
            if impervious_pct > 60:
                score += 15

            score = max(0, min(100, score))
            return {
                "cover_class": cover_class,
                "wetland_proximity_m": wetland_proximity_m,
                "impervious_pct": round(impervious_pct, 1),
                "land_cover_score": score,
                "source": {
                    "name": "ESA WorldCover v200 via Google Earth Engine",
                    "url": "https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200",
                    "retrieval_date": datetime.now(timezone.utc).isoformat(),
                    "notes": "Class mode and 500m built-up/wetland context.",
                    "status": "ok",
                },
            }
        except Exception as exc:
            logger.warning("WorldCover GEE query failed for %s,%s: %s", lat, lng, exc)

    logger.warning("WorldCover source unavailable for %s,%s; applying neutral fallback", lat, lng)
    return {
        "cover_class": "Unknown",
        "wetland_proximity_m": None,
        "impervious_pct": None,
        "land_cover_score": 50,
        "data_notes": "Land cover data unavailable for this coordinate; neutral drainage risk applied.",
        "source": {
            "name": "ESA WorldCover v200",
            "url": "https://worldcover2021.esa.int/",
            "retrieval_date": datetime.now(timezone.utc).isoformat(),
            "notes": "Fallback used due to source unavailability.",
            "status": "unavailable",
        },
    }
