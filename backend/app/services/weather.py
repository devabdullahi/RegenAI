"""
Open-Meteo weather service.

Fetches a 7-day forecast from the Open-Meteo public API (no key required) and
returns records shaped to match the `weather_cache` table schema.

API docs: https://open-meteo.com/en/docs
"""

import logging
from datetime import datetime, timezone
from typing import TypedDict

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

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


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

class WeatherData(TypedDict):
    """One row of the `weather_cache` table (without auto-generated columns)."""

    field_id: str        # filled in by the enrichment layer
    date: str            # ISO-8601 date string  e.g. "2026-04-02"
    temp_high: float     # °C
    temp_low: float      # °C
    precip_mm: float     # mm
    soil_temp: float     # °C  (0 cm depth, may be None from API → 0.0)
    fetched_at: str      # ISO-8601 UTC datetime string


# ---------------------------------------------------------------------------
# Core fetch function
# ---------------------------------------------------------------------------

async def fetch_weather_forecast(
    latitude: float,
    longitude: float,
    field_id: str,
) -> list[WeatherData]:
    """Fetch a 7-day forecast from Open-Meteo for the given coordinates.

    Args:
        latitude: Decimal degrees, WGS-84.
        longitude: Decimal degrees, WGS-84.
        field_id: UUID of the field; embedded into every returned record so
            the enrichment layer can insert them directly.

    Returns:
        A list of up to 7 WeatherData dicts, one per forecast day.  Returns
        an empty list if the API call fails — callers should treat this as a
        non-fatal condition and log accordingly.

    Raises:
        Never raises — all exceptions are caught and logged.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(_DAILY_VARS),
        "timezone": "America/Chicago",
        "forecast_days": 7,
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
            response = await client.get(OPEN_METEO_BASE_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException:
        logger.warning(
            "Open-Meteo request timed out after %.0fs for field=%s",
            _TIMEOUT_SECONDS,
            field_id,
        )
        return []
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Open-Meteo returned HTTP %s for field=%s: %s",
            exc.response.status_code,
            field_id,
            exc.response.text[:200],
        )
        return []
    except Exception:
        logger.exception("Unexpected error fetching Open-Meteo data for field=%s", field_id)
        return []

    return _parse_forecast(payload, field_id, fetched_at)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_forecast(
    payload: dict,
    field_id: str,
    fetched_at: str,
) -> list[WeatherData]:
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
    daily = payload.get("daily", {})

    dates = daily.get("time", [])
    temp_highs = daily.get("temperature_2m_max", [])
    temp_lows = daily.get("temperature_2m_min", [])
    precips = daily.get("precipitation_sum", [])
    soil_temps = daily.get("soil_temperature_0cm_max", [])

    if not dates:
        logger.warning("Open-Meteo response contained no daily data for field=%s", field_id)
        return []

    records: list[WeatherData] = []

    for i, date in enumerate(dates):
        # Each parallel array may be shorter than `dates` if the API drops a
        # variable; use .get-style index-with-default via the helper below.
        record: WeatherData = {
            "field_id": field_id,
            "date": date,
            "temp_high": _safe_float(temp_highs, i, default=0.0),
            "temp_low": _safe_float(temp_lows, i, default=0.0),
            "precip_mm": _safe_float(precips, i, default=0.0),
            "soil_temp": _safe_float(soil_temps, i, default=0.0),
            "fetched_at": fetched_at,
        }
        records.append(record)

    logger.info("Parsed %d forecast days for field=%s", len(records), field_id)
    return records


def _safe_float(sequence: list, index: int, default: float) -> float:
    """Return sequence[index] as a float, or `default` if out-of-range or None."""
    try:
        value = sequence[index]
        return float(value) if value is not None else default
    except (IndexError, TypeError, ValueError):
        return default
