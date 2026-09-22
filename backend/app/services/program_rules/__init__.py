"""
Dated, sourced USDA program rules for RegenAI.

Every rate, cap, and fixed amount used by the CSP estimators lives here with
an ``as_of`` date and a ``source_url`` so the API can cite exactly which rule
version produced an estimate. When NRCS publishes new policy, add a new
constant (or update ``as_of``/``source_url``) here rather than hard-coding
numbers in service modules.

Primary source for FY2026 CSP changes:
    NRCS National Bulletin 440-26-2, "PGM - Fiscal Year 2026 Financial
    Assistance Program Changes and Guidance", dated 2025-12-17.
"""

# Re-exported so ``app.services.program_rules`` keeps its original import surface.
# The definitions now live in the sibling modules listed below.

from app.services.program_rules.aph import (
    APH_CFR_TITLE,
    APH_CFR_URL,
    APH_MAX_YIELD_YEARS,
    APH_MIN_YIELD_YEARS,
    APH_RULES_AS_OF,
)
from app.services.program_rules.csp_limits import (
    CSP_ACT_NOW_NOTE,
    CSP_ACTIVITY_MODEL_NOTE,
    CSP_ACTIVITY_RATE_AS_OF,
    CSP_ACTIVITY_RATE_BASIS,
    CSP_ACTIVITY_RATE_SOURCE_TITLE,
    CSP_ACTIVITY_RATE_SOURCE_URL,
    CSP_ACTIVITY_RATE_STATUS,
    CSP_ADDITIONAL_CONCERNS_REQUIRED,
    CSP_ANNUAL_PAYMENT_LIMIT,
    CSP_CFR_1470_20_URL,
    CSP_CONTRACT_LIMIT_FY2026_INDIVIDUAL,
    CSP_CONTRACT_LIMIT_FY2026_JOINT,
    CSP_CONTRACT_LIMIT_PRE_FY2026_INDIVIDUAL,
    CSP_CONTRACT_LIMIT_PRE_FY2026_JOINT,
    CSP_CONTRACT_YEARS,
    CSP_DEFAULT_CONTRACT_FY,
    CSP_EXISTING_ACTIVITY_PAYMENT,
    CSP_FY2026_RULES_START_FY,
    CSP_HIGHER_PAYMENT_CATEGORIES,
    CSP_MIN_PRIORITY_CONCERNS,
)
from app.services.program_rules.csp_scoring import (
    CSP_CART_MAX_POINTS_PER_CONCERN,
    CSP_CART_MAX_POINTS_RULE,
    CSP_RANKING_THRESHOLD_STATUS_KNOWN,
    CSP_RANKING_THRESHOLD_STATUS_UNKNOWN,
    CSP_RANKING_THRESHOLD_UNKNOWN_NOTE,
    CSP_SCORING_MODEL_AS_OF,
    CSP_SCORING_MODEL_NOTE,
    CSP_SOM_DEFAULT_TIER,
    CSP_SOM_MULTIPLIERS,
    CSP_SOM_POOR_TIER,
    CSP_SOM_RULE,
    CSP_SOM_TIER_MIN_PCT,
    CSP_STATE_RANKING_THRESHOLD_RULE,
    CSP_STATE_RANKING_THRESHOLDS,
    CSP_STEWARDSHIP_THRESHOLD_FRACTION,
    CSP_STEWARDSHIP_THRESHOLD_RULE,
)
from app.services.program_rules.fiscal import (
    FEDERAL_FY_START_MONTH,
    csp_contract_limit,
    csp_rules_metadata,
    csp_scoring_rules_metadata,
    csp_state_ranking_threshold_metadata,
    federal_fiscal_year,
)
from app.services.program_rules.practices import (
    CSP_GAP_CLOSURE_ACTIVITIES,
    CSP_PRACTICE_CATALOG,
    CSP_PRACTICE_CATALOG_RULE,
    CSP_SCORING_ESTIMATED_RULES,
    NRCS_PRACTICE_CODES_VERIFIED_AS_OF,
    NRCS_PRACTICE_STANDARDS_URL,
    CspPractice,
)
from app.services.program_rules.rule_types import (
    EstimatedRule,
    RuleStatus,
    RuleValue,
)
from app.services.program_rules.sources import (
    CSP_PROGRAM_URL,
    NB_440_26_2_AS_OF,
    NB_440_26_2_TITLE,
    NB_440_26_2_URL,
)

