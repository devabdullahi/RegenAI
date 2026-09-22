"""
Recommendations router for RegenAI.

Lists and updates stored recommendations, and triggers AI generation for a
farm. Generation is rate limited because each call hits the DeepSeek LLM API.
"""

import logging
from uuid import UUID

import openai
from fastapi import APIRouter, Depends, HTTPException, Request
from postgrest.exceptions import APIError

from app.auth.access import assert_farm_access, assert_field_access
from app.auth.middleware import get_authenticated_client, get_current_user
from app.models.schemas import RecommendationResponse, RecommendationStatusUpdate
from app.rate_limit import limiter
from app.services.recommendations import RecommendationOutputError
from app.services.recommendations import generate_recommendations as run_generation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/", response_model=list[RecommendationResponse])
async def list_recommendations(
    field_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """List recommendations for a field (404 if the field is missing or not yours)."""
    field_id_str = str(field_id)
    assert_field_access(field_id_str, supabase)
    try:
        result = (
            supabase.table("recommendations")
            .select("*")
            .eq("field_id", field_id_str)
            .order("created_at", desc=True)
            .execute()
        )
    except APIError:
        logger.exception("Failed to list recommendations for field=%s", field_id)
        raise HTTPException(status_code=500, detail="Failed to list recommendations")
    return result.data or []


@router.patch("/{recommendation_id}/status", response_model=RecommendationResponse)
async def update_recommendation_status(
    recommendation_id: UUID,
    body: RecommendationStatusUpdate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Update a recommendation's status (pending → acted/dismissed)."""
    try:
        result = (
            supabase.table("recommendations")
            .update({"status": body.status.value})
            .eq("id", str(recommendation_id))
            .execute()
        )
    except APIError:
        logger.exception("Failed to update recommendation id=%s", recommendation_id)
        raise HTTPException(status_code=500, detail="Failed to update recommendation")
    if not result.data:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return result.data[0]


@router.post("/generate", status_code=202)
@limiter.limit("10/hour")
async def generate_recommendations(
    request: Request,
    farm_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Generate AI-powered conservation practice recommendations for a farm.

    Assembles farm context, calls the DeepSeek LLM API, validates output against
    known EQIP practice codes, and stores the results. Returns a 202 with
    the generated recommendations summary.

    Errors: 404 farm not found; 503 AI service unreachable or rate limited;
    502 AI service error or unusable AI output; 500 database failure.
    """
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)

    try:
        recommendations = await run_generation(farm_id_str, supabase)
    except ValueError:
        logger.warning("Farm not found during recommendation generation farm=%s", farm_id_str)
        raise HTTPException(status_code=404, detail="Farm not found")
    except APIError:
        logger.exception("Database error during recommendation generation farm=%s", farm_id_str)
        raise HTTPException(
            status_code=500,
            detail="Recommendations could not be saved. Please try again later.",
        )
    except openai.APIConnectionError:
        # Also covers openai.APITimeoutError, which subclasses APIConnectionError.
        logger.exception("LLM connection error farm=%s", farm_id_str)
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable. Please try again later.",
        )
    except openai.RateLimitError:
        # Subclass of APIStatusError — must be caught before it.
        logger.warning("LLM rate limit hit farm=%s", farm_id_str)
        raise HTTPException(
            status_code=503,
            detail="AI service is busy. Please try again in a few minutes.",
        )
    except openai.APIStatusError as exc:
        # status_code distinguishes e.g. DeepSeek 402 (insufficient balance) from 5xx.
        logger.exception(
            "LLM API status error farm=%s status=%s", farm_id_str, exc.status_code
        )
        raise HTTPException(
            status_code=502,
            detail="AI service returned an error. Please try again later.",
        )
    except RecommendationOutputError:
        logger.exception("Unusable AI output farm=%s", farm_id_str)
        raise HTTPException(
            status_code=502,
            detail="AI service returned an unusable response. Please try again.",
        )
    except openai.APIError:
        logger.exception("LLM API error farm=%s", farm_id_str)
        raise HTTPException(
            status_code=500,
            detail="Recommendation generation failed. Please try again later.",
        )

    return {
        "status": "generation_complete",
        "farm_id": farm_id_str,
        "recommendations_count": len(recommendations),
        "recommendations": [
            {
                "id": r.get("id"),
                "field_id": r.get("field_id"),
                "practice_code": r.get("practice_code"),
                "title": r.get("title"),
                "priority": r.get("priority"),
                "status": r.get("status"),
            }
            for r in recommendations
        ],
    }
