"""
CSP eligibility engine for RegenAI.

Evaluates whether a farm qualifies for the USDA NRCS Conservation Stewardship
Program by checking the two statutory eligibility requirements:

    1. The operation currently meets the stewardship threshold on at least
       2 Priority Resource Concerns (the "existing performance" test).
    2. The producer controls (owns or has written lease for) all land — this
       check is delegated to the NRCS office; we flag based on available data.

All scoring logic is delegated to csp_scoring.calculate_stewardship_score().
This module adds the eligibility gate layer, assembles the
CSPEligibilityResponse payload, and upserts it to csp_eligibility_assessments
on every evaluation (including GET /csp/eligibility). The persisted row is
read by the payment estimator and the AI farm context; the API itself always
recomputes rather than serving the stored row.

Key program facts:
    - Need >= 2 priority resource concerns meeting stewardship threshold
      (``program_rules.CSP_MIN_PRIORITY_CONCERNS``)
    - CART score >= state ranking threshold → the farm MAY qualify for the
      ACT NOW fast-track if the state offers it (state discretion; not a
      guarantee)
    - Most states have no ranking threshold on file. Those farms are never
      ``act_now``: the threshold and ``meets_ranking_threshold`` are None and
      the notes say the state's cut-off is not published.
    - The per-concern stewardship threshold and the state ranking thresholds
      RegenAI does hold are estimates
      (see ``program_rules.CSP_SCORING_ESTIMATED_RULES``)
    - FY2026: selection of eight priority resource concerns still applies
      (NRCS NB 440-26-2)
"""

import logging
from datetime import datetime, timezone
from typing import Final

from postgrest.exceptions import APIError

from app.services.csp_scoring import calculate_stewardship_score
from app.services.program_rules import (
    CSP_ACT_NOW_NOTE,
    CSP_ADDITIONAL_CONCERNS_REQUIRED,
    CSP_CONTRACT_YEARS,
    CSP_GAP_CLOSURE_ACTIVITIES,
    CSP_MIN_PRIORITY_CONCERNS,
    federal_fiscal_year,
)

logger = logging.getLogger(__name__)

#: Table holding one persisted assessment per (farm_id, fiscal_year).
ASSESSMENTS_TABLE: str = "csp_eligibility_assessments"

#: Conflict target for the upsert — must match UNIQUE(farm_id, fiscal_year).
ASSESSMENT_CONFLICT_TARGET: str = "farm_id,fiscal_year"

#: Every eligibility_status value this service can write. The DB CHECK
#: constraint (supabase/migrations/20260913000008_fix_write_paths.sql) must
#: allow all of these; tests/test_schema_drift.py keeps them in sync.
ELIGIBILITY_STATUSES: tuple[str, ...] = (
    "act_now",
    "eligible",
    "pending_review",
    "not_eligible",
)

# Minimum number of priority resource concerns that must meet the stewardship
# threshold for a farm to be CSP-eligible (statutory requirement).
_MIN_CONCERNS_MEETING_THRESHOLD: Final[int] = int(CSP_MIN_PRIORITY_CONCERNS.value or 0)

# Keep the recommendation list short enough for a farmer to act on.
_MAX_RECOMMENDED_ACTIVITIES: Final[int] = 6


def _utcnow() -> datetime:
    """Current UTC time (isolated so tests can pin the date)."""
    return datetime.now(tz=timezone.utc)


def fetch_latest_assessment(supabase, farm_id: str, columns: str) -> dict | None:
    """Return the most recent persisted assessment row for a farm, or None.

    Rows are keyed by (farm_id, fiscal_year), so a farm can have several.
    The latest fiscal year wins, then the latest ``evaluated_at``. Uses
    ``limit(1)`` rather than ``.single()`` so multiple fiscal-year rows or
    zero rows do not raise.

    Exceptions from the query propagate to the caller.
    """
    result = (
        supabase.table(ASSESSMENTS_TABLE)
        .select(columns)
        .eq("farm_id", farm_id)
        .order("fiscal_year", desc=True)
        .order("evaluated_at", desc=True)
        .limit(1)
        .execute()
    )
    data = result.data
    if isinstance(data, list):
        return data[0] if data else None
    return data or None