__all__ = [
    "APH_CFR_TITLE",
    "APH_CFR_URL",
    "APH_MAX_YIELD_YEARS",
    "APH_MIN_YIELD_YEARS",
    "APH_RULES_AS_OF",
    "CSP_ACTIVITY_MODEL_NOTE",
    "CSP_ACTIVITY_RATE_AS_OF",
    "CSP_ACTIVITY_RATE_BASIS",
    "CSP_ACTIVITY_RATE_SOURCE_TITLE",
    "CSP_ACTIVITY_RATE_SOURCE_URL",
    "CSP_ACTIVITY_RATE_STATUS",
    "CSP_ACT_NOW_NOTE",
    "CSP_ADDITIONAL_CONCERNS_REQUIRED",
    "CSP_ANNUAL_PAYMENT_LIMIT",
    "CSP_CART_MAX_POINTS_PER_CONCERN",
    "CSP_CART_MAX_POINTS_RULE",
    "CSP_CFR_1470_20_URL",
    "CSP_CONTRACT_LIMIT_FY2026_INDIVIDUAL",
    "CSP_CONTRACT_LIMIT_FY2026_JOINT",
    "CSP_CONTRACT_LIMIT_PRE_FY2026_INDIVIDUAL",
    "CSP_CONTRACT_LIMIT_PRE_FY2026_JOINT",
    "CSP_CONTRACT_YEARS",
    "CSP_DEFAULT_CONTRACT_FY",
    "CSP_EXISTING_ACTIVITY_PAYMENT",
    "CSP_FY2026_RULES_START_FY",
    "CSP_GAP_CLOSURE_ACTIVITIES",
    "CSP_HIGHER_PAYMENT_CATEGORIES",
    "CSP_MIN_PRIORITY_CONCERNS",
    "CSP_PRACTICE_CATALOG",
    "CSP_PRACTICE_CATALOG_RULE",
    "CSP_PROGRAM_URL",
    "CSP_RANKING_THRESHOLD_STATUS_KNOWN",
    "CSP_RANKING_THRESHOLD_STATUS_UNKNOWN",
    "CSP_RANKING_THRESHOLD_UNKNOWN_NOTE",
    "CSP_SCORING_ESTIMATED_RULES",
    "CSP_SCORING_MODEL_AS_OF",
    "CSP_SCORING_MODEL_NOTE",
    "CSP_SOM_DEFAULT_TIER",
    "CSP_SOM_MULTIPLIERS",
    "CSP_SOM_POOR_TIER",
    "CSP_SOM_RULE",
    "CSP_SOM_TIER_MIN_PCT",
    "CSP_STATE_RANKING_THRESHOLDS",
    "CSP_STATE_RANKING_THRESHOLD_RULE",
    "CSP_STEWARDSHIP_THRESHOLD_FRACTION",
    "CSP_STEWARDSHIP_THRESHOLD_RULE",
    "CspPractice",
    "EstimatedRule",
    "FEDERAL_FY_START_MONTH",
    "NB_440_26_2_AS_OF",
    "NB_440_26_2_TITLE",
    "NB_440_26_2_URL",
    "NRCS_PRACTICE_CODES_VERIFIED_AS_OF",
    "NRCS_PRACTICE_STANDARDS_URL",
    "RuleStatus",
    "RuleValue",
    "csp_contract_limit",
    "csp_rules_metadata",
    "csp_scoring_rules_metadata",
    "csp_state_ranking_threshold_metadata",
    "federal_fiscal_year",
]
