"""CSP contract limits, payment caps, contract term and the eligibility gate (NB 440-26-2)."""

from __future__ import annotations

from typing import Final

from app.services.program_rules.rule_types import RuleValue
from app.services.program_rules.sources import (
    CSP_PROGRAM_URL,
    NB_440_26_2_AS_OF,
    NB_440_26_2_TITLE,
    NB_440_26_2_URL,
)

#: First fiscal year in which the revised (higher) CSP contract limits apply.
CSP_FY2026_RULES_START_FY: Final[int] = 2026


#: Fiscal year assumed for a new contract when the caller does not specify one.
CSP_DEFAULT_CONTRACT_FY: Final[int] = 2026


CSP_CONTRACT_LIMIT_FY2026_INDIVIDUAL: Final[RuleValue] = RuleValue(
    key="csp_contract_limit_fy2026_individual",
    value=300_000.0,
    unit="usd_per_contract",
    as_of=NB_440_26_2_AS_OF,
    source_url=NB_440_26_2_URL,
    source_title=NB_440_26_2_TITLE,
    note="Contracts enrolled in FY2026 or later; individuals and legal entities.",
)


CSP_CONTRACT_LIMIT_FY2026_JOINT: Final[RuleValue] = RuleValue(
    key="csp_contract_limit_fy2026_joint",
    value=600_000.0,
    unit="usd_per_contract",
    as_of=NB_440_26_2_AS_OF,
    source_url=NB_440_26_2_URL,
    source_title=NB_440_26_2_TITLE,
    note="Contracts enrolled in FY2026 or later; joint operations.",
)


CSP_CONTRACT_LIMIT_PRE_FY2026_INDIVIDUAL: Final[RuleValue] = RuleValue(
    key="csp_contract_limit_pre_fy2026_individual",
    value=200_000.0,
    unit="usd_per_contract",
    as_of=NB_440_26_2_AS_OF,
    source_url=NB_440_26_2_URL,
    source_title=NB_440_26_2_TITLE,
    note="Contracts obligated before FY2026; a person or legal entity.",
)


CSP_CONTRACT_LIMIT_PRE_FY2026_JOINT: Final[RuleValue] = RuleValue(
    key="csp_contract_limit_pre_fy2026_joint",
    value=400_000.0,
    unit="usd_per_contract",
    as_of=NB_440_26_2_AS_OF,
    source_url=NB_440_26_2_URL,
    source_title=NB_440_26_2_TITLE,
    note="Contracts obligated before FY2026; joint operations or general partnerships.",
)


CSP_ANNUAL_PAYMENT_LIMIT: Final[RuleValue] = RuleValue(
    key="csp_annual_payment_limit",
    value=None,
    unit="usd_per_year",
    as_of=NB_440_26_2_AS_OF,
    source_url=NB_440_26_2_URL,
    source_title=NB_440_26_2_TITLE,
    note=(
        "There are no payment limitations in FY 2026; the authority for CSP "
        "payment limitations expired in 2024."
    ),
)


CSP_EXISTING_ACTIVITY_PAYMENT: Final[RuleValue] = RuleValue(
    key="csp_existing_activity_payment",
    value=4_000.0,
    unit="usd_per_contract_per_year",
    as_of=NB_440_26_2_AS_OF,
    source_url=NB_440_26_2_URL,
    source_title=NB_440_26_2_TITLE,
    note=(
        "The EAP will be $4,000 per contract each year for new contracts "
        "starting in FY 2026. It is a fixed per-contract payment, not a floor "
        "on the total payment."
    ),
)


CSP_CONTRACT_YEARS: Final[RuleValue] = RuleValue(
    key="csp_contract_years",
    value=5,
    unit="years",
    as_of=NB_440_26_2_AS_OF,
    source_url=CSP_PROGRAM_URL,
    source_title="NRCS Conservation Stewardship Program",
    note="CSP contracts run for five years.",
)


CSP_ACTIVITY_MODEL_NOTE: Final[str] = (
    "Starting FY2026, unique 'E' enhancement codes are no longer used, bundles "
    "and some structural/infrastructure practices are no longer offered, and "
    "NRCS uses a single activity list. RegenAI keys activities by NRCS "
    "conservation practice standard code."
)


#: Activity categories that NB 440-26-2 says still receive higher CSP payments.
CSP_HIGHER_PAYMENT_CATEGORIES: Final[dict[str, str]] = {
    "cover_crop": "Cover crop activities",
    "agm": "Advanced grazing management (AGM)",
    "rccr": "Resource conserving crop rotation (RCCR)",
    "irccr": "Improved resource conserving crop rotation (IRCCR)",
}


#: Per-acre activity rates are carried over from pre-FY2026 seed data and have
#: NOT been verified against a FY2026 state payment schedule.
CSP_ACTIVITY_RATE_STATUS: Final[str] = "estimate"


CSP_ACTIVITY_RATE_BASIS: Final[str] = (
    "Pre-FY2026 estimate, pending FY2026 state payment schedule"
)


CSP_ACTIVITY_RATE_AS_OF: Final[str] = "2026-04-06"


CSP_ACTIVITY_RATE_SOURCE_URL: Final[str | None] = None


CSP_ACTIVITY_RATE_SOURCE_TITLE: Final[str] = (
    "RegenAI CSP seed data (pre-FY2026 enhancement rates, "
    "supabase/migrations/20260406000004_csp_seed_data.sql)"
)


CSP_MIN_PRIORITY_CONCERNS: Final[RuleValue] = RuleValue(
    key="csp_min_priority_concerns_meeting_threshold",
    value=2,
    unit="priority_resource_concerns",
    as_of=NB_440_26_2_AS_OF,
    source_url=CSP_PROGRAM_URL,
    source_title="NRCS Conservation Stewardship Program",
    note=(
        "An operation must meet the stewardship threshold on at least two "
        "priority resource concerns to enroll. The frontend mirrors this value "
        "as CSP_MIN_CONCERNS in lib/api/adapters.ts."
    ),
)


CSP_CFR_1470_20_URL: Final[str] = (
    "https://www.ecfr.gov/current/title-7/subtitle-B/chapter-XIV/subchapter-B/"
    "part-1470/subpart-B/section-1470.20"
)


CSP_ADDITIONAL_CONCERNS_REQUIRED: Final[RuleValue] = RuleValue(
    key="csp_additional_priority_concerns_by_contract_end",
    value=1,
    unit="priority_resource_concerns",
    as_of="2026-09-13",
    source_url=CSP_CFR_1470_20_URL,
    source_title="7 CFR 1470.20, Application for contracts and selecting offers from applicants",
    note=(
        "Besides meeting the stewardship threshold on at least two priority "
        "resource concerns at contract offer, the applicant must meet or exceed "
        "it on at least one additional priority resource concern by the end of "
        f"the contract. Also stated on the NRCS CSP page ({CSP_PROGRAM_URL}). "
        "Renewals have a stricter requirement that RegenAI does not model."
    ),
)


CSP_ACT_NOW_NOTE: Final[str] = (
    "ACT NOW is used at the state conservationist's discretion. Meeting the "
    "ranking threshold does not guarantee fast-track approval."
)