def _eligible_notes(
    *,
    concerns_meeting: int,
    cart_score: float,
    ranking_threshold: float | None,
    gap_to_threshold: float | None,
) -> str:
    """Plain-language note for a farm that is eligible but not ACT NOW.

    When RegenAI has no ranking threshold for the state, the note says so
    rather than comparing the score with a number we do not have.
    """
    opening = (
        f"Farm meets the minimum CSP eligibility requirements: {concerns_meeting} "
        f"priority resource concern(s) are above the stewardship threshold."
    )
    if ranking_threshold is None or gap_to_threshold is None:
        return (
            f"{opening} Your state's CSP ranking threshold is not published, so "
            f"RegenAI cannot tell you whether a CART score of {cart_score:.1f} would "
            f"rank high enough for funding. NRCS ranks and selects applications; ask "
            f"your local NRCS office where this score stands."
        )
    return (
        f"{opening} CART score {cart_score:.1f} is {gap_to_threshold:.1f} points below "
        f"the {ranking_threshold:.1f}-point state ranking threshold. Adopting additional "
        f"conservation activities could raise the score enough to be considered for "
        f"ACT NOW, if your state offers it."
    )


def _recommend_gap_closure(resource_concerns: list[dict]) -> list[str]:
    """Return up to ``_MAX_RECOMMENDED_ACTIVITIES`` activity codes for unmet concerns."""
    recommended: list[str] = []
    for concern in resource_concerns:
        if concern["meets_threshold"]:
            continue
        for code in CSP_GAP_CLOSURE_ACTIVITIES.get(concern["concern_id"], ()):
            if code not in recommended:
                recommended.append(code)
    return recommended[:_MAX_RECOMMENDED_ACTIVITIES]


