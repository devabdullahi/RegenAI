"""
Tests for app.services.enrichment — weather + soil orchestration.

Coverage targets:
  - GeoJSON boundary → location_source="geojson_centroid", no approximation warning
  - County-centroid fallback → location_source="county_centroid_approximate" + warning
  - No coordinates → warning, nothing fetched
  - Weather / soil database write failures → visible warnings (not silent 0/False)
  - Skipped weather days and incomplete soil readings → warnings
  - The nationwide county centroid table: coverage, shape and plausibility
  - Drift guards: Celery scaffolding removed
"""

import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from postgrest.exceptions import APIError

from app.services import enrichment
from app.services.county_centroids import (
    _DATA_PATH,
    COUNTY_CENTROIDS,
    COUNTY_DATA_AS_OF,
    COUNTY_DATA_SOURCES,
    COUNTY_RECORDS,
    lookup_county_centroid,
    normalize_county_fips,
)
from app.services.enrichment import _centroid_from_geojson, run_enrichment
from app.services.soil import SoilLookup
from app.services.weather import WeatherForecast

_FIELD_ID = "field-enrich-1"
_FARM_ID = "farm-enrich-1"
_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[-93.0, 42.0], [-92.0, 42.0], [-92.0, 43.0], [-93.0, 42.0]]],
}
_WEATHER_ROW = {
    "field_id": _FIELD_ID,
    "date": "2026-04-20",
    "temp_high": 20.0,
    "temp_low": 8.0,
    "precip_mm": 1.0,
    "soil_temp": None,
    "fetched_at": "2026-04-20T00:00:00+00:00",
}
_SOIL_PROFILE = {
    "field_id": _FIELD_ID,
    "ssurgo_map_unit": "WbA",
    "texture": "Silty clay loam",
    "ph": 6.8,
    "organic_matter_pct": 3.5,
    "source": "ssurgo",
    "fetched_at": "2026-04-20T00:00:00+00:00",
}


class _FakeQuery:
    def __init__(self, db: "_FakeSupabase", table: str):
        self._db = db
        self._table = table
        self._write = None

    def select(self, *_args, **_kwargs):
        return self

    eq = single = limit = order = select

    def upsert(self, rows, **_kwargs):
        self._write = rows
        return self

    insert = upsert

    def execute(self):
        if self._write is not None:
            if self._table in self._db.failing_writes:
                raise APIError({"message": f"{self._table} write failed"})
            rows = self._write if isinstance(self._write, list) else [self._write]
            return MagicMock(data=rows)
        return MagicMock(data=self._db.tables.get(self._table))


class _FakeSupabase:
    def __init__(self, field: dict, farm: dict, failing_writes: set[str] | None = None):
        self.tables = {"fields": field, "farms": farm}
        self.failing_writes = failing_writes or set()

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self, name)


@pytest.fixture
def fake_fetches(monkeypatch):
    """Replace the network fetches; tests adjust the return values."""
    weather = AsyncMock(return_value=WeatherForecast(rows=[_WEATHER_ROW], skipped_dates=[]))
    soil = AsyncMock(return_value=SoilLookup(profile=_SOIL_PROFILE, missing_readings=[]))
    monkeypatch.setattr(enrichment, "fetch_weather_forecast", weather)
    monkeypatch.setattr(enrichment, "fetch_soil_profile", soil)
    return weather, soil


def _field(boundary=None) -> dict:
    return {"id": _FIELD_ID, "farm_id": _FARM_ID, "boundary_geojson": boundary}


_FARM_IN_TABLE = {"id": _FARM_ID, "county_fips": "19153"}
# 99999 is not a county FIPS code; the nationwide table covers every real one.
_FARM_NOT_IN_TABLE = {"id": _FARM_ID, "county_fips": "99999"}
_FARM_WITHOUT_FIPS = {"id": _FARM_ID, "county_fips": ""}


