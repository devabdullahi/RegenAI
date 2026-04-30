import logging
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from app.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer()


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Return a cached Supabase anon client (user-scoped, respects RLS).

    lru_cache(maxsize=1) ensures a single client is created per process,
    avoiding connection pool exhaustion from per-request instantiation.
    """
    return create_client(settings.supabase_url, settings.supabase_anon_key)


@lru_cache(maxsize=1)
def get_admin_client() -> Client:
    """Return a cached Supabase service-role client (bypasses RLS).

    Only use in admin scripts — NEVER expose through request handlers.
    lru_cache(maxsize=1) ensures a single client is created per process.
    """
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Validate the Supabase JWT and return the user.

    Raises:
        HTTPException 503 — network/timeout errors reaching Supabase.
        HTTPException 401 — token is invalid or expired.
    """
    supabase = get_supabase_client()
    token = credentials.credentials

    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return user_response.user

    except HTTPException:
        raise

    except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
        logger.exception("Supabase auth request failed due to connectivity issue: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Authentication service temporarily unavailable. Please retry.",
        )

    except Exception as exc:
        logger.exception("Unexpected error during token validation: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_authenticated_client(
    user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Client:
    """Return a Supabase client authenticated with the user's JWT for this request.

    Reuses the process-level cached anon client from get_supabase_client()
    rather than calling create_client() on every request, which avoids
    per-request connection pool exhaustion. Only the session token is updated
    per-request so RLS policies remain user-scoped.

    Depends on get_current_user so the token is fully validated before the
    session is applied. All queries through this client respect RLS policies.
    """
    supabase = get_supabase_client()
    supabase.auth.set_session(credentials.credentials, "")
    return supabase
