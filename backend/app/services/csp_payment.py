"""
CSP payment estimator for RegenAI.

Implements the two-component CSP payment formula for FY2024+:

    Total Annual Payment = EAP + EnAP

    Existing Activity Payment (EAP):
        Per-acre rate (state + land use) × total eligible acres × number of
        resource concerns currently addressed above the stewardship threshold.

    Enhancement Activity Payment (EnAP):
        100% of estimated practice implementation cost for each enhancement
        activity the producer commits to adopting. When 3 or more enhancement
        activities form a recognized bundle, the rate is 115% (bundle premium).

Payment caps (FY2024 NRCS rules):
    - Minimum annual payment:   $4,000 per contract
    - Maximum annual payment:   $50,000 per contract
    - Maximum contract payment: $200,000 over 5 years

EAP rates are state- and land-use-specific flat rates published in the NRCS
FY2024 CSP payment schedule. Enhancement practice cost estimates are derived
from the NRCS national average cost-per-acre database.
"""

import logging
from datetime import datetime, timezone
from typing import Final

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Payment schedule constants (FY2024)
# ---------------------------------------------------------------------------

_CONTRACT_YEARS: Final[int] = 5
_MIN_ANNUAL_PAYMENT: Final[float] = 4_000.0
_MAX_ANNUAL_PAYMENT: Final[float] = 50_000.0
_MAX_CONTRACT_PAYMENT: Final[float] = 200_000.0

# EAP base rates (USD per acre) by state and land use type.
# Source: NRCS FY2024 CSP Payment Schedules — cropland rates.
_EAP_RATES_CROPLAND: Final[dict[str, float]] = {
    "IL": 18.50,
    "IN": 17.75,
    "IA": 19.25,
    "KS": 15.50,
    "MI": 16.00,
    "MN": 18.00,
    "MO": 16.50,
    "NE": 16.75,
    "ND": 14.25,
    "OH": 17.25,
    "SD": 14.50,
    "WI": 17.00,
    "_default": 16.00,
}

# EAP rates for pasture/hay land (generally lower than cropland)
_EAP_RATES_PASTURE: Final[dict[str, float]] = {
    "IL": 11.00,
    "IN": 10.50,
    "IA": 11.50,
    "KS": 9.25,
    "MI": 9.75,
    "MN": 10.75,
    "MO": 9.75,
    "NE": 10.00,
    "ND": 8.50,
    "OH": 10.25,
    "SD": 8.75,
    "WI": 10.00,
    "_default": 9.75,
}

# EAP rate multiplier per additional resource concern above threshold.
# Base rate covers the first concern; each additional concern adds this fraction.
_EAP_ADDITIONAL_CONCERN_MULTIPLIER: Final[float] = 0.25

# Enhancement activity cost estimates (USD per acre).
# Source: NRCS national average practice cost schedule.
_ENHANCEMENT_COSTS_PER_ACRE: Final[dict[str, float]] = {
    "E327A": 45.00,   # Conservation Cover — establishment
    "E328A": 12.00,   # Resource Conserving Crop Rotation
    "E329A": 8.50,    # No-Till (transition year)
    "E330A": 18.00,   # Contour Farming
    "E340A": 35.00,   # Cover Crop — species mix
    "E380A": 120.00,  # Windbreak/Shelterbelt Establishment (per acre equivalent)
    "E382A": 22.00,   # Fence
    "E393A": 55.00,   # Filter Strip establishment
    "E412A": 95.00,   # Grassed Waterway
    "E484A": 80.00,   # Irrigation Pipeline
    "E528A": 15.00,   # Prescribed Grazing Plan
    "E590A": 10.00,   # Nutrient Management Plan
    "E600A": 180.00,  # Terrace
    "E612A": 140.00,  # Tree/Shrub Establishment
    "E657A": 65.00,   # Micro-Irrigation System
    "E666A": 12.00,   # Irrigation Water Management Plan
}

