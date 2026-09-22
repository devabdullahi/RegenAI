"""
Tests for app.services.csp_payment and app.services.program_rules (FY2026 rules).

Coverage targets:
  - Program rules: contract limits by fiscal year / joint operation, EAP
    $4,000/contract/yr, no annual payment limit, citation metadata
  - EAP is a fixed per-contract payment (not a floor, not per-acre)
  - Activity payments: per-acre estimates, no bundle premium, E-code mapping
  - Contract limit caps only the 5-year total; no annual cap
  - estimate_csp_payments() full integration (mocked Supabase)
  - get_recommended_enhancements() ranked output shape (practice-standard codes)
"""

import pytest
from postgrest.exceptions import APIError

from tests.conftest import make_supabase_mock, FARM_ID, FIELD_ID_A, FIELD_ID_B

from app.services import program_rules
from app.services.program_rules import (
    CSP_ANNUAL_PAYMENT_LIMIT,
    CSP_EXISTING_ACTIVITY_PAYMENT,
    NB_440_26_2_AS_OF,
    NB_440_26_2_URL,
    csp_contract_limit,
    csp_rules_metadata,
)
from app.services.csp_payment import (
    _CONTRACT_YEARS,
    _CSP_ACTIVITIES,
    _DEFAULT_ACTIVITY_CODES,
    _EXISTING_ACTIVITY_PAYMENT,
    _apply_contract_limit,
    _calculate_activity_payments,
    _calculate_eap,
    estimate_csp_payments,
    get_recommended_enhancements,
    normalize_activity_code,
)


# ---------------------------------------------------------------------------
# Program rules
# ---------------------------------------------------------------------------

class TestProgramRules:
    def test_fy2026_individual_limit_is_300k(self):
        limit = csp_contract_limit(2026, joint_operation=False)
        assert limit["amount"] == 300_000.0
        assert limit["rules_period"] == "FY2026+"
        assert limit["applies_to"] == "individual_or_entity"
        assert limit["label"] == "$300,000 contract limit (FY2026+)"

    def test_fy2026_joint_limit_is_600k(self):
        limit = csp_contract_limit(2026, joint_operation=True)
        assert limit["amount"] == 600_000.0
        assert limit["applies_to"] == "joint_operation"

    def test_later_fiscal_years_use_fy2026_limits(self):
        assert csp_contract_limit(2028)["amount"] == 300_000.0

    def test_pre_fy2026_individual_limit_is_200k(self):
        limit = csp_contract_limit(2025, joint_operation=False)
        assert limit["amount"] == 200_000.0
        assert limit["rules_period"] == "pre-FY2026"

    def test_pre_fy2026_joint_limit_is_400k(self):
        assert csp_contract_limit(2024, joint_operation=True)["amount"] == 400_000.0

    def test_default_contract_is_new_fy2026(self):
        assert csp_contract_limit()["amount"] == 300_000.0

    def test_eap_is_4000_per_contract_per_year(self):
        assert CSP_EXISTING_ACTIVITY_PAYMENT.value == 4_000.0
        assert CSP_EXISTING_ACTIVITY_PAYMENT.unit == "usd_per_contract_per_year"

    def test_no_annual_payment_limit(self):
        assert CSP_ANNUAL_PAYMENT_LIMIT.value is None

    def test_every_rule_has_as_of_and_source(self):
        rules = [
            v for v in vars(program_rules).values()
            if isinstance(v, program_rules.RuleValue)
        ]
        assert rules, "expected RuleValue constants"
        for rule in rules:
            assert rule.as_of, rule.key
            assert rule.source_url, rule.key

    def test_limit_cites_bulletin(self):
        limit = csp_contract_limit()
        assert limit["as_of"] == NB_440_26_2_AS_OF == "2025-12-17"
        assert limit["source_url"] == NB_440_26_2_URL

    def test_rules_metadata_shape(self):
        meta = csp_rules_metadata(2026, joint_operation=True)
        assert meta["as_of"] == "2025-12-17"
        assert meta["source_url"] == NB_440_26_2_URL
        assert meta["annual_payment_limit"] is None
        assert meta["contract_limit"]["amount"] == 600_000.0
        assert meta["existing_activity_payment"]["amount"] == 4_000.0
        assert meta["activity_rates"]["status"] == "estimate"
        assert "pending FY2026 state payment schedule" in meta["activity_rates"]["basis"]


