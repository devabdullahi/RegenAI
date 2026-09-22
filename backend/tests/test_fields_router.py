"""
Tests for app.routers.fields — Field CRUD and enrichment endpoints.

Coverage targets:
  - POST /api/v1/fields with valid data → 201
  - POST /api/v1/fields missing/invalid field → 422
  - GET /api/v1/fields?farm_id= → returns filtered list; 404 for unknown/hidden farm
  - GET /api/v1/fields/{id}/soil → latest soil profile, null if none, 404 unknown field
  - GET /api/v1/fields/{id}/weather → weather list, 404 unknown field
  - POST /api/v1/fields/{id}/enrich → 202 + enrichment summary, 404 when field missing,
    500 when the access lookup fails, 429 past the 10/hour limit

Auth and Supabase are replaced via FastAPI dependency_overrides (patching the
module-level names does not affect dependencies already bound by Depends()).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.auth.middleware import get_authenticated_client, get_current_user
from app.main import app
from app.rate_limit import limiter

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_BASE = "/api/v1/fields"
_USER_ID = "user-uuid-field-test"
_FARM_ID = "5b0f3c1e-2a4d-4c1e-9b2a-6d7e8f901234"
_FIELD_ID = "7c2d4e6f-1a3b-4c5d-8e9f-0a1b2c3d4e5f"
_MISSING_FIELD_ID = "00000000-0000-4000-8000-000000000000"

_FIELD_ROW = {
    "id": _FIELD_ID,
    "farm_id": _FARM_ID,
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
    "field_id": _FIELD_ID,
    "ssurgo_map_unit": "70D",
    "texture": "silt loam",
    "ph": 6.8,
    "organic_matter_pct": 3.2,
    "source": "SSURGO",
    "fetched_at": "2026-02-01T00:00:00+00:00",
}

_WEATHER_ROW = {
    "id": "wx-uuid-1",
    "field_id": _FIELD_ID,
    "date": "2026-04-20",
    "temp_high": 68.0,
    "temp_low": 45.0,
    "precip_mm": 2.5,
    "soil_temp": 52.0,
    "fetched_at": "2026-04-20T12:00:00+00:00",
}

_VALID_FIELD_PAYLOAD = {
    "farm_id": _FARM_ID,
    "name": "North 40",
    "acres": 120.0,
    "crop_type": "corn",
    "practices": ["340"],
}

_ENRICHMENT_RESULT = {
    "field_id": _FIELD_ID,
    "weather_days_upserted": 7,
    "soil_profile_saved": True,
    "location_source": "geojson_centroid",
    "warnings": [],
}

_LOOKUP_ERROR = {"message": "connection reset", "code": "XX000", "hint": None, "details": None}


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _mock_user() -> MagicMock:
    user = MagicMock()
    user.id = _USER_ID
    return user


@pytest.fixture
def make_client():
    """Return a factory that builds a TestClient with auth + Supabase overridden."""

    def _make(supabase: MagicMock) -> TestClient:
        user = _mock_user()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_authenticated_client] = lambda: supabase
        return TestClient(app)

    try:
        yield _make
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_authenticated_client, None)


def _supabase_with_insert(return_data: list | None) -> MagicMock:
    mock = MagicMock()
    mock.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=return_data
    )
    return mock


def _chain(return_data) -> MagicMock:
    chain = MagicMock()
    for method in ("select", "eq", "in_", "order", "single", "limit"):
        getattr(chain, method).return_value = chain
    chain.execute.return_value = MagicMock(data=return_data)
    return chain


def _supabase_by_table(responses: dict) -> tuple[MagicMock, dict[str, MagicMock]]:
    """One chain per table, each returning its own data. Returns (client, chains)."""
    chains = {name: _chain(data) for name, data in responses.items()}
    mock = MagicMock()
    mock.table.side_effect = lambda name: chains.setdefault(name, _chain(None))
    return mock, chains


# ---------------------------------------------------------------------------
# POST /api/v1/fields/
# ---------------------------------------------------------------------------

class TestCreateField:
    def test_create_field_valid_data_returns_201(self, make_client):
        """Valid payload should create a field and return 201."""
        client = make_client(_supabase_with_insert([_FIELD_ROW]))

        response = client.post(f"{_BASE}/", json=_VALID_FIELD_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == _FIELD_ID
        assert body["name"] == "North 40"
        assert body["farm_id"] == _FARM_ID

    def test_create_field_sends_json_serialisable_farm_id(self, make_client):
        """farm_id is parsed as a UUID but must be sent to Supabase as a string."""
        mock_supabase = _supabase_with_insert([_FIELD_ROW])
        client = make_client(mock_supabase)

        client.post(f"{_BASE}/", json=_VALID_FIELD_PAYLOAD)

        inserted = mock_supabase.table.return_value.insert.call_args.args[0]
        assert inserted["farm_id"] == _FARM_ID
        assert isinstance(inserted["farm_id"], str)

    @pytest.mark.parametrize("missing", ["farm_id", "name", "acres", "crop_type"])
    def test_create_field_missing_required_field_returns_422(self, make_client, missing):
        """A payload missing any required field should return 422."""
        mock_supabase = MagicMock()
        client = make_client(mock_supabase)
        payload = {k: v for k, v in _VALID_FIELD_PAYLOAD.items() if k != missing}

        response = client.post(f"{_BASE}/", json=payload)

        assert response.status_code == 422
        mock_supabase.table.assert_not_called()

    @pytest.mark.parametrize("acres", [0, -10.0])
    def test_create_field_non_positive_acres_returns_422(self, make_client, acres):
        """acres must be > 0."""
        client = make_client(MagicMock())
        response = client.post(f"{_BASE}/", json={**_VALID_FIELD_PAYLOAD, "acres": acres})
        assert response.status_code == 422

    def test_create_field_non_uuid_farm_id_returns_422(self, make_client):
        """farm_id must be a UUID."""
        client = make_client(MagicMock())
        response = client.post(f"{_BASE}/", json={**_VALID_FIELD_PAYLOAD, "farm_id": "farm-1"})
        assert response.status_code == 422

    def test_create_field_db_failure_returns_500(self, make_client):
        """When Supabase insert returns no data, the router should return 500."""
        client = make_client(_supabase_with_insert(None))
        response = client.post(f"{_BASE}/", json=_VALID_FIELD_PAYLOAD)
        assert response.status_code == 500

    def test_create_field_api_error_returns_500(self, make_client):
        mock_supabase = _supabase_with_insert(None)
        mock_supabase.table.return_value.insert.return_value.execute.side_effect = APIError(
            _LOOKUP_ERROR
        )
        response = make_client(mock_supabase).post(f"{_BASE}/", json=_VALID_FIELD_PAYLOAD)
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to create field"

    def test_create_field_optional_boundary_geojson(self, make_client):
        """boundary_geojson is optional and should be accepted when valid GeoJSON."""
        boundary = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        }
        row = {**_FIELD_ROW, "boundary_geojson": boundary}
        client = make_client(_supabase_with_insert([row]))

        response = client.post(
            f"{_BASE}/", json={**_VALID_FIELD_PAYLOAD, "boundary_geojson": boundary}
        )

        assert response.status_code == 201

    def test_create_field_unclosed_polygon_returns_422(self, make_client):
        """A Polygon ring that is not closed violates RFC 7946 and is rejected."""
        boundary = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}
        client = make_client(MagicMock())

        response = client.post(
            f"{_BASE}/", json={**_VALID_FIELD_PAYLOAD, "boundary_geojson": boundary}
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/fields/?farm_id=
# ---------------------------------------------------------------------------

class TestListFields:
    def test_list_fields_returns_filtered_list(self, make_client):
        """GET /fields?farm_id= should return only fields belonging to that farm."""
        mock_supabase, _ = _supabase_by_table(
            {"farms": [{"id": _FARM_ID}], "fields": [_FIELD_ROW]}
        )
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/?farm_id={_FARM_ID}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["farm_id"] == _FARM_ID

    def test_list_fields_empty_farm_returns_empty_list(self, make_client):
        """An accessible farm with no fields should return an empty list."""
        mock_supabase, _ = _supabase_by_table({"farms": [{"id": _FARM_ID}], "fields": []})
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/?farm_id={_FARM_ID}")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_fields_unknown_farm_returns_404(self, make_client):
        """A farm that is missing or hidden by RLS is 404, not an empty list."""
        mock_supabase, chains = _supabase_by_table({"farms": [], "fields": []})
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/?farm_id={_FARM_ID}")

        assert response.status_code == 404
        chains["fields"].execute.assert_not_called()

    def test_list_fields_filters_by_farm_id(self, make_client):
        """The query must filter on farm_id (as a string) via .eq()."""
        mock_supabase, chains = _supabase_by_table(
            {"farms": [{"id": _FARM_ID}], "fields": [_FIELD_ROW]}
        )
        client = make_client(mock_supabase)

        client.get(f"{_BASE}/?farm_id={_FARM_ID}")

        chains["fields"].eq.assert_called_with("farm_id", _FARM_ID)

    def test_list_fields_missing_farm_id_returns_422(self, make_client):
        """farm_id query parameter is required; its absence should return 422."""
        client = make_client(MagicMock())
        response = client.get(f"{_BASE}/")
        assert response.status_code == 422

    def test_list_fields_non_uuid_farm_id_returns_422(self, make_client):
        """farm_id query parameter must be a UUID."""
        client = make_client(MagicMock())
        response = client.get(f"{_BASE}/?farm_id=not-a-uuid")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET/PATCH/DELETE /api/v1/fields/{field_id}
# ---------------------------------------------------------------------------

class TestGetUpdateDeleteField:
    def test_get_field_returns_row(self, make_client):
        mock_supabase, chains = _supabase_by_table({"fields": _FIELD_ROW})
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_FIELD_ID}")

        assert response.status_code == 200
        assert response.json()["id"] == _FIELD_ID
        chains["fields"].eq.assert_called_once_with("id", _FIELD_ID)

    def test_get_field_no_rows_returns_404(self, make_client):
        """PGRST116 (zero rows: missing or hidden by RLS) is a 404."""
        mock_supabase, chains = _supabase_by_table({"fields": None})
        chains["fields"].execute.side_effect = APIError(
            {"message": "JSON object requested, multiple (or no) rows returned", "code": "PGRST116"}
        )
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_MISSING_FIELD_ID}")

        assert response.status_code == 404

    def test_get_field_db_error_returns_500_not_404(self, make_client):
        """Any other database failure is a real error and must not look like 'not found'."""
        mock_supabase, chains = _supabase_by_table({"fields": None})
        chains["fields"].execute.side_effect = APIError(_LOOKUP_ERROR)
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_FIELD_ID}")

        assert response.status_code == 500

    @staticmethod
    def _supabase_with_update(return_data) -> tuple[MagicMock, MagicMock]:
        # spec mirrors postgrest's update builder, which has no .single().
        update_chain = MagicMock(spec=["eq", "execute"])
        update_chain.eq.return_value = update_chain
        update_chain.execute.return_value = MagicMock(data=return_data)
        mock = MagicMock()
        mock.table.return_value.update.return_value = update_chain
        return mock, update_chain

    def test_update_field_returns_updated_row(self, make_client):
        mock_supabase, update_chain = self._supabase_with_update(
            [{**_FIELD_ROW, "name": "Renamed"}]
        )
        client = make_client(mock_supabase)

        response = client.patch(f"{_BASE}/{_FIELD_ID}", json={"name": "Renamed"})

        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"
        mock_supabase.table.return_value.update.assert_called_once_with({"name": "Renamed"})
        update_chain.eq.assert_called_once_with("id", _FIELD_ID)

    def test_update_hidden_field_returns_404(self, make_client):
        """RLS turns an update on someone else's field into zero rows."""
        mock_supabase, _ = self._supabase_with_update([])
        client = make_client(mock_supabase)

        response = client.patch(f"{_BASE}/{_MISSING_FIELD_ID}", json={"name": "Renamed"})

        assert response.status_code == 404

    def test_update_field_db_error_returns_500(self, make_client):
        mock_supabase, update_chain = self._supabase_with_update(None)
        update_chain.execute.side_effect = APIError(_LOOKUP_ERROR)
        client = make_client(mock_supabase)

        response = client.patch(f"{_BASE}/{_FIELD_ID}", json={"name": "Renamed"})

        assert response.status_code == 500

    def test_delete_hidden_field_returns_404_without_deleting(self, make_client):
        mock_supabase, chains = _supabase_by_table({"fields": []})
        client = make_client(mock_supabase)

        response = client.delete(f"{_BASE}/{_MISSING_FIELD_ID}")

        assert response.status_code == 404
        chains["fields"].delete.assert_not_called()

    def test_delete_field_access_lookup_error_returns_500(self, make_client):
        mock_supabase, chains = _supabase_by_table({"fields": None})
        chains["fields"].execute.side_effect = APIError(_LOOKUP_ERROR)
        client = make_client(mock_supabase)

        response = client.delete(f"{_BASE}/{_FIELD_ID}")

        assert response.status_code == 500
        chains["fields"].delete.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/v1/fields/{field_id}/soil
