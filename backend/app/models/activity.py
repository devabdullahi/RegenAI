"""Field activity log models."""

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


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

    # Non-fatal notices from create (e.g. harvest saved but yield history not synced).
    warnings: list[str] = Field(default_factory=list)


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
