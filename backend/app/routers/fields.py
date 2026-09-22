"""
Fields router for RegenAI.

Field CRUD plus the cached soil and weather readings for a field, and the
enrichment trigger that refreshes them. RLS scopes every query to the
authenticated user's farms, so a missing row means "not found or not yours".
"""

import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from postgrest.exceptions import APIError

from app.auth.access import PGRST_NO_ROWS, assert_farm_access, assert_field_access
from app.auth.middleware import get_authenticated_client, get_current_user
from app.models.schemas import (
    FieldCreate,
    FieldResponse,
    FieldUpdate,
    SoilProfileResponse,
    WeatherResponse,
)
from app.rate_limit import limiter
from app.services.enrichment import run_enrichment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fields", tags=["Fields"])

# Enrichment caches a 7-day forecast; the widget shows one week.
_WEATHER_DAYS_RETURNED = 7

# PostgREST errors plus transport failures reaching Supabase. Anything else is
# a bug and propagates.
_DB_ERRORS: tuple[type[Exception], ...] = (APIError, httpx.HTTPError)


@router.get("/", response_model=list[FieldResponse])
async def list_fields(
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """List all fields for a farm. 404 if the farm is missing or not the user's."""
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)
    try:
        result = (
            supabase.table("fields")
            .select("*")
            .eq("farm_id", farm_id_str)
            .order("created_at", desc=True)
            .execute()
        )
    except _DB_ERRORS as exc:
        logger.exception("Failed to list fields farm_id=%s", farm_id_str)
        raise HTTPException(status_code=500, detail="Failed to list fields") from exc
    return result.data or []


@router.post("/", response_model=FieldResponse, status_code=201)
@limiter.limit("30/hour")
async def create_field(
    request: Request,
    field: FieldCreate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Create a new field."""
    data = {
        # UUID objects are not JSON-serialisable by the Supabase HTTP client.
        "farm_id": str(field.farm_id),
        "name": field.name,
        "acres": field.acres,
        "crop_type": field.crop_type,
        "boundary_geojson": field.boundary_geojson,
        "boundary_description": field.boundary_description,
        "practices": field.practices,
    }
    try:
        result = supabase.table("fields").insert(data).execute()
    except _DB_ERRORS as exc:
        logger.exception("Failed to create field farm_id=%s", data["farm_id"])
        raise HTTPException(status_code=500, detail="Failed to create field") from exc
    if not result.data:
        logger.error("Field insert returned no row farm_id=%s", data["farm_id"])
        raise HTTPException(status_code=500, detail="Failed to create field")
    return result.data[0]


@router.get("/{field_id}", response_model=FieldResponse)
async def get_field(
    field_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Get a single field. 404 if missing or hidden by RLS; 500 on other DB errors."""
    field_id_str = str(field_id)
    try:
        result = supabase.table("fields").select("*").eq("id", field_id_str).single().execute()
    except APIError as exc:
        if exc.code == PGRST_NO_ROWS:
            raise HTTPException(status_code=404, detail="Field not found") from exc
        logger.error("Failed to fetch field field_id=%s error=%s", field_id_str, exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve field") from exc
    if not result.data:
        raise HTTPException(status_code=404, detail="Field not found")
    return result.data


@router.patch("/{field_id}", response_model=FieldResponse)
async def update_field(
    field_id: UUID,
    field: FieldUpdate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Partially update a field. Only provided fields are applied."""
    data = field.model_dump(mode="json", exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    field_id_str = str(field_id)
    try:
        result = supabase.table("fields").update(data).eq("id", field_id_str).execute()
    except APIError as exc:
        logger.error("Failed to update field field_id=%s error=%s", field_id_str, exc)
        raise HTTPException(status_code=500, detail="Failed to update field") from exc
    # RLS turns an update on someone else's field into zero affected rows.
    if not result.data:
        raise HTTPException(status_code=404, detail="Field not found")
    return result.data[0]


@router.delete("/{field_id}", status_code=204)
@limiter.limit("30/hour")
async def delete_field(
    request: Request,
    field_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Delete a field. RLS ensures the user can only delete their own fields.
    Cascading deletes on the DB handle related soil_profiles, weather_cache,
    and recommendations rows automatically."""
    field_id_str = str(field_id)
    assert_field_access(field_id_str, supabase)
    try:
        supabase.table("fields").delete().eq("id", field_id_str).execute()
    except APIError as exc:
        logger.error("Failed to delete field field_id=%s error=%s", field_id_str, exc)
        raise HTTPException(status_code=500, detail="Failed to delete field") from exc


@router.get("/{field_id}/soil", response_model=SoilProfileResponse | None)
async def get_soil_profile(
    field_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Get the latest soil profile for a field.

    404 if the field is missing or not the user's; null if the field has no
    soil profile yet.
    """
    field_id_str = str(field_id)
    assert_field_access(field_id_str, supabase)
    try:
        result = (
            supabase.table("soil_profiles")
            .select("*")
            .eq("field_id", field_id_str)
            .order("fetched_at", desc=True)
            .limit(1)
            .execute()
        )
    except _DB_ERRORS as exc:
        logger.exception("Failed to fetch soil profile field_id=%s", field_id_str)
        raise HTTPException(status_code=500, detail="Failed to retrieve soil profile") from exc
    return result.data[0] if result.data else None


@router.get("/{field_id}/weather", response_model=list[WeatherResponse])
async def get_weather(
    field_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Get up to a week of cached weather days for a field, newest date first.

    404 if the field is missing or not the user's.
    """
    field_id_str = str(field_id)
    assert_field_access(field_id_str, supabase)
    try:
        result = (
            supabase.table("weather_cache")
            .select("*")
            .eq("field_id", field_id_str)
            .order("date", desc=True)
            .limit(_WEATHER_DAYS_RETURNED)
            .execute()
        )
    except _DB_ERRORS as exc:
        logger.exception("Failed to fetch weather field_id=%s", field_id_str)
        raise HTTPException(status_code=500, detail="Failed to retrieve weather data") from exc
    return result.data or []


@router.post("/{field_id}/enrich", status_code=202)
@limiter.limit("10/hour")
async def enrich_field(
    request: Request,
    field_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Fetch weather forecast + soil profile for a field and persist the results.

    Calls Open-Meteo (weather) and USDA SSURGO (soil) concurrently inside this
    request so callers get a result summary immediately. Fetch failures,
    skipped readings, database write failures and approximate (county-centre)
    locations are reported in ``warnings`` rather than raising — the endpoint
    returns 202 as long as the field exists and is accessible.
    """
    field_id_str = str(field_id)
    assert_field_access(field_id_str, supabase)

    logger.info("Starting enrichment for field=%s user=%s", field_id_str, user.id)
    enrichment_result = await run_enrichment(field_id_str, supabase)

    return {
        "status": "enrichment_complete",
        "field_id": enrichment_result["field_id"],
        "weather_days_upserted": enrichment_result["weather_days_upserted"],
        "soil_profile_saved": enrichment_result["soil_profile_saved"],
        "location_source": enrichment_result["location_source"],
        "warnings": enrichment_result["warnings"],
    }
