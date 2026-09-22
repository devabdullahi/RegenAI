"""
CSP payment estimator for RegenAI (FY2026 NRCS rules).

Implements the FY2026 CSP payment structure described in NRCS National
Bulletin 440-26-2 (2025-12-17):

    Annual estimate = Existing Activity Payment (EAP) + activity payments

    Existing Activity Payment (EAP):
        A fixed amount per contract each year for new contracts starting in
        FY2026 (``CSP_EXISTING_ACTIVITY_PAYMENT``). It is not a floor on the
        total payment and does not scale with acres. It is only estimated when
        the farm can hold a contract (meets the stewardship threshold on the
        minimum number of priority resource concerns).

    Activity payments:
        Per-acre estimates for the conservation activities the producer adopts.
        FY2026 no longer uses unique "E" enhancement codes or bundles, so
        activities are keyed by NRCS conservation practice standard code.
        Rates are pre-FY2026 estimates pending the FY2026 state payment
        schedule (see ``program_rules``).

Limits:
    - Annual payment limitation: ``CSP_ANNUAL_PAYMENT_LIMIT`` (none in FY2026).
    - Contract limit by contract fiscal year and operation type
      (``csp_contract_limit``). The 5-year total is capped at that limit.

All rule values, the activity catalog and their citations live in
``app.services.program_rules``.
"""

import logging
from datetime import datetime, timezone
from typing import Final

from postgrest.exceptions import APIError

