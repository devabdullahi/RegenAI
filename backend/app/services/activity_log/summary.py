"""Per-field activity summary for a farm."""

from fastapi import HTTPException
from postgrest.exceptions import APIError

from app.auth.access import assert_farm_access
from app.services.activity_log.common import logger


async def get_activity_summary(farm_id: str, supabase) -> dict:
    """Return aggregate activity stats for all fields on a farm.

    Returns:
        Dict with ``farm_id``, ``count_by_type`` (dict), ``last_activity_per_field``
        (list), and ``total_activities`` (int).

    Raises:
        HTTPException 404: Farm not found or inaccessible.
        HTTPException 500: Query failure.
    """
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)

    try:
        fields_result = (
            supabase.table("fields").select("id, name").eq("farm_id", farm_id_str).execute()
        )
    except APIError as exc:
        logger.error(
            "activity_log.get_activity_summary: failed to fetch fields farm=%s error=%s",
            farm_id_str,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve farm data. Please try again."
        )

    fields: list[dict] = fields_result.data or []
    if not fields:
        return {
            "farm_id": farm_id_str,
            "total_activities": 0,
            "count_by_type": {},
            "last_activity_per_field": [],
        }

    field_name_map: dict[str, str] = {f["id"]: f["name"] for f in fields}

    try:
        activities_result = (
            supabase.table("field_activities")
            .select("id, field_id, activity_type, activity_date")
            .in_("field_id", list(field_name_map))
            .execute()
        )
    except APIError as exc:
        logger.error(
            "activity_log.get_activity_summary: failed to fetch activities farm=%s error=%s",
            farm_id_str,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve activity data. Please try again.",
        )

    activities: list[dict] = activities_result.data or []
    count_by_type: dict[str, int] = {}
    last_date_per_field: dict[str, str] = {}

    for act in activities:
        activity_type = act.get("activity_type", "other")
        count_by_type[activity_type] = count_by_type.get(activity_type, 0) + 1

        act_field_id = act.get("field_id", "")
        activity_date = act.get("activity_date", "")
        if not act_field_id or not activity_date:
            continue
        previous = last_date_per_field.get(act_field_id)
        if previous is None or activity_date > previous:
            last_date_per_field[act_field_id] = activity_date

    last_activity_per_field = [
        {
            "field_id": act_field_id,
            "field_name": field_name_map.get(act_field_id, ""),
            "last_activity_date": last_date,
        }
        for act_field_id, last_date in sorted(
            last_date_per_field.items(), key=lambda item: item[1], reverse=True
        )
    ]

    return {
        "farm_id": farm_id_str,
        "total_activities": len(activities),
        "count_by_type": count_by_type,
        "last_activity_per_field": last_activity_per_field,
    }
