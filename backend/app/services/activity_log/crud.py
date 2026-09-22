"""Create, read, update and delete for field activities."""

from datetime import date

from fastapi import HTTPException
from postgrest.exceptions import APIError

from app.models.schemas import ActivityCreate, ActivityUpdate
from app.services.activity_log.common import _NOT_NULL_UPDATE_FIELDS, logger
from app.services.activity_log.helpers import (
    _apply_filters,
    _assert_field_access,
    _check_rules,
    _from_columns,
    _sanitize_payload,
    _select_one,
    _to_columns,
    _utcnow,
)
from app.services.activity_log.yield_history import _auto_upsert_yield_history


async def create_activity(data: ActivityCreate, supabase) -> tuple[dict, list[str]]:
    """Validate and insert a new field activity record.

    When a harvest activity includes yield_bu_acre and crop_year, a
    yield_history row is also upserted so APH stays current. A failed sync is
    non-fatal and reported in the returned warnings.

    Returns:
        Tuple of (activity row with API field names, warnings list).

    Raises:
        HTTPException 404: Field not found.
        HTTPException 422: Business rule violation.
        HTTPException 500: Database write failure.
    """
    field = await _assert_field_access(data.field_id, supabase)
    activity_type = data.activity_type.value

    _check_rules(
        activity_type=activity_type,
        activity_date=data.activity_date,
        restricted_use=data.restricted_use,
        applicator_name=data.applicator_name,
        applicator_license=data.applicator_license,
        acres_applied=data.acres_applied,
        field_acres=field.get("acres"),
    )

    warnings: list[str] = []
    if activity_type == "harvest" and data.yield_bu_acre is None:
        warnings.append(
            "Harvest activity recorded without yield_bu_acre. "
            "Consider updating this record once yield data is available."
        )

    payload = data.model_dump(mode="json", exclude_none=True)
    payload["updated_at"] = _utcnow().isoformat()
    payload["restricted_use"] = data.restricted_use
    payload = _to_columns(_sanitize_payload(payload))

    try:
        result = supabase.table("field_activities").insert(payload).execute()
    except APIError as exc:
        logger.error(
            "activity_log.create_activity: insert failed field=%s error=%s",
            data.field_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to save activity. Please try again.")
    if not result.data:
        logger.error("activity_log.create_activity: insert returned no row field=%s", data.field_id)
        raise HTTPException(status_code=500, detail="Failed to save activity. Please try again.")

    row = _from_columns(result.data[0])
    logger.info(
        "activity_log: created activity id=%s type=%s field=%s",
        row.get("id"),
        activity_type,
        data.field_id,
    )

    if activity_type == "harvest" and data.yield_bu_acre is not None and data.crop_year:
        sync_warning = await _auto_upsert_yield_history(
            field_id=data.field_id,
            crop_year=data.crop_year,
            crop_type=field.get("crop_type"),
            yield_bu_acre=data.yield_bu_acre,
            moisture_pct=data.moisture_pct,
            acres_harvested=data.acres_applied,
            supabase=supabase,
        )
        if sync_warning:
            warnings.append(sync_warning)

    return row, warnings


async def list_activities(
    field_id: str,
    supabase,
    *,
    activity_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Fetch paginated field activities with optional filters.

    Returns:
        Dict with keys ``activities`` (list) and ``total_count`` (int).

    Raises:
        HTTPException 404: Field not found.
        HTTPException 500: Query failure.
    """
    await _assert_field_access(field_id, supabase)
    field_id_str = str(field_id)
    filters = {"activity_type": activity_type, "start_date": start_date, "end_date": end_date}

    try:
        count_result = _apply_filters(
            supabase.table("field_activities").select("id", count="exact"),
            field_id_str,
            **filters,
        ).execute()
        data_result = (
            _apply_filters(
                supabase.table("field_activities").select("*"), field_id_str, **filters
            )
            .order("activity_date", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
    except APIError as exc:
        logger.error(
            "activity_log.list_activities: query failed field=%s error=%s",
            field_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve activities. Please try again."
        )

    return {
        "activities": [_from_columns(row) for row in data_result.data or []],
        "total_count": count_result.count or 0,
    }


async def get_activity(activity_id: str, supabase) -> dict:
    """Fetch a single activity by ID (API field names).

    Raises:
        HTTPException 404: Activity not found.
        HTTPException 500: Database error.
    """
    activity_id_str = str(activity_id)
    query = supabase.table("field_activities").select("*").eq("id", activity_id_str)
    return _from_columns(_select_one(query, entity="Activity", entity_id=activity_id_str))


async def _field_acres_for_update(field_id: str, activity_id: str, supabase) -> float | None:
    """Return the field's acreage for the acres_applied rule, or None if unavailable.

    The activity itself was already found, so a failed field lookup should not
    block the update; it is logged and the acreage rule is skipped.
    """
    try:
        field = await _assert_field_access(field_id, supabase)
    except HTTPException as exc:
        logger.warning(
            "activity_log.update_activity: acreage check skipped activity=%s field=%s "
            "error=%s",
            activity_id,
            field_id,
            exc.detail,
        )
        return None
    return field.get("acres")


async def update_activity(activity_id: str, data: ActivityUpdate, supabase) -> dict:
    """Apply a partial update to an existing activity.

    Only fields explicitly set in the payload are written. The shared rules are
    re-checked against the merged existing + updated values.

    Raises:
        HTTPException 404: Activity not found.
        HTTPException 422: Business rule violation (e.g. future date).
        HTTPException 500: Database write failure.
    """
    activity_id_str = str(activity_id)
    existing = await get_activity(activity_id, supabase)
    updates = data.model_dump(mode="json", exclude_unset=True)

    # These columns are NOT NULL; an explicit null in a PATCH means "unchanged".
    for not_null_field in _NOT_NULL_UPDATE_FIELDS:
        if not_null_field in updates and updates[not_null_field] is None:
            del updates[not_null_field]

    field_acres = None
    if data.acres_applied is not None and existing.get("field_id"):
        field_acres = await _field_acres_for_update(
            existing["field_id"], activity_id_str, supabase
        )

    _check_rules(
        activity_type=updates.get("activity_type", existing.get("activity_type")),
        activity_date=data.activity_date,
        restricted_use=updates.get("restricted_use", existing.get("restricted_use", False)),
        applicator_name=data.applicator_name or existing.get("applicator_name"),
        applicator_license=data.applicator_license or existing.get("applicator_license"),
        acres_applied=data.acres_applied,
        field_acres=field_acres,
    )

    updates["updated_at"] = _utcnow().isoformat()
    payload = _to_columns(_sanitize_payload(updates))

    try:
        result = (
            supabase.table("field_activities")
            .update(payload)
            .eq("id", activity_id_str)
            .execute()
        )
    except APIError as exc:
        logger.error(
            "activity_log.update_activity: update failed id=%s error=%s",
            activity_id_str,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to update activity. Please try again."
        )
    if not result.data:
        # The row was visible a moment ago; zero updated rows means it vanished.
        raise HTTPException(status_code=404, detail="Activity not found")
    return _from_columns(result.data[0])


async def delete_activity(activity_id: str, supabase) -> None:
    """Delete an activity record.

    Raises:
        HTTPException 404: Activity not found.
        HTTPException 500: Database delete failure.
    """
    await get_activity(activity_id, supabase)  # confirm existence via RLS

    try:
        supabase.table("field_activities").delete().eq("id", str(activity_id)).execute()
    except APIError as exc:
        logger.error(
            "activity_log.delete_activity: delete failed id=%s error=%s",
            activity_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to delete activity. Please try again."
        )

    logger.info("activity_log: deleted activity id=%s", activity_id)
