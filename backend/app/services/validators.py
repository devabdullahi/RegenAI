"""
Output validators for the AI recommendation pipeline.

Provides Pydantic models for LLM output validation and a hallucination guard
that verifies every practice_code against the eqip_practices table.
"""

import logging
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models for LLM output validation
# ---------------------------------------------------------------------------

class LLMPriority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class LLMRecommendation(BaseModel):
    """Schema for a single recommendation as returned by the LLM.

    LLM output is untrusted: unknown keys are rejected rather than ignored so a
    drifting output shape fails validation instead of being silently accepted.
    """

    model_config = ConfigDict(extra="forbid")

    field_id: UUID = Field(..., description="UUID of the target field")
    practice_code: str = Field(..., min_length=1, description="EQIP practice code")
    title: str = Field(..., min_length=1, max_length=200, description="Short title")
    rationale: str = Field(..., min_length=10, description="Explanation with data citations")
    priority: LLMPriority = Field(default=LLMPriority.medium)
    csp_impact: str | None = None

    @field_validator("practice_code")
    @classmethod
    def strip_practice_code(cls, v: str) -> str:
        """Normalize practice code to stripped string."""
        return v.strip()

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()


# ---------------------------------------------------------------------------
# Hallucination guard
# ---------------------------------------------------------------------------

def validate_practice_codes(
    recommendations: list[LLMRecommendation],
    valid_codes: set[str],
) -> tuple[list[LLMRecommendation], list[LLMRecommendation]]:
    """Check every recommendation's practice_code against the known EQIP codes.

    Args:
        recommendations: Parsed LLM recommendations.
        valid_codes: Set of practice code strings from the eqip_practices table.

    Returns:
        A tuple of (valid_recommendations, flagged_recommendations).
        Flagged recommendations have an unknown practice_code; the caller
        logs and drops them so farmers never see an unverified practice.
    """
    valid: list[LLMRecommendation] = []
    flagged: list[LLMRecommendation] = []

    for rec in recommendations:
        if rec.practice_code in valid_codes:
            valid.append(rec)
        else:
            logger.warning(
                "Hallucination guard flagged practice_code=%s (title=%s) — "
                "not found in eqip_practices table",
                rec.practice_code,
                rec.title,
            )
            flagged.append(rec)

    logger.info(
        "Hallucination guard: %d valid, %d flagged out of %d total",
        len(valid),
        len(flagged),
        len(recommendations),
    )

    return valid, flagged


def validate_field_ids(
    recommendations: list[LLMRecommendation],
    valid_field_ids: set[str],
) -> tuple[list[LLMRecommendation], list[LLMRecommendation]]:
    """Verify that every recommendation targets a field belonging to this farm.

    This prevents the LLM from hallucinating field IDs that could reference
    another farm's data.

    Args:
        recommendations: Parsed LLM recommendations.
        valid_field_ids: Set of field UUID strings belonging to the target farm.

    Returns:
        A tuple of (valid_recommendations, flagged_recommendations).
    """
    valid: list[LLMRecommendation] = []
    flagged: list[LLMRecommendation] = []

    for rec in recommendations:
        # str(UUID) is the canonical lowercase form Postgres returns for uuid columns.
        if str(rec.field_id) in valid_field_ids:
            valid.append(rec)
        else:
            logger.warning(
                "Field ID guard flagged field_id=%s (title=%s) — "
                "not in this farm's field set",
                rec.field_id,
                rec.title,
            )
            flagged.append(rec)

    return valid, flagged
