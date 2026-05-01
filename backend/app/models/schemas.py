from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# --- Enums ---

class RecommendationStatus(str, Enum):
    pending = "pending"
    acted = "acted"
    dismissed = "dismissed"


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class CreditProgram(str, Enum):
    eqip = "EQIP"
    vcm = "VCM"


class CreditStatus(str, Enum):
    eligible = "eligible"
    not_eligible = "not_eligible"
    pending_review = "pending_review"


class Goals(str, Enum):
    cost_savings = "cost_savings"
    carbon_credits = "carbon_credits"
    both = "both"


# --- Farm ---

class FarmCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    state: str = Field(..., pattern=r"^[A-Z]{2}$")
    county_fips: str = Field(..., pattern=r"^\d{5}$")
    total_acres: float = Field(..., gt=0)
    goals: Goals | None = None


class FarmUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    state: str | None = Field(None, pattern=r"^[A-Z]{2}$")
    county_fips: str | None = Field(None, pattern=r"^\d{5}$")
    total_acres: float | None = Field(None, gt=0)
    goals: Goals | None = None


class FarmResponse(BaseModel):
    id: UUID
    user_id: str
    name: str
    state: str
    county_fips: str
    total_acres: float
    goals: Goals | None = None
    created_at: datetime


# --- Field ---

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


# --- Soil Profile ---

class SoilProfileResponse(BaseModel):
    id: str
    field_id: str
    ssurgo_map_unit: str
    texture: str
    ph: float
    organic_matter_pct: float
    source: str
    fetched_at: datetime


# --- Weather ---

class WeatherResponse(BaseModel):
    id: str
    field_id: str
    date: str
    temp_high: float
    temp_low: float
    precip_mm: float
    soil_temp: float
    fetched_at: datetime


# --- Recommendation ---

class RecommendationResponse(BaseModel):
    id: str
    field_id: str
    created_at: datetime
    practice_code: str
    title: str
    rationale: str
    priority: Priority
    status: RecommendationStatus


class RecommendationStatusUpdate(BaseModel):
    status: RecommendationStatus


# --- Credit Eligibility ---

class CreditEligibilityResponse(BaseModel):
    """Single stored credit eligibility record from the credit_eligibility table."""

    id: str
    farm_id: UUID
    program: CreditProgram
    status: CreditStatus
    practices_documented: list[str]
    notes: str
    updated_at: datetime


class CreditEligibilityGetResponse(BaseModel):
    """Response shape for GET /credits/ — latest EQIP and VCM records for a farm."""

    farm_id: UUID
    eqip: CreditEligibilityResponse | None = None
    vcm: CreditEligibilityResponse | None = None


class EvaluatedProgramResult(BaseModel):
    """Per-program result produced by a fresh evaluation run."""

    program: str
    eligibility_status: CreditStatus | None = None
    practices_documented: list[str] = Field(default_factory=list)
    notes: str = ""
    updated_at: datetime | None = None
    # VCM-specific optional fields
    program_name: str | None = None
    estimated_total_credits: float | None = None
    field_breakdown: list[dict] = Field(default_factory=list)


class CreditEvaluateResponse(BaseModel):
    """Response shape for POST /credits/evaluate."""

    status: str
    farm_id: UUID
    eqip: EvaluatedProgramResult
    vcm: EvaluatedProgramResult


class CreditReportFarm(BaseModel):
    id: str | None = None
    name: str | None = None
    state: str | None = None
    county_fips: str | None = None
    total_acres: float | None = None
    goals: Goals | None = None


class CreditReportField(BaseModel):
    id: str | None = None
    name: str | None = None
    acres: float | None = None
    crop_type: str | None = None
    practices: list[str] = Field(default_factory=list)


class CreditReportProgram(BaseModel):
    status: CreditStatus | None = None
    notes: str = ""
    practices_documented: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None
    # VCM-specific optional fields
    program_name: str | None = None
    estimated_total_credits: float | None = None
    field_breakdown: list[dict] = Field(default_factory=list)


class CreditReportResponse(BaseModel):
    """Response shape for GET /credits/report."""

    report_type: str
    generated_at: str
    farm: CreditReportFarm
    fields: list[CreditReportField]
    eqip: CreditReportProgram
    vcm: CreditReportProgram


# --- CSP Navigator ---

class CSPApplicationStatus(str, Enum):
    eligible = "eligible"
    not_eligible = "not_eligible"
    pending_review = "pending_review"
    act_now = "act_now"  # CART score meets/exceeds state ranking threshold


class CSPResourceConcern(BaseModel):
    """A single NRCS Priority Resource Concern with its stewardship assessment."""

    concern_id: str = Field(..., description="Internal identifier, e.g. 'soil_health'")
    name: str = Field(..., description="Human-readable concern name")
    category: str = Field(..., description="One of the 8 NRCS priority categories")
    practices_addressing: list[str] = Field(
        default_factory=list,
        description="EQIP practice codes on the farm that address this concern",
    )
    meets_threshold: bool = Field(
        ...,
        description="Whether the farm currently meets the stewardship threshold",
    )
    points_earned: float = Field(0.0, ge=0.0)
    points_possible: float = Field(0.0, ge=0.0)


