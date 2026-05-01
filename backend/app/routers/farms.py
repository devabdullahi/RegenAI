import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from postgrest.exceptions import APIError

from app.auth.middleware import get_current_user, get_authenticated_client
from app.rate_limit import limiter
from app.models.schemas import FarmCreate, FarmUpdate, FarmResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/farms", tags=["Farms"])


@router.get("/", response_model=list[FarmResponse])
async def list_farms(
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """List all farms for the current user. RLS enforces user isolation."""
    try:
        result = supabase.table("farms").select("*").order("created_at", desc=True).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to list farms: {e}")
        raise HTTPException(status_code=500, detail="Failed to list farms")


@router.post("/", response_model=FarmResponse, status_code=201)
@limiter.limit("30/hour")
async def create_farm(
    request: Request,
    farm: FarmCreate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Create a new farm for the current user."""
    data = {
        "user_id": user.id,
        "name": farm.name,
        "state": farm.state,
        "county_fips": farm.county_fips,
        "total_acres": farm.total_acres,
        "goals": farm.goals.value if farm.goals else None,
    }
    try:
        result = supabase.table("farms").insert(data).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create farm")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create farm: {e}")
        raise HTTPException(status_code=500, detail="Failed to create farm")


@router.get("/{farm_id}", response_model=FarmResponse)
async def get_farm(
    farm_id: UUID,
    _user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Get a single farm by ID. RLS ensures user can only access their own."""
    try:
        result = supabase.table("farms").select("*").eq("id", farm_id).single().execute()
    except APIError:
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
    data = farm.model_dump(exclude_unset=True)
    if "goals" in data and data["goals"] is not None:
        data["goals"] = data["goals"].value if hasattr(data["goals"], "value") else data["goals"]
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = supabase.table("farms").update(data).eq("id", farm_id).execute()
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
    try:
        supabase.table("farms").select("id").eq("id", farm_id).single().execute()
    except APIError:
        raise HTTPException(status_code=404, detail="Farm not found")
    supabase.table("farms").delete().eq("id", farm_id).execute()
