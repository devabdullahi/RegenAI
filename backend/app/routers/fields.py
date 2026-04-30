import logging

from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError

from app.auth.middleware import get_current_user, get_authenticated_client
from app.models.schemas import FieldCreate, FieldUpdate, FieldResponse, SoilProfileResponse, WeatherResponse
from app.services.enrichment import run_enrichment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fields", tags=["Fields"])


@router.get("/", response_model=list[FieldResponse])
async def list_fields(
    farm_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """List all fields for a farm. RLS ensures data isolation."""
    result = (
        supabase.table("fields")
        .select("*")
        .eq("farm_id", farm_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.post("/", response_model=FieldResponse, status_code=201)
async def create_field(
    field: FieldCreate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Create a new field."""
    data = {
        "farm_id": field.farm_id,
        "name": field.name,
        "acres": field.acres,
        "crop_type": field.crop_type,
        "boundary_geojson": field.boundary_geojson,
        "boundary_description": field.boundary_description,
        "practices": field.practices,
    }
    result = supabase.table("fields").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create field")
    return result.data[0]


@router.get("/{field_id}", response_model=FieldResponse)
async def get_field(
    field_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Get a single field."""
    try:
        result = supabase.table("fields").select("*").eq("id", field_id).single().execute()
    except APIError:
        raise HTTPException(status_code=404, detail="Field not found")
    return result.data


@router.patch("/{field_id}", response_model=FieldResponse)
async def update_field(
    field_id: str,
    field: FieldUpdate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Partially update a field. Only provided fields are applied."""
    data = field.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        result = (
            supabase.table("fields")
            .update(data)
            .eq("id", field_id)
            .single()
            .execute()
        )
    except APIError:
        raise HTTPException(status_code=404, detail="Field not found")
    return result.data


@router.delete("/{field_id}", status_code=204)
async def delete_field(
    field_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Delete a field. RLS ensures the user can only delete their own fields.
    Cascading deletes on the DB handle related soil_profiles, weather_cache,
    and recommendations rows automatically."""
    try:
        supabase.table("fields").select("id").eq("id", field_id).single().execute()
    except APIError:
        raise HTTPException(status_code=404, detail="Field not found")
    supabase.table("fields").delete().eq("id", field_id).execute()


@router.get("/{field_id}/soil", response_model=SoilProfileResponse | None)
async def get_soil_profile(
    field_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Get the soil profile for a field."""
    result = (
        supabase.table("soil_profiles")
        .select("*")
        .eq("field_id", field_id)
        .order("fetched_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


@router.get("/{field_id}/weather", response_model=list[WeatherResponse])
async def get_weather(
    field_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Get weather data for a field (last 7 days)."""
    result = (
        supabase.table("weather_cache")
        .select("*")
        .eq("field_id", field_id)
        .order("date", desc=True)
        .limit(7)
        .execute()
    )
    return result.data


@router.post("/{field_id}/enrich", status_code=202)
async def enrich_field(
    field_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Fetch weather forecast + soil profile for a field and persist the results.

    Calls Open-Meteo (weather) and USDA SSURGO (soil) synchronously in this
    request so callers get a result summary immediately.  Both external APIs
    are called concurrently.  Failures in either service are reported in the
    ``warnings`` list rather than raising an error — the endpoint always
    returns 202 as long as the field exists and is accessible.

    When Celery is available, replace the direct ``run_enrichment`` call with:
        from app.tasks.enrichment import enrich_field_task
        enrich_field_task.delay(field_id)
    and return immediately with ``{"status": "enrichment_queued"}``.
    """
    # Verify field exists and the authenticated user has RLS access to it.
    try:
        supabase.table("fields").select("id").eq("id", field_id).single().execute()
    except APIError:
        raise HTTPException(status_code=404, detail="Field not found")

    logger.info("Starting enrichment for field=%s user=%s", field_id, user.id)

    # Run enrichment directly (no Celery yet).
    # The authenticated supabase client is passed so RLS remains enforced.
    enrichment_result = await run_enrichment(field_id, supabase)

    return {
        "status": "enrichment_complete",
        "field_id": enrichment_result["field_id"],
        "weather_days_upserted": enrichment_result["weather_days_upserted"],
        "soil_profile_saved": enrichment_result["soil_profile_saved"],
        "warnings": enrichment_result["warnings"],
    }
