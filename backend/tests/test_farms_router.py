"""
Tests for app.routers.farms — Farm CRUD endpoints.

Coverage targets:
  - POST /farms with valid data → 201 + correct response shape
  - POST /farms with missing required field → 422
  - GET /farms → returns list for the current user
  - GET /farms/{id} → returns a single farm
  - GET /farms/{id} for non-existent farm → 404
  - PATCH /farms/{id} with partial update → 200 + updated record
  - DELETE /farms/{id} → 204
  - DELETE /farms/{non-existent} → behavior when DB returns empty

All Supabase I/O and auth dependencies are mocked so no real HTTP calls are made.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import _make_chain, FARM_ID

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_USER_ID = "user-uuid-test-1"

_VALID_FARM_PAYLOAD = {
    "name": "Sunrise Farm",
    "state": "IA",
    "county_fips": "19153",
    "total_acres": 320.0,
    "goals": "cost_savings",
}

_FARM_DB_ROW = {
    "id": FARM_ID,
    "user_id": _USER_ID,
    "name": "Sunrise Farm",
    "state": "IA",
    "county_fips": "19153",
    "total_acres": 320.0,
    "goals": "cost_savings",
    "created_at": "2026-01-15T10:00:00+00:00",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _mock_user(user_id: str = _USER_ID) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    return user


def _make_supabase_with_insert(return_data: list | None) -> MagicMock:
    """Return a mock Supabase where table().insert().execute() yields return_data."""
    mock = MagicMock()
    insert_chain = MagicMock()
    execute_result = MagicMock()
    execute_result.data = return_data
    insert_chain.execute.return_value = execute_result
    mock.table.return_value.insert.return_value = insert_chain
    return mock


def _make_supabase_with_select(return_data) -> MagicMock:
    """Return a mock Supabase where any select chain returns return_data."""
    mock = MagicMock()
    chain = _make_chain(data=return_data)
    mock.table.return_value = chain
    return mock


def _make_supabase_with_update(return_data: list | None) -> MagicMock:
    """Return a mock Supabase where table().update().eq().execute() yields return_data."""
    mock = MagicMock()
    update_chain = MagicMock()
    execute_result = MagicMock()
    execute_result.data = return_data
    update_chain.execute.return_value = execute_result
    update_chain.eq.return_value = update_chain
    mock.table.return_value.update.return_value = update_chain
    return mock


# ---------------------------------------------------------------------------
# POST /farms
# ---------------------------------------------------------------------------

class TestCreateFarm:
    def test_create_farm_valid_data_returns_201(self):
        """Valid payload should create a farm and return 201 with the new record."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_insert([_FARM_DB_ROW])

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.post("/farms/", json=_VALID_FARM_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == FARM_ID
        assert body["name"] == "Sunrise Farm"
        assert body["state"] == "IA"

    def test_create_farm_inserts_correct_user_id(self):
        """The router should set user_id from the authenticated user, not the payload."""
        mock_user = _mock_user(user_id="the-real-user-id")
        captured_inserts: list[dict] = []

        mock_supabase = MagicMock()

        def capture_insert(data):
            captured_inserts.append(data)
            chain = MagicMock()
            result = MagicMock()
            result.data = [{**_FARM_DB_ROW, "user_id": "the-real-user-id"}]
            chain.execute.return_value = result
            return chain

        mock_supabase.table.return_value.insert.side_effect = capture_insert

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            client.post("/farms/", json=_VALID_FARM_PAYLOAD)

        assert len(captured_inserts) == 1
        assert captured_inserts[0]["user_id"] == "the-real-user-id"

    def test_create_farm_missing_name_returns_422(self):
        """A payload missing the required 'name' field should return 422."""
        payload = {k: v for k, v in _VALID_FARM_PAYLOAD.items() if k != "name"}
        client = TestClient(app)
        response = client.post(
            "/farms/",
            json=payload,
            headers={"Authorization": "Bearer any-token"},
        )
        assert response.status_code == 422

    def test_create_farm_missing_state_returns_422(self):
        """A payload missing the required 'state' field should return 422."""
        payload = {k: v for k, v in _VALID_FARM_PAYLOAD.items() if k != "state"}
        client = TestClient(app)
        response = client.post(
            "/farms/",
            json=payload,
            headers={"Authorization": "Bearer any-token"},
        )
        assert response.status_code == 422

    def test_create_farm_missing_county_fips_returns_422(self):
        """A payload missing the required 'county_fips' field should return 422."""
        payload = {k: v for k, v in _VALID_FARM_PAYLOAD.items() if k != "county_fips"}
        client = TestClient(app)
        response = client.post(
            "/farms/",
            json=payload,
            headers={"Authorization": "Bearer any-token"},
        )
        assert response.status_code == 422

    def test_create_farm_zero_acres_returns_422(self):
        """total_acres must be > 0; zero should return 422."""
        payload = {**_VALID_FARM_PAYLOAD, "total_acres": 0}
        client = TestClient(app)
        response = client.post(
            "/farms/",
            json=payload,
            headers={"Authorization": "Bearer any-token"},
        )
        assert response.status_code == 422

    def test_create_farm_db_insert_fails_returns_500(self):
        """When Supabase insert returns no data, the router should return 500."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_insert(None)

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.post("/farms/", json=_VALID_FARM_PAYLOAD)

        assert response.status_code == 500

    def test_create_farm_without_goals_field_accepted(self):
        """goals is optional; payload without it should be accepted."""
        payload = {k: v for k, v in _VALID_FARM_PAYLOAD.items() if k != "goals"}
        row = {**_FARM_DB_ROW, "goals": None}
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_insert([row])

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.post("/farms/", json=payload)

        assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /farms/
# ---------------------------------------------------------------------------

class TestListFarms:
    def test_list_farms_returns_list(self):
        """GET /farms/ should return a JSON list."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_select([_FARM_DB_ROW])

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.get("/farms/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == FARM_ID

    def test_list_farms_empty_returns_empty_list(self):
        """GET /farms/ with no farms should return an empty list, not an error."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_select([])

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.get("/farms/")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_farms_uses_order_by_created_at(self):
        """The list endpoint should call .order() on the query chain."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        chain = _make_chain(data=[_FARM_DB_ROW])
        mock_supabase.table.return_value = chain

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            client.get("/farms/")

        chain.order.assert_called_once_with("created_at", desc=True)


# ---------------------------------------------------------------------------
# GET /farms/{farm_id}
# ---------------------------------------------------------------------------

class TestGetFarm:
    def test_get_farm_existing_returns_200(self):
        """GET /farms/{id} for an existing farm should return 200 and the farm."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_select(_FARM_DB_ROW)

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.get(f"/farms/{FARM_ID}")

        assert response.status_code == 200
        assert response.json()["id"] == FARM_ID

    def test_get_farm_not_found_returns_404(self):
        """GET /farms/{id} for a non-existent farm should return 404."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_select(None)

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.get("/farms/nonexistent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_farm_queries_correct_table(self):
        """The router should query the 'farms' table."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        chain = _make_chain(data=_FARM_DB_ROW)
        mock_supabase.table.return_value = chain

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            client.get(f"/farms/{FARM_ID}")

        mock_supabase.table.assert_called_once_with("farms")


# ---------------------------------------------------------------------------
# PATCH /farms/{farm_id}
# ---------------------------------------------------------------------------

class TestUpdateFarm:
    def test_patch_farm_returns_200(self):
        """PATCH /farms/{id} with valid data should return 200 and the updated record."""
        updated_row = {**_FARM_DB_ROW, "name": "Updated Farm Name", "total_acres": 400.0}
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_update([updated_row])

        update_payload = {**_VALID_FARM_PAYLOAD, "name": "Updated Farm Name", "total_acres": 400.0}

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.patch(f"/farms/{FARM_ID}", json=update_payload)

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Farm Name"
        assert response.json()["total_acres"] == 400.0

    def test_patch_farm_not_found_returns_404(self):
        """PATCH on a non-existent farm (DB returns empty data) should return 404."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_update(None)

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.patch("/farms/does-not-exist", json=_VALID_FARM_PAYLOAD)

        assert response.status_code == 404

    def test_patch_farm_missing_required_field_returns_422(self):
        """A PATCH payload missing a required field should return 422."""
        payload = {k: v for k, v in _VALID_FARM_PAYLOAD.items() if k != "total_acres"}
        client = TestClient(app)
        response = client.patch(
            f"/farms/{FARM_ID}",
            json=payload,
            headers={"Authorization": "Bearer token"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /farms/{farm_id}
# ---------------------------------------------------------------------------

class TestDeleteFarm:
    def test_delete_farm_returns_204(self):
        """DELETE /farms/{id} should return 204 No Content on success."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        delete_chain = MagicMock()
        delete_chain.execute.return_value = MagicMock(data=None)
        delete_chain.eq.return_value = delete_chain
        mock_supabase.table.return_value.delete.return_value = delete_chain

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.delete(f"/farms/{FARM_ID}")

        assert response.status_code == 204

    def test_delete_farm_calls_correct_table_and_id(self):
        """DELETE should target the 'farms' table and filter by the given farm_id."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        delete_chain = MagicMock()
        delete_chain.execute.return_value = MagicMock(data=None)
        delete_chain.eq.return_value = delete_chain
        mock_supabase.table.return_value.delete.return_value = delete_chain

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            client.delete(f"/farms/{FARM_ID}")

        mock_supabase.table.assert_called_with("farms")
        delete_chain.eq.assert_called_once_with("id", FARM_ID)

    def test_delete_nonexistent_farm_returns_204(self):
        """DELETE on a non-existent farm still returns 204 (no separate existence check)."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        delete_chain = MagicMock()
        delete_chain.execute.return_value = MagicMock(data=None)
        delete_chain.eq.return_value = delete_chain
        mock_supabase.table.return_value.delete.return_value = delete_chain

        with (
            patch("app.routers.farms.get_current_user", return_value=mock_user),
            patch("app.routers.farms.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.delete("/farms/definitely-does-not-exist")

        assert response.status_code == 204
