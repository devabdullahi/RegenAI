"""RegenAI's stewardship scoring model. These values are UNSOURCED ESTIMATES."""

from __future__ import annotations

from typing import Final

from app.services.program_rules.rule_types import EstimatedRule

CSP_SCORING_MODEL_AS_OF: Final[str] = "2026-09-13"


CSP_SCORING_MODEL_NOTE: Final[str] = (
    "RegenAI's approximation of the NRCS CART score. Point weights, the "
    "stewardship threshold, soil organic matter multipliers and state ranking "
    "thresholds are estimates; NRCS and each state set the real values."
)


#: Maximum RegenAI points per priority resource concern (sums to 100).
CSP_CART_MAX_POINTS_PER_CONCERN: Final[dict[str, float]] = {
    "soil_health": 20.0,
    "soil_erosion": 15.0,
    "water_quality": 20.0,
    "water_quantity": 10.0,
    "air_quality": 10.0,
    "plant_condition": 10.0,
    "animals": 5.0,
    "energy": 10.0,
}


CSP_CART_MAX_POINTS_RULE: Final[EstimatedRule] = EstimatedRule(
    key="csp_cart_max_points_per_concern",
    status="estimate",
    as_of=CSP_SCORING_MODEL_AS_OF,
    note=(
        "Earlier code described these as 'NRCS FY2024 CART worksheets', but no "
        "worksheet is on file. CART weights vary by state and land use."
    ),
)


#: Fraction of a concern's maximum points that counts as meeting the
#: stewardship threshold for that concern.
CSP_STEWARDSHIP_THRESHOLD_FRACTION: Final[float] = 0.50


CSP_STEWARDSHIP_THRESHOLD_RULE: Final[EstimatedRule] = EstimatedRule(
    key="csp_stewardship_threshold_fraction",
    status="estimate",
    as_of=CSP_SCORING_MODEL_AS_OF,
    note="NRCS sets stewardship thresholds per resource concern in CART; 50% is a proxy.",
)


#: State CART ranking thresholds (points out of 100). States absent from this
#: map have no threshold on file: the score is reported without one rather
#: than against an invented default (see ``CSP_RANKING_THRESHOLD_*`` below).
CSP_STATE_RANKING_THRESHOLDS: Final[dict[str, float]] = {
    "IL": 45.0,
    "IN": 43.0,
    "IA": 47.0,
    "KS": 40.0,
    "MI": 42.0,
    "MN": 45.0,
    "MO": 41.0,
    "NE": 42.0,
    "ND": 38.0,
    "OH": 44.0,
    "SD": 39.0,
    "WI": 43.0,
}


CSP_STATE_RANKING_THRESHOLD_RULE: Final[EstimatedRule] = EstimatedRule(
    key="csp_state_ranking_thresholds",
    status="unverified",
    as_of=CSP_SCORING_MODEL_AS_OF,
    note=(
        "Described in earlier code as historical median cut-off scores; no "
        "source is on file. States set ranking cut-offs per signup."
    ),
)


#: Per-response provenance for the state ranking threshold. There is
#: deliberately no numeric default: NRCS state offices set ranking cut-offs
#: each signup and do not publish them in advance, so a state that is not in
#: ``CSP_STATE_RANKING_THRESHOLDS`` gets ``None`` and this status.
CSP_RANKING_THRESHOLD_STATUS_KNOWN: Final[str] = "known_estimate"
CSP_RANKING_THRESHOLD_STATUS_UNKNOWN: Final[str] = "not_published"


CSP_RANKING_THRESHOLD_UNKNOWN_NOTE: Final[str] = (
    "No CSP ranking threshold is on file for this state. NRCS state offices "
    "set and apply ranking cut-offs, so RegenAI reports no threshold rather "
    "than an invented one."
)


#: Soil organic matter tiers: minimum SOM % for each tier, highest first.
#: Anything below the lowest minimum is ``"poor"``.
CSP_SOM_TIER_MIN_PCT: Final[dict[str, float]] = {
    "high": 4.0,
    "medium": 2.5,
    "low": 1.5,
}


CSP_SOM_POOR_TIER: Final[str] = "poor"


#: Tier assumed when a farm has no soil organic matter data (conservative).
CSP_SOM_DEFAULT_TIER: Final[str] = "low"


#: Multiplier applied to soil_health points for each SOM tier.
CSP_SOM_MULTIPLIERS: Final[dict[str, float]] = {
    "high": 1.5,
    "medium": 1.2,
    "low": 1.0,
    "poor": 0.7,
}


CSP_SOM_RULE: Final[EstimatedRule] = EstimatedRule(
    key="csp_som_multipliers",
    status="estimate",
    as_of=CSP_SCORING_MODEL_AS_OF,
    note="RegenAI weighting of soil organic matter; not an NRCS CART factor table.",
)
