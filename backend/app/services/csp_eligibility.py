"""
CSP eligibility engine for RegenAI.

Evaluates whether a farm qualifies for the USDA NRCS Conservation Stewardship
Program by checking the two statutory eligibility requirements:

    1. The operation currently meets the stewardship threshold on at least
       2 Priority Resource Concerns (the "existing performance" test).
    2. The producer controls (owns or has written lease for) all land — this
       check is delegated to the NRCS office; we flag based on available data.

All scoring logic is delegated to csp_scoring.calculate_stewardship_score().
This module adds the eligibility gate layer and assembles the final
CSPEligibilityResponse payload, persisting it to the csp_eligibility_assessments table
for cached reads by the router.

Key program facts (FY2024):
    - Need >= 2 priority resource concerns meeting stewardship threshold
    - CART score >= state ranking threshold → ACT NOW fast-track approval
    - Minimum stewardship threshold = 50% of max points for that concern
"""

import logging
from datetime import datetime, timezone

from app.services.csp_scoring import (
    calculate_stewardship_score,
    _CONCERN_NAMES,
    _STEWARDSHIP_THRESHOLD_FRACTION,
    _MAX_POINTS_PER_CONCERN,
)

logger = logging.getLogger(__name__)

# Minimum number of priority resource concerns that must meet the stewardship
# threshold for a farm to be CSP-eligible (statutory requirement).
_MIN_CONCERNS_MEETING_THRESHOLD: int = 2

# Enhancement activities most likely to close a stewardship gap, mapped by
# the resource concern they primarily address. Codes match the NRCS master
# reference table in csp_enhancement_activities.
_GAP_CLOSURE_ENHANCEMENTS: dict[str, list[str]] = {
    "soil_health": ["E328A", "E340A", "E590A"],
    "soil_erosion": ["E330A", "E380A", "E412A"],
    "water_quality": ["E590A", "E393A", "E329A"],
    "water_quantity": ["E484A", "E666A"],
    "air_quality": ["E340A", "E380A"],
    "plant_condition": ["E327A", "E528A"],
    "animals": ["E528A", "E382A"],
    "energy": ["E657A", "E666A"],
}


