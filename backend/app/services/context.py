"""
Farm context assembler for the AI recommendation pipeline.

Gathers all relevant data for a single farm into a unified context dict
that the LLM prompt builder can consume. Every query is scoped to a single
farm_id to enforce data isolation.
"""

import logging
from datetime import datetime, timezone

from postgrest.exceptions import APIError

from app.services.csp_eligibility import fetch_latest_assessment
from app.services.weather import FORECAST_DAYS

logger = logging.getLogger(__name__)

# Columns of csp_eligibility_assessments that csp_eligibility actually writes.
# resource_concerns_met holds the full csp_scoring result (per-concern scores
# and the state ranking threshold used for the evaluation).
_ASSESSMENT_COLUMNS = (
    "eligibility_status, fiscal_year, rc_count_above_threshold, stewardship_score, "
    "act_now_eligible, resource_concerns_met, active_enhancement_codes, notes, "
    "evaluated_at"
)


def _summarize_assessment(row: dict) -> dict:
    """Reduce a csp_eligibility_assessments row to the fields the prompt uses.

    Values that are absent stay None so the prompt omits them instead of
    substituting a default.
    """
    score_detail = row.get("resource_concerns_met")
    if not isinstance(score_detail, dict):
        score_detail = {}

    resource_concerns = [
        {
            "name": concern.get("name") or concern.get("concern_id", ""),
            "points_earned": concern.get("points_earned"),
            "points_possible": concern.get("points_possible"),
            "meets_threshold": bool(concern.get("meets_threshold")),
        }
        for concern in score_detail.get("resource_concern_scores") or []
        if isinstance(concern, dict)
    ]

    return {
        "eligibility_status": row.get("eligibility_status"),
        "fiscal_year": row.get("fiscal_year"),
        "stewardship_score": row.get("stewardship_score"),
        "max_possible_points": score_detail.get("max_possible_points"),
        "rc_count_above_threshold": row.get("rc_count_above_threshold"),
        # The act_now_eligible column is NOT NULL, so it cannot express "the
        # state's ranking threshold is unknown". The score payload can, and
        # takes precedence: None there keeps the line out of the prompt
        # instead of asserting the farm missed a cut-off we do not have.
        "act_now_eligible": score_detail.get(
            "meets_ranking_threshold", row.get("act_now_eligible")
        ),
        "state_ranking_threshold": score_detail.get("state_ranking_threshold"),
        "resource_concerns": resource_concerns,
        "gap_closure_activity_codes": row.get("active_enhancement_codes") or [],
        "notes": row.get("notes"),
        "evaluated_at": row.get("evaluated_at"),
    }


