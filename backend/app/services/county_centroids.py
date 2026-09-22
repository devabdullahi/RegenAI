"""
Nationwide county centroid lookup (county FIPS → latitude/longitude).

Weather (Open-Meteo) and soil (SSURGO) queries need a point.  When a field has
no stored boundary we fall back to the centre of the farm's county, which is
approximate but works in every state.

The table is data, not code: it is generated from the US Census Bureau
Gazetteer county file by ``scripts/generate_county_centroids.py`` and committed
as ``app/data/county_centroids.json``.  Keeping it in JSON means the numbers
carry their own provenance (``source_url``, Gazetteer vintage, ``as_of``) in
the same file, and regenerating it produces a reviewable data-only diff instead
of a code change.  Nothing is downloaded at runtime.

The coordinates are the Gazetteer's INTPTLAT/INTPTLONG "internal point", which
the Census guarantees falls inside the county polygon — unlike an area
centroid, which can land outside a horseshoe-shaped or island county.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, TypedDict

_DATA_PATH: Final[Path] = Path(__file__).resolve().parents[1] / "data" / "county_centroids.json"


class CountyRecord(TypedDict):
    """One county / county-equivalent row as stored in the JSON table."""

    lat: float
    lon: float
    name: str
    state: str
    source: str


_DOCUMENT: Final[dict] = json.loads(_DATA_PATH.read_text(encoding="utf-8"))

#: FIPS → full row, including county name, state and the Gazetteer vintage.
COUNTY_RECORDS: Final[dict[str, CountyRecord]] = _DOCUMENT["counties"]

#: FIPS → (lat, lng), the shape the enrichment pipeline consumes.
COUNTY_CENTROIDS: Final[dict[str, tuple[float, float]]] = {
    fips: (record["lat"], record["lon"]) for fips, record in COUNTY_RECORDS.items()
}

#: Provenance for the table, surfaced so callers and tests can cite it.
COUNTY_DATA_AS_OF: Final[str] = _DOCUMENT["as_of"]
COUNTY_DATA_SOURCES: Final[list[dict]] = _DOCUMENT["sources"]


def normalize_county_fips(fips: str | int | None) -> str | None:
    """Return a 5-digit FIPS string, or None when the value cannot be one.

    County FIPS codes for Alabama (01xxx) through Connecticut (09xxx) lose
    their leading zero whenever a code passes through an integer — a CSV
    import, a spreadsheet, a JSON number.  Left-padding a short all-digit value
    keeps those states usable instead of silently returning no coordinates.
    """
    if fips is None:
        return None

    text = str(fips).strip()
    if not text.isdigit() or len(text) > 5:
        return None
    return text.zfill(5)


def lookup_county_centroid(fips: str | int | None) -> tuple[float, float] | None:
    """Return (lat, lng) for a county FIPS code, or None when it is unknown."""
    normalized = normalize_county_fips(fips)
    if normalized is None:
        return None
    return COUNTY_CENTROIDS.get(normalized)
