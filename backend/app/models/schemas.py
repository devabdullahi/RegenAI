"""Backward-compatible re-exports.

The models now live in per-domain modules beside this one; importing
``app.models.schemas`` keeps working so call sites need not change.
New code may import from the specific module instead.
"""

from app.models.activity import (
    ActivityCreate,
    ActivityListResponse,
    ActivityResponse,
    ActivityType,
    ActivityUpdate,
    ScoutingSeverity,
)
from app.models.credit import (
    CreditEligibilityGetResponse,
    CreditEligibilityResponse,
    CreditEvaluateResponse,
    CreditReportFarm,
    CreditReportField,
    CreditReportProgram,
    CreditReportResponse,
    EvaluatedProgramResult,
)
from app.models.csp import (
    CSPActivityPaymentItem,
    CSPActivityRatesRule,
    CSPApplicationStatus,
    CSPContractLimit,
    CSPEligibilityResponse,
    CSPEnhancementActivity,
    CSPEnhancementsResponse,
    CSPEstimatedRuleCitation,
    CSPEvaluateEligibilitySummary,
    CSPEvaluatePaymentSummary,
    CSPEvaluateResponse,
    CSPEvaluateScoreSummary,
    CSPExistingActivityPaymentRule,
    CSPMinPriorityConcernsRule,
    CSPPaymentEstimate,
    CSPPaymentFieldBreakdown,
    CSPResourceConcern,
    CSPRulesMetadata,
    CSPScoreBreakdown,
    CSPScoringRulesMetadata,
    CSPStateRankingThresholdCitation,
)
from app.models.document import (
    DocumentResponse,
    DocumentType,
)
from app.models.enums import (
    CreditProgram,
    CreditStatus,
    Goals,
    Priority,
    RecommendationStatus,
)
from app.models.farm import (
    FarmCreate,
    FarmResponse,
    FarmUpdate,
)
from app.models.field import (
    FieldCreate,
    FieldResponse,
    FieldUpdate,
)
from app.models.program_deadline import (
    DeadlineUrgency,
    ProgramDeadlineItem,
    ProgramDeadlinesResponse,
    ProgramDeadlineStatus,
)
from app.models.recommendation import (
    RecommendationResponse,
    RecommendationStatusUpdate,
)
from app.models.soil_weather import (
    SoilProfileResponse,
    WeatherResponse,
)
from app.models.yield_history import (
    APHResponse,
    YieldHistoryCreate,
    YieldHistoryResponse,
)

__all__ = [
    "APHResponse",
    "ActivityCreate",
    "ActivityListResponse",
    "ActivityResponse",
    "ActivityType",
    "ActivityUpdate",
    "CSPActivityPaymentItem",
    "CSPActivityRatesRule",
    "CSPApplicationStatus",
    "CSPContractLimit",
    "CSPEligibilityResponse",
    "CSPEnhancementActivity",
    "CSPEnhancementsResponse",
    "CSPEstimatedRuleCitation",
    "CSPEvaluateEligibilitySummary",
    "CSPEvaluatePaymentSummary",
    "CSPEvaluateResponse",
    "CSPEvaluateScoreSummary",
    "CSPExistingActivityPaymentRule",
    "CSPMinPriorityConcernsRule",
    "CSPPaymentEstimate",
    "CSPPaymentFieldBreakdown",
    "CSPResourceConcern",
    "CSPRulesMetadata",
    "CSPScoreBreakdown",
    "CSPScoringRulesMetadata",
    "CSPStateRankingThresholdCitation",
    "CreditEligibilityGetResponse",
    "CreditEligibilityResponse",
    "CreditEvaluateResponse",
    "CreditProgram",
    "CreditReportFarm",
    "CreditReportField",
    "CreditReportProgram",
    "CreditReportResponse",
    "CreditStatus",
    "DeadlineUrgency",
    "DocumentResponse",
    "DocumentType",
    "EvaluatedProgramResult",
    "FarmCreate",
    "FarmResponse",
    "FarmUpdate",
    "FieldCreate",
    "FieldResponse",
    "FieldUpdate",
    "Goals",
    "Priority",
    "ProgramDeadlineItem",
    "ProgramDeadlineStatus",
    "ProgramDeadlinesResponse",
    "RecommendationResponse",
    "RecommendationStatus",
    "RecommendationStatusUpdate",
    "ScoutingSeverity",
    "SoilProfileResponse",
    "WeatherResponse",
    "YieldHistoryCreate",
    "YieldHistoryResponse",
]
