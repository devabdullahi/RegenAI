"""
Tests for app.routers.farms — Farm CRUD endpoints.

Coverage targets:
  - POST /api/v1/farms with valid data → 201 + correct response shape
  - POST /api/v1/farms with missing/invalid field → 422
  - GET /api/v1/farms → returns list for the current user
  - GET /api/v1/farms/{id} → returns a single farm; 404 when missing; 422 for non-UUID
  - PATCH /api/v1/farms/{id} partial update → 200; 404 when missing; 400 when empty;
    500 on DB error
  - DELETE /api/v1/farms/{id} → 204; 404 when the farm is not accessible; 500 on DB error

Auth and Supabase are replaced via FastAPI dependency_overrides (patching the
module-level names does not affect dependencies already bound by Depends()).
No real HTTP calls are made.
"""

from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.auth.middleware import get_authenticated_client, get_current_user
from app.main import app

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_BASE = "/api/v1/farms"
_USER_ID = "user-uuid-test-1"
_FARM_ID = "5b0f3c1e-2a4d-4c1e-9b2a-6d7e8f901234"
_MISSING_FARM_ID = "00000000-0000-4000-8000-000000000000"

_VALID_FARM_PAYLOAD = {
    "name": "Sunrise Farm",
    "state": "IA",
    "county_fips": "19153",
    "total_acres": 320.0,
    "goals": "cost_savings",
}

_FARM_DB_ROW = {
    "id": _FARM_ID,
    "user_id": _USER_ID,
    "name": "Sunrise Farm",
    "state": "IA",
    "county_fips": "19153",
    "total_acres": 320.0,
    "goals": "cost_savings",
    "created_at": "2026-01-15T10:00:00+00:00",
}

_NOT_FOUND_ERROR = {
    "message": "JSON object requested, multiple (or no) rows returned",
    "code": "PGRST116",
}


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _mock_user(user_id: str = _USER_ID) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    return user


@pytest.fixture
def make_client():
    """Return a factory that builds a TestClient with auth + Supabase overridden."""

    def _make(supabase: MagicMock, user: MagicMock | None = None) -> TestClient:
        resolved_user = user or _mock_user()
        app.dependency_overrides[get_current_user] = lambda: resolved_user
        app.dependency_overrides[get_authenticated_client] = lambda: supabase
        return TestClient(app)

    try:
        yield _make
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_authenticated_client, None)


def _supabase_with_insert(return_data: list | None) -> MagicMock:
    """table().insert().execute() yields return_data."""
    mock = MagicMock()
    mock.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=return_data
    )
    return mock


def _supabase_with_select(return_data) -> tuple[MagicMock, MagicMock]:
    """table().select().<filters>...execute() yields return_data. Returns (client, chain)."""
    mock = MagicMock()
    chain = MagicMock()
    for method in ("select", "eq", "order", "single", "limit"):
        getattr(chain, method).return_value = chain
    chain.execute.return_value = MagicMock(data=return_data)
    mock.table.return_value = chain
    return mock, chain


def _supabase_with_update(return_data: list | None) -> tuple[MagicMock, MagicMock]:
    """table().update().eq().execute() yields return_data. Returns (client, update_chain)."""
    mock = MagicMock()
    update_chain = MagicMock()
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=return_data)
    mock.table.return_value.update.return_value = update_chain
    return mock, update_chain


def _supabase_for_delete(farm_exists: bool = True) -> tuple[MagicMock, MagicMock]:
    """Access check via select().eq().limit().execute(), then delete().eq().execute()."""
    mock = MagicMock()
    select_exec = mock.table.return_value.select.return_value.eq.return_value.limit.return_value
    select_exec.execute.return_value = MagicMock(data=[{"id": _FARM_ID}] if farm_exists else [])

    delete_chain = MagicMock()
    delete_chain.eq.return_value = delete_chain
    delete_chain.execute.return_value = MagicMock(data=None)
    mock.table.return_value.delete.return_value = delete_chain
    return mock, delete_chain


# ---------------------------------------------------------------------------
# POST /api/v1/farms/
# ---------------------------------------------------------------------------

