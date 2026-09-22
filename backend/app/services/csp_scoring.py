"""
CSP stewardship score calculator for RegenAI.

Approximates the USDA NRCS Conservation Assessment Ranking Tool (CART) for
row-crop operations. The farm is scored on the eight Priority Resource
Concern categories and, where RegenAI holds an estimated ranking threshold
for the farm's state, the total is compared with it. Meeting that threshold
means the farm *may* be considered for the CSP "ACT NOW" fast-track, which
states use at their discretion — it is never a guarantee (see
``program_rules.CSP_ACT_NOW_NOTE``).

Most states have no threshold on file. For those, ``state_ranking_threshold``,
``meets_ranking_threshold`` and ``gap_to_threshold`` are all None; the
``scoring_rules.state_ranking_threshold`` block says ``not_published``.

Every weight, threshold and practice mapping comes from
``app.services.program_rules``. Most are RegenAI estimates with no primary
source, so responses carry ``is_estimate`` and a ``scoring_rules`` citation.
"""

import logging
from datetime import datetime, timezone
from typing import Final

from postgrest.exceptions import APIError

from app.services.program_rules import (
    CSP_CART_MAX_POINTS_PER_CONCERN,
    CSP_PRACTICE_CATALOG,
    CSP_SOM_DEFAULT_TIER,
    CSP_SOM_MULTIPLIERS,
    CSP_SOM_POOR_TIER,
    CSP_SOM_TIER_MIN_PCT,
    CSP_STATE_RANKING_THRESHOLDS,
    CSP_STEWARDSHIP_THRESHOLD_FRACTION,
    csp_scoring_rules_metadata,
)

logger = logging.getLogger(__name__)

_MAX_TOTAL_POINTS: Final[float] = sum(CSP_CART_MAX_POINTS_PER_CONCERN.values())

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    """Current UTC time (isolated so tests can pin the date)."""
    return datetime.now(tz=timezone.utc)


def _get_som_tier(organic_matter_pct: float | None) -> str:
    """Return the SOM tier label for a given organic matter percentage.

    Args:
        organic_matter_pct: Soil organic matter as a percentage, or None.

    Returns:
        One of 'high', 'medium', 'low', 'poor'.
    """
    if organic_matter_pct is None:
        return CSP_SOM_DEFAULT_TIER
    for tier, min_pct in CSP_SOM_TIER_MIN_PCT.items():
        if organic_matter_pct >= min_pct:
            return tier
    return CSP_SOM_POOR_TIER


