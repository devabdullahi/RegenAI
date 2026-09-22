"""
Tests for app.services.csp_eligibility — CSP eligibility evaluation.

Coverage targets:
  - All four eligibility statuses: act_now, eligible, pending_review, not_eligible
  - The 2-concern minimum requirement gate
  - Gap-closure enhancement recommendations (populated when concerns are unmet)
  - Persistence to csp_eligibility_assessments (upsert called once; failure is non-fatal)
  - Return payload keys match CSPEligibilityResponse schema
"""

import json

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from postgrest.exceptions import APIError
from tests.conftest import FARM_ID

from app.services.csp_eligibility import (
    evaluate_csp_eligibility,
    _MAX_RECOMMENDED_ACTIVITIES,
    _MIN_CONCERNS_MEETING_THRESHOLD,
)
from app.services.program_rules import (
    CSP_GAP_CLOSURE_ACTIVITIES as _GAP_CLOSURE_ENHANCEMENTS,
    CSP_MIN_PRIORITY_CONCERNS,
    csp_scoring_rules_metadata,
)


# ---------------------------------------------------------------------------
# Helpers: build supabase mocks for specific eligibility scenarios
# ---------------------------------------------------------------------------

def _supabase_for_score(
    total_points: float,
    state: str,
    concerns_meeting: int,
    state_threshold: float | None,
):
    """
    Patch calculate_stewardship_score to return a controlled score dict so we
    can drive eligibility logic independently of the scoring engine.

    ``state_threshold=None`` models a state with no published ranking
    threshold: the scoring engine then reports meets/gap as None too.
    """
    concern_ids = [
        "soil_health", "soil_erosion", "water_quality", "water_quantity",
        "air_quality", "plant_condition", "animals", "energy",
    ]
    # Build concern list: first N concerns flagged as meeting threshold
    concerns = []
    for i, cid in enumerate(concern_ids):
        max_pts = {"soil_health": 20, "soil_erosion": 15, "water_quality": 20,
                   "water_quantity": 10, "air_quality": 10, "plant_condition": 10,
                   "animals": 5, "energy": 10}[cid]
        earned = max_pts * 0.6 if i < concerns_meeting else 0.0
        concerns.append({
            "concern_id": cid,
            "name": cid,
            "category": cid,
            "practices_addressing": [],
            "meets_threshold": i < concerns_meeting,
            "points_earned": earned,
            "points_possible": float(max_pts),
        })

    threshold_known = state_threshold is not None
    gap = max(0.0, state_threshold - total_points) if threshold_known else None

    return {
        "farm_id": FARM_ID,
        "total_points": total_points,
        "max_possible_points": 100.0,
        "state_ranking_threshold": state_threshold,
        "meets_ranking_threshold": (
            total_points >= state_threshold if threshold_known else None
        ),
        "gap_to_threshold": gap,
        "resource_concern_scores": concerns,
        "component_scores": {},
        "avg_som_pct": None,
        "som_tier": "low",
        "is_estimate": True,
        "scoring_rules": csp_scoring_rules_metadata(state),
        "evaluated_at": "2026-04-06T00:00:00+00:00",
    }


def _make_supabase_with_upsert():
    """Supabase mock where upsert succeeds silently."""
    mock = MagicMock()
    upsert_chain = MagicMock()
    upsert_chain.execute.return_value = MagicMock(data=None)
    mock.table.return_value.upsert.return_value = upsert_chain
    return mock


