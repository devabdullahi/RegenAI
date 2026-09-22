"""Recommendation response and status-update models."""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Priority, RecommendationStatus


class RecommendationResponse(BaseModel):
    id: str
    field_id: str
    created_at: datetime
    practice_code: str
    title: str
    rationale: str
    priority: Priority
    status: RecommendationStatus


class RecommendationStatusUpdate(BaseModel):
    status: RecommendationStatus