# ---------------------------------------------------------------------------

class TestGetSoilProfile:
    def test_get_soil_returns_latest_profile(self, make_client):
        """GET /fields/{id}/soil should return the most recent soil record."""
        mock_supabase, _ = _supabase_by_table(
            {"fields": [{"id": _FIELD_ID}], "soil_profiles": [_SOIL_ROW]}
        )
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_FIELD_ID}/soil")

        assert response.status_code == 200
        body = response.json()
        assert body["field_id"] == _FIELD_ID
        assert body["organic_matter_pct"] == 3.2

    def test_get_soil_no_profile_returns_null(self, make_client):
        """An accessible field without a soil profile returns null."""
        mock_supabase, _ = _supabase_by_table(
            {"fields": [{"id": _FIELD_ID}], "soil_profiles": []}
        )
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_FIELD_ID}/soil")

        assert response.status_code == 200
        assert response.json() is None

    def test_get_soil_unknown_field_returns_404(self, make_client):
        """A field that is missing or hidden by RLS is 404, not null."""
        mock_supabase, chains = _supabase_by_table({"fields": [], "soil_profiles": []})
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_MISSING_FIELD_ID}/soil")

        assert response.status_code == 404
        chains["soil_profiles"].execute.assert_not_called()

    def test_get_soil_queries_soil_profiles_table(self, make_client):
        """The soil endpoint should query the 'soil_profiles' table for this field."""
        mock_supabase, chains = _supabase_by_table(
            {"fields": [{"id": _FIELD_ID}], "soil_profiles": [_SOIL_ROW]}
        )
        client = make_client(mock_supabase)

        client.get(f"{_BASE}/{_FIELD_ID}/soil")

        mock_supabase.table.assert_called_with("soil_profiles")
        chains["soil_profiles"].eq.assert_called_with("field_id", _FIELD_ID)

    def test_get_soil_orders_by_fetched_at_desc(self, make_client):
        """The query must order by fetched_at descending to get the most recent entry."""
        mock_supabase, chains = _supabase_by_table(
            {"fields": [{"id": _FIELD_ID}], "soil_profiles": [_SOIL_ROW]}
        )
        client = make_client(mock_supabase)

        client.get(f"{_BASE}/{_FIELD_ID}/soil")

        chains["soil_profiles"].order.assert_called_with("fetched_at", desc=True)