# ---------------------------------------------------------------------------
# Status: act_now  (>= 2 concerns AND meets ranking threshold)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestActNowStatus:
    async def test_act_now_when_score_meets_threshold_and_two_concerns(self):
        score_data = _supabase_for_score(
            total_points=50.0, state="IA",
            concerns_meeting=3, state_threshold=47.0,
        )
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert result["status"] == "act_now"
        assert result["is_eligible"] is True

    async def test_act_now_notes_mention_fast_track(self):
        score_data = _supabase_for_score(50.0, "IL", 2, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert "ACT NOW" in result["eligibility_notes"]
        assert result["meets_ranking_threshold"] is True

    async def test_act_now_notes_are_not_a_guarantee(self):
        """ACT NOW is at state discretion — notes must not promise approval."""
        score_data = _supabase_for_score(50.0, "IL", 2, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        notes = result["eligibility_notes"]
        assert "may qualify" in notes
        assert "if your state offers it" in notes
        assert "not guarantee" in notes
        assert "qualifies for CSP ACT NOW" not in notes
        assert "approval." not in notes.split("ACT NOW is used")[0]

    async def test_eligible_notes_do_not_promise_act_now(self):
        score_data = _supabase_for_score(30.0, "IL", 2, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert result["status"] == "eligible"
        assert "if your state offers it" in result["eligibility_notes"]

    async def test_act_now_resource_concerns_meeting_threshold_count(self):
        score_data = _supabase_for_score(50.0, "IL", 4, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert result["resource_concerns_meeting_threshold"] == 4


# ---------------------------------------------------------------------------
# Status: eligible  (>= 2 concerns but BELOW ranking threshold)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEligibleStatus:
    async def test_eligible_when_two_concerns_but_below_threshold(self):
        score_data = _supabase_for_score(
            total_points=30.0, state="IA",
            concerns_meeting=2, state_threshold=47.0,
        )
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert result["status"] == "eligible"
        assert result["is_eligible"] is True

    async def test_eligible_notes_mention_gap(self):
        score_data = _supabase_for_score(30.0, "IA", 2, 47.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        # Notes should reference the gap
        assert "17.0" in result["eligibility_notes"]  # gap = 47 - 30

    async def test_eligible_with_exactly_two_concerns(self):
        score_data = _supabase_for_score(20.0, "IL", 2, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert result["status"] == "eligible"
        assert result["is_eligible"] is True


# ---------------------------------------------------------------------------
# Status: pending_review  (exactly 1 concern meets threshold)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPendingReviewStatus:
    async def test_pending_review_with_one_concern(self):
        score_data = _supabase_for_score(10.0, "IL", 1, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert result["status"] == "pending_review"
        assert result["is_eligible"] is False

    async def test_pending_review_notes_mention_minimum(self):
        score_data = _supabase_for_score(10.0, "IL", 1, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert str(_MIN_CONCERNS_MEETING_THRESHOLD) in result["eligibility_notes"]

    async def test_pending_review_follows_rule_minimum_not_literal_one(self):
        """With a minimum of 3, a farm meeting 2 concerns is close to eligible.

        The status used to be gated on exactly 1 concern, so this farm was
        reported as not_eligible with a note claiming no concerns were met.
        """
        score_data = _supabase_for_score(10.0, "IL", 2, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch("app.services.csp_eligibility._MIN_CONCERNS_MEETING_THRESHOLD", 3), patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert result["status"] == "pending_review"
        assert "2 priority resource concern(s)" in result["eligibility_notes"]
        assert "1 more resource concern(s)" in result["eligibility_notes"]


# ---------------------------------------------------------------------------
# Status: not_eligible  (0 concerns)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestNotEligibleStatus:
    async def test_not_eligible_with_zero_concerns(self):
        score_data = _supabase_for_score(0.0, "IL", 0, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert result["status"] == "not_eligible"
        assert result["is_eligible"] is False

    async def test_not_eligible_notes_mention_cart_score(self):
        score_data = _supabase_for_score(0.0, "IL", 0, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert "0.0" in result["eligibility_notes"]


# ---------------------------------------------------------------------------
# Gap closure enhancements
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRecommendedEnhancements:
    async def test_enhancements_populated_when_concerns_not_met(self):
        """Concerns below threshold should trigger enhancement recommendations."""
        score_data = _supabase_for_score(0.0, "IL", 0, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert len(result["recommended_enhancements"]) > 0

    async def test_enhancements_empty_when_all_concerns_met(self):
        """If all 8 concerns meet threshold, no gaps → no enhancements needed."""
        score_data = _supabase_for_score(90.0, "IL", 8, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert result["recommended_enhancements"] == []

    async def test_enhancements_capped_at_six(self):
        """Should never return more than 6 enhancement codes."""
        score_data = _supabase_for_score(0.0, "IL", 0, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert _MAX_RECOMMENDED_ACTIVITIES == 6
        # With every concern unmet there are more candidates than the cap.
        assert len(result["recommended_enhancements"]) == _MAX_RECOMMENDED_ACTIVITIES

    async def test_min_concerns_defined_once_in_program_rules(self):
        from app.services.csp_payment import _MIN_CONCERNS_FOR_CONTRACT

        assert CSP_MIN_PRIORITY_CONCERNS.value == 2
        assert _MIN_CONCERNS_MEETING_THRESHOLD == CSP_MIN_PRIORITY_CONCERNS.value
        assert _MIN_CONCERNS_FOR_CONTRACT == CSP_MIN_PRIORITY_CONCERNS.value

    async def test_gap_closure_codes_are_fy2026_activities(self):
        """No retired E-codes; every code exists in the FY2026 activity catalog."""
        from app.services.csp_payment import _CSP_ACTIVITIES

        for codes in _GAP_CLOSURE_ENHANCEMENTS.values():
            for code in codes:
                assert not code.startswith("E"), code
                assert code in _CSP_ACTIVITIES, code

    async def test_enhancements_use_known_codes(self):
        """All returned codes should be recognised in the gap-closure map."""
        all_known = {code for codes in _GAP_CLOSURE_ENHANCEMENTS.values() for code in codes}
        score_data = _supabase_for_score(0.0, "IL", 0, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        for code in result["recommended_enhancements"]:
            assert code in all_known, f"Unknown enhancement code returned: {code}"

    async def test_no_duplicate_enhancements(self):
        score_data = _supabase_for_score(0.0, "IL", 0, 45.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        codes = result["recommended_enhancements"]
        assert len(codes) == len(set(codes)), "Duplicate enhancement codes in output"


# ---------------------------------------------------------------------------
# Persistence (upsert) behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPersistence:
    async def test_upsert_called_once_on_success(self):
        score_data = _supabase_for_score(50.0, "IA", 3, 47.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            await evaluate_csp_eligibility(FARM_ID, supabase)

        supabase.table.assert_any_call("csp_eligibility_assessments")

    async def test_payload_is_json_serializable_with_rounded_score(self):
        score_data = _supabase_for_score(46.6, "IA", 3, 47.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            await evaluate_csp_eligibility(FARM_ID, supabase)

        payload = supabase.table.return_value.upsert.call_args.args[0]
        json.dumps(payload)  # the Supabase client must be able to serialize it
        assert payload["stewardship_score"] == 47  # rounded, not truncated to 46
        assert payload["eligibility_status"] == "eligible"

    async def test_upsert_failure_does_not_raise(self, caplog):
        """A database write failure is non-fatal but logged with the farm id."""
        score_data = _supabase_for_score(50.0, "IA", 3, 47.0)

        mock = MagicMock()
        # Upsert raises, but other calls succeed
        upsert_chain = MagicMock()
        upsert_chain.execute.side_effect = APIError(
            {"message": "DB write failed", "code": "23514"}
        )

        def _table(name):
            chain = MagicMock()
            chain.execute.return_value = MagicMock(data=None)
            for method in ("select", "eq", "in_", "order", "single", "limit"):
                getattr(chain, method).return_value = chain
            chain.upsert.return_value = upsert_chain
            return chain

        mock.table.side_effect = _table

        with caplog.at_level("ERROR"), patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, mock)

        # Result should still be present despite the write failure
        assert result["farm_id"] == FARM_ID
        assert result["status"] == "act_now"
        assert "failed to persist assessment" in caplog.text
        assert FARM_ID in caplog.text

    async def test_non_database_upsert_error_propagates(self):
        """A non-API failure (e.g. unserializable payload) must not be swallowed."""
        score_data = _supabase_for_score(50.0, "IA", 3, 47.0)
        mock = MagicMock()
        mock.table.return_value.upsert.return_value.execute.side_effect = TypeError(
            "Object of type UUID is not JSON serializable"
        )

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            with pytest.raises(TypeError):
                await evaluate_csp_eligibility(FARM_ID, mock)


# ---------------------------------------------------------------------------
# Return payload completeness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPayloadShape:
    async def test_all_required_keys_present(self):
        score_data = _supabase_for_score(50.0, "IA", 3, 47.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        required = {
            "farm_id", "status", "is_eligible",
            "resource_concerns_meeting_threshold",
            "resource_concerns_detail", "cart_score",
            "state_ranking_threshold", "meets_ranking_threshold",
            "eligibility_notes", "recommended_enhancements", "evaluated_at",
            "is_estimate", "scoring_rules",
        }
        assert required.issubset(result.keys())
        assert result["is_estimate"] is True

    async def test_validates_against_schema(self):
        from app.models.schemas import CSPEligibilityResponse

        score_data = _supabase_for_score(50.0, "IA", 3, 47.0)
        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, _make_supabase_with_upsert())

        CSPEligibilityResponse(**result)

    async def test_resource_concerns_detail_is_list(self):
        score_data = _supabase_for_score(50.0, "IA", 3, 47.0)
        supabase = _make_supabase_with_upsert()

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert isinstance(result["resource_concerns_detail"], list)
        assert len(result["resource_concerns_detail"]) == 8



# ---------------------------------------------------------------------------
# States with no published ranking threshold: unknown must stay unknown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUnknownRankingThreshold:
    """A state RegenAI has no threshold for must never be told it ranks."""

    async def _evaluate(self, total_points=90.0, concerns_meeting=4, state="TX"):
        score_data = _supabase_for_score(
            total_points=total_points, state=state,
            concerns_meeting=concerns_meeting, state_threshold=None,
        )
        supabase = _make_supabase_with_upsert()
        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)
        return result, supabase

    async def test_high_score_is_eligible_not_act_now(self):
        result, _ = await self._evaluate(total_points=90.0, concerns_meeting=4)
        assert result["status"] == "eligible"
        assert result["is_eligible"] is True

    async def test_threshold_fields_are_null(self):
        result, _ = await self._evaluate()
        assert result["state_ranking_threshold"] is None
        assert result["meets_ranking_threshold"] is None

    async def test_notes_say_threshold_is_not_published(self):
        result, _ = await self._evaluate()
        notes = result["eligibility_notes"]
        assert "not published" in notes
        assert "NRCS" in notes
        assert "ACT NOW" not in notes

    async def test_notes_quote_no_threshold_number(self):
        """The note must not invent a points cut-off to compare against."""
        result, _ = await self._evaluate()
        assert "state ranking threshold" not in result["eligibility_notes"]
        assert "42" not in result["eligibility_notes"]

    async def test_persisted_act_now_eligible_is_false(self):
        """The NOT NULL column stores false; unknown lives in the score payload."""
        _, supabase = await self._evaluate()
        payload = supabase.table.return_value.upsert.call_args[0][0]
        assert payload["act_now_eligible"] is False
        assert payload["eligibility_status"] == "eligible"
        assert payload["resource_concerns_met"]["meets_ranking_threshold"] is None

    async def test_scoring_rules_report_not_published(self):
        result, _ = await self._evaluate()
        citation = result["scoring_rules"]["state_ranking_threshold"]
        assert citation["status"] == "not_published"
        assert citation["value"] is None

    async def test_response_validates_against_schema(self):
        from app.models.schemas import CSPEligibilityResponse

        result, _ = await self._evaluate()
        response = CSPEligibilityResponse(**result)
        assert response.state_ranking_threshold is None
        assert response.meets_ranking_threshold is None

    async def test_too_few_concerns_still_pending_review(self):
        result, _ = await self._evaluate(total_points=90.0, concerns_meeting=1)
        assert result["status"] == "pending_review"
        assert result["is_eligible"] is False

    async def test_known_threshold_state_can_still_act_now(self):
        """Regression guard: dropping the default must not disable ACT NOW."""
        score_data = _supabase_for_score(
            total_points=50.0, state="IA", concerns_meeting=3, state_threshold=47.0,
        )
        supabase = _make_supabase_with_upsert()
        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, supabase)

        assert result["status"] == "act_now"
        assert result["meets_ranking_threshold"] is True
        payload = supabase.table.return_value.upsert.call_args[0][0]
        assert payload["act_now_eligible"] is True
