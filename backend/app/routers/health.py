"""
Health router for RegenAI: unversioned GET /health for load balancers.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.auth.middleware import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Return service health with a lightweight Supabase connectivity check."""
    checks = {"supabase": "unknown"}
    healthy = True

    try:
        # Reuse the process-level cached anon client — no new connections needed
        # for a health probe.  The anon client has public read access to the
        # eqip_practices reference table which is sufficient to confirm that
        # the Supabase PostgREST endpoint is reachable.
        client = get_supabase_client()
        client.table("eqip_practices").select("code").limit(1).execute()
        checks["supabase"] = "ok"
    except Exception as exc:
        # Intentionally non-fatal: the probe reports 503 instead of crashing.
        logger.warning("Health check: Supabase connectivity failed error=%s", exc)
        checks["supabase"] = "error"
        healthy = False

    if healthy:
        return {"status": "healthy", "service": "regenai-api", "checks": checks}
    return JSONResponse(
        status_code=503,
        content={"status": "degraded", "service": "regenai-api", "checks": checks},
    )
