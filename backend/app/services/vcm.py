"""
VCM (Voluntary Carbon Market) credit estimator for RegenAI.

Translates acted conservation practice recommendations into estimated carbon
credit units per acre per year. The credit bands and soil organic matter
(SOM) tiers are internal estimates, not a registry protocol — they live in
``app.services.credit_rules`` with their ``as_of`` date and ``estimate``
status, and every result carries ``is_estimate=True`` and
``VCM_METHOD_LABEL``.

Within a practice's band, SOM picks the rate: SOM >= the high tier uses the
upper bound, SOM >= the low tier the midpoint, and lower SOM the lower bound.
Fields without a soil reading use the lower bound (conservative estimate).

Results are persisted to credit_eligibility with program="VCM". A failed read
or write raises ``CreditDataError`` rather than saving an estimate computed
from missing data.
"""

import logging
from datetime import datetime, timezone

import httpx
from postgrest.exceptions import APIError

from app.services.credit_rules import (
    VCM_CREDIT_BANDS,
    VCM_METHOD_LABEL,
    VCM_SOM_TIERS,
    CreditDataError,
    vcm_rules_metadata,
)

logger = logging.getLogger(__name__)

# Database/transport failures become CreditDataError; anything else is a bug
# and propagates unchanged.
_DB_ERRORS: tuple[type[Exception], ...] = (APIError, httpx.HTTPError)


def _credits_per_acre(practice_code: str, organic_matter_pct: float | None) -> float:
    """Resolve a single credit rate for a practice code and SOM value.

    Args:
        practice_code: Practice code; must be a key of VCM_CREDIT_BANDS.
        organic_matter_pct: Soil organic matter percentage, or None if unknown.
            Unknown SOM uses the lower bound rather than an assumed reading.

    Returns:
        Estimated credits per acre per year.
    """
    band = VCM_CREDIT_BANDS[practice_code]
    if organic_matter_pct is None:
        return band.low
    if organic_matter_pct >= VCM_SOM_TIERS.high_pct:
        return band.high
    if organic_matter_pct >= VCM_SOM_TIERS.low_pct:
        return round((band.low + band.high) / 2, 3)
    return band.low


def _practice_name(code: str) -> str:
    band = VCM_CREDIT_BANDS.get(code)
    return band.practice_name if band else code


