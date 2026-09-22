"""
CSP Navigator router for RegenAI.

Exposes endpoints for USDA NRCS Conservation Stewardship Program (CSP)
eligibility assessment, stewardship scoring, payment estimation, and
enhancement activity recommendations.

All endpoints require a valid Supabase JWT (Bearer token). Row Level Security
policies are enforced through the authenticated Supabase client, so users can
only access data for farms they own.

Every farm endpoint recomputes its result on each request; none serves a
stored copy. GET /csp/eligibility and POST /csp/evaluate also upsert the
assessment row in csp_eligibility_assessments as a side effect.

Payment amounts, contract limits and their citations are defined only in
``app.services.program_rules`` and returned in each response's ``rules`` /
``scoring_rules`` block. RegenAI's score and thresholds are estimates
(``is_estimate`` in responses).
"""

import logging
import re
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from postgrest.exceptions import APIError

from app.auth.access import assert_farm_access
from app.auth.middleware import get_authenticated_client, get_current_user
from app.models.schemas import (
    CSPEligibilityResponse,
    CSPEnhancementsResponse,
    CSPEvaluateResponse,
    CSPPaymentEstimate,
    CSPScoreBreakdown,
    ProgramDeadlinesResponse,
)
from app.rate_limit import limiter
from app.services.csp_eligibility import evaluate_csp_eligibility
from app.services.csp_payment import estimate_csp_payments, get_recommended_enhancements
from app.services.csp_scoring import calculate_stewardship_score
from app.services.program_deadlines import build_deadlines_response, today_central
from app.services.program_rules import CSP_DEFAULT_CONTRACT_FY, csp_rules_metadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/csp", tags=["CSP Navigator"])


_INVALID_FARM_DETAIL = "Invalid farm data. Please verify your farm is set up correctly."


# ---------------------------------------------------------------------------
# GET /csp/eligibility
# ---------------------------------------------------------------------------

@router.get("/eligibility", response_model=CSPEligibilityResponse)
async def get_csp_eligibility(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Run a full CSP eligibility assessment for a farm.

    Evaluates whether the operation currently meets the stewardship threshold
    on at least 2 priority resource concerns (the statutory eligibility
    requirement), and whether the estimated CART score meets the estimated
    state ranking threshold (the farm may then be considered for ACT NOW if
    the state offers it).

    Side effect: recomputes and upserts the farm's assessment row for the
    current fiscal year.

    Args:
        farm_id: UUID of the farm to assess.

    Returns:
        CSPEligibilityResponse with per-concern detail, recommended gap-closure
        activities, plain-language notes, and ``scoring_rules`` citations.

    Raises:
        HTTPException 404: Farm not found.
        HTTPException 400: Farm data could not be evaluated.
        HTTPException 500: Database error.
    """
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)

    try:
        return await evaluate_csp_eligibility(farm_id_str, supabase)
    except ValueError as exc:
        logger.warning("csp/eligibility: evaluation failed farm=%s: %s", farm_id_str, exc)
        raise HTTPException(status_code=400, detail=_INVALID_FARM_DETAIL) from exc
    except APIError as exc:
        logger.error("csp/eligibility: database error farm=%s: %s", farm_id_str, exc)
        raise HTTPException(
            status_code=500,
            detail="CSP eligibility evaluation failed. Please try again.",
        ) from exc


# ---------------------------------------------------------------------------
# GET /csp/score
# ---------------------------------------------------------------------------

@router.get("/score", response_model=CSPScoreBreakdown)
async def get_csp_score(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Return the estimated CART stewardship score breakdown for a farm.

    Scores the farm across all eight NRCS priority resource concern categories
    using field practices, soil organic matter data, and acted
    recommendations. Includes the estimated state ranking threshold and the
    points needed to reach it. Read-only.

    Args:
        farm_id: UUID of the farm to score.

    Returns:
        CSPScoreBreakdown with per-concern scores, gap analysis,
        ``is_estimate`` and ``scoring_rules`` citations.

    Raises:
        HTTPException 404: Farm not found.
        HTTPException 400: Farm data could not be scored.
        HTTPException 500: Database error.
    """
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)

    try:
        return await calculate_stewardship_score(farm_id_str, supabase)
    except ValueError as exc:
        logger.warning("csp/score: scoring failed farm=%s: %s", farm_id_str, exc)
        raise HTTPException(status_code=400, detail=_INVALID_FARM_DETAIL) from exc
    except APIError as exc:
        logger.error("csp/score: database error farm=%s: %s", farm_id_str, exc)
        raise HTTPException(
            status_code=500,
            detail="CSP score calculation failed. Please try again.",
        ) from exc


