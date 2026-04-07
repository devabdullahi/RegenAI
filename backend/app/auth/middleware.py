from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client

from app.config import settings

security = HTTPBearer()


def get_supabase_client():
    """Create a Supabase client with the anon key (user-scoped, respects RLS)."""
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def get_admin_client():
    """Create a Supabase client with the service role key (bypasses RLS).
    Only use in admin scripts — NEVER in request handlers."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Validate the Supabase JWT and return the user.
    Uses anon key client to respect RLS policies."""
    supabase = get_supabase_client()
    token = credentials.credentials

    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return user_response.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_authenticated_client(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Return a Supabase client authenticated with the user's JWT.
    All queries through this client respect RLS policies."""
    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    supabase.auth.set_session(credentials.credentials, "")
    return supabase