# ---------------------------------------------------------------------------
# Unit: _calculate_eap
# ---------------------------------------------------------------------------

class TestCalculateEap:
    def test_fixed_4000_when_contract_possible(self):
        assert _calculate_eap(2) == 4_000.0

    def test_does_not_scale_with_concerns(self):
        assert _calculate_eap(5) == _calculate_eap(2) == _EXISTING_ACTIVITY_PAYMENT

    def test_zero_below_two_concerns(self):
        assert _calculate_eap(1) == 0.0
        assert _calculate_eap(0) == 0.0
        assert _calculate_eap(-1) == 0.0


# ---------------------------------------------------------------------------
# Unit: activity catalog & payments
# ---------------------------------------------------------------------------

class TestActivityCatalog:
    def test_no_e_codes_in_catalog(self):
        for code in _CSP_ACTIVITIES:
            assert not code.startswith("E"), code

    def test_codes_keyed_by_practice_standard(self):
        for code, activity in _CSP_ACTIVITIES.items():
            assert code.split("-")[0] == activity.practice_standard_code
            assert activity.practice_standard_code.isdigit()

    def test_activities_come_from_single_catalog(self):
        """Payment activities are the catalog entries that carry a rate."""
        expected = {
            code
            for code, practice in program_rules.CSP_PRACTICE_CATALOG.items()
            if practice.estimated_rate_per_acre is not None
        }
        assert set(_CSP_ACTIVITIES) == expected
        for code, activity in _CSP_ACTIVITIES.items():
            assert activity is program_rules.CSP_PRACTICE_CATALOG[code]

    def test_higher_payment_categories_flagged(self):
        flagged = {
            a.higher_payment_category
            for a in _CSP_ACTIVITIES.values()
            if a.higher_payment_category
        }
        assert flagged == {"cover_crop", "agm", "rccr", "irccr"}
        assert _CSP_ACTIVITIES["340"].higher_payment_category == "cover_crop"
        assert _CSP_ACTIVITIES["328-RCCR"].higher_payment_category == "rccr"
        assert _CSP_ACTIVITIES["328-IRCCR"].higher_payment_category == "irccr"
        assert _CSP_ACTIVITIES["528"].higher_payment_category == "agm"

    def test_legacy_e_codes_map_to_activities(self):
        assert normalize_activity_code("E340A") == "340"
        assert normalize_activity_code("e328b") == "328-IRCCR"
        assert normalize_activity_code("E449A") == "554"
        assert normalize_activity_code("340") == "340"
        assert normalize_activity_code("E412A") is None
        assert normalize_activity_code("NOPE") is None


class TestCalculateActivityPayments:
    def test_empty_returns_zero(self):
        total, items = _calculate_activity_payments([], 100.0)
        assert total == 0.0
        assert items == []

    def test_single_activity(self):
        rate = _CSP_ACTIVITIES["340"].estimated_rate_per_acre
        total, items = _calculate_activity_payments(["340"], 100.0)
        assert total == pytest.approx(rate * 100.0, abs=0.01)
        assert items[0]["rate_is_estimate"] is True
        assert items[0]["higher_payment"] is True

    def test_no_bundle_premium_for_three_or_more(self):
        codes = ["340", "590", "328-RCCR"]
        expected = sum(_CSP_ACTIVITIES[c].estimated_rate_per_acre for c in codes) * 100.0
        total, _ = _calculate_activity_payments(codes, 100.0)
        assert total == pytest.approx(expected, abs=0.01)

    def test_unknown_code_contributes_zero(self):
        known, _ = _calculate_activity_payments(["340"], 100.0)
        with_unknown, items = _calculate_activity_payments(["340", "XXXX"], 100.0)
        assert with_unknown == pytest.approx(known, abs=0.01)
        assert len(items) == 1

    def test_legacy_code_and_duplicate_collapsed(self):
        total, items = _calculate_activity_payments(["E340A", "340"], 100.0)
        assert [i["code"] for i in items] == ["340"]

    def test_scales_with_acres(self):
        t100, _ = _calculate_activity_payments(_DEFAULT_ACTIVITY_CODES, 100.0)
        t200, _ = _calculate_activity_payments(_DEFAULT_ACTIVITY_CODES, 200.0)
        assert t200 == pytest.approx(t100 * 2.0, abs=0.01)


