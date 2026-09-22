"""CSP Navigator models: scoring, payments, eligibility, enhancements."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


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


class CSPEstimatedRuleCitation(BaseModel):
    """Provenance of one unsourced scoring value (program_rules.EstimatedRule)."""

    key: str
    status: Literal["estimate", "unverified"]
    as_of: str
    note: str
    source_url: str | None = None
    source_title: str | None = None


class CSPMinPriorityConcernsRule(BaseModel):
    value: int = Field(..., ge=0)
    as_of: str
    source_url: str | None = None


class CSPStateRankingThresholdCitation(BaseModel):
    """Provenance of the state ranking threshold used for one response.

    ``status`` is ``known_estimate`` when RegenAI holds an (unverified)
    threshold for the state and ``not_published`` when it holds none. There is
    no fallback number: ``value`` is null whenever the status is
    ``not_published``.
    """

    state: str | None = Field(None, description="Two-letter state the score was run for")
    value: float | None = Field(
        None,
        description="Estimated ranking threshold in points; null when not published",
    )
    status: Literal["known_estimate", "not_published"]
    as_of: str
    source_url: str | None = None
    note: str


class CSPScoringRulesMetadata(BaseModel):
    """Citation block for the RegenAI CART approximation."""

    is_estimate: bool
    model: str
    as_of: str
    source_url: str | None = None
    note: str
    min_priority_concerns: CSPMinPriorityConcernsRule
    state_ranking_threshold: CSPStateRankingThresholdCitation
    estimated_rules: list[CSPEstimatedRuleCitation] = Field(default_factory=list)


class CSPScoreBreakdown(BaseModel):
    """Detailed CART stewardship score for a farm."""

    farm_id: str
    total_points: float = Field(..., ge=0.0)
    max_possible_points: float = Field(..., ge=0.0)
    state_ranking_threshold: float | None = Field(
        None,
        description=(
            "Estimated state ranking threshold (RegenAI estimate, unverified); "
            "null when the state has no published threshold on file"
        ),
    )
    meets_ranking_threshold: bool | None = Field(
        None,
        description="Null when the state ranking threshold is unknown",
    )
    gap_to_threshold: Annotated[float, Field(ge=0.0)] | None = Field(
        None,
        description=(
            "Points needed to reach the ranking threshold (0 if already met); "
            "null when the threshold is unknown"
        ),
    )
    resource_concern_scores: list[CSPResourceConcern]
    component_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Points earned per resource concern id",
    )
    avg_som_pct: float | None = Field(None, description="Mean soil organic matter %")
    som_tier: str = Field("low", description="SOM tier: high, medium, low, or poor")
    is_estimate: bool = Field(
        True,
        description="True when the score depends on unsourced RegenAI estimates",
    )
    scoring_rules: CSPScoringRulesMetadata
    evaluated_at: datetime


class CSPContractLimit(BaseModel):
    """The CSP contract limit applied to an estimate, with its citation."""

    amount: float = Field(..., ge=0.0)
    label: str = Field(..., description="Display label for the limit, from program_rules")
    rule_key: str
    applies_to: Literal["individual_or_entity", "joint_operation"]
    contract_fiscal_year: int
    rules_period: Literal["FY2026+", "pre-FY2026"]
    as_of: str
    source_url: str | None = None
    source_title: str | None = None


class CSPActivityPaymentItem(BaseModel):
    """One conservation activity included in a CSP payment estimate."""

    code: str = Field(..., description="Activity code, e.g. '340' or '328-RCCR'")
    practice_standard_code: str = Field(..., description="NRCS practice standard, e.g. '340'")
    name: str
    higher_payment: bool = Field(
        False,
        description="True for cover crop, AGM, RCCR, and IRCCR activities",
    )
    higher_payment_category: str | None = None
    estimated_rate_per_acre: float = Field(..., ge=0.0)
    rate_is_estimate: bool = True
    acres: float = Field(..., ge=0.0)
    estimated_annual_payment: float = Field(..., ge=0.0)


class CSPPaymentFieldBreakdown(BaseModel):
    """One field's acre-proportional share of a CSP payment estimate."""

    field_id: str
    field_name: str = ""
    acres: float = Field(..., ge=0.0)
    eap_annual: float = Field(..., ge=0.0)
    activity_payment_annual: float = Field(..., ge=0.0)
    total_annual: float = Field(..., ge=0.0)


class CSPExistingActivityPaymentRule(BaseModel):
    amount: float = Field(..., ge=0.0)
    unit: str
    label: str
    note: str
    as_of: str
    source_url: str | None = None


class CSPActivityRatesRule(BaseModel):
    status: str
    basis: str
    as_of: str
    source_url: str | None = None
    source_title: str


class CSPRulesMetadata(BaseModel):
    """Rule citation block returned by CSP payment and enhancement endpoints."""

    program: str
    as_of: str
    source_title: str
    source_url: str
    contract_limit: CSPContractLimit
    annual_payment_limit: float | None = None
    annual_payment_limit_note: str
    existing_activity_payment: CSPExistingActivityPaymentRule
    contract_years: int = Field(..., ge=1)
    activity_rates: CSPActivityRatesRule
    activity_model_note: str


