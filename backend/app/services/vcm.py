"""
VCM (Voluntary Carbon Market) credit estimator for RegenAI.

Implements a simplified Soil Carbon Protocol that translates acted
conservation practice recommendations into estimated carbon credit units
(tonnes CO2e per acre per year). Results are persisted to the
credit_eligibility table with program="VCM" and include a per-field
breakdown suitable for downstream PDF report generation.

Protocol rules (hardcoded per execution brief):
    - Cover Crop (340):            0.5 – 1.2 credits/acre/year
    - No-Till (329):               0.3 – 0.8 credits/acre/year
    - Conservation Rotation (328): 0.2 – 0.5 credits/acre/year

The range within each band is resolved by soil organic matter (SOM):
    - SOM >= 3.0 %  → upper bound of range
    - SOM 1.5–2.9 % → midpoint of range
    - SOM < 1.5 %   → lower bound of range

Fields without a soil profile use the lower bound (conservative estimate).
"""

import logging
from datetime import datetime, timezone
from typing import NamedTuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------

class _CreditBand(NamedTuple):
    low: float
    high: float


# Mapping from EQIP practice code → Soil Carbon Protocol credit band
_PROTOCOL_PRACTICES: dict[str, _CreditBand] = {
    "340": _CreditBand(low=0.5, high=1.2),  # Cover Crop
    "329": _CreditBand(low=0.3, high=0.8),  # No-Till
    "328": _CreditBand(low=0.2, high=0.5),  # Conservation Crop Rotation
}

_PRACTICE_NAMES: dict[str, str] = {
    "340": "Cover Crop",
    "329": "Residue and Tillage Management, No-Till",
    "328": "Conservation Crop Rotation",
}

# SOM thresholds for credit tier selection
_SOM_HIGH_THRESHOLD = 3.0   # % — qualifies for upper bound
_SOM_LOW_THRESHOLD = 1.5    # % — below this uses lower bound


