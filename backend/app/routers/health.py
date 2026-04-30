import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from supabase import create_client

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Return service health with a lightweight Supabase connectivity check."""
    checks = {"supabase": "unknown"}
    healthy = True

    try:
        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        client.table("eqip_practices").select("code").limit(1).execute()
        checks["supabase"] = "ok"
    except Exception:
        logger.warning("Health check: Supabase connectivity failed")
        checks["supabase"] = "error"
        healthy = False

    if healthy:
        return {"status": "healthy", "service": "regenai-api", "checks": checks}
    return JSONResponse(
        status_code=503,
        content={"status": "degraded", "service": "regenai-api", "checks": checks},
    )
