"""
USDA SSURGO soil service.

Queries the USDA Soil Data Access (SDA) REST endpoint via a SQL-like POST
request and returns a record shaped to match the `soil_profiles` table schema.

SDA endpoint docs:
    https://sdmdataaccess.sc.egov.usda.gov/WebServiceHelp.aspx

Design notes:
  - SSURGO can be genuinely slow (5-15 s) and occasionally returns HTTP 500 or
    malformed XML/JSON.  All failures are caught and return no profile with a
    warning log so the enrichment layer can continue without soil data.
  - The SDA endpoint returns JSON when the ``format`` field is set to ``JSON``.
  - We request the dominant component (comppct_r >= _MIN_COMPONENT_PCT, ordered DESC) and
    read only the top horizon for OM, pH, and texture.
  - Missing pH or organic matter is never replaced with a made-up value.
    `soil_profiles` requires both (NOT NULL), so an incomplete component is
    not saved and the missing readings are reported to the caller.
"""

import logging
from datetime import datetime, timezone
from typing import NamedTuple, TypedDict

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30.0   # SDA can be slow — give it extra headroom

# Components under this share of the map unit are minor inclusions, not the
# soil a field is farmed on.
_MIN_COMPONENT_PCT = 15


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

class SoilProfile(TypedDict):
    """One row of the `soil_profiles` table (without auto-generated columns)."""

    field_id: str            # filled in by the enrichment layer
    ssurgo_map_unit: str     # map-unit symbol  e.g. "WbA"
    texture: str             # e.g. "Silty clay loam"
    ph: float                # pH 1:1 H2O
    organic_matter_pct: float
    source: str              # always "ssurgo" for this service
    fetched_at: str          # ISO-8601 UTC datetime string


class SoilLookup(NamedTuple):
    """Result of a soil query.

    ``profile`` is None when nothing can be saved. ``missing_readings`` names
    the required readings SSURGO lacked (e.g. ``["ph"]``) when that is why.
    """

    profile: SoilProfile | None
    missing_readings: list[str]


# ---------------------------------------------------------------------------
# SQL template
# ---------------------------------------------------------------------------

# We use positional format() substitution — lat/lng are floats validated by the
# caller, so there is no SQL-injection risk against the SDA query language.
_SOIL_SQL_TEMPLATE = """\
SELECT musym, muname, comppct_r, compname, taxclname,
       (SELECT TOP 1 om_r
        FROM chorizon
        WHERE chorizon.cokey = component.cokey
        ORDER BY hzdept_r) AS organic_matter,
       (SELECT TOP 1 ph1to1h2o_r
        FROM chorizon
        WHERE chorizon.cokey = component.cokey
        ORDER BY hzdept_r) AS ph,
       (SELECT TOP 1 texdesc
        FROM chtexturegrp
        WHERE chtexturegrp.chkey = (
            SELECT TOP 1 chkey
            FROM chorizon
            WHERE chorizon.cokey = component.cokey
            ORDER BY hzdept_r
        ) AND rvindicator = 'Yes') AS texture
FROM mapunit
INNER JOIN component ON mapunit.mukey = component.mukey
INNER JOIN sacatalog ON mapunit.mukey IN (
    SELECT mukey
    FROM mupolygon
    WHERE mupolygon.mupolygongeo.STContains(
        geometry::STGeomFromText('POINT({lng} {lat})', 4326)
    ) = 1
)
WHERE comppct_r >= {min_component_pct}
ORDER BY comppct_r DESC\
"""

# Column positions in the SDA response Row array (order of the SELECT above)
_COL_MUSYM = 0
_COL_OM = 5
_COL_PH = 6
_COL_TEXTURE = 7

_NO_PROFILE = SoilLookup(profile=None, missing_readings=[])


# ---------------------------------------------------------------------------
# Core fetch function
# ---------------------------------------------------------------------------