# Human-readable names for enhancement activities
_ENHANCEMENT_NAMES: Final[dict[str, str]] = {
    "E327A": "Conservation Cover",
    "E328A": "Resource Conserving Crop Rotation",
    "E329A": "Residue and Tillage Management, No-Till",
    "E330A": "Contour Farming",
    "E340A": "Cover Crop — Diverse Species Mix",
    "E380A": "Windbreak/Shelterbelt Establishment",
    "E382A": "Livestock Exclusion Fence",
    "E393A": "Filter Strip",
    "E412A": "Grassed Waterway",
    "E484A": "Irrigation Pipeline",
    "E528A": "Prescribed Grazing",
    "E590A": "Nutrient Management Plan",
    "E600A": "Terrace",
    "E612A": "Tree and Shrub Establishment",
    "E657A": "Irrigation System — Micro-Irrigation",
    "E666A": "Irrigation Water Management",
}

# Resource concerns each enhancement primarily addresses
_ENHANCEMENT_CONCERNS: Final[dict[str, list[str]]] = {
    "E327A": ["plant_condition", "soil_health"],
    "E328A": ["soil_health", "soil_erosion"],
    "E329A": ["soil_health", "soil_erosion", "water_quality"],
    "E330A": ["soil_erosion"],
    "E340A": ["soil_health", "water_quality", "air_quality"],
    "E380A": ["soil_erosion", "air_quality"],
    "E382A": ["animals", "water_quality"],
    "E393A": ["water_quality", "soil_erosion"],
    "E412A": ["water_quality", "soil_erosion"],
    "E484A": ["water_quantity"],
    "E528A": ["plant_condition", "animals"],
    "E590A": ["water_quality"],
    "E600A": ["water_quality", "soil_erosion"],
    "E612A": ["soil_erosion", "air_quality", "plant_condition"],
    "E657A": ["energy", "water_quantity"],
    "E666A": ["water_quantity"],
}

# Minimum number of enhancements required to qualify for the 115% bundle premium.
_BUNDLE_THRESHOLD: Final[int] = 3
_BUNDLE_RATE: Final[float] = 1.15


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _eap_rate(state: str, land_use: str = "cropland") -> float:
    """Look up the base EAP per-acre rate for a state and land use.

    Args:
        state: Two-letter state abbreviation.
        land_use: 'cropland' (default) or 'pasture'.

    Returns:
        EAP rate in USD per acre.
    """
    key = state.upper()
    if land_use == "pasture":
        return _EAP_RATES_PASTURE.get(key, _EAP_RATES_PASTURE["_default"])
    return _EAP_RATES_CROPLAND.get(key, _EAP_RATES_CROPLAND["_default"])


def _calculate_eap(
    total_acres: float,
    concerns_meeting_threshold: int,
    state: str,
    land_use: str = "cropland",
) -> tuple[float, float]:
    """Calculate the annual Existing Activity Payment (EAP).

    Formula (FY2024):
        base_rate = EAP per-acre rate for state/land-use
        effective_rate = base_rate × (1 + (concerns - 1) × 0.25)
        EAP = effective_rate × total_acres

    The 25% increment per additional concern above the first reflects NRCS
    policy that farms addressing more resource concerns earn a proportionally
    higher EAP.

    Args:
        total_acres: Total eligible cropland acres in the operation.
        concerns_meeting_threshold: Number of priority resource concerns
            currently addressed above the stewardship threshold.
        state: Two-letter state abbreviation.
        land_use: 'cropland' or 'pasture'.

    Returns:
        Tuple of (annual_eap, effective_rate_per_acre).
    """
    if concerns_meeting_threshold < 1:
        return 0.0, 0.0

    base_rate = _eap_rate(state, land_use)
    # Each concern beyond the first adds 25% of the base rate
    extra_concerns = max(0, concerns_meeting_threshold - 1)
    effective_rate = base_rate * (1.0 + extra_concerns * _EAP_ADDITIONAL_CONCERN_MULTIPLIER)
    annual_eap = round(effective_rate * total_acres, 2)
    return annual_eap, round(effective_rate, 4)


def _calculate_enap(
    enhancement_codes: list[str],
    total_acres: float,
) -> tuple[float, bool]:
    """Calculate the annual Enhancement Activity Payment (EnAP).

    Formula:
        cost_per_acre = sum of per-acre costs for each selected enhancement
        is_bundle = len(enhancements) >= 3
        payment_rate = 1.15 if is_bundle else 1.00
        EnAP = cost_per_acre × total_acres × payment_rate

    Args:
        enhancement_codes: List of E-codes for enhancements the producer
            commits to adopting.
        total_acres: Total eligible acres.

    Returns:
        Tuple of (annual_enap, is_bundle).
    """
    if not enhancement_codes:
        return 0.0, False

    total_cost_per_acre = sum(
        _ENHANCEMENT_COSTS_PER_ACRE.get(code, 0.0) for code in enhancement_codes
    )
    is_bundle = len(enhancement_codes) >= _BUNDLE_THRESHOLD
    rate = _BUNDLE_RATE if is_bundle else 1.0
    annual_enap = round(total_cost_per_acre * total_acres * rate, 2)
    return annual_enap, is_bundle