# ---------------------------------------------------------------------------
# Unit: _apply_contract_limit
# ---------------------------------------------------------------------------

class TestApplyContractLimit:
    def test_zero_stays_zero(self):
        assert _apply_contract_limit(0.0, 300_000.0) == (0.0, 0.0, False)

    def test_no_minimum_floor(self):
        """Old $4,000 floor semantics are gone: small payments stay small."""
        annual, five_year, capped = _apply_contract_limit(1_000.0, 300_000.0)
        assert annual == 1_000.0
        assert five_year == 5_000.0
        assert capped is False

    def test_no_annual_cap_above_50k(self):
        """$55k/yr was capped to $50k under old rules; FY2026 has no annual limit."""
        annual, five_year, capped = _apply_contract_limit(55_000.0, 300_000.0)
        assert annual == 55_000.0
        assert five_year == 275_000.0
        assert capped is False

    def test_five_year_capped_at_fy2026_limit(self):
        annual, five_year, capped = _apply_contract_limit(70_000.0, 300_000.0)
        assert annual == 70_000.0
        assert five_year == 300_000.0
        assert capped is True

    def test_joint_limit_allows_higher_total(self):
        _, five_year, capped = _apply_contract_limit(70_000.0, 600_000.0)
        assert five_year == 350_000.0
        assert capped is False

    def test_pre_fy2026_limit(self):
        _, five_year, capped = _apply_contract_limit(45_000.0, 200_000.0)
        assert five_year == 200_000.0
        assert capped is True

    def test_contract_years(self):
        assert _CONTRACT_YEARS == 5


# ---------------------------------------------------------------------------
# Integration: estimate_csp_payments
# ---------------------------------------------------------------------------

def _supabase(farm_row, field_rows, concerns_meeting=2):
    assessment = {"rc_count_above_threshold": concerns_meeting, "stewardship_score": 40.0}
    return make_supabase_mock(
        {
            "farms": {"data": farm_row},
            "fields": {"data": field_rows},
            "csp_eligibility_assessments": {"data": assessment},
            "csp_enhancement_activities": {"data": []},
        }
    )