def _get_ranking_threshold(state: str) -> float | None:
    """Look up the (estimated) CART ranking threshold for a state.

    Args:
        state: Two-letter state abbreviation (upper or lower case).

    Returns:
        The state's ranking threshold, or None when RegenAI holds none for
        that state. There is deliberately no fallback value: NRCS state
        offices set ranking cut-offs and do not publish them in advance, so an
        invented default would be shown to farmers as if it were a real
        cut-off.
    """
    return CSP_STATE_RANKING_THRESHOLDS.get(state.upper())


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
    """Calculate the estimated CART stewardship score for a farm.

    Algorithm:
        1. Fetch farm record to determine state (for the ranking threshold,
           which may be unknown).
        2. Fetch all fields and aggregate current practices.
        3. Fetch most-recent soil profile per field for SOM data.
        4. Fetch acted recommendations to include additional practice evidence.
        5. Score each resource concern category based on practices present,
           with SOM multiplier applied to soil_health.
        6. Compare total against the state ranking threshold when one exists.
        7. Return detailed breakdown with gap analysis.

    Args:
        farm_id: UUID string of the farm to score.
        supabase: Authenticated Supabase client (respects RLS).

    Returns:
        A dict with keys: farm_id, total_points, max_possible_points,
        state_ranking_threshold, meets_ranking_threshold, gap_to_threshold,
        resource_concern_scores, component_scores, avg_som_pct, som_tier,
        is_estimate, scoring_rules, evaluated_at.

    Raises:
        ValueError: If the farm cannot be found.
        APIError: If the fields query fails (no fields means no score).
    """
    # 1. Farm
    try:
        farm_result = (
            supabase.table("farms")
            .select("id, state, total_acres")
            .eq("id", farm_id)
            .single()
            .execute()
        )
    except APIError as exc:
        # .single() raises when zero rows match (missing or hidden by RLS).
        logger.warning("csp_scoring: farm lookup failed farm=%s error=%s", farm_id, exc)
        raise ValueError(f"Could not retrieve farm {farm_id}") from exc

    farm: dict = farm_result.data or {}
    if not farm:
        raise ValueError(f"Farm {farm_id} not found")

    state: str = (farm.get("state") or "").upper()
    ranking_threshold: float | None = _get_ranking_threshold(state)

    # 2. Fields — required; a failure here propagates rather than scoring zero.
    fields_result = (
        supabase.table("fields")
        .select("id, name, acres, crop_type, practices")
        .eq("farm_id", farm_id)
        .execute()
    )
    fields: list[dict] = fields_result.data or []
    field_ids: list[str] = [f["id"] for f in fields]

    # 3. Soil profiles (most recent per field). Optional evidence: on failure
    #    the conservative default SOM tier is used.
    som_by_field: dict[str, float | None] = {}
    if field_ids:
        try:
            soil_result = (
                supabase.table("soil_profiles")
                .select("field_id, organic_matter_pct")
                .in_("field_id", field_ids)
                .order("fetched_at", desc=True)
                .execute()
            )
            for row in soil_result.data or []:
                som_by_field.setdefault(row["field_id"], row.get("organic_matter_pct"))
        except APIError as exc:
            logger.warning(
                "csp_scoring: soil profiles unavailable farm=%s error=%s", farm_id, exc
            )

    som_values = [v for v in som_by_field.values() if v is not None]
    avg_som: float | None = sum(som_values) / len(som_values) if som_values else None

    # 4. Acted recommendations. Optional evidence: on failure only field
    #    practices are scored.
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
                code = str(rec.get("practice_code") or "").strip()
                if code:
                    acted_codes.add(code)
        except APIError as exc:
            logger.warning(
                "csp_scoring: acted recommendations unavailable farm=%s error=%s",
                farm_id,
                exc,
            )

    # 5. Aggregate all practice codes on the farm
    all_practices: set[str] = _collect_practices(fields) | acted_codes

    # 6. Score each resource concern
    som_tier = _get_som_tier(avg_som)
    som_multiplier = CSP_SOM_MULTIPLIERS[som_tier]

    concern_scores: list[dict] = []
    component_scores: dict[str, float] = {}
    total_points: float = 0.0

    for concern_id, max_pts in CSP_CART_MAX_POINTS_PER_CONCERN.items():
        threshold_pts = max_pts * CSP_STEWARDSHIP_THRESHOLD_FRACTION

        addressing_practices: list[str] = [
            code
            for code, practice in CSP_PRACTICE_CATALOG.items()
            if concern_id in practice.resource_concerns and code in all_practices
        ]
        raw_pts: float = sum(
            CSP_PRACTICE_CATALOG[code].base_points for code in addressing_practices
        )
        if concern_id == "soil_health":
            raw_pts *= som_multiplier

        earned_pts: float = min(raw_pts, max_pts)
        concern_scores.append(
            {
                "concern_id": concern_id,
                "name": _CONCERN_NAMES[concern_id],
                "category": concern_id,
                "practices_addressing": addressing_practices,
                "meets_threshold": earned_pts >= threshold_pts,
                "points_earned": round(earned_pts, 2),
                "points_possible": max_pts,
            }
        )
        component_scores[concern_id] = round(earned_pts, 2)
        total_points += earned_pts

    total_points = round(total_points, 2)

    # An unknown threshold stays unknown: None, never False and never a gap of
    # zero, so no caller can read "meets the cut-off" out of missing data.
    meets_ranking_threshold: bool | None = (
        None if ranking_threshold is None else total_points >= ranking_threshold
    )
    gap: float | None = (
        None
        if ranking_threshold is None
        else max(0.0, round(ranking_threshold - total_points, 2))
    )

    logger.info(
        "csp_scoring: farm=%s state=%s total_pts=%.2f threshold=%s meets=%s",
        farm_id,
        state,
        total_points,
        ranking_threshold,
        meets_ranking_threshold,
    )

    scoring_rules = csp_scoring_rules_metadata(state)
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
        "is_estimate": scoring_rules["is_estimate"],
        "scoring_rules": scoring_rules,
        "evaluated_at": _utcnow().isoformat(),
    }
