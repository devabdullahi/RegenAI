"""
EQIP eligibility engine for RegenAI.

Evaluates whether a farm qualifies for USDA EQIP cost-share payments by
matching acted recommendations against registered EQIP practice codes and
checking for supporting documentation. Results are persisted to the
credit_eligibility table so the router can serve cached reads.

A failed read or write raises ``CreditDataError``: a status computed from
missing data would otherwise be saved as if it were the farm's real result.
"""

import logging
from datetime import datetime, timezone

import httpx
from postgrest.exceptions import APIError

from app.models.schemas import DocumentType
from app.services.credit_rules import CreditDataError

logger = logging.getLogger(__name__)

# Database/transport failures become CreditDataError; anything else is a bug
# and propagates unchanged.
_DB_ERRORS: tuple[type[Exception], ...] = (APIError, httpx.HTTPError)

# Document types that count as "basic documentation" for the initial pass (a
# more rigorous review happens offline). ``other`` is deliberately excluded:
# an unlabelled upload says nothing about the practice. Ordered for the
# plain-language note; tests keep every entry a real DocumentType.
QUALIFYING_DOC_TYPE_LABELS: dict[str, str] = {
    DocumentType.soil_report.value: "soil report",
    DocumentType.field_photo.value: "field photo",
    DocumentType.compliance.value: "compliance record",
}
QUALIFYING_DOC_TYPES: frozenset[str] = frozenset(QUALIFYING_DOC_TYPE_LABELS)

_QUALIFYING_DOC_TYPES_TEXT: str = (
    ", ".join(list(QUALIFYING_DOC_TYPE_LABELS.values())[:-1])
    + ", or "
    + list(QUALIFYING_DOC_TYPE_LABELS.values())[-1]
)


async def evaluate_eqip_eligibility(
    farm_id: str,
    supabase,
    *,
    now: datetime | None = None,
) -> dict:
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
        now: Evaluation timestamp; defaults to the current UTC time.

    Returns:
        A dict with keys: farm_id, program, status, practices_documented,
        notes, updated_at.

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

    if not field_ids:
        logger.warning("eqip: farm=%s has no registered fields", farm_id)
        return _upsert_result(
            farm_id=farm_id,
            status="not_eligible",
            practices_documented=[],
            notes="No fields are registered for this farm. Add fields before applying for EQIP.",
            evaluated_at=evaluated_at,
            supabase=supabase,
        )

    acted_recs = _read_rows(
        lambda: (
            supabase.table("recommendations")
            .select("field_id, practice_code, title")
            .in_("field_id", field_ids)
            .eq("status", "acted")
        ),
        what="acted recommendations",
        farm_id=farm_id,
    )

    if not acted_recs:
        return _upsert_result(
            farm_id=farm_id,
            status="not_eligible",
            practices_documented=[],
            notes=(
                "No acted recommendations found. Mark at least one recommendation as "
                "'acted' to begin the EQIP eligibility review."
            ),
            evaluated_at=evaluated_at,
            supabase=supabase,
        )

    eqip_rows = _read_rows(
        lambda: supabase.table("eqip_practices").select("code, name, category"),
        what="EQIP practice codes",
        farm_id=farm_id,
    )
    eqip_lookup: dict[str, dict] = {row["code"]: row for row in eqip_rows}

    # De-duplicate by (field_id, practice_code) so one field acting on the
    # same practice multiple times does not skew the list.
    seen: set[tuple[str, str]] = set()
    matched_practices: list[dict] = []

    for rec in acted_recs:
        code: str = rec["practice_code"]
        key = (rec["field_id"], code)
        if key in seen:
            continue
        seen.add(key)
        if code not in eqip_lookup:
            continue
        matched_practices.append(
            {
                "code": code,
                "name": eqip_lookup[code]["name"],
                "category": eqip_lookup[code].get("category", ""),
                "field_id": rec["field_id"],
                "title": rec.get("title", ""),
            }
        )

    if not matched_practices:
        acted_codes = sorted({r["practice_code"] for r in acted_recs})
        return _upsert_result(
            farm_id=farm_id,
            status="not_eligible",
            practices_documented=[],
            notes=(
                f"Acted practice codes ({', '.join(acted_codes) or 'none'}) do not match "
                "any registered EQIP practice codes. Continue adding conservation practices "
                "to qualify."
            ),
            evaluated_at=evaluated_at,
            supabase=supabase,
        )

    documents = _read_rows(
        lambda: supabase.table("documents").select("doc_type").eq("farm_id", farm_id),
        what="documents",
        farm_id=farm_id,
    )
    doc_types: set[str] = {
        d["doc_type"] for d in documents if d.get("doc_type") in QUALIFYING_DOC_TYPES
    }

    practices_documented: list[str] = sorted({mp["code"] for mp in matched_practices})
    practice_summary = ", ".join(f"{mp['code']} – {mp['name']}" for mp in matched_practices)

    if doc_types:
        status = "eligible"
        doc_note = (
            f"Supporting documents on file: {', '.join(sorted(doc_types))}. "
            "Farm meets basic documentation requirements for EQIP application."
        )
    else:
        status = "pending_review"
        doc_note = (
            f"No qualifying supporting documents found ({_QUALIFYING_DOC_TYPES_TEXT}). "
            "Upload at least one to complete the EQIP application."
        )

    notes = (
        f"EQIP-eligible practices identified: {practice_summary}. "
        f"{doc_note} "
        f"Matched {len(matched_practices)} acted practice(s) across "
        f"{len(field_ids)} field(s)."
    )

    return _upsert_result(
        farm_id=farm_id,
        status=status,
        practices_documented=practices_documented,
        notes=notes,
        evaluated_at=evaluated_at,
        supabase=supabase,
    )


def _read_rows(build_query, *, what: str, farm_id: str) -> list[dict]:
    """Execute a read query, raising CreditDataError instead of guessing on failure."""
    try:
        return build_query().execute().data or []
    except _DB_ERRORS as exc:
        logger.exception("eqip: failed to read %s for farm=%s", what, farm_id)
        raise CreditDataError(
            f"EQIP evaluation could not read {what}; no result was saved."
        ) from exc


def _upsert_result(
    *,
    farm_id: str,
    status: str,
    practices_documented: list[str],
    notes: str,
    evaluated_at: datetime,
    supabase,
) -> dict:
    """Persist the evaluation result to credit_eligibility and return the saved row.

    Upserts on (farm_id, program) so repeated evaluations overwrite the
    previous result.

    Raises:
        CreditDataError: If the upsert fails or returns no row, so callers
            never report a result that was not saved.
    """
    payload = {
        "farm_id": farm_id,
        "program": "EQIP",
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
        logger.exception("eqip: failed to upsert credit_eligibility for farm=%s", farm_id)
        raise CreditDataError("EQIP evaluation result could not be saved.") from exc

    if not result.data:
        logger.error("eqip: credit_eligibility upsert returned no row for farm=%s", farm_id)
        raise CreditDataError("EQIP evaluation result could not be saved.")

    logger.info(
        "eqip: evaluation complete farm=%s status=%s practices=%s",
        farm_id,
        status,
        practices_documented,
    )
    # Merge the saved row over the payload so evaluation fields are present
    # even when the DB returns a partial representation.
    return {**payload, **result.data[0]}
