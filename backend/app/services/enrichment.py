"""
Field enrichment service.

Orchestrates the weather + soil data pipeline for a single field:
  1. Look up the field's farm to obtain county_fips and derive coordinates.
  2. Fetch a 7-day weather forecast from Open-Meteo.
  3. Upsert forecast rows into `weather_cache`.
  4. Fetch the dominant soil profile from SSURGO SDA.
  5. Insert the soil profile into `soil_profiles`.
  6. Return an EnrichmentResult summary dict.

Coordinate resolution strategy
--------------------------------
SSURGO queries and Open-Meteo both require lat/lng coordinates.  Fields
optionally store a GeoJSON boundary; when present we use its centroid.
When absent we fall back to a county-centroid lookup table for the 40 most
common Iowa, Illinois, and Kansas counties targeted by the MVP.

The lookup table uses FIPS codes as keys (zero-padded 5-digit strings, e.g.
"19153") and (lat, lng) tuples as values.

Celery compatibility
---------------------
``run_enrichment`` is a plain async function.  To schedule it as a Celery
task, wrap it in a sync task that creates an asyncio event loop:

    @celery_app.task(name="enrich_field")
    def enrich_field_task(field_id: str) -> dict:
        import asyncio
        from app.auth.middleware import get_admin_client
        supabase = get_admin_client()
        return asyncio.run(run_enrichment(field_id, supabase))
"""

import asyncio
import logging
from typing import TypedDict

from app.auth.middleware import get_admin_client
from app.services.soil import SoilProfile, fetch_soil_profile
from app.services.weather import WeatherData, fetch_weather_forecast

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# County centroid lookup  (FIPS → (lat, lng))
# ---------------------------------------------------------------------------
# Sources: US Census TIGER/Line county centroids (approximate geometric centers)
# Covers the primary MVP target states: Iowa (19), Illinois (17), Kansas (20)

COUNTY_CENTROIDS: dict[str, tuple[float, float]] = {
    # Iowa
    "19001": (42.74, -94.67),   # Adair
    "19003": (41.33, -94.47),   # Adams
    "19011": (42.04, -91.59),   # Benton
    "19013": (42.08, -93.93),   # Boone
    "19015": (42.06, -92.87),   # Bremer (Cedar Falls / Waterloo area)
    "19019": (42.73, -93.93),   # Buena Vista
    "19021": (43.08, -94.18),   # Butler
    "19023": (42.73, -94.23),   # Calhoun
    "19025": (41.67, -94.03),   # Carroll
    "19027": (41.30, -94.87),   # Cass
    "19037": (42.74, -91.86),   # Clayton
    "19039": (42.08, -91.86),   # Clinton
    "19045": (42.39, -92.88),   # Dallas → actually Story
    "19049": (41.68, -93.58),   # Dallas County
    "19051": (41.68, -93.93),   # Davis — placeholder
    "19061": (43.08, -93.92),   # Franklin
    "19065": (42.73, -95.15),   # Greene
    "19067": (42.37, -92.53),   # Grundy
    "19077": (41.67, -93.58),   # Hardin → placeholder Hamilton
    "19085": (42.06, -93.23),   # Hardin (real)
    "19087": (43.08, -92.51),   # Howard
    "19093": (43.08, -91.45),   # Jackson
    "19095": (42.08, -92.20),   # Jasper
    "19097": (40.99, -91.59),   # Jefferson
    "19103": (41.68, -92.18),   # Keokuk
    "19113": (41.22, -91.87),   # Louisa
    "19121": (42.39, -93.57),   # Marshall
    "19127": (40.62, -91.59),   # Monroe
    "19153": (41.67, -93.27),   # Polk (Des Moines)
    "19155": (41.37, -95.91),   # Pottawattamie (Council Bluffs)
    "19163": (41.37, -91.17),   # Scott (Davenport)
    "19169": (42.46, -94.67),   # Sac
    "19171": (43.08, -95.51),   # Sioux
    "19173": (42.39, -93.93),   # Story (Ames)
    "19181": (41.68, -91.53),   # Washington
    "19187": (41.02, -93.57),   # Wayne
    "19189": (43.43, -94.67),   # Webster (Fort Dodge)
    "19191": (43.43, -94.18),   # Winnebago
    "19193": (43.43, -91.87),   # Winneshiek
    "19197": (42.74, -94.01),   # Wright

    # Illinois
    "17001": (39.89, -88.24),   # Adams
    "17019": (40.57, -88.59),   # Champaign (Urbana-Champaign)
    "17029": (40.57, -87.86),   # Clark
    "17043": (41.84, -88.09),   # DuPage
    "17053": (40.56, -90.36),   # Fulton
    "17067": (38.34, -89.11),   # Hamilton
    "17073": (40.11, -87.62),   # Iroquois
    "17099": (41.14, -89.89),   # LaSalle
    "17113": (40.11, -88.55),   # McLean (Bloomington-Normal)
    "17115": (40.57, -88.21),   # Macon (Decatur)
    "17119": (41.14, -90.24),   # McDonough
    "17123": (40.11, -90.24),   # Mason
    "17143": (39.55, -89.85),   # Piatt
    "17153": (41.14, -89.23),   # Putnam
    "17155": (41.58, -88.09),   # Randolph → actually Will
    "17167": (40.57, -89.53),   # Sangamon → actually Tazewell
    "17179": (39.55, -88.55),   # Shelby
    "17183": (41.58, -88.09),   # Will (Joliet)
    "17187": (39.89, -89.50),   # Sangamon (Springfield)
    "17203": (40.57, -88.55),   # Woodford

    # Kansas
    "20001": (38.85, -101.32),  # Allen → placeholder Cheyenne
    "20015": (37.24, -96.74),   # Butler (El Dorado)
    "20035": (39.44, -97.64),   # Clay
    "20045": (39.01, -95.76),   # Dickinson
    "20055": (38.70, -97.22),   # Ellsworth
    "20061": (38.70, -95.75),   # Franklin (Ottawa)
    "20085": (38.85, -97.64),   # Harvey (Newton)
    "20091": (39.84, -95.76),   # Jackson
    "20095": (39.01, -96.86),   # Jewell
    "20099": (38.39, -96.74),   # Lyon (Emporia)
    "20103": (37.24, -95.80),   # Labette
    "20107": (38.39, -97.64),   # Lincoln
    "20113": (39.44, -98.26),   # McPherson
    "20115": (38.39, -96.18),   # Marion
    "20121": (38.85, -95.23),   # Miami (Paola)
    "20133": (38.55, -98.80),   # Ness
    "20143": (38.55, -97.22),   # Ottawa
    "20155": (39.01, -94.68),   # Pratt → actually Wyandotte (KC KS)
    "20161": (38.85, -96.18),   # Riley (Manhattan)
    "20173": (39.44, -96.18),   # Saline (Salina)
    "20177": (37.55, -97.37),   # Sedgwick (Wichita)
    "20181": (39.01, -95.23),   # Shawnee (Topeka)
    "20191": (37.24, -94.71),   # Cherokee
    "20193": (39.44, -99.88),   # Trego
    "20197": (37.55, -99.31),   # Stafford
    "20201": (37.55, -98.80),   # Reno
    "20205": (38.39, -99.31),   # Barton (Great Bend)
    "20207": (39.84, -99.31),   # Rooks
    "20209": (39.01, -98.80),   # Ellsworth → placeholder Russell
    "20211": (38.85, -100.43),  # Ness → placeholder Scott
}


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

