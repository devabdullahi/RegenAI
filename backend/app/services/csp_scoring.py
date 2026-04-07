"""
CSP stewardship score calculator for RegenAI.

Implements the USDA NRCS Conservation Assessment Ranking Tool (CART) logic
for Midwest row-crop operations. Scores are calculated per the eight Priority
Resource Concern categories and compared against state-specific ranking
thresholds to determine whether a farm qualifies for the CSP "ACT NOW" fast-
track approval pathway.

Point allocations are derived from NRCS FY2024 CART worksheets. State ranking
thresholds represent historical median cut-off scores for Midwest states.
"""

import logging
from datetime import datetime, timezone
from typing import Final

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CART configuration constants
# ---------------------------------------------------------------------------

# Maximum points per resource concern category (NRCS FY2024 CART)
_MAX_POINTS_PER_CONCERN: Final[dict[str, float]] = {
    "soil_health": 20.0,
    "soil_erosion": 15.0,
    "water_quality": 20.0,
    "water_quantity": 10.0,
    "air_quality": 10.0,
    "plant_condition": 10.0,
    "animals": 5.0,
    "energy": 10.0,
}

_MAX_TOTAL_POINTS: Final[float] = sum(_MAX_POINTS_PER_CONCERN.values())  # 100.0

# Human-readable names for the 8 NRCS priority resource concern categories
_CONCERN_NAMES: Final[dict[str, str]] = {
    "soil_health": "Soil Health and Soil Organic Matter",
    "soil_erosion": "Soil Erosion (Wind and Water)",
    "water_quality": "Water Quality (Nutrients, Sediment, Pesticides)",
    "water_quantity": "Water Quantity (Irrigation Efficiency, Drainage)",
    "air_quality": "Air Quality (GHG Emissions, Particulates, Odor)",
    "plant_condition": "Plant Condition (Species Diversity, Productivity)",
    "animals": "Animals (Livestock Management)",
    "energy": "Energy (Efficiency of Energy Use)",
}

# EQIP practice codes mapped to the resource concerns they address.
# Source: NRCS practice standard eligibility tables for Midwest cropland.
_PRACTICE_CONCERN_MAP: Final[dict[str, list[str]]] = {
    "327": ["soil_health", "plant_condition"],      # Conservation Cover
    "328": ["soil_health", "soil_erosion"],          # Conservation Crop Rotation
    "329": ["soil_health", "soil_erosion", "water_quality"],  # No-Till
    "330": ["soil_erosion", "water_quality"],        # Contour Farming
    "340": ["soil_health", "water_quality", "air_quality"],   # Cover Crop
    "380": ["soil_erosion", "air_quality"],          # Windbreak/Shelterbelt Establishment
    "382": ["animals", "water_quality"],             # Fence
    "393": ["water_quality", "soil_erosion"],        # Filter Strip
    "412": ["water_quality", "soil_erosion"],        # Grassed Waterway
    "484": ["water_quantity"],                       # Irrigation Pipeline
    "528": ["plant_condition", "animals"],           # Prescribed Grazing
    "590": ["water_quality"],                        # Nutrient Management
    "600": ["water_quality", "water_quantity"],      # Terrace
    "612": ["soil_erosion", "air_quality", "plant_condition"],  # Tree/Shrub Establishment
    "657": ["energy"],                               # Irrigation System, Micro-Irrigation
    "666": ["water_quantity"],                       # Irrigation Water Management
}

# Stewardship threshold: minimum CART score for a single resource concern to be
# considered "above threshold" (i.e., the farm is addressing it adequately).
# Expressed as a fraction of the concern's maximum possible points.
_STEWARDSHIP_THRESHOLD_FRACTION: Final[float] = 0.50

# State-specific CART ranking thresholds (historical median cut-off scores).
# Farms at or above these scores qualify for the ACT NOW fast-track pathway.
_STATE_RANKING_THRESHOLDS: Final[dict[str, float]] = {
    "IL": 45.0,
    "IN": 43.0,
    "IA": 47.0,
    "KS": 40.0,
    "MI": 42.0,
    "MN": 45.0,
    "MO": 41.0,
    "NE": 42.0,
    "ND": 38.0,
    "OH": 44.0,
    "SD": 39.0,
    "WI": 43.0,
    # Default for states not in table
    "_default": 42.0,
}

