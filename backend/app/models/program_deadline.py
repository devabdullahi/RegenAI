"""Program deadline models for GET /csp/deadlines."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class ProgramDeadlineStatus(str, Enum):
    confirmed = "confirmed"  # date published by the agency (or reported from it)
    expected = "expected"  # recurring program, this year's dates not out yet
    not_announced = "not_announced"  # no cutoff published yet


class DeadlineUrgency(str, Enum):
    # Day cutoffs are program_deadlines.URGENT_DAYS / SOON_DAYS.
    urgent = "urgent"
    soon = "soon"
    later = "later"


class ProgramDeadlineItem(BaseModel):
    """One upcoming program deadline with computed countdown fields."""

    id: str
    program: str = Field(..., description="Program name, e.g. 'EQIP and CSP', 'SDRP'")
    state: str = Field(..., description="Two-letter state code, or 'ALL'")
    title: str
    description: str = Field(..., description="Plain-language explanation")
    status: ProgramDeadlineStatus
    source_url: str
    as_of: date = Field(..., description="Date the entry was last verified")
    period_label: str = Field(..., description="Funding period, e.g. 'FY2027 funding'")
    fiscal_year: int | None = None
    deadline_date: date | None = None
    notes: str | None = None
    days_remaining: int | None = None
    urgency: DeadlineUrgency | None = None
    # Legacy aliases kept for older clients of GET /csp/deadlines.
    cutoff_date: date | None = None
    signup_period: str | None = None


class ProgramDeadlinesResponse(BaseModel):
    """Response shape for GET /csp/deadlines."""

    state: str = Field(..., description="Two-letter code, or 'NATIONAL' when omitted")
    today: date
    deadlines: list[ProgramDeadlineItem]
    advisory: str
    program_url: str