# ---------------------------------------------------------------------------
# GET /csp/payments
# ---------------------------------------------------------------------------

@router.get("/payments", response_model=CSPPaymentEstimate)
async def get_csp_payments(
    farm_id: UUID,
    contract_fiscal_year: int = Query(
        CSP_DEFAULT_CONTRACT_FY,
        ge=2019,
        le=2100,
        description="Fiscal year the contract is obligated in; limits depend on it",
    ),
    joint_operation: bool = Query(
        False,
        description="True for a joint operation contract (higher contract limit)",
    ),
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Estimate annual and contract-term CSP payments for a farm.

    Annual estimate = Existing Activity Payment (only when the farm can hold a
    contract) + estimated conservation activity payments. The contract total
    is capped at the contract limit for the contract's fiscal year and
    operation type. Amounts and limits come from ``program_rules`` and are
    cited in the response's ``rules`` block.

    Concerns meeting threshold come from the latest persisted assessment, or
    are scored inline when none exists. Read-only.

    Args:
        farm_id: UUID of the farm to estimate payments for.
        contract_fiscal_year: Contract fiscal year (default CSP_DEFAULT_CONTRACT_FY).
        joint_operation: Whether the contract is for a joint operation.

    Returns:
        CSPPaymentEstimate including ``contract_limit`` and ``rules``
        citation metadata (as_of, source_url).

    Raises:
        HTTPException 404: Farm not found.
        HTTPException 400: Farm data could not be estimated.
        HTTPException 500: Database error.
    """
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)

    try:
        return await estimate_csp_payments(
            farm_id_str,
            supabase,
            contract_fiscal_year=contract_fiscal_year,
            joint_operation=joint_operation,
        )
    except ValueError as exc:
        logger.warning("csp/payments: estimation failed farm=%s: %s", farm_id_str, exc)
        raise HTTPException(status_code=400, detail=_INVALID_FARM_DETAIL) from exc
    except APIError as exc:
        logger.error("csp/payments: database error farm=%s: %s", farm_id_str, exc)
        raise HTTPException(
            status_code=500,
            detail="CSP payment estimation failed. Please try again.",
        ) from exc


# ---------------------------------------------------------------------------
# GET /csp/enhancements
# ---------------------------------------------------------------------------

@router.get("/enhancements", response_model=CSPEnhancementsResponse)
async def get_csp_enhancements(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Return ranked CSP conservation activity recommendations for a farm.

    Scores each FY2026 CSP activity (keyed by NRCS practice standard code;
    "E" enhancement codes and bundles are retired) against the farm's current
    stewardship gaps and returns them sorted by impact priority. Read-only.

    Estimated annual payments use pre-FY2026 per-acre rate estimates pending
    the FY2026 state payment schedule; cover crop, AGM, RCCR, and IRCCR
    activities are flagged as higher-payment categories.

    Args:
        farm_id: UUID of the farm.

    Returns:
        CSPEnhancementsResponse: ``enhancements`` sorted by priority score and
        ``rules`` citation metadata.

    Raises:
        HTTPException 404: Farm not found.
        HTTPException 400: Farm data could not be evaluated.
        HTTPException 500: Database error.
    """
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)

    try:
        enhancements = await get_recommended_enhancements(farm_id_str, supabase)
    except ValueError as exc:
        logger.warning("csp/enhancements: failed farm=%s: %s", farm_id_str, exc)
        raise HTTPException(status_code=400, detail=_INVALID_FARM_DETAIL) from exc
    except APIError as exc:
        logger.error("csp/enhancements: database error farm=%s: %s", farm_id_str, exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate enhancement recommendations. Please try again.",
        ) from exc

    return {
        "farm_id": farm_id_str,
        "enhancements": enhancements,
        "rules": csp_rules_metadata(),
    }


