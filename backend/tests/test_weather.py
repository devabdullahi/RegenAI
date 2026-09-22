"""
Tests for app.services.weather — Open-Meteo forecast fetch and parsing.

httpx is served by a MockTransport, so no network calls are made.

Coverage targets:
  - Request goes to settings.open_meteo_forecast_url
  - Complete days parsed into weather_cache rows
  - Missing temperature/precipitation → day skipped and reported, never 0.0
  - Missing soil temperature → None
  - Timeout / HTTP error → empty forecast
"""

import httpx
import pytest

from app.services import weather
from app.services.weather import _parse_forecast, fetch_weather_forecast

_FIELD_ID = "field-weather-1"
_TEST_URL = "https://weather.test/v1/forecast"


def _payload(**daily_overrides) -> dict:
    daily = {
        "time": ["2026-04-20", "2026-04-21"],
        "temperature_2m_max": [20.5, 22.0],
        "temperature_2m_min": [8.0, 9.5],
        "precipitation_sum": [0.0, 3.2],
        "soil_temperature_0cm_max": [14.0, 15.0],
    }
    daily.update(daily_overrides)
    return {"daily": daily}


@pytest.fixture
def mock_http(monkeypatch):
    """Route weather.httpx.AsyncClient through a MockTransport with a settable handler."""
    state: dict = {"handler": lambda request: httpx.Response(200, json=_payload())}
    requests: list[httpx.Request] = []
    real_client = httpx.AsyncClient

    def _handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return state["handler"](request)

    def _client_factory(*_args, **kwargs):
        return real_client(transport=httpx.MockTransport(_handler), timeout=kwargs.get("timeout"))

    monkeypatch.setattr(weather.httpx, "AsyncClient", _client_factory)
    monkeypatch.setattr(weather.settings, "open_meteo_forecast_url", _TEST_URL)
    state["requests"] = requests
    return state


@pytest.mark.asyncio
class TestFetchWeatherForecast:
    async def test_uses_configured_url_and_parses_rows(self, mock_http):
        forecast = await fetch_weather_forecast(42.0, -93.0, _FIELD_ID)

        request = mock_http["requests"][0]
        assert str(request.url).startswith(_TEST_URL)
        assert len(forecast.rows) == 2
        assert forecast.skipped_dates == []
        first = forecast.rows[0]
        assert first["field_id"] == _FIELD_ID
        assert first["temp_high"] == 20.5
        assert first["precip_mm"] == 0.0

    async def test_requests_configured_forecast_length(self, mock_http):
        await fetch_weather_forecast(42.0, -93.0, _FIELD_ID)

        params = mock_http["requests"][0].url.params
        assert params["forecast_days"] == str(weather.FORECAST_DAYS)

    async def test_non_json_body_returns_empty_forecast(self, mock_http):
        mock_http["handler"] = lambda request: httpx.Response(200, text="<html>maintenance</html>")
        forecast = await fetch_weather_forecast(42.0, -93.0, _FIELD_ID)

        assert forecast.rows == []

    async def test_timeout_returns_empty_forecast(self, mock_http):
        def _timeout(request):
            raise httpx.ReadTimeout("slow", request=request)

        mock_http["handler"] = _timeout
        forecast = await fetch_weather_forecast(42.0, -93.0, _FIELD_ID)

        assert forecast.rows == []

    async def test_http_error_returns_empty_forecast(self, mock_http):
        mock_http["handler"] = lambda request: httpx.Response(500, text="upstream down")
        forecast = await fetch_weather_forecast(42.0, -93.0, _FIELD_ID)

        assert forecast.rows == []


class TestParseForecast:
    def test_missing_temperature_skips_day_instead_of_zero(self):
        payload = _payload(temperature_2m_max=[None, 22.0])
        forecast = _parse_forecast(payload, _FIELD_ID, "2026-04-20T00:00:00+00:00")

        assert [r["date"] for r in forecast.rows] == ["2026-04-21"]
        assert forecast.skipped_dates == ["2026-04-20"]
        assert all(r["temp_high"] != 0.0 for r in forecast.rows)

    def test_short_precipitation_array_skips_day(self):
        payload = _payload(precipitation_sum=[1.0])
        forecast = _parse_forecast(payload, _FIELD_ID, "2026-04-20T00:00:00+00:00")

        assert forecast.skipped_dates == ["2026-04-21"]

    def test_missing_soil_temperature_is_none(self):
        payload = _payload(soil_temperature_0cm_max=[None])
        forecast = _parse_forecast(payload, _FIELD_ID, "2026-04-20T00:00:00+00:00")

        assert len(forecast.rows) == 2
        assert forecast.rows[0]["soil_temp"] is None
        assert forecast.rows[1]["soil_temp"] is None

    def test_non_object_payload_returns_empty(self):
        """A JSON array body used to raise AttributeError out of the parser."""
        forecast = _parse_forecast(["unexpected"], _FIELD_ID, "2026-04-20T00:00:00+00:00")
        assert forecast.rows == []
        assert forecast.skipped_dates == []

    def test_no_daily_data_returns_empty(self):
        forecast = _parse_forecast({}, _FIELD_ID, "2026-04-20T00:00:00+00:00")
        assert forecast.rows == []
        assert forecast.skipped_dates == []