class TestCreateFarm:
    def test_create_farm_valid_data_returns_201(self, make_client):
        """Valid payload should create a farm and return 201 with the new record."""
        client = make_client(_supabase_with_insert([_FARM_DB_ROW]))

        response = client.post(f"{_BASE}/", json=_VALID_FARM_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == _FARM_ID
        assert body["name"] == "Sunrise Farm"
        assert body["state"] == "IA"

    def test_create_farm_inserts_correct_user_id(self, make_client):
        """The router should set user_id from the authenticated user, not the payload."""
        captured_inserts: list[dict] = []
        mock_supabase = MagicMock()

        def capture_insert(data):
            captured_inserts.append(data)
            chain = MagicMock()
            chain.execute.return_value = MagicMock(
                data=[{**_FARM_DB_ROW, "user_id": "the-real-user-id"}]
            )
            return chain

        mock_supabase.table.return_value.insert.side_effect = capture_insert
        client = make_client(mock_supabase, user=_mock_user("the-real-user-id"))

        client.post(f"{_BASE}/", json={**_VALID_FARM_PAYLOAD, "user_id": "attacker-id"})

        assert len(captured_inserts) == 1
        assert captured_inserts[0]["user_id"] == "the-real-user-id"

    @pytest.mark.parametrize("missing", ["name", "state", "county_fips", "total_acres"])
    def test_create_farm_missing_required_field_returns_422(self, make_client, missing):
        """A payload missing any required field should return 422."""
        mock_supabase = MagicMock()
        client = make_client(mock_supabase)
        payload = {k: v for k, v in _VALID_FARM_PAYLOAD.items() if k != missing}

        response = client.post(f"{_BASE}/", json=payload)

        assert response.status_code == 422
        mock_supabase.table.assert_not_called()

    def test_create_farm_zero_acres_returns_422(self, make_client):
        """total_acres must be > 0; zero should return 422."""
        client = make_client(MagicMock())
        response = client.post(f"{_BASE}/", json={**_VALID_FARM_PAYLOAD, "total_acres": 0})
        assert response.status_code == 422

    def test_create_farm_invalid_state_returns_422(self, make_client):
        """state must be a two-letter uppercase abbreviation."""
        client = make_client(MagicMock())
        response = client.post(f"{_BASE}/", json={**_VALID_FARM_PAYLOAD, "state": "Iowa"})
        assert response.status_code == 422

    def test_create_farm_db_insert_fails_returns_500(self, make_client):
        """When Supabase insert returns no data, the router should return 500."""
        client = make_client(_supabase_with_insert(None))
        response = client.post(f"{_BASE}/", json=_VALID_FARM_PAYLOAD)
        assert response.status_code == 500

    def test_create_farm_api_error_returns_500(self, make_client):
        mock_supabase = _supabase_with_insert(None)
        mock_supabase.table.return_value.insert.return_value.execute.side_effect = APIError(
            {"message": "insert failed", "code": "23514", "hint": None, "details": None}
        )
        response = make_client(mock_supabase).post(f"{_BASE}/", json=_VALID_FARM_PAYLOAD)
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to create farm"

    def test_create_farm_without_goals_field_accepted(self, make_client):
        """goals is optional; payload without it should be accepted."""
        payload = {k: v for k, v in _VALID_FARM_PAYLOAD.items() if k != "goals"}
        client = make_client(_supabase_with_insert([{**_FARM_DB_ROW, "goals": None}]))

        response = client.post(f"{_BASE}/", json=payload)

        assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/v1/farms/
# ---------------------------------------------------------------------------

class TestListFarms:
    def test_list_farms_returns_list(self, make_client):
        """GET /farms/ should return a JSON list."""
        mock_supabase, _ = _supabase_with_select([_FARM_DB_ROW])
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == _FARM_ID

    def test_list_farms_empty_returns_empty_list(self, make_client):
        """GET /farms/ with no farms should return an empty list, not an error."""
        mock_supabase, _ = _supabase_with_select([])
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.parametrize(
        "error",
        [
            APIError({"message": "boom", "code": "XX000", "hint": None, "details": None}),
            httpx.ConnectError("connection refused"),
        ],
        ids=["api_error", "transport_error"],
    )
    def test_list_farms_db_error_returns_500(self, make_client, error):
        mock_supabase, chain = _supabase_with_select([])
        chain.execute.side_effect = error
        response = make_client(mock_supabase).get(f"{_BASE}/")
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to list farms"

    def test_list_farms_non_db_error_is_not_masked_as_500_detail(self, make_client):
        """Only database errors are caught; a bug propagates."""
        mock_supabase, chain = _supabase_with_select([])
        chain.execute.side_effect = TypeError("bug")
        with pytest.raises(TypeError):
            make_client(mock_supabase).get(f"{_BASE}/")

    def test_list_farms_uses_order_by_created_at(self, make_client):
        """The list endpoint should order by created_at descending."""
        mock_supabase, chain = _supabase_with_select([_FARM_DB_ROW])
        client = make_client(mock_supabase)

        client.get(f"{_BASE}/")

        chain.order.assert_called_once_with("created_at", desc=True)


# ---------------------------------------------------------------------------
# GET /api/v1/farms/{farm_id}
# ---------------------------------------------------------------------------

class TestGetFarm:
    def test_get_farm_existing_returns_200(self, make_client):
        """GET /farms/{id} for an existing farm should return 200 and the farm."""
        mock_supabase, _ = _supabase_with_select(_FARM_DB_ROW)
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_FARM_ID}")

        assert response.status_code == 200
        assert response.json()["id"] == _FARM_ID

    def test_get_farm_not_found_returns_404(self, make_client):
        """When PostgREST reports no row (RLS-filtered or absent), return 404."""
        mock_supabase, chain = _supabase_with_select(None)
        chain.execute.side_effect = APIError(_NOT_FOUND_ERROR)
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_MISSING_FARM_ID}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_farm_db_error_returns_500_not_404(self, make_client):
        """Only PGRST116 means 'no row'; other database failures are real errors."""
        mock_supabase, chain = _supabase_with_select(None)
        chain.execute.side_effect = APIError({"message": "boom", "code": "XX000"})
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_FARM_ID}")

        assert response.status_code == 500

    def test_get_farm_empty_result_returns_404(self, make_client):
        """An empty result must be a 404, never a 500 from response validation."""
        mock_supabase, _ = _supabase_with_select(None)
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_MISSING_FARM_ID}")

        assert response.status_code == 404

    def test_get_farm_non_uuid_id_returns_422(self, make_client):
        """farm_id is typed as UUID; a malformed id is rejected before hitting the DB."""
        mock_supabase = MagicMock()
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/nonexistent-id")

        assert response.status_code == 422
        mock_supabase.table.assert_not_called()

    def test_get_farm_queries_correct_table_and_id(self, make_client):
        """The router should query the 'farms' table filtered by the id as a string."""
        mock_supabase, chain = _supabase_with_select(_FARM_DB_ROW)
        client = make_client(mock_supabase)

        client.get(f"{_BASE}/{_FARM_ID}")

        mock_supabase.table.assert_called_once_with("farms")
        chain.eq.assert_called_once_with("id", _FARM_ID)


