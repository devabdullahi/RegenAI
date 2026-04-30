"""
CSP Navigator router for RegenAI.

Exposes endpoints for USDA NRCS Conservation Stewardship Program (CSP)
eligibility assessment, stewardship scoring, payment estimation, and
enhancement activity recommendations.

All endpoints require a valid Supabase JWT (Bearer token). Row Level Security
policies are enforced through the authenticated Supabase client, so users can
only access data for farms they own.

CSP program summary:
    - 5-year contracts paying for existing conservation AND new enhancements
    - Minimum $4,000 / maximum $50,000 per year; $200,000 over contract
    - Eligibility: stewardship threshold on >= 2 priority resource concerns
    - CART score >= state ranking threshold → ACT NOW fast-track approval
"""

import logging
import re
from datetime import date, timezone, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from postgrest.exceptions import APIError

from app.auth.middleware import get_authenticated_client, get_current_user
from app.main import limiter
from app.services.csp_eligibility import evaluate_csp_eligibility
from app.services.csp_payment import estimate_csp_payments, get_recommended_enhancements
from app.services.csp_scoring import calculate_stewardship_score

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/csp", tags=["CSP Navigator"])


# ---------------------------------------------------------------------------
# Application deadlines by state (quarterly batching schedule, FY2025)
# ---------------------------------------------------------------------------

_CSP_DEADLINES: dict[str, list[dict]] = {
    "IL": [
        {"cutoff_date": "2025-05-15", "signup_period": "Spring 2025", "notes": "Continuous signup; NRCS batches applications quarterly."},
        {"cutoff_date": "2025-08-15", "signup_period": "Summer 2025", "notes": "Continuous signup; NRCS batches applications quarterly."},
        {"cutoff_date": "2025-11-14", "signup_period": "Fall 2025",   "notes": "Continuous signup; NRCS batches applications quarterly."},
    ],
    "IN": [
        {"cutoff_date": "2025-05-15", "signup_period": "Spring 2025", "notes": "Continuous signup; check with local NRCS office."},
        {"cutoff_date": "2025-08-15", "signup_period": "Summer 2025", "notes": "Continuous signup; check with local NRCS office."},
        {"cutoff_date": "2025-11-14", "signup_period": "Fall 2025",   "notes": "Continuous signup; check with local NRCS office."},
    ],
    "IA": [
        {"cutoff_date": "2025-05-15", "signup_period": "Spring 2025", "notes": "Iowa NRCS batches quarterly; highest-scoring applications funded first."},
        {"cutoff_date": "2025-08-15", "signup_period": "Summer 2025", "notes": "Iowa NRCS batches quarterly."},
        {"cutoff_date": "2025-11-14", "signup_period": "Fall 2025",   "notes": "Iowa NRCS batches quarterly."},
    ],
    "KS": [
        {"cutoff_date": "2025-05-15", "signup_period": "Spring 2025", "notes": "Contact Kansas NRCS state office for county-specific ranking dates."},
        {"cutoff_date": "2025-08-15", "signup_period": "Summer 2025", "notes": "Contact Kansas NRCS state office."},
        {"cutoff_date": "2025-11-14", "signup_period": "Fall 2025",   "notes": "Contact Kansas NRCS state office."},
    ],
    "MN": [
        {"cutoff_date": "2025-05-15", "signup_period": "Spring 2025", "notes": "Minnesota prioritizes operations with SWCD partnership plans."},
        {"cutoff_date": "2025-08-15", "signup_period": "Summer 2025", "notes": "Minnesota NRCS state office."},
        {"cutoff_date": "2025-11-14", "signup_period": "Fall 2025",   "notes": "Minnesota NRCS state office."},
    ],
    "MO": [
        {"cutoff_date": "2025-05-15", "signup_period": "Spring 2025", "notes": "Missouri NRCS prioritizes water quality resource concerns in applicable watersheds."},
        {"cutoff_date": "2025-08-15", "signup_period": "Summer 2025", "notes": "Missouri NRCS."},
        {"cutoff_date": "2025-11-14", "signup_period": "Fall 2025",   "notes": "Missouri NRCS."},
    ],
    "NE": [
        {"cutoff_date": "2025-05-15", "signup_period": "Spring 2025", "notes": "Nebraska often has competitive ranking pools; apply early."},
        {"cutoff_date": "2025-08-15", "signup_period": "Summer 2025", "notes": "Nebraska NRCS."},
        {"cutoff_date": "2025-11-14", "signup_period": "Fall 2025",   "notes": "Nebraska NRCS."},
    ],
    "OH": [
        {"cutoff_date": "2025-05-15", "signup_period": "Spring 2025", "notes": "Ohio NRCS; H2Ohio watershed farms may receive ranking preference."},
        {"cutoff_date": "2025-08-15", "signup_period": "Summer 2025", "notes": "Ohio NRCS."},
        {"cutoff_date": "2025-11-14", "signup_period": "Fall 2025",   "notes": "Ohio NRCS."},
    ],
    "WI": [
        {"cutoff_date": "2025-05-15", "signup_period": "Spring 2025", "notes": "Wisconsin NRCS; dairy operations may qualify for additional enhancements."},
        {"cutoff_date": "2025-08-15", "signup_period": "Summer 2025", "notes": "Wisconsin NRCS."},
        {"cutoff_date": "2025-11-14", "signup_period": "Fall 2025",   "notes": "Wisconsin NRCS."},
    ],
}

