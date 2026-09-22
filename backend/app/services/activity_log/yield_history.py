"""Yield history records and the APH calculation, plus the harvest auto-sync."""

from uuid import UUID

import httpx
from fastapi import HTTPException
from postgrest.exceptions import APIError

from app.models.schemas import YieldHistoryCreate
from app.services.activity_log.common import _APH_MAX_YEARS, _APH_MIN_YEARS, logger
from app.services.activity_log.helpers import _assert_field_access, _sanitize_text


async def create_yield_history(data: YieldHistoryCreate, supabase) -> dict:
    """Insert or update a yield history record for a field+year.

    Uses upsert on (field_id, crop_year) so duplicate entries from the
    harvest auto-sync do not cause errors.

    Raises:
        HTTPException 404: Field not found.
        HTTPException 500: Database write failure.
    """
    await _assert_field_access(data.field_id, supabase)

    payload: dict = {
        "field_id": str(data.field_id),
        "crop_year": data.crop_year,
        "crop_type": _sanitize_text(data.crop_type),
        "yield_bu_acre": data.yield_bu_acre,
        "moisture_pct": data.moisture_pct,
        "acres_harvested": data.acres_harvested,
        "notes": _sanitize_text(data.notes),
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        result = (
            supabase.table("yield_history")
            .upsert(payload, on_conflict="field_id,crop_year")
            .execute()
        )
    except APIError as exc:
        logger.error(
            "activity_log.create_yield_history: upsert failed field=%s year=%s error=%s",
            data.field_id,
            data.crop_year,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to save yield history. Please try again.",
        )
    if not result.data:
        logger.error(
            "activity_log.create_yield_history: upsert returned no row field=%s year=%s",
            data.field_id,
            data.crop_year,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to save yield history. Please try again.",
        )
    return result.data[0]


async def list_yield_history(field_id: str, supabase) -> list[dict]:
    """Return all yield history records for a field, newest year first.

    Raises:
        HTTPException 404: Field not found.
        HTTPException 500: Query failure.
    """
    await _assert_field_access(field_id, supabase)

    try:
        result = (
            supabase.table("yield_history")
            .select("*")
            .eq("field_id", str(field_id))
            .order("crop_year", desc=True)
            .execute()
        )
    except APIError as exc:
        logger.error(
            "activity_log.list_yield_history: query failed field=%s error=%s",
            field_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve yield history. Please try again.",
        )
    return result.data or []


async def calculate_aph(field_id: str, supabase) -> dict:
    """Calculate the Actual Production History (APH) yield for a field.

    Simple average of the most recent crop years, bounded by
    ``APH_MIN_YIELD_YEARS`` / ``APH_MAX_YIELD_YEARS`` (7 CFR 400.55).

    Raises:
        HTTPException 404: Field not found.
        HTTPException 422: Fewer than the minimum years of yield data available.
        HTTPException 500: Query failure.
    """
    rows: list[dict] = await list_yield_history(field_id, supabase)

    # Take the _APH_MAX_YEARS most recent entries (already ordered DESC).
    qualifying = rows[:_APH_MAX_YEARS]

    if len(qualifying) < _APH_MIN_YEARS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"APH calculation requires at least {_APH_MIN_YEARS} years of yield data. "
                f"Only {len(qualifying)} year(s) found for this field."
            ),
        )

    yields: list[float] = [r["yield_bu_acre"] for r in qualifying]
    aph_yield: float = round(sum(yields) / len(yields), 2)

    years: list[int] = sorted([r["crop_year"] for r in qualifying])
    year_range = f"{years[0]}–{years[-1]}"

    logger.info(
        "activity_log.calculate_aph: field=%s aph=%.2f years=%d",
        field_id,
        aph_yield,
        len(qualifying),
    )

    return {
        "field_id": str(field_id),
        "aph_yield": aph_yield,
        "years_used": len(qualifying),
        "year_range": year_range,
        "records": qualifying,
    }


async def _auto_upsert_yield_history(
    *,
    field_id: UUID,
    crop_year: int,
    crop_type: str | None,
    yield_bu_acre: float,
    moisture_pct: float | None,
    acres_harvested: float | None,
    supabase,
) -> str | None:
    """Upsert a yield_history row for a logged harvest.

    Non-fatal: the harvest activity is already saved, so a sync failure is
    logged and returned as a warning instead of rolling back the activity.

    Returns:
        A warning message if the sync did not happen, else None.
    """
    failure_warning = (
        f"Harvest saved, but yield history for {crop_year} was not updated. "
        "Add it on the yield history page."
    )
    # yield_history.crop_type is NOT NULL; the harvest payload has no crop, so
    # it comes from the field.
    if not crop_type:
        logger.warning(
            "activity_log: yield_history sync skipped field=%s year=%s reason=no crop_type",
            field_id,
            crop_year,
        )
        return failure_warning

    payload: dict = {
        "field_id": str(field_id),
        "crop_year": crop_year,
        "crop_type": crop_type,
        "yield_bu_acre": yield_bu_acre,
    }
    if moisture_pct is not None:
        payload["moisture_pct"] = moisture_pct
    if acres_harvested is not None:
        payload["acres_harvested"] = acres_harvested

    try:
        supabase.table("yield_history").upsert(payload, on_conflict="field_id,crop_year").execute()
    except (APIError, httpx.HTTPError) as exc:
        logger.warning(
            "activity_log: yield_history sync failed field=%s year=%s error=%s "
            "(non-fatal, activity was saved)",
            field_id,
            crop_year,
            exc,
            exc_info=True,
        )
        return failure_warning

    logger.info(
        "activity_log: auto-synced yield_history field=%s year=%s yield=%.2f",
        field_id,
        crop_year,
        yield_bu_acre,
    )
    return None
