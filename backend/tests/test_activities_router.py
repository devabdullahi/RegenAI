"""
Tests for app.routers.activities — activity CRUD, yield history, APH.

Auth and Supabase are replaced via FastAPI dependency_overrides. Supabase is
a FakeSupabase (tests/test_schema_drift.py) that records writes, so tests
assert payloads use string ids and only real columns. The service's clock
(`_today`) is pinned so date rules are deterministic.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.auth.middleware import get_authenticated_client, get_current_user
from app.main import app
from tests.test_schema_drift import FakeSupabase, table_columns

_BASE = "/api/v1"
_PINNED_TODAY = date(2026, 9, 13)
_FIELD_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_FARM_ID = "5b0f3c1e-2a4d-4c1e-9b2a-6d7e8f901234"
_ACTIVITY_ID = "12345678-1234-4678-8234-000000000001"

_FIELD_ROW = {
    "id": _FIELD_ID,
    "farm_id": _FARM_ID,
    "acres": 120.0,
    "name": "North 40",
    "crop_type": "corn",
}

_ACTIVITY_ROW = {
    "id": _ACTIVITY_ID,
    "field_id": _FIELD_ID,
    "activity_type": "scout",
    "activity_date": "2026-09-01",
    "restricted_use": False,
    "pest_name": "corn rootworm",
    "created_at": "2026-09-01T10:00:00+00:00",
    "updated_at": "2026-09-01T10:00:00+00:00",
}


def _yield_row(year: int, bushels: float) -> dict:
    return {
        "id": f"yh-{year}",
        "field_id": _FIELD_ID,
        "crop_year": year,
        "crop_type": "corn",
        "yield_bu_acre": bushels,
        "moisture_pct": None,
        "acres_harvested": None,
        "notes": None,
        "created_at": "2026-01-01T00:00:00+00:00",
    }


@pytest.fixture(autouse=True)
def _pin_today():
    with patch("app.services.activity_log.helpers._today", return_value=_PINNED_TODAY):
        yield


@pytest.fixture
def make_client():
    def _make(supabase: FakeSupabase) -> TestClient:
        user = MagicMock()
        user.id = "user-1"
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_authenticated_client] = lambda: supabase
        return TestClient(app)

    try:
        yield _make
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_authenticated_client, None)


def _db_error() -> APIError:
    return APIError({"message": "boom", "code": "XX000", "hint": None, "details": None})


# ---------------------------------------------------------------------------
# POST /activities
# ---------------------------------------------------------------------------


class TestCreateActivity:
    def test_scout_maps_pest_disease_found_to_pest_name(self, make_client):
        supabase = FakeSupabase(rows={"fields": [_FIELD_ROW]})
        client = make_client(supabase)

        response = client.post(
            f"{_BASE}/activities",
            json={
                "field_id": _FIELD_ID,
                "activity_type": "scout",
                "activity_date": "2026-09-01",
                "pest_disease_found": "corn rootworm",
                "severity": "moderate",
                "cover_crop_species": "cereal rye",
            },
        )

        assert response.status_code == 201, response.text
        (payload,) = supabase.writes_for("field_activities", "insert")
        assert payload["pest_name"] == "corn rootworm"
        assert "pest_disease_found" not in payload
        assert payload["field_id"] == _FIELD_ID and isinstance(payload["field_id"], str)
        assert set(payload) <= table_columns("field_activities")

        body = response.json()
        assert body["pest_disease_found"] == "corn rootworm"
        assert body["warnings"] == []

    def test_harvest_syncs_yield_history_with_field_crop_type(self, make_client):
        supabase = FakeSupabase(rows={"fields": [_FIELD_ROW]})
        client = make_client(supabase)

        response = client.post(
            f"{_BASE}/activities",
            json={
                "field_id": _FIELD_ID,
                "activity_type": "harvest",
                "activity_date": "2026-09-10",
                "yield_bu_acre": 201.5,
                "moisture_pct": 15.2,
                "crop_year": 2026,
                "acres_applied": 100,
            },
        )

        assert response.status_code == 201, response.text
        (yield_payload,) = supabase.writes_for("yield_history", "upsert")
        assert yield_payload["crop_type"] == "corn"
        assert yield_payload["field_id"] == _FIELD_ID
        assert set(yield_payload) <= table_columns("yield_history")
        assert response.json()["warnings"] == []

    def test_harvest_yield_sync_failure_is_reported_as_warning(self, make_client):
        supabase = FakeSupabase(
            rows={"fields": [_FIELD_ROW]},
            errors={("yield_history", "upsert"): _db_error()},
        )
        client = make_client(supabase)

        response = client.post(
            f"{_BASE}/activities",
            json={
                "field_id": _FIELD_ID,
                "activity_type": "harvest",
                "activity_date": "2026-09-10",
                "yield_bu_acre": 190,
                "crop_year": 2026,
            },
        )

        assert response.status_code == 201
        warnings = response.json()["warnings"]
        assert len(warnings) == 1
        assert "yield history" in warnings[0].lower()

    def test_future_date_returns_422(self, make_client):
        supabase = FakeSupabase(rows={"fields": [_FIELD_ROW]})
        client = make_client(supabase)

        response = client.post(
            f"{_BASE}/activities",
            json={"field_id": _FIELD_ID, "activity_type": "plant", "activity_date": "2026-09-14"},
        )

        assert response.status_code == 422
        assert supabase.writes == []

    def test_unknown_field_returns_404(self, make_client):
        client = make_client(FakeSupabase(rows={"fields": []}))
        response = client.post(
            f"{_BASE}/activities",
            json={"field_id": _FIELD_ID, "activity_type": "plant", "activity_date": "2026-09-01"},
        )
        assert response.status_code == 404

    def test_insert_error_returns_500(self, make_client):
        supabase = FakeSupabase(
            rows={"fields": [_FIELD_ROW]},
            errors={("field_activities", "insert"): _db_error()},
        )
        client = make_client(supabase)
        response = client.post(
            f"{_BASE}/activities",
            json={"field_id": _FIELD_ID, "activity_type": "plant", "activity_date": "2026-09-01"},
        )
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /activities, GET/PATCH/DELETE /activities/{id}
# ---------------------------------------------------------------------------


class TestReadUpdateDelete:
    def test_list_returns_mapped_rows_and_count(self, make_client):
        supabase = FakeSupabase(rows={"fields": [_FIELD_ROW], "field_activities": [_ACTIVITY_ROW]})
        client = make_client(supabase)

        response = client.get(
            f"{_BASE}/activities",
            params={"field_id": _FIELD_ID, "activity_type": "scout", "start_date": "2026-01-01"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total_count"] == 1
        assert body["activities"][0]["pest_disease_found"] == "corn rootworm"
        data_query = supabase.last_query("field_activities")
        assert ("eq", ("field_id", _FIELD_ID)) in data_query.filters
        assert ("eq", ("activity_type", "scout")) in data_query.filters
        assert ("gte", ("activity_date", "2026-01-01")) in data_query.filters

    def test_get_single_activity(self, make_client):
        client = make_client(FakeSupabase(rows={"field_activities": [_ACTIVITY_ROW]}))
        response = client.get(f"{_BASE}/activities/{_ACTIVITY_ID}")
        assert response.status_code == 200
        assert response.json()["pest_disease_found"] == "corn rootworm"

    def test_get_missing_activity_returns_404(self, make_client):
        client = make_client(FakeSupabase(rows={"field_activities": []}))
        response = client.get(f"{_BASE}/activities/{_ACTIVITY_ID}")
        assert response.status_code == 404

    def test_get_db_error_returns_500_not_404(self, make_client):
        supabase = FakeSupabase(errors={("field_activities", "select"): _db_error()})
        client = make_client(supabase)
        response = client.get(f"{_BASE}/activities/{_ACTIVITY_ID}")
        assert response.status_code == 500

    def test_patch_maps_columns_and_uses_string_id(self, make_client):
        supabase = FakeSupabase(rows={"fields": [_FIELD_ROW], "field_activities": [_ACTIVITY_ROW]})
        client = make_client(supabase)

        response = client.patch(
            f"{_BASE}/activities/{_ACTIVITY_ID}",
            json={
                "pest_disease_found": "aphids",
                "seed_treatment": "fungicide",
                "tillage_depth_in": 4,
                "acres_applied": 50,
                "restricted_use": None,
            },
        )

        assert response.status_code == 200, response.text
        (payload,) = supabase.writes_for("field_activities", "update")
        assert payload["pest_name"] == "aphids"
        assert "pest_disease_found" not in payload
        assert "restricted_use" not in payload
        assert set(payload) <= table_columns("field_activities")
        update_query = supabase.last_query("field_activities")
        assert ("eq", ("id", _ACTIVITY_ID)) in update_query.filters
        assert response.json()["pest_disease_found"] == "aphids"

    def test_patch_future_date_returns_422(self, make_client):
        supabase = FakeSupabase(rows={"field_activities": [_ACTIVITY_ROW]})
        client = make_client(supabase)
        response = client.patch(
            f"{_BASE}/activities/{_ACTIVITY_ID}", json={"activity_date": "2026-12-01"}
        )
        assert response.status_code == 422
        assert supabase.writes == []

    def test_patch_restricted_spray_without_credentials_returns_422(self, make_client):
        supabase = FakeSupabase(rows={"field_activities": [_ACTIVITY_ROW]})
        client = make_client(supabase)
        response = client.patch(
            f"{_BASE}/activities/{_ACTIVITY_ID}",
            json={"activity_type": "spray", "restricted_use": True},
        )
        assert response.status_code == 422

    def test_delete_activity(self, make_client):
        supabase = FakeSupabase(rows={"field_activities": [_ACTIVITY_ROW]})
        client = make_client(supabase)

        response = client.delete(f"{_BASE}/activities/{_ACTIVITY_ID}")

        assert response.status_code == 204
        delete_query = supabase.last_query("field_activities")
        assert delete_query.op == "delete"
        assert ("eq", ("id", _ACTIVITY_ID)) in delete_query.filters


# ---------------------------------------------------------------------------
# Yield history + APH
# ---------------------------------------------------------------------------


class TestYieldHistory:
    def test_record_yield_history(self, make_client):
        supabase = FakeSupabase(rows={"fields": [_FIELD_ROW]})
        client = make_client(supabase)

        response = client.post(
            f"{_BASE}/yield-history",
            json={
                "field_id": _FIELD_ID,
                "crop_year": 2025,
                "crop_type": "corn",
                "yield_bu_acre": 185,
                "notes": "dry year",
            },
        )

        assert response.status_code == 201, response.text
        (payload,) = supabase.writes_for("yield_history", "upsert")
        assert payload["field_id"] == _FIELD_ID
        assert set(payload) <= table_columns("yield_history")

    def test_list_yield_history(self, make_client):
        rows = [_yield_row(2025, 190), _yield_row(2024, 180)]
        client = make_client(FakeSupabase(rows={"fields": [_FIELD_ROW], "yield_history": rows}))

        response = client.get(f"{_BASE}/yield-history", params={"field_id": _FIELD_ID})

        assert response.status_code == 200
        assert [r["crop_year"] for r in response.json()] == [2025, 2024]

    def test_aph_with_four_years(self, make_client):
        rows = [_yield_row(2025 - i, 180 + i) for i in range(4)]
        client = make_client(FakeSupabase(rows={"fields": [_FIELD_ROW], "yield_history": rows}))

        response = client.get(f"{_BASE}/yield-history/aph", params={"field_id": _FIELD_ID})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["years_used"] == 4
        assert body["aph_yield"] == pytest.approx(181.5)

    def test_aph_with_too_few_years_returns_422(self, make_client):
        rows = [_yield_row(2025, 180)]
        client = make_client(FakeSupabase(rows={"fields": [_FIELD_ROW], "yield_history": rows}))
        response = client.get(f"{_BASE}/yield-history/aph", params={"field_id": _FIELD_ID})
        assert response.status_code == 422
