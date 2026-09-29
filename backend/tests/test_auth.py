"""
Tests for app.auth.middleware — JWT validation and Supabase client factories.

Coverage targets:
  - Valid JWT token → get_current_user returns user object
  - Missing Authorization header → 401 (HTTPBearer handles this)
  - Supabase returning no user → 401
  - Supabase auth raising any exception → 401 (caught, re-raised as 401)
  - get_authenticated_client creates client and sets session with the token
  - get_admin_client creates client using the service role key
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from supabase_auth.errors import AuthApiError

from app.config import settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_cached_clients():
    """get_supabase_client/get_admin_client are lru_cached singletons.

    Clear the caches around every test so a client created (or mocked) by one
    test is never returned to another, which would make the create_client
    patches below ineffective and the tests order-dependent.
    """
    from app.auth.middleware import get_admin_client, get_supabase_client

    get_admin_client.cache_clear()
    get_supabase_client.cache_clear()
    yield
    get_admin_client.cache_clear()
    get_supabase_client.cache_clear()


def _make_credentials(token: str = "valid-jwt-token") -> HTTPAuthorizationCredentials:
    """Build an HTTPAuthorizationCredentials object with the given token."""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _make_user(user_id: str = "user-uuid-abc") -> MagicMock:
    """Build a mock Supabase user object."""
    user = MagicMock()
    user.id = user_id
    user.email = "farmer@example.com"
    return user


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    """Tests for the get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        """A valid JWT that Supabase accepts should return the user object."""
        from app.auth.middleware import get_current_user

        mock_user = _make_user()
        mock_auth_response = MagicMock()
        mock_auth_response.user = mock_user

        mock_supabase = MagicMock()
        mock_supabase.auth.get_user.return_value = mock_auth_response

        credentials = _make_credentials("good-token")
        mock_request = MagicMock()

        with patch("app.auth.middleware.get_supabase_client", return_value=mock_supabase):
            result = await get_current_user(mock_request, credentials)

        assert result is mock_user
        mock_supabase.auth.get_user.assert_called_once_with("good-token")

    @pytest.mark.asyncio
    async def test_supabase_returns_none_user_raises_401(self):
        """When Supabase returns a response with user=None, expect 401."""
        from app.auth.middleware import get_current_user

        mock_auth_response = MagicMock()
        mock_auth_response.user = None

        mock_supabase = MagicMock()
        mock_supabase.auth.get_user.return_value = mock_auth_response

        credentials = _make_credentials("token-with-null-user")
        mock_request = MagicMock()

        with patch("app.auth.middleware.get_supabase_client", return_value=mock_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_supabase_returns_none_response_raises_401(self):
        """When Supabase auth.get_user returns None entirely, expect 401."""
        from app.auth.middleware import get_current_user

        mock_supabase = MagicMock()
        mock_supabase.auth.get_user.return_value = None

        credentials = _make_credentials("bad-token")
        mock_request = MagicMock()

        with patch("app.auth.middleware.get_supabase_client", return_value=mock_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_supabase_auth_exception_raises_401(self):
        """Any exception from Supabase auth must be caught and re-raised as 401."""
        from app.auth.middleware import get_current_user

        mock_supabase = MagicMock()
        mock_supabase.auth.get_user.side_effect = Exception("JWT expired")

        credentials = _make_credentials("expired-token")
        mock_request = MagicMock()

        with patch("app.auth.middleware.get_supabase_client", return_value=mock_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_malformed_token_raises_401(self):
        """A token that Supabase rejects with a ValueError should produce 401."""
        from app.auth.middleware import get_current_user

        mock_supabase = MagicMock()
        mock_supabase.auth.get_user.side_effect = ValueError("malformed JWT segment")

        credentials = _make_credentials("not.a.real.jwt")
        mock_request = MagicMock()

        with patch("app.auth.middleware.get_supabase_client", return_value=mock_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        """Simulates an expired token scenario where Supabase raises."""
        from app.auth.middleware import get_current_user

        mock_supabase = MagicMock()
        mock_supabase.auth.get_user.side_effect = Exception("Token has expired")

        credentials = _make_credentials("expired.jwt.token")
        mock_request = MagicMock()

        with patch("app.auth.middleware.get_supabase_client", return_value=mock_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_401_detail_message(self):
        """The 401 detail should be a human-readable message."""
        from app.auth.middleware import get_current_user

        mock_supabase = MagicMock()
        mock_supabase.auth.get_user.side_effect = Exception("any error")

        credentials = _make_credentials("bad")
        mock_request = MagicMock()

        with patch("app.auth.middleware.get_supabase_client", return_value=mock_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, credentials)

        assert exc_info.value.detail == "Invalid or expired token"

    @pytest.mark.asyncio
    async def test_rejected_token_logs_warning_without_traceback(self, caplog):
        """A token Supabase rejects is a client error: WARNING level, no traceback."""
        from app.auth.middleware import get_current_user

        mock_supabase = MagicMock()
        mock_supabase.auth.get_user.side_effect = AuthApiError("invalid JWT", 401, "bad_jwt")

        with patch("app.auth.middleware.get_supabase_client", return_value=mock_supabase):
            with caplog.at_level(logging.DEBUG, logger="app.auth.middleware"):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(MagicMock(), _make_credentials("bad-token"))

        assert exc_info.value.status_code == 401
        assert [record.levelno for record in caplog.records] == [logging.WARNING]
        assert caplog.records[0].exc_info is None

    @pytest.mark.asyncio
    async def test_unexpected_error_still_logged_with_traceback(self, caplog):
        """Non-auth exceptions remain ERROR-level with a traceback for debugging."""
        from app.auth.middleware import get_current_user

        mock_supabase = MagicMock()
        mock_supabase.auth.get_user.side_effect = RuntimeError("client bug")

        with patch("app.auth.middleware.get_supabase_client", return_value=mock_supabase):
            with caplog.at_level(logging.DEBUG, logger="app.auth.middleware"):
                with pytest.raises(HTTPException):
                    await get_current_user(MagicMock(), _make_credentials("token"))

        assert [record.levelno for record in caplog.records] == [logging.ERROR]
        assert caplog.records[0].exc_info is not None


# ---------------------------------------------------------------------------
# get_authenticated_client
# ---------------------------------------------------------------------------

class TestGetAuthenticatedClient:
    """Tests for the get_authenticated_client dependency."""

    @pytest.mark.asyncio
    async def test_returns_supabase_client(self):
        """get_authenticated_client should return a Supabase client object."""
        from app.auth.middleware import get_authenticated_client

        mock_supabase = MagicMock()
        credentials = _make_credentials("user-jwt")

        with patch("app.auth.middleware.create_client", return_value=mock_supabase):
            result = await get_authenticated_client(user=_make_user(), credentials=credentials)

        assert result is mock_supabase

    @pytest.mark.asyncio
    async def test_scopes_postgrest_to_user_token(self):
        """The user's JWT must be applied to the PostgREST sub-client so RLS is enforced.

        set_session() with an empty refresh token is intentionally no longer used.
        """
        from app.auth.middleware import get_authenticated_client

        mock_supabase = MagicMock()
        token = "the-user-access-token"
        credentials = _make_credentials(token)

        with patch("app.auth.middleware.create_client", return_value=mock_supabase):
            await get_authenticated_client(user=_make_user(), credentials=credentials)

        mock_supabase.postgrest.auth.assert_called_once_with(token)
        mock_supabase.auth.set_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_fresh_client_per_request(self):
        """Each request must get its own client to prevent cross-request token leakage."""
        from app.auth.middleware import get_authenticated_client

        with patch(
            "app.auth.middleware.create_client",
            side_effect=lambda url, key: MagicMock(),
        ) as create_mock:
            first = await get_authenticated_client(
                user=_make_user("user-a"), credentials=_make_credentials("token-a")
            )
            second = await get_authenticated_client(
                user=_make_user("user-b"), credentials=_make_credentials("token-b")
            )

        assert create_mock.call_count == 2
        assert first is not second
        first.postgrest.auth.assert_called_once_with("token-a")
        second.postgrest.auth.assert_called_once_with("token-b")

    @pytest.mark.asyncio
    async def test_uses_anon_key_not_service_role(self):
        """The authenticated client should use the anon key, not the service role key."""
        from app.auth.middleware import get_authenticated_client
        from app.config import settings

        credentials = _make_credentials("token")
        captured_calls = []

        def capture_create_client(url, key):
            captured_calls.append({"url": url, "key": key})
            return MagicMock()

        with patch("app.auth.middleware.create_client", side_effect=capture_create_client):
            await get_authenticated_client(user=_make_user(), credentials=credentials)

        assert len(captured_calls) == 1
        assert captured_calls[0]["key"] == settings.supabase_anon_key
        assert captured_calls[0]["key"] != settings.supabase_service_role_key


# ---------------------------------------------------------------------------
# get_admin_client
# ---------------------------------------------------------------------------

class TestGetAdminClient:
    """Tests for the get_admin_client factory function."""

    def test_returns_supabase_client(self):
        """get_admin_client should return a Supabase client."""
        from app.auth.middleware import get_admin_client

        mock_client = MagicMock()
        with patch("app.auth.middleware.create_client", return_value=mock_client):
            result = get_admin_client()

        assert result is mock_client

    def test_uses_service_role_key(self):
        """The admin client must be created with the service role key."""
        from app.auth.middleware import get_admin_client
        from app.config import settings

        captured_calls = []

        def capture_create_client(url, key):
            captured_calls.append({"url": url, "key": key})
            return MagicMock()

        with patch("app.auth.middleware.create_client", side_effect=capture_create_client):
            get_admin_client()

        assert len(captured_calls) == 1
        assert captured_calls[0]["key"] == settings.supabase_service_role_key

    def test_uses_correct_supabase_url(self):
        """The admin client must connect to the configured Supabase URL."""
        from app.auth.middleware import get_admin_client
        from app.config import settings

        captured_calls = []

        def capture_create_client(url, key):
            captured_calls.append({"url": url, "key": key})
            return MagicMock()

        with patch("app.auth.middleware.create_client", side_effect=capture_create_client):
            get_admin_client()

        assert captured_calls[0]["url"] == settings.supabase_url


# ---------------------------------------------------------------------------
# get_supabase_client (anon factory)
# ---------------------------------------------------------------------------

class TestGetSupabaseClient:
    """Tests for the basic anon-key Supabase client factory."""

    def test_returns_supabase_client(self):
        """get_supabase_client should return a Supabase client."""
        from app.auth.middleware import get_supabase_client

        mock_client = MagicMock()
        with patch("app.auth.middleware.create_client", return_value=mock_client):
            result = get_supabase_client()

        assert result is mock_client

    def test_uses_anon_key(self):
        """The anon client must use the anon key, not the service role key."""
        from app.auth.middleware import get_supabase_client
        from app.config import settings

        captured_calls = []

        def capture_create_client(url, key):
            captured_calls.append({"url": url, "key": key})
            return MagicMock()

        with patch("app.auth.middleware.create_client", side_effect=capture_create_client):
            get_supabase_client()

        assert captured_calls[0]["key"] == settings.supabase_anon_key


@pytest.mark.asyncio
async def test_authenticated_client_scopes_storage_to_the_user_jwt():
    """Storage must carry the user's JWT, not the anon key.

    supabase-py builds the Storage client lazily from options.headers, which
    postgrest.auth() never touches. If only PostgREST is scoped, storage
    requests go out as the anon role and every storage policy (granted TO
    authenticated and keyed on auth.uid()) denies them, so document uploads
    fail. This is a drift guard for that class of bug.
    """
    from app.auth.middleware import get_authenticated_client

    token = "user-jwt-BBB"
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    client = await get_authenticated_client(user=MagicMock(), credentials=credentials)

    def header(headers, name="Authorization"):
        return {k.lower(): v for k, v in dict(headers).items()}.get(name.lower())

    assert header(client.storage._client.headers) == f"Bearer {token}"
    assert header(client.options.headers) == f"Bearer {token}"
    # The project's anon key must still travel as the apikey header.
    assert header(client.options.headers, "apikey") == settings.supabase_anon_key
