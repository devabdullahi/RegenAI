"""Yield history and APH models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
