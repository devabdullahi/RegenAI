"""
Farms router for RegenAI.

Farm CRUD for the authenticated user. RLS scopes every query to the user's
own farms, so a missing row means "not found or not yours".
"""

import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from postgrest.exceptions import APIError

from app.auth.access import PGRST_NO_ROWS, assert_farm_access
from app.auth.middleware import get_authenticated_client, get_current_user
from app.models.schemas import FarmCreate, FarmResponse, FarmUpdate
from app.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/farms", tags=["Farms"])

# PostgREST errors plus transport failures reaching Supabase. Anything else is
# a bug and propagates.
_DB_ERRORS: tuple[type[Exception], ...] = (APIError, httpx.HTTPError)


@router.get("/", response_model=list[FarmResponse])
async def list_farms(
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """List all farms for the current user. RLS enforces user isolation."""
    try:
        result = supabase.table("farms").select("*").order("created_at", desc=True).execute()
    except _DB_ERRORS as exc:
        logger.exception("Failed to list farms user=%s", user.id)
        raise HTTPException(status_code=500, detail="Failed to list farms") from exc
    return result.data or []


@router.post("/", response_model=FarmResponse, status_code=201)
@limiter.limit("30/hour")
async def create_farm(
    request: Request,
    farm: FarmCreate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Create a new farm for the current user."""
    data = {**farm.model_dump(mode="json"), "user_id": user.id}
    try:
        result = supabase.table("farms").insert(data).execute()
    except _DB_ERRORS as exc:
        logger.exception("Failed to create farm user=%s", user.id)
        raise HTTPException(status_code=500, detail="Failed to create farm") from exc
    if not result.data:
        logger.error("Farm insert returned no row user=%s", user.id)
        raise HTTPException(status_code=500, detail="Failed to create farm")
    return result.data[0]


@router.get("/{farm_id}", response_model=FarmResponse)
async def get_farm(
    farm_id: UUID,
    _user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Get a single farm by ID. 404 if missing or hidden by RLS; 500 on other DB errors."""
    farm_id_str = str(farm_id)
    try:
        result = supabase.table("farms").select("*").eq("id", farm_id_str).single().execute()
    except APIError as exc:
        if exc.code == PGRST_NO_ROWS:
            raise HTTPException(status_code=404, detail="Farm not found") from exc
        logger.error("Failed to fetch farm id=%s error=%s", farm_id_str, exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve farm") from exc
    if not result.data:
        raise HTTPException(status_code=404, detail="Farm not found")
    return result.data


@router.patch("/{farm_id}", response_model=FarmResponse)
async def update_farm(
    farm_id: UUID,
    farm: FarmUpdate,
    _user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Partially update farm details. Only provided fields are updated."""
    data = farm.model_dump(mode="json", exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        result = supabase.table("farms").update(data).eq("id", str(farm_id)).execute()
    except APIError as exc:
        logger.exception("Failed to update farm id=%s", farm_id)
        raise HTTPException(status_code=500, detail="Failed to update farm") from exc
    # RLS turns an update on someone else's farm into zero affected rows.
    if not result.data:
        raise HTTPException(status_code=404, detail="Farm not found")
    return result.data[0]


@router.delete("/{farm_id}", status_code=204)
async def delete_farm(
    farm_id: UUID,
    _user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Delete a farm. RLS ensures user can only delete their own."""
    assert_farm_access(farm_id, supabase)
    try:
        supabase.table("farms").delete().eq("id", str(farm_id)).execute()
    except APIError as exc:
        logger.exception("Failed to delete farm id=%s", farm_id)
        raise HTTPException(status_code=500, detail="Failed to delete farm") from exc
