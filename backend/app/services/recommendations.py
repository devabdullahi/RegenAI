"""
LLM recommendation service for RegenAI.

Orchestrates the full pipeline: context assembly -> prompt building ->
LLM (DeepSeek) API call -> output validation -> hallucination guard -> persistence.
"""

import json
import logging

import openai
from postgrest.exceptions import APIError
from pydantic import ValidationError

from app.config import settings
from app.services.context import assemble_farm_context
from app.services.prompts import RECOMMENDATION_SYSTEM_PROMPT, build_user_message
from app.services.validators import (
    LLMRecommendation,
    validate_field_ids,
    validate_practice_codes,
)

logger = logging.getLogger(__name__)

# Shared DeepSeek client (OpenAI-compatible API) — created once per process, not per request.
_llm_client = openai.AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)

# Extra attempts after the first when the LLM's output is malformed. API errors
# (connection, rate limit, status) are not retried here; they propagate.
_MAX_RETRIES = 1


class RecommendationOutputError(RuntimeError):
    """The LLM responded, but no attempt produced a usable recommendation list."""


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

async def _call_llm(system_prompt: str, user_message: str) -> str | None:
    """Call the DeepSeek chat completions API and return the text response.

    Returns None if the response has no choices or empty content (treated as
    malformed output by the caller).

    Raises:
        openai.APIError: Connection, rate-limit and status errors are logged
            and re-raised so the router can map them to 503/502/500.
    """
    try:
        completion = await _llm_client.chat.completions.create(
            model=settings.deepseek_model,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            # Thinking mode is DeepSeek's default, and it ignores temperature and
            # puts reasoning in a separate field. We want a deterministic bare JSON
            # array in `content`, so thinking is disabled explicitly.
            extra_body={"thinking": {"type": "disabled"}},
        )
    except openai.APIError as exc:
        logger.error("LLM API call failed: %s: %s", type(exc).__name__, str(exc)[:200])
        raise

    if not completion.choices:
        logger.warning("LLM returned no choices")
        return None

    choice = completion.choices[0]
    finish_reason = choice.finish_reason
    # A truncated "length" reply is not rescued: it fails strict parsing and the
    # caller's retry loop handles it.
    if finish_reason != "stop":
        logger.warning("LLM finish_reason=%s (expected stop)", finish_reason)

    content = choice.message.content
    if not content or not content.strip():
        logger.warning("LLM returned no text content (finish_reason=%s)", finish_reason)
        return None

    raw_text = content.strip()
    logger.info(
        "LLM response received: %d chars, finish_reason=%s",
        len(raw_text),
        finish_reason,
    )
    return raw_text


# ---------------------------------------------------------------------------
# Strict JSON parsing
# ---------------------------------------------------------------------------

def _parse_llm_json(raw_text: str) -> list | None:
    """Parse the LLM's raw text output into a list.

    The only accepted shape is a bare JSON array (surrounding whitespace is
    trimmed). The system prompt forbids code fences, so everything else is
    rejected with None, which triggers a retry: code fences of any kind, prose
    around the JSON, or a wrapping object such as {"recommendations": [...]}.
    We asked for a bare array and do not rescue other shapes.
    """
    text = raw_text.strip()

    if "```" in text:
        logger.warning("LLM output contains a code fence; a bare JSON array was required")
        return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("LLM output is not a bare JSON array: %s", exc)
        return None

    if not isinstance(parsed, list):
        logger.warning("Parsed JSON is not a list, got %s", type(parsed).__name__)
        return None

    return parsed


# ---------------------------------------------------------------------------
# Pydantic validation
# ---------------------------------------------------------------------------