class CSPScoreBreakdown(BaseModel):
    """Detailed CART stewardship score for a farm."""

    farm_id: str
    total_points: float = Field(..., ge=0.0)
    max_possible_points: float = Field(..., ge=0.0)
    state_ranking_threshold: float = Field(
        ...,
        description="State-set minimum CART score for ranking approval",
    )
    meets_ranking_threshold: bool
    gap_to_threshold: float = Field(
        ...,
        ge=0.0,
        description="Points needed to reach ranking threshold (0 if already met)",
    )
    resource_concern_scores: list[CSPResourceConcern]
    component_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Score breakdown by practice category (soil, water, air, etc.)",
    )
    evaluated_at: datetime


class CSPPaymentEstimate(BaseModel):
    """Annual and 5-year CSP payment estimate for a farm."""

    farm_id: str
    eligible_acres: float = Field(..., ge=0.0)
    # Existing Activity Payment
    eap_annual: float = Field(
        ...,
        ge=0.0,
        description="Annual Existing Activity Payment in USD",
    )
    eap_rate_per_acre: float = Field(..., ge=0.0)
    resource_concerns_addressed: int = Field(
        ...,
        ge=0,
        description="Number of priority resource concerns addressed above threshold",
    )
    # Enhancement Activity Payment
    enap_annual: float = Field(
        ...,
        ge=0.0,
        description="Annual Enhancement Activity Payment in USD",
    )
    enap_is_bundle: bool = Field(
        False,
        description="True if enhancements qualify for 115% bundle rate",
    )
    # Totals
    total_annual_payment: float = Field(..., ge=0.0)
    total_5year_payment: float = Field(..., ge=0.0)
    payment_capped: bool = Field(
        False,
        description="True if the estimate was capped at NRCS annual or contract limits",
    )
    field_breakdown: list[dict] = Field(
        default_factory=list,
        description="Per-field payment detail",
    )
    state: str
    estimated_at: datetime


class CSPEnhancementActivity(BaseModel):
    """A recommended CSP enhancement activity for a farm."""

    code: str = Field(..., description="Enhancement activity code, e.g. E328A")
    name: str
    category: str = Field(..., description="Resource concern category addressed")
    land_use: str = Field("cropland")
    description: str
    estimated_cost_per_acre: float = Field(..., ge=0.0)
    payment_rate_pct: float = Field(
        100.0,
        description="Percentage of practice cost covered (100% standard, 115% bundle)",
    )
    estimated_annual_payment: float = Field(..., ge=0.0)
    applicable_acres: float = Field(..., ge=0.0)
    resource_concerns_addressed: list[str] = Field(default_factory=list)
    priority_score: float = Field(
        0.0,
        description="Ranking score contribution if this enhancement is adopted",
    )
    is_bundle_eligible: bool = False


class CSPEligibilityResponse(BaseModel):
    """Full CSP eligibility assessment for a farm."""

    farm_id: str
    status: CSPApplicationStatus
    is_eligible: bool
    resource_concerns_meeting_threshold: int = Field(
        ...,
        ge=0,
        description="Number of priority resource concerns currently meeting threshold (need >= 2)",
    )
    resource_concerns_detail: list[CSPResourceConcern] = Field(default_factory=list)
    cart_score: float = Field(..., ge=0.0)
    state_ranking_threshold: float
    meets_ranking_threshold: bool
    eligibility_notes: str
    recommended_enhancements: list[str] = Field(
        default_factory=list,
        description="Enhancement codes that would close the stewardship gap",
    )
    evaluated_at: datetime


# ---------------------------------------------------------------------------
# Field Activity Log
# ---------------------------------------------------------------------------

class ActivityType(str, Enum):
    plant = "plant"
    spray = "spray"
    fertilize = "fertilize"
    scout = "scout"
    harvest = "harvest"
    tillage = "tillage"
    cover_crop = "cover_crop"
    other = "other"


class ScoutingSeverity(str, Enum):
    none = "none"
    low = "low"
    moderate = "moderate"
    high = "high"
    critical = "critical"


