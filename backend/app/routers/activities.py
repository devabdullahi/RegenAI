"""
Field Activity Log router for RegenAI.

Exposes endpoints for logging, retrieving, updating, and deleting field
activities (planting, spraying, scouting, harvest, tillage, cover crops,
etc.) as well as yield history recording and APH calculation.

All endpoints require a valid Supabase JWT (Bearer token). Row Level Security
policies are enforced through the authenticated Supabase client, so users can
only access activities for fields they own.

Validation highlights:
    - UUID type used for all ID path/query parameters (FastAPI auto-validates).
    - activity_date cannot be in the future.
    - restricted_use spray requires applicator_name + applicator_license.
    - acres_applied cannot exceed the field's total acres.
    - APH requires >= 4 years of yield history (max 10 years used).
"""

import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.middleware import get_authenticated_client, get_current_user
from app.models.schemas import (
    ActivityCreate,
    ActivityListResponse,
    ActivityResponse,
    ActivityType,
    ActivityUpdate,
    APHResponse,
    YieldHistoryCreate,
    YieldHistoryResponse,
)
from app.services.activity_log import (
    calculate_aph,
    create_activity,
    create_yield_history,
    delete_activity,
    get_activity,
    get_activity_summary,
    list_activities,
    list_yield_history,
    update_activity,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Field Activity Log"])


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@router.post("/activities", response_model=ActivityResponse, status_code=201)
async def log_activity(
    body: ActivityCreate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Log a new field activity.

    Validates field ownership, business rules (date, spray credentials,
    acreage), and inserts the record. When a harvest activity includes
    ``yield_bu_acre`` and ``crop_year``, a yield_history row is automatically
    upserted.

    Args:
        body: Activity payload.

    Returns:
        Newly created ActivityResponse. Non-fatal problems (e.g. harvest saved
        but yield history not synced) are listed in ``warnings``.

    Raises:
        HTTPException 404: Field not found.
        HTTPException 422: Business rule violation.
        HTTPException 500: Database error.
    """
    row, warnings = await create_activity(body, supabase)
    if warnings:
        logger.info(
            "activities.log_activity: id=%s warnings=%s", row.get("id"), warnings
        )
    return {**row, "warnings": warnings}


@router.get("/activities", response_model=ActivityListResponse)
async def list_field_activities(
    field_id: UUID,
    activity_type: ActivityType | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """List activities for a field with optional filters and pagination.

    Args:
        field_id: UUID of the field (required).
        activity_type: Optional filter by activity type.
        start_date: Optional inclusive lower bound on activity_date.
        end_date: Optional inclusive upper bound on activity_date.
        limit: Page size (1–200, default 50).
        offset: Row offset for pagination (default 0).

    Returns:
        ActivityListResponse with activities list and total_count.

    Raises:
        HTTPException 404: Field not found.
        HTTPException 422: start_date is after end_date.
        HTTPException 500: Database error.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422, detail="start_date cannot be after end_date."
        )

    return await list_activities(
        field_id=str(field_id),
        supabase=supabase,
        activity_type=activity_type.value if activity_type else None,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@router.get("/activities/summary")
async def activity_summary(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Return activity summary statistics for all fields on a farm.

    Provides activity count by type and the most recent activity date per
    field — useful for dashboard cards and field health indicators.

    Args:
        farm_id: UUID of the farm.

    Returns:
        Dict with ``farm_id``, ``total_activities``, ``count_by_type``,
        and ``last_activity_per_field``.

    Raises:
        HTTPException 404: Farm not found.
        HTTPException 500: Database error.
    """
    return await get_activity_summary(str(farm_id), supabase)


@router.get("/activities/{activity_id}", response_model=ActivityResponse)
async def get_single_activity(
    activity_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Get a single activity by ID.

    Args:
        activity_id: UUID of the activity record.

    Returns:
        ActivityResponse.

    Raises:
        HTTPException 404: Activity not found or not accessible.
    """
    return await get_activity(str(activity_id), supabase)


@router.patch("/activities/{activity_id}", response_model=ActivityResponse)
async def patch_activity(
    activity_id: UUID,
    body: ActivityUpdate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Partially update an existing activity.

    Only fields present in the request body are modified. Applies the same
    business rules as creation (date, spray credentials, acreage) using merged
    existing + updated values.

    Args:
        activity_id: UUID of the activity to update.
        body: Partial update payload (all fields optional).

    Returns:
        Updated ActivityResponse.

    Raises:
        HTTPException 404: Activity not found.
        HTTPException 422: Business rule violation.
        HTTPException 500: Database error.
    """
    return await update_activity(str(activity_id), body, supabase)


@router.delete("/activities/{activity_id}", status_code=204)
async def remove_activity(
    activity_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Delete a field activity record.

    Args:
        activity_id: UUID of the activity to delete.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException 404: Activity not found.
        HTTPException 500: Database error.
    """
    await delete_activity(str(activity_id), supabase)


# ---------------------------------------------------------------------------
# Yield History
# ---------------------------------------------------------------------------


@router.post("/yield-history", response_model=YieldHistoryResponse, status_code=201)
async def record_yield_history(
    body: YieldHistoryCreate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Record a yield history entry for a field and crop year.

    Upserts on (field_id, crop_year) — submitting for an existing year
    overwrites that year's data. Useful for manual corrections or importing
    historical yield records.

    Args:
        body: Yield history payload.

    Returns:
        Newly created or updated YieldHistoryResponse.

    Raises:
        HTTPException 404: Field not found.
        HTTPException 500: Database error.
    """
    return await create_yield_history(body, supabase)


@router.get("/yield-history", response_model=list[YieldHistoryResponse])
async def get_yield_history(
    field_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Get yield history for a field, ordered by crop_year descending.

    Args:
        field_id: UUID of the field (required).

    Returns:
        List of YieldHistoryResponse ordered newest year first.

    Raises:
        HTTPException 404: Field not found.
        HTTPException 500: Database error.
    """
    return await list_yield_history(str(field_id), supabase)


@router.get("/yield-history/aph", response_model=APHResponse)
async def get_aph(
    field_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Calculate the Actual Production History (APH) yield for a field.

    Uses up to the 10 most recent years of yield data per USDA FSA standards.
    A minimum of 4 years is required; returns HTTP 422 if fewer are on file.

    Args:
        field_id: UUID of the field.

    Returns:
        APHResponse with ``aph_yield``, ``years_used``, ``year_range``,
        and the individual year ``records``.

    Raises:
        HTTPException 404: Field not found.
        HTTPException 422: Fewer than 4 years of yield data available.
        HTTPException 500: Database error.
    """
    return await calculate_aph(str(field_id), supabase)