def _credits_per_acre(practice_code: str, organic_matter_pct: float | None) -> float:
    """Resolve a single credit rate for a practice code and SOM value.

    Args:
        practice_code: EQIP practice code (must be in _PROTOCOL_PRACTICES).
        organic_matter_pct: Soil organic matter percentage, or None if unknown.

    Returns:
        Estimated credits per acre per year as a float.
    """
    band = _PROTOCOL_PRACTICES[practice_code]
    som = organic_matter_pct if organic_matter_pct is not None else 0.0

    if som >= _SOM_HIGH_THRESHOLD:
        return band.high
    if som >= _SOM_LOW_THRESHOLD:
        return round((band.low + band.high) / 2, 3)
    return band.low


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def estimate_vcm_credits(farm_id: str, supabase) -> dict:
    """Estimate Soil Carbon Protocol VCM credits for a farm.

    Algorithm:
        1. Fetch all fields for the farm (need acres).
        2. Fetch acted recommendations that match protocol practice codes.
        3. Fetch soil profiles to resolve SOM tiers per field.
        4. For each (field, practice) pair, compute:
               estimated_credits = acres × credits_per_acre(practice, som)
        5. Aggregate into a per-field breakdown and a farm total.
        6. Upsert result into credit_eligibility (program="VCM").

    Args:
        farm_id: UUID of the farm to evaluate.
        supabase: Authenticated Supabase client (respects RLS).

    Returns:
        A dict with keys: farm_id, program, status, practices_documented,
        notes, updated_at, plus extra keys estimated_total_credits and
        field_breakdown for the report endpoint (these are embedded in notes
        as JSON-serialisable data and also returned at the top level).

    Raises:
        ValueError: If the farm has no accessible fields.
    """
    # ------------------------------------------------------------------
    # 1. Fetch fields
    # ------------------------------------------------------------------
    try:
        fields_result = (
            supabase.table("fields")
            .select("id, name, acres")
            .eq("farm_id", farm_id)
            .execute()
        )
        fields: list[dict] = fields_result.data or []
    except Exception:
        logger.exception("vcm: failed to fetch fields for farm=%s", farm_id)
        raise ValueError(f"Could not retrieve fields for farm {farm_id}")

    field_ids: list[str] = [f["id"] for f in fields]
    field_map: dict[str, dict] = {f["id"]: f for f in fields}

    if not field_ids:
        return await _upsert_result(
            farm_id=farm_id,
            status="not_eligible",
            practices_documented=[],
            notes="No fields registered. Add fields to estimate VCM credits.",
            estimated_total_credits=0.0,
            field_breakdown=[],
            supabase=supabase,
        )

    # ------------------------------------------------------------------
    # 2. Fetch acted recommendations that match protocol codes
    # ------------------------------------------------------------------
    protocol_codes = list(_PROTOCOL_PRACTICES.keys())

    try:
        recs_result = (
            supabase.table("recommendations")
            .select("field_id, practice_code, title")
            .in_("field_id", field_ids)
            .eq("status", "acted")
            .in_("practice_code", protocol_codes)
            .execute()
        )
        acted_recs: list[dict] = recs_result.data or []
    except Exception:
        logger.exception(
            "vcm: failed to fetch acted recommendations for farm=%s", farm_id
        )
        acted_recs = []

    if not acted_recs:
        return await _upsert_result(
            farm_id=farm_id,
            status="not_eligible",
            practices_documented=[],
            notes=(
                "No acted recommendations match the Soil Carbon Protocol practices "
                f"({', '.join(protocol_codes)}). Act on at least one qualifying "
                "recommendation to generate a VCM credit estimate."
            ),
            estimated_total_credits=0.0,
            field_breakdown=[],
            supabase=supabase,
        )

    # ------------------------------------------------------------------
    # 3. Fetch soil profiles (most recent per field for SOM lookup)
    # ------------------------------------------------------------------
    som_by_field: dict[str, float | None] = {fid: None for fid in field_ids}

    try:
        soil_result = (
            supabase.table("soil_profiles")
            .select("field_id, organic_matter_pct")
            .in_("field_id", field_ids)
            .order("fetched_at", desc=True)
            .execute()
        )
        seen_fields: set[str] = set()
        for row in soil_result.data or []:
            fid = row["field_id"]
            if fid not in seen_fields:
                som_by_field[fid] = row.get("organic_matter_pct")
                seen_fields.add(fid)
    except Exception:
        logger.exception("vcm: failed to fetch soil profiles for farm=%s", farm_id)
        # Proceed with None SOM values → conservative (low-bound) estimates

    # ------------------------------------------------------------------
    # 4. Compute per-(field, practice) credit estimates
    # ------------------------------------------------------------------
    # De-duplicate: one entry per unique (field_id, practice_code)
    seen_pairs: set[tuple[str, str]] = set()
    line_items: list[dict] = []

    for rec in acted_recs:
        fid = rec["field_id"]
        code = rec["practice_code"]
        pair = (fid, code)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        acres: float = field_map[fid].get("acres") or 0.0
        som: float | None = som_by_field.get(fid)
        rate: float = _credits_per_acre(code, som)
        credits: float = round(acres * rate, 3)

        line_items.append(
            {
                "field_id": fid,
                "field_name": field_map[fid].get("name", ""),
                "acres": acres,
                "practice_code": code,
                "practice_name": _PRACTICE_NAMES.get(code, code),
                "som_pct": som,
                "rate_credits_per_acre": rate,
                "estimated_credits": credits,
            }
        )

    # ------------------------------------------------------------------
    # 5. Aggregate into per-field breakdown and farm total
    # ------------------------------------------------------------------
    # Group line items by field for the breakdown structure
    field_credits: dict[str, dict] = {}
    for item in line_items:
        fid = item["field_id"]
        if fid not in field_credits:
            field_credits[fid] = {
                "field_id": fid,
                "field_name": item["field_name"],
                "acres": item["acres"],
                "practices": [],
                "field_total_credits": 0.0,
            }
        field_credits[fid]["practices"].append(
            {
                "practice_code": item["practice_code"],
                "practice_name": item["practice_name"],
                "rate_credits_per_acre": item["rate_credits_per_acre"],
                "estimated_credits": item["estimated_credits"],
            }
        )
        field_credits[fid]["field_total_credits"] = round(
            field_credits[fid]["field_total_credits"] + item["estimated_credits"], 3
        )

    field_breakdown: list[dict] = list(field_credits.values())
    estimated_total: float = round(
        sum(fc["field_total_credits"] for fc in field_breakdown), 3
    )
    practices_documented: list[str] = sorted({item["practice_code"] for item in line_items})

    # ------------------------------------------------------------------
    # 6. Compose notes and determine status
    # ------------------------------------------------------------------
    status = "eligible" if estimated_total > 0 else "pending_review"

    fields_with_credits = len(field_breakdown)
    practice_summary = ", ".join(
        f"{code} ({_PRACTICE_NAMES.get(code, code)})"
        for code in practices_documented
    )
    som_note = (
        "Soil organic matter data used to refine credit rate tiers. "
        if any(v is not None for v in som_by_field.values())
        else "No soil organic matter data found — conservative (lower-bound) rates applied. "
    )

    notes = (
        f"Soil Carbon Protocol estimate: {estimated_total:.2f} total credit units "
        f"across {fields_with_credits} field(s). "
        f"Qualifying practices: {practice_summary}. "
        f"{som_note}"
        "Credits are estimates only; third-party verification required before issuance."
    )

    return await _upsert_result(
        farm_id=farm_id,
        status=status,
        practices_documented=practices_documented,
        notes=notes,
        estimated_total_credits=estimated_total,
        field_breakdown=field_breakdown,
        supabase=supabase,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _upsert_result(
    *,
    farm_id: str,
    status: str,
    practices_documented: list[str],
    notes: str,
    estimated_total_credits: float,
    field_breakdown: list[dict],
    supabase,
) -> dict:
    """Persist VCM evaluation result to credit_eligibility and return it.

    The credit_eligibility table stores only the columns defined in the schema.
    Richer data (field_breakdown, estimated_total_credits) is returned in the
    response dict for the router but not stored separately — the report
    endpoint re-runs the estimator to get the full breakdown.

    Args:
        farm_id: UUID of the farm.
        status: One of 'eligible', 'not_eligible', 'pending_review'.
        practices_documented: Matched protocol practice codes.
        notes: Human-readable evaluation summary.
        estimated_total_credits: Total estimated carbon credits for the farm.
        field_breakdown: Per-field credit detail list.
        supabase: Authenticated Supabase client.

    Returns:
        The persisted row augmented with estimated_total_credits and
        field_breakdown.
    """
    now = datetime.now(tz=timezone.utc).isoformat()

    payload = {
        "farm_id": farm_id,
        "program": "VCM",
        "status": status,
        "practices_documented": practices_documented,
        "notes": notes,
        "updated_at": now,
    }

    try:
        result = (
            supabase.table("credit_eligibility")
            .upsert(payload, on_conflict="farm_id,program")
            .execute()
        )
        row: dict = dict(result.data[0]) if result.data else dict(payload)
    except Exception:
        logger.exception(
            "vcm: failed to upsert credit_eligibility for farm=%s", farm_id
        )
        row = dict(payload)

    # Augment with rich data for the router response
    row["estimated_total_credits"] = estimated_total_credits
    row["field_breakdown"] = field_breakdown
    row["program_name"] = "Soil Carbon Protocol"

    logger.info(
        "vcm: evaluation complete farm=%s status=%s total_credits=%.3f practices=%s",
        farm_id,
        status,
        estimated_total_credits,
        practices_documented,
    )
    return row
