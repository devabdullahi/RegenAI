"""
Open-Meteo weather service.

Fetches a 7-day forecast from the Open-Meteo public API (no key required) and
returns records shaped to match the `weather_cache` table schema.

Missing readings are never replaced with made-up values. `weather_cache`
requires temp_high, temp_low and precip_mm (NOT NULL), so a day missing any of
them is skipped and reported; soil_temp is nullable and stored as None.

API docs: https://open-meteo.com/en/docs
"""

import logging
from datetime import datetime, timezone
from typing import NamedTuple, TypedDict

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Daily variables we request.  The names match Open-Meteo's query parameter
# values exactly; they also map 1-to-1 to what we parse below.
_DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "soil_temperature_0cm_max",
]

# How long (seconds) to wait for the Open-Meteo server to respond.
_TIMEOUT_SECONDS = 20.0

#: Days requested per forecast; context.py sizes its weather_cache read from it.
FORECAST_DAYS = 7

# Daily aggregates are bucketed by local day. Target-state farms are mostly on
# US Central time.
_FORECAST_TIMEZONE = "America/Chicago"


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

class WeatherData(TypedDict):
    """One row of the `weather_cache` table (without auto-generated columns)."""

    field_id: str
    date: str                # ISO-8601 date string  e.g. "2026-04-02"
    temp_high: float         # °C
    temp_low: float          # °C
    precip_mm: float         # mm
    soil_temp: float | None  # °C at 0 cm depth; None when the API has no reading
    fetched_at: str          # ISO-8601 UTC datetime string


class WeatherForecast(NamedTuple):
    """Parsed forecast rows plus the dates dropped for missing required readings."""

    rows: list[WeatherData]
    skipped_dates: list[str]


# ---------------------------------------------------------------------------
# Core fetch function
# ---------------------------------------------------------------------------

async def fetch_weather_forecast(
    latitude: float,
    longitude: float,
    field_id: str,
) -> WeatherForecast:
    """Fetch a 7-day forecast from Open-Meteo for the given coordinates.

    Args:
        latitude: Decimal degrees, WGS-84.
        longitude: Decimal degrees, WGS-84.
        field_id: UUID of the field; embedded into every returned record so
            the enrichment layer can insert them directly.

    Returns:
        A WeatherForecast. ``rows`` is empty if the API call fails — callers
        treat this as non-fatal and report it as a warning.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(_DAILY_VARS),
        "timezone": _FORECAST_TIMEZONE,
        "forecast_days": FORECAST_DAYS,
    }

    fetched_at = datetime.now(tz=timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            logger.info(
                "Fetching Open-Meteo forecast for field=%s lat=%.4f lon=%.4f",
                field_id,
                latitude,
                longitude,
            )
            response = await client.get(settings.open_meteo_forecast_url, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException:
        logger.warning(
            "Open-Meteo request timed out after %.0fs for field=%s",
            _TIMEOUT_SECONDS,
            field_id,
        )
        return WeatherForecast(rows=[], skipped_dates=[])
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Open-Meteo returned HTTP %s for field=%s: %s",
            exc.response.status_code,
            field_id,
            exc.response.text[:200],
        )
        return WeatherForecast(rows=[], skipped_dates=[])
    except (httpx.HTTPError, ValueError) as exc:
        # Connection errors, and bodies that are not JSON (JSONDecodeError is a ValueError).
        logger.warning(
            "Open-Meteo request failed for field=%s: %s: %s", field_id, type(exc).__name__, exc
        )
        return WeatherForecast(rows=[], skipped_dates=[])

    return _parse_forecast(payload, field_id, fetched_at)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_forecast(
    payload: dict,
    field_id: str,
    fetched_at: str,
) -> WeatherForecast:
    """Convert a raw Open-Meteo JSON response into WeatherData records.

    Open-Meteo returns parallel arrays keyed by variable name under
    ``payload["daily"]``.  Each index corresponds to one day.

    Example payload shape::

        {
          "daily": {
            "time": ["2026-04-02", "2026-04-03", ...],
            "temperature_2m_max": [18.5, 20.1, ...],
            "temperature_2m_min": [9.0, 11.2, ...],
            "precipitation_sum": [0.0, 2.3, ...],
            "soil_temperature_0cm_max": [14.1, 15.6, ...]
          }
        }
    """
    daily = payload.get("daily") if isinstance(payload, dict) else None
    if not isinstance(daily, dict):
        logger.warning("Open-Meteo response has no daily object for field=%s", field_id)
        return WeatherForecast(rows=[], skipped_dates=[])

    dates = daily.get("time", [])
    temp_highs = daily.get("temperature_2m_max", [])
    temp_lows = daily.get("temperature_2m_min", [])
    precips = daily.get("precipitation_sum", [])
    soil_temps = daily.get("soil_temperature_0cm_max", [])

    if not dates:
        logger.warning("Open-Meteo response contained no daily data for field=%s", field_id)
        return WeatherForecast(rows=[], skipped_dates=[])

    records: list[WeatherData] = []
    skipped_dates: list[str] = []

    for i, date in enumerate(dates):
        temp_high = _safe_float(temp_highs, i)
        temp_low = _safe_float(temp_lows, i)
        precip_mm = _safe_float(precips, i)

        if temp_high is None or temp_low is None or precip_mm is None:
            skipped_dates.append(date)
            continue

        records.append(
            {
                "field_id": field_id,
                "date": date,
                "temp_high": temp_high,
                "temp_low": temp_low,
                "precip_mm": precip_mm,
                "soil_temp": _safe_float(soil_temps, i),
                "fetched_at": fetched_at,
            }
        )

    if skipped_dates:
        logger.warning(
            "Open-Meteo missing temperature/precipitation for field=%s dates=%s; days skipped",
            field_id,
            skipped_dates,
        )
    logger.info("Parsed %d forecast days for field=%s", len(records), field_id)
    return WeatherForecast(rows=records, skipped_dates=skipped_dates)


def _safe_float(sequence: list, index: int) -> float | None:
    """Return sequence[index] as a float, or None if out of range, null, or not numeric."""
    try:
        value = sequence[index]
        return float(value) if value is not None else None
    except (IndexError, TypeError, ValueError):
        return None