@pytest.mark.asyncio
class TestLocationSource:
    async def test_boundary_uses_geojson_centroid(self, fake_fetches):
        db = _FakeSupabase(_field(_POLYGON), _FARM_IN_TABLE)
        result = await run_enrichment(_FIELD_ID, db)

        assert result["location_source"] == "geojson_centroid"
        assert result["warnings"] == []
        assert result["weather_days_upserted"] == 1
        assert result["soil_profile_saved"] is True

    async def test_county_fallback_is_flagged_approximate(self, fake_fetches):
        db = _FakeSupabase(_field(), _FARM_IN_TABLE)
        result = await run_enrichment(_FIELD_ID, db)

        assert result["location_source"] == "county_centroid_approximate"
        assert any("county centre" in w for w in result["warnings"])
        weather, _ = fake_fetches
        lat, lng, _field_id = weather.await_args.args
        assert (lat, lng) == COUNTY_CENTROIDS["19153"]

    async def test_county_fallback_works_outside_the_midwest(self, fake_fetches):
        """Enrichment used to cover only IA/KS/IL; every state must resolve now."""
        db = _FakeSupabase(_field(), {"id": _FARM_ID, "county_fips": "39049"})  # Franklin, OH
        result = await run_enrichment(_FIELD_ID, db)

        assert result["location_source"] == "county_centroid_approximate"
        weather, _ = fake_fetches
        lat, lng, _field_id = weather.await_args.args
        assert (lat, lng) == COUNTY_CENTROIDS["39049"]

    async def test_no_coordinates_skips_fetches(self, fake_fetches):
        db = _FakeSupabase(_field(), _FARM_NOT_IN_TABLE)
        result = await run_enrichment(_FIELD_ID, db)

        assert result["location_source"] is None
        assert any("Could not resolve coordinates" in w for w in result["warnings"])
        weather, soil = fake_fetches
        weather.assert_not_awaited()
        soil.assert_not_awaited()

    async def test_missing_county_fips_skips_fetches(self, fake_fetches):
        db = _FakeSupabase(_field(), _FARM_WITHOUT_FIPS)
        result = await run_enrichment(_FIELD_ID, db)

        assert result["location_source"] is None
        assert any("Could not resolve coordinates" in w for w in result["warnings"])
        weather, soil = fake_fetches
        weather.assert_not_awaited()
        soil.assert_not_awaited()


@pytest.mark.asyncio
class TestWriteFailuresAreVisible:
    async def test_weather_write_failure_adds_warning(self, fake_fetches):
        db = _FakeSupabase(_field(_POLYGON), _FARM_IN_TABLE, failing_writes={"weather_cache"})
        result = await run_enrichment(_FIELD_ID, db)

        assert result["weather_days_upserted"] == 0
        assert any("Weather data could not be saved" in w for w in result["warnings"])
        assert result["soil_profile_saved"] is True

    async def test_soil_write_failure_adds_warning(self, fake_fetches):
        db = _FakeSupabase(_field(_POLYGON), _FARM_IN_TABLE, failing_writes={"soil_profiles"})
        result = await run_enrichment(_FIELD_ID, db)

        assert result["soil_profile_saved"] is False
        assert any("Soil profile could not be saved" in w for w in result["warnings"])


@pytest.mark.asyncio
class TestIncompleteReadings:
    async def test_skipped_weather_days_are_reported(self, fake_fetches):
        weather, _ = fake_fetches
        weather.return_value = WeatherForecast(rows=[_WEATHER_ROW], skipped_dates=["2026-04-21"])
        db = _FakeSupabase(_field(_POLYGON), _FARM_IN_TABLE)

        result = await run_enrichment(_FIELD_ID, db)

        assert any("2026-04-21" in w for w in result["warnings"])

    async def test_missing_soil_readings_are_reported(self, fake_fetches):
        _, soil = fake_fetches
        soil.return_value = SoilLookup(profile=None, missing_readings=["ph"])
        db = _FakeSupabase(_field(_POLYGON), _FARM_IN_TABLE)

        result = await run_enrichment(_FIELD_ID, db)

        assert result["soil_profile_saved"] is False
        assert any("no ph reading" in w for w in result["warnings"])

    async def test_no_weather_data_is_reported(self, fake_fetches):
        weather, _ = fake_fetches
        weather.return_value = WeatherForecast(rows=[], skipped_dates=[])
        db = _FakeSupabase(_field(_POLYGON), _FARM_IN_TABLE)

        result = await run_enrichment(_FIELD_ID, db)

        assert result["weather_days_upserted"] == 0
        assert any("no usable data" in w for w in result["warnings"])


class TestMalformedBoundary:
    def test_malformed_geojson_is_logged_as_warning(self, caplog):
        """A bad boundary silently falls back to the county centre; it must be visible."""
        bad_polygon = {"type": "Polygon", "coordinates": [[["not", "numbers"]]]}

        with caplog.at_level(logging.WARNING, logger="app.services.enrichment"):
            assert _centroid_from_geojson(bad_polygon) is None

        assert "malformed GeoJSON" in caplog.text


