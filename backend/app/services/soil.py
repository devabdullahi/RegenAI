"""
USDA SSURGO soil service.

Queries the USDA Soil Data Access (SDA) REST endpoint via a SQL-like POST
request and returns a record shaped to match the `soil_profiles` table schema.

SDA endpoint docs:
    https://sdmdataaccess.sc.egov.usda.gov/WebServiceHelp.aspx

Design notes:
  - SSURGO can be genuinely slow (5-15 s) and occasionally returns HTTP 500 or
    malformed XML/JSON.  All failures are caught and return None with a warning
    log so the enrichment layer can continue without soil data.
  - The SDA endpoint returns JSON when the ``format`` field is set to ``JSON``.
  - We request the dominant component (comppct_r >= 15, ordered DESC) and
    read only the top horizon for OM, pH, and texture.
"""

import logging
from datetime import datetime, timezone
from typing import TypedDict

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"

_TIMEOUT_SECONDS = 30.0   # SDA can be slow — give it extra headroom


# ---------------------------------------------------------------------------
# Return type
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
WHERE comppct_r >= 15
ORDER BY comppct_r DESC\
"""

# Column positions in the SDA response Row array
_COL_MUSYM = 0
_COL_MUNAME = 1
_COL_COMPPCT = 2
_COL_COMPNAME = 3
_COL_TAXCLNAME = 4
_COL_OM = 5
_COL_PH = 6
_COL_TEXTURE = 7


# ---------------------------------------------------------------------------
# Core fetch function
# ---------------------------------------------------------------------------

async def fetch_soil_profile(
    latitude: float,
    longitude: float,
    field_id: str,
) -> SoilProfile | None:
    """Query SDA for the dominant soil component at the given coordinates.

    Args:
        latitude: Decimal degrees, WGS-84.
        longitude: Decimal degrees, WGS-84.
        field_id: UUID of the field; embedded in the returned record.

    Returns:
        A SoilProfile dict if a result is found, or None if the API call
        fails, the point falls outside mapped soil polygons, or the response
        cannot be parsed.  All failure paths emit a warning log.

    Raises:
        Never raises — all exceptions are caught and logged.
    """
    sql = _SOIL_SQL_TEMPLATE.format(lat=latitude, lng=longitude)
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
            response = await client.post(SDA_URL, data=form_data)
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException:
        logger.warning(
            "SSURGO SDA request timed out after %.0fs for field=%s",
            _TIMEOUT_SECONDS,
            field_id,
        )
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "SSURGO SDA returned HTTP %s for field=%s: %s",
            exc.response.status_code,
            field_id,
            exc.response.text[:300],
        )
        return None
    except Exception:
        logger.exception("Unexpected error querying SSURGO SDA for field=%s", field_id)
        return None

    return _parse_soil_response(payload, field_id, fetched_at)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_soil_response(
    payload: dict,
    field_id: str,
    fetched_at: str,
) -> SoilProfile | None:
    """Convert the SDA JSON payload into a SoilProfile dict.

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
    try:
        table = payload.get("Table", [])
    except AttributeError:
        logger.warning("SSURGO SDA response is not a dict for field=%s", field_id)
        return None

    # Expect at least a header row + one data row
    if len(table) < 2:
        logger.warning(
            "SSURGO SDA returned no soil data for field=%s (point may be outside mapped area)",
            field_id,
        )
        return None

    # table[0] is the column-name row; table[1] is the first (dominant) component
    row = table[1]

    try:
        musym: str = str(row[_COL_MUSYM] or "UNKNOWN")
        texture: str = str(row[_COL_TEXTURE] or "Unknown")
        ph: float = float(row[_COL_PH]) if row[_COL_PH] is not None else 7.0
        organic_matter: float = float(row[_COL_OM]) if row[_COL_OM] is not None else 0.0
    except (IndexError, TypeError, ValueError) as exc:
        logger.warning(
            "Could not parse SSURGO row for field=%s: %s  row=%r",
            field_id,
            exc,
            row,
        )
        return None

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
    return profile
