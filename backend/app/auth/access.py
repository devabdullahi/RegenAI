"""
Shared ownership checks for request handlers.

The authenticated Supabase client carries the user's JWT, so RLS hides rows
the user does not own. A missing row therefore means "not found or not
yours" and maps to 404; any other database failure is a real error and
maps to 500.
"""

import logging
from uuid import UUID

from fastapi import HTTPException
from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)

# PostgREST code raised by .single() when zero rows match (missing or hidden by RLS).
PGRST_NO_ROWS = "PGRST116"


def assert_field_access(field_id: UUID | str, supabase) -> None:
    """Raise 404 unless the field exists and is visible to the current user.

    Raises:
        HTTPException: 404 if the field is missing or hidden by RLS,
            500 if the lookup itself fails.
    """
    field_id_str = str(field_id)
    try:
        result = (
            supabase.table("fields").select("id").eq("id", field_id_str).limit(1).execute()
        )
    except APIError as exc:
        logger.error("assert_field_access: lookup failed field=%s error=%s", field_id_str, exc)
        raise HTTPException(status_code=500, detail="Failed to verify field access.") from exc

    if not result.data:
        raise HTTPException(status_code=404, detail="Field not found")


def assert_farm_access(farm_id: UUID | str, supabase) -> None:
    """Raise 404 unless the farm exists and is visible to the current user.

    Raises:
        HTTPException: 404 if the farm is missing or hidden by RLS,
            500 if the lookup itself fails.
    """
    farm_id_str = str(farm_id)
    try:
        result = (
            supabase.table("farms").select("id").eq("id", farm_id_str).limit(1).execute()
        )
    except APIError as exc:
        logger.error("assert_farm_access: lookup failed farm=%s error=%s", farm_id_str, exc)
        raise HTTPException(status_code=500, detail="Failed to verify farm access.") from exc

    if not result.data:
        raise HTTPException(status_code=404, detail="Farm not found")
