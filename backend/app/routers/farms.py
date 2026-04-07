from fastapi import APIRouter, Depends, HTTPException

from app.auth.middleware import get_current_user, get_authenticated_client
from app.models.schemas import FarmCreate, FarmResponse

router = APIRouter(prefix="/farms", tags=["Farms"])


@router.get("/", response_model=list[FarmResponse])
async def list_farms(
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """List all farms for the current user. RLS enforces user isolation."""
    result = supabase.table("farms").select("*").order("created_at", desc=True).execute()
    return result.data


@router.post("/", response_model=FarmResponse, status_code=201)
async def create_farm(
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
    result = supabase.table("farms").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create farm")
    return result.data[0]


@router.get("/{farm_id}", response_model=FarmResponse)
async def get_farm(
    farm_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Get a single farm by ID. RLS ensures user can only access their own."""
    result = supabase.table("farms").select("*").eq("id", farm_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Farm not found")
    return result.data


@router.patch("/{farm_id}", response_model=FarmResponse)
async def update_farm(
    farm_id: str,
    farm: FarmCreate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Update farm details."""
    data = {
        "name": farm.name,
        "state": farm.state,
        "county_fips": farm.county_fips,
        "total_acres": farm.total_acres,
        "goals": farm.goals.value if farm.goals else None,
    }
    result = supabase.table("farms").update(data).eq("id", farm_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Farm not found")
    return result.data[0]


@router.delete("/{farm_id}", status_code=204)
async def delete_farm(
    farm_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Delete a farm. RLS ensures user can only delete their own."""
    supabase.table("farms").delete().eq("id", farm_id).execute()
