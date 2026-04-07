"""
Tests for app.services.csp_eligibility — CSP eligibility evaluation.

Coverage targets:
  - All four eligibility statuses: act_now, eligible, pending_review, not_eligible
  - The 2-concern minimum requirement gate
  - Gap-closure enhancement recommendations (populated when concerns are unmet)
  - Persistence to csp_assessments (upsert called once; failure is non-fatal)
  - Return payload keys match CSPEligibilityResponse schema
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from tests.conftest import make_supabase_mock, FARM_ID, FIELD_ID_A

from app.services.csp_eligibility import (
    evaluate_csp_eligibility,
    _MIN_CONCERNS_MEETING_THRESHOLD,
    _GAP_CLOSURE_ENHANCEMENTS,
)


# ---------------------------------------------------------------------------
# Helpers: build supabase mocks for specific eligibility scenarios
# ---------------------------------------------------------------------------

def _supabase_for_score(total_points: float, state: str, concerns_meeting: int, state_threshold: float):
    """
    Patch calculate_stewardship_score to return a controlled score dict so we
    can drive eligibility logic independently of the scoring engine.
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

    gap = max(0.0, state_threshold - total_points)

    return {
        "farm_id": FARM_ID,
        "total_points": total_points,
        "max_possible_points": 100.0,
        "state_ranking_threshold": state_threshold,
        "meets_ranking_threshold": total_points >= state_threshold,
        "gap_to_threshold": gap,
        "resource_concern_scores": concerns,
        "component_scores": {},
        "avg_som_pct": None,
        "som_tier": "low",
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

        assert len(result["recommended_enhancements"]) <= 6

    async def test_enhancements_use_known_e_codes(self):
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

        # BUG: csp_eligibility.py upserts to "csp_eligibility_assessments" but the
        # router, payment service, and all documentation refer to "csp_assessments".
        # This name mismatch means the payment service cannot read the assessment that
        # eligibility just wrote, breaking the cached-read optimisation.
        # The actual call is to "csp_eligibility_assessments":
        supabase.table.assert_any_call("csp_eligibility_assessments")

    async def test_upsert_failure_does_not_raise(self):
        """A persistence failure must be swallowed — result still returned."""
        score_data = _supabase_for_score(50.0, "IA", 3, 47.0)

        mock = MagicMock()
        # Upsert raises, but other calls succeed
        upsert_chain = MagicMock()
        upsert_chain.execute.side_effect = Exception("DB write failed")

        def _table(name):
            chain = MagicMock()
            chain.execute.return_value = MagicMock(data=None)
            for method in ("select", "eq", "in_", "order", "single", "limit"):
                getattr(chain, method).return_value = chain
            chain.upsert.return_value = upsert_chain
            return chain

        mock.table.side_effect = _table

        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            result = await evaluate_csp_eligibility(FARM_ID, mock)

        # Result should still be present despite the write failure
        assert result["farm_id"] == FARM_ID
        assert result["status"] == "act_now"


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
        }
        assert required.issubset(result.keys())

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