# ---------------------------------------------------------------------------
# PATCH /api/v1/farms/{farm_id}
# ---------------------------------------------------------------------------

class TestUpdateFarm:
    def test_patch_farm_returns_200(self, make_client):
        """PATCH /farms/{id} with valid data should return 200 and the updated record."""
        updated_row = {**_FARM_DB_ROW, "name": "Updated Farm Name", "total_acres": 400.0}
        mock_supabase, _ = _supabase_with_update([updated_row])
        client = make_client(mock_supabase)

        response = client.patch(
            f"{_BASE}/{_FARM_ID}",
            json={"name": "Updated Farm Name", "total_acres": 400.0},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Farm Name"
        assert response.json()["total_acres"] == 400.0

    def test_patch_farm_only_sends_provided_fields(self, make_client):
        """PATCH is a partial update: only fields present in the payload are written."""
        mock_supabase, update_chain = _supabase_with_update([_FARM_DB_ROW])
        client = make_client(mock_supabase)

        client.patch(f"{_BASE}/{_FARM_ID}", json={"name": "Renamed"})

        mock_supabase.table.return_value.update.assert_called_once_with({"name": "Renamed"})
        update_chain.eq.assert_called_once_with("id", _FARM_ID)

    def test_patch_farm_not_found_returns_404(self, make_client):
        """PATCH on a non-existent farm (DB returns empty data) should return 404."""
        mock_supabase, _ = _supabase_with_update(None)
        client = make_client(mock_supabase)

        response = client.patch(f"{_BASE}/{_MISSING_FARM_ID}", json=_VALID_FARM_PAYLOAD)

        assert response.status_code == 404

    def test_patch_farm_empty_payload_returns_400(self, make_client):
        """A PATCH with no fields to update should return 400."""
        mock_supabase, _ = _supabase_with_update([_FARM_DB_ROW])
        client = make_client(mock_supabase)

        response = client.patch(f"{_BASE}/{_FARM_ID}", json={})

        assert response.status_code == 400
        mock_supabase.table.assert_not_called()

    def test_patch_farm_invalid_value_returns_422(self, make_client):
        """Provided fields are still validated (total_acres must be > 0)."""
        client = make_client(MagicMock())
        response = client.patch(f"{_BASE}/{_FARM_ID}", json={"total_acres": 0})
        assert response.status_code == 422

    def test_patch_farm_serializes_goals_enum_to_string(self, make_client):
        """The Goals enum must reach Supabase as its plain JSON string value."""
        mock_supabase, _ = _supabase_with_update([_FARM_DB_ROW])
        client = make_client(mock_supabase)

        client.patch(f"{_BASE}/{_FARM_ID}", json={"goals": "cost_savings"})

        sent = mock_supabase.table.return_value.update.call_args.args[0]
        assert sent == {"goals": "cost_savings"}
        assert type(sent["goals"]) is str

    def test_patch_farm_passes_id_as_str(self, make_client):
        """UUID path ids are converted to str before reaching the Supabase client."""
        mock_supabase, update_chain = _supabase_with_update([_FARM_DB_ROW])
        client = make_client(mock_supabase)

        client.patch(f"{_BASE}/{_FARM_ID}", json={"name": "Renamed"})

        filter_value = update_chain.eq.call_args.args[1]
        assert type(filter_value) is str

    def test_patch_farm_db_error_returns_500(self, make_client, caplog):
        """A PostgREST failure on update is a server error (500), logged with the farm id."""
        mock_supabase, update_chain = _supabase_with_update(None)
        update_chain.execute.side_effect = APIError({"message": "boom", "code": "XX000"})
        client = make_client(mock_supabase)

        with caplog.at_level("ERROR", logger="app.routers.farms"):
            response = client.patch(f"{_BASE}/{_FARM_ID}", json={"name": "Renamed"})

        assert response.status_code == 500
        assert _FARM_ID in caplog.text


# ---------------------------------------------------------------------------
# DELETE /api/v1/farms/{farm_id}
# ---------------------------------------------------------------------------

class TestDeleteFarm:
    def test_delete_farm_returns_204(self, make_client):
        """DELETE /farms/{id} should return 204 No Content on success."""
        mock_supabase, _ = _supabase_for_delete(farm_exists=True)
        client = make_client(mock_supabase)

        response = client.delete(f"{_BASE}/{_FARM_ID}")

        assert response.status_code == 204

    def test_delete_farm_calls_correct_table_and_id(self, make_client):
        """DELETE should target the 'farms' table and filter by the given farm_id."""
        mock_supabase, delete_chain = _supabase_for_delete(farm_exists=True)
        client = make_client(mock_supabase)

        client.delete(f"{_BASE}/{_FARM_ID}")

        mock_supabase.table.assert_called_with("farms")
        delete_chain.eq.assert_called_once_with("id", _FARM_ID)

    def test_delete_nonexistent_farm_returns_404(self, make_client):
        """DELETE on a farm that is absent or not visible under RLS returns 404
        and never issues the delete."""
        mock_supabase, _ = _supabase_for_delete(farm_exists=False)
        client = make_client(mock_supabase)

        response = client.delete(f"{_BASE}/{_MISSING_FARM_ID}")

        assert response.status_code == 404
        mock_supabase.table.return_value.delete.assert_not_called()

    def test_delete_access_lookup_error_returns_500(self, make_client):
        """A failing ownership lookup is a real error (500), not a 404, and skips the delete."""
        mock_supabase, _ = _supabase_for_delete(farm_exists=True)
        select_exec = (
            mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value
        )
        select_exec.execute.side_effect = APIError({"message": "boom", "code": "XX000"})
        client = make_client(mock_supabase)

        response = client.delete(f"{_BASE}/{_FARM_ID}")

        assert response.status_code == 500
        mock_supabase.table.return_value.delete.assert_not_called()

    def test_delete_db_error_returns_500(self, make_client, caplog):
        """A PostgREST failure on the delete itself returns 500, logged with the farm id."""
        mock_supabase, delete_chain = _supabase_for_delete(farm_exists=True)
        delete_chain.execute.side_effect = APIError({"message": "boom", "code": "XX000"})
        client = make_client(mock_supabase)

        with caplog.at_level("ERROR", logger="app.routers.farms"):
            response = client.delete(f"{_BASE}/{_FARM_ID}")

        assert response.status_code == 500
        assert _FARM_ID in caplog.text

    def test_delete_passes_id_as_str(self, make_client):
        """UUID path ids are converted to str before reaching the Supabase client."""
        mock_supabase, delete_chain = _supabase_for_delete(farm_exists=True)
        client = make_client(mock_supabase)

        client.delete(f"{_BASE}/{_FARM_ID}")

        assert type(delete_chain.eq.call_args.args[1]) is str
