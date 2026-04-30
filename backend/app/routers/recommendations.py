import logging

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from postgrest.exceptions import APIError

from app.auth.middleware import get_current_user, get_authenticated_client
from app.main import limiter
from app.models.schemas import RecommendationResponse, RecommendationStatusUpdate
from app.services.recommendations import generate_recommendations as run_generation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/", response_model=list[RecommendationResponse])
async def list_recommendations(
    field_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """List recommendations for a field."""
    result = (
        supabase.table("recommendations")
        .select("*")
        .eq("field_id", field_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.patch("/{recommendation_id}/status", response_model=RecommendationResponse)
async def update_recommendation_status(
    recommendation_id: str,
    body: RecommendationStatusUpdate,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Update a recommendation's status (pending → acted/dismissed)."""
    result = (
        supabase.table("recommendations")
        .update({"status": body.status.value})
        .eq("id", recommendation_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return result.data[0]


@router.post("/generate", status_code=202)
@limiter.limit("10/hour")
async def generate_recommendations(
    request: Request,
    farm_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Generate AI-powered conservation practice recommendations for a farm.

    Assembles farm context, calls the Claude API, validates output against
    known EQIP practice codes, and stores the results. Returns a 202 with
    the generated recommendations summary.
    """
    # Verify farm access (RLS ensures the user owns this farm)
    try:
        result = supabase.table("farms").select("id").eq("id", farm_id).single().execute()
    except APIError:
        raise HTTPException(status_code=404, detail="Farm not found")

    try:
        recommendations = await run_generation(farm_id, supabase)
    except APIError:
        logger.exception("Database error during recommendation generation for farm=%s", farm_id)
        raise HTTPException(
            status_code=500,
            detail="Recommendation generation failed. Please try again later.",
        )
    except anthropic.APIError:
        logger.exception("Anthropic API error during recommendation generation for farm=%s", farm_id)
        raise HTTPException(
            status_code=500,
            detail="Recommendation generation failed. Please try again later.",
        )
    except anthropic.APIConnectionError:
        logger.exception("Anthropic connection error for farm=%s", farm_id)
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable. Please try again later.",
        )
    except anthropic.RateLimitError:
        logger.warning("Anthropic rate limit hit for farm=%s", farm_id)
        raise HTTPException(
            status_code=503,
            detail="AI service is busy. Please try again in a few minutes.",
        )

    return {
        "status": "generation_complete",
        "farm_id": farm_id,
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
