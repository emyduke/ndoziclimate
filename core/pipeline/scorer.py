from datetime import datetime, timezone

GRADE_THRESHOLDS = {
    "A": (0, 29),
    "B": (30, 54),
    "C": (55, 74),
    "D": (75, 100),
}

GRADE_LABELS = {
    "A": "Climate Stable",
    "B": "Moderate Adaptation Required",
    "C": "High Climate Exposure",
    "D": "Significant Long-Term Risk",
}

WEIGHTS = {
    "flood": 0.35,
    "rainfall": 0.25,
    "heat": 0.20,
    "coastal": 0.20,
}


def _clamp_score(value: float | int) -> int:
    return int(max(0, min(100, round(float(value)))))


def compute_flood_score(
    elevation: dict, flood_history: dict, land_cover: dict, infrastructure: dict
) -> int:
    value = (
        elevation.get("drainage_score", 50) * 0.30
        + flood_history.get("flood_history_score", 50) * 0.35
        + land_cover.get("land_cover_score", 50) * 0.20
        + infrastructure.get("infra_score", 50) * 0.15
    )
    return _clamp_score(value)


def compute_rainfall_score(rainfall: dict) -> int:
    return _clamp_score(rainfall.get("rainfall_score", 50))


def compute_heat_score(lat: float, state: str, projections: dict) -> int:
    base = projections.get("projection_score", 50)
    north_boost = 8 if lat > 12.0 else 0
    return _clamp_score(base + north_boost)


def compute_coastal_score(coastal: dict, elevation: dict) -> int:
    base = coastal.get("coastal_score", 50)
    elev = elevation.get("elevation_m")
    if elev is not None and elev < 10 and coastal.get("distance_to_coast_km", 999) <= 10:
        base += 10
    return _clamp_score(base)


def compute_grade(composite: int) -> tuple[str, str]:
    for grade, (lo, hi) in GRADE_THRESHOLDS.items():
        if lo <= composite <= hi:
            return grade, GRADE_LABELS[grade]
    return "D", GRADE_LABELS["D"]


def _format_naira(value: float) -> str:
    return f"N{int(round(value)):,}"


def compute_adaptation_cost(
    composite: int, property_type: str, coastal: dict, flood_history: dict
) -> tuple[str, str]:
    base_costs = {
        "Residential Land": (500000, 1200000),
        "Commercial Land": (2000000, 8000000),
        "Industrial Land": (3500000, 15000000),
        "Residential Building": (800000, 3500000),
        "Commercial Building": (2000000, 8000000),
        "Agricultural Land": (500000, 1200000),
    }
    grade, _ = compute_grade(composite)
    multipliers = {"A": 1.0, "B": 1.5, "C": 2.8, "D": 4.5}

    lo, hi = base_costs.get(property_type, (800000, 3500000))
    multiplier = multipliers[grade]

    if coastal.get("storm_surge_exposure") == "high":
        multiplier += 0.4
    if flood_history.get("flood_recurrence") in {"seasonal", "permanent"}:
        multiplier += 0.3

    return _format_naira(lo * multiplier), _format_naira(hi * multiplier)


def build_data_sources_list(pipeline_results: dict) -> list[dict]:
    names = [
        "elevation",
        "rainfall",
        "flood_history",
        "land_cover",
        "infrastructure",
        "coastal",
        "projections",
    ]
    output = []
    now = datetime.now(timezone.utc).isoformat()
    for name in names:
        source = pipeline_results.get(name, {}).get("source", {})
        output.append(
            {
                "name": source.get("name", name),
                "url": source.get("url", ""),
                "retrieval_date": source.get("retrieval_date", now),
                "notes": source.get("notes", ""),
            }
        )
    return output


def assemble_result(pipeline_results: dict, ai_narrative: dict) -> dict:
    elevation = pipeline_results.get("elevation", {})
    rainfall = pipeline_results.get("rainfall", {})
    flood_history = pipeline_results.get("flood_history", {})
    land_cover = pipeline_results.get("land_cover", {})
    infrastructure = pipeline_results.get("infrastructure", {})
    coastal = pipeline_results.get("coastal", {})
    projections = pipeline_results.get("projections", {})

    flood = compute_flood_score(elevation, flood_history, land_cover, infrastructure)
    rainfall_score = compute_rainfall_score(rainfall)
    heat = compute_heat_score(
        pipeline_results.get("lat", 9.0), pipeline_results.get("state", ""), projections
    )
    coastal_score = compute_coastal_score(coastal, elevation)

    composite = _clamp_score(
        flood * WEIGHTS["flood"]
        + rainfall_score * WEIGHTS["rainfall"]
        + heat * WEIGHTS["heat"]
        + coastal_score * WEIGHTS["coastal"]
    )
    grade, grade_label = compute_grade(composite)
    cost_low, cost_high = compute_adaptation_cost(
        composite,
        pipeline_results.get("property_type", "Residential Building"),
        coastal,
        flood_history,
    )

    return {
        "grade": grade,
        "gradeLabel": grade_label,
        "compositeScore": composite,
        "flood": flood,
        "rainfall": rainfall_score,
        "heat": heat,
        "coastal": coastal_score,
        "exposureSummary": ai_narrative["summary"],
        "costLow": cost_low,
        "costHigh": cost_high,
        "recommendations": ai_narrative["recommendations"],
        "dataSources": build_data_sources_list(pipeline_results),
        "projectionScenario": "SSP2-4.5 moderate rainfall increase",
        "dataRetrievedAt": datetime.now(timezone.utc).isoformat(),
        "dataNotes": pipeline_results.get("data_notes", ""),
    }