async def estimate_vcm_credits(
    farm_id: str,
    supabase,
    *,
    now: datetime | None = None,
) -> dict:
    """Estimate VCM credits for a farm and persist the summary.

    Algorithm:
        1. Fetch all fields for the farm (need acres).
        2. Fetch acted recommendations for practices that have a credit band.
        3. Fetch soil profiles to resolve SOM tiers per field.
        4. For each (field, practice) pair:
               estimated_credits = acres × credits_per_acre(practice, som)
        5. Aggregate into a per-field breakdown and a farm total.
        6. Upsert the summary into credit_eligibility (program="VCM").

    Args:
        farm_id: UUID of the farm to evaluate.
        supabase: Authenticated Supabase client (respects RLS).
        now: Evaluation timestamp; defaults to the current UTC time.

    Returns:
        The saved credit_eligibility row plus estimated_total_credits,
        field_breakdown, program_name, and the rule provenance keys from
        ``vcm_rules_metadata()`` (method_label, is_estimate, rules_as_of, ...).

    Raises:
        CreditDataError: If any input read or the result upsert fails.
    """
    evaluated_at = now or datetime.now(tz=timezone.utc)

    fields = _read_rows(
        lambda: supabase.table("fields").select("id, name, acres").eq("farm_id", farm_id),
        what="fields",
        farm_id=farm_id,
    )
    field_ids: list[str] = [f["id"] for f in fields]
    field_map: dict[str, dict] = {f["id"]: f for f in fields}

    if not field_ids:
        return _upsert_result(
            farm_id=farm_id,
            status="not_eligible",
            practices_documented=[],
            notes="No fields registered. Add fields to estimate VCM credits.",
            estimated_total_credits=0.0,
            field_breakdown=[],
            evaluated_at=evaluated_at,
            supabase=supabase,
        )

    credited_codes = list(VCM_CREDIT_BANDS.keys())
    rec_rows = _read_rows(
        lambda: (
            supabase.table("recommendations")
            .select("field_id, practice_code, title")
            .in_("field_id", field_ids)
            .eq("status", "acted")
            .in_("practice_code", credited_codes)
        ),
        what="acted recommendations",
        farm_id=farm_id,
    )
    # Re-check codes locally: never trust the query filter alone, since an
    # unexpected code would otherwise raise KeyError in _credits_per_acre.
    acted_recs = [rec for rec in rec_rows if rec.get("practice_code") in VCM_CREDIT_BANDS]

    if not acted_recs:
        return _upsert_result(
            farm_id=farm_id,
            status="not_eligible",
            practices_documented=[],
            notes=(
                "No acted recommendations match the practices RegenAI estimates VCM "
                f"credits for ({', '.join(credited_codes)}). Act on at least one "
                "qualifying recommendation to generate a VCM credit estimate."
            ),
            estimated_total_credits=0.0,
            field_breakdown=[],
            evaluated_at=evaluated_at,
            supabase=supabase,
        )

    soil_rows = _read_rows(
        lambda: (
            supabase.table("soil_profiles")
            .select("field_id, organic_matter_pct")
            .in_("field_id", field_ids)
            .order("fetched_at", desc=True)
        ),
        what="soil profiles",
        farm_id=farm_id,
    )
    # Rows are newest first, so the first row seen per field is its latest reading.
    som_by_field: dict[str, float | None] = {fid: None for fid in field_ids}
    seen_fields: set[str] = set()
    for row in soil_rows:
        fid = row["field_id"]
        if fid in seen_fields:
            continue
        seen_fields.add(fid)
        som_by_field[fid] = row.get("organic_matter_pct")

    seen_pairs: set[tuple[str, str]] = set()
    field_credits: dict[str, dict] = {}

    for rec in acted_recs:
        fid = rec["field_id"]
        code = rec["practice_code"]
        if (fid, code) in seen_pairs:
            continue
        seen_pairs.add((fid, code))

        acres: float = field_map[fid].get("acres") or 0.0
        rate = _credits_per_acre(code, som_by_field.get(fid))
        credits = round(acres * rate, 3)

        entry = field_credits.setdefault(
            fid,
            {
                "field_id": fid,
                "field_name": field_map[fid].get("name", ""),
                "acres": acres,
                "practices": [],
                "field_total_credits": 0.0,
            },
        )
        entry["practices"].append(
            {
                "practice_code": code,
                "practice_name": _practice_name(code),
                "rate_credits_per_acre": rate,
                "estimated_credits": credits,
            }
        )
        entry["field_total_credits"] = round(entry["field_total_credits"] + credits, 3)

    field_breakdown: list[dict] = list(field_credits.values())
    estimated_total = round(sum(fc["field_total_credits"] for fc in field_breakdown), 3)
    practices_documented = sorted({code for _, code in seen_pairs})

    status = "eligible" if estimated_total > 0 else "pending_review"
    practice_summary = ", ".join(
        f"{code} ({_practice_name(code)})" for code in practices_documented
    )
    som_note = (
        "Soil organic matter data used to refine credit rate tiers. "
        if any(v is not None for v in som_by_field.values())
        else "No soil organic matter data found — conservative (lower-bound) rates applied. "
    )
    notes = (
        f"{VCM_METHOD_LABEL}: {estimated_total:.2f} total credit units "
        f"across {len(field_breakdown)} field(s). "
        f"Qualifying practices: {practice_summary}. "
        f"{som_note}"
        "Credits are estimates only; third-party verification required before issuance."
    )

    return _upsert_result(
        farm_id=farm_id,
        status=status,
        practices_documented=practices_documented,
        notes=notes,
        estimated_total_credits=estimated_total,
        field_breakdown=field_breakdown,
        evaluated_at=evaluated_at,
        supabase=supabase,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_rows(build_query, *, what: str, farm_id: str) -> list[dict]:
    """Execute a read query, raising CreditDataError instead of guessing on failure."""
    try:
        return build_query().execute().data or []
    except _DB_ERRORS as exc:
        logger.exception("vcm: failed to read %s for farm=%s", what, farm_id)
        raise CreditDataError(
            f"VCM estimate could not read {what}; no result was saved."
        ) from exc


def _upsert_result(
    *,
    farm_id: str,
    status: str,
    practices_documented: list[str],
    notes: str,
    estimated_total_credits: float,
    field_breakdown: list[dict],
    evaluated_at: datetime,
    supabase,
) -> dict:
    """Persist the VCM summary to credit_eligibility and return it with detail.

    credit_eligibility has no columns for the breakdown or total, so those are
    returned to the caller but not stored — the report endpoint re-runs the
    estimator to get them.

    Raises:
        CreditDataError: If the upsert fails or returns no row, so callers
            never report a result that was not saved.
    """
    payload = {
        "farm_id": farm_id,
        "program": "VCM",
        "status": status,
        "practices_documented": practices_documented,
        "notes": notes,
        "updated_at": evaluated_at.isoformat(),
    }

    try:
        result = (
            supabase.table("credit_eligibility")
            .upsert(payload, on_conflict="farm_id,program")
            .execute()
        )
    except _DB_ERRORS as exc:
        logger.exception("vcm: failed to upsert credit_eligibility for farm=%s", farm_id)
        raise CreditDataError("VCM estimate could not be saved.") from exc

    if not result.data:
        logger.error("vcm: credit_eligibility upsert returned no row for farm=%s", farm_id)
        raise CreditDataError("VCM estimate could not be saved.")

    logger.info(
        "vcm: evaluation complete farm=%s status=%s total_credits=%.3f practices=%s",
        farm_id,
        status,
        estimated_total_credits,
        practices_documented,
    )
    return {
        **payload,
        **result.data[0],
        "estimated_total_credits": estimated_total_credits,
        "field_breakdown": field_breakdown,
        "program_name": VCM_METHOD_LABEL,
        **vcm_rules_metadata(),
    }
