import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.auth.middleware import get_supabase_client
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Return service health with Supabase, Claude API, and Open-Meteo checks."""
    checks = {"supabase": "unknown", "claude_api": "unknown", "open_meteo": "unknown"}
    healthy = True

    # Supabase connectivity
    try:
        client = get_supabase_client()
        client.table("eqip_practices").select("code").limit(1).execute()
        checks["supabase"] = "ok"
    except Exception:
        logger.warning("Health check: Supabase connectivity failed")
        checks["supabase"] = "error"
        healthy = False

    # Claude API key validity (lightweight check — just verifies the key format)
    if settings.anthropic_api_key and settings.anthropic_api_key.startswith("sk-"):
        checks["claude_api"] = "ok"
    else:
        logger.warning("Health check: Anthropic API key missing or malformed")
        checks["claude_api"] = "error"
        healthy = False

    # Open-Meteo reachability (free weather API used for field recommendations)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&current_weather=true")
            checks["open_meteo"] = "ok" if resp.status_code == 200 else "error"
            if resp.status_code != 200:
                healthy = False
    except Exception:
        logger.warning("Health check: Open-Meteo connectivity failed")
        checks["open_meteo"] = "error"
        healthy = False

    if healthy:
        return {"status": "healthy", "service": "regenai-api", "checks": checks}
    return JSONResponse(
        status_code=503,
        content={"status": "degraded", "service": "regenai-api", "checks": checks},
    )
