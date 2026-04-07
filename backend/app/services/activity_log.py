"""
Field Activity Log service for RegenAI.

Provides business logic for creating, listing, and summarizing field
activities, recording yield history, and calculating Actual Production
History (APH). All database operations use the caller-supplied authenticated
Supabase client so RLS policies remain enforced throughout.
"""

import html
import logging
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException

from app.models.schemas import ActivityCreate, ActivityUpdate, YieldHistoryCreate

logger = logging.getLogger(__name__)

# Maximum years of yield history used for APH calculation (USDA standard).
_APH_MAX_YEARS: int = 10
_APH_MIN_YEARS: int = 4

# Text fields that require sanitization before storage.
_TEXT_FIELDS: frozenset[str] = frozenset(
    {
        "seed_variety",
        "seed_treatment",
        "product_name",
        "rate_unit",
        "target_pest",
        "applicator_name",
        "applicator_license",
        "pest_disease_found",
        "cover_crop_species",
        "notes",
        "operator",
        "equipment_used",
        "crop_type",
    }
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitize_text(value: str | None) -> str | None:
    """HTML-escape a user-supplied text value to prevent XSS/injection.

    Args:
        value: Raw string from request payload.

    Returns:
        Escaped string, or None if value is None.
    """
    if value is None:
        return None
    return html.escape(str(value).strip())


def _sanitize_payload(payload: dict) -> dict:
    """Apply _sanitize_text to every text field in a database payload dict.

    Args:
        payload: Raw key/value dict destined for Supabase.

    Returns:
        New dict with text fields sanitized.
    """
    return {
        k: (_sanitize_text(v) if k in _TEXT_FIELDS and isinstance(v, str) else v)
        for k, v in payload.items()
    }


async def _assert_field_access(field_id: UUID, supabase) -> dict:
    """Fetch the field row and raise HTTP 404 if inaccessible.

    Because the Supabase client carries the user's JWT, RLS silently filters
    rows the user does not own — a missing row therefore signals either
    non-existence or an access denial.

    Args:
        field_id: UUID of the field to check.
        supabase: Authenticated Supabase client.

    Returns:
        The field row dict (id, farm_id, acres, …).

    Raises:
        HTTPException 404: Field not found or not accessible.
    """
    try:
        result = (
            supabase.table("fields")
            .select("id, farm_id, acres, name")
            .eq("id", str(field_id))
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Field not found")
        return result.data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Field not found")


def _validate_activity(data: ActivityCreate, field: dict) -> list[str]:
    """Run domain-level validation rules and return a list of warning strings.

    Hard failures raise HTTPException directly. Soft warnings (e.g. missing
    yield on harvest) are collected and returned so the router can include them
    in the response.

    Args:
        data: Validated ActivityCreate payload.
        field: Field row dict containing at least ``acres``.

    Returns:
        List of non-fatal warning messages (may be empty).

    Raises:
        HTTPException 422: Business rule violation that blocks the operation.
    """
    warnings: list[str] = []
    today = date.today()

    # activity_date cannot be in the future
    if data.activity_date > today:
        raise HTTPException(
            status_code=422,
            detail="activity_date cannot be in the future.",
        )

    # Spray: restricted_use requires applicator credentials
    if data.activity_type.value == "spray" and data.restricted_use:
        if not data.applicator_name or not data.applicator_license:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Restricted-use spray applications require both "
                    "applicator_name and applicator_license."
                ),
            )

    # Harvest: warn if yield not provided
    if data.activity_type.value == "harvest" and data.yield_bu_acre is None:
        warnings.append(
            "Harvest activity recorded without yield_bu_acre. "
            "Consider updating this record once yield data is available."
        )

    # acres_applied cannot exceed field's total acres
    field_acres: float | None = field.get("acres")
    if (
        data.acres_applied is not None
        and field_acres is not None
        and data.acres_applied > field_acres
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                f"acres_applied ({data.acres_applied}) exceeds the field's "
                f"total acreage ({field_acres})."
            ),
        )

    return warnings