async def evaluate_csp_eligibility(farm_id: str, supabase) -> dict:
    """Evaluate full CSP eligibility for a farm.

    Algorithm:
        1. Run the CART stewardship scoring engine.
        2. Count how many resource concerns meet the stewardship threshold.
        3. Determine overall eligibility status:
               - act_now:       CART score >= state threshold AND >= 2 concerns met
               - eligible:      >= 2 concerns met (below ranking threshold)
               - pending_review: 1 concern met (close to eligible)
               - not_eligible:  0 concerns meeting threshold
        4. Identify recommended enhancements to close any gap.
        5. Persist the assessment to csp_eligibility_assessments table.
        6. Return the full eligibility response dict.

    Args:
        farm_id: UUID of the farm to evaluate.
        supabase: Authenticated Supabase client (respects RLS).

    Returns:
        A dict conforming to CSPEligibilityResponse schema fields.

    Raises:
        ValueError: If the farm cannot be found or has no accessible fields.
    """
    # ------------------------------------------------------------------
    # 1. Run stewardship scoring
    # ------------------------------------------------------------------
    score_data = await calculate_stewardship_score(farm_id, supabase)

    # ------------------------------------------------------------------
    # 2. Count resource concerns meeting the stewardship threshold
    # ------------------------------------------------------------------
    resource_concerns = score_data["resource_concern_scores"]
    concerns_meeting: int = sum(
        1 for c in resource_concerns if c["meets_threshold"]
    )

    cart_score: float = score_data["total_points"]
    ranking_threshold: float = score_data["state_ranking_threshold"]
    meets_ranking_threshold: bool = score_data["meets_ranking_threshold"]

    # ------------------------------------------------------------------
    # 3. Determine eligibility status
    # ------------------------------------------------------------------
    if concerns_meeting >= _MIN_CONCERNS_MEETING_THRESHOLD and meets_ranking_threshold:
        status = "act_now"
        is_eligible = True
        notes = (
            f"Farm qualifies for CSP ACT NOW fast-track approval. "
            f"CART score {cart_score:.1f} meets the {score_data['state_ranking_threshold']:.1f}-point "
            f"state ranking threshold with {concerns_meeting} priority resource concern(s) "
            f"above the stewardship threshold."
        )
    elif concerns_meeting >= _MIN_CONCERNS_MEETING_THRESHOLD:
        status = "eligible"
        is_eligible = True
        gap = score_data["gap_to_threshold"]
        notes = (
            f"Farm meets the minimum CSP eligibility requirements: "
            f"{concerns_meeting} priority resource concern(s) are above the stewardship "
            f"threshold. CART score {cart_score:.1f} is {gap:.1f} points below the "
            f"{ranking_threshold:.1f}-point state ranking threshold. Adopting additional "
            f"enhancements may qualify the farm for the ACT NOW pathway."
        )
    elif concerns_meeting == 1:
        status = "pending_review"
        is_eligible = False
        notes = (
            f"Farm currently meets the stewardship threshold on 1 priority resource "
            f"concern. CSP requires a minimum of {_MIN_CONCERNS_MEETING_THRESHOLD}. "
            f"Adopting practices that address a second resource concern will establish "
            f"eligibility. Discuss with your local NRCS office."
        )
    else:
        status = "not_eligible"
        is_eligible = False
        notes = (
            f"Farm does not yet meet the CSP stewardship threshold on any priority "
            f"resource concern. CART score is {cart_score:.1f} out of "
            f"{score_data['max_possible_points']:.1f} possible points. "
            f"Begin implementing conservation practices and contact your local NRCS "
            f"office to identify the highest-priority improvement areas."
        )

    # ------------------------------------------------------------------
    # 4. Identify recommended enhancements to close gaps
    # ------------------------------------------------------------------
    recommended_enhancements: list[str] = []
    for concern in resource_concerns:
        if not concern["meets_threshold"]:
            cid = concern["concern_id"]
            enhancements = _GAP_CLOSURE_ENHANCEMENTS.get(cid, [])
            for enh in enhancements:
                if enh not in recommended_enhancements:
                    recommended_enhancements.append(enh)
            if len(recommended_enhancements) >= 6:
                break

    # ------------------------------------------------------------------
    # 5. Persist assessment to csp_eligibility_assessments table
    # ------------------------------------------------------------------
    now = datetime.now(tz=timezone.utc).isoformat()
    assessment_payload = {
        "farm_id": farm_id,
        "status": status,
        "is_eligible": is_eligible,
        "concerns_meeting_threshold": concerns_meeting,
        "cart_score": cart_score,
        "state_ranking_threshold": ranking_threshold,
        "meets_ranking_threshold": meets_ranking_threshold,
        "eligibility_notes": notes,
        "recommended_enhancements": recommended_enhancements,
        "score_breakdown": score_data,
        "evaluated_at": now,
    }

    try:
        supabase.table("csp_eligibility_assessments").upsert(
            assessment_payload, on_conflict="farm_id"
        ).execute()
    except Exception:
        logger.exception(
            "csp_eligibility: failed to persist assessment for farm=%s", farm_id
        )
        # Non-fatal — we still return the computed result

    logger.info(
        "csp_eligibility: farm=%s status=%s cart=%.1f concerns_met=%d",
        farm_id,
        status,
        cart_score,
        concerns_meeting,
    )

    return {
        "farm_id": farm_id,
        "status": status,
        "is_eligible": is_eligible,
        "resource_concerns_meeting_threshold": concerns_meeting,
        "resource_concerns_detail": resource_concerns,
        "cart_score": cart_score,
        "state_ranking_threshold": ranking_threshold,
        "meets_ranking_threshold": meets_ranking_threshold,
        "eligibility_notes": notes,
        "recommended_enhancements": recommended_enhancements,
        "evaluated_at": now,
    }