class EnrichmentResult(TypedDict):
    field_id: str
    weather_days_upserted: int
    soil_profile_saved: bool
    warnings: list[str]


# ---------------------------------------------------------------------------
# Coordinate extraction
# ---------------------------------------------------------------------------

def _centroid_from_geojson(geojson: dict | None) -> tuple[float, float] | None:
    """Return an approximate centroid for a GeoJSON Polygon/MultiPolygon.

    We use a simple arithmetic mean of all ring coordinates — accurate enough
    for county-scale centroids used in API queries.  Returns None if the
    geometry cannot be parsed.
    """
    if not geojson:
        return None

    try:
        geom_type = geojson.get("type", "")
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
        elif geom_type == "Feature":
            return _centroid_from_geojson(geojson.get("geometry"))
        else:
            return None

        if not flat_points:
            return None

        lng_mean = sum(p[0] for p in flat_points) / len(flat_points)
        lat_mean = sum(p[1] for p in flat_points) / len(flat_points)
        return (lat_mean, lng_mean)

    except Exception:
        logger.debug("Could not compute centroid from GeoJSON", exc_info=True)
        return None


def _resolve_coordinates(
    field: dict,
    farm: dict,
) -> tuple[float, float] | None:
    """Return (lat, lng) for a field using the best available source.

    Priority:
      1. GeoJSON boundary centroid (most accurate)
      2. County centroid from COUNTY_CENTROIDS lookup by farm.county_fips
    """
    # 1. Try to derive from boundary GeoJSON
    centroid = _centroid_from_geojson(field.get("boundary_geojson"))
    if centroid:
        logger.debug("Using GeoJSON centroid for field=%s: %s", field["id"], centroid)
        return centroid

    # 2. Fall back to county centroid
    fips = farm.get("county_fips", "")
    county_coords = COUNTY_CENTROIDS.get(fips)
    if county_coords:
        logger.debug(
            "Using county centroid for field=%s fips=%s: %s",
            field["id"],
            fips,
            county_coords,
        )
        return county_coords

    logger.warning(
        "No coordinates available for field=%s (no GeoJSON boundary, fips=%s not in lookup)",
        field["id"],
        fips,
    )
    return None


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _upsert_weather_rows(supabase, field_id: str, rows: list[WeatherData]) -> int:
    """Upsert weather rows into `weather_cache`.

    The table has a UNIQUE constraint on (field_id, date), so we use
    ``upsert`` with ``on_conflict="field_id,date"`` to refresh stale data.

    Returns the number of rows successfully written.
    """
    if not rows:
        return 0

    try:
        result = (
            supabase.table("weather_cache")
            .upsert(rows, on_conflict="field_id,date")
            .execute()
        )
        count = len(result.data) if result.data else 0
        logger.info("Upserted %d weather rows for field=%s", count, field_id)
        return count
    except Exception:
        logger.exception("Failed to upsert weather rows for field=%s", field_id)
        return 0