def _apply_payment_caps(annual_payment: float) -> tuple[float, float, bool]:
    """Enforce NRCS annual and contract payment caps.

    Rules:
        - Minimum annual payment: $4,000 (enforced only if eligible)
        - Maximum annual payment: $50,000
        - Maximum contract total: $200,000 over 5 years

    The annual cap ($50k) and contract cap ($200k) are applied independently.
    A farmer can receive $50k in year 1 but the 5-year total cannot exceed $200k.

    Returns:
        Tuple of (capped_annual, five_year_total, was_capped).
    """
    capped = annual_payment
    was_capped = False

    if capped > _MAX_ANNUAL_PAYMENT:
        capped = _MAX_ANNUAL_PAYMENT
        was_capped = True

    # Apply minimum floor only if some payment is due
    if 0 < capped < _MIN_ANNUAL_PAYMENT:
        capped = _MIN_ANNUAL_PAYMENT

    # 5-year total is capped independently at $200k
    five_year = capped * _CONTRACT_YEARS
    if five_year > _MAX_CONTRACT_PAYMENT:
        five_year = _MAX_CONTRACT_PAYMENT
        was_capped = True

    return round(capped, 2), round(five_year, 2), was_capped


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def estimate_csp_payments(farm_id: str, supabase) -> dict:
    """Estimate annual and 5-year CSP payments for a farm.

    Algorithm:
        1. Fetch farm (state, total_acres).
        2. Fetch all fields for per-field breakdown.
        3. Fetch most-recent CSP assessment for concerns_meeting_threshold.
           If no cached assessment exists, run scoring inline.
        4. Determine applicable enhancement activities from the
           csp_enhancement_activities reference table and field practices.
        5. Calculate EAP and EnAP with NRCS formula.
        6. Apply annual and 5-year payment caps.
        7. Return structured payment estimate.

    Args:
        farm_id: UUID of the farm to estimate payments for.
        supabase: Authenticated Supabase client (respects RLS).

    Returns:
        A dict conforming to CSPPaymentEstimate schema fields.

    Raises:
        ValueError: If the farm cannot be found.
    """
    # ------------------------------------------------------------------
    # 1. Fetch farm record
    # ------------------------------------------------------------------
    try:
        farm_result = (
            supabase.table("farms")
            .select("id, state, total_acres")
            .eq("id", farm_id)
            .single()
            .execute()
        )
        farm: dict = farm_result.data or {}
    except Exception:
        logger.exception("csp_payment: failed to fetch farm=%s", farm_id)
        raise ValueError(f"Could not retrieve farm {farm_id}")

    if not farm:
        raise ValueError(f"Farm {farm_id} not found")

    state: str = farm.get("state", "").upper()
    total_acres: float = float(farm.get("total_acres") or 0.0)

    # ------------------------------------------------------------------
    # 2. Fetch fields for per-field breakdown
    # ------------------------------------------------------------------
    try:
        fields_result = (
            supabase.table("fields")
            .select("id, name, acres, crop_type, practices")
            .eq("farm_id", farm_id)
            .execute()
        )
        fields: list[dict] = fields_result.data or []
    except Exception:
        logger.exception("csp_payment: failed to fetch fields for farm=%s", farm_id)
        fields = []

    field_ids: list[str] = [f["id"] for f in fields]

    # ------------------------------------------------------------------
    # 3. Get concerns_meeting_threshold from cached assessment or scoring
    # ------------------------------------------------------------------
    concerns_meeting_threshold: int = 0

    try:
        assessment_result = (
            supabase.table("csp_eligibility_assessments")
            .select("rc_count_above_threshold, stewardship_score")
            .eq("farm_id", farm_id)
            .single()
            .execute()
        )
        if assessment_result.data:
            concerns_meeting_threshold = int(
                assessment_result.data.get("rc_count_above_threshold") or 0
            )
    except Exception:
        logger.warning(
            "csp_payment: no cached assessment for farm=%s — running scoring inline",
            farm_id,
        )
        # Run scoring inline if no cached assessment
        try:
            from app.services.csp_scoring import calculate_stewardship_score

            score_data = await calculate_stewardship_score(farm_id, supabase)
            concerns_meeting_threshold = sum(
                1
                for c in score_data["resource_concern_scores"]
                if c["meets_threshold"]
            )
        except Exception:
            logger.exception(
                "csp_payment: inline scoring failed for farm=%s", farm_id
            )
            concerns_meeting_threshold = 0

    # ------------------------------------------------------------------
    # 4. Determine applicable enhancement activities
    #    Pull recommended enhancements from enhancement reference table
    # ------------------------------------------------------------------
    enhancement_codes: list[str] = []

    try:
        enh_result = (
            supabase.table("csp_enhancement_activities")
            .select("code, name, estimated_cost_per_acre")
            .eq("land_use", "cropland")
            .execute()
        )
        enh_rows: list[dict] = enh_result.data or []
    except Exception:
        logger.warning(
            "csp_payment: could not fetch enhancement activities for farm=%s — using defaults",
            farm_id,
        )
        enh_rows = []

    # Build enhancement list: use DB entries if available, else use our local
    # cost schedule keys. Limit to top 5 for a realistic enhancement scenario.
    if enh_rows:
        # Pick the first 5 from the reference table
        enhancement_codes = [row["code"] for row in enh_rows[:5]]
    else:
        # Fallback: use the 3 highest-value enhancements from our cost table
        enhancement_codes = ["E340A", "E590A", "E328A"]

    # ------------------------------------------------------------------
    # 5. Calculate EAP
    # ------------------------------------------------------------------
    eap_annual, eap_rate_per_acre = _calculate_eap(
        total_acres=total_acres,
        concerns_meeting_threshold=concerns_meeting_threshold,
        state=state,
        land_use="cropland",
    )

    # ------------------------------------------------------------------
    # 6. Calculate EnAP
    # ------------------------------------------------------------------
    enap_annual, is_bundle = _calculate_enap(
        enhancement_codes=enhancement_codes,
        total_acres=total_acres,
    )

    # ------------------------------------------------------------------
    # 7. Apply payment caps
    # ------------------------------------------------------------------
    raw_annual_total = eap_annual + enap_annual
    annual_total, five_year_total, was_capped = _apply_payment_caps(raw_annual_total)

    # Pro-rate EAP and EnAP if cap was applied
    if was_capped and raw_annual_total > 0:
        cap_ratio = annual_total / raw_annual_total
        eap_annual = round(eap_annual * cap_ratio, 2)
        enap_annual = round(enap_annual * cap_ratio, 2)

    # ------------------------------------------------------------------
    # 8. Build per-field breakdown
    # ------------------------------------------------------------------
    field_breakdown: list[dict] = []
    for field in fields:
        field_acres = float(field.get("acres") or 0.0)
        if total_acres > 0:
            field_share = field_acres / total_acres
        else:
            field_share = 0.0

        field_breakdown.append(
            {
                "field_id": field["id"],
                "field_name": field.get("name", ""),
                "acres": field_acres,
                "eap_annual": round(eap_annual * field_share, 2),
                "enap_annual": round(enap_annual * field_share, 2),
                "total_annual": round(annual_total * field_share, 2),
            }
        )

    logger.info(
        "csp_payment: farm=%s state=%s acres=%.1f concerns=%d "
        "eap=%.2f enap=%.2f total=%.2f capped=%s",
        farm_id,
        state,
        total_acres,
        concerns_meeting_threshold,
        eap_annual,
        enap_annual,
        annual_total,
        was_capped,
    )

    now = datetime.now(tz=timezone.utc).isoformat()

    return {
        "farm_id": farm_id,
        "eligible_acres": total_acres,
        "eap_annual": eap_annual,
        "eap_rate_per_acre": eap_rate_per_acre,
        "resource_concerns_addressed": concerns_meeting_threshold,
        "enap_annual": enap_annual,
        "enap_is_bundle": is_bundle,
        "enhancement_codes_included": enhancement_codes,
        "total_annual_payment": annual_total,
        "total_5year_payment": five_year_total,
        "payment_capped": was_capped,
        "field_breakdown": field_breakdown,
        "state": state,
        "estimated_at": now,
    }


