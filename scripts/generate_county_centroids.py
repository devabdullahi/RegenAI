#!/usr/bin/env python3
"""
Regenerate the nationwide county centroid table used by field enrichment.

What it downloads
    The US Census Bureau Gazetteer "counties, national" files:
        https://www2.census.gov/geo/docs/maps-data/data/gazetteer/<YEAR>_Gazetteer/<YEAR>_Gaz_counties_national.zip
    Each zip holds one delimited text file with one row per county or county
    equivalent.  We read the INTPTLAT / INTPTLONG columns — the Census
    "internal point", a coordinate guaranteed to fall inside the county
    polygon.  A naive area centroid can land outside an irregular (horseshoe,
    coastal, island) county, which would send SSURGO and Open-Meteo queries to
    the wrong place, so the internal point is preferred.

    Two vintages are downloaded:
      * the primary vintage supplies every current county / county equivalent;
      * each legacy vintage supplies only the GEOIDs the primary no longer has.
        Today that is exactly Connecticut's eight pre-2022 counties
        (09001-09015), which the Census replaced with nine planning regions
        (09110-09190) but which still appear in older USDA program data.  A
        farm record carrying a legacy FIPS must still resolve to coordinates.

How to run
    From the repository root, with any Python 3.11+ interpreter (standard
    library only, no project dependencies required):

        python scripts/generate_county_centroids.py

    Useful flags:
        --primary-year 2026        Census Gazetteer vintage to use as primary
        --legacy-year 2020         repeatable; supplies retired GEOIDs only
        --as-of 2026-09-22         recorded in the output (default: today, UTC)
        --output <path>            override the destination file
        --check                    regenerate and diff instead of writing
                                   (exit 1 if the committed file is stale)

What it writes
    backend/app/data/county_centroids.json — a JSON object with a provenance
    header (`as_of`, one entry per source file with its URL, vintage and
    Last-Modified header) and a `counties` map of
        "<5-digit FIPS>": {"lat": .., "lon": .., "name": .., "state": ..,
                           "source": "<vintage>"}
    The file is sorted by FIPS so re-runs produce a reviewable diff.

    Nothing downloads at application runtime or during tests: the backend
    reads the committed JSON (see backend/app/services/county_centroids.py).
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "backend" / "app" / "data" / "county_centroids.json"

GAZETTEER_URL_TEMPLATE = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "{year}_Gazetteer/{year}_Gaz_counties_national.zip"
)

DEFAULT_PRIMARY_YEAR = "2026"
DEFAULT_LEGACY_YEARS = ("2020",)

# The Gazetteer switched from tab- to pipe-delimited between the 2020 and 2026
# vintages, so the delimiter is detected from the header row rather than fixed.
_DELIMITERS = ("|", "\t")

# Rough bounds for the US plus Puerto Rico, used only to catch a misparsed
# column (e.g. reading ALAND as a latitude), not to validate geography.
_MIN_LAT, _MAX_LAT = 17.0, 72.0
_MAX_ABS_LON = 180.0


class CountyRow(NamedTuple):
    fips: str
    lat: float
    lon: float
    name: str
    state: str


class GazetteerFile(NamedTuple):
    year: str
    url: str
    member_name: str
    last_modified: str
    rows: list[CountyRow]


def download_gazetteer(year: str) -> GazetteerFile:
    """Download and parse one Gazetteer county file."""
    url = GAZETTEER_URL_TEMPLATE.format(year=year)
    request = urllib.request.Request(url, headers={"User-Agent": "RegenAI-county-centroids"})
    print(f"Downloading {url}", file=sys.stderr)
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - fixed host
        payload = response.read()
        last_modified = response.headers.get("Last-Modified", "")

    archive = zipfile.ZipFile(io.BytesIO(payload))
    member_name = archive.namelist()[0]
    text = archive.read(member_name).decode("utf-8-sig")
    rows = _parse_gazetteer_text(text)
    print(f"  {member_name}: {len(rows)} rows", file=sys.stderr)
    return GazetteerFile(year, url, member_name, last_modified, rows)


def _parse_gazetteer_text(text: str) -> list[CountyRow]:
    lines = text.splitlines()
    if not lines:
        raise ValueError("Gazetteer file is empty")

    header_line = lines[0]
    delimiter = next((d for d in _DELIMITERS if d in header_line), None)
    if delimiter is None:
        raise ValueError(f"Could not detect a delimiter in header: {header_line!r}")

    header = [column.strip() for column in header_line.split(delimiter)]
    required = ("USPS", "GEOID", "NAME", "INTPTLAT", "INTPTLONG")
    missing = [column for column in required if column not in header]
    if missing:
        raise ValueError(f"Gazetteer header is missing columns: {missing}")
    index = {column: position for position, column in enumerate(header)}

    rows: list[CountyRow] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = [field.strip() for field in line.split(delimiter)]
        rows.append(
            CountyRow(
                fips=fields[index["GEOID"]],
                lat=float(fields[index["INTPTLAT"]]),
                lon=float(fields[index["INTPTLONG"]]),
                name=fields[index["NAME"]],
                state=fields[index["USPS"]],
            )
        )
    return rows


def _validate(row: CountyRow) -> None:
    if len(row.fips) != 5 or not row.fips.isdigit():
        raise ValueError(f"Unexpected GEOID {row.fips!r} for {row.name}")
    if not _MIN_LAT <= row.lat <= _MAX_LAT or abs(row.lon) > _MAX_ABS_LON:
        raise ValueError(f"Implausible internal point for {row.fips} {row.name}: {row}")


def build_table(
    primary: GazetteerFile,
    legacy_files: list[GazetteerFile],
) -> tuple[dict[str, dict], list[dict]]:
    """Merge the primary vintage with retired GEOIDs from the legacy vintages."""
    counties: dict[str, dict] = {}
    source_counts: dict[str, int] = {}

    for gazetteer in [primary, *legacy_files]:
        added = 0
        for row in gazetteer.rows:
            _validate(row)
            if row.fips in counties:
                # The primary vintage wins; a legacy file only fills retired codes.
                continue
            counties[row.fips] = {
                "lat": round(row.lat, 6),
                "lon": round(row.lon, 6),
                "name": row.name,
                "state": row.state,
                "source": gazetteer.year,
            }
            added += 1
        source_counts[gazetteer.year] = added

    sources = [
        {
            "vintage": gazetteer.year,
            "role": "primary" if gazetteer is primary else "legacy_supplement",
            "source_url": gazetteer.url,
            "file": gazetteer.member_name,
            "last_modified": gazetteer.last_modified,
            "rows_in_file": len(gazetteer.rows),
            "rows_used": source_counts[gazetteer.year],
        }
        for gazetteer in [primary, *legacy_files]
    ]
    return counties, sources


def render_document(document: dict) -> str:
    """Serialise the table with one county per line so diffs stay reviewable."""
    header_entries = [
        f" {json.dumps(key)}: {json.dumps(value, indent=1, ensure_ascii=False)}"
        for key, value in document.items()
        if key != "counties"
    ]
    county_entries = [
        f'  {json.dumps(fips)}: {json.dumps(record, ensure_ascii=False)}'
        for fips, record in document["counties"].items()
    ]
    body = ",\n".join([*header_entries, ' "counties": {\n' + ",\n".join(county_entries) + "\n }"])
    return "{\n" + body + "\n}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-year", default=DEFAULT_PRIMARY_YEAR)
    parser.add_argument("--legacy-year", action="append", default=None)
    parser.add_argument("--as-of", default=dt.datetime.now(dt.UTC).date().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed file differs from a fresh download",
    )
    args = parser.parse_args()

    legacy_years = args.legacy_year if args.legacy_year is not None else list(DEFAULT_LEGACY_YEARS)

    primary = download_gazetteer(args.primary_year)
    legacy_files = [download_gazetteer(year) for year in legacy_years]
    counties, sources = build_table(primary, legacy_files)

    document = {
        "description": (
            "County / county-equivalent internal points (FIPS -> lat/lon) used to "
            "approximate a field's location when no field boundary is on file."
        ),
        "as_of": args.as_of,
        "coordinate_columns": "INTPTLAT / INTPTLONG (Census internal point, inside the polygon)",
        "generated_by": "scripts/generate_county_centroids.py",
        "sources": sources,
        "county_count": len(counties),
        "counties": dict(sorted(counties.items())),
    }
    rendered = render_document(document)

    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        # as_of moves with every run, so compare the county table only.
        fresh_counties = document["counties"]
        current_counties = json.loads(current)["counties"] if current else {}
        if fresh_counties != current_counties:
            print(f"{args.output} is stale; re-run without --check", file=sys.stderr)
            return 1
        print(f"{args.output} matches the {args.primary_year} Gazetteer", file=sys.stderr)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {len(counties)} counties to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