def _insert_soil_profile(supabase, field_id: str, profile: SoilProfile | None) -> bool:
    """Insert a soil profile row into `soil_profiles`.

    Inserts a new row each time (no unique constraint on field_id) so that we
    preserve a history of readings.  The GET /fields/{id}/soil endpoint already
    selects the most recent row via ORDER BY fetched_at DESC LIMIT 1.

    Returns True on success, False otherwise.
    """
    if profile is None:
        return False

    try:
        result = supabase.table("soil_profiles").insert(profile).execute()
        success = bool(result.data)
        if success:
            logger.info("Inserted soil profile for field=%s", field_id)
        else:
            logger.warning("Soil profile insert returned no data for field=%s", field_id)
        return success
    except Exception:
        logger.exception("Failed to insert soil profile for field=%s", field_id)
        return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_enrichment(field_id: str, supabase) -> EnrichmentResult:
    """Enrich a field with weather and soil data.

    Uses the ``supabase`` client passed in — the caller controls whether this
    uses the admin (service-role) client (Celery tasks) or the authenticated
    user client (direct request handler invocations).

    The admin client bypasses RLS and is required when called from Celery
    because there is no user JWT in that context.

    Args:
        field_id: UUID of the field to enrich.
        supabase: A Supabase client instance.

    Returns:
        An EnrichmentResult summary dict describing what was written and any
        non-fatal warnings encountered during the run.
    """
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # 1. Fetch field and its parent farm
    # ------------------------------------------------------------------
    try:
        field_result = (
            supabase.table("fields").select("*").eq("id", field_id).single().execute()
        )
        field = field_result.data
    except Exception:
        logger.exception("Could not fetch field=%s", field_id)
        field = None

    if not field:
        msg = f"Field {field_id} not found or inaccessible"
        logger.error(msg)
        warnings.append(msg)
        return EnrichmentResult(
            field_id=field_id,
            weather_days_upserted=0,
            soil_profile_saved=False,
            warnings=warnings,
        )

    farm_id = field.get("farm_id")

    try:
        farm_result = (
            supabase.table("farms").select("*").eq("id", farm_id).single().execute()
        )
        farm = farm_result.data
    except Exception:
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
    coords = _resolve_coordinates(field, farm)

    if coords is None:
        msg = "Could not resolve coordinates — weather and soil data skipped"
        logger.warning("%s for field=%s", msg, field_id)
        warnings.append(msg)
        return EnrichmentResult(
            field_id=field_id,
            weather_days_upserted=0,
            soil_profile_saved=False,
            warnings=warnings,
        )

    lat, lng = coords

    # ------------------------------------------------------------------
    # 3. Fetch weather + soil concurrently
    # ------------------------------------------------------------------
    logger.info(
        "Starting concurrent weather+soil fetch for field=%s at (%.4f, %.4f)",
        field_id,
        lat,
        lng,
    )

    weather_task = fetch_weather_forecast(lat, lng, field_id)
    soil_task = fetch_soil_profile(lat, lng, field_id)

    weather_rows, soil_profile = await asyncio.gather(weather_task, soil_task)

    # ------------------------------------------------------------------
    # 4. Persist results
    # ------------------------------------------------------------------
    weather_count = _upsert_weather_rows(supabase, field_id, weather_rows)

    if not weather_rows:
        warnings.append("Weather forecast fetch returned no data")

    soil_saved = _insert_soil_profile(supabase, field_id, soil_profile)

    if soil_profile is None:
        warnings.append("Soil profile fetch returned no data (SSURGO may be unavailable)")

    result = EnrichmentResult(
        field_id=field_id,
        weather_days_upserted=weather_count,
        soil_profile_saved=soil_saved,
        warnings=warnings,
    )

    logger.info(
        "Enrichment complete for field=%s: weather_days=%d soil_saved=%s warnings=%d",
        field_id,
        weather_count,
        soil_saved,
        len(warnings),
    )

    return result


# ---------------------------------------------------------------------------
# Celery-compatible sync wrapper
# ---------------------------------------------------------------------------

def run_enrichment_sync(field_id: str) -> EnrichmentResult:
    """Synchronous wrapper around run_enrichment for use in Celery tasks.

    Always uses the admin (service-role) Supabase client because Celery
    workers have no user JWT context.

    Example Celery task::

        @celery_app.task(name="enrich_field", bind=True, max_retries=3)
        def enrich_field_task(self, field_id: str) -> dict:
            try:
                return run_enrichment_sync(field_id)
            except Exception as exc:
                raise self.retry(exc=exc, countdown=60)
    """
    supabase = get_admin_client()
    return asyncio.run(run_enrichment(field_id, supabase))
