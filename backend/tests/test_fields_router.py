"""
Tests for app.routers.fields — Field CRUD and enrichment endpoints.

Coverage targets:
  - POST /fields with valid data → 201
  - POST /fields missing required field → 422
  - GET /fields?farm_id= → returns filtered list
  - GET /fields/{id}/soil → returns latest soil profile (or None)
  - GET /fields/{id}/weather → returns weather data list
  - POST /fields/{id}/enrich → 202 + enrichment summary, 404 when field missing
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import _make_chain, FARM_ID, FIELD_ID_A, FIELD_ID_B

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_USER_ID = "user-uuid-field-test"

_FIELD_ROW = {
    "id": FIELD_ID_A,
    "farm_id": FARM_ID,
    "name": "North 40",
    "acres": 120.0,
    "crop_type": "corn",
    "boundary_geojson": None,
    "boundary_description": None,
    "practices": ["340", "329"],
    "created_at": "2026-01-20T08:00:00+00:00",
}

_SOIL_ROW = {
    "id": "soil-uuid-1",
    "field_id": FIELD_ID_A,
    "ssurgo_map_unit": "70D",
    "texture": "silt loam",
    "ph": 6.8,
    "organic_matter_pct": 3.2,
    "source": "SSURGO",
    "fetched_at": "2026-02-01T00:00:00+00:00",
}

_WEATHER_ROW = {
    "id": "wx-uuid-1",
    "field_id": FIELD_ID_A,
    "date": "2026-04-20",
    "temp_high": 68.0,
    "temp_low": 45.0,
    "precip_mm": 2.5,
    "soil_temp": 52.0,
    "fetched_at": "2026-04-20T12:00:00+00:00",
}

_VALID_FIELD_PAYLOAD = {
    "farm_id": FARM_ID,
    "name": "North 40",
    "acres": 120.0,
    "crop_type": "corn",
    "practices": ["340"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user() -> MagicMock:
    user = MagicMock()
    user.id = _USER_ID
    return user


def _make_supabase_with_insert(return_data: list | None) -> MagicMock:
    mock = MagicMock()
    insert_chain = MagicMock()
    result = MagicMock()
    result.data = return_data
    insert_chain.execute.return_value = result
    mock.table.return_value.insert.return_value = insert_chain
    return mock


def _make_supabase_select_returning(return_data) -> MagicMock:
    """Build a mock Supabase where all select chains return return_data."""
    mock = MagicMock()
    chain = _make_chain(data=return_data)
    mock.table.return_value = chain
    return mock


# ---------------------------------------------------------------------------
# POST /fields
# ---------------------------------------------------------------------------

class TestCreateField:
    def test_create_field_valid_data_returns_201(self):
        """Valid payload should create a field and return 201."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_insert([_FIELD_ROW])

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.post("/fields/", json=_VALID_FIELD_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == FIELD_ID_A
        assert body["name"] == "North 40"
        assert body["farm_id"] == FARM_ID

    def test_create_field_missing_name_returns_422(self):
        """Payload missing 'name' should return 422."""
        payload = {k: v for k, v in _VALID_FIELD_PAYLOAD.items() if k != "name"}
        client = TestClient(app)
        response = client.post(
            "/fields/",
            json=payload,
            headers={"Authorization": "Bearer token"},
        )
        assert response.status_code == 422

    def test_create_field_missing_acres_returns_422(self):
        """Payload missing 'acres' should return 422."""
        payload = {k: v for k, v in _VALID_FIELD_PAYLOAD.items() if k != "acres"}
        client = TestClient(app)
        response = client.post(
            "/fields/",
            json=payload,
            headers={"Authorization": "Bearer token"},
        )
        assert response.status_code == 422

    def test_create_field_missing_crop_type_returns_422(self):
        """Payload missing 'crop_type' should return 422."""
        payload = {k: v for k, v in _VALID_FIELD_PAYLOAD.items() if k != "crop_type"}
        client = TestClient(app)
        response = client.post(
            "/fields/",
            json=payload,
            headers={"Authorization": "Bearer token"},
        )
        assert response.status_code == 422

    def test_create_field_zero_acres_returns_422(self):
        """acres must be > 0; zero should return 422."""
        payload = {**_VALID_FIELD_PAYLOAD, "acres": 0}
        client = TestClient(app)
        response = client.post(
            "/fields/",
            json=payload,
            headers={"Authorization": "Bearer token"},
        )
        assert response.status_code == 422

    def test_create_field_negative_acres_returns_422(self):
        """Negative acres are invalid and should return 422."""
        payload = {**_VALID_FIELD_PAYLOAD, "acres": -10.0}
        client = TestClient(app)
        response = client.post(
            "/fields/",
            json=payload,
            headers={"Authorization": "Bearer token"},
        )
        assert response.status_code == 422

    def test_create_field_db_failure_returns_500(self):
        """When Supabase insert returns no data, the router should return 500."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_insert(None)

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.post("/fields/", json=_VALID_FIELD_PAYLOAD)

        assert response.status_code == 500

    def test_create_field_optional_boundary_geojson(self):
        """boundary_geojson is optional and should be accepted when provided."""
        payload = {
            **_VALID_FIELD_PAYLOAD,
            "boundary_geojson": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1]]]},
        }
        row = {**_FIELD_ROW, "boundary_geojson": payload["boundary_geojson"]}
        mock_user = _mock_user()
        mock_supabase = _make_supabase_with_insert([row])

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.post("/fields/", json=payload)

        assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /fields?farm_id=
# ---------------------------------------------------------------------------

class TestListFields:
    def test_list_fields_returns_filtered_list(self):
        """GET /fields?farm_id= should return only fields belonging to that farm."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_select_returning([_FIELD_ROW])

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.get(f"/fields/?farm_id={FARM_ID}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["farm_id"] == FARM_ID

    def test_list_fields_empty_farm_returns_empty_list(self):
        """A farm with no fields should return an empty list."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_select_returning([])

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.get(f"/fields/?farm_id={FARM_ID}")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_fields_filters_by_farm_id(self):
        """The query must filter on farm_id via .eq()."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        chain = _make_chain(data=[_FIELD_ROW])
        mock_supabase.table.return_value = chain

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            client.get(f"/fields/?farm_id={FARM_ID}")

        chain.eq.assert_called_with("farm_id", FARM_ID)

    def test_list_fields_missing_farm_id_returns_422(self):
        """farm_id query parameter is required; its absence should return 422."""
        client = TestClient(app)
        response = client.get(
            "/fields/",
            headers={"Authorization": "Bearer token"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /fields/{field_id}/soil
# ---------------------------------------------------------------------------

class TestGetSoilProfile:
    def test_get_soil_returns_latest_profile(self):
        """GET /fields/{id}/soil should return the most recent soil record."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_select_returning([_SOIL_ROW])

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.get(f"/fields/{FIELD_ID_A}/soil")

        assert response.status_code == 200
        body = response.json()
        assert body["field_id"] == FIELD_ID_A
        assert body["organic_matter_pct"] == 3.2

    def test_get_soil_no_profile_returns_null(self):
        """When no soil profile exists for the field, the response body should be null."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_select_returning([])

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.get(f"/fields/{FIELD_ID_A}/soil")

        assert response.status_code == 200
        assert response.json() is None

    def test_get_soil_queries_soil_profiles_table(self):
        """The soil endpoint should query the 'soil_profiles' table."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        chain = _make_chain(data=[_SOIL_ROW])
        mock_supabase.table.return_value = chain

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            client.get(f"/fields/{FIELD_ID_A}/soil")

        mock_supabase.table.assert_called_with("soil_profiles")

    def test_get_soil_orders_by_fetched_at_desc(self):
        """The query must order by fetched_at descending to get the most recent entry."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        chain = _make_chain(data=[_SOIL_ROW])
        mock_supabase.table.return_value = chain

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            client.get(f"/fields/{FIELD_ID_A}/soil")

        chain.order.assert_called_with("fetched_at", desc=True)


# ---------------------------------------------------------------------------
# GET /fields/{field_id}/weather
# ---------------------------------------------------------------------------

class TestGetWeather:
    def test_get_weather_returns_list(self):
        """GET /fields/{id}/weather should return a list of weather records."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_select_returning([_WEATHER_ROW])

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.get(f"/fields/{FIELD_ID_A}/weather")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["field_id"] == FIELD_ID_A

    def test_get_weather_empty_returns_empty_list(self):
        """When no weather data exists, return empty list."""
        mock_user = _mock_user()
        mock_supabase = _make_supabase_select_returning([])

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.get(f"/fields/{FIELD_ID_A}/weather")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_weather_limits_to_7_days(self):
        """The weather query should call .limit(7)."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        chain = _make_chain(data=[_WEATHER_ROW])
        mock_supabase.table.return_value = chain

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            client.get(f"/fields/{FIELD_ID_A}/weather")

        chain.limit.assert_called_with(7)

    def test_get_weather_queries_weather_cache_table(self):
        """The endpoint should query the 'weather_cache' table."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        chain = _make_chain(data=[])
        mock_supabase.table.return_value = chain

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            client.get(f"/fields/{FIELD_ID_A}/weather")

        mock_supabase.table.assert_called_with("weather_cache")


# ---------------------------------------------------------------------------
# POST /fields/{field_id}/enrich
# ---------------------------------------------------------------------------

class TestEnrichField:
    def test_enrich_existing_field_returns_202(self):
        """POST /fields/{id}/enrich on an accessible field should return 202."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        # Field existence check
        check_chain = _make_chain(data={"id": FIELD_ID_A})
        mock_supabase.table.return_value = check_chain

        enrichment_result = {
            "field_id": FIELD_ID_A,
            "weather_days_upserted": 7,
            "soil_profile_saved": True,
            "warnings": [],
        }

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
            patch(
                "app.routers.fields.run_enrichment",
                new=AsyncMock(return_value=enrichment_result),
            ),
        ):
            client = TestClient(app)
            response = client.post(f"/fields/{FIELD_ID_A}/enrich")

        assert response.status_code == 202

    def test_enrich_returns_correct_summary_keys(self):
        """The 202 response should contain status, field_id, weather_days_upserted, soil_profile_saved, warnings."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        check_chain = _make_chain(data={"id": FIELD_ID_A})
        mock_supabase.table.return_value = check_chain

        enrichment_result = {
            "field_id": FIELD_ID_A,
            "weather_days_upserted": 5,
            "soil_profile_saved": False,
            "warnings": ["SSURGO service unavailable"],
        }

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
            patch(
                "app.routers.fields.run_enrichment",
                new=AsyncMock(return_value=enrichment_result),
            ),
        ):
            client = TestClient(app)
            response = client.post(f"/fields/{FIELD_ID_A}/enrich")

        body = response.json()
        assert body["status"] == "enrichment_complete"
        assert body["field_id"] == FIELD_ID_A
        assert body["weather_days_upserted"] == 5
        assert body["soil_profile_saved"] is False
        assert "SSURGO service unavailable" in body["warnings"]

    def test_enrich_nonexistent_field_returns_404(self):
        """POST /fields/{id}/enrich for a field not accessible via RLS should return 404."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        # Field existence check returns None
        check_chain = _make_chain(data=None)
        mock_supabase.table.return_value = check_chain

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
        ):
            client = TestClient(app)
            response = client.post(f"/fields/nonexistent-field-id/enrich")

        assert response.status_code == 404

    def test_enrich_passes_supabase_client_to_run_enrichment(self):
        """The authenticated supabase client must be forwarded to run_enrichment."""
        mock_user = _mock_user()
        mock_supabase = MagicMock()
        check_chain = _make_chain(data={"id": FIELD_ID_A})
        mock_supabase.table.return_value = check_chain

        enrichment_result = {
            "field_id": FIELD_ID_A,
            "weather_days_upserted": 7,
            "soil_profile_saved": True,
            "warnings": [],
        }
        captured_calls = []

        async def capturing_run_enrichment(field_id, supabase):
            captured_calls.append({"field_id": field_id, "supabase": supabase})
            return enrichment_result

        with (
            patch("app.routers.fields.get_current_user", return_value=mock_user),
            patch("app.routers.fields.get_authenticated_client", return_value=mock_supabase),
            patch("app.routers.fields.run_enrichment", side_effect=capturing_run_enrichment),
        ):
            client = TestClient(app)
            client.post(f"/fields/{FIELD_ID_A}/enrich")

        assert len(captured_calls) == 1
        assert captured_calls[0]["field_id"] == FIELD_ID_A
        assert captured_calls[0]["supabase"] is mock_supabase
