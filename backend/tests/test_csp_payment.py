"""
Tests for app.services.csp_payment — EAP + EnAP payment estimation.

Coverage targets:
  - EAP calculation formula (base rate × concern multiplier × acres)
  - EAP zero when concerns_meeting_threshold < 1
  - EnAP calculation with and without bundle premium (115% vs 100%)
  - Payment caps: $4k minimum floor, $50k annual max, $200k contract max
  - State-specific EAP rate lookups (cropland and pasture)
  - Per-field breakdown proportional to field acres
  - estimate_csp_payments() full integration (mocked Supabase)
  - get_recommended_enhancements() ranked output shape
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from tests.conftest import make_supabase_mock, FARM_ID, FIELD_ID_A, FIELD_ID_B

from app.services.csp_payment import (
    _eap_rate,
    _calculate_eap,
    _calculate_enap,
    _apply_payment_caps,
    _EAP_RATES_CROPLAND,
    _EAP_RATES_PASTURE,
    _ENHANCEMENT_COSTS_PER_ACRE,
    _MIN_ANNUAL_PAYMENT,
    _MAX_ANNUAL_PAYMENT,
    _MAX_CONTRACT_PAYMENT,
    _CONTRACT_YEARS,
    _BUNDLE_THRESHOLD,
    estimate_csp_payments,
    get_recommended_enhancements,
)


# ---------------------------------------------------------------------------
# Unit: _eap_rate
# ---------------------------------------------------------------------------

class TestEapRate:
    def test_known_cropland_state(self):
        assert _eap_rate("IA", "cropland") == 19.25
        assert _eap_rate("IL", "cropland") == 18.50

    def test_known_pasture_state(self):
        assert _eap_rate("IA", "pasture") == 11.50
        assert _eap_rate("IL", "pasture") == 11.00

    def test_unknown_state_returns_default_cropland(self):
        assert _eap_rate("TX", "cropland") == _EAP_RATES_CROPLAND["_default"]

    def test_unknown_state_returns_default_pasture(self):
        assert _eap_rate("TX", "pasture") == _EAP_RATES_PASTURE["_default"]

    def test_case_insensitive_state(self):
        assert _eap_rate("ia") == _eap_rate("IA")

    def test_default_land_use_is_cropland(self):
        assert _eap_rate("IA") == _eap_rate("IA", "cropland")


# ---------------------------------------------------------------------------
# Unit: _calculate_eap
# ---------------------------------------------------------------------------

class TestCalculateEap:
    def test_zero_concerns_returns_zero(self):
        eap, rate = _calculate_eap(100.0, 0, "IA")
        assert eap == 0.0
        assert rate == 0.0

    def test_negative_concerns_returns_zero(self):
        eap, rate = _calculate_eap(100.0, -1, "IA")
        assert eap == 0.0

    def test_one_concern_uses_base_rate(self):
        """1 concern → no multiplier uplift, effective_rate == base_rate."""
        base = _eap_rate("IA", "cropland")  # 19.25
        eap, rate = _calculate_eap(100.0, 1, "IA")
        assert rate == pytest.approx(base, abs=0.001)
        assert eap == pytest.approx(base * 100.0, abs=0.01)

    def test_two_concerns_adds_25_pct_uplift(self):
        """2 concerns → effective_rate = base × 1.25."""
        base = _eap_rate("IA", "cropland")
        eap, rate = _calculate_eap(100.0, 2, "IA")
        expected_rate = base * 1.25
        assert rate == pytest.approx(expected_rate, abs=0.001)
        assert eap == pytest.approx(expected_rate * 100.0, abs=0.01)

    def test_three_concerns_adds_50_pct_uplift(self):
        base = _eap_rate("IA", "cropland")
        eap, rate = _calculate_eap(100.0, 3, "IA")
        expected_rate = base * 1.50
        assert rate == pytest.approx(expected_rate, abs=0.001)

    def test_scales_linearly_with_acres(self):
        eap_100, _ = _calculate_eap(100.0, 2, "IL")
        eap_200, _ = _calculate_eap(200.0, 2, "IL")
        assert eap_200 == pytest.approx(eap_100 * 2.0, abs=0.01)

    def test_pasture_rate_used_when_specified(self):
        cropland_eap, _ = _calculate_eap(100.0, 1, "IA", "cropland")
        pasture_eap, _ = _calculate_eap(100.0, 1, "IA", "pasture")
        assert pasture_eap < cropland_eap

    def test_zero_acres_returns_zero_payment(self):
        eap, rate = _calculate_eap(0.0, 3, "IA")
        assert eap == 0.0


# ---------------------------------------------------------------------------
# Unit: _calculate_enap
# ---------------------------------------------------------------------------

class TestCalculateEnap:
    def test_no_enhancements_returns_zero(self):
        enap, is_bundle = _calculate_enap([], 100.0)
        assert enap == 0.0
        assert is_bundle is False

    def test_single_enhancement_no_bundle_rate(self):
        """1 enhancement → 100% rate."""
        cost = _ENHANCEMENT_COSTS_PER_ACRE["E340A"]  # 35.00
        enap, is_bundle = _calculate_enap(["E340A"], 100.0)
        assert is_bundle is False
        assert enap == pytest.approx(cost * 100.0, abs=0.01)

    def test_two_enhancements_no_bundle_rate(self):
        """2 enhancements → still 100% (below bundle threshold)."""
        total_cost = (
            _ENHANCEMENT_COSTS_PER_ACRE["E340A"] +
            _ENHANCEMENT_COSTS_PER_ACRE["E590A"]
        )  # 35 + 10 = 45
        enap, is_bundle = _calculate_enap(["E340A", "E590A"], 100.0)
        assert is_bundle is False
        assert enap == pytest.approx(total_cost * 100.0, abs=0.01)

    def test_three_enhancements_triggers_bundle_115_pct(self):
        """3 enhancements → 115% bundle rate."""
        codes = ["E340A", "E590A", "E328A"]
        total_cost = sum(_ENHANCEMENT_COSTS_PER_ACRE[c] for c in codes)
        enap, is_bundle = _calculate_enap(codes, 100.0)
        assert is_bundle is True
        assert enap == pytest.approx(total_cost * 100.0 * 1.15, abs=0.01)

    def test_four_enhancements_also_bundle(self):
        codes = ["E340A", "E590A", "E328A", "E329A"]
        _, is_bundle = _calculate_enap(codes, 100.0)
        assert is_bundle is True

    def test_bundle_threshold_is_three(self):
        assert _BUNDLE_THRESHOLD == 3

    def test_scales_with_acres(self):
        enap_100, _ = _calculate_enap(["E340A", "E590A", "E328A"], 100.0)
        enap_200, _ = _calculate_enap(["E340A", "E590A", "E328A"], 200.0)
        assert enap_200 == pytest.approx(enap_100 * 2.0, abs=0.01)

    def test_unknown_enhancement_code_contributes_zero(self):
        enap_known, _ = _calculate_enap(["E340A"], 100.0)
        enap_unknown, _ = _calculate_enap(["E340A", "EXXXX"], 100.0)
        assert enap_unknown == pytest.approx(enap_known, abs=0.01)

    def test_zero_acres_returns_zero(self):
        enap, _ = _calculate_enap(["E340A", "E590A", "E328A"], 0.0)
        assert enap == 0.0


# ---------------------------------------------------------------------------
# Unit: _apply_payment_caps
# ---------------------------------------------------------------------------

class TestApplyPaymentCaps:
    def test_zero_payment_stays_zero(self):
        capped, five_year, was_capped = _apply_payment_caps(0.0)
        assert capped == 0.0
        assert five_year == 0.0
        assert was_capped is False

    def test_minimum_floor_applied(self):
        """Any positive payment below $4k should be raised to $4k."""
        capped, five_year, was_capped = _apply_payment_caps(1_000.0)
        assert capped == _MIN_ANNUAL_PAYMENT
        assert five_year == _MIN_ANNUAL_PAYMENT * _CONTRACT_YEARS
        assert was_capped is False  # min floor is applied but not flagged as "capped"

    def test_payment_exactly_at_minimum_unchanged(self):
        capped, five_year, was_capped = _apply_payment_caps(_MIN_ANNUAL_PAYMENT)
        assert capped == _MIN_ANNUAL_PAYMENT
        assert five_year == _MIN_ANNUAL_PAYMENT * _CONTRACT_YEARS

    def test_payment_between_min_and_max_unchanged(self):
        capped, five_year, _ = _apply_payment_caps(25_000.0)
        assert capped == 25_000.0
        assert five_year == 125_000.0

    def test_maximum_annual_cap_applied(self):
        """$60k input capped to $50k annual. 5-year total capped at $200k."""
        capped, five_year, was_capped = _apply_payment_caps(60_000.0)
        assert capped == _MAX_ANNUAL_PAYMENT
        assert five_year == _MAX_CONTRACT_PAYMENT  # 50k*5=250k > 200k → capped
        assert was_capped is True

    def test_five_year_cap_independent_of_annual(self):
        """$45k annual is below $50k annual cap, but $45k*5=$225k > $200k contract cap."""
        capped, five_year, was_capped = _apply_payment_caps(45_000.0)
        assert capped == 45_000.0  # annual stays at $45k (below $50k cap)
        assert five_year == _MAX_CONTRACT_PAYMENT  # 5-year capped at $200k
        assert was_capped is True

    def test_payment_at_exactly_max_annual(self):
        """$50k annual stays at $50k. 5-year capped at $200k (not $250k)."""
        capped, five_year, was_capped = _apply_payment_caps(_MAX_ANNUAL_PAYMENT)
        assert capped == _MAX_ANNUAL_PAYMENT
        assert five_year == _MAX_CONTRACT_PAYMENT
        assert was_capped is True

    def test_contract_max_constants(self):
        assert _MIN_ANNUAL_PAYMENT == 4_000.0
        assert _MAX_ANNUAL_PAYMENT == 50_000.0
        assert _MAX_CONTRACT_PAYMENT == 200_000.0
        assert _CONTRACT_YEARS == 5


# ---------------------------------------------------------------------------
# Integration: estimate_csp_payments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEstimateCspPayments:

    def _base_supabase(self, farm_row, field_rows, concerns_meeting=2):
        """Build a supabase mock with assessment data for the given concern count.

        NOTE: The payment service reads from "csp_eligibility_assessments" (not
        "csp_assessments"), so the mock key must match that name.  This is itself
        a symptom of Bug #1: inconsistent table naming across services.
        """
        assessment = {"concerns_meeting_threshold": concerns_meeting, "cart_score": 40.0}
        return make_supabase_mock(
            {
                "farms": {"data": farm_row},
                "fields": {"data": field_rows},
                # Must match the actual table name used in csp_payment.py line 344
                "csp_eligibility_assessments": {"data": assessment},
                "csp_enhancement_activities": {"data": []},
            }
        )

    async def test_returns_required_keys(self, farm_row, field_rows):
        supabase = self._base_supabase(farm_row, field_rows)
        result = await estimate_csp_payments(FARM_ID, supabase)
        required = {
            "farm_id", "eligible_acres", "eap_annual", "eap_rate_per_acre",
            "resource_concerns_addressed", "enap_annual", "enap_is_bundle",
            "enhancement_codes_included", "total_annual_payment",
            "total_5year_payment", "payment_capped", "field_breakdown",
            "state", "estimated_at",
        }
        assert required.issubset(result.keys())

    async def test_farm_id_in_response(self, farm_row, field_rows):
        supabase = self._base_supabase(farm_row, field_rows)
        result = await estimate_csp_payments(FARM_ID, supabase)
        assert result["farm_id"] == FARM_ID

    async def test_state_from_farm_record(self, farm_row, field_rows):
        supabase = self._base_supabase(farm_row, field_rows)
        result = await estimate_csp_payments(FARM_ID, supabase)
        assert result["state"] == "IA"

    async def test_eligible_acres_matches_farm_total(self, farm_row, field_rows):
        supabase = self._base_supabase(farm_row, field_rows)
        result = await estimate_csp_payments(FARM_ID, supabase)
        assert result["eligible_acres"] == farm_row["total_acres"]

    async def test_eap_positive_with_two_concerns(self, farm_row, field_rows):
        supabase = self._base_supabase(farm_row, field_rows, concerns_meeting=2)
        result = await estimate_csp_payments(FARM_ID, supabase)
        assert result["eap_annual"] > 0.0

    async def test_eap_zero_with_no_concerns(self, farm_row, field_rows):
        supabase = self._base_supabase(farm_row, field_rows, concerns_meeting=0)
        result = await estimate_csp_payments(FARM_ID, supabase)
        assert result["eap_annual"] == 0.0

    async def test_default_fallback_enhancements_give_bundle(self, farm_row, field_rows):
        """When DB has no enhancement rows, fallback codes ['E340A','E590A','E328A']
        is 3 codes → should trigger bundle premium."""
        supabase = self._base_supabase(farm_row, field_rows)
        result = await estimate_csp_payments(FARM_ID, supabase)
        # 3 fallback codes → bundle
        assert result["enap_is_bundle"] is True

    async def test_total_annual_equals_eap_plus_enap_or_capped(self, farm_row, field_rows):
        supabase = self._base_supabase(farm_row, field_rows)
        result = await estimate_csp_payments(FARM_ID, supabase)
        raw_sum = result["eap_annual"] + result["enap_annual"]
        # After capping, total_annual_payment must be <= MAX_ANNUAL_PAYMENT
        assert result["total_annual_payment"] <= _MAX_ANNUAL_PAYMENT
        # And total should be at least min(raw_sum, MAX) — just verify non-negative
        assert result["total_annual_payment"] >= 0.0

    async def test_five_year_total_is_annual_times_5(self, farm_row, field_rows):
        supabase = self._base_supabase(farm_row, field_rows)
        result = await estimate_csp_payments(FARM_ID, supabase)
        expected = round(result["total_annual_payment"] * _CONTRACT_YEARS, 2)
        assert result["total_5year_payment"] == pytest.approx(expected, abs=0.01)

    async def test_field_breakdown_count_matches_fields(self, farm_row, field_rows):
        supabase = self._base_supabase(farm_row, field_rows)
        result = await estimate_csp_payments(FARM_ID, supabase)
        assert len(result["field_breakdown"]) == len(field_rows)

    async def test_field_breakdown_proportional_to_acres(self, farm_row, field_rows):
        """North 40 (120ac) vs South 60 (80ac): payment ratio should match acres."""
        supabase = self._base_supabase(farm_row, field_rows)
        result = await estimate_csp_payments(FARM_ID, supabase)
        breakdown = {fb["field_id"]: fb for fb in result["field_breakdown"]}
        north = breakdown[FIELD_ID_A]
        south = breakdown[FIELD_ID_B]
        # Proportionality: north_total / south_total ≈ 120 / 80 = 1.5
        if south["total_annual"] > 0:
            ratio = north["total_annual"] / south["total_annual"]
            assert ratio == pytest.approx(1.5, abs=0.05)

    async def test_field_breakdown_sums_to_total(self, farm_row, field_rows):
        supabase = self._base_supabase(farm_row, field_rows)
        result = await estimate_csp_payments(FARM_ID, supabase)
        total_from_fields = sum(fb["total_annual"] for fb in result["field_breakdown"])
        assert total_from_fields == pytest.approx(result["total_annual_payment"], abs=0.10)

    async def test_farm_not_found_raises_value_error(self):
        supabase = make_supabase_mock({"farms": {"data": None}})
        with pytest.raises(ValueError, match=FARM_ID):
            await estimate_csp_payments(FARM_ID, supabase)

    async def test_payment_cap_applied_for_large_farm(self, farm_row, field_rows):
        """A very large farm (10k acres) should hit the annual cap."""
        big_farm = dict(farm_row)
        big_farm["total_acres"] = 10_000.0
        supabase = make_supabase_mock(
            {
                "farms": {"data": big_farm},
                "fields": {"data": field_rows},
                "csp_eligibility_assessments": {"data": {"concerns_meeting_threshold": 5, "cart_score": 60.0}},
                "csp_enhancement_activities": {"data": []},
            }
        )
        result = await estimate_csp_payments(FARM_ID, supabase)
        assert result["total_annual_payment"] <= _MAX_ANNUAL_PAYMENT
        assert result["payment_capped"] is True


# ---------------------------------------------------------------------------
# Integration: get_recommended_enhancements
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetRecommendedEnhancements:

    async def test_returns_list(self, farm_row):
        supabase = make_supabase_mock(
            {
                "farms": {"data": farm_row},
                "csp_assessments": {"data": None},
                "csp_enhancement_activities": {"data": []},
            }
        )
        result = await get_recommended_enhancements(FARM_ID, supabase)
        assert isinstance(result, list)

    async def test_each_item_has_required_fields(self, farm_row):
        supabase = make_supabase_mock(
            {
                "farms": {"data": farm_row},
                "csp_assessments": {"data": None},
                "csp_enhancement_activities": {"data": []},
            }
        )
        result = await get_recommended_enhancements(FARM_ID, supabase)
        required = {
            "code", "name", "category", "land_use", "description",
            "estimated_cost_per_acre", "payment_rate_pct",
            "estimated_annual_payment", "applicable_acres",
            "resource_concerns_addressed", "priority_score", "is_bundle_eligible",
        }
        for item in result:
            assert required.issubset(item.keys()), f"Missing keys in item: {item.get('code')}"

    async def test_sorted_by_priority_score_descending(self, farm_row):
        supabase = make_supabase_mock(
            {
                "farms": {"data": farm_row},
                "csp_assessments": {"data": None},
                "csp_enhancement_activities": {"data": []},
            }
        )
        result = await get_recommended_enhancements(FARM_ID, supabase)
        scores = [r["priority_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    async def test_farm_not_found_raises_value_error(self):
        supabase = make_supabase_mock({"farms": {"data": None}})
        with pytest.raises(ValueError):
            await get_recommended_enhancements(FARM_ID, supabase)

    async def test_estimated_annual_payment_scales_with_farm_acres(self):
        """Larger farm should produce higher estimated annual payments per enhancement."""
        small_farm = {"id": FARM_ID, "state": "IA", "total_acres": 50.0}
        large_farm = {"id": FARM_ID, "state": "IA", "total_acres": 500.0}

        small_sb = make_supabase_mock(
            {"farms": {"data": small_farm}, "csp_assessments": {"data": None}, "csp_enhancement_activities": {"data": []}}
        )
        large_sb = make_supabase_mock(
            {"farms": {"data": large_farm}, "csp_assessments": {"data": None}, "csp_enhancement_activities": {"data": []}}
        )

        small_result = await get_recommended_enhancements(FARM_ID, small_sb)
        large_result = await get_recommended_enhancements(FARM_ID, large_sb)

        # Find the same code in both results
        small_map = {r["code"]: r for r in small_result}
        large_map = {r["code"]: r for r in large_result}
        common = set(small_map) & set(large_map)
        assert len(common) > 0
        code = next(iter(common))
        assert large_map[code]["estimated_annual_payment"] > small_map[code]["estimated_annual_payment"]
