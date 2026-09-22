"""
Tests for CSP Pydantic models in app.models.schemas.

Coverage targets:
  - All new CSP enum values (CSPApplicationStatus)
  - CSPResourceConcern validation (required fields, defaults, bounds)
  - CSPScoreBreakdown validation
  - CSPPaymentEstimate validation
  - CSPEnhancementActivity validation
  - CSPEligibilityResponse validation
  - Edge cases: missing required fields raise ValidationError
  - Edge cases: negative numeric fields raise ValidationError (ge=0 constraints)
  - Invalid enum values raise ValidationError
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    CSPApplicationStatus,
    CSPResourceConcern,
    CSPScoreBreakdown,
    CSPPaymentEstimate,
    CSPEnhancementActivity,
    CSPEligibilityResponse,
)
from app.services.program_rules import csp_rules_metadata, csp_scoring_rules_metadata

NOW = datetime.now(tz=timezone.utc)
FARM_ID = "farm-uuid-test-1234"


# ---------------------------------------------------------------------------
# CSPApplicationStatus enum
# ---------------------------------------------------------------------------

class TestCSPApplicationStatus:
    def test_valid_values(self):
        assert CSPApplicationStatus.eligible == "eligible"
        assert CSPApplicationStatus.not_eligible == "not_eligible"
        assert CSPApplicationStatus.pending_review == "pending_review"
        assert CSPApplicationStatus.act_now == "act_now"

    def test_has_all_four_statuses(self):
        values = {s.value for s in CSPApplicationStatus}
        assert values == {"eligible", "not_eligible", "pending_review", "act_now"}

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            CSPApplicationStatus("invalid_status")

    def test_str_subclass(self):
        """All enum members should be usable as plain strings."""
        assert isinstance(CSPApplicationStatus.act_now, str)


# ---------------------------------------------------------------------------
# CSPResourceConcern
# ---------------------------------------------------------------------------

class TestCSPResourceConcern:
    def _valid(self, **overrides):
        data = {
            "concern_id": "soil_health",
            "name": "Soil Health and Soil Organic Matter",
            "category": "soil_health",
            "practices_addressing": ["340", "329"],
            "meets_threshold": True,
            "points_earned": 12.5,
            "points_possible": 20.0,
        }
        data.update(overrides)
        return data

    def test_valid_model_creates_successfully(self):
        concern = CSPResourceConcern(**self._valid())
        assert concern.concern_id == "soil_health"
        assert concern.meets_threshold is True

    def test_practices_addressing_defaults_to_empty_list(self):
        data = self._valid()
        del data["practices_addressing"]
        concern = CSPResourceConcern(**data)
        assert concern.practices_addressing == []

    def test_points_earned_defaults_to_zero(self):
        data = self._valid()
        del data["points_earned"]
        concern = CSPResourceConcern(**data)
        assert concern.points_earned == 0.0

    def test_points_possible_defaults_to_zero(self):
        data = self._valid()
        del data["points_possible"]
        concern = CSPResourceConcern(**data)
        assert concern.points_possible == 0.0

    def test_missing_concern_id_raises(self):
        data = self._valid()
        del data["concern_id"]
        with pytest.raises(ValidationError):
            CSPResourceConcern(**data)

    def test_missing_name_raises(self):
        data = self._valid()
        del data["name"]
        with pytest.raises(ValidationError):
            CSPResourceConcern(**data)

    def test_missing_meets_threshold_raises(self):
        data = self._valid()
        del data["meets_threshold"]
        with pytest.raises(ValidationError):
            CSPResourceConcern(**data)

    def test_negative_points_earned_raises(self):
        with pytest.raises(ValidationError):
            CSPResourceConcern(**self._valid(points_earned=-1.0))

    def test_negative_points_possible_raises(self):
        with pytest.raises(ValidationError):
            CSPResourceConcern(**self._valid(points_possible=-5.0))

    def test_zero_points_allowed(self):
        concern = CSPResourceConcern(**self._valid(points_earned=0.0, points_possible=0.0))
        assert concern.points_earned == 0.0


# ---------------------------------------------------------------------------
# CSPScoreBreakdown
# ---------------------------------------------------------------------------

class TestCSPScoreBreakdown:
    def _valid_concern(self):
        return CSPResourceConcern(
            concern_id="soil_health",
            name="Soil Health",
            category="soil_health",
            meets_threshold=True,
            points_earned=12.0,
            points_possible=20.0,
        )

    def _valid(self, **overrides):
        data = {
            "farm_id": FARM_ID,
            "total_points": 45.5,
            "max_possible_points": 100.0,
            "state_ranking_threshold": 47.0,
            "meets_ranking_threshold": False,
            "gap_to_threshold": 1.5,
            "resource_concern_scores": [self._valid_concern()],
            "component_scores": {"soil_health": 12.0},
            "avg_som_pct": 3.1,
            "som_tier": "medium",
            "is_estimate": True,
            "scoring_rules": csp_scoring_rules_metadata(),
            "evaluated_at": NOW,
        }
        data.update(overrides)
        return data

    def test_valid_model_creates(self):
        sb = CSPScoreBreakdown(**self._valid())
        assert sb.total_points == 45.5
        assert sb.avg_som_pct == 3.1
        assert sb.scoring_rules.is_estimate is True

    def test_scoring_rules_required(self):
        data = self._valid()
        del data["scoring_rules"]
        with pytest.raises(ValidationError):
            CSPScoreBreakdown(**data)

    def test_missing_farm_id_raises(self):
        data = self._valid()
        del data["farm_id"]
        with pytest.raises(ValidationError):
            CSPScoreBreakdown(**data)

    def test_negative_total_points_raises(self):
        with pytest.raises(ValidationError):
            CSPScoreBreakdown(**self._valid(total_points=-1.0))

    def test_negative_gap_to_threshold_raises(self):
        with pytest.raises(ValidationError):
            CSPScoreBreakdown(**self._valid(gap_to_threshold=-0.1))

    def test_unknown_threshold_fields_accept_none(self):
        """States with no published threshold send nulls, not a default."""
        sb = CSPScoreBreakdown(
            **self._valid(
                state_ranking_threshold=None,
                meets_ranking_threshold=None,
                gap_to_threshold=None,
                scoring_rules=csp_scoring_rules_metadata("TX"),
            )
        )
        assert sb.state_ranking_threshold is None
        assert sb.meets_ranking_threshold is None
        assert sb.gap_to_threshold is None
        assert sb.scoring_rules.state_ranking_threshold.status == "not_published"
        assert sb.scoring_rules.state_ranking_threshold.value is None

    def test_known_state_scoring_rules_citation(self):
        sb = CSPScoreBreakdown(**self._valid(scoring_rules=csp_scoring_rules_metadata("IA")))
        citation = sb.scoring_rules.state_ranking_threshold
        assert citation.status == "known_estimate"
        assert citation.value == 47.0
        assert citation.state == "IA"

    def test_component_scores_defaults_to_empty_dict(self):
        data = self._valid()
        del data["component_scores"]
        sb = CSPScoreBreakdown(**data)
        assert sb.component_scores == {}

    def test_resource_concern_scores_accepts_empty_list(self):
        sb = CSPScoreBreakdown(**self._valid(resource_concern_scores=[]))
        assert sb.resource_concern_scores == []

    def test_evaluated_at_required(self):
        data = self._valid()
        del data["evaluated_at"]
        with pytest.raises(ValidationError):
            CSPScoreBreakdown(**data)


# ---------------------------------------------------------------------------
# CSPPaymentEstimate
# ---------------------------------------------------------------------------

class TestCSPPaymentEstimate:
    def _valid(self, **overrides):
        data = {
            "farm_id": FARM_ID,
            "eligible_acres": 200.0,
            "eap_annual": 4000.0,
            "resource_concerns_addressed": 2,
            "activity_payment_annual": 2460.0,
            "activities_included": [
                {
                    "code": "340",
                    "practice_standard_code": "340",
                    "name": "Cover Crop",
                    "higher_payment": True,
                    "higher_payment_category": "Cover crop activities",
                    "estimated_rate_per_acre": 9.0,
                    "rate_is_estimate": True,
                    "acres": 200.0,
                    "estimated_annual_payment": 1800.0,
                }
            ],
            "total_annual_payment": 6460.0,
            "total_5year_payment": 32300.0,
            "contract_years": 5,
            "contract_fiscal_year": 2026,
            "joint_operation": False,
            "contract_limit": {
                "amount": 300000.0,
                "label": "$300,000 contract limit (FY2026+)",
                "rule_key": "csp_contract_limit_fy2026_individual",
                "applies_to": "individual_or_entity",
                "contract_fiscal_year": 2026,
                "rules_period": "FY2026+",
                "as_of": "2025-12-17",
                "source_url": "https://directives.nrcs.usda.gov/",
                "source_title": "NB 440-26-2",
            },
            "annual_payment_limit": None,
            "payment_capped": False,
            "field_breakdown": [],
            "state": "IA",
            "rules": csp_rules_metadata(),
            "estimated_at": NOW,
        }
        data.update(overrides)
        return data

    def test_valid_model_creates(self):
        est = CSPPaymentEstimate(**self._valid())
        assert est.eligible_acres == 200.0
        assert est.contract_limit.amount == 300000.0
        assert est.activities_included[0].practice_standard_code == "340"

    def test_annual_payment_limit_defaults_to_none(self):
        data = self._valid()
        del data["annual_payment_limit"]
        assert CSPPaymentEstimate(**data).annual_payment_limit is None

    def test_invalid_rules_period_raises(self):
        data = self._valid()
        data["contract_limit"] = dict(data["contract_limit"], rules_period="FY2024")
        with pytest.raises(ValidationError):
            CSPPaymentEstimate(**data)

    def test_missing_contract_limit_raises(self):
        data = self._valid()
        del data["contract_limit"]
        with pytest.raises(ValidationError):
            CSPPaymentEstimate(**data)

    def test_negative_eap_annual_raises(self):
        with pytest.raises(ValidationError):
            CSPPaymentEstimate(**self._valid(eap_annual=-100.0))

    def test_negative_activity_payment_annual_raises(self):
        with pytest.raises(ValidationError):
            CSPPaymentEstimate(**self._valid(activity_payment_annual=-1.0))

    def test_negative_total_annual_raises(self):
        with pytest.raises(ValidationError):
            CSPPaymentEstimate(**self._valid(total_annual_payment=-5000.0))

    def test_negative_eligible_acres_raises(self):
        with pytest.raises(ValidationError):
            CSPPaymentEstimate(**self._valid(eligible_acres=-10.0))

    def test_negative_resource_concerns_raises(self):
        with pytest.raises(ValidationError):
            CSPPaymentEstimate(**self._valid(resource_concerns_addressed=-1))

    def test_payment_capped_defaults_to_false(self):
        data = self._valid()
        del data["payment_capped"]
        est = CSPPaymentEstimate(**data)
        assert est.payment_capped is False

    def test_activities_included_defaults_to_empty(self):
        data = self._valid()
        del data["activities_included"]
        est = CSPPaymentEstimate(**data)
        assert est.activities_included == []

    def test_field_breakdown_defaults_to_empty_list(self):
        data = self._valid()
        del data["field_breakdown"]
        est = CSPPaymentEstimate(**data)
        assert est.field_breakdown == []

    def test_missing_state_raises(self):
        data = self._valid()
        del data["state"]
        with pytest.raises(ValidationError):
            CSPPaymentEstimate(**data)


# ---------------------------------------------------------------------------
# CSPEnhancementActivity
# ---------------------------------------------------------------------------

class TestCSPEnhancementActivity:
    def _valid(self, **overrides):
        data = {
            "code": "340",
            "practice_standard_code": "340",
            "name": "Cover Crop",
            "category": "soil_health",
            "land_use": "cropland",
            "description": "Multi-species cover crop mix to improve soil health",
            "estimated_rate_per_acre": 9.0,
            "rate_is_estimate": True,
            "rate_basis": "Pre-FY2026 estimate, pending FY2026 state payment schedule",
            "estimated_annual_payment": 1800.0,
            "applicable_acres": 200.0,
            "resource_concerns_addressed": ["soil_health", "water_quality"],
            "priority_score": 4.0,
            "higher_payment": True,
            "higher_payment_category": "Cover crop activities",
        }
        data.update(overrides)
        return data

    def test_valid_model_creates(self):
        act = CSPEnhancementActivity(**self._valid())
        assert act.code == "340"
        assert act.practice_standard_code == "340"

    def test_negative_rate_per_acre_raises(self):
        with pytest.raises(ValidationError):
            CSPEnhancementActivity(**self._valid(estimated_rate_per_acre=-1.0))

    def test_negative_applicable_acres_raises(self):
        with pytest.raises(ValidationError):
            CSPEnhancementActivity(**self._valid(applicable_acres=-10.0))

    def test_negative_estimated_annual_payment_raises(self):
        with pytest.raises(ValidationError):
            CSPEnhancementActivity(**self._valid(estimated_annual_payment=-1.0))

    def test_land_use_defaults_to_cropland(self):
        data = self._valid()
        del data["land_use"]
        act = CSPEnhancementActivity(**data)
        assert act.land_use == "cropland"

    def test_rate_is_estimate_defaults_to_true(self):
        data = self._valid()
        del data["rate_is_estimate"]
        act = CSPEnhancementActivity(**data)
        assert act.rate_is_estimate is True

    def test_priority_score_defaults_to_zero(self):
        data = self._valid()
        del data["priority_score"]
        act = CSPEnhancementActivity(**data)
        assert act.priority_score == 0.0

    def test_higher_payment_defaults_to_false(self):
        data = self._valid()
        del data["higher_payment"]
        del data["higher_payment_category"]
        act = CSPEnhancementActivity(**data)
        assert act.higher_payment is False
        assert act.higher_payment_category is None

    def test_missing_code_raises(self):
        data = self._valid()
        del data["code"]
        with pytest.raises(ValidationError):
            CSPEnhancementActivity(**data)

    def test_resource_concerns_addressed_defaults_empty(self):
        data = self._valid()
        del data["resource_concerns_addressed"]
        act = CSPEnhancementActivity(**data)
        assert act.resource_concerns_addressed == []


# ---------------------------------------------------------------------------
# CSPEligibilityResponse
# ---------------------------------------------------------------------------

class TestCSPEligibilityResponse:
    def _valid_concern(self):
        return CSPResourceConcern(
            concern_id="soil_health",
            name="Soil Health",
            category="soil_health",
            meets_threshold=True,
            points_earned=12.0,
            points_possible=20.0,
        )

    def _valid(self, **overrides):
        data = {
            "farm_id": FARM_ID,
            "status": CSPApplicationStatus.act_now,
            "is_eligible": True,
            "resource_concerns_meeting_threshold": 3,
            "min_concerns_required": 2,
            "additional_concerns_required": 1,
            "contract_years": 5,
            "resource_concerns_detail": [self._valid_concern()],
            "cart_score": 49.5,
            "state_ranking_threshold": 47.0,
            "meets_ranking_threshold": True,
            "eligibility_notes": "Farm may qualify for the ACT NOW fast-track if your state offers it.",
            "recommended_enhancements": [],
            "is_estimate": True,
            "scoring_rules": csp_scoring_rules_metadata(),
            "evaluated_at": NOW,
        }
        data.update(overrides)
        return data

    def test_valid_model_creates(self):
        resp = CSPEligibilityResponse(**self._valid())
        assert resp.status == CSPApplicationStatus.act_now
        assert resp.is_eligible is True

    def test_unknown_threshold_fields_accept_none(self):
        resp = CSPEligibilityResponse(
            **self._valid(
                status=CSPApplicationStatus.eligible,
                state_ranking_threshold=None,
                meets_ranking_threshold=None,
                scoring_rules=csp_scoring_rules_metadata("TX"),
            )
        )
        assert resp.state_ranking_threshold is None
        assert resp.meets_ranking_threshold is None
        assert resp.scoring_rules.state_ranking_threshold.status == "not_published"

    def test_all_four_statuses_accepted(self):
        for s in CSPApplicationStatus:
            resp = CSPEligibilityResponse(**self._valid(status=s))
            assert resp.status == s

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            CSPEligibilityResponse(**self._valid(status="UNKNOWN"))

    def test_negative_cart_score_raises(self):
        with pytest.raises(ValidationError):
            CSPEligibilityResponse(**self._valid(cart_score=-1.0))

    def test_negative_resource_concerns_meeting_raises(self):
        with pytest.raises(ValidationError):
            CSPEligibilityResponse(**self._valid(resource_concerns_meeting_threshold=-1))

    def test_resource_concerns_detail_defaults_empty(self):
        data = self._valid()
        del data["resource_concerns_detail"]
        resp = CSPEligibilityResponse(**data)
        assert resp.resource_concerns_detail == []

    def test_recommended_enhancements_defaults_empty(self):
        data = self._valid()
        del data["recommended_enhancements"]
        resp = CSPEligibilityResponse(**data)
        assert resp.recommended_enhancements == []

    def test_missing_is_eligible_raises(self):
        data = self._valid()
        del data["is_eligible"]
        with pytest.raises(ValidationError):
            CSPEligibilityResponse(**data)

    def test_missing_eligibility_notes_raises(self):
        data = self._valid()
        del data["eligibility_notes"]
        with pytest.raises(ValidationError):
            CSPEligibilityResponse(**data)

    def test_status_coerced_from_string(self):
        """Enum fields should accept raw strings for convenience."""
        resp = CSPEligibilityResponse(**self._valid(status="eligible"))
        assert resp.status == CSPApplicationStatus.eligible

    def test_string_evaluated_at_parsed(self):
        """ISO datetime strings should be accepted for evaluated_at."""
        resp = CSPEligibilityResponse(**self._valid(evaluated_at="2026-04-06T12:00:00+00:00"))
        assert isinstance(resp.evaluated_at, datetime)