_DEFAULT_DEADLINES: list[dict] = [
    {"cutoff_date": "2025-05-15", "signup_period": "Spring 2025", "notes": "Continuous signup; contact your local NRCS service center for state-specific ranking dates."},
    {"cutoff_date": "2025-08-15", "signup_period": "Summer 2025", "notes": "Continuous signup; contact your local NRCS service center."},
    {"cutoff_date": "2025-11-14", "signup_period": "Fall 2025",   "notes": "Continuous signup; contact your local NRCS service center."},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _assert_farm_access(farm_id: UUID, supabase) -> None:
    """Raise HTTP 404 if the farm does not exist or the user cannot access it.

    Because the Supabase client carries the user's JWT, RLS silently filters
    rows the user does not own — a missing row therefore signals either
    non-existence or an access denial.
    """
    try:
        supabase.table("farms").select("id").eq("id", str(farm_id)).single().execute()
    except APIError:
        raise HTTPException(status_code=404, detail="Farm not found")


# ---------------------------------------------------------------------------
# GET /csp/eligibility
# ---------------------------------------------------------------------------

@router.get("/eligibility")
async def get_csp_eligibility(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Run a full CSP eligibility assessment for a farm.

    Evaluates whether the operation currently meets the NRCS stewardship
    threshold on at least 2 priority resource concerns (the statutory
    eligibility requirement), and whether the CART score qualifies for the
    ACT NOW fast-track approval pathway.

    Returns a structured eligibility result including per-resource-concern
    detail, recommended gap-closure enhancements, and plain-language
    eligibility notes.

    Args:
        farm_id: UUID of the farm to assess.

    Returns:
        Full CSPEligibilityResponse dict.

    Raises:
        HTTPException 404: Farm not found.
        HTTPException 500: Internal evaluation error.
    """
    await _assert_farm_access(farm_id, supabase)

    try:
        result = await evaluate_csp_eligibility(farm_id, supabase)
    except ValueError as exc:
        logger.warning("csp/eligibility: evaluation failed farm=%s: %s", farm_id, exc)
        raise HTTPException(status_code=400, detail="Invalid farm data. Please verify your farm is set up correctly.")
    except Exception:
        logger.exception("csp/eligibility: unexpected error for farm=%s", farm_id)
        raise HTTPException(
            status_code=500,
            detail="CSP eligibility evaluation failed. Please try again.",
        )

    return result


# ---------------------------------------------------------------------------
# GET /csp/score
# ---------------------------------------------------------------------------

@router.get("/score")
async def get_csp_score(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Return the CART stewardship score breakdown for a farm.

    Scores the farm across all eight NRCS priority resource concern categories
    using available field practices, soil organic matter data, and acted
    recommendations. Includes the state-specific ranking threshold and a
    gap analysis showing how many points are needed to reach the threshold.

    Args:
        farm_id: UUID of the farm to score.

    Returns:
        CSPScoreBreakdown dict with per-concern scores and gap analysis.

    Raises:
        HTTPException 404: Farm not found.
        HTTPException 500: Scoring error.
    """
    await _assert_farm_access(farm_id, supabase)

    try:
        result = await calculate_stewardship_score(farm_id, supabase)
    except ValueError as exc:
        logger.warning("csp/score: scoring failed farm=%s: %s", farm_id, exc)
        raise HTTPException(status_code=400, detail="Invalid farm data. Please verify your farm is set up correctly.")
    except Exception:
        logger.exception("csp/score: unexpected error for farm=%s", farm_id)
        raise HTTPException(
            status_code=500,
            detail="CSP score calculation failed. Please try again.",
        )

    return result


# ---------------------------------------------------------------------------
# GET /csp/payments
# ---------------------------------------------------------------------------

@router.get("/payments")
async def get_csp_payments(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Estimate annual and 5-year CSP payments for a farm.

    Calculates the Existing Activity Payment (EAP) using the FY2024 per-acre
    rate for the farm's state multiplied by the number of resource concerns
    addressed above threshold, plus the Enhancement Activity Payment (EnAP)
    at 100% of practice cost (115% for qualifying bundles of 3+ enhancements).

    Applies NRCS payment caps: $4,000 minimum, $50,000 annual maximum,
    $200,000 over the 5-year contract.

    Args:
        farm_id: UUID of the farm to estimate payments for.

    Returns:
        CSPPaymentEstimate dict with EAP, EnAP, total annual, and 5-year totals,
        including a per-field payment breakdown.

    Raises:
        HTTPException 404: Farm not found.
        HTTPException 500: Estimation error.
    """
    await _assert_farm_access(farm_id, supabase)

    try:
        result = await estimate_csp_payments(farm_id, supabase)
    except ValueError as exc:
        logger.warning("csp/payments: estimation failed farm=%s: %s", farm_id, exc)
        raise HTTPException(status_code=400, detail="Invalid farm data. Please verify your farm is set up correctly.")
    except Exception:
        logger.exception("csp/payments: unexpected error for farm=%s", farm_id)
        raise HTTPException(
            status_code=500,
            detail="CSP payment estimation failed. Please try again.",
        )

    return result


# ---------------------------------------------------------------------------
# GET /csp/enhancements
# ---------------------------------------------------------------------------

@router.get("/enhancements")
async def get_csp_enhancements(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Return ranked enhancement activity recommendations for a farm.

    Fetches the CSP enhancement activity reference table, scores each activity
    against the farm's current stewardship gaps, and returns them sorted by
    impact priority. Activities that close below-threshold resource concern
    gaps are ranked highest.

    Includes estimated annual payment for each enhancement based on per-acre
    cost × farm total acres, and flags activities eligible for the 115%
    bundle premium.

    Args:
        farm_id: UUID of the farm.

    Returns:
        List of CSPEnhancementActivity dicts sorted by priority score.

    Raises:
        HTTPException 404: Farm not found.
        HTTPException 500: Recommendation error.
    """
    await _assert_farm_access(farm_id, supabase)

    try:
        result = await get_recommended_enhancements(farm_id, supabase)
    except ValueError as exc:
        logger.warning("csp/enhancements: failed farm=%s: %s", farm_id, exc)
        raise HTTPException(status_code=400, detail="Invalid farm data. Please verify your farm is set up correctly.")
    except Exception:
        logger.exception("csp/enhancements: unexpected error for farm=%s", farm_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate enhancement recommendations. Please try again.",
        )

    return {"farm_id": farm_id, "enhancements": result}


# ---------------------------------------------------------------------------
# POST /csp/evaluate
# ---------------------------------------------------------------------------

@router.post("/evaluate")
@limiter.limit("20/hour")
async def run_full_csp_evaluation(
    request: Request,
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Run a complete CSP evaluation: eligibility + score + payments.

    Executes the full evaluation pipeline in sequence:
        1. CART stewardship scoring (updates csp_eligibility_assessments table)
        2. Eligibility determination (uses score result)
        3. Payment estimation (uses eligibility result)

    Results are persisted to the csp_eligibility_assessments table and returned
    immediately. This endpoint is idempotent — repeated calls overwrite
    previous results with the latest data.

    Use this endpoint when you want a complete, fresh CSP snapshot. Use
    the individual GET endpoints (/score, /eligibility, /payments) for
    read-only access to cached results.

    Args:
        farm_id: UUID of the farm to evaluate.

    Returns:
        A dict containing the full eligibility, score, and payment results
        along with a summary status.

    Raises:
        HTTPException 404: Farm not found.
        HTTPException 400: Validation error (e.g. no fields registered).
        HTTPException 500: Evaluation pipeline failure.
    """
    await _assert_farm_access(farm_id, supabase)

    # Step 1: Stewardship score
    try:
        score_result = await calculate_stewardship_score(farm_id, supabase)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid farm data. Please verify your farm is set up correctly.")
    except Exception:
        logger.exception("csp/evaluate: scoring failed for farm=%s", farm_id)
        raise HTTPException(
            status_code=500, detail="CSP scoring failed. Please try again."
        )

    # Step 2: Eligibility (uses fresh score, which is now cached)
    try:
        eligibility_result = await evaluate_csp_eligibility(farm_id, supabase)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid farm data. Please verify your farm is set up correctly.")
    except Exception:
        logger.exception("csp/evaluate: eligibility failed for farm=%s", farm_id)
        raise HTTPException(
            status_code=500,
            detail="CSP eligibility evaluation failed. Please try again.",
        )

    # Step 3: Payment estimation (reads from freshly-cached assessment)
    try:
        payment_result = await estimate_csp_payments(farm_id, supabase)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid farm data. Please verify your farm is set up correctly.")
    except Exception:
        logger.exception("csp/evaluate: payment estimation failed for farm=%s", farm_id)
        raise HTTPException(
            status_code=500,
            detail="CSP payment estimation failed. Please try again.",
        )

    logger.info(
        "csp/evaluate: complete farm=%s status=%s cart=%.1f annual_payment=%.2f",
        farm_id,
        eligibility_result.get("status"),
        score_result.get("total_points", 0.0),
        payment_result.get("total_annual_payment", 0.0),
    )

    return {
        "status": "evaluation_complete",
        "farm_id": farm_id,
        "eligibility": {
            "status": eligibility_result["status"],
            "is_eligible": eligibility_result["is_eligible"],
            "resource_concerns_meeting_threshold": eligibility_result[
                "resource_concerns_meeting_threshold"
            ],
            "cart_score": eligibility_result["cart_score"],
            "meets_ranking_threshold": eligibility_result["meets_ranking_threshold"],
            "eligibility_notes": eligibility_result["eligibility_notes"],
            "recommended_enhancements": eligibility_result["recommended_enhancements"],
        },
        "score": {
            "total_points": score_result["total_points"],
            "max_possible_points": score_result["max_possible_points"],
            "state_ranking_threshold": score_result["state_ranking_threshold"],
            "gap_to_threshold": score_result["gap_to_threshold"],
            "component_scores": score_result["component_scores"],
        },
        "payments": {
            "total_annual_payment": payment_result["total_annual_payment"],
            "total_5year_payment": payment_result["total_5year_payment"],
            "eap_annual": payment_result["eap_annual"],
            "enap_annual": payment_result["enap_annual"],
            "payment_capped": payment_result["payment_capped"],
        },
        "evaluated_at": eligibility_result["evaluated_at"],
    }


# ---------------------------------------------------------------------------
# GET /csp/deadlines
# ---------------------------------------------------------------------------

@router.get("/deadlines")
async def get_csp_deadlines(
    state: str | None = None,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Return upcoming CSP application deadlines.

    CSP accepts applications on a continuous basis. NRCS state offices batch
    and rank applications on a roughly quarterly schedule. This endpoint
    returns the next upcoming batching cutoff dates for a given state, or
    national defaults if the state is not specified or not in the table.

    Deadlines are hardcoded based on published FY2025 NRCS signup schedules.
    Always advise farmers to confirm dates with their local NRCS service
    center, as cutoff dates can shift based on funding availability.

    Args:
        state: Optional two-letter state abbreviation (e.g. 'IA'). If
            omitted, returns generic national deadline guidance.

    Returns:
        Dict with state, upcoming deadlines list, and an advisory note.
    """
    today = datetime.now(tz=timezone.utc).date()

    state_key: str = state.upper().strip() if state else ""
    if state_key and not re.match(r"^[A-Z]{2}$", state_key):
        raise HTTPException(status_code=400, detail="Invalid state code. Use a two-letter abbreviation (e.g. 'IA').")
    raw_deadlines: list[dict] = _CSP_DEADLINES.get(state_key, _DEFAULT_DEADLINES)

    # Filter to upcoming deadlines only; return all if none remain
    upcoming = [
        d for d in raw_deadlines
        if date.fromisoformat(d["cutoff_date"]) >= today
    ]
    if not upcoming:
        upcoming = raw_deadlines  # Return historical if all dates have passed

    return {
        "state": state_key or "NATIONAL",
        "deadlines": upcoming,
        "advisory": (
            "CSP uses continuous signup with quarterly ranking batches. "
            "Applications submitted before the cutoff date are ranked "
            "together; highest CART scores are funded first. Contact your "
            "local USDA Service Center (farmers.gov/service-center-locator) "
            "to confirm current cutoff dates and verify your application "
            "is complete before the batching deadline."
        ),
        "program_url": "https://www.nrcs.usda.gov/programs-initiatives/csp-conservation-stewardship-program",
    }