@pytest.mark.asyncio
class TestEstimateCspPayments:

    async def test_returns_required_keys(self, farm_row, field_rows):
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows))
        required = {
            "farm_id", "eligible_acres", "resource_concerns_addressed",
            "eap_annual", "activity_payment_annual", "activities_included",
            "total_annual_payment", "total_5year_payment", "contract_years",
            "contract_fiscal_year", "joint_operation", "contract_limit",
            "annual_payment_limit", "payment_capped", "field_breakdown",
            "state", "rules", "estimated_at",
        }
        assert required.issubset(result.keys())
        for legacy in ("enap_annual", "enap_is_bundle", "enhancement_codes_included"):
            assert legacy not in result

    async def test_validates_against_schema(self, farm_row, field_rows):
        from app.models.schemas import CSPPaymentEstimate

        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows))
        est = CSPPaymentEstimate(**result)
        assert est.contract_limit.amount == 300_000.0
        assert est.annual_payment_limit is None

    async def test_state_without_ranking_threshold_still_estimates(self, field_rows):
        """A state with no published ranking threshold must not break payments.

        With no persisted assessment the estimator falls back to the scoring
        engine, which now returns a None ranking threshold for such states.
        """
        supabase = make_supabase_mock(
            {
                "farms": {"data": {"id": FARM_ID, "state": "TX", "total_acres": 100.0}},
                "fields": {"data": field_rows},
                "csp_eligibility_assessments": {"data": None},
                "csp_enhancement_activities": {"data": []},
                "soil_profiles": {"data": []},
                "recommendations": {"data": []},
            }
        )
        result = await estimate_csp_payments(FARM_ID, supabase)
        assert result["state"] == "TX"
        assert result["total_annual_payment"] >= 0.0

    async def test_farm_state_and_acres(self, farm_row, field_rows):
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows))
        assert result["farm_id"] == FARM_ID
        assert result["state"] == "IA"
        assert result["eligible_acres"] == farm_row["total_acres"]

    async def test_eap_is_fixed_4000(self, farm_row, field_rows):
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows, 2))
        assert result["eap_annual"] == 4_000.0

    async def test_eap_zero_with_no_concerns(self, farm_row, field_rows):
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows, 0))
        assert result["eap_annual"] == 0.0

    async def test_eap_zero_with_one_concern(self, farm_row, field_rows):
        """EAP needs the minimum number of concerns (2) meeting threshold."""
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows, 1))
        assert result["eap_annual"] == 0.0
        assert result["resource_concerns_addressed"] == 1

    async def test_assessment_read_error_falls_back_to_inline_scoring(
        self, farm_row, field_rows, caplog
    ):
        """An APIError reading the assessment is logged and scoring runs inline."""
        supabase = _supabase(farm_row, field_rows, concerns_meeting=5)
        real_table = supabase.table.side_effect

        def _table(name):
            chain = real_table(name)
            if name == "csp_eligibility_assessments":
                chain.execute.side_effect = APIError({"message": "boom", "code": "XX000"})
            return chain

        supabase.table.side_effect = _table
        with caplog.at_level("WARNING"):
            result = await estimate_csp_payments(FARM_ID, supabase)

        assert FARM_ID in caplog.text
        # Inline scoring of the fixture practices, not the (unreadable) 5.
        assert result["resource_concerns_addressed"] != 5

    async def test_annual_is_eap_plus_activities(self, farm_row, field_rows):
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows))
        assert result["total_annual_payment"] == pytest.approx(
            result["eap_annual"] + result["activity_payment_annual"], abs=0.01
        )

    async def test_activities_use_practice_standard_codes(self, farm_row, field_rows):
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows))
        codes = [a["code"] for a in result["activities_included"]]
        assert codes == _DEFAULT_ACTIVITY_CODES
        assert all(not c.startswith("E") for c in codes)
        assert all(a["rate_is_estimate"] for a in result["activities_included"])

    async def test_default_contract_is_fy2026_individual(self, farm_row, field_rows):
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows))
        assert result["contract_fiscal_year"] == 2026
        assert result["joint_operation"] is False
        assert result["contract_limit"]["amount"] == 300_000.0
        assert result["annual_payment_limit"] is None

    async def test_rules_metadata_included(self, farm_row, field_rows):
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows))
        rules = result["rules"]
        assert rules["as_of"] == "2025-12-17"
        assert rules["source_url"] == NB_440_26_2_URL
        assert rules["contract_limit"]["rule_key"] == result["contract_limit"]["rule_key"]

    async def test_five_year_is_annual_times_5_when_uncapped(self, farm_row, field_rows):
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows))
        assert result["payment_capped"] is False
        assert result["total_5year_payment"] == pytest.approx(
            result["total_annual_payment"] * _CONTRACT_YEARS, abs=0.01
        )

    async def test_large_farm_no_annual_cap_but_contract_limit(self, farm_row, field_rows):
        """10,000 acres → annual well above the old $50k cap; 5-year capped at $300k."""
        big = dict(farm_row, total_acres=10_000.0)
        result = await estimate_csp_payments(FARM_ID, _supabase(big, field_rows, 5))
        assert result["total_annual_payment"] > 50_000.0
        assert result["total_5year_payment"] == 300_000.0
        assert result["payment_capped"] is True

    async def test_joint_operation_limit(self, farm_row, field_rows):
        big = dict(farm_row, total_acres=10_000.0)
        result = await estimate_csp_payments(
            FARM_ID, _supabase(big, field_rows, 5), joint_operation=True
        )
        assert result["contract_limit"]["amount"] == 600_000.0
        assert result["total_5year_payment"] <= 600_000.0
        assert result["total_5year_payment"] > 300_000.0

    async def test_pre_fy2026_contract_limit(self, farm_row, field_rows):
        big = dict(farm_row, total_acres=10_000.0)
        result = await estimate_csp_payments(
            FARM_ID, _supabase(big, field_rows, 5), contract_fiscal_year=2025
        )
        assert result["contract_limit"]["amount"] == 200_000.0
        assert result["contract_limit"]["rules_period"] == "pre-FY2026"
        assert result["total_5year_payment"] == 200_000.0

    async def test_field_breakdown_count_and_proportion(self, farm_row, field_rows):
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows))
        assert len(result["field_breakdown"]) == len(field_rows)
        breakdown = {fb["field_id"]: fb for fb in result["field_breakdown"]}
        north, south = breakdown[FIELD_ID_A], breakdown[FIELD_ID_B]
        assert "activity_payment_annual" in north
        if south["total_annual"] > 0:
            assert north["total_annual"] / south["total_annual"] == pytest.approx(1.5, abs=0.05)

    async def test_field_breakdown_sums_to_total(self, farm_row, field_rows):
        result = await estimate_csp_payments(FARM_ID, _supabase(farm_row, field_rows))
        total = sum(fb["total_annual"] for fb in result["field_breakdown"])
        assert total == pytest.approx(result["total_annual_payment"], abs=0.10)

    async def test_farm_not_found_raises_value_error(self):
        supabase = make_supabase_mock({"farms": {"data": None}})
        with pytest.raises(ValueError, match=FARM_ID):
            await estimate_csp_payments(FARM_ID, supabase)


