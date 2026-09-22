"""Field models, including the RFC 7946 GeoJSON boundary validators."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_VALID_GEOJSON_TYPES = frozenset(
    ("Point", "LineString", "Polygon", "MultiPoint", "MultiLineString",
     "MultiPolygon", "GeometryCollection", "Feature", "FeatureCollection")
)
_GEOMETRY_TYPES_REQUIRING_COORDINATES = frozenset(
    ("Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon")
)


def _validate_polygon_rings(coordinates: Any) -> None:
    """Validate RFC 7946 Polygon ring rules.

    Each ring must have at least 4 positions and be closed (first position
    equal to last position).  Raises ValueError on violation.
    """
    if not isinstance(coordinates, list):
        raise ValueError(
            "Invalid boundary geometry: Polygon coordinates must be a list of rings"
        )
    for ring_index, ring in enumerate(coordinates):
        if not isinstance(ring, list):
            raise ValueError(
                f"Invalid boundary geometry: Polygon ring {ring_index} must be a list of positions"
            )
        if len(ring) < 4:
            raise ValueError(
                f"Invalid boundary geometry: Polygon ring {ring_index} must have at least "
                f"4 positions (RFC 7946), got {len(ring)}"
            )
        if ring[0] != ring[-1]:
            raise ValueError(
                f"Invalid boundary geometry: Polygon ring {ring_index} is not closed "
                f"(first position must equal last position per RFC 7946)"
            )


def _validate_boundary_geojson(value: Any) -> Any:
    """Shared structural validator for GeoJSON boundary fields (RFC 7946)."""
    if value is None:
        return value
    if not isinstance(value, dict):
        raise ValueError("Invalid boundary geometry: must be valid GeoJSON")
    geo_type = value.get("type")
    if geo_type is None:
        raise ValueError(
            "Invalid boundary geometry: GeoJSON object must have a 'type' field. "
            "Expected one of: Point, Polygon, MultiPolygon, LineString, "
            "MultiLineString, MultiPoint, GeometryCollection, Feature, FeatureCollection"
        )
    if geo_type not in _VALID_GEOJSON_TYPES:
        raise ValueError(
            f"Invalid boundary geometry: unsupported GeoJSON type '{geo_type}'. "
            "Expected one of: Point, Polygon, MultiPolygon, LineString, "
            "MultiLineString, MultiPoint, GeometryCollection, Feature, FeatureCollection"
        )
    if geo_type in _GEOMETRY_TYPES_REQUIRING_COORDINATES and "coordinates" not in value:
        raise ValueError(
            f"Invalid boundary geometry: GeoJSON type '{geo_type}' requires a 'coordinates' field"
        )
    if geo_type == "Polygon":
        _validate_polygon_rings(value["coordinates"])
    return value


class FieldCreate(BaseModel):
    farm_id: UUID
    name: str = Field(..., min_length=1, max_length=200)
    acres: float = Field(..., gt=0)
    crop_type: str = Field(..., min_length=1, max_length=100)
    boundary_geojson: dict | None = None
    boundary_description: str | None = None
    practices: list[str] = Field(default_factory=list)

    @field_validator("boundary_geojson", mode="before")
    @classmethod
    def validate_boundary_geojson(cls, value: Any) -> Any:
        return _validate_boundary_geojson(value)


class FieldUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    acres: float | None = Field(None, gt=0)
    crop_type: str | None = Field(None, min_length=1, max_length=100)
    boundary_geojson: dict | None = None
    boundary_description: str | None = None
    practices: list[str] | None = None

    @field_validator("boundary_geojson", mode="before")
    @classmethod
    def validate_boundary_geojson(cls, value: Any) -> Any:
        return _validate_boundary_geojson(value)


class FieldResponse(BaseModel):
    id: UUID
    farm_id: UUID
    name: str
    acres: float
    crop_type: str
    boundary_geojson: dict | None = None
    boundary_description: str | None = None
    practices: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None