# ---------------------------------------------------------------------------
# Activity CRUD
# ---------------------------------------------------------------------------


async def create_activity(data: ActivityCreate, supabase) -> tuple[dict, list[str]]:
    """Validate and insert a new field activity record.

    When a harvest activity includes yield_bu_acre, the function also
    auto-upserts a yield_history row for the corresponding crop_year so APH
    calculations stay current without requiring a separate API call.

    Args:
        data: Validated ActivityCreate payload from the router.
        supabase: Authenticated Supabase client (respects RLS).

    Returns:
        Tuple of (activity_row dict, warnings list).

    Raises:
        HTTPException 404: Field not found.
        HTTPException 422: Business rule violation.
        HTTPException 500: Database write failure.
    """
    field = await _assert_field_access(data.field_id, supabase)
    warnings = _validate_activity(data, field)

    now_iso = datetime.now(tz=timezone.utc).isoformat()

    payload: dict = {
        "field_id": str(data.field_id),
        "activity_type": data.activity_type.value,
        "activity_date": data.activity_date.isoformat(),
        "seed_variety": data.seed_variety,
        "seeding_rate": data.seeding_rate,
        "seed_treatment": data.seed_treatment,
        "product_name": data.product_name,
        "rate_per_acre": data.rate_per_acre,
        "rate_unit": data.rate_unit,
        "target_pest": data.target_pest,
        "restricted_use": data.restricted_use,
        "applicator_name": data.applicator_name,
        "applicator_license": data.applicator_license,
        "yield_bu_acre": data.yield_bu_acre,
        "moisture_pct": data.moisture_pct,
        "crop_year": data.crop_year,
        "pest_disease_found": data.pest_disease_found,
        "severity": data.severity.value if data.severity else None,
        "tillage_depth_in": data.tillage_depth_in,
        "cover_crop_species": data.cover_crop_species,
        "notes": data.notes,
        "operator": data.operator,
        "equipment_used": data.equipment_used,
        "cost_per_acre": data.cost_per_acre,
        "acres_applied": data.acres_applied,
        "updated_at": now_iso,
    }

    payload = _sanitize_payload(payload)
    # Remove None values to let DB defaults / nullable columns handle them cleanly.
    payload = {k: v for k, v in payload.items() if v is not None or k in {"restricted_use"}}

    try:
        result = supabase.table("field_activities").insert(payload).execute()
        if not result.data:
            raise RuntimeError("Insert returned no data")
        row: dict = result.data[0]
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "activity_log.create_activity: insert failed field=%s", data.field_id
        )
        raise HTTPException(
            status_code=500, detail="Failed to save activity. Please try again."
        )

    logger.info(
        "activity_log: created activity id=%s type=%s field=%s",
        row.get("id"),
        data.activity_type.value,
        data.field_id,
    )

    # Auto-upsert yield history when harvest has yield data.
    if (
        data.activity_type.value == "harvest"
        and data.yield_bu_acre is not None
        and data.crop_year is not None
    ):
        await _auto_upsert_yield_history(
            field_id=data.field_id,
            crop_year=data.crop_year,
            yield_bu_acre=data.yield_bu_acre,
            moisture_pct=data.moisture_pct,
            acres_harvested=data.acres_applied,
            supabase=supabase,
        )

    return row, warnings


