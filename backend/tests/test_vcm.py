"""
Tests for app.services.vcm — Voluntary Carbon Market credit estimator.

Coverage targets:
  - Farm with cover crops (340) acted → positive credit estimate
  - Farm with no-till (329) acted → positive credit estimate
  - Farm with no regenerative practices acted → not_eligible, 0 credits
  - Farm with no fields → not_eligible, 0 credits
  - Per-field breakdown included in result
  - SOM >= 3.0 → upper bound of credit band
  - SOM 1.5-2.9 → midpoint of credit band
  - SOM < 1.5 → lower bound of credit band
  - No soil profile → conservative lower-bound rates
  - Zero-acre field → 0 credits for that field
  - De-duplication: same (field, practice) counted once
  - _credits_per_acre unit tests for each band and SOM tier
  - Persistence: credit_eligibility upsert called with program="VCM"
  - Upsert failure is non-fatal
  - Result contains estimated_total_credits and field_breakdown keys
"""

import pytest
from unittest.mock import MagicMock
from tests.conftest import _make_chain, FARM_ID, FIELD_ID_A, FIELD_ID_B

from app.services.vcm import (
    _credits_per_acre,
    _PROTOCOL_PRACTICES,
    _SOM_HIGH_THRESHOLD,
    _SOM_LOW_THRESHOLD,
    estimate_vcm_credits,
)


# ---------------------------------------------------------------------------
# Unit tests: _credits_per_acre
# ---------------------------------------------------------------------------

class TestCreditsPerAcre:
    def test_cover_crop_high_som_returns_high_bound(self):
        """SOM >= 3.0 for code 340 should return the upper bound (1.2)."""
        result = _credits_per_acre("340", 3.5)
        assert result == pytest.approx(1.2, abs=0.001)

    def test_cover_crop_medium_som_returns_midpoint(self):
        """SOM 1.5-2.9 for code 340 should return midpoint (0.5+1.2)/2=0.85."""
        result = _credits_per_acre("340", 2.0)
        assert result == pytest.approx(0.85, abs=0.001)

    def test_cover_crop_low_som_returns_low_bound(self):
        """SOM < 1.5 for code 340 should return the lower bound (0.5)."""
        result = _credits_per_acre("340", 1.0)
        assert result == pytest.approx(0.5, abs=0.001)

    def test_no_till_high_som(self):
        """SOM >= 3.0 for code 329 should return upper bound (0.8)."""
        result = _credits_per_acre("329", 4.0)
        assert result == pytest.approx(0.8, abs=0.001)

    def test_no_till_medium_som(self):
        """SOM 1.5-2.9 for code 329 should return midpoint (0.3+0.8)/2=0.55."""
        result = _credits_per_acre("329", 2.5)
        assert result == pytest.approx(0.55, abs=0.001)

    def test_no_till_low_som(self):
        """SOM < 1.5 for code 329 should return lower bound (0.3)."""
        result = _credits_per_acre("329", 0.5)
        assert result == pytest.approx(0.3, abs=0.001)

    def test_conservation_rotation_high_som(self):
        """SOM >= 3.0 for code 328 should return upper bound (0.5)."""
        result = _credits_per_acre("328", 5.0)
        assert result == pytest.approx(0.5, abs=0.001)

    def test_conservation_rotation_medium_som(self):
        """SOM 1.5-2.9 for code 328 should return midpoint (0.2+0.5)/2=0.35."""
        result = _credits_per_acre("328", 2.0)
        assert result == pytest.approx(0.35, abs=0.001)

    def test_conservation_rotation_low_som(self):
        """SOM < 1.5 for code 328 should return lower bound (0.2)."""
        result = _credits_per_acre("328", 1.4)
        assert result == pytest.approx(0.2, abs=0.001)

    def test_none_som_treated_as_zero(self):
        """None SOM should be treated as 0.0 → uses lower bound."""
        result_none = _credits_per_acre("340", None)
        result_zero = _credits_per_acre("340", 0.0)
        assert result_none == result_zero

    def test_boundary_som_high_threshold(self):
        """SOM exactly at _SOM_HIGH_THRESHOLD qualifies for the high band."""
        result = _credits_per_acre("340", _SOM_HIGH_THRESHOLD)
        assert result == pytest.approx(1.2, abs=0.001)

    def test_boundary_som_low_threshold(self):
        """SOM exactly at _SOM_LOW_THRESHOLD qualifies for the medium (midpoint) band."""
        result = _credits_per_acre("340", _SOM_LOW_THRESHOLD)
        assert result == pytest.approx(0.85, abs=0.001)


