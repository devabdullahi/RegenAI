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
    """Return a cached Supabase anon client for non-authenticated operations
    such as the health check endpoint.

    Do NOT use this client in request handlers that need user-scoped RLS
    enforcement — use get_authenticated_client() instead, which creates a
    fresh client per request to prevent cross-request session contamination.
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

    Uses the cached anon client only for the auth.get_user() call, which is
    safe because get_user() is stateless — it sends the token to Supabase
    and returns a result without mutating the client's session state.

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
    """Return a fresh Supabase client authenticated with the user's JWT.

    A new client is created on every request rather than reusing the cached
    singleton from get_supabase_client(). This prevents a race condition
    where concurrent requests would call set_session() on the same shared
    client object, potentially running user A's database query with user B's
    token and bypassing Row Level Security isolation.

    The performance trade-off (one extra create_client() call per request) is
    intentional and necessary for security. create_client() is lightweight —
    it does not open a network connection; connections are established lazily
    by the underlying httpx client when the first query executes.

    Depends on get_current_user so the token is fully validated before the
    session is applied to the new client. All queries through the returned
    client respect RLS policies scoped to the authenticated user.
    """
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    # Set the Authorization header directly on the PostgREST sub-client so
    # that all database queries are scoped to this user's JWT and RLS policies
    # are enforced correctly.  Calling set_session() with an empty refresh
    # token can cause auth failures; this approach is safer and avoids
    # mutating the shared auth state on the client object.
    client.postgrest.auth(credentials.credentials)
    return client
