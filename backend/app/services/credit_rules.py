"""
Dated rule values for the RegenAI credit estimators (VCM and EQIP).

The VCM credit bands and soil-organic-matter tiers below are NOT taken from a
carbon registry methodology. They were set internally when the MVP was
scoped and have no primary source, so every value carries ``status="estimate"``
and ``source_url=None``. The API surfaces ``VCM_METHOD_LABEL`` and
``is_estimate`` so no screen presents these numbers as registry-issued credits.

When a real methodology is adopted, replace the values here (with its
``as_of`` date and ``source_url``) rather than editing ``vcm.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Provenance shared by every VCM rule value
# ---------------------------------------------------------------------------

#: Shown wherever the VCM estimate is named. Deliberately not a protocol name.
VCM_METHOD_LABEL: Final[str] = "RegenAI estimate (not a registry protocol)"

VCM_RULES_STATUS: Final[str] = "estimate"
#: Date the band values were introduced (schema v1 / MVP execution brief).
VCM_RULES_AS_OF: Final[str] = "2026-04-02"
VCM_RULES_SOURCE_URL: Final[str | None] = None
VCM_RULES_SOURCE_TITLE: Final[str] = (
    "RegenAI MVP execution brief (internal, unsourced; not a registry methodology)"
)
VCM_RULES_NOTE: Final[str] = (
    "Credit rates are internal placeholder estimates. Actual credits depend on "
    "the registry, methodology, baseline and third-party verification."
)

CREDIT_RATE_UNIT: Final[str] = "credits_per_acre_per_year"


@dataclass(frozen=True)
class VcmCreditBand:
    """Estimated credit range for one conservation practice."""

    practice_code: str
    practice_name: str
    low: float
    high: float
    unit: str = CREDIT_RATE_UNIT
    as_of: str = VCM_RULES_AS_OF
    source_url: str | None = VCM_RULES_SOURCE_URL
    status: str = VCM_RULES_STATUS


@dataclass(frozen=True)
class SomTierThresholds:
    """Soil organic matter cut-offs that pick a point inside a credit band.

    SOM >= high_pct uses the band's upper bound, SOM >= low_pct the midpoint,
    and anything lower (or unknown) the lower bound.
    """

    high_pct: float
    low_pct: float
    as_of: str = VCM_RULES_AS_OF
    source_url: str | None = VCM_RULES_SOURCE_URL
    status: str = VCM_RULES_STATUS


#: Practice code (NRCS conservation practice standard) -> estimated credit band.
VCM_CREDIT_BANDS: Final[dict[str, VcmCreditBand]] = {
    "340": VcmCreditBand("340", "Cover Crop", low=0.5, high=1.2),
    "329": VcmCreditBand("329", "Residue and Tillage Management, No-Till", low=0.3, high=0.8),
    "328": VcmCreditBand("328", "Conservation Crop Rotation", low=0.2, high=0.5),
}

VCM_SOM_TIERS: Final[SomTierThresholds] = SomTierThresholds(high_pct=3.0, low_pct=1.5)


def vcm_rules_metadata() -> dict:
    """Return the provenance block included in VCM API responses."""
    return {
        "method_label": VCM_METHOD_LABEL,
        "is_estimate": True,
        "rules_status": VCM_RULES_STATUS,
        "rules_as_of": VCM_RULES_AS_OF,
        "rules_source_url": VCM_RULES_SOURCE_URL,
        "rules_source_title": VCM_RULES_SOURCE_TITLE,
        "rules_note": VCM_RULES_NOTE,
    }


# ---------------------------------------------------------------------------
# Errors shared by the credit estimators
# ---------------------------------------------------------------------------

class CreditDataError(RuntimeError):
    """A credit evaluation could not read its inputs or save its result.

    Raised instead of persisting a status computed from missing data. The
    message is safe to show to the user.
    """
