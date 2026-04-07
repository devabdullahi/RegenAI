"""
Tests for app.services.csp_scoring — CART stewardship scoring engine.

Coverage targets:
  - Stewardship point calculation with various practice combinations
  - SOM bonus multiplier logic (_get_som_tier + application)
  - State ranking threshold lookup and comparison
  - Gap analysis in the returned payload
  - Empty-practice case (should return 0 total score)
  - Concern clamping to per-category max
  - Farm-not-found raises ValueError
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from tests.conftest import make_supabase_mock, FARM_ID, FIELD_ID_A

from app.services.csp_scoring import (
    _get_som_tier,
    _get_ranking_threshold,
    _collect_practices,
    _MAX_POINTS_PER_CONCERN,
    _MAX_TOTAL_POINTS,
    _STATE_RANKING_THRESHOLDS,
    calculate_stewardship_score,
)


# ---------------------------------------------------------------------------
# Unit tests for private helpers (no I/O)
# ---------------------------------------------------------------------------

class TestGetSomTier:
    def test_none_returns_low(self):
        assert _get_som_tier(None) == "low"

    def test_below_1_5_is_poor(self):
        assert _get_som_tier(1.4) == "poor"
        assert _get_som_tier(0.0) == "poor"

    def test_boundary_1_5_is_low(self):
        assert _get_som_tier(1.5) == "low"

    def test_between_1_5_and_2_5_is_low(self):
        assert _get_som_tier(2.0) == "low"

    def test_boundary_2_5_is_medium(self):
        assert _get_som_tier(2.5) == "medium"

    def test_between_2_5_and_4_is_medium(self):
        assert _get_som_tier(3.9) == "medium"

    def test_boundary_4_0_is_high(self):
        assert _get_som_tier(4.0) == "high"

    def test_above_4_is_high(self):
        assert _get_som_tier(6.0) == "high"


class TestGetRankingThreshold:
    def test_known_states(self):
        assert _get_ranking_threshold("IA") == 47.0
        assert _get_ranking_threshold("IL") == 45.0
        assert _get_ranking_threshold("ND") == 38.0

    def test_case_insensitive(self):
        assert _get_ranking_threshold("ia") == _get_ranking_threshold("IA")
        assert _get_ranking_threshold("mn") == _get_ranking_threshold("MN")

    def test_unknown_state_returns_default(self):
        assert _get_ranking_threshold("TX") == _STATE_RANKING_THRESHOLDS["_default"]
        assert _get_ranking_threshold("CA") == _STATE_RANKING_THRESHOLDS["_default"]


class TestCollectPractices:
    def test_empty_fields_returns_empty_set(self):
        assert _collect_practices([]) == set()

    def test_single_field_single_practice(self):
        fields = [{"practices": ["340"]}]
        result = _collect_practices(fields)
        assert result == {"340"}

    def test_practices_are_normalised_to_uppercase(self):
        fields = [{"practices": ["340", "329"]}]
        result = _collect_practices(fields)
        assert "340" in result
        assert "329" in result

    def test_deduplicates_across_fields(self):
        fields = [
            {"practices": ["340", "329"]},
            {"practices": ["329", "590"]},
        ]
        result = _collect_practices(fields)
        assert result == {"340", "329", "590"}

    def test_fields_with_none_practices(self):
        fields = [{"practices": None}, {"practices": ["340"]}]
        result = _collect_practices(fields)
        assert result == {"340"}

    def test_fields_with_missing_practices_key(self):
        fields = [{}, {"practices": ["590"]}]
        result = _collect_practices(fields)
        assert result == {"590"}

    def test_strips_whitespace_from_codes(self):
        fields = [{"practices": [" 340 ", "329"]}]
        result = _collect_practices(fields)
        assert "340" in result


class TestMaxTotalPoints:
    def test_max_sums_to_100(self):
        assert _MAX_TOTAL_POINTS == 100.0

    def test_all_eight_concerns_present(self):
        assert len(_MAX_POINTS_PER_CONCERN) == 8


# ---------------------------------------------------------------------------
# Integration tests — calculate_stewardship_score (mocked Supabase)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCalculateStewardshipScore:

    async def test_empty_practices_returns_zero_score(self):
        """A farm with no practices should score 0 on every concern."""
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IA", "total_acres": 100.0}},
                "fields": {"data": [{"id": FIELD_ID_A, "name": "F1", "acres": 100.0, "crop_type": "corn", "practices": []}]},
                "soil_profiles": {"data": []},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)

        assert result["total_points"] == 0.0
        assert result["farm_id"] == FARM_ID
        for concern in result["resource_concern_scores"]:
            assert concern["points_earned"] == 0.0
            assert concern["meets_threshold"] is False

    async def test_no_field_practices_no_acted_recs_scores_zero(self):
        """Fields list empty and no recs → zero score."""
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IL", "total_acres": 50.0}},
                "fields": {"data": []},
                "soil_profiles": {"data": []},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)
        assert result["total_points"] == 0.0

    async def test_cover_crop_addresses_soil_health_water_quality_air(self):
        """Practice 340 (Cover Crop) should contribute to soil_health, water_quality, air_quality."""
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IL", "total_acres": 100.0}},
                "fields": {"data": [{"id": FIELD_ID_A, "name": "F", "acres": 100.0, "crop_type": "corn", "practices": ["340"]}]},
                "soil_profiles": {"data": []},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)
        component = result["component_scores"]

        assert component["soil_health"] > 0.0
        assert component["water_quality"] > 0.0
        assert component["air_quality"] > 0.0
        # Concerns practice 340 does NOT address
        assert component["water_quantity"] == 0.0
        assert component["animals"] == 0.0
        assert component["energy"] == 0.0

    async def test_high_som_boosts_soil_health_score(self):
        """SOM >= 4.0% should apply the 1.5× bonus multiplier to soil_health."""
        base_supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IL", "total_acres": 100.0}},
                "fields": {"data": [{"id": FIELD_ID_A, "name": "F", "acres": 100.0, "crop_type": "corn", "practices": ["340"]}]},
                "soil_profiles": {"data": [{"field_id": FIELD_ID_A, "organic_matter_pct": 1.5}]},
                "recommendations": {"data": []},
            }
        )
        high_som_supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IL", "total_acres": 100.0}},
                "fields": {"data": [{"id": FIELD_ID_A, "name": "F", "acres": 100.0, "crop_type": "corn", "practices": ["340"]}]},
                "soil_profiles": {"data": [{"field_id": FIELD_ID_A, "organic_matter_pct": 5.0}]},
                "recommendations": {"data": []},
            }
        )

        base_result = await calculate_stewardship_score(FARM_ID, base_supabase)
        high_result = await calculate_stewardship_score(FARM_ID, high_som_supabase)

        assert high_result["component_scores"]["soil_health"] > base_result["component_scores"]["soil_health"]
        assert high_result["som_tier"] == "high"
        assert base_result["som_tier"] == "low"

    async def test_poor_som_reduces_soil_health_score(self):
        """SOM < 1.5% should apply the 0.7× penalty multiplier to soil_health."""
        poor_som_supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IL", "total_acres": 100.0}},
                "fields": {"data": [{"id": FIELD_ID_A, "name": "F", "acres": 100.0, "crop_type": "corn", "practices": ["340"]}]},
                "soil_profiles": {"data": [{"field_id": FIELD_ID_A, "organic_matter_pct": 0.8}]},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, poor_som_supabase)
        assert result["som_tier"] == "poor"
        # 340 base_pts = 5.0, × 0.7 = 3.5 for soil_health
        assert result["component_scores"]["soil_health"] == pytest.approx(3.5, abs=0.01)

    async def test_soil_health_score_clamped_to_category_max(self):
        """Many soil-health practices + high SOM must not exceed the 20-pt cap."""
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IA", "total_acres": 100.0}},
                "fields": {"data": [{"id": FIELD_ID_A, "name": "F", "acres": 100.0, "crop_type": "corn",
                                     "practices": ["327", "328", "329", "340"]}]},
                "soil_profiles": {"data": [{"field_id": FIELD_ID_A, "organic_matter_pct": 5.0}]},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)
        assert result["component_scores"]["soil_health"] <= 20.0

    async def test_state_ranking_threshold_ia(self):
        """Iowa's threshold (47.0) should appear in the result."""
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IA", "total_acres": 100.0}},
                "fields": {"data": []},
                "soil_profiles": {"data": []},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)
        assert result["state_ranking_threshold"] == 47.0

    async def test_meets_ranking_threshold_true_when_score_above(self):
        """A farm with many practices should exceed the state threshold."""
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "ND", "total_acres": 100.0}},
                # ND threshold = 38.0 (lowest), many practices → should exceed it
                "fields": {"data": [{"id": FIELD_ID_A, "name": "F", "acres": 100.0, "crop_type": "corn",
                                     "practices": ["340", "329", "328", "590", "393", "412", "612"]}]},
                "soil_profiles": {"data": [{"field_id": FIELD_ID_A, "organic_matter_pct": 4.5}]},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)
        assert result["meets_ranking_threshold"] is True
        assert result["gap_to_threshold"] == 0.0

    async def test_gap_to_threshold_calculated_correctly(self):
        """gap_to_threshold must equal max(0, threshold - total_points)."""
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IA", "total_acres": 100.0}},
                "fields": {"data": [{"id": FIELD_ID_A, "name": "F", "acres": 100.0, "crop_type": "corn",
                                     "practices": ["590"]}]},
                "soil_profiles": {"data": []},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)
        expected_gap = max(0.0, result["state_ranking_threshold"] - result["total_points"])
        assert result["gap_to_threshold"] == pytest.approx(expected_gap, abs=0.01)

    async def test_acted_recommendations_contribute_to_score(self):
        """Acted recommendations with practice codes should raise the total."""
        # Without acted recs (only 590)
        no_recs = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IL", "total_acres": 100.0}},
                "fields": {"data": [{"id": FIELD_ID_A, "name": "F", "acres": 100.0, "crop_type": "corn", "practices": ["590"]}]},
                "soil_profiles": {"data": []},
                "recommendations": {"data": []},
            }
        )
        # With an acted rec for cover crop (340)
        with_recs = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IL", "total_acres": 100.0}},
                "fields": {"data": [{"id": FIELD_ID_A, "name": "F", "acres": 100.0, "crop_type": "corn", "practices": ["590"]}]},
                "soil_profiles": {"data": []},
                "recommendations": {"data": [{"practice_code": "340"}]},
            }
        )

        score_no_recs = await calculate_stewardship_score(FARM_ID, no_recs)
        score_with_recs = await calculate_stewardship_score(FARM_ID, with_recs)

        assert score_with_recs["total_points"] > score_no_recs["total_points"]

    async def test_response_contains_required_keys(self):
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IL", "total_acres": 100.0}},
                "fields": {"data": []},
                "soil_profiles": {"data": []},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)
        required = {
            "farm_id", "total_points", "max_possible_points",
            "state_ranking_threshold", "meets_ranking_threshold",
            "gap_to_threshold", "resource_concern_scores",
            "component_scores", "avg_som_pct", "som_tier", "evaluated_at",
        }
        assert required.issubset(result.keys())

    async def test_resource_concern_scores_has_eight_entries(self):
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IL", "total_acres": 100.0}},
                "fields": {"data": []},
                "soil_profiles": {"data": []},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)
        assert len(result["resource_concern_scores"]) == 8

    async def test_farm_not_found_raises_value_error(self):
        """Supabase returning no farm data must raise ValueError."""
        supabase = make_supabase_mock({"farms": {"data": None}})
        with pytest.raises(ValueError, match=FARM_ID):
            await calculate_stewardship_score(FARM_ID, supabase)

    async def test_farm_fetch_exception_raises_value_error(self):
        """If the DB call itself blows up, we should get ValueError."""
        supabase = MagicMock()
        supabase.table.side_effect = Exception("connection timeout")
        with pytest.raises(ValueError):
            await calculate_stewardship_score(FARM_ID, supabase)

    async def test_avg_som_computed_from_multiple_fields(self):
        """avg_som_pct must be the mean of per-field SOM readings."""
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IA", "total_acres": 200.0}},
                "fields": {"data": [
                    {"id": "f1", "name": "A", "acres": 100.0, "crop_type": "corn", "practices": []},
                    {"id": "f2", "name": "B", "acres": 100.0, "crop_type": "corn", "practices": []},
                ]},
                "soil_profiles": {"data": [
                    {"field_id": "f1", "organic_matter_pct": 3.0},
                    {"field_id": "f2", "organic_matter_pct": 1.0},
                ]},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)
        assert result["avg_som_pct"] == pytest.approx(2.0, abs=0.01)

    async def test_meets_threshold_flag_per_concern(self):
        """Only concerns where earned >= 50% of max should be flagged True."""
        # Practice 590 gives 4 pts to water_quality (max 20, threshold 10) → False
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "IL", "total_acres": 100.0}},
                "fields": {"data": [{"id": FIELD_ID_A, "name": "F", "acres": 100.0, "crop_type": "corn",
                                     "practices": ["590"]}]},
                "soil_profiles": {"data": []},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)
        water_q = next(c for c in result["resource_concern_scores"] if c["concern_id"] == "water_quality")
        # 590 → 4 pts, threshold = 10 pts → should NOT meet threshold
        assert water_q["meets_threshold"] is False

    async def test_unknown_state_uses_default_threshold(self):
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "TX", "total_acres": 100.0}},
                "fields": {"data": []},
                "soil_profiles": {"data": []},
                "recommendations": {"data": []},
            }
        )
        result = await calculate_stewardship_score(FARM_ID, supabase)
        assert result["state_ranking_threshold"] == _STATE_RANKING_THRESHOLDS["_default"]