# ---------------------------------------------------------------------------
# GET /api/v1/fields/{field_id}/weather
# ---------------------------------------------------------------------------

class TestGetWeather:
    def test_get_weather_returns_list(self, make_client):
        """GET /fields/{id}/weather should return a list of weather records."""
        mock_supabase, _ = _supabase_by_table(
            {"fields": [{"id": _FIELD_ID}], "weather_cache": [_WEATHER_ROW]}
        )
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_FIELD_ID}/weather")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["field_id"] == _FIELD_ID

    def test_get_weather_null_soil_temp_is_returned_as_null(self, make_client):
        """soil_temp is nullable in weather_cache; a missing reading must not 500."""
        row = {**_WEATHER_ROW, "soil_temp": None}
        mock_supabase, _ = _supabase_by_table(
            {"fields": [{"id": _FIELD_ID}], "weather_cache": [row]}
        )
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_FIELD_ID}/weather")

        assert response.status_code == 200
        assert response.json()[0]["soil_temp"] is None

    def test_get_weather_empty_returns_empty_list(self, make_client):
        """An accessible field with no weather data returns an empty list."""
        mock_supabase, _ = _supabase_by_table(
            {"fields": [{"id": _FIELD_ID}], "weather_cache": []}
        )
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_FIELD_ID}/weather")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_weather_unknown_field_returns_404(self, make_client):
        """A field that is missing or hidden by RLS is 404, not an empty list."""
        mock_supabase, chains = _supabase_by_table({"fields": [], "weather_cache": []})
        client = make_client(mock_supabase)

        response = client.get(f"{_BASE}/{_MISSING_FIELD_ID}/weather")

        assert response.status_code == 404
        chains["weather_cache"].execute.assert_not_called()

    def test_get_weather_limits_to_7_days(self, make_client):
        """The weather query should call .limit(7)."""
        mock_supabase, chains = _supabase_by_table(
            {"fields": [{"id": _FIELD_ID}], "weather_cache": [_WEATHER_ROW]}
        )
        client = make_client(mock_supabase)

        client.get(f"{_BASE}/{_FIELD_ID}/weather")

        chains["weather_cache"].limit.assert_called_with(7)

    def test_get_weather_queries_weather_cache_table(self, make_client):
        """The endpoint should query the 'weather_cache' table."""
        mock_supabase, _ = _supabase_by_table(
            {"fields": [{"id": _FIELD_ID}], "weather_cache": []}
        )
        client = make_client(mock_supabase)

        client.get(f"{_BASE}/{_FIELD_ID}/weather")

        mock_supabase.table.assert_called_with("weather_cache")