from app.services.csp_eligibility import fetch_latest_assessment
from app.services.csp_scoring import calculate_stewardship_score
from app.services.program_rules import (
    CSP_ACTIVITY_RATE_BASIS,
    CSP_ANNUAL_PAYMENT_LIMIT,
    CSP_CONTRACT_YEARS,
    CSP_DEFAULT_CONTRACT_FY,
    CSP_EXISTING_ACTIVITY_PAYMENT,
    CSP_HIGHER_PAYMENT_CATEGORIES,
    CSP_MIN_PRIORITY_CONCERNS,
    CSP_PRACTICE_CATALOG,
    CspPractice,
    csp_contract_limit,
    csp_rules_metadata,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule constants (sourced from program_rules)
# ---------------------------------------------------------------------------

_CONTRACT_YEARS: Final[int] = int(CSP_CONTRACT_YEARS.value)
_EXISTING_ACTIVITY_PAYMENT: Final[float] = float(CSP_EXISTING_ACTIVITY_PAYMENT.value or 0.0)
_ANNUAL_PAYMENT_LIMIT: Final[float | None] = CSP_ANNUAL_PAYMENT_LIMIT.value
_MIN_CONCERNS_FOR_CONTRACT: Final[int] = int(CSP_MIN_PRIORITY_CONCERNS.value or 0)

# Priority weights used to rank activities: a concern the farm has not yet met
# counts double, because closing it moves the farm toward eligibility.
_UNMET_CONCERN_WEIGHT: Final[float] = 2.0
_MET_CONCERN_WEIGHT: Final[float] = 1.0

#: CSP activities — catalog entries that carry a payment estimate.
_CSP_ACTIVITIES: Final[dict[str, CspPractice]] = {
    code: practice
    for code, practice in CSP_PRACTICE_CATALOG.items()
    if practice.is_csp_activity
}

# Default activity scenario used for the annual estimate when the producer has
# not selected activities: cover crop, nutrient management, and RCCR.
_DEFAULT_ACTIVITY_CODES: Final[list[str]] = ["340", "590", "328-RCCR"]

# Map retired E-codes to the FY2026 activity that replaces them.
_LEGACY_CODE_MAP: Final[dict[str, str]] = {
    legacy: code
    for code, activity in _CSP_ACTIVITIES.items()
    for legacy in activity.legacy_codes
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    """Current UTC time (isolated so tests can pin the date)."""
    return datetime.now(tz=timezone.utc)


def normalize_activity_code(code: str) -> str | None:
    """Return the FY2026 activity code for a code or retired E-code.

    Args:
        code: A current activity code (e.g. '340') or retired E-code ('E340A').

    Returns:
        The current activity code, or None if the code is unknown.
    """
    if code in _CSP_ACTIVITIES:
        return code
    return _LEGACY_CODE_MAP.get(code.upper())


def _activity_view(code: str, total_acres: float) -> dict:
    """Build the public dict for one catalog activity at a farm's acreage."""
    activity = _CSP_ACTIVITIES[code]
    rate = float(activity.estimated_rate_per_acre or 0.0)
    category_key = activity.higher_payment_category
    return {
        "code": code,
        "practice_standard_code": activity.practice_standard_code,
        "name": activity.name,
        "higher_payment": category_key is not None,
        "higher_payment_category": (
            CSP_HIGHER_PAYMENT_CATEGORIES[category_key] if category_key else None
        ),
        "estimated_rate_per_acre": rate,
        "rate_is_estimate": True,
        "acres": total_acres,
        "estimated_annual_payment": round(rate * total_acres, 2),
    }


def _calculate_eap(concerns_meeting_threshold: int) -> float:
    """Return the annual Existing Activity Payment for a contract.

    FY2026 rule: a fixed per-contract amount each year
    (``CSP_EXISTING_ACTIVITY_PAYMENT``). A contract requires the
    farm to meet the stewardship threshold on the minimum number of priority
    resource concerns, so no EAP is estimated below that.
    """
    if concerns_meeting_threshold < _MIN_CONCERNS_FOR_CONTRACT:
        return 0.0
    return _EXISTING_ACTIVITY_PAYMENT


def _calculate_activity_payments(
    activity_codes: list[str],
    total_acres: float,
) -> tuple[float, list[dict]]:
    """Sum estimated per-acre activity payments.

    No bundle premium is applied — bundles are not offered in FY2026.
    Unknown codes contribute nothing.

    Returns:
        Tuple of (annual_activity_payment, per-activity breakdown).
    """
    breakdown: list[dict] = []
    seen: set[str] = set()
    for raw in activity_codes:
        code = normalize_activity_code(raw)
        if code is None or code in seen:
            continue
        seen.add(code)
        breakdown.append(_activity_view(code, total_acres))
    total = round(sum(item["estimated_annual_payment"] for item in breakdown), 2)
    return total, breakdown


def _apply_contract_limit(
    annual_payment: float,
    contract_limit: float,
) -> tuple[float, float, bool]:
    """Apply FY2026 limits to an annual payment estimate.

    - No annual payment limit: the annual estimate is returned unchanged.
    - The 5-year contract total is capped at ``contract_limit``.

    Returns:
        Tuple of (annual_payment, five_year_total, contract_limit_applied).
    """
    annual = round(max(0.0, annual_payment), 2)
    five_year = annual * _CONTRACT_YEARS
    capped = five_year > contract_limit
    if capped:
        five_year = contract_limit
    return annual, round(five_year, 2), capped


def _fetch_farm(farm_id: str, supabase) -> dict:
    """Return the farm row or raise ValueError if it is missing or hidden."""
    try:
        farm_result = (
            supabase.table("farms")
            .select("id, state, total_acres")
            .eq("id", farm_id)
            .single()
            .execute()
        )
    except APIError as exc:
        # .single() raises when zero rows match (missing or hidden by RLS).
        logger.warning("csp_payment: farm lookup failed farm=%s error=%s", farm_id, exc)
        raise ValueError(f"Could not retrieve farm {farm_id}") from exc

    farm: dict = farm_result.data or {}
    if not farm:
        raise ValueError(f"Farm {farm_id} not found")
    return farm


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

async def estimate_csp_payments(
    farm_id: str,
    supabase,
    contract_fiscal_year: int = CSP_DEFAULT_CONTRACT_FY,
    joint_operation: bool = False,
) -> dict:
    """Estimate annual and 5-year CSP payments for a farm.

    Algorithm:
        1. Fetch farm (state, total_acres) and fields.
        2. Read concerns meeting threshold from the latest persisted
           assessment, or run scoring inline when none exists.
        3. EAP per contract per year (if the farm can hold a contract).
        4. Activity payments = sum of estimated per-acre rates x acres.
        5. Annual estimate = EAP + activity payments (no annual limit).
        6. 5-year total capped at the contract limit for the contract's
           fiscal year and operation type.

    Args:
        farm_id: UUID string of the farm to estimate payments for.
        supabase: Authenticated Supabase client (respects RLS).
        contract_fiscal_year: Fiscal year the contract is obligated in
            (default: FY2026, i.e. a new contract).
        joint_operation: True for a joint operation contract.

    Returns:
        A dict conforming to the CSPPaymentEstimate schema.

    Raises:
        ValueError: If the farm cannot be found.
    """
    # 1. Farm
    farm = _fetch_farm(farm_id, supabase)
    state: str = (farm.get("state") or "").upper()
    total_acres: float = float(farm.get("total_acres") or 0.0)

    # Fields are only used for the per-field breakdown, so a failure degrades
    # to an empty breakdown instead of failing the estimate.
    fields: list[dict] = []
    try:
        fields_result = (
            supabase.table("fields")
            .select("id, name, acres, crop_type, practices")
            .eq("farm_id", farm_id)
            .execute()
        )
        fields = fields_result.data or []
    except APIError as exc:
        logger.warning(
            "csp_payment: fields unavailable for breakdown farm=%s error=%s", farm_id, exc
        )

    # 2. Concerns meeting threshold
    assessment: dict | None = None
    try:
        assessment = fetch_latest_assessment(
            supabase, farm_id, "rc_count_above_threshold, stewardship_score"
        )
    except APIError as exc:
        logger.warning(
            "csp_payment: could not read persisted assessment farm=%s error=%s",
            farm_id,
            exc,
        )

    if assessment is not None:
        concerns_meeting_threshold = int(assessment.get("rc_count_above_threshold") or 0)
    else:
        logger.info(
            "csp_payment: no persisted assessment for farm=%s — running scoring inline",
            farm_id,
        )
        score_data = await calculate_stewardship_score(farm_id, supabase)
        concerns_meeting_threshold = sum(
            1 for c in score_data["resource_concern_scores"] if c["meets_threshold"]
        )

    # 3-4. EAP and activity payments
    eap_annual = _calculate_eap(concerns_meeting_threshold)
    activity_payment_annual, activities = _calculate_activity_payments(
        _DEFAULT_ACTIVITY_CODES, total_acres
    )

    # 5-6. Limits
    limit = csp_contract_limit(contract_fiscal_year, joint_operation)
    annual_total, five_year_total, limit_applied = _apply_contract_limit(
        eap_annual + activity_payment_annual, limit["amount"]
    )

    # Per-field breakdown (proportional to acres)
    field_breakdown: list[dict] = []
    for field in fields:
        field_acres = float(field.get("acres") or 0.0)
        share = field_acres / total_acres if total_acres > 0 else 0.0
        field_breakdown.append(
            {
                "field_id": str(field["id"]),
                "field_name": field.get("name") or "",
                "acres": field_acres,
                "eap_annual": round(eap_annual * share, 2),
                "activity_payment_annual": round(activity_payment_annual * share, 2),
                "total_annual": round(annual_total * share, 2),
            }
        )

    logger.info(
        "csp_payment: farm=%s state=%s acres=%.1f concerns=%d eap=%.2f "
        "activities=%.2f total=%.2f contract_fy=%d joint=%s limit_applied=%s",
        farm_id,
        state,
        total_acres,
        concerns_meeting_threshold,
        eap_annual,
        activity_payment_annual,
        annual_total,
        contract_fiscal_year,
        joint_operation,
        limit_applied,
    )

    return {
        "farm_id": farm_id,
        "eligible_acres": total_acres,
        "resource_concerns_addressed": concerns_meeting_threshold,
        "eap_annual": eap_annual,
        "activity_payment_annual": activity_payment_annual,
        "activities_included": activities,
        "total_annual_payment": annual_total,
        "total_5year_payment": five_year_total,
        "contract_years": _CONTRACT_YEARS,
        "contract_fiscal_year": contract_fiscal_year,
        "joint_operation": joint_operation,
        "contract_limit": limit,
        "annual_payment_limit": _ANNUAL_PAYMENT_LIMIT,
        "payment_capped": limit_applied,
        "field_breakdown": field_breakdown,
        "state": state,
        "rules": csp_rules_metadata(contract_fiscal_year, joint_operation),
        "estimated_at": _utcnow().isoformat(),
    }


async def get_recommended_enhancements(farm_id: str, supabase) -> list[dict]:
    """Return scored and ranked CSP activity recommendations for a farm.

    Scores each activity in the FY2026 catalog by how well it closes the
    farm's current stewardship gaps. Descriptions from the
    ``csp_enhancement_activities`` reference table are used when an active row
    exists for the activity code; retired E-code rows are ignored.

    Args:
        farm_id: UUID string of the farm.
        supabase: Authenticated Supabase client.

    Returns:
        List of activity dicts sorted by priority score descending.

    Raises:
        ValueError: If the farm cannot be found.
    """
    farm = _fetch_farm(farm_id, supabase)
    total_acres: float = float(farm.get("total_acres") or 0.0)

    # Concerns below threshold. Without a persisted assessment every concern
    # is treated as unmet, so ranking falls back to breadth of coverage.
    all_concerns = {
        concern
        for activity in _CSP_ACTIVITIES.values()
        for concern in activity.resource_concerns
    }
    below_threshold_concerns: set[str] = set(all_concerns)
    try:
        assessment = fetch_latest_assessment(supabase, farm_id, "resource_concerns_met")
    except APIError as exc:
        logger.warning(
            "csp_payment: could not read persisted assessment for activities "
            "farm=%s error=%s",
            farm_id,
            exc,
        )
        assessment = None

    if assessment:
        score_breakdown = assessment.get("resource_concerns_met") or {}
        if isinstance(score_breakdown, dict):
            below_threshold_concerns = {
                concern["concern_id"]
                for concern in score_breakdown.get("resource_concern_scores", [])
                if not concern.get("meets_threshold", False)
            }

    # Optional descriptive overrides from the reference table
    db_rows: dict[str, dict] = {}
    try:
        rows_result = (
            supabase.table("csp_enhancement_activities")
            .select("code, name, description, implementation_notes, active")
            .eq("active", True)
            .execute()
        )
        for row in rows_result.data or []:
            code = row.get("code")
            if code in _CSP_ACTIVITIES:
                db_rows[code] = row
    except APIError as exc:
        logger.warning(
            "csp_payment: activity reference table unavailable farm=%s error=%s",
            farm_id,
            exc,
        )

    results: list[dict] = []
    for code, activity in _CSP_ACTIVITIES.items():
        concerns = activity.resource_concerns
        priority_score = sum(
            _UNMET_CONCERN_WEIGHT if c in below_threshold_concerns else _MET_CONCERN_WEIGHT
            for c in concerns
        )
        view = _activity_view(code, total_acres)
        row = db_rows.get(code, {})
        results.append(
            {
                "code": code,
                "practice_standard_code": activity.practice_standard_code,
                "name": row.get("name") or activity.name,
                "category": activity.category,
                "land_use": "cropland",
                "description": row.get("description") or activity.description,
                "implementation_notes": row.get("implementation_notes") or "",
                "estimated_rate_per_acre": view["estimated_rate_per_acre"],
                "rate_is_estimate": True,
                "rate_basis": CSP_ACTIVITY_RATE_BASIS,
                "estimated_annual_payment": view["estimated_annual_payment"],
                "applicable_acres": total_acres,
                "resource_concerns_addressed": list(concerns),
                "priority_score": priority_score,
                "higher_payment": view["higher_payment"],
                "higher_payment_category": view["higher_payment_category"],
            }
        )

    results.sort(key=lambda x: x["priority_score"], reverse=True)
    return results