class ActivityCreate(BaseModel):
    """Payload for logging a new field activity."""

    field_id: UUID
    activity_type: ActivityType
    activity_date: date

    # Planting fields
    seed_variety: str | None = Field(None, max_length=200)
    seeding_rate: float | None = Field(None, ge=0)
    seed_treatment: str | None = Field(None, max_length=200)

    # Spray / fertilize fields
    product_name: str | None = Field(None, max_length=200)
    rate_per_acre: float | None = Field(None, ge=0)
    rate_unit: str | None = Field(None, max_length=50)
    target_pest: str | None = Field(None, max_length=200)
    restricted_use: bool = False
    applicator_name: str | None = Field(None, max_length=200)
    applicator_license: str | None = Field(None, max_length=100)

    # Harvest fields
    yield_bu_acre: float | None = Field(None, ge=0)
    moisture_pct: float | None = Field(None, ge=0, le=100)
    crop_year: int | None = Field(None, ge=1990, le=2100)

    # Scouting fields
    pest_disease_found: str | None = Field(None, max_length=200)
    severity: ScoutingSeverity | None = None

    # Tillage / cover crop fields
    tillage_depth_in: float | None = Field(None, ge=0)
    cover_crop_species: str | None = Field(None, max_length=200)

    # Common optional fields
    notes: str | None = Field(None, max_length=2000)
    operator: str | None = Field(None, max_length=200)
    equipment_used: str | None = Field(None, max_length=200)
    cost_per_acre: float | None = Field(None, ge=0)
    acres_applied: float | None = Field(None, ge=0)


class ActivityResponse(BaseModel):
    """Full activity record returned from the API."""

    id: str
    field_id: str
    activity_type: ActivityType
    activity_date: date

    seed_variety: str | None = None
    seeding_rate: float | None = None
    seed_treatment: str | None = None

    product_name: str | None = None
    rate_per_acre: float | None = None
    rate_unit: str | None = None
    target_pest: str | None = None
    restricted_use: bool = False
    applicator_name: str | None = None
    applicator_license: str | None = None

    yield_bu_acre: float | None = None
    moisture_pct: float | None = None
    crop_year: int | None = None

    pest_disease_found: str | None = None
    severity: ScoutingSeverity | None = None

    tillage_depth_in: float | None = None
    cover_crop_species: str | None = None

    notes: str | None = None
    operator: str | None = None
    equipment_used: str | None = None
    cost_per_acre: float | None = None
    acres_applied: float | None = None

    created_at: datetime
    updated_at: datetime


class ActivityListResponse(BaseModel):
    """Paginated list of field activities."""

    activities: list[ActivityResponse]
    total_count: int


class ActivityUpdate(BaseModel):
    """Partial update payload for an existing activity."""

    activity_type: ActivityType | None = None
    activity_date: date | None = None

    seed_variety: str | None = Field(None, max_length=200)
    seeding_rate: float | None = Field(None, ge=0)
    seed_treatment: str | None = Field(None, max_length=200)

    product_name: str | None = Field(None, max_length=200)
    rate_per_acre: float | None = Field(None, ge=0)
    rate_unit: str | None = Field(None, max_length=50)
    target_pest: str | None = Field(None, max_length=200)
    restricted_use: bool | None = None
    applicator_name: str | None = Field(None, max_length=200)
    applicator_license: str | None = Field(None, max_length=100)

    yield_bu_acre: float | None = Field(None, ge=0)
    moisture_pct: float | None = Field(None, ge=0, le=100)
    crop_year: int | None = Field(None, ge=1990, le=2100)

    pest_disease_found: str | None = Field(None, max_length=200)
    severity: ScoutingSeverity | None = None

    tillage_depth_in: float | None = Field(None, ge=0)
    cover_crop_species: str | None = Field(None, max_length=200)

    notes: str | None = Field(None, max_length=2000)
    operator: str | None = Field(None, max_length=200)
    equipment_used: str | None = Field(None, max_length=200)
    cost_per_acre: float | None = Field(None, ge=0)
    acres_applied: float | None = Field(None, ge=0)


# ---------------------------------------------------------------------------
# Yield History
# ---------------------------------------------------------------------------

class YieldHistoryCreate(BaseModel):
    """Payload for recording a yield history entry."""

    field_id: UUID
    crop_year: int = Field(..., ge=1990, le=2100)
    crop_type: str = Field(..., min_length=1, max_length=100)
    yield_bu_acre: float = Field(..., ge=0)
    moisture_pct: float | None = Field(None, ge=0, le=100)
    acres_harvested: float | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=2000)


class YieldHistoryResponse(BaseModel):
    """Full yield history record returned from the API."""

    id: str
    field_id: str
    crop_year: int
    crop_type: str
    yield_bu_acre: float
    moisture_pct: float | None = None
    acres_harvested: float | None = None
    notes: str | None = None
    created_at: datetime


class APHResponse(BaseModel):
    """Actual Production History calculation result."""

    field_id: str
    aph_yield: float
    years_used: int
    year_range: str
    records: list[YieldHistoryResponse]


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

class DocumentType(str, Enum):
    soil_report = "soil_report"
    field_photo = "field_photo"
    compliance = "compliance"


class DocumentCreate(BaseModel):
    """Metadata submitted alongside a multipart file upload."""

    farm_id: UUID
    doc_type: DocumentType
    description: str | None = Field(None, max_length=500)


class DocumentResponse(BaseModel):
    """Document record returned from the API."""

    id: str
    farm_id: str
    user_id: str
    doc_type: DocumentType
    file_name: str
    storage_path: str
    size_bytes: int
    description: str | None = None
    created_at: datetime
