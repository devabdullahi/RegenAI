"""
LLM recommendation service for RegenAI.

Orchestrates the full pipeline: context assembly -> prompt building ->
Claude API call -> output validation -> hallucination guard -> persistence.
"""

import json
import logging
from datetime import datetime, timezone

import anthropic

from app.config import settings
from app.services.context import assemble_farm_context
from app.services.prompts import RECOMMENDATION_SYSTEM_PROMPT, build_user_message
from app.services.validators import (
    LLMRecommendation,
    LLMRecommendationList,
    validate_field_ids,
    validate_practice_codes,
)

logger = logging.getLogger(__name__)

# Shared Anthropic client — created once per process, not per request.
_anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Claude model to use for recommendation generation.
_MODEL = "claude-sonnet-4-20250514"

# Maximum tokens for the recommendation response. 3-6 recommendations in JSON
# typically requires 1500-2500 tokens; we allow headroom.
_MAX_TOKENS = 4096

# Temperature: low for structured/factual output, slight variation for
# diversity across runs.
_TEMPERATURE = 0.3

# Maximum retry attempts on malformed LLM output before returning empty.
_MAX_RETRIES = 1


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

async def _call_claude(system_prompt: str, user_message: str) -> str | None:
    """Call the Anthropic messages API and return the text response.

    Returns None if the API call fails or returns no content.
    """
    try:
        message = await _anthropic_client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            temperature=_TEMPERATURE,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message},
            ],
        )

        # Extract text from the response content blocks
        text_parts = [
            block.text
            for block in message.content
            if hasattr(block, "text")
        ]

        if not text_parts:
            logger.warning("Claude returned no text content blocks")
            return None

        raw_text = "\n".join(text_parts).strip()
        logger.info(
            "Claude response received: %d chars, stop_reason=%s",
            len(raw_text),
            message.stop_reason,
        )
        return raw_text

    except anthropic.APIConnectionError:
        logger.error("Failed to connect to Anthropic API")
        return None
    except anthropic.RateLimitError:
        logger.error("Anthropic API rate limit exceeded")
        return None
    except anthropic.APIStatusError as exc:
        logger.error(
            "Anthropic API error: status=%d message=%s",
            exc.status_code,
            str(exc)[:200],
        )
        return None
    except Exception:
        logger.exception("Unexpected error calling Claude API")
        return None


# ---------------------------------------------------------------------------
# JSON parsing with cleanup
# ---------------------------------------------------------------------------

def _parse_llm_json(raw_text: str) -> list[dict] | None:
    """Parse the LLM's raw text output into a list of dicts.

    Handles common LLM quirks: markdown code fences, leading prose, trailing
    text after the JSON array.

    Returns None if parsing fails.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # Remove opening fence (with optional language tag)
        first_newline = text.index("\n") if "\n" in text else 3
        text = text[first_newline + 1:]
        # Remove closing fence
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Find the JSON array boundaries
    start = text.find("[")
    end = text.rfind("]")

    if start == -1 or end == -1 or end <= start:
        logger.warning("Could not find JSON array in LLM output")
        return None

    json_str = text[start:end + 1]

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse error: %s", exc)
        return None

    if not isinstance(parsed, list):
        logger.warning("Parsed JSON is not a list, got %s", type(parsed).__name__)
        return None

    return parsed


# ---------------------------------------------------------------------------
# Pydantic validation
# ---------------------------------------------------------------------------

def _validate_recommendations(raw_list: list[dict]) -> list[LLMRecommendation]:
    """Validate a list of raw dicts against the LLMRecommendation schema.

    Individual items that fail validation are logged and skipped rather than
    failing the entire batch.
    """
    validated: list[LLMRecommendation] = []

    for i, item in enumerate(raw_list):
        try:
            rec = LLMRecommendation.model_validate(item)
            validated.append(rec)
        except Exception as exc:
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
    status: str = "pending",
) -> list[dict]:
    """Insert validated recommendations into the recommendations table.

    Args:
        supabase: Supabase client instance.
        recommendations: Validated LLMRecommendation objects.
        status: Status to assign. 'pending' for valid, could be extended.

    Returns:
        List of inserted row dicts from Supabase (including generated id and
        created_at).
    """
    if not recommendations:
        return []

    rows = [
        {
            "field_id": rec.field_id,
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
        stored = result.data or []
        logger.info("Stored %d recommendations", len(stored))
        return stored
    except Exception:
        logger.exception("Failed to store recommendations")
        return []


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
      3. Call Claude API
      4. Parse and validate JSON output with Pydantic
      5. Run hallucination guard (practice codes + field IDs)
      6. Store valid recommendations in the database
      7. Return the stored recommendations

    On LLM failure or malformed output, retries once. If both attempts fail,
    returns an empty list with a warning logged.

    Args:
        farm_id: UUID of the farm to generate recommendations for.
        supabase: An authenticated Supabase client instance.

    Returns:
        A list of recommendation dicts as stored in the database, or an
        empty list if generation failed.
    """
    # ------------------------------------------------------------------
    # Step 1: Assemble context
    # ------------------------------------------------------------------
    try:
        context = await assemble_farm_context(farm_id, supabase)
    except ValueError as exc:
        logger.error("Context assembly failed for farm=%s: %s", farm_id, exc)
        return []

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
    # Steps 3-4: Call Claude and parse output (with retry)
    # ------------------------------------------------------------------
    validated_recs: list[LLMRecommendation] = []
    attempts = 0

    while attempts <= _MAX_RETRIES:
        attempts += 1
        logger.info(
            "Calling Claude for farm=%s (attempt %d/%d)",
            farm_id,
            attempts,
            _MAX_RETRIES + 1,
        )

        raw_text = await _call_claude(RECOMMENDATION_SYSTEM_PROMPT, user_message)

        if raw_text is None:
            logger.warning(
                "Claude API returned no output for farm=%s (attempt %d)",
                farm_id,
                attempts,
            )
            continue

        parsed = _parse_llm_json(raw_text)

        if parsed is None:
            logger.warning(
                "Failed to parse JSON from Claude output for farm=%s (attempt %d)",
                farm_id,
                attempts,
            )
            continue

        validated_recs = _validate_recommendations(parsed)

        if validated_recs:
            break
        else:
            logger.warning(
                "No recommendations passed validation for farm=%s (attempt %d)",
                farm_id,
                attempts,
            )

    if not validated_recs:
        logger.error(
            "All %d attempts to generate recommendations failed for farm=%s",
            attempts,
            farm_id,
        )
        return []

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

    if flagged_by_code:
        logger.warning(
            "%d recommendations had unknown practice codes for farm=%s",
            len(flagged_by_code),
            farm_id,
        )

    # ------------------------------------------------------------------
    # Step 6: Store results
    # ------------------------------------------------------------------

    # Store valid recommendations as 'pending'
    stored = _store_recommendations(supabase, valid_by_code, status="pending")

    # Store flagged-by-code recommendations as 'pending' but log them;
    # in the future these could go to a review queue. For now, we skip them
    # to avoid showing potentially hallucinated practices to farmers.
    if flagged_by_code:
        logger.info(
            "Skipped %d recommendations with unverified practice codes for farm=%s: %s",
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