# ---------------------------------------------------------------------------
# POST /csp/evaluate
# ---------------------------------------------------------------------------

@router.post("/evaluate", response_model=CSPEvaluateResponse)
@limiter.limit("20/hour")
async def run_full_csp_evaluation(
    request: Request,
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Run a complete CSP evaluation: score + eligibility + payments.

    Executes the full evaluation pipeline in sequence:
        1. Stewardship scoring.
        2. Eligibility determination (re-scores and upserts the assessment
           row in csp_eligibility_assessments).
        3. Payment estimation (reads the assessment row written in step 2).

    Repeated calls overwrite the current fiscal year's assessment row with
    the latest data. The GET endpoints compute the same results; this endpoint
    returns a combined summary in one call.

    Args:
        farm_id: UUID of the farm to evaluate.

    Returns:
        CSPEvaluateResponse with eligibility, score, and payment summaries.

    Raises:
        HTTPException 404: Farm not found.
        HTTPException 400: Farm data could not be evaluated.
        HTTPException 500: Database error.
    """
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)

    try:
        score_result = await calculate_stewardship_score(farm_id_str, supabase)
        eligibility_result = await evaluate_csp_eligibility(farm_id_str, supabase)
        payment_result = await estimate_csp_payments(farm_id_str, supabase)
    except ValueError as exc:
        logger.warning("csp/evaluate: evaluation failed farm=%s: %s", farm_id_str, exc)
        raise HTTPException(status_code=400, detail=_INVALID_FARM_DETAIL) from exc
    except APIError as exc:
        logger.error("csp/evaluate: database error farm=%s: %s", farm_id_str, exc)
        raise HTTPException(
            status_code=500, detail="CSP evaluation failed. Please try again."
        ) from exc

    logger.info(
        "csp/evaluate: complete farm=%s status=%s cart=%.1f annual_payment=%.2f",
        farm_id_str,
        eligibility_result["status"],
        score_result["total_points"],
        payment_result["total_annual_payment"],
    )

    return {
        "status": "evaluation_complete",
        "farm_id": farm_id_str,
        "eligibility": eligibility_result,
        "score": score_result,
        "payments": payment_result,
        "evaluated_at": eligibility_result["evaluated_at"],
    }


# ---------------------------------------------------------------------------
# GET /csp/deadlines
# ---------------------------------------------------------------------------

@router.get("/deadlines", response_model=ProgramDeadlinesResponse)
async def get_csp_deadlines(
    state: str | None = None,
    today: date = Depends(today_central),
    user=Depends(get_current_user),
):
    """Return upcoming program deadlines (NRCS EQIP/CSP, SDRP, cover-crop discounts).

    Reads the dated, sourced table in ``app.services.program_deadlines``.
    Returns entries for the state plus all-state entries, soonest first, with
    past dates removed and ``days_remaining`` / ``urgency`` computed against
    ``today`` (injectable for tests). States with no published cutoff get a
    ``not_announced`` entry linking to their NRCS office.

    Args:
        state: Optional two-letter state abbreviation (e.g. 'IA'). If
            omitted, returns all-state deadlines plus generic guidance.

    Raises:
        HTTPException 400: State is not a two-letter code.
    """
    state_key: str = state.upper().strip() if state else ""
    if state_key and not re.match(r"^[A-Z]{2}$", state_key):
        raise HTTPException(
            status_code=400,
            detail="Invalid state code. Use a two-letter abbreviation (e.g. 'IA').",
        )
    return build_deadlines_response(state_key, today)
