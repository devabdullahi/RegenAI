"""
Credit tracking router for RegenAI.

Exposes endpoints to query EQIP and VCM eligibility records, trigger
fresh evaluations, and assemble data for a credit eligibility report.

All endpoints require a valid Supabase JWT (Bearer token). The
authenticated Supabase client passed to service functions ensures Row
Level Security policies are enforced — users can only access data for
farms they own.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from postgrest.exceptions import APIError

from app.auth.access import assert_farm_access
from app.auth.middleware import get_authenticated_client, get_current_user
from app.models.schemas import (
    CreditEligibilityGetResponse,
    CreditEvaluateResponse,
    CreditReportResponse,
)
from app.rate_limit import limiter
from app.services.credit_rules import VCM_METHOD_LABEL, CreditDataError, vcm_rules_metadata
from app.services.eqip import evaluate_eqip_eligibility
from app.services.vcm import estimate_vcm_credits

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/credits", tags=["Credits"])

# Rule provenance attached to every VCM section; program_name is kept for
# existing clients and carries the same label as method_label.
_VCM_PROVENANCE: dict = {**vcm_rules_metadata(), "program_name": VCM_METHOD_LABEL}

# PostgREST errors plus transport failures reaching Supabase. Anything else is
# a bug and propagates.
_DB_ERRORS: tuple[type[Exception], ...] = (APIError, httpx.HTTPError)

# Shown when an engine cannot read its inputs or save its result. The
# CreditDataError text names internal tables, so it is logged, not returned.
_ENGINE_DATA_ERROR_DETAIL = (
    "{program} evaluation could not be completed because some farm data could not "
    "be loaded or saved. Nothing was changed. Please try again."
)


def get_utc_now() -> datetime:
    """Current UTC time; a dependency so tests can pin the clock."""
    return datetime.now(tz=timezone.utc)


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
    evaluation engines. A program that has not been evaluated yet is returned
    as null. Use POST /credits/evaluate to trigger a fresh evaluation.
    """
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)

    try:
        result = (
            supabase.table("credit_eligibility")
            .select("*")
            .eq("farm_id", farm_id_str)
            .order("updated_at", desc=True)
            .execute()
        )
        rows: list[dict] = result.data or []
    except _DB_ERRORS as exc:
        logger.exception("credits: failed to fetch eligibility for farm=%s", farm_id_str)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve credit eligibility records.",
        ) from exc

    # Rows are newest first — keep the first row seen for each program.
    eqip_row = next((r for r in rows if r.get("program") == "EQIP"), None)
    vcm_row = next((r for r in rows if r.get("program") == "VCM"), None)

    return {"farm_id": farm_id, "eqip": eqip_row, "vcm": vcm_row}


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
    now: datetime = Depends(get_utc_now),
):
    """Trigger a fresh EQIP and VCM evaluation for a farm.

    Runs both eligibility engines in sequence, persists the results to the
    credit_eligibility table, and returns both results. Repeated calls
    overwrite the previous results. If an engine cannot read its inputs or
    save its result, the request fails with 500 and nothing wrong is saved.
    """
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)

    eqip_result = await _run_engine(
        "EQIP", evaluate_eqip_eligibility, farm_id_str, supabase, now
    )
    vcm_result = await _run_engine("VCM", estimate_vcm_credits, farm_id_str, supabase, now)

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
            "eligibility_status": vcm_result.get("status"),
            "practices_documented": vcm_result.get("practices_documented", []),
            "notes": vcm_result.get("notes", ""),
            "updated_at": vcm_result.get("updated_at"),
            **_vcm_detail_fields(vcm_result),
        },
    }


async def _run_engine(program: str, engine, farm_id: str, supabase, now: datetime) -> dict:
    """Run one credit engine, mapping data failures to HTTP 500.

    Engines wrap database failures in CreditDataError; any other exception is
    a bug and propagates to FastAPI's 500 handler.
    """
    try:
        return await engine(farm_id, supabase, now=now)
    except CreditDataError as exc:
        logger.error("credits: %s evaluation data error farm=%s: %s", program, farm_id, exc)
        raise HTTPException(
            status_code=500, detail=_ENGINE_DATA_ERROR_DETAIL.format(program=program)
        ) from exc


def _vcm_detail_fields(vcm_result: dict) -> dict:
    """VCM estimate fields plus rule provenance, shared by evaluate and report."""
    return {
        "estimated_total_credits": vcm_result.get("estimated_total_credits", 0.0),
        "field_breakdown": vcm_result.get("field_breakdown", []),
        **_VCM_PROVENANCE,
    }


# ---------------------------------------------------------------------------
# GET /credits/report
# ---------------------------------------------------------------------------

