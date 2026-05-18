import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .ai_layer import generate_narrative
from .cache import cache_get, cache_set
from .models import AssessmentResult
from .pipeline import (
    climate_proj,
    coastal,
    elevation,
    flood_history,
    infrastructure,
    land_cover,
    rainfall,
)
from .pipeline.scorer import (
    WEIGHTS,
    assemble_result,
    compute_coastal_score,
    compute_flood_score,
    compute_grade,
    compute_heat_score,
    compute_rainfall_score,
)
from .serializers import AssessmentInputSerializer

logger = logging.getLogger(__name__)


class IndexView(TemplateView):
    template_name = "index.html"


class AssessmentView(APIView):
    def post(self, request):
        serializer = AssessmentInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        lat = data["lat"]
        lng = data["lng"]
        state = data["state"]
        property_type = data["property_type"]
        notes = data.get("notes", "")

        cache_key = hashlib.md5(
            f"{round(lat,3)},{round(lng,3)},{state},{property_type}".encode()
        ).hexdigest()

        cached = cache_get(cache_key)
        if cached:
            logger.info("Cache hit: %s", cache_key)
            return Response(cached)

        try:
            with ThreadPoolExecutor(max_workers=7) as pool:
                futures = {
                    "elevation": pool.submit(elevation.get_elevation_data, lat, lng),
                    "rainfall": pool.submit(rainfall.get_rainfall_data, lat, lng),
                    "flood_history": pool.submit(flood_history.get_flood_history, lat, lng),
                    "land_cover": pool.submit(land_cover.get_land_cover, lat, lng),
                    "infrastructure": pool.submit(
                        infrastructure.get_infrastructure_data, lat, lng
                    ),
                    "coastal": pool.submit(coastal.get_coastal_risk, lat, lng),
                    "projections": pool.submit(
                        climate_proj.get_climate_projections, lat, lng, state
                    ),
                }
                pipeline_results = {name: f.result() for name, f in futures.items()}

            elev_data = pipeline_results["elevation"]
            rain_data = pipeline_results["rainfall"]
            flood_data = pipeline_results["flood_history"]
            cover_data = pipeline_results["land_cover"]
            infra_data = pipeline_results["infrastructure"]
            coast_data = pipeline_results["coastal"]
            proj_data = pipeline_results["projections"]

            flood_score = compute_flood_score(elev_data, flood_data, cover_data, infra_data)
            rain_score = compute_rainfall_score(rain_data)
            heat_score = compute_heat_score(lat, state, proj_data)
            coast_score = compute_coastal_score(coast_data, elev_data)

            composite = int(
                flood_score * WEIGHTS["flood"]
                + rain_score * WEIGHTS["rainfall"]
                + heat_score * WEIGHTS["heat"]
                + coast_score * WEIGHTS["coastal"]
            )
            grade, grade_label = compute_grade(composite)

            data_notes = " | ".join(
                [
                    pipeline_results[k].get("data_notes", "")
                    for k in [
                        "elevation",
                        "rainfall",
                        "flood_history",
                        "land_cover",
                        "infrastructure",
                        "coastal",
                        "projections",
                    ]
                    if pipeline_results[k].get("data_notes")
                ]
            )

            pipeline_context = {
                "elevation_m": elev_data.get("elevation_m"),
                "slope_deg": elev_data.get("slope_deg"),
                "distance_to_coast_km": coast_data.get("distance_to_coast_km"),
                "cover_class": cover_data.get("cover_class"),
                "flood_recurrence": flood_data.get("flood_recurrence"),
                "flood_occurrence_pct": flood_data.get("occurrence_pct"),
                "annual_mean_mm": rain_data.get("annual_mean_mm"),
                "max_3day_event_mm": rain_data.get("max_3day_event_mm"),
                "projected_rainfall_change_pct": proj_data.get(
                    "projected_rainfall_change_pct"
                ),
                "projected_temp_increase_c": proj_data.get("projected_temp_increase_c"),
                "heat_stress_days_increase": proj_data.get("heat_stress_days_increase"),
                "drainage_density": infra_data.get("drainage_density"),
                "data_notes": data_notes,
            }

            ai_narrative = generate_narrative(
                lat,
                lng,
                state,
                property_type,
                flood_score,
                rain_score,
                heat_score,
                coast_score,
                composite,
                grade,
                pipeline_context,
            )

            result = assemble_result(
                {
                    **pipeline_results,
                    "lat": lat,
                    "lng": lng,
                    "state": state,
                    "property_type": property_type,
                    "data_notes": data_notes,
                },
                ai_narrative,
            )

            AssessmentResult.objects.create(
                latitude=lat,
                longitude=lng,
                state=state,
                property_type=property_type,
                notes=notes,
                composite_score=composite,
                flood_score=flood_score,
                rainfall_score=rain_score,
                heat_score=heat_score,
                coastal_score=coast_score,
                grade=grade,
                grade_label=grade_label,
                exposure_summary=ai_narrative["summary"],
                cost_low=result["costLow"],
                cost_high=result["costHigh"],
                recommendations=ai_narrative["recommendations"],
                data_sources_used=result["dataSources"],
                data_notes=data_notes,
            )

            cache_set(cache_key, result)
            return Response(result)
        except Exception as exc:
            logger.exception("Assessment pipeline error: %s", exc)
            return Response(
                {"error": "Assessment failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
