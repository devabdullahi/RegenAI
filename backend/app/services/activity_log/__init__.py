"""
Field Activity Log service for RegenAI.

Provides business logic for creating, listing, and summarizing field
activities, recording yield history, and calculating Actual Production
History (APH). All database operations use the caller-supplied authenticated
Supabase client so RLS policies remain enforced throughout.

API vs. column names: the API field ``pest_disease_found`` is stored in the
``field_activities.pest_name`` column (migration 005). It is renamed on write
and mapped back on read so the public contract stays unchanged.
"""

# Re-exported so ``app.services.activity_log`` keeps its original import surface.
# The definitions now live in the sibling modules listed below.

from app.services.activity_log.common import (
    logger,
)
from app.services.activity_log.crud import (
    create_activity,
    delete_activity,
    get_activity,
    list_activities,
    update_activity,
)
from app.services.activity_log.summary import (
    get_activity_summary,
)
from app.services.activity_log.yield_history import (
    calculate_aph,
    create_yield_history,
    list_yield_history,
)

__all__ = [
    "calculate_aph",
    "create_activity",
    "create_yield_history",
    "delete_activity",
    "get_activity",
    "get_activity_summary",
    "list_activities",
    "list_yield_history",
    "logger",
    "update_activity",
]