# ---------------------------------------------------------------------------
# Integration: get_recommended_enhancements
# ---------------------------------------------------------------------------

def _enh_supabase(farm, rows=None):
    return make_supabase_mock(
        {
            "farms": {"data": farm},
            "csp_eligibility_assessments": {"data": None},
            "csp_enhancement_activities": {"data": rows or []},
        }
    )


@pytest.mark.asyncio
class TestGetRecommendedEnhancements:

    async def test_returns_full_catalog(self, farm_row):
        result = await get_recommended_enhancements(FARM_ID, _enh_supabase(farm_row))
        assert {r["code"] for r in result} == set(_CSP_ACTIVITIES)

    async def test_each_item_has_required_fields(self, farm_row):
        from app.models.schemas import CSPEnhancementActivity

        result = await get_recommended_enhancements(FARM_ID, _enh_supabase(farm_row))
        required = {
            "code", "practice_standard_code", "name", "category", "land_use",
            "description", "estimated_rate_per_acre", "rate_is_estimate",
            "rate_basis", "estimated_annual_payment", "applicable_acres",
            "resource_concerns_addressed", "priority_score", "higher_payment",
            "higher_payment_category",
        }
        for item in result:
            assert required.issubset(item.keys()), item.get("code")
            assert "is_bundle_eligible" not in item
            assert "payment_rate_pct" not in item
            CSPEnhancementActivity(**item)

    async def test_no_e_codes_even_if_db_has_legacy_rows(self, farm_row):
        legacy = [{"code": "E340A", "name": "Old", "description": "old", "active": True}]
        result = await get_recommended_enhancements(FARM_ID, _enh_supabase(farm_row, legacy))
        assert all(not r["code"].startswith("E") for r in result)

    async def test_db_description_used_for_current_code(self, farm_row):
        rows = [{"code": "340", "name": "Cover Crop", "description": "From DB", "active": True}]
        result = await get_recommended_enhancements(FARM_ID, _enh_supabase(farm_row, rows))
        cover = next(r for r in result if r["code"] == "340")
        assert cover["description"] == "From DB"

    async def test_sorted_by_priority_score_descending(self, farm_row):
        result = await get_recommended_enhancements(FARM_ID, _enh_supabase(farm_row))
        scores = [r["priority_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    async def test_farm_not_found_raises_value_error(self):
        supabase = make_supabase_mock({"farms": {"data": None}})
        with pytest.raises(ValueError):
            await get_recommended_enhancements(FARM_ID, supabase)

    async def test_estimated_annual_payment_scales_with_farm_acres(self):
        small = await get_recommended_enhancements(
            FARM_ID, _enh_supabase({"id": FARM_ID, "state": "IA", "total_acres": 50.0})
        )
        large = await get_recommended_enhancements(
            FARM_ID, _enh_supabase({"id": FARM_ID, "state": "IA", "total_acres": 500.0})
        )
        s = {r["code"]: r for r in small}
        la = {r["code"]: r for r in large}
        assert la["340"]["estimated_annual_payment"] > s["340"]["estimated_annual_payment"]
