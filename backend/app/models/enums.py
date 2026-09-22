"""Cross-cutting enums shared by several response models."""

from enum import Enum


class RecommendationStatus(str, Enum):
    pending = "pending"
    acted = "acted"
    dismissed = "dismissed"


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class CreditProgram(str, Enum):
    eqip = "EQIP"
    vcm = "VCM"


class CreditStatus(str, Enum):
    eligible = "eligible"
    not_eligible = "not_eligible"
    pending_review = "pending_review"


class Goals(str, Enum):
    cost_savings = "cost_savings"
    carbon_credits = "carbon_credits"
    both = "both"
