from datetime import datetime, timezone
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "cmip6_nigeria_state_projections.json"


def get_climate_projections(lat: float, lng: float, state: str) -> dict:
    try:
        projections = json.loads(DATA_FILE.read_text())
        data = projections.get(state)
        if not data:
            raise ValueError(f"No projection data configured for {state}")

        projection_score = int(
            max(
                0,
                min(
                    100,
                    30
                    + (data["rainfall_change_pct"] * 2)
                    + (data["temp_increase_c"] * 20)
                    + (data["heat_stress_days_increase"] * 0.6),
                ),
            )
        )

        return {
            "scenario": "SSP2-4.5 moderate",
            "projected_rainfall_change_pct": data["rainfall_change_pct"],
            "projected_temp_increase_c": data["temp_increase_c"],
            "heat_stress_days_increase": data["heat_stress_days_increase"],
            "projection_score": projection_score,
            "source": {
                "name": "CMIP6 CORDEX-Africa regional summary",
                "url": "https://www.ipcc-data.org/",
                "retrieval_date": datetime.now(timezone.utc).isoformat(),
                "notes": data.get("notes", "SSP2-4.5 ensemble summary."),
                "status": "ok",
            },
        }
    except Exception as exc:
        logger.warning("Projection lookup failed for %s (%s,%s): %s", state, lat, lng, exc)
        return {
            "scenario": "SSP2-4.5 moderate",
            "projected_rainfall_change_pct": 6.5,
            "projected_temp_increase_c": 1.2,
            "heat_stress_days_increase": 16,
            "projection_score": 50,
            "data_notes": "CMIP6 state projection unavailable; national ensemble average applied.",
            "source": {
                "name": "CMIP6 CORDEX-Africa regional summary",
                "url": "https://www.ipcc-data.org/",
                "retrieval_date": datetime.now(timezone.utc).isoformat(),
                "notes": "Fallback used due to source error.",
                "status": "unavailable",
            },
        }