async def assemble_farm_context(farm_id: str, supabase) -> dict:
    """Assemble all available context for a farm into a single dict.

    Security: Every query filters on farm_id (or field_ids derived from that
    farm_id) so that a caller can never leak data from another farm.

    Args:
        farm_id: UUID of the farm to assemble context for.
        supabase: An authenticated Supabase client instance.

    Returns:
        A dict containing farm profile, fields, soil profiles, weather data,
        current practices, acted recommendations, valid EQIP practice codes,
        and the latest CSP assessment summary.  Missing data sections are
        returned as empty lists (or None) with a warning entry so the prompt
        builder can communicate gaps to the LLM.

    Raises:
        ValueError: If the farm cannot be found.
    """
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # 1. Farm profile
    # ------------------------------------------------------------------
    try:
        farm_result = (
            supabase.table("farms")
            .select("*")
            .eq("id", farm_id)
            .single()
            .execute()
        )
        farm = farm_result.data
    except APIError as exc:
        logger.error("Failed to fetch farm=%s: %s", farm_id, exc)
        raise ValueError(f"Farm {farm_id} not found or inaccessible") from exc

    if not farm:
        raise ValueError(f"Farm {farm_id} not found or inaccessible")

    # ------------------------------------------------------------------
    # 2. All fields belonging to this farm
    # ------------------------------------------------------------------
    try:
        fields_result = (
            supabase.table("fields")
            .select("*")
            .eq("farm_id", farm_id)
            .execute()
        )
        fields = fields_result.data or []
    except APIError as exc:
        logger.error("Failed to fetch fields for farm=%s: %s", farm_id, exc)
        fields = []
        warnings.append("Could not fetch fields")

    if not fields:
        warnings.append("Farm has no fields registered")

    field_ids = [f["id"] for f in fields]

    # ------------------------------------------------------------------
    # 3. Soil profiles for all fields (most recent per field)
    # ------------------------------------------------------------------
    soil_profiles: list[dict] = []
    if field_ids:
        try:
            soil_result = (
                supabase.table("soil_profiles")
                .select("*")
                .in_("field_id", field_ids)
                .order("fetched_at", desc=True)
                .execute()
            )
            # De-duplicate to keep only the most recent profile per field
            seen_fields: set[str] = set()
            for row in soil_result.data or []:
                fid = row["field_id"]
                if fid not in seen_fields:
                    soil_profiles.append(row)
                    seen_fields.add(fid)
        except APIError as exc:
            logger.error("Failed to fetch soil profiles for farm=%s: %s", farm_id, exc)
            warnings.append("Could not fetch soil profiles")

    if not soil_profiles:
        warnings.append("No soil data available for any field")

    # ------------------------------------------------------------------
    # 4. Weather cache (most recent 7 days per field)
    # ------------------------------------------------------------------
    weather_data: list[dict] = []
    if field_ids:
        try:
            weather_result = (
                supabase.table("weather_cache")
                .select("*")
                .in_("field_id", field_ids)
                .order("date", desc=True)
                # One forecast per field is cached; scale the row limit with the
                # number of fields so larger farms are not truncated.
                .limit(FORECAST_DAYS * len(field_ids))
                .execute()
            )
            weather_data = weather_result.data or []
        except APIError as exc:
            logger.error("Failed to fetch weather cache for farm=%s: %s", farm_id, exc)
            warnings.append("Could not fetch weather data")

    if not weather_data:
        warnings.append("No weather data available")

    # ------------------------------------------------------------------
    # 5. Current practices (from field records)
    # ------------------------------------------------------------------
    current_practices: list[str] = []
    for field in fields:
        practices = field.get("practices") or []
        for p in practices:
            if p and p not in current_practices:
                current_practices.append(p)

    # ------------------------------------------------------------------
    # 6. Previously acted recommendations (avoid re-recommending)
    # ------------------------------------------------------------------
    acted_recommendations: list[dict] = []
    if field_ids:
        try:
            acted_result = (
                supabase.table("recommendations")
                .select("field_id, practice_code, title, status")
                .in_("field_id", field_ids)
                .in_("status", ["acted", "dismissed"])
                .execute()
            )
            acted_recommendations = acted_result.data or []
        except APIError as exc:
            logger.error(
                "Failed to fetch acted recommendations for farm=%s: %s", farm_id, exc
            )
            warnings.append("Could not fetch recommendation history")

    # ------------------------------------------------------------------
    # 7. Valid EQIP practice codes (reference data for hallucination guard)
    # ------------------------------------------------------------------
    eqip_practices: list[dict] = []
    try:
        eqip_result = (
            supabase.table("eqip_practices")
            .select("code, name, category, description, unit")
            .execute()
        )
        eqip_practices = eqip_result.data or []
    except APIError as exc:
        logger.error("Failed to fetch EQIP practices for farm=%s: %s", farm_id, exc)
        warnings.append("Could not fetch EQIP practice reference data")

    # ------------------------------------------------------------------
    # 8. CSP eligibility assessment (non-fatal)
    # ------------------------------------------------------------------
    csp_assessment: dict | None = None
    try:
        assessment_row = fetch_latest_assessment(supabase, farm_id, _ASSESSMENT_COLUMNS)
    except APIError as exc:
        logger.warning("Could not fetch CSP assessment for farm=%s: %s", farm_id, exc)
        warnings.append("Could not fetch CSP assessment")
    else:
        if assessment_row:
            csp_assessment = _summarize_assessment(assessment_row)

    # ------------------------------------------------------------------
    # 9. Assemble the context dict
    # ------------------------------------------------------------------
    context = {
        "farm": {
            "id": farm["id"],
            "name": farm.get("name", ""),
            "state": farm.get("state", ""),
            "county_fips": farm.get("county_fips", ""),
            "total_acres": farm.get("total_acres", 0),
            "goals": farm.get("goals"),
        },
        "fields": [
            {
                "id": f["id"],
                "name": f.get("name", ""),
                "acres": f.get("acres", 0),
                "crop_type": f.get("crop_type", ""),
                "practices": f.get("practices") or [],
            }
            for f in fields
        ],
        "soil_profiles": [
            {
                "field_id": s["field_id"],
                "texture": s.get("texture", "Unknown"),
                "ph": s.get("ph"),
                "organic_matter_pct": s.get("organic_matter_pct"),
                "ssurgo_map_unit": s.get("ssurgo_map_unit", ""),
            }
            for s in soil_profiles
        ],
        "weather": [
            {
                "field_id": w["field_id"],
                "date": w.get("date", ""),
                "temp_high": w.get("temp_high"),
                "temp_low": w.get("temp_low"),
                "precip_mm": w.get("precip_mm"),
                "soil_temp": w.get("soil_temp"),
            }
            for w in weather_data
        ],
        "current_practices": current_practices,
        "acted_recommendations": [
            {
                "field_id": r["field_id"],
                "practice_code": r["practice_code"],
                "title": r["title"],
                "status": r["status"],
            }
            for r in acted_recommendations
        ],
        "eqip_practices": eqip_practices,
        "csp_assessment": csp_assessment,
        "data_warnings": warnings,
        "assembled_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    logger.info(
        "Assembled context for farm=%s: %d fields, %d soil profiles, "
        "%d weather records, %d EQIP practices, %d warnings",
        farm_id,
        len(fields),
        len(soil_profiles),
        len(weather_data),
        len(eqip_practices),
        len(warnings),
    )

    return context