# ---------------------------------------------------------------------------
# Helpers for integration tests
# ---------------------------------------------------------------------------

def _make_vcm_supabase(
    fields: list[dict],
    acted_recs: list[dict],
    soil_profiles: list[dict] | None = None,
    upsert_data: list[dict] | None = None,
) -> MagicMock:
    """Build a mock Supabase for VCM evaluation."""
    mock = MagicMock()

    if upsert_data is None:
        upsert_data = [{"id": "elig-vcm-1", "farm_id": FARM_ID, "program": "VCM"}]

    def _table(name: str):
        if name == "fields":
            return _make_chain(data=fields)
        if name == "recommendations":
            return _make_chain(data=acted_recs)
        if name == "soil_profiles":
            return _make_chain(data=soil_profiles or [])
        if name == "credit_eligibility":
            tbl = MagicMock()
            upsert_chain = MagicMock()
            upsert_chain.execute.return_value = MagicMock(data=upsert_data)
            tbl.upsert.return_value = upsert_chain
            return tbl
        return _make_chain(data=None)

    mock.table.side_effect = _table
    return mock


# ---------------------------------------------------------------------------
# Integration tests: estimate_vcm_credits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEstimateVcmCredits:
    async def test_cover_crop_practice_generates_positive_credits(self):
        """A farm with cover crop (340) acted on 100-acre field → credits > 0."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 100.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        supabase = _make_vcm_supabase(fields, acted_recs)
        result = await estimate_vcm_credits(FARM_ID, supabase)

        assert result["estimated_total_credits"] > 0
        assert result["status"] == "eligible"

    async def test_no_till_practice_generates_positive_credits(self):
        """A farm with no-till (329) acted → credits > 0."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 80.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "329", "title": "No-Till"}]

        supabase = _make_vcm_supabase(fields, acted_recs)
        result = await estimate_vcm_credits(FARM_ID, supabase)

        assert result["estimated_total_credits"] > 0

    async def test_conservation_rotation_generates_positive_credits(self):
        """A farm with conservation rotation (328) acted → credits > 0."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 60.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "328", "title": "Conservation Rotation"}]

        supabase = _make_vcm_supabase(fields, acted_recs)
        result = await estimate_vcm_credits(FARM_ID, supabase)

        assert result["estimated_total_credits"] > 0

    async def test_non_protocol_practice_generates_no_credits(self):
        """A practice not in _PROTOCOL_PRACTICES (e.g., 590) should not produce credits."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 100.0}]
        # 590 = Nutrient Management — not in the Soil Carbon Protocol
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "590", "title": "Nutrient Mgmt"}]

        supabase = _make_vcm_supabase(fields, acted_recs)
        result = await estimate_vcm_credits(FARM_ID, supabase)

        assert result["estimated_total_credits"] == 0.0
        assert result["status"] == "not_eligible"

    async def test_no_acted_recommendations_returns_not_eligible(self):
        """No acted recs → not_eligible with zero credits."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 100.0}]

        supabase = _make_vcm_supabase(fields, acted_recs=[])
        result = await estimate_vcm_credits(FARM_ID, supabase)

        assert result["status"] == "not_eligible"
        assert result["estimated_total_credits"] == 0.0

    async def test_no_fields_returns_not_eligible(self):
        """A farm with no registered fields → not_eligible, 0 credits."""
        supabase = _make_vcm_supabase(fields=[], acted_recs=[])
        result = await estimate_vcm_credits(FARM_ID, supabase)

        assert result["status"] == "not_eligible"
        assert result["estimated_total_credits"] == 0.0
        assert result["field_breakdown"] == []

    async def test_per_field_breakdown_included(self):
        """The result must contain a per-field breakdown list."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 100.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        supabase = _make_vcm_supabase(fields, acted_recs)
        result = await estimate_vcm_credits(FARM_ID, supabase)

        assert "field_breakdown" in result
        assert len(result["field_breakdown"]) == 1
        field_entry = result["field_breakdown"][0]
        assert field_entry["field_id"] == FIELD_ID_A
        assert "practices" in field_entry
        assert len(field_entry["practices"]) == 1

    async def test_zero_acre_field_produces_zero_credits(self):
        """A field with 0 acres (or missing acres) should contribute 0 credits."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 0.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        supabase = _make_vcm_supabase(fields, acted_recs)
        result = await estimate_vcm_credits(FARM_ID, supabase)

        assert result["estimated_total_credits"] == 0.0
        # Field breakdown entry may exist but with 0 credits
        if result["field_breakdown"]:
            assert result["field_breakdown"][0]["field_total_credits"] == 0.0

    async def test_high_som_gives_more_credits_than_low_som(self):
        """Higher SOM should produce more credits per acre for the same practice."""
        fields = [{"id": FIELD_ID_A, "name": "Field", "acres": 100.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        low_som_profiles = [{"field_id": FIELD_ID_A, "organic_matter_pct": 1.0, "fetched_at": "2026-01-01"}]
        high_som_profiles = [{"field_id": FIELD_ID_A, "organic_matter_pct": 4.0, "fetched_at": "2026-01-01"}]

        supabase_low = _make_vcm_supabase(fields, acted_recs, soil_profiles=low_som_profiles)
        supabase_high = _make_vcm_supabase(fields, acted_recs, soil_profiles=high_som_profiles)

        result_low = await estimate_vcm_credits(FARM_ID, supabase_low)
        result_high = await estimate_vcm_credits(FARM_ID, supabase_high)

        assert result_high["estimated_total_credits"] > result_low["estimated_total_credits"]

    async def test_no_soil_profile_uses_conservative_rate(self):
        """Without a soil profile, the lower-bound credit rate should be applied."""
        fields = [{"id": FIELD_ID_A, "name": "Field", "acres": 100.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        # No soil profiles
        supabase = _make_vcm_supabase(fields, acted_recs, soil_profiles=[])
        result = await estimate_vcm_credits(FARM_ID, supabase)

        # Lower bound for 340 is 0.5 credits/acre × 100 acres = 50.0
        assert result["estimated_total_credits"] == pytest.approx(50.0, abs=0.01)

    async def test_multiple_fields_total_sums_correctly(self):
        """Credits across multiple fields should sum to the farm total."""
        fields = [
            {"id": FIELD_ID_A, "name": "North 40", "acres": 100.0},
            {"id": FIELD_ID_B, "name": "South 60", "acres": 50.0},
        ]
        acted_recs = [
            {"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"},
            {"field_id": FIELD_ID_B, "practice_code": "329", "title": "No-Till"},
        ]

        supabase = _make_vcm_supabase(fields, acted_recs, soil_profiles=[])
        result = await estimate_vcm_credits(FARM_ID, supabase)

        # Field A: 340 at low SOM → 0.5 × 100 = 50.0
        # Field B: 329 at low SOM → 0.3 × 50 = 15.0
        expected_total = 50.0 + 15.0
        assert result["estimated_total_credits"] == pytest.approx(expected_total, abs=0.01)

    async def test_deduplication_same_field_and_practice_counted_once(self):
        """If the same (field_id, practice_code) appears twice, count it only once."""
        fields = [{"id": FIELD_ID_A, "name": "Field", "acres": 100.0}]
        acted_recs = [
            {"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"},
            {"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop Duplicate"},
        ]

        supabase = _make_vcm_supabase(fields, acted_recs, soil_profiles=[])
        result = await estimate_vcm_credits(FARM_ID, supabase)

        # Should be 0.5 × 100 = 50.0, not doubled
        assert result["estimated_total_credits"] == pytest.approx(50.0, abs=0.01)

    async def test_result_contains_program_name(self):
        """The result must include program_name='Soil Carbon Protocol'."""
        fields = [{"id": FIELD_ID_A, "name": "Field", "acres": 100.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        supabase = _make_vcm_supabase(fields, acted_recs)
        result = await estimate_vcm_credits(FARM_ID, supabase)

        assert result.get("program_name") == "Soil Carbon Protocol"

    async def test_result_contains_required_top_level_keys(self):
        """Result dict must contain all expected keys for the router to use."""
        fields = [{"id": FIELD_ID_A, "name": "Field", "acres": 100.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        supabase = _make_vcm_supabase(fields, acted_recs)
        result = await estimate_vcm_credits(FARM_ID, supabase)

        required = {
            "farm_id", "program", "status", "practices_documented",
            "notes", "updated_at", "estimated_total_credits", "field_breakdown",
            "program_name",
        }
        assert required.issubset(result.keys())

    async def test_practices_documented_sorted_unique(self):
        """practices_documented must be a sorted list of unique codes."""
        fields = [
            {"id": FIELD_ID_A, "name": "Field A", "acres": 100.0},
            {"id": FIELD_ID_B, "name": "Field B", "acres": 50.0},
        ]
        acted_recs = [
            {"field_id": FIELD_ID_A, "practice_code": "329", "title": "No-Till"},
            {"field_id": FIELD_ID_B, "practice_code": "328", "title": "Rotation"},
            {"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"},
        ]

        supabase = _make_vcm_supabase(fields, acted_recs, soil_profiles=[])
        result = await estimate_vcm_credits(FARM_ID, supabase)

        codes = result["practices_documented"]
        assert codes == sorted(set(codes))

    async def test_field_breakdown_has_correct_structure(self):
        """Each field breakdown entry must have the expected nested structure."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 100.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        supabase = _make_vcm_supabase(fields, acted_recs, soil_profiles=[])
        result = await estimate_vcm_credits(FARM_ID, supabase)

        breakdown = result["field_breakdown"]
        assert len(breakdown) == 1
        entry = breakdown[0]
        required_field_keys = {"field_id", "field_name", "acres", "practices", "field_total_credits"}
        assert required_field_keys.issubset(entry.keys())

        practice_entry = entry["practices"][0]
        required_practice_keys = {
            "practice_code", "practice_name", "rate_credits_per_acre", "estimated_credits"
        }
        assert required_practice_keys.issubset(practice_entry.keys())


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestVcmPersistence:
    async def test_upsert_called_with_program_vcm(self):
        """The credit_eligibility upsert must use program='VCM'."""
        fields = [{"id": FIELD_ID_A, "name": "Field", "acres": 100.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]
        captured: list[dict] = []

        mock = MagicMock()

        def _table(name):
            if name == "fields":
                return _make_chain(data=fields)
            if name == "recommendations":
                return _make_chain(data=acted_recs)
            if name == "soil_profiles":
                return _make_chain(data=[])
            if name == "credit_eligibility":
                tbl = MagicMock()

                def capture(payload, **kwargs):
                    captured.append(payload)
                    chain = MagicMock()
                    chain.execute.return_value = MagicMock(data=[payload])
                    return chain

                tbl.upsert.side_effect = capture
                return tbl
            return _make_chain(data=None)

        mock.table.side_effect = _table

        await estimate_vcm_credits(FARM_ID, mock)

        assert len(captured) == 1
        assert captured[0]["program"] == "VCM"
        assert captured[0]["farm_id"] == FARM_ID

    async def test_upsert_failure_is_non_fatal(self):
        """A upsert failure must not raise; the result is still returned."""
        fields = [{"id": FIELD_ID_A, "name": "Field", "acres": 100.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        mock = MagicMock()

        def _table(name):
            if name == "fields":
                return _make_chain(data=fields)
            if name == "recommendations":
                return _make_chain(data=acted_recs)
            if name == "soil_profiles":
                return _make_chain(data=[])
            if name == "credit_eligibility":
                tbl = MagicMock()
                upsert_chain = MagicMock()
                upsert_chain.execute.side_effect = Exception("write failure")
                tbl.upsert.return_value = upsert_chain
                return tbl
            return _make_chain(data=None)

        mock.table.side_effect = _table

        result = await estimate_vcm_credits(FARM_ID, mock)

        # Result still includes required keys despite write failure
        assert "estimated_total_credits" in result
        assert result["farm_id"] == FARM_ID