class CSPPaymentEstimate(BaseModel):
    """Annual and 5-year CSP payment estimate for a farm (FY2026 rules)."""

    farm_id: str
    eligible_acres: float = Field(..., ge=0.0)
    resource_concerns_addressed: int = Field(
        ...,
        ge=0,
        description="Number of priority resource concerns addressed above threshold",
    )
    eap_annual: float = Field(
        ...,
        ge=0.0,
        description="Existing Activity Payment: fixed USD per contract per year (see rules)",
    )
    activity_payment_annual: float = Field(
        ...,
        ge=0.0,
        description="Estimated annual payment for conservation activities in USD",
    )
    activities_included: list[CSPActivityPaymentItem] = Field(default_factory=list)
    total_annual_payment: float = Field(..., ge=0.0)
    total_5year_payment: float = Field(..., ge=0.0)
    contract_years: int = Field(5, ge=1)
    contract_fiscal_year: int
    joint_operation: bool = False
    contract_limit: CSPContractLimit
    annual_payment_limit: float | None = Field(
        None,
        description="Annual payment limit in USD, or None when the rules set none",
    )
    payment_capped: bool = Field(
        False,
        description="True if the 5-year total was capped at the contract limit",
    )
    field_breakdown: list[CSPPaymentFieldBreakdown] = Field(
        default_factory=list,
        description="Per-field payment detail",
    )
    state: str
    rules: CSPRulesMetadata = Field(
        ...,
        description="Rule citation metadata (as_of, source_url, limits applied)",
    )
    estimated_at: datetime


class CSPEnhancementActivity(BaseModel):
    """A recommended CSP conservation activity for a farm (FY2026 model)."""

    code: str = Field(..., description="Activity code, e.g. '340' or '328-RCCR'")
    practice_standard_code: str = Field(..., description="NRCS practice standard, e.g. '340'")
    name: str
    category: str = Field(..., description="Resource concern category addressed")
    land_use: str = Field("cropland")
    description: str
    implementation_notes: str = ""
    estimated_rate_per_acre: float = Field(..., ge=0.0)
    rate_is_estimate: bool = True
    rate_basis: str = ""
    estimated_annual_payment: float = Field(..., ge=0.0)
    applicable_acres: float = Field(..., ge=0.0)
    resource_concerns_addressed: list[str] = Field(default_factory=list)
    priority_score: float = Field(
        0.0,
        description="Ranking score contribution if this activity is adopted",
    )
    higher_payment: bool = False
    higher_payment_category: str | None = None


class CSPEligibilityResponse(BaseModel):
    """Full CSP eligibility assessment for a farm."""

    farm_id: str
    status: CSPApplicationStatus
    is_eligible: bool
    resource_concerns_meeting_threshold: int = Field(
        ...,
        ge=0,
        description="Number of priority resource concerns currently meeting threshold",
    )
    min_concerns_required: int = Field(
        ...,
        ge=0,
        description=(
            "Priority resource concerns that must meet threshold to enroll "
            "(program_rules.CSP_MIN_PRIORITY_CONCERNS)"
        ),
    )
    additional_concerns_required: int = Field(
        ...,
        ge=0,
        description=(
            "Additional priority resource concerns the participant must agree to meet "
            "threshold on by the end of the contract "
            "(program_rules.CSP_ADDITIONAL_CONCERNS_REQUIRED)"
        ),
    )
    contract_years: int = Field(
        ...,
        ge=1,
        description="CSP contract length in years (program_rules.CSP_CONTRACT_YEARS)",
    )
    resource_concerns_detail: list[CSPResourceConcern] = Field(default_factory=list)
    cart_score: float = Field(..., ge=0.0)
    state_ranking_threshold: float | None = Field(
        None,
        description="Null when the state has no published ranking threshold on file",
    )
    meets_ranking_threshold: bool | None = Field(
        None,
        description="Null when the state ranking threshold is unknown",
    )
    eligibility_notes: str
    recommended_enhancements: list[str] = Field(
        default_factory=list,
        description="Activity codes that would close the stewardship gap",
    )
    is_estimate: bool = Field(
        True,
        description="True when the assessment depends on unsourced RegenAI estimates",
    )
    scoring_rules: CSPScoringRulesMetadata
    evaluated_at: datetime
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal problems, e.g. the assessment could not be saved.",
    )


class CSPEnhancementsResponse(BaseModel):
    """GET /csp/enhancements: ranked activities plus rule citations."""

    farm_id: str
    enhancements: list[CSPEnhancementActivity]
    rules: CSPRulesMetadata


class CSPEvaluateEligibilitySummary(BaseModel):
    status: CSPApplicationStatus
    is_eligible: bool
    resource_concerns_meeting_threshold: int = Field(..., ge=0)
    cart_score: float = Field(..., ge=0.0)
    meets_ranking_threshold: bool | None = None
    eligibility_notes: str
    recommended_enhancements: list[str] = Field(default_factory=list)


class CSPEvaluateScoreSummary(BaseModel):
    total_points: float = Field(..., ge=0.0)
    max_possible_points: float = Field(..., ge=0.0)
    state_ranking_threshold: float | None = None
    gap_to_threshold: Annotated[float, Field(ge=0.0)] | None = None
    component_scores: dict[str, float] = Field(default_factory=dict)


class CSPEvaluatePaymentSummary(BaseModel):
    total_annual_payment: float = Field(..., ge=0.0)
    total_5year_payment: float = Field(..., ge=0.0)
    eap_annual: float = Field(..., ge=0.0)
    activity_payment_annual: float = Field(..., ge=0.0)
    payment_capped: bool
    contract_limit: CSPContractLimit
    annual_payment_limit: float | None = None
    rules: CSPRulesMetadata


class CSPEvaluateResponse(BaseModel):
    """POST /csp/evaluate: summary of a fresh score, eligibility and payment run."""

    status: Literal["evaluation_complete"]
    farm_id: str
    eligibility: CSPEvaluateEligibilitySummary
    score: CSPEvaluateScoreSummary
    payments: CSPEvaluatePaymentSummary
    evaluated_at: datetime
