import json
import logging

import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Ndozi Climate Due Diligence Engine's narrative writer.
You receive real, computed climate risk scores derived from NASA SRTM, CHIRPS rainfall data,
JRC Global Surface Water, ESA WorldCover, OpenStreetMap, and CMIP6 projections.
Your job is to write clear, probabilistic, evidence-based narrative text interpreting
these scores for a Nigerian real estate audience.

RULES:
- Always use probabilistic language: \"shows elevated vulnerability\", \"models suggest\",
  \"based on available data\", \"assessed exposure indicates\"
- Never write deterministic statements like \"this land will flood\" or \"guaranteed risk\"
- Be specific to the location, state, and property type provided
- The climate adaptation cost figure is a modelled estimate - never describe it as a quote or valuation
- Keep the exposure summary to 2-3 sentences maximum
- Recommendations must be specific and actionable for the stated property type

Return ONLY valid JSON, no markdown, no backticks:
{
  \"summary\": \"2-3 sentence probabilistic exposure summary\",
  \"recommendations\": \"2-3 specific actionable recommendations separated by newlines\"
}"""


def _fallback_narrative(state: str, property_type: str, composite: int) -> dict:
    summary = (
        f"Based on available geospatial and climate datasets for {state}, the assessed exposure "
        f"for this {property_type.lower()} indicates a composite risk level of {composite}/100. "
        "Models suggest risk management should prioritize flood resilience, drainage quality, "
        "and heat-adaptive design over a 10-year horizon."
    )
    recommendations = (
        "Commission a site-specific drainage and elevation survey before final investment commitment.\n"
        "Include flood-resilient materials and stormwater controls in baseline design assumptions.\n"
        "Ring-fence adaptation budget and review insurance coverage against modeled climate exposure."
    )
    return {"summary": summary, "recommendations": recommendations}


def generate_narrative(
    lat: float,
    lng: float,
    state: str,
    property_type: str,
    flood: int,
    rainfall: int,
    heat: int,
    coastal: int,
    composite: int,
    grade: str,
    pipeline_context: dict,
) -> dict:
    if not settings.ANTHROPIC_API_KEY:
        return _fallback_narrative(state, property_type, composite)

    user_prompt = f"""
Property Assessment Data:
- GPS: {lat}, {lng}
- State: {state}, Nigeria
- Property Type: {property_type}
- Climate Investment Grade: {grade}
- Composite Score: {composite}/100

Computed Risk Scores (0-100, higher = greater risk exposure):
- Flood Exposure: {flood} (derived from NASA SRTM elevation, JRC flood history, drainage analysis)
- Rainfall Risk: {rainfall} (CHIRPS 10-year historical rainfall intensity)
- Heat Index: {heat} (CMIP6 SSP2-4.5 projection, latitude-adjusted)
- Coastal Risk: {coastal} (OSM coastline distance + DEM analysis)

Additional Context:
- Elevation: {pipeline_context.get('elevation_m', 'N/A')}m ASL
- Slope: {pipeline_context.get('slope_deg', 'N/A')} degrees
- Distance to coast: {pipeline_context.get('distance_to_coast_km', 'N/A')}km
- Land cover: {pipeline_context.get('cover_class', 'N/A')}
- Flood occurrence: {pipeline_context.get('flood_recurrence', 'N/A')}
- Flood occurrence percentage: {pipeline_context.get('flood_occurrence_pct', 'N/A')}%
- Annual rainfall mean: {pipeline_context.get('annual_mean_mm', 'N/A')}mm
- Max 3-day rainfall event: {pipeline_context.get('max_3day_event_mm', 'N/A')}mm
- Drainage density: {pipeline_context.get('drainage_density', 'N/A')}
- 10-year rainfall change projection: {pipeline_context.get('projected_rainfall_change_pct', 'N/A')}%
- 10-year temperature increase projection: {pipeline_context.get('projected_temp_increase_c', 'N/A')}C
- Heat-stress days increase: {pipeline_context.get('heat_stress_days_increase', 'N/A')} days/year
- Data notes: {pipeline_context.get('data_notes', 'Full dataset available')}

Write the narrative summary and recommendations for this assessed property.
"""

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(text)
        if "summary" in parsed and "recommendations" in parsed:
            return parsed
    except Exception as exc:
        logger.warning("Anthropic narrative fallback used: %s", exc)

    return _fallback_narrative(state, property_type, composite)
