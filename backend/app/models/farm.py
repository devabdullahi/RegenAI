"""Farm request and response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import Goals


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