# Point contribution per practice per resource concern.
# Each practice earns points for the concerns it addresses, scaled by data quality.
_PRACTICE_BASE_POINTS: Final[dict[str, float]] = {
    "327": 3.0,
    "328": 4.0,
    "329": 5.0,
    "330": 3.0,
    "340": 5.0,
    "380": 2.0,
    "382": 1.5,
    "393": 3.0,
    "412": 3.0,
    "484": 2.0,
    "528": 2.5,
    "590": 4.0,
    "600": 3.0,
    "612": 2.5,
    "657": 2.0,
    "666": 3.0,
}

# Soil organic matter (SOM) bonus multipliers for soil_health scoring.
_SOM_BONUS: Final[dict[str, float]] = {
    "high": 1.5,    # SOM >= 4.0%  (excellent)
    "medium": 1.2,  # SOM 2.5–3.9%
    "low": 1.0,     # SOM 1.5–2.4%
    "poor": 0.7,    # SOM < 1.5%  (degraded)
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_som_tier(organic_matter_pct: float | None) -> str:
    """Return the SOM tier label for a given organic matter percentage.

    Args:
        organic_matter_pct: Soil organic matter as a percentage, or None.

    Returns:
        One of 'high', 'medium', 'low', 'poor'.
    """
    if organic_matter_pct is None:
        return "low"  # Conservative default
    if organic_matter_pct >= 4.0:
        return "high"
    if organic_matter_pct >= 2.5:
        return "medium"
    if organic_matter_pct >= 1.5:
        return "low"
    return "poor"


def _get_ranking_threshold(state: str) -> float:
    """Look up the CART ranking threshold for a state.

    Args:
        state: Two-letter state abbreviation (upper or lower case).

    Returns:
        The minimum CART score for ACT NOW fast-track eligibility.
    """
    return _STATE_RANKING_THRESHOLDS.get(
        state.upper(), _STATE_RANKING_THRESHOLDS["_default"]
    )


def _collect_practices(fields: list[dict]) -> set[str]:
    """Aggregate all unique practice codes across a farm's fields.

    Args:
        fields: List of field dicts containing a 'practices' list.

    Returns:
        Set of practice code strings.
    """
    codes: set[str] = set()
    for field in fields:
        for practice in field.get("practices") or []:
            # Practices may be stored as code strings (e.g. "340") or
            # descriptive strings. Normalise to stripped uppercase.
            codes.add(str(practice).strip().upper())
    return codes


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def calculate_stewardship_score(farm_id: str, supabase) -> dict:
    """Calculate the CART stewardship score for a farm.

    Algorithm:
        1. Fetch farm record to determine state (for ranking threshold).
        2. Fetch all fields and aggregate current practices.
        3. Fetch most-recent soil profile per field for SOM data.
        4. Fetch acted recommendations to include additional practice evidence.
        5. Score each resource concern category based on practices present,
           with SOM bonus applied to soil_health.
        6. Compare total against state ranking threshold.
        7. Return detailed breakdown with gap analysis.

    Args:
        farm_id: UUID of the farm to score.
        supabase: Authenticated Supabase client (respects RLS).

    Returns:
        A dict with keys: farm_id, total_points, max_possible_points,
        state_ranking_threshold, meets_ranking_threshold, gap_to_threshold,
        resource_concern_scores, component_scores, evaluated_at.

    Raises:
        ValueError: If the farm cannot be found.
    """
    # ------------------------------------------------------------------
    # 1. Fetch farm record
    # ------------------------------------------------------------------
    try:
        farm_result = (
            supabase.table("farms")
            .select("id, state, total_acres")
            .eq("id", farm_id)
            .single()
            .execute()
        )
        farm: dict = farm_result.data or {}
    except Exception:
        logger.exception("csp_scoring: failed to fetch farm=%s", farm_id)
        raise ValueError(f"Could not retrieve farm {farm_id}")

    if not farm:
        raise ValueError(f"Farm {farm_id} not found")

    state: str = farm.get("state", "").upper()
    ranking_threshold: float = _get_ranking_threshold(state)

    # ------------------------------------------------------------------
    # 2. Fetch all fields
    # ------------------------------------------------------------------
    try:
        fields_result = (
            supabase.table("fields")
            .select("id, name, acres, crop_type, practices")
            .eq("farm_id", farm_id)
            .execute()
        )
        fields: list[dict] = fields_result.data or []
    except Exception:
        logger.exception("csp_scoring: failed to fetch fields for farm=%s", farm_id)
        fields = []

    field_ids: list[str] = [f["id"] for f in fields]

    # ------------------------------------------------------------------
    # 3. Fetch soil profiles (most recent per field for SOM)
    # ------------------------------------------------------------------
    som_by_field: dict[str, float | None] = {}
    avg_som: float | None = None

    if field_ids:
        try:
            soil_result = (
                supabase.table("soil_profiles")
                .select("field_id, organic_matter_pct")
                .in_("field_id", field_ids)
                .order("fetched_at", desc=True)
                .execute()
            )
            seen_fields: set[str] = set()
            for row in soil_result.data or []:
                fid = row["field_id"]
                if fid not in seen_fields:
                    som_by_field[fid] = row.get("organic_matter_pct")
                    seen_fields.add(fid)
        except Exception:
            logger.exception(
                "csp_scoring: failed to fetch soil profiles for farm=%s", farm_id
            )

    # Compute farm-level average SOM
    som_values = [v for v in som_by_field.values() if v is not None]
    if som_values:
        avg_som = sum(som_values) / len(som_values)

    # ------------------------------------------------------------------
    # 4. Fetch acted recommendations for additional practice evidence
    # ------------------------------------------------------------------
    acted_codes: set[str] = set()
    if field_ids:
        try:
            recs_result = (
                supabase.table("recommendations")
                .select("practice_code")
                .in_("field_id", field_ids)
                .eq("status", "acted")
                .execute()
            )
            for rec in recs_result.data or []:
                code = str(rec.get("practice_code", "")).strip()
                if code:
                    acted_codes.add(code)
        except Exception:
            logger.exception(
                "csp_scoring: failed to fetch acted recs for farm=%s", farm_id
            )

    # ------------------------------------------------------------------
    # 5. Aggregate all practice codes on the farm
    # ------------------------------------------------------------------
    field_practices: set[str] = _collect_practices(fields)
    all_practices: set[str] = field_practices | acted_codes

    # ------------------------------------------------------------------
    # 6. Score each resource concern
    # ------------------------------------------------------------------
    som_tier = _get_som_tier(avg_som)
    som_bonus_multiplier = _SOM_BONUS[som_tier]

    concern_scores: list[dict] = []
    component_scores: dict[str, float] = {}
    total_points: float = 0.0

    for concern_id, max_pts in _MAX_POINTS_PER_CONCERN.items():
        concern_name = _CONCERN_NAMES[concern_id]
        threshold_pts = max_pts * _STEWARDSHIP_THRESHOLD_FRACTION

        # Find all practices on the farm that address this concern
        addressing_practices: list[str] = [
            code
            for code, concerns in _PRACTICE_CONCERN_MAP.items()
            if concern_id in concerns and code in all_practices
        ]

        # Sum raw practice points for this concern
        raw_pts: float = sum(
            _PRACTICE_BASE_POINTS.get(code, 0.0) for code in addressing_practices
        )

        # Apply SOM bonus multiplier to soil_health concern
        if concern_id == "soil_health":
            raw_pts *= som_bonus_multiplier

        # Clamp to maximum for this concern
        earned_pts: float = min(raw_pts, max_pts)
        meets_threshold: bool = earned_pts >= threshold_pts

        concern_scores.append(
            {
                "concern_id": concern_id,
                "name": concern_name,
                "category": concern_id,
                "practices_addressing": addressing_practices,
                "meets_threshold": meets_threshold,
                "points_earned": round(earned_pts, 2),
                "points_possible": max_pts,
            }
        )
        component_scores[concern_id] = round(earned_pts, 2)
        total_points += earned_pts

    total_points = round(total_points, 2)
    meets_ranking_threshold: bool = total_points >= ranking_threshold
    gap: float = max(0.0, round(ranking_threshold - total_points, 2))

    logger.info(
        "csp_scoring: farm=%s state=%s total_pts=%.2f threshold=%.1f meets=%s",
        farm_id,
        state,
        total_points,
        ranking_threshold,
        meets_ranking_threshold,
    )

    return {
        "farm_id": farm_id,
        "total_points": total_points,
        "max_possible_points": _MAX_TOTAL_POINTS,
        "state_ranking_threshold": ranking_threshold,
        "meets_ranking_threshold": meets_ranking_threshold,
        "gap_to_threshold": gap,
        "resource_concern_scores": concern_scores,
        "component_scores": component_scores,
        "avg_som_pct": avg_som,
        "som_tier": som_tier,
        "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
