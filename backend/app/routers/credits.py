"""
Credit tracking router for RegenAI.

Exposes endpoints to query EQIP and VCM eligibility records, trigger
fresh evaluations, and assemble data for PDF report generation.

All endpoints require a valid Supabase JWT (Bearer token). The
authenticated Supabase client passed to service functions ensures Row
Level Security policies are enforced — users can only access data for
farms they own.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from postgrest.exceptions import APIError

from app.auth.middleware import get_authenticated_client, get_current_user
from app.main import limiter
from app.models.schemas import (
    CreditEligibilityGetResponse,
    CreditEvaluateResponse,
    CreditReportResponse,
)
from app.services.eqip import evaluate_eqip_eligibility
from app.services.vcm import estimate_vcm_credits

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/credits", tags=["Credits"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _assert_farm_access(farm_id: UUID, supabase) -> None:
    """Raise HTTP 404 if the farm does not exist or the user cannot access it.

    Because the supabase client already has the user's JWT set, RLS will
    silently filter out rows the user does not own, so a missing row is
    sufficient signal that access is denied.

    Args:
        farm_id: UUID of the farm to check.
        supabase: Authenticated Supabase client.

    Raises:
        HTTPException: 404 if the farm is not found or not accessible.
    """
    try:
        supabase.table("farms").select("id").eq("id", str(farm_id)).single().execute()
    except APIError:
        raise HTTPException(status_code=404, detail="Farm not found")


# ---------------------------------------------------------------------------
# GET /credits
# ---------------------------------------------------------------------------

@router.get("/", response_model=CreditEligibilityGetResponse)
async def get_credit_eligibility(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Return the most recent EQIP and VCM eligibility records for a farm.

    Reads directly from the credit_eligibility table without re-running the
    evaluation engines. If no records exist yet, returns an empty list for
    that program. Use POST /credits/evaluate to trigger a fresh evaluation.

    Args:
        farm_id: UUID of the farm to query.

    Returns:
        A dict with keys 'eqip' and 'vcm', each containing the latest
        eligibility record or None if not yet evaluated.
    """
    await _assert_farm_access(farm_id, supabase)

    try:
        result = (
            supabase.table("credit_eligibility")
            .select("*")
            .eq("farm_id", str(farm_id))
            .order("updated_at", desc=True)
            .execute()
        )
        rows: list[dict] = result.data or []
    except Exception:
        logger.exception("credits: failed to fetch eligibility for farm=%s", farm_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve credit eligibility records.",
        )

    # Separate by program — return the most recent row for each
    eqip_row: dict | None = next(
        (r for r in rows if r.get("program") == "EQIP"), None
    )
    vcm_row: dict | None = next(
        (r for r in rows if r.get("program") == "VCM"), None
    )

    return {
        "farm_id": farm_id,
        "eqip": eqip_row,
        "vcm": vcm_row,
    }


# ---------------------------------------------------------------------------
# POST /credits/evaluate
# ---------------------------------------------------------------------------

