"""
Tests for app.services.soil — SSURGO SDA query and parsing.

httpx is served by a MockTransport, so no network calls are made.

Coverage targets:
  - Request goes to settings.ssurgo_sda_url
  - Complete dominant component → profile
  - Missing pH or organic matter → no profile, missing readings reported (never 7.0 / 0.0)
  - Point outside mapped area, timeout, HTTP error → no profile
"""

import httpx
import pytest

from app.services import soil
from app.services.soil import _parse_soil_response, fetch_soil_profile

_FIELD_ID = "field-soil-1"
_TEST_URL = "https://sda.test/Tabular/post.rest"
_HEADER = ["musym", "muname", "comppct_r", "compname", "taxclname", "organic_matter", "ph",
           "texture"]


def _row(om=3.5, ph=6.8) -> list:
    return ["WbA", "Webster silty clay loam", 85, "Webster", "Fine...", om, ph, "Silty clay loam"]


@pytest.fixture
def mock_http(monkeypatch):
    """Route soil.httpx.AsyncClient through a MockTransport with a settable handler."""
    state: dict = {
        "handler": lambda request: httpx.Response(200, json={"Table": [_HEADER, _row()]})
    }
    requests: list[httpx.Request] = []
    real_client = httpx.AsyncClient

    def _handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return state["handler"](request)

    def _client_factory(*_args, **kwargs):
        return real_client(transport=httpx.MockTransport(_handler), timeout=kwargs.get("timeout"))

    monkeypatch.setattr(soil.httpx, "AsyncClient", _client_factory)
    monkeypatch.setattr(soil.settings, "ssurgo_sda_url", _TEST_URL)
    state["requests"] = requests
    return state


@pytest.mark.asyncio
class TestFetchSoilProfile:
    async def test_uses_configured_url_and_returns_profile(self, mock_http):
        lookup = await fetch_soil_profile(42.0, -93.0, _FIELD_ID)

        assert str(mock_http["requests"][0].url) == _TEST_URL
        assert lookup.profile is not None
        assert lookup.profile["ph"] == 6.8
        assert lookup.profile["organic_matter_pct"] == 3.5
        assert lookup.missing_readings == []

    async def test_timeout_returns_no_profile(self, mock_http):
        def _timeout(request):
            raise httpx.ReadTimeout("slow", request=request)

        mock_http["handler"] = _timeout
        lookup = await fetch_soil_profile(42.0, -93.0, _FIELD_ID)

        assert lookup.profile is None
        assert lookup.missing_readings == []

    async def test_non_json_body_returns_no_profile(self, mock_http):
        mock_http["handler"] = lambda request: httpx.Response(200, text="Invalid query")
        lookup = await fetch_soil_profile(42.0, -93.0, _FIELD_ID)

        assert lookup.profile is None

    async def test_http_error_returns_no_profile(self, mock_http):
        mock_http["handler"] = lambda request: httpx.Response(500, text="SDA error")
        lookup = await fetch_soil_profile(42.0, -93.0, _FIELD_ID)

        assert lookup.profile is None


class TestParseSoilResponse:
    def test_missing_ph_is_not_invented(self):
        lookup = _parse_soil_response({"Table": [_HEADER, _row(ph=None)]}, _FIELD_ID, "t")

        assert lookup.profile is None
        assert lookup.missing_readings == ["ph"]

    def test_missing_organic_matter_is_not_invented(self):
        lookup = _parse_soil_response({"Table": [_HEADER, _row(om=None)]}, _FIELD_ID, "t")

        assert lookup.profile is None
        assert lookup.missing_readings == ["organic_matter_pct"]

    def test_both_readings_missing(self):
        lookup = _parse_soil_response({"Table": [_HEADER, _row(om=None, ph=None)]}, _FIELD_ID, "t")

        assert lookup.missing_readings == ["ph", "organic_matter_pct"]

    def test_table_that_is_not_a_list_returns_no_profile(self):
        """{"Table": null} used to raise TypeError out of the parser."""
        lookup = _parse_soil_response({"Table": None}, _FIELD_ID, "t")

        assert lookup.profile is None
        assert lookup.missing_readings == []

    def test_outside_mapped_area_returns_no_profile(self):
        lookup = _parse_soil_response({"Table": [_HEADER]}, _FIELD_ID, "t")

        assert lookup.profile is None
        assert lookup.missing_readings == []