class TestCountyCentroidTable:
    """The table is generated data; these guard its coverage and plausibility.

    Counts come from the 2026 Census Gazetteer county file (3,144 counties and
    county equivalents across the 50 states and DC, plus 78 Puerto Rico
    municipios) with Connecticut's 8 pre-2022 counties carried forward from the
    2020 file, because USDA program records still use those codes.
    """

    def test_covers_every_us_county(self):
        current_us_counties = [
            fips
            for fips, record in COUNTY_RECORDS.items()
            if record["state"] != "PR" and record["source"] == "2026"
        ]
        assert len(current_us_counties) == 3144
        assert len(COUNTY_RECORDS) == 3230

    def test_covers_all_fifty_states_dc_and_puerto_rico(self):
        states = {record["state"] for record in COUNTY_RECORDS.values()}
        assert len(states) == 52  # 50 states + DC + PR (the only territory in the source)
        assert {"AK", "HI", "DC", "PR", "IA", "KS", "IL", "TX"} <= states

    def test_retired_connecticut_counties_still_resolve(self):
        """Connecticut replaced counties with planning regions in 2022."""
        legacy = {fips for fips, r in COUNTY_RECORDS.items() if r["source"] == "2020"}
        assert legacy == {"09001", "09003", "09005", "09007", "09009", "09011", "09013", "09015"}
        assert lookup_county_centroid("09003") is not None  # Hartford County
        assert lookup_county_centroid("09110") is not None  # Capitol Planning Region

    def test_every_key_is_a_five_digit_fips(self):
        bad_keys = [fips for fips in COUNTY_RECORDS if len(fips) != 5 or not fips.isdigit()]
        assert bad_keys == []

    def test_no_duplicate_fips_in_the_data_file(self):
        """json.load would silently keep the last of any duplicated key."""
        document = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
        raw_pairs = json.loads(
            _DATA_PATH.read_text(encoding="utf-8"),
            object_pairs_hook=lambda pairs: pairs,
        )
        county_pairs = dict(raw_pairs)["counties"]
        assert len(county_pairs) == len(document["counties"])

    def test_state_prefix_is_consistent(self):
        """The first two FIPS digits are the state, so they must not disagree."""
        states_by_prefix: dict[str, set[str]] = {}
        for fips, record in COUNTY_RECORDS.items():
            states_by_prefix.setdefault(fips[:2], set()).add(record["state"])
        conflicts = {prefix: s for prefix, s in states_by_prefix.items() if len(s) > 1}
        assert conflicts == {}

    def test_coordinates_are_inside_plausible_bounds(self):
        # Generous boxes: Alaska crosses the antimeridian (the Aleutians sit at
        # positive longitude) and Puerto Rico's Mayaguez reaches Mona Island.
        bounds = {
            "HI": (18.5, 22.5, -161.0, -154.0),
            "PR": (17.8, 18.7, -68.0, -65.2),
        }
        out_of_bounds = []
        for fips, record in COUNTY_RECORDS.items():
            lat, lon, state = record["lat"], record["lon"], record["state"]
            if state == "AK":
                inside = 51.0 <= lat <= 72.0 and (-180.0 <= lon <= -129.0 or 172.0 <= lon <= 180.0)
            else:
                min_lat, max_lat, min_lon, max_lon = bounds.get(state, (24.4, 49.5, -125.1, -66.8))
                inside = min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
            if not inside:
                out_of_bounds.append((fips, record))
        assert out_of_bounds == []

    @pytest.mark.parametrize(
        ("fips", "name", "state", "lat", "lon"),
        [
            ("19169", "Story County", "IA", 42.0375, -93.4661),
            ("19153", "Polk County", "IA", 41.6843, -93.5682),
            ("17019", "Champaign County", "IL", 40.1390, -88.1970),
            ("20177", "Shawnee County", "KS", 39.0417, -95.7568),
            ("06037", "Los Angeles County", "CA", 34.1964, -118.2619),
        ],
    )
    def test_spot_checks_against_known_counties(self, fips, name, state, lat, lon):
        record = COUNTY_RECORDS[fips]
        assert (record["name"], record["state"]) == (name, state)
        assert record["lat"] == pytest.approx(lat, abs=0.01)
        assert record["lon"] == pytest.approx(lon, abs=0.01)

    def test_provenance_is_recorded(self):
        """CLAUDE.md §4: sourced data carries as_of and source_url."""
        assert COUNTY_DATA_AS_OF
        assert COUNTY_DATA_SOURCES
        for source in COUNTY_DATA_SOURCES:
            assert source["source_url"].startswith("https://www2.census.gov/geo/docs/")
            assert source["vintage"]


class TestFipsNormalization:
    def test_pads_codes_that_lost_a_leading_zero(self):
        """01001 becomes 1001 whenever a FIPS code round-trips through an int."""
        assert normalize_county_fips("1001") == "01001"
        assert normalize_county_fips(1001) == "01001"
        assert lookup_county_centroid("1001") == COUNTY_CENTROIDS["01001"]

    def test_rejects_values_that_cannot_be_a_fips_code(self):
        assert normalize_county_fips(None) is None
        assert normalize_county_fips("") is None
        assert normalize_county_fips("19-169") is None
        assert normalize_county_fips("191690") is None
        assert lookup_county_centroid("") is None


class TestDriftGuards:
    def test_table_is_loaded_from_the_generated_data_file(self):
        """The table must stay data; a hand-edited dict in code is what we replaced."""
        assert _DATA_PATH.name == "county_centroids.json"
        assert not hasattr(enrichment, "COUNTY_CENTROIDS")

    def test_celery_scaffolding_removed(self):
        assert not hasattr(enrichment, "run_enrichment_sync")
        assert not hasattr(enrichment, "get_admin_client")
