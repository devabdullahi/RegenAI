"""
Field enrichment service.

Orchestrates the weather + soil data pipeline for a single field:
  1. Look up the field's farm to obtain county_fips and derive coordinates.
  2. Fetch a 7-day weather forecast from Open-Meteo.
  3. Upsert forecast rows into `weather_cache`.
  4. Fetch the dominant soil profile from SSURGO SDA.
  5. Insert the soil profile into `soil_profiles`.
  6. Return an EnrichmentResult summary dict.

Runs inside the request; there is no background queue.

Coordinate resolution strategy
--------------------------------
SSURGO queries and Open-Meteo both require lat/lng coordinates.  Fields
optionally store a GeoJSON boundary; when present we use its centroid.
When absent we fall back to the centre of the farm's county, looked up by FIPS
code in ``app.services.county_centroids`` (every US county and county
equivalent, generated from the Census Gazetteer).  Those results are
approximate — a county centre can be tens of miles from the field — so the
result carries ``location_source="county_centroid_approximate"`` and a warning.
"""

import asyncio
import logging
from typing import Literal, TypedDict

import httpx
from postgrest.exceptions import APIError

from app.services.county_centroids import lookup_county_centroid
from app.services.soil import SoilProfile, fetch_soil_profile
from app.services.weather import WeatherData, fetch_weather_forecast

logger = logging.getLogger(__name__)

# Database/transport failures are reported as warnings; anything else is a bug
# and propagates.
_DB_ERRORS: tuple[type[Exception], ...] = (APIError, httpx.HTTPError)

LocationSource = Literal["geojson_centroid", "county_centroid_approximate"]


_COUNTY_CENTROID_WARNING = (
    "Location approximated from the farm's county centre (no field boundary on file); "
    "weather and soil data may not match the field. Add a field boundary for accurate data."
)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

class EnrichmentResult(TypedDict):
    field_id: str
    weather_days_upserted: int
    soil_profile_saved: bool
    location_source: LocationSource | None
    warnings: list[str]


# ---------------------------------------------------------------------------
# Coordinate extraction
# ---------------------------------------------------------------------------

def _centroid_from_geojson(geojson: dict | None) -> tuple[float, float] | None:
    """Return an approximate centroid for a GeoJSON Polygon/MultiPolygon.

    We use a simple arithmetic mean of all ring coordinates — accurate enough
    for the point queries made to Open-Meteo and SSURGO.  Returns None if the
    geometry cannot be parsed.
    """
    if not geojson:
        return None

    try:
        geom_type = geojson.get("type", "")
        if geom_type == "Feature":
            return _centroid_from_geojson(geojson.get("geometry"))

        coords = geojson.get("coordinates")
        if not coords:
            return None

        # Collect all [lng, lat] pairs regardless of geometry nesting depth
        flat_points: list[list[float]] = []
        if geom_type == "Polygon":
            for ring in coords:
                flat_points.extend(ring)
        elif geom_type == "MultiPolygon":
            for polygon in coords:
                for ring in polygon:
                    flat_points.extend(ring)
        else:
            return None

        if not flat_points:
            return None

        lng_mean = sum(p[0] for p in flat_points) / len(flat_points)
        lat_mean = sum(p[1] for p in flat_points) / len(flat_points)
        return (lat_mean, lng_mean)

    except (AttributeError, IndexError, KeyError, TypeError):
        # A malformed stored boundary silently falls back to the county centre,
        # so make it visible.
        logger.warning("Could not compute centroid from malformed GeoJSON", exc_info=True)
        return None


def _resolve_coordinates(
    field: dict,
    farm: dict,
) -> tuple[tuple[float, float], LocationSource] | None:
    """Return ((lat, lng), location_source) for a field, or None.

    Priority:
      1. GeoJSON boundary centroid (most accurate)
      2. County centroid looked up by farm.county_fips (approximate)
    """
    centroid = _centroid_from_geojson(field.get("boundary_geojson"))
    if centroid:
        logger.debug("Using GeoJSON centroid for field=%s: %s", field["id"], centroid)
        return centroid, "geojson_centroid"

    fips = farm.get("county_fips", "")
    county_coords = lookup_county_centroid(fips)
    if county_coords:
        logger.debug(
            "Using county centroid for field=%s fips=%s: %s",
            field["id"],
            fips,
            county_coords,
        )
        return county_coords, "county_centroid_approximate"

    logger.warning(
        "No coordinates available for field=%s (no GeoJSON boundary, county fips=%s unknown)",
        field["id"],
        fips,
    )
    return None


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _upsert_weather_rows(supabase, field_id: str, rows: list[WeatherData]) -> int:
    """Upsert weather rows into `weather_cache` and return how many were written.

    The table has a UNIQUE constraint on (field_id, date), so we use
    ``upsert`` with ``on_conflict="field_id,date"`` to refresh stale data.
    Database errors propagate to the caller, which reports them as warnings.
    """
    if not rows:
        return 0

    result = (
        supabase.table("weather_cache")
        .upsert(rows, on_conflict="field_id,date")
        .execute()
    )
    count = len(result.data) if result.data else 0
    logger.info("Upserted %d weather rows for field=%s", count, field_id)
    return count


