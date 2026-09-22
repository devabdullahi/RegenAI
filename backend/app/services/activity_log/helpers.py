"""Internal helpers.

The pinnable clock, payload sanitising, API-to-column mapping, field
access checks and list filters.
"""

import html
from datetime import date, datetime, timezone

from fastapi import HTTPException
from postgrest.exceptions import APIError

from app.auth.access import PGRST_NO_ROWS
from app.services.activity_log.common import _API_TO_COLUMN, _TEXT_FIELDS, logger


def _utcnow() -> datetime:
    """Current UTC time."""
    return datetime.now(tz=timezone.utc)


def _today() -> date:
    """Today's date, used for the no-future-dates rule."""
    return date.today()


def _sanitize_text(value: str | None) -> str | None:
    """HTML-escape a user-supplied text value to prevent XSS/injection."""
    if value is None:
        return None
    return html.escape(str(value).strip())


def _sanitize_payload(payload: dict) -> dict:
    """Apply _sanitize_text to every text field in a payload dict."""
    return {
        k: (_sanitize_text(v) if k in _TEXT_FIELDS and isinstance(v, str) else v)
        for k, v in payload.items()
    }


def _to_columns(payload: dict) -> dict:
    """Rename API field names to their field_activities column names."""
    return {_API_TO_COLUMN.get(k, k): v for k, v in payload.items()}


def _from_columns(row: dict) -> dict:
    """Expose column values under their API field names."""
    mapped = dict(row)
    for api_name, column in _API_TO_COLUMN.items():
        if column in mapped:
            mapped[api_name] = mapped.pop(column)
    return mapped


def _select_one(query, *, entity: str, entity_id: str) -> dict:
    """Execute a ``.single()`` query, mapping zero rows to 404.

    Raises:
        HTTPException 404: no row (missing or hidden by RLS).
        HTTPException 500: any other database error.
    """
    try:
        result = query.single().execute()
    except APIError as exc:
        if exc.code == PGRST_NO_ROWS:
            raise HTTPException(status_code=404, detail=f"{entity} not found")
        logger.error(
            "activity_log: %s lookup failed id=%s error=%s",
            entity.lower(),
            entity_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to load {entity.lower()}.")
    if not result.data:
        raise HTTPException(status_code=404, detail=f"{entity} not found")
    return result.data


async def _assert_field_access(field_id: str, supabase) -> dict:
    """Fetch the field row (id, farm_id, acres, name, crop_type) or raise 404.

    Because the Supabase client carries the user's JWT, RLS silently filters
    rows the user does not own, so a missing row means "not found or not yours".
    """
    field_id_str = str(field_id)
    query = (
        supabase.table("fields")
        .select("id, farm_id, acres, name, crop_type")
        .eq("id", field_id_str)
    )
    return _select_one(query, entity="Field", entity_id=field_id_str)


def _check_rules(
    *,
    activity_type: str | None,
    activity_date: date | None,
    restricted_use: bool,
    applicator_name: str | None,
    applicator_license: str | None,
    acres_applied: float | None,
    field_acres: float | None,
) -> None:
    """Enforce hard business rules shared by create and update.

    Raises:
        HTTPException 422: future date, restricted-use spray without applicator
            credentials, or acres_applied above the field's acreage.
    """
    if activity_date is not None and activity_date > _today():
        raise HTTPException(status_code=422, detail="activity_date cannot be in the future.")

    # FIFRA: restricted-use pesticide records must name a certified applicator.
    if activity_type == "spray" and restricted_use:
        if not applicator_name or not applicator_license:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Restricted-use spray applications require both "
                    "applicator_name and applicator_license."
                ),
            )

    if acres_applied is not None and field_acres is not None and acres_applied > field_acres:
        raise HTTPException(
            status_code=422,
            detail=(
                f"acres_applied ({acres_applied}) exceeds the field's "
                f"total acreage ({field_acres})."
            ),
        )


def _apply_filters(
    query,
    field_id: str,
    *,
    activity_type: str | None,
    start_date: date | None,
    end_date: date | None,
):
    """Apply the shared field/type/date filters to a field_activities query."""
    query = query.eq("field_id", field_id)
    if activity_type:
        query = query.eq("activity_type", activity_type)
    if start_date:
        query = query.gte("activity_date", start_date.isoformat())
    if end_date:
        query = query.lte("activity_date", end_date.isoformat())
    return query