@router.get("/report", response_model=CreditReportResponse)
async def get_credit_report(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
    now: datetime = Depends(get_utc_now),
):
    """Assemble all data required for a credit eligibility report.

    Returns the farm profile, field inventory, and the latest EQIP/VCM
    evaluations as structured data for the frontend to render.

    Side effect: when a VCM record already exists, this GET re-runs the VCM
    estimator to rebuild the per-field breakdown (which is not stored). That
    re-run upserts credit_eligibility, so the stored VCM row's status, notes
    and updated_at are refreshed from current data on every report request.

    Reads that fail are reported in ``data_warnings`` rather than hidden: the
    affected section is returned empty or as the stored record so the rest of
    the report remains usable.
    """
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)
    data_warnings: list[str] = []

    try:
        farm_rows = supabase.table("farms").select("*").eq("id", farm_id_str).limit(1).execute()
    except _DB_ERRORS as exc:
        logger.exception("credits/report: failed to fetch farm=%s", farm_id_str)
        raise HTTPException(status_code=500, detail="Failed to retrieve farm data.") from exc
    if not farm_rows.data:
        raise HTTPException(status_code=404, detail="Farm not found")
    farm: dict = farm_rows.data[0]

    fields: list[dict] = []
    try:
        fields_result = (
            supabase.table("fields")
            .select("id, name, acres, crop_type, practices")
            .eq("farm_id", farm_id_str)
            .execute()
        )
        fields = fields_result.data or []
    except _DB_ERRORS:
        logger.exception("credits/report: failed to fetch fields for farm=%s", farm_id_str)
        data_warnings.append("Field list could not be loaded; the fields section is incomplete.")

    eqip_record: dict | None = None
    vcm_record: dict | None = None
    eligibility_loaded = True
    try:
        eligibility_result = (
            supabase.table("credit_eligibility").select("*").eq("farm_id", farm_id_str).execute()
        )
        for row in eligibility_result.data or []:
            if row.get("program") == "EQIP":
                eqip_record = row
            elif row.get("program") == "VCM":
                vcm_record = row
    except _DB_ERRORS:
        eligibility_loaded = False
        logger.exception(
            "credits/report: failed to fetch credit_eligibility for farm=%s", farm_id_str
        )
        data_warnings.append(
            "Stored EQIP and VCM results could not be loaded; program sections are incomplete."
        )

    vcm_detail: dict | None = None
    if vcm_record:
        try:
            vcm_detail = await estimate_vcm_credits(farm_id_str, supabase, now=now)
        except CreditDataError:
            logger.exception("credits/report: VCM re-estimation failed for farm=%s", farm_id_str)
            data_warnings.append(
                "VCM estimate could not be recalculated; showing the stored result "
                "without a per-field breakdown."
            )

    return {
        "report_type": "credit_eligibility",
        "generated_at": now.isoformat(),
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
        "eqip": _eqip_report_section(eqip_record, eligibility_loaded),
        "vcm": _vcm_report_section(vcm_record, vcm_detail, eligibility_loaded),
        "data_warnings": data_warnings,
    }


def _eqip_report_section(record: dict | None, loaded: bool) -> dict:
    if record is None:
        return {"status": None, "notes": _not_evaluated_note("EQIP", "eligibility data", loaded)}
    return {
        "status": record.get("status"),
        "practices_documented": record.get("practices_documented", []),
        "notes": record.get("notes", ""),
        "updated_at": record.get("updated_at"),
    }


def _vcm_report_section(record: dict | None, detail: dict | None, loaded: bool) -> dict:
    if record is None:
        return {
            "status": None,
            "estimated_total_credits": 0.0,
            "notes": _not_evaluated_note("VCM", "credit estimates", loaded),
            **_VCM_PROVENANCE,
        }
    if detail is None:
        # Re-estimation failed: fall back to the stored row, which has no breakdown.
        return {
            "status": record.get("status"),
            "practices_documented": record.get("practices_documented", []),
            "notes": record.get("notes", ""),
            "updated_at": record.get("updated_at"),
            "estimated_total_credits": None,
            **_VCM_PROVENANCE,
        }
    return {
        "status": detail.get("status"),
        "practices_documented": detail.get("practices_documented", []),
        "notes": detail.get("notes", ""),
        "updated_at": detail.get("updated_at"),
        **_vcm_detail_fields(detail),
    }


def _not_evaluated_note(program: str, generates: str, loaded: bool) -> str:
    if not loaded:
        return f"{program} results could not be loaded. Try again shortly."
    return (
        f"{program} evaluation has not been run yet. "
        f"Call POST /credits/evaluate to generate {generates}."
    )