async def evaluate_csp_eligibility(farm_id: str, supabase) -> dict:
    """Evaluate full CSP eligibility for a farm.

    Algorithm:
        1. Run the CART stewardship scoring engine.
        2. Count how many resource concerns meet the stewardship threshold.
        3. Determine overall eligibility status:
               - act_now:       CART score >= a known state threshold AND the
                                minimum number of concerns met (may qualify for
                                ACT NOW if the state offers it)
               - eligible:      minimum concerns met, but below the ranking
                                threshold or the state has no published one
               - pending_review: at least one, but fewer than the minimum
               - not_eligible:  0 concerns meeting threshold
        4. Identify recommended activities to close any gap.
        5. Upsert the assessment to csp_eligibility_assessments.
        6. Return the full eligibility response dict.

    Args:
        farm_id: UUID string of the farm to evaluate.
        supabase: Authenticated Supabase client (respects RLS).

    Returns:
        A dict conforming to CSPEligibilityResponse schema fields.

    Raises:
        ValueError: If the farm cannot be found.
    """
    # 1. Run stewardship scoring
    score_data = await calculate_stewardship_score(farm_id, supabase)

    # 2. Count resource concerns meeting the stewardship threshold
    resource_concerns = score_data["resource_concern_scores"]
    concerns_meeting: int = sum(1 for c in resource_concerns if c["meets_threshold"])

    cart_score: float = score_data["total_points"]
    # Both are None when RegenAI holds no ranking threshold for the farm's
    # state. Unknown is never treated as "missed": ACT NOW is only ever
    # claimed against a threshold we actually hold.
    ranking_threshold: float | None = score_data["state_ranking_threshold"]
    meets_ranking_threshold: bool | None = score_data["meets_ranking_threshold"]

    # 3. Determine eligibility status
    if concerns_meeting >= _MIN_CONCERNS_MEETING_THRESHOLD and meets_ranking_threshold:
        status = "act_now"
        is_eligible = True
        notes = (
            f"Farm meets CSP eligibility requirements and may qualify for the "
            f"ACT NOW fast-track if your state offers it. CART score {cart_score:.1f} "
            f"meets the {ranking_threshold:.1f}-point "
            f"state ranking threshold with {concerns_meeting} priority resource concern(s) "
            f"above the stewardship threshold. {CSP_ACT_NOW_NOTE}"
        )
    elif concerns_meeting >= _MIN_CONCERNS_MEETING_THRESHOLD:
        status = "eligible"
        is_eligible = True
        notes = _eligible_notes(
            concerns_meeting=concerns_meeting,
            cart_score=cart_score,
            ranking_threshold=ranking_threshold,
            gap_to_threshold=score_data["gap_to_threshold"],
        )
    elif concerns_meeting > 0:
        # Some but not enough concerns: compare against the rule value rather
        # than a literal 1, so a change to the minimum keeps this status honest.
        status = "pending_review"
        is_eligible = False
        concerns_short = _MIN_CONCERNS_MEETING_THRESHOLD - concerns_meeting
        notes = (
            f"Farm currently meets the stewardship threshold on {concerns_meeting} "
            f"priority resource concern(s). CSP requires a minimum of "
            f"{_MIN_CONCERNS_MEETING_THRESHOLD}. Adopting practices that address "
            f"{concerns_short} more resource concern(s) will establish eligibility. "
            f"Discuss with your local NRCS office."
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

    # 4. Recommended activities to close gaps
    recommended_enhancements = _recommend_gap_closure(resource_concerns)

    # 5. Persist assessment
    evaluated = _utcnow()
    now = evaluated.isoformat()
    fiscal_year = federal_fiscal_year(evaluated)
    assessment_payload = {
        "farm_id": farm_id,
        "fiscal_year": fiscal_year,
        "eligibility_status": status,
        "is_eligible": is_eligible,
        "rc_count_above_threshold": concerns_meeting,
        # INTEGER column; round rather than truncate (46.9 -> 47).
        "stewardship_score": round(cart_score),
        # NOT NULL BOOLEAN column: an unknown threshold is stored as false
        # because we cannot claim the farm meets it. The nullable value stays
        # in resource_concerns_met (the full score payload), which is what the
        # AI context reads so an unknown is never rendered as "no".
        "act_now_eligible": meets_ranking_threshold is True,
        "notes": notes,
        "active_enhancement_codes": recommended_enhancements,
        "resource_concerns_met": score_data,
        "evaluated_at": now,
    }

    try:
        supabase.table(ASSESSMENTS_TABLE).upsert(
            assessment_payload, on_conflict=ASSESSMENT_CONFLICT_TARGET
        ).execute()
    except APIError as exc:
        # Non-fatal — the computed result is still returned, but log loudly so
        # a schema/RLS mismatch is visible rather than silently dropping data.
        logger.error(
            "csp_eligibility: failed to persist assessment for farm=%s "
            "fiscal_year=%s status=%s: %s",
            farm_id,
            fiscal_year,
            status,
            exc,
        )

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
        "min_concerns_required": _MIN_CONCERNS_MEETING_THRESHOLD,
        "additional_concerns_required": int(CSP_ADDITIONAL_CONCERNS_REQUIRED.value or 0),
        "contract_years": int(CSP_CONTRACT_YEARS.value or 0),
        "resource_concerns_detail": resource_concerns,
        "cart_score": cart_score,
        "state_ranking_threshold": ranking_threshold,
        "meets_ranking_threshold": meets_ranking_threshold,
        "eligibility_notes": notes,
        "recommended_enhancements": recommended_enhancements,
        "is_estimate": score_data["is_estimate"],
        "scoring_rules": score_data["scoring_rules"],
        "evaluated_at": now,
    }