# ---------------------------------------------------------------------------
# Database error handling on list/soil/weather reads
# ---------------------------------------------------------------------------

_READ_ROUTES = [
    ("fields", f"{_BASE}/?farm_id={_FARM_ID}", "Failed to list fields"),
    ("soil_profiles", f"{_BASE}/{_FIELD_ID}/soil", "Failed to retrieve soil profile"),
    ("weather_cache", f"{_BASE}/{_FIELD_ID}/weather", "Failed to retrieve weather data"),
]


class TestReadErrorHandling:
    @pytest.mark.parametrize(("table", "url", "detail"), _READ_ROUTES)
    @pytest.mark.parametrize(
        "error",
        [APIError(_LOOKUP_ERROR), httpx.ReadTimeout("timed out")],
        ids=["api_error", "transport_error"],
    )
    def test_db_error_returns_500(self, make_client, table, url, detail, error):
        mock_supabase, chains = _supabase_by_table(
            {"farms": [{"id": _FARM_ID}], "fields": [{"id": _FIELD_ID}], table: []}
        )
        # The list route checks access via farms; soil/weather check via fields.
        chains[table].execute.side_effect = error

        response = make_client(mock_supabase).get(url)

        assert response.status_code == 500
        assert response.json()["detail"] == detail

    @pytest.mark.parametrize(("table", "url", "_detail"), _READ_ROUTES)
    def test_non_db_error_propagates(self, make_client, table, url, _detail):
        """Only database errors are caught; a bug is not reported as a DB failure."""
        mock_supabase, chains = _supabase_by_table(
            {"farms": [{"id": _FARM_ID}], "fields": [{"id": _FIELD_ID}], table: []}
        )
        chains[table].execute.side_effect = TypeError("bug")

        with pytest.raises(TypeError):
            make_client(mock_supabase).get(url)