@router.post("/evaluate", response_model=CreditEvaluateResponse)
@limiter.limit("20/hour")
async def evaluate_credits(
    request: Request,
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Trigger a fresh EQIP and VCM evaluation for a farm.

    Runs both eligibility engines in sequence, persists the results to the
    credit_eligibility table, and returns both results immediately. This
    endpoint is idempotent — repeated calls will overwrite the previous
    results with the latest data.

    Args:
        farm_id: UUID of the farm to evaluate.

    Returns:
        A dict containing the evaluation results for both programs along
        with summary statistics.
    """
    await _assert_farm_access(farm_id, supabase)

    farm_id_str = str(farm_id)

    # Run EQIP evaluation
    try:
        eqip_result = await evaluate_eqip_eligibility(farm_id_str, supabase)
    except ValueError as exc:
        logger.warning("credits: EQIP evaluation failed for farm=%s: %s", farm_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("credits: EQIP evaluation error for farm=%s", farm_id)
        raise HTTPException(
            status_code=500,
            detail="EQIP evaluation failed. Please try again.",
        )

    # Run VCM estimation
    try:
        vcm_result = await estimate_vcm_credits(farm_id_str, supabase)
    except ValueError as exc:
        logger.warning("credits: VCM evaluation failed for farm=%s: %s", farm_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("credits: VCM evaluation error for farm=%s", farm_id)
        raise HTTPException(
            status_code=500,
            detail="VCM estimation failed. Please try again.",
        )

    return {
        "status": "evaluation_complete",
        "farm_id": farm_id,
        "eqip": {
            "program": "EQIP",
            "eligibility_status": eqip_result.get("status"),
            "practices_documented": eqip_result.get("practices_documented", []),
            "notes": eqip_result.get("notes", ""),
            "updated_at": eqip_result.get("updated_at"),
        },
        "vcm": {
            "program": "VCM",
            "program_name": vcm_result.get("program_name", "Soil Carbon Protocol"),
            "eligibility_status": vcm_result.get("status"),
            "estimated_total_credits": vcm_result.get("estimated_total_credits", 0.0),
            "practices_documented": vcm_result.get("practices_documented", []),
            "field_breakdown": vcm_result.get("field_breakdown", []),
            "notes": vcm_result.get("notes", ""),
            "updated_at": vcm_result.get("updated_at"),
        },
    }


# ---------------------------------------------------------------------------
# GET /credits/report
# ---------------------------------------------------------------------------

@router.get("/report", response_model=CreditReportResponse)
async def get_credit_report(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Assemble all data required for a credit eligibility PDF report.

    Fetches the farm profile, field inventory, and the latest EQIP/VCM
    evaluations in a single response. The VCM result is re-evaluated live
    to include the full per-field breakdown (not stored in the DB). If no
    credit records exist yet, the report will note that an evaluation must
    be triggered first.

    This endpoint intentionally returns raw data rather than a PDF so that
    the PDF renderer (WeasyPrint, added in a future iteration) can be
    swapped or templated independently.

    Args:
        farm_id: UUID of the farm.

    Returns:
        A structured dict ready for report templating, containing farm
        metadata, field list, EQIP eligibility, VCM credit estimate, and
        a generated_at timestamp.
    """
    farm_id_str = str(farm_id)
    await _assert_farm_access(farm_id, supabase)

    # ------------------------------------------------------------------
    # Farm profile
    # ------------------------------------------------------------------
    try:
        farm_result = (
            supabase.table("farms")
            .select("*")
            .eq("id", farm_id_str)
            .single()
            .execute()
        )
        farm: dict = farm_result.data or {}
    except APIError:
        raise HTTPException(status_code=404, detail="Farm not found")
    except Exception:
        logger.exception("credits/report: failed to fetch farm=%s", farm_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve farm data.")

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    try:
        fields_result = (
            supabase.table("fields")
            .select("id, name, acres, crop_type, practices")
            .eq("farm_id", farm_id_str)
            .execute()
        )
        fields: list[dict] = fields_result.data or []
    except Exception:
        logger.exception("credits/report: failed to fetch fields for farm=%s", farm_id)
        fields = []

    # ------------------------------------------------------------------
    # Stored EQIP record (read-only — no re-evaluation here)
    # ------------------------------------------------------------------
    eqip_record: dict | None = None
    vcm_record: dict | None = None

    try:
        eligibility_result = (
            supabase.table("credit_eligibility")
            .select("*")
            .eq("farm_id", farm_id_str)
            .execute()
        )
        for row in eligibility_result.data or []:
            if row.get("program") == "EQIP":
                eqip_record = row
            elif row.get("program") == "VCM":
                vcm_record = row
    except Exception:
        logger.exception(
            "credits/report: failed to fetch credit_eligibility for farm=%s", farm_id
        )

    # ------------------------------------------------------------------
    # Re-run VCM estimator to get the full per-field breakdown
    # (stored notes row lacks the breakdown detail)
    # ------------------------------------------------------------------
    vcm_detail: dict | None = None
    if vcm_record:
        try:
            vcm_detail = await estimate_vcm_credits(farm_id_str, supabase)
        except Exception:
            logger.exception(
                "credits/report: VCM re-estimation failed for farm=%s", farm_id
            )
            vcm_detail = vcm_record  # Fall back to stored record without breakdown

    # ------------------------------------------------------------------
    # Assemble report payload
    # ------------------------------------------------------------------
    from datetime import datetime, timezone

    report = {
        "report_type": "credit_eligibility",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "farm": {
            "id": farm.get("id"),
            "name": farm.get("name"),
            "state": farm.get("state"),
            "county_fips": farm.get("county_fips"),
            "total_acres": farm.get("total_acres"),
            "goals": farm.get("goals"),
        },
        "fields": [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "acres": f.get("acres"),
                "crop_type": f.get("crop_type"),
                "practices": f.get("practices") or [],
            }
            for f in fields
        ],
        "eqip": (
            {
                "status": eqip_record.get("status"),
                "practices_documented": eqip_record.get("practices_documented", []),
                "notes": eqip_record.get("notes", ""),
                "updated_at": eqip_record.get("updated_at"),
            }
            if eqip_record
            else {
                "status": None,
                "notes": "EQIP evaluation has not been run yet. "
                "Call POST /credits/evaluate to generate eligibility data.",
            }
        ),
        "vcm": (
            {
                "status": vcm_detail.get("status") if vcm_detail else None,
                "program_name": "Soil Carbon Protocol",
                "estimated_total_credits": (
                    vcm_detail.get("estimated_total_credits", 0.0)
                    if vcm_detail
                    else 0.0
                ),
                "practices_documented": (
                    vcm_detail.get("practices_documented", []) if vcm_detail else []
                ),
                "field_breakdown": (
                    vcm_detail.get("field_breakdown", []) if vcm_detail else []
                ),
                "notes": vcm_detail.get("notes", "") if vcm_detail else "",
                "updated_at": (
                    vcm_detail.get("updated_at") if vcm_detail else None
                ),
            }
            if vcm_record
            else {
                "status": None,
                "program_name": "Soil Carbon Protocol",
                "estimated_total_credits": 0.0,
                "notes": "VCM evaluation has not been run yet. "
                "Call POST /credits/evaluate to generate credit estimates.",
            }
        ),
    }

    return report
