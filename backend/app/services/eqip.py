"""
EQIP eligibility engine for RegenAI.

Evaluates whether a farm qualifies for USDA EQIP cost-share payments by
matching acted recommendations against registered EQIP practice codes and
checking for supporting documentation. Results are persisted to the
credit_eligibility table so the router can serve cached reads.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Minimum document types that constitute "basic documentation" for a practice.
# The presence of at least one qualifying document for the farm is sufficient
# for the initial eligibility pass — a more rigorous review happens offline.
_QUALIFYING_DOC_TYPES: frozenset[str] = frozenset(
    {"soil_report", "field_photo", "compliance"}
)


async def evaluate_eqip_eligibility(farm_id: str, supabase) -> dict:
    """Evaluate EQIP cost-share eligibility for a farm.

    Algorithm:
        1. Fetch all fields for the farm.
        2. Fetch all recommendations with status="acted" across those fields.
        3. Load all valid EQIP practice codes from the eqip_practices table.
        4. Intersect acted practice codes with valid EQIP codes.
        5. Check whether the farm has at least one qualifying document on file.
        6. Determine overall status and construct human-readable notes.
        7. Upsert the result into credit_eligibility (program="EQIP").

    Args:
        farm_id: UUID of the farm to evaluate.
        supabase: Authenticated Supabase client (respects RLS).

    Returns:
        A dict with keys: farm_id, program, status, practices_documented,
        notes, updated_at.

    Raises:
        ValueError: If the farm cannot be found or has no accessible fields.
    """
    # ------------------------------------------------------------------
    # 1. Fetch all fields for this farm
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
        logger.exception("eqip: failed to fetch fields for farm=%s", farm_id)
        raise ValueError(f"Could not retrieve fields for farm {farm_id}")

    field_ids: list[str] = [f["id"] for f in fields]

    if not field_ids:
        logger.warning("eqip: farm=%s has no registered fields", farm_id)
        return await _upsert_result(
            farm_id=farm_id,
            status="not_eligible",
            practices_documented=[],
            notes="No fields are registered for this farm. Add fields before applying for EQIP.",
            supabase=supabase,
        )

    # ------------------------------------------------------------------
    # 2. Fetch acted recommendations across all fields
    # ------------------------------------------------------------------
    try:
        recs_result = (
            supabase.table("recommendations")
            .select("field_id, practice_code, title")
            .in_("field_id", field_ids)
            .eq("status", "acted")
            .execute()
        )
        acted_recs: list[dict] = recs_result.data or []
    except Exception:
        logger.exception(
            "eqip: failed to fetch acted recommendations for farm=%s", farm_id
        )
        acted_recs = []

    if not acted_recs:
        return await _upsert_result(
            farm_id=farm_id,
            status="not_eligible",
            practices_documented=[],
            notes=(
                "No acted recommendations found. Mark at least one recommendation as "
                "'acted' to begin the EQIP eligibility review."
            ),
            supabase=supabase,
        )

    # ------------------------------------------------------------------
    # 3. Load valid EQIP practice codes from reference table
    # ------------------------------------------------------------------
    try:
        eqip_result = (
            supabase.table("eqip_practices")
            .select("code, name, category")
            .execute()
        )
        eqip_rows: list[dict] = eqip_result.data or []
    except Exception:
        logger.exception("eqip: failed to fetch eqip_practices reference table")
        eqip_rows = []

    # Build a lookup: code -> practice metadata
    eqip_lookup: dict[str, dict] = {row["code"]: row for row in eqip_rows}

    # ------------------------------------------------------------------
    # 4. Intersect acted codes with valid EQIP codes
    # ------------------------------------------------------------------
    # De-duplicate by (field_id, practice_code) so one field acting on the
    # same practice multiple times does not skew the list.
    seen: set[tuple[str, str]] = set()
    matched_practices: list[dict] = []

    for rec in acted_recs:
        code: str = rec["practice_code"]
        field_id: str = rec["field_id"]
        key = (field_id, code)

        if key in seen:
            continue
        seen.add(key)

        if code in eqip_lookup:
            matched_practices.append(
                {
                    "code": code,
                    "name": eqip_lookup[code]["name"],
                    "category": eqip_lookup[code].get("category", ""),
                    "field_id": field_id,
                    "title": rec.get("title", ""),
                }
            )

    practices_documented: list[str] = sorted(
        {mp["code"] for mp in matched_practices}
    )

    if not matched_practices:
        acted_codes = sorted({r["practice_code"] for r in acted_recs})
        return await _upsert_result(
            farm_id=farm_id,
            status="not_eligible",
            practices_documented=[],
            notes=(
                f"Acted practice codes ({', '.join(acted_codes) or 'none'}) do not match "
                "any registered EQIP practice codes. Continue adding conservation practices "
                "to qualify."
            ),
            supabase=supabase,
        )

    # ------------------------------------------------------------------
    # 5. Check for supporting documents
    # ------------------------------------------------------------------
    try:
        docs_result = (
            supabase.table("documents")
            .select("doc_type")
            .eq("farm_id", farm_id)
            .execute()
        )
        doc_types: set[str] = {
            d["doc_type"]
            for d in (docs_result.data or [])
            if d.get("doc_type") in _QUALIFYING_DOC_TYPES
        }
    except Exception:
        logger.exception("eqip: failed to fetch documents for farm=%s", farm_id)
        doc_types = set()

    has_documentation = bool(doc_types)

    # ------------------------------------------------------------------
    # 6. Determine status and compose notes
    # ------------------------------------------------------------------
    practice_summary = ", ".join(
        f"{mp['code']} – {mp['name']}" for mp in matched_practices
    )

    if has_documentation:
        status = "eligible"
        doc_note = (
            f"Supporting documents on file: {', '.join(sorted(doc_types))}. "
            "Farm meets basic documentation requirements for EQIP application."
        )
    else:
        status = "pending_review"
        doc_note = (
            "No supporting documents found (soil report, field photo, or compliance "
            "record). Upload at least one document to complete the EQIP application."
        )

    notes = (
        f"EQIP-eligible practices identified: {practice_summary}. "
        f"{doc_note} "
        f"Matched {len(matched_practices)} acted practice(s) across "
        f"{len(field_ids)} field(s)."
    )

    return await _upsert_result(
        farm_id=farm_id,
        status=status,
        practices_documented=practices_documented,
        notes=notes,
        supabase=supabase,
    )


async def _upsert_result(
    *,
    farm_id: str,
    status: str,
    practices_documented: list[str],
    notes: str,
    supabase,
) -> dict:
    """Persist evaluation result to credit_eligibility and return it.

    Uses an upsert on (farm_id, program) so repeated evaluations overwrite
    the previous result cleanly. The updated_at timestamp is always refreshed
    to the current UTC time so callers can detect stale data.

    Args:
        farm_id: UUID of the farm.
        status: One of 'eligible', 'not_eligible', 'pending_review'.
        practices_documented: List of matched EQIP practice codes.
        notes: Human-readable explanation of the evaluation outcome.
        supabase: Authenticated Supabase client.

    Returns:
        The persisted row as a dict.
    """
    now = datetime.now(tz=timezone.utc).isoformat()

    payload = {
        "farm_id": farm_id,
        "program": "EQIP",
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
        row: dict = result.data[0] if result.data else payload
    except Exception:
        logger.exception(
            "eqip: failed to upsert credit_eligibility for farm=%s", farm_id
        )
        row = payload

    logger.info(
        "eqip: evaluation complete farm=%s status=%s practices=%s",
        farm_id,
        status,
        practices_documented,
    )
    return row
