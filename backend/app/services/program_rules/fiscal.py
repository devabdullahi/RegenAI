"""Federal fiscal-year helpers and the rules-metadata assemblers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Final

from app.services.program_rules.csp_limits import (
    CSP_ACTIVITY_MODEL_NOTE,
    CSP_ACTIVITY_RATE_AS_OF,
    CSP_ACTIVITY_RATE_BASIS,
    CSP_ACTIVITY_RATE_SOURCE_TITLE,
    CSP_ACTIVITY_RATE_SOURCE_URL,
    CSP_ACTIVITY_RATE_STATUS,
    CSP_ANNUAL_PAYMENT_LIMIT,
    CSP_CONTRACT_LIMIT_FY2026_INDIVIDUAL,
    CSP_CONTRACT_LIMIT_FY2026_JOINT,
    CSP_CONTRACT_LIMIT_PRE_FY2026_INDIVIDUAL,
    CSP_CONTRACT_LIMIT_PRE_FY2026_JOINT,
    CSP_CONTRACT_YEARS,
    CSP_DEFAULT_CONTRACT_FY,
    CSP_EXISTING_ACTIVITY_PAYMENT,
    CSP_FY2026_RULES_START_FY,
    CSP_MIN_PRIORITY_CONCERNS,
)
from app.services.program_rules.csp_scoring import (
    CSP_RANKING_THRESHOLD_STATUS_KNOWN,
    CSP_RANKING_THRESHOLD_STATUS_UNKNOWN,
    CSP_RANKING_THRESHOLD_UNKNOWN_NOTE,
    CSP_SCORING_MODEL_AS_OF,
    CSP_SCORING_MODEL_NOTE,
    CSP_STATE_RANKING_THRESHOLD_RULE,
    CSP_STATE_RANKING_THRESHOLDS,
)
from app.services.program_rules.practices import CSP_SCORING_ESTIMATED_RULES
from app.services.program_rules.sources import NB_440_26_2_AS_OF, NB_440_26_2_TITLE, NB_440_26_2_URL

#: Month (1-12) in which the US federal fiscal year begins (October 1).
FEDERAL_FY_START_MONTH: Final[int] = 10


def federal_fiscal_year(when: date | datetime) -> int:
    """Return the US federal fiscal year containing ``when``.

    The federal fiscal year runs October 1 through September 30 and is named
    for the calendar year in which it ends: 2025-09-30 is FY2025, 2025-10-01
    is FY2026.
    """
    return when.year + 1 if when.month >= FEDERAL_FY_START_MONTH else when.year


def csp_contract_limit(
    contract_fiscal_year: int = CSP_DEFAULT_CONTRACT_FY,
    joint_operation: bool = False,
) -> dict:
    """Return the CSP contract limit that applies to a contract.

    Args:
        contract_fiscal_year: Federal fiscal year the contract is (or would be)
            obligated in. FY2026 and later use the revised limits.
        joint_operation: True for joint operations / general partnerships.

    Returns:
        Dict with ``amount``, ``label``, ``rule_key``, ``applies_to``,
        ``contract_fiscal_year``, ``rules_period``, ``as_of``, ``source_url``,
        and ``source_title``.
    """
    fy2026_plus = contract_fiscal_year >= CSP_FY2026_RULES_START_FY
    if fy2026_plus:
        rule = (
            CSP_CONTRACT_LIMIT_FY2026_JOINT
            if joint_operation
            else CSP_CONTRACT_LIMIT_FY2026_INDIVIDUAL
        )
        period = "FY2026+"
    else:
        rule = (
            CSP_CONTRACT_LIMIT_PRE_FY2026_JOINT
            if joint_operation
            else CSP_CONTRACT_LIMIT_PRE_FY2026_INDIVIDUAL
        )
        period = "pre-FY2026"

    amount = float(rule.value or 0.0)
    who = "joint operation " if joint_operation else ""
    return {
        "amount": amount,
        "label": f"${amount:,.0f} {who}contract limit ({period})",
        "rule_key": rule.key,
        "applies_to": "joint_operation" if joint_operation else "individual_or_entity",
        "contract_fiscal_year": contract_fiscal_year,
        "rules_period": period,
        "as_of": rule.as_of,
        "source_url": rule.source_url,
        "source_title": rule.source_title,
    }


def csp_rules_metadata(
    contract_fiscal_year: int = CSP_DEFAULT_CONTRACT_FY,
    joint_operation: bool = False,
) -> dict:
    """Return the rule citation block included in CSP API responses."""
    eap = CSP_EXISTING_ACTIVITY_PAYMENT
    return {
        "program": "CSP",
        "as_of": NB_440_26_2_AS_OF,
        "source_title": NB_440_26_2_TITLE,
        "source_url": NB_440_26_2_URL,
        "contract_limit": csp_contract_limit(contract_fiscal_year, joint_operation),
        "annual_payment_limit": CSP_ANNUAL_PAYMENT_LIMIT.value,
        "annual_payment_limit_note": CSP_ANNUAL_PAYMENT_LIMIT.note,
        "existing_activity_payment": {
            "amount": float(eap.value or 0.0),
            "unit": eap.unit,
            "label": f"EAP ${float(eap.value or 0.0):,.0f}/contract/yr",
            "note": eap.note,
            "as_of": eap.as_of,
            "source_url": eap.source_url,
        },
        "contract_years": int(CSP_CONTRACT_YEARS.value),
        "activity_rates": {
            "status": CSP_ACTIVITY_RATE_STATUS,
            "basis": CSP_ACTIVITY_RATE_BASIS,
            "as_of": CSP_ACTIVITY_RATE_AS_OF,
            "source_url": CSP_ACTIVITY_RATE_SOURCE_URL,
            "source_title": CSP_ACTIVITY_RATE_SOURCE_TITLE,
        },
        "activity_model_note": CSP_ACTIVITY_MODEL_NOTE,
    }


def csp_state_ranking_threshold_metadata(state: str | None = None) -> dict:
    """Return the ranking-threshold provenance for one state.

    ``status`` is ``known_estimate`` when RegenAI holds an (unverified)
    threshold for the state and ``not_published`` otherwise. There is no
    numeric fallback: an unknown threshold is reported as ``None`` so the UI
    and the AI prompt can say the cut-off is unknown instead of showing a
    made-up number.
    """
    state_code = (state or "").strip().upper()
    threshold = CSP_STATE_RANKING_THRESHOLDS.get(state_code)
    is_known = threshold is not None
    return {
        "state": state_code or None,
        "value": threshold,
        "status": (
            CSP_RANKING_THRESHOLD_STATUS_KNOWN
            if is_known
            else CSP_RANKING_THRESHOLD_STATUS_UNKNOWN
        ),
        "as_of": CSP_STATE_RANKING_THRESHOLD_RULE.as_of,
        "source_url": CSP_STATE_RANKING_THRESHOLD_RULE.source_url,
        "note": (
            CSP_STATE_RANKING_THRESHOLD_RULE.note
            if is_known
            else CSP_RANKING_THRESHOLD_UNKNOWN_NOTE
        ),
    }


def csp_scoring_rules_metadata(state: str | None = None) -> dict:
    """Return the citation block for score and eligibility responses.

    ``is_estimate`` is True whenever any scoring input is unsourced, so the UI
    can label the score as a RegenAI estimate rather than an NRCS figure.

    Args:
        state: Two-letter state abbreviation the score was evaluated for.
            Omitted (or unknown) means the ranking threshold block reports
            ``not_published``.
    """
    return {
        "is_estimate": bool(CSP_SCORING_ESTIMATED_RULES),
        "model": "RegenAI CART approximation",
        "as_of": CSP_SCORING_MODEL_AS_OF,
        "source_url": None,
        "note": CSP_SCORING_MODEL_NOTE,
        "min_priority_concerns": {
            "value": int(CSP_MIN_PRIORITY_CONCERNS.value or 0),
            "as_of": CSP_MIN_PRIORITY_CONCERNS.as_of,
            "source_url": CSP_MIN_PRIORITY_CONCERNS.source_url,
        },
        "state_ranking_threshold": csp_state_ranking_threshold_metadata(state),
        "estimated_rules": [rule.to_dict() for rule in CSP_SCORING_ESTIMATED_RULES],
    }