async def get_recommended_enhancements(farm_id: str, supabase) -> list[dict]:
    """Return scored and ranked CSP enhancement activity recommendations.

    Fetches the enhancement activity reference table, filters to cropland
    activities, and scores each by how well it would close the farm's current
    stewardship gaps — favouring activities that address concerns currently
    below threshold.

    Args:
        farm_id: UUID of the farm.
        supabase: Authenticated Supabase client.

    Returns:
        List of enhancement dicts sorted by priority score descending.

    Raises:
        ValueError: If the farm cannot be found.
    """
    # Fetch farm for acres
    try:
        farm_result = (
            supabase.table("farms")
            .select("id, state, total_acres")
            .eq("id", farm_id)
            .single()
            .execute()
        )
        farm: dict = farm_result.data or {}
    except Exception:
        raise ValueError(f"Could not retrieve farm {farm_id}")

    if not farm:
        raise ValueError(f"Farm {farm_id} not found")

    total_acres: float = float(farm.get("total_acres") or 0.0)

    # Identify concerns below threshold from cached or fresh assessment
    below_threshold_concerns: set[str] = set()
    try:
        assessment_result = (
            supabase.table("csp_eligibility_assessments")
            .select("resource_concerns_met")
            .eq("farm_id", farm_id)
            .single()
            .execute()
        )
        if assessment_result.data:
            score_bd = assessment_result.data.get("resource_concerns_met") or {}
            for concern in score_bd.get("resource_concern_scores", []):
                if not concern.get("meets_threshold", False):
                    below_threshold_concerns.add(concern["concern_id"])
    except Exception:
        logger.warning(
            "csp_payment: no cached assessment for enhancements farm=%s", farm_id
        )
        # Default: assume all concerns need work
        below_threshold_concerns = set(_ENHANCEMENT_CONCERNS.keys())

    # Fetch reference table
    try:
        enh_result = (
            supabase.table("csp_enhancement_activities")
            .select("*")
            .eq("land_use", "cropland")
            .execute()
        )
        enh_rows: list[dict] = enh_result.data or []
    except Exception:
        logger.warning(
            "csp_payment: enhancement reference table unavailable for farm=%s", farm_id
        )
        enh_rows = []

    # If no DB entries, build from local constants
    if not enh_rows:
        enh_rows = [
            {
                "code": code,
                "name": _ENHANCEMENT_NAMES.get(code, code),
                "category": _ENHANCEMENT_CONCERNS.get(code, ["general"])[0],
                "land_use": "cropland",
                "description": f"Enhancement activity {code}",
                "estimated_cost_per_acre": _ENHANCEMENT_COSTS_PER_ACRE.get(code, 15.0),
            }
            for code in _ENHANCEMENT_COSTS_PER_ACRE
        ]

    # Score each enhancement
    results: list[dict] = []
    for row in enh_rows:
        code: str = row.get("code", "")
        concerns_addressed = _ENHANCEMENT_CONCERNS.get(code, [])
        # Priority score: +2 for each below-threshold concern addressed, +1 for others
        priority_score: float = sum(
            2.0 if c in below_threshold_concerns else 1.0
            for c in concerns_addressed
        )

        cost_per_acre = float(
            row.get("estimated_cost_per_acre")
            or _ENHANCEMENT_COSTS_PER_ACRE.get(code, 15.0)
        )
        is_bundle_eligible = len(concerns_addressed) >= 2

        results.append(
            {
                "code": code,
                "name": row.get("name", _ENHANCEMENT_NAMES.get(code, code)),
                "category": row.get("category", ""),
                "land_use": row.get("land_use", "cropland"),
                "description": row.get("description", ""),
                "estimated_cost_per_acre": cost_per_acre,
                "payment_rate_pct": 115.0 if is_bundle_eligible else 100.0,
                "estimated_annual_payment": round(cost_per_acre * total_acres, 2),
                "applicable_acres": total_acres,
                "resource_concerns_addressed": concerns_addressed,
                "priority_score": priority_score,
                "is_bundle_eligible": is_bundle_eligible,
            }
        )

    results.sort(key=lambda x: x["priority_score"], reverse=True)
    return results