async def fetch_soil_profile(
    latitude: float,
    longitude: float,
    field_id: str,
) -> SoilLookup:
    """Query SDA for the dominant soil component at the given coordinates.

    Args:
        latitude: Decimal degrees, WGS-84.
        longitude: Decimal degrees, WGS-84.
        field_id: UUID of the field; embedded in the returned record.

    Returns:
        A SoilLookup. ``profile`` is None if the API call fails, the point
        falls outside mapped soil polygons, the response cannot be parsed, or
        a required reading is missing. All failure paths emit a warning log.
    """
    sql = _SOIL_SQL_TEMPLATE.format(
        lat=latitude, lng=longitude, min_component_pct=_MIN_COMPONENT_PCT
    )
    form_data = {"query": sql, "format": "JSON+COLUMNNAME+METADATA"}

    fetched_at = datetime.now(tz=timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            logger.info(
                "Querying SSURGO SDA for field=%s lat=%.4f lon=%.4f",
                field_id,
                latitude,
                longitude,
            )
            response = await client.post(settings.ssurgo_sda_url, data=form_data)
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException:
        logger.warning(
            "SSURGO SDA request timed out after %.0fs for field=%s",
            _TIMEOUT_SECONDS,
            field_id,
        )
        return _NO_PROFILE
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "SSURGO SDA returned HTTP %s for field=%s: %s",
            exc.response.status_code,
            field_id,
            exc.response.text[:300],
        )
        return _NO_PROFILE
    except (httpx.HTTPError, ValueError) as exc:
        # Connection errors, and bodies that are not JSON (JSONDecodeError is a ValueError).
        logger.warning(
            "SSURGO SDA request failed for field=%s: %s: %s", field_id, type(exc).__name__, exc
        )
        return _NO_PROFILE

    return _parse_soil_response(payload, field_id, fetched_at)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_soil_response(
    payload: dict,
    field_id: str,
    fetched_at: str,
) -> SoilLookup:
    """Convert the SDA JSON payload into a SoilLookup.

    SDA returns JSON shaped like::

        {
          "Table": [
            ["musym", "muname", "comppct_r", "compname", "taxclname",
             "organic_matter", "ph", "texture"],
            ["WbA", "Webster silty clay loam", 85, "Webster", "Fine...",
             3.5, 6.8, "Silty clay loam"]
          ]
        }

    The first row is the column-name header; subsequent rows are data.
    We take the first data row (highest comppct_r) as the dominant component.
    """
    table = payload.get("Table") if isinstance(payload, dict) else None
    if not isinstance(table, list):
        logger.warning("SSURGO SDA response has no Table list for field=%s", field_id)
        return _NO_PROFILE

    # Expect at least a header row + one data row
    if len(table) < 2:
        logger.warning(
            "SSURGO SDA returned no soil data for field=%s (point may be outside mapped area)",
            field_id,
        )
        return _NO_PROFILE

    # table[0] is the column-name row; table[1] is the first (dominant) component
    row = table[1]

    try:
        musym = str(row[_COL_MUSYM] or "UNKNOWN")
        texture = str(row[_COL_TEXTURE] or "Unknown")
        ph = float(row[_COL_PH]) if row[_COL_PH] is not None else None
        organic_matter = float(row[_COL_OM]) if row[_COL_OM] is not None else None
    except (IndexError, TypeError, ValueError) as exc:
        logger.warning(
            "Could not parse SSURGO row for field=%s: %s  row=%r",
            field_id,
            exc,
            row,
        )
        return _NO_PROFILE

    missing_readings = [
        name
        for name, value in (("ph", ph), ("organic_matter_pct", organic_matter))
        if value is None
    ]
    if ph is None or organic_matter is None:
        logger.warning(
            "SSURGO component for field=%s map_unit=%s lacks %s; profile not saved",
            field_id,
            musym,
            ", ".join(missing_readings),
        )
        return SoilLookup(profile=None, missing_readings=missing_readings)

    profile: SoilProfile = {
        "field_id": field_id,
        "ssurgo_map_unit": musym,
        "texture": texture,
        "ph": ph,
        "organic_matter_pct": organic_matter,
        "source": "ssurgo",
        "fetched_at": fetched_at,
    }

    logger.info(
        "Parsed SSURGO profile for field=%s: map_unit=%s texture=%s ph=%.1f om=%.2f%%",
        field_id,
        musym,
        texture,
        ph,
        organic_matter,
    )
    return SoilLookup(profile=profile, missing_readings=[])