def _validate_recommendations(raw_list: list) -> list[LLMRecommendation]:
    """Validate a list of raw items against the LLMRecommendation schema.

    Individual items that fail validation are logged and skipped rather than
    failing the entire batch.
    """
    validated: list[LLMRecommendation] = []

    for i, item in enumerate(raw_list):
        try:
            validated.append(LLMRecommendation.model_validate(item))
        except ValidationError as exc:
            logger.warning(
                "Recommendation #%d failed validation: %s — item: %r",
                i,
                exc,
                item,
            )

    logger.info(
        "Pydantic validation: %d of %d recommendations passed",
        len(validated),
        len(raw_list),
    )
    return validated


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _store_recommendations(
    supabase,
    recommendations: list[LLMRecommendation],
    farm_id: str,
    status: str = "pending",
) -> list[dict]:
    """Insert validated recommendations into the recommendations table.

    Returns:
        List of inserted row dicts from Supabase (including generated id and
        created_at).

    Raises:
        APIError: If the insert fails. Generated recommendations that cannot
            be saved must not be reported as a success.
    """
    if not recommendations:
        return []

    rows = [
        {
            # The Supabase client cannot JSON-serialize UUID objects.
            "field_id": str(rec.field_id),
            "practice_code": rec.practice_code,
            "title": rec.title,
            "rationale": rec.rationale,
            "priority": rec.priority.value,
            "status": status,
        }
        for rec in recommendations
    ]

    try:
        result = supabase.table("recommendations").insert(rows).execute()
    except APIError as exc:
        logger.error(
            "Failed to store %d recommendations for farm=%s: %s", len(rows), farm_id, exc
        )
        raise

    stored = result.data or []
    logger.info("Stored %d recommendations for farm=%s", len(stored), farm_id)
    return stored


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def generate_recommendations(
    farm_id: str,
    supabase,
) -> list[dict]:
    """Generate AI-powered conservation practice recommendations for a farm.

    Pipeline steps:
      1. Assemble farm context from database
      2. Build prompt from template
      3. Call the LLM (DeepSeek) API
      4. Parse and validate JSON output with Pydantic
      5. Run hallucination guard (practice codes + field IDs)
      6. Store valid recommendations in the database
      7. Return the stored recommendations

    Malformed output is retried once. API errors are not retried.

    Args:
        farm_id: UUID string of the farm to generate recommendations for.
        supabase: An authenticated Supabase client instance.

    Returns:
        The recommendation rows as stored in the database. Empty when the farm
        has no fields or every recommendation was rejected by the guards.

    Raises:
        ValueError: The farm was not found or is not accessible.
        openai.APIError: The LLM API call failed.
        RecommendationOutputError: Every attempt produced unusable output.
        APIError: Storing the recommendations failed.
    """
    # ------------------------------------------------------------------
    # Step 1: Assemble context (ValueError propagates for a missing farm)
    # ------------------------------------------------------------------
    context = await assemble_farm_context(farm_id, supabase)

    # Extract valid codes and field IDs for the hallucination guard
    valid_practice_codes: set[str] = {
        p["code"] for p in context.get("eqip_practices", [])
    }
    valid_field_ids: set[str] = {
        f["id"] for f in context.get("fields", [])
    }

    if not valid_field_ids:
        logger.warning("Farm %s has no fields — cannot generate recommendations", farm_id)
        return []

    # ------------------------------------------------------------------
    # Step 2: Build prompt
    # ------------------------------------------------------------------
    user_message = build_user_message(context)

    # ------------------------------------------------------------------
    # Steps 3-4: Call the LLM and parse output (retry malformed output)
    # ------------------------------------------------------------------
    validated_recs: list[LLMRecommendation] = []
    attempts = 0

    while attempts <= _MAX_RETRIES:
        attempts += 1
        logger.info(
            "Calling LLM for farm=%s (attempt %d/%d)",
            farm_id,
            attempts,
            _MAX_RETRIES + 1,
        )

        raw_text = await _call_llm(RECOMMENDATION_SYSTEM_PROMPT, user_message)

        if raw_text is None:
            logger.warning(
                "LLM returned no text for farm=%s (attempt %d)", farm_id, attempts
            )
            continue

        parsed = _parse_llm_json(raw_text)

        if parsed is None:
            logger.warning(
                "Rejected malformed LLM output for farm=%s (attempt %d)",
                farm_id,
                attempts,
            )
            continue

        validated_recs = _validate_recommendations(parsed)

        if validated_recs:
            break

        logger.warning(
            "No recommendations passed validation for farm=%s (attempt %d)",
            farm_id,
            attempts,
        )

    if not validated_recs:
        logger.error(
            "All %d attempts produced unusable output for farm=%s", attempts, farm_id
        )
        raise RecommendationOutputError(
            f"LLM produced no valid recommendations after {attempts} attempts"
        )

    # ------------------------------------------------------------------
    # Step 5: Hallucination guards
    # ------------------------------------------------------------------

    # Guard 1: Verify field IDs belong to this farm
    valid_by_field, flagged_by_field = validate_field_ids(
        validated_recs, valid_field_ids
    )

    if flagged_by_field:
        logger.warning(
            "%d recommendations had hallucinated field IDs for farm=%s",
            len(flagged_by_field),
            farm_id,
        )

    # Guard 2: Verify practice codes exist in EQIP table
    valid_by_code, flagged_by_code = validate_practice_codes(
        valid_by_field, valid_practice_codes
    )

    # ------------------------------------------------------------------
    # Step 6: Store results
    # ------------------------------------------------------------------
    stored = _store_recommendations(supabase, valid_by_code, farm_id, status="pending")

    # Recommendations with unverified practice codes are dropped, not stored,
    # so farmers never see a practice that is not in eqip_practices.
    if flagged_by_code:
        logger.warning(
            "Dropped %d recommendations with unverified practice codes for farm=%s: %s",
            len(flagged_by_code),
            farm_id,
            [r.practice_code for r in flagged_by_code],
        )

    # ------------------------------------------------------------------
    # Step 7: Return
    # ------------------------------------------------------------------
    logger.info(
        "Recommendation generation complete for farm=%s: "
        "%d generated, %d stored, %d flagged",
        farm_id,
        len(validated_recs),
        len(stored),
        len(flagged_by_code) + len(flagged_by_field),
    )

    return stored
