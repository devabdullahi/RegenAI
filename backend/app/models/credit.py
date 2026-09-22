"""Credit eligibility (EQIP / VCM) and credit report models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import CreditProgram, CreditStatus, Goals


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
    # VCM rule provenance (app.services.credit_rules.vcm_rules_metadata)
    method_label: str | None = None
    is_estimate: bool | None = None
    rules_status: str | None = None
    rules_as_of: str | None = None
    rules_source_url: str | None = None
    rules_source_title: str | None = None
    rules_note: str | None = None


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
    # VCM rule provenance (app.services.credit_rules.vcm_rules_metadata)
    method_label: str | None = None
    is_estimate: bool | None = None
    rules_status: str | None = None
    rules_as_of: str | None = None
    rules_source_url: str | None = None
    rules_source_title: str | None = None
    rules_note: str | None = None


class CreditReportResponse(BaseModel):
    """Response shape for GET /credits/report."""

    report_type: str
    generated_at: str
    farm: CreditReportFarm
    fields: list[CreditReportField]
    eqip: CreditReportProgram
    vcm: CreditReportProgram
    # Sections that could not be loaded; empty when the report is complete.
    data_warnings: list[str] = Field(default_factory=list)