async def list_activities(
    field_id: UUID,
    supabase,
    *,
    activity_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Fetch paginated field activities with optional filters.

    Args:
        field_id: UUID of the field to query.
        supabase: Authenticated Supabase client.
        activity_type: Optional ActivityType value to filter on.
        start_date: Inclusive lower bound on activity_date.
        end_date: Inclusive upper bound on activity_date.
        limit: Maximum rows to return (caller enforces max 200).
        offset: Row offset for pagination.

    Returns:
        Dict with keys ``activities`` (list) and ``total_count`` (int).

    Raises:
        HTTPException 404: Field not found.
        HTTPException 500: Query failure.
    """
    await _assert_field_access(field_id, supabase)

    try:
        # Build the base count query.
        count_q = (
            supabase.table("field_activities")
            .select("id", count="exact")
            .eq("field_id", str(field_id))
        )
        if activity_type:
            count_q = count_q.eq("activity_type", activity_type)
        if start_date:
            count_q = count_q.gte("activity_date", start_date.isoformat())
        if end_date:
            count_q = count_q.lte("activity_date", end_date.isoformat())

        count_result = count_q.execute()
        total_count: int = count_result.count or 0

        # Data query with same filters.
        data_q = (
            supabase.table("field_activities")
            .select("*")
            .eq("field_id", str(field_id))
        )
        if activity_type:
            data_q = data_q.eq("activity_type", activity_type)
        if start_date:
            data_q = data_q.gte("activity_date", start_date.isoformat())
        if end_date:
            data_q = data_q.lte("activity_date", end_date.isoformat())

        data_result = (
            data_q
            .order("activity_date", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        activities: list[dict] = data_result.data or []
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "activity_log.list_activities: query failed field=%s", field_id
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve activities. Please try again."
        )

    return {"activities": activities, "total_count": total_count}


async def get_activity(activity_id: UUID, supabase) -> dict:
    """Fetch a single activity by ID.

    Args:
        activity_id: UUID of the activity record.
        supabase: Authenticated Supabase client.

    Returns:
        Activity row dict.

    Raises:
        HTTPException 404: Activity not found.
    """
    try:
        result = (
            supabase.table("field_activities")
            .select("*")
            .eq("id", str(activity_id))
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Activity not found")
        return result.data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Activity not found")


async def update_activity(
    activity_id: UUID, data: ActivityUpdate, supabase
) -> dict:
    """Apply a partial update to an existing activity.

    Only fields explicitly set in the payload are written; all others remain
    unchanged. activity_date is validated against today if provided.

    Args:
        activity_id: UUID of the activity to update.
        data: Partial update payload.
        supabase: Authenticated Supabase client.

    Returns:
        Updated activity row dict.

    Raises:
        HTTPException 404: Activity not found.
        HTTPException 422: Business rule violation (e.g. future date).
        HTTPException 500: Database write failure.
    """
    # Confirm the record exists and belongs to this user via RLS.
    existing = await get_activity(activity_id, supabase)

    if data.activity_date is not None and data.activity_date > date.today():
        raise HTTPException(
            status_code=422, detail="activity_date cannot be in the future."
        )

    # Re-run spray/restricted_use validation with merged values.
    merged_restricted = (
        data.restricted_use
        if data.restricted_use is not None
        else existing.get("restricted_use", False)
    )
    merged_type = data.activity_type.value if data.activity_type else existing.get("activity_type")
    merged_applicator_name = data.applicator_name or existing.get("applicator_name")
    merged_applicator_license = data.applicator_license or existing.get("applicator_license")

    if merged_type == "spray" and merged_restricted:
        if not merged_applicator_name or not merged_applicator_license:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Restricted-use spray applications require both "
                    "applicator_name and applicator_license."
                ),
            )

    # Check acres_applied against field acreage if being updated.
    if data.acres_applied is not None:
        field_id = existing.get("field_id")
        if field_id:
            try:
                field_result = (
                    supabase.table("fields")
                    .select("acres")
                    .eq("id", field_id)
                    .single()
                    .execute()
                )
                field_acres = field_result.data.get("acres") if field_result.data else None
                if field_acres is not None and data.acres_applied > field_acres:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"acres_applied ({data.acres_applied}) exceeds the field's "
                            f"total acreage ({field_acres})."
                        ),
                    )
            except HTTPException:
                raise
            except Exception:
                pass  # Non-critical; proceed without acres validation.

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    raw_updates: dict = {
        k: v for k, v in data.model_dump(exclude_unset=True).items()
    }

    if "activity_type" in raw_updates:
        raw_updates["activity_type"] = raw_updates["activity_type"].value if hasattr(raw_updates["activity_type"], "value") else raw_updates["activity_type"]
    if "severity" in raw_updates and raw_updates["severity"] is not None:
        raw_updates["severity"] = raw_updates["severity"].value if hasattr(raw_updates["severity"], "value") else raw_updates["severity"]
    if "activity_date" in raw_updates and raw_updates["activity_date"] is not None:
        raw_updates["activity_date"] = raw_updates["activity_date"].isoformat()

    raw_updates["updated_at"] = now_iso
    updates = _sanitize_payload(raw_updates)

    try:
        result = (
            supabase.table("field_activities")
            .update(updates)
            .eq("id", str(activity_id))
            .execute()
        )
        if not result.data:
            raise RuntimeError("Update returned no data")
        return result.data[0]
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "activity_log.update_activity: update failed id=%s", activity_id
        )
        raise HTTPException(
            status_code=500, detail="Failed to update activity. Please try again."
        )


async def delete_activity(activity_id: UUID, supabase) -> None:
    """Delete an activity record.

    Args:
        activity_id: UUID of the activity to delete.
        supabase: Authenticated Supabase client.

    Raises:
        HTTPException 404: Activity not found.
        HTTPException 500: Database delete failure.
    """
    await get_activity(activity_id, supabase)  # confirm existence via RLS

    try:
        supabase.table("field_activities").delete().eq("id", str(activity_id)).execute()
    except Exception:
        logger.exception(
            "activity_log.delete_activity: delete failed id=%s", activity_id
        )
        raise HTTPException(
            status_code=500, detail="Failed to delete activity. Please try again."
        )

    logger.info("activity_log: deleted activity id=%s", activity_id)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


async def get_activity_summary(farm_id: UUID, supabase) -> dict:
    """Return aggregate activity stats for all fields on a farm.

    Provides a count of activities by type and the most recent activity date
    per field. Useful for dashboard overview cards.

    Args:
        farm_id: UUID of the farm.
        supabase: Authenticated Supabase client.

    Returns:
        Dict with ``farm_id``, ``count_by_type`` (dict), ``last_activity_per_field``
        (list), and ``total_activities`` (int).

    Raises:
        HTTPException 404: Farm not found or inaccessible.
        HTTPException 500: Query failure.
    """
    # Verify farm access via RLS.
    try:
        farm_result = (
            supabase.table("farms")
            .select("id")
            .eq("id", str(farm_id))
            .single()
            .execute()
        )
        if not farm_result.data:
            raise HTTPException(status_code=404, detail="Farm not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Farm not found")

    # Fetch all field IDs for this farm.
    try:
        fields_result = (
            supabase.table("fields")
            .select("id, name")
            .eq("farm_id", str(farm_id))
            .execute()
        )
        fields: list[dict] = fields_result.data or []
    except Exception:
        logger.exception(
            "activity_log.get_activity_summary: failed to fetch fields farm=%s", farm_id
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve farm data. Please try again."
        )

    field_ids: list[str] = [f["id"] for f in fields]
    field_name_map: dict[str, str] = {f["id"]: f["name"] for f in fields}

    if not field_ids:
        return {
            "farm_id": str(farm_id),
            "total_activities": 0,
            "count_by_type": {},
            "last_activity_per_field": [],
        }

    try:
        activities_result = (
            supabase.table("field_activities")
            .select("id, field_id, activity_type, activity_date")
            .in_("field_id", field_ids)
            .execute()
        )
        activities: list[dict] = activities_result.data or []
    except Exception:
        logger.exception(
            "activity_log.get_activity_summary: failed to fetch activities farm=%s",
            farm_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve activity data. Please try again.",
        )

    # Aggregate count by type.
    count_by_type: dict[str, int] = {}
    last_date_per_field: dict[str, str] = {}

    for act in activities:
        atype = act.get("activity_type", "other")
        count_by_type[atype] = count_by_type.get(atype, 0) + 1

        fid = act.get("field_id", "")
        adate = act.get("activity_date", "")
        if fid and adate:
            existing = last_date_per_field.get(fid)
            if existing is None or adate > existing:
                last_date_per_field[fid] = adate

    last_activity_per_field = [
        {
            "field_id": fid,
            "field_name": field_name_map.get(fid, ""),
            "last_activity_date": last_date,
        }
        for fid, last_date in sorted(
            last_date_per_field.items(), key=lambda x: x[1], reverse=True
        )
    ]

    return {
        "farm_id": str(farm_id),
        "total_activities": len(activities),
        "count_by_type": count_by_type,
        "last_activity_per_field": last_activity_per_field,
    }


# ---------------------------------------------------------------------------
# Yield History
# ---------------------------------------------------------------------------


async def create_yield_history(data: YieldHistoryCreate, supabase) -> dict:
    """Insert or update a yield history record for a field+year.

    Uses upsert on (field_id, crop_year) so duplicate entries from the
    harvest auto-sync do not cause errors.

    Args:
        data: Validated YieldHistoryCreate payload.
        supabase: Authenticated Supabase client.

    Returns:
        Yield history row dict.

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
        if not result.data:
            raise RuntimeError("Upsert returned no data")
        return result.data[0]
    except Exception:
        logger.exception(
            "activity_log.create_yield_history: upsert failed field=%s year=%s",
            data.field_id,
            data.crop_year,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to save yield history. Please try again.",
        )


async def list_yield_history(field_id: UUID, supabase) -> list[dict]:
    """Return all yield history records for a field, newest year first.

    Args:
        field_id: UUID of the field.
        supabase: Authenticated Supabase client.

    Returns:
        List of yield history row dicts ordered by crop_year descending.

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
        return result.data or []
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "activity_log.list_yield_history: query failed field=%s", field_id
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve yield history. Please try again.",
        )


async def calculate_aph(field_id: UUID, supabase) -> dict:
    """Calculate the Actual Production History (APH) yield for a field.

    Uses up to the 10 most recent crop years (USDA FSA standard). Requires
    at least 4 years of data; returns an error if fewer are available.

    Args:
        field_id: UUID of the field.
        supabase: Authenticated Supabase client.

    Returns:
        Dict with ``aph_yield``, ``years_used``, ``year_range``, ``field_id``,
        and ``records`` (individual year data).

    Raises:
        HTTPException 404: Field not found.
        HTTPException 422: Fewer than 4 years of yield data available.
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


# ---------------------------------------------------------------------------
# Internal: harvest auto-sync
# ---------------------------------------------------------------------------


async def _auto_upsert_yield_history(
    *,
    field_id: UUID,
    crop_year: int,
    yield_bu_acre: float,
    moisture_pct: float | None,
    acres_harvested: float | None,
    supabase,
) -> None:
    """Silently upsert a yield_history row when a harvest activity is logged.

    Failures are logged but do not propagate — the harvest activity has already
    been committed at this point and a yield_history sync failure should not
    roll back a successful activity creation.

    Args:
        field_id: UUID of the harvested field.
        crop_year: Four-digit crop year.
        yield_bu_acre: Recorded yield in bushels per acre.
        moisture_pct: Optional grain moisture percentage.
        acres_harvested: Optional acres harvested (from acres_applied).
        supabase: Authenticated Supabase client.
    """
    payload: dict = {
        "field_id": str(field_id),
        "crop_year": crop_year,
        "yield_bu_acre": yield_bu_acre,
    }
    if moisture_pct is not None:
        payload["moisture_pct"] = moisture_pct
    if acres_harvested is not None:
        payload["acres_harvested"] = acres_harvested

    try:
        supabase.table("yield_history").upsert(
            payload, on_conflict="field_id,crop_year"
        ).execute()
        logger.info(
            "activity_log: auto-synced yield_history field=%s year=%s yield=%.2f",
            field_id,
            crop_year,
            yield_bu_acre,
        )
    except Exception:
        logger.warning(
            "activity_log: auto-sync to yield_history failed field=%s year=%s "
            "(non-fatal — activity was saved successfully)",
            field_id,
            crop_year,
        )