# ---------------------------------------------------------------------------
# POST /api/v1/fields/{field_id}/enrich
# ---------------------------------------------------------------------------

class TestEnrichField:
    def test_enrich_existing_field_returns_202(self, make_client):
        """POST /fields/{id}/enrich on an accessible field should return 202."""
        mock_supabase, _ = _supabase_by_table({"fields": [{"id": _FIELD_ID}]})
        client = make_client(mock_supabase)

        with patch(
            "app.routers.fields.run_enrichment",
            new=AsyncMock(return_value=_ENRICHMENT_RESULT),
        ):
            response = client.post(f"{_BASE}/{_FIELD_ID}/enrich")

        assert response.status_code == 202

    def test_enrich_returns_correct_summary_keys(self, make_client):
        """The 202 response should contain status, field_id, weather_days_upserted,
        soil_profile_saved, location_source and warnings."""
        mock_supabase, _ = _supabase_by_table({"fields": [{"id": _FIELD_ID}]})
        client = make_client(mock_supabase)
        enrichment_result = {
            "field_id": _FIELD_ID,
            "weather_days_upserted": 5,
            "soil_profile_saved": False,
            "location_source": "county_centroid_approximate",
            "warnings": ["SSURGO service unavailable"],
        }

        with patch(
            "app.routers.fields.run_enrichment",
            new=AsyncMock(return_value=enrichment_result),
        ):
            response = client.post(f"{_BASE}/{_FIELD_ID}/enrich")

        body = response.json()
        assert body["status"] == "enrichment_complete"
        assert body["field_id"] == _FIELD_ID
        assert body["weather_days_upserted"] == 5
        assert body["soil_profile_saved"] is False
        assert body["location_source"] == "county_centroid_approximate"
        assert "SSURGO service unavailable" in body["warnings"]

    def test_enrich_nonexistent_field_returns_404(self, make_client):
        """A field not accessible via RLS should return 404 without enriching."""
        mock_supabase, _ = _supabase_by_table({"fields": []})
        client = make_client(mock_supabase)
        run_mock = AsyncMock(return_value=_ENRICHMENT_RESULT)

        with patch("app.routers.fields.run_enrichment", new=run_mock):
            response = client.post(f"{_BASE}/{_MISSING_FIELD_ID}/enrich")

        assert response.status_code == 404
        run_mock.assert_not_awaited()

    def test_enrich_access_lookup_failure_returns_500(self, make_client):
        """A database error during the access check is a real failure, not a 404."""
        mock_supabase, chains = _supabase_by_table({"fields": None})
        chains["fields"].execute.side_effect = APIError(_LOOKUP_ERROR)
        client = make_client(mock_supabase)
        run_mock = AsyncMock(return_value=_ENRICHMENT_RESULT)

        with patch("app.routers.fields.run_enrichment", new=run_mock):
            response = client.post(f"{_BASE}/{_FIELD_ID}/enrich")

        assert response.status_code == 500
        run_mock.assert_not_awaited()

    def test_enrich_passes_supabase_client_to_run_enrichment(self, make_client):
        """The authenticated supabase client and the field id (as str) must be forwarded."""
        mock_supabase, _ = _supabase_by_table({"fields": [{"id": _FIELD_ID}]})
        client = make_client(mock_supabase)
        captured_calls: list[dict] = []

        async def capturing_run_enrichment(field_id, supabase):
            captured_calls.append({"field_id": field_id, "supabase": supabase})
            return _ENRICHMENT_RESULT

        with patch("app.routers.fields.run_enrichment", side_effect=capturing_run_enrichment):
            client.post(f"{_BASE}/{_FIELD_ID}/enrich")

        assert len(captured_calls) == 1
        assert captured_calls[0]["field_id"] == _FIELD_ID
        assert isinstance(captured_calls[0]["field_id"], str)
        assert captured_calls[0]["supabase"] is mock_supabase

    def test_enrich_is_rate_limited_to_10_per_hour(self, make_client):
        """Enrichment calls two external APIs, so it is limited to 10 requests/hour."""
        mock_supabase, _ = _supabase_by_table({"fields": [{"id": _FIELD_ID}]})
        client = make_client(mock_supabase)

        limiter.reset()
        limiter.enabled = True
        try:
            with patch(
                "app.routers.fields.run_enrichment",
                new=AsyncMock(return_value=_ENRICHMENT_RESULT),
            ):
                statuses = [
                    client.post(f"{_BASE}/{_FIELD_ID}/enrich").status_code for _ in range(11)
                ]
        finally:
            limiter.enabled = False
            limiter.reset()

        assert statuses[:10] == [202] * 10
        assert statuses[10] == 429