def _insert_soil_profile(supabase, field_id: str, profile: SoilProfile) -> bool:
    """Insert a soil profile row into `soil_profiles`; True if a row came back.

    Inserts a new row each time (no unique constraint on field_id) so that we
    preserve a history of readings.  The GET /fields/{id}/soil endpoint
    selects the most recent row.  Database errors propagate to the caller.
    """
    result = supabase.table("soil_profiles").insert(profile).execute()
    saved = bool(result.data)
    if saved:
        logger.info("Inserted soil profile for field=%s", field_id)
    return saved


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_enrichment(field_id: str, supabase) -> EnrichmentResult:
    """Enrich a field with weather and soil data.

    Args:
        field_id: UUID of the field to enrich.
        supabase: The request's authenticated Supabase client (RLS enforced).

    Returns:
        An EnrichmentResult summary dict describing what was written, where
        the coordinates came from, and any non-fatal warnings (fetch failures,
        skipped readings, and database write failures).
    """
    warnings: list[str] = []

    def _result(
        weather_count: int = 0,
        soil_saved: bool = False,
        location_source: LocationSource | None = None,
    ) -> EnrichmentResult:
        return EnrichmentResult(
            field_id=field_id,
            weather_days_upserted=weather_count,
            soil_profile_saved=soil_saved,
            location_source=location_source,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # 1. Fetch field and its parent farm
    # ------------------------------------------------------------------
    try:
        field = supabase.table("fields").select("*").eq("id", field_id).single().execute().data
    except _DB_ERRORS:
        logger.exception("Could not fetch field=%s", field_id)
        field = None

    if not field:
        msg = f"Field {field_id} not found or inaccessible"
        logger.error(msg)
        warnings.append(msg)
        return _result()

    farm_id = field.get("farm_id")
    try:
        farm = supabase.table("farms").select("*").eq("id", farm_id).single().execute().data
    except _DB_ERRORS:
        logger.exception("Could not fetch farm=%s for field=%s", farm_id, field_id)
        farm = None

    if not farm:
        msg = f"Farm {farm_id} not found for field {field_id}"
        logger.warning(msg)
        warnings.append(msg)
        farm = {}

    # ------------------------------------------------------------------
    # 2. Resolve coordinates
    # ------------------------------------------------------------------
    resolved = _resolve_coordinates(field, farm)
    if resolved is None:
        msg = "Could not resolve coordinates — weather and soil data skipped"
        logger.warning("%s for field=%s", msg, field_id)
        warnings.append(msg)
        return _result()

    (lat, lng), location_source = resolved
    if location_source == "county_centroid_approximate":
        warnings.append(_COUNTY_CENTROID_WARNING)

    # ------------------------------------------------------------------
    # 3. Fetch weather + soil concurrently
    # ------------------------------------------------------------------
    logger.info(
        "Starting concurrent weather+soil fetch for field=%s at (%.4f, %.4f) source=%s",
        field_id,
        lat,
        lng,
        location_source,
    )
    forecast, soil_lookup = await asyncio.gather(
        fetch_weather_forecast(lat, lng, field_id),
        fetch_soil_profile(lat, lng, field_id),
    )

    # ------------------------------------------------------------------
    # 4. Persist results
    # ------------------------------------------------------------------
    if forecast.skipped_dates:
        warnings.append(
            "Weather days skipped for missing temperature or precipitation readings: "
            + ", ".join(forecast.skipped_dates)
        )

    weather_count = 0
    if not forecast.rows:
        warnings.append("Weather forecast fetch returned no usable data")
    else:
        try:
            weather_count = _upsert_weather_rows(supabase, field_id, forecast.rows)
        except _DB_ERRORS:
            logger.exception("Failed to upsert weather rows for field=%s", field_id)
            warnings.append("Weather data could not be saved (database write failed)")
        else:
            if weather_count == 0:
                warnings.append("Weather data save returned no rows; nothing was stored")

    soil_saved = False
    if soil_lookup.profile is None:
        if soil_lookup.missing_readings:
            warnings.append(
                "Soil profile not saved: SSURGO has no "
                + " or ".join(soil_lookup.missing_readings)
                + " reading for this location"
            )
        else:
            warnings.append("Soil profile fetch returned no data (SSURGO may be unavailable)")
    else:
        try:
            soil_saved = _insert_soil_profile(supabase, field_id, soil_lookup.profile)
        except _DB_ERRORS:
            logger.exception("Failed to insert soil profile for field=%s", field_id)
            warnings.append("Soil profile could not be saved (database write failed)")
        else:
            if not soil_saved:
                logger.warning("Soil profile insert returned no data for field=%s", field_id)
                warnings.append("Soil profile save returned no row; nothing was stored")

    logger.info(
        "Enrichment complete for field=%s: weather_days=%d soil_saved=%s warnings=%d",
        field_id,
        weather_count,
        soil_saved,
        len(warnings),
    )
    return _result(weather_count, soil_saved, location_source)
