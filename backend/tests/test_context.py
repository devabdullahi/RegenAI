"""Tests for app.services.context.assemble_farm_context."""

import logging
from unittest.mock import MagicMock

import pytest
from postgrest.exceptions import APIError

from app.services.context import assemble_farm_context
from tests.conftest import FARM_ID, FIELD_ID_A, FIELD_ID_B, _make_chain

_SCORE_DETAIL = {
    "total_points": 38.5,
    "max_possible_points": 80.0,
    "state_ranking_threshold": 47.0,
    "resource_concern_scores": [
        {"concern_id": "soil_health", "name": "Soil Health", "meets_threshold": True,
         "points_earned": 9.0, "points_possible": 10.0},
        {"concern_id": "water_quality", "name": "Water Quality", "meets_threshold": False,
         "points_earned": 2.0, "points_possible": 10.0},
    ],
}

_ASSESSMENT_ROW = {
    "eligibility_status": "pending_review",
    "fiscal_year": 2026,
    "rc_count_above_threshold": 1,
    "stewardship_score": 38,
    "act_now_eligible": False,
    "resource_concerns_met": _SCORE_DETAIL,
    "active_enhancement_codes": ["590", "393"],
    "notes": "Meets 1 concern.",
    "evaluated_at": "2026-09-01T00:00:00+00:00",
}


def _supabase(tables: dict) -> MagicMock:
    """Supabase mock returning one persistent chain per table so calls can be inspected."""
    chains = {name: _make_chain(data=data) for name, data in tables.items()}
    supabase = MagicMock()
    supabase.table.side_effect = lambda name: chains.setdefault(name, _make_chain(data=None))
    supabase.chains = chains
    return supabase


def _standard_tables(**overrides) -> dict:
    tables = {
        "farms": {"id": FARM_ID, "name": "Test", "state": "IA", "total_acres": 200.0},
        "fields": [
            {"id": FIELD_ID_A, "name": "North", "acres": 120.0, "practices": ["340"]},
            {"id": FIELD_ID_B, "name": "South", "acres": 80.0, "practices": []},
        ],
        "soil_profiles": [],
        "weather_cache": [],
        "recommendations": [],
        "eqip_practices": [{"code": "340", "name": "Cover Crop"}],
        "csp_eligibility_assessments": [_ASSESSMENT_ROW],
    }
    tables.update(overrides)
    return tables


@pytest.mark.asyncio
class TestAssessmentContext:
    async def test_selects_columns_the_eligibility_service_writes(self):
        supabase = _supabase(_standard_tables())

        await assemble_farm_context(FARM_ID, supabase)

        chain = supabase.chains["csp_eligibility_assessments"]
        selected = {c.strip() for c in chain.select.call_args.args[0].split(",")}
        assert {
            "eligibility_status",
            "fiscal_year",
            "rc_count_above_threshold",
            "stewardship_score",
            "act_now_eligible",
            "resource_concerns_met",
            "active_enhancement_codes",
            "notes",
            "evaluated_at",
        } == selected
        chain.eq.assert_any_call("farm_id", FARM_ID)

    async def test_summary_reads_threshold_and_concerns_from_score_detail(self):
        context = await assemble_farm_context(FARM_ID, _supabase(_standard_tables()))

        assert context["csp_assessment"] == {
            "eligibility_status": "pending_review",
            "fiscal_year": 2026,
            "stewardship_score": 38,
            "max_possible_points": 80.0,
            "rc_count_above_threshold": 1,
            "act_now_eligible": False,
            "state_ranking_threshold": 47.0,
            "resource_concerns": [
                {"name": "Soil Health", "points_earned": 9.0, "points_possible": 10.0,
                 "meets_threshold": True},
                {"name": "Water Quality", "points_earned": 2.0, "points_possible": 10.0,
                 "meets_threshold": False},
            ],
            "gap_closure_activity_codes": ["590", "393"],
            "notes": "Meets 1 concern.",
            "evaluated_at": "2026-09-01T00:00:00+00:00",
        }

    async def test_missing_score_detail_leaves_threshold_unknown(self):
        row = {**_ASSESSMENT_ROW, "resource_concerns_met": []}
        tables = _standard_tables(csp_eligibility_assessments=[row])

        context = await assemble_farm_context(FARM_ID, _supabase(tables))

        assert context["csp_assessment"]["state_ranking_threshold"] is None
        assert context["csp_assessment"]["resource_concerns"] == []

    async def test_unknown_ranking_threshold_stays_unknown(self):
        """The NOT NULL act_now_eligible column must not turn unknown into "no"."""
        detail = {
            **_SCORE_DETAIL,
            "state_ranking_threshold": None,
            "meets_ranking_threshold": None,
        }
        row = {**_ASSESSMENT_ROW, "resource_concerns_met": detail}
        tables = _standard_tables(csp_eligibility_assessments=[row])

        context = await assemble_farm_context(FARM_ID, _supabase(tables))

        assert context["csp_assessment"]["state_ranking_threshold"] is None
        assert context["csp_assessment"]["act_now_eligible"] is None

    async def test_score_detail_meets_threshold_wins_over_column(self):
        detail = {**_SCORE_DETAIL, "meets_ranking_threshold": True}
        row = {**_ASSESSMENT_ROW, "resource_concerns_met": detail}
        tables = _standard_tables(csp_eligibility_assessments=[row])

        context = await assemble_farm_context(FARM_ID, _supabase(tables))

        assert context["csp_assessment"]["act_now_eligible"] is True

    async def test_legacy_row_without_meets_flag_falls_back_to_column(self):
        """Rows written before the field existed still read the stored column."""
        context = await assemble_farm_context(FARM_ID, _supabase(_standard_tables()))
        assert "meets_ranking_threshold" not in _SCORE_DETAIL
        assert context["csp_assessment"]["act_now_eligible"] is False

    async def test_no_assessment_row_gives_none(self):
        tables = _standard_tables(csp_eligibility_assessments=[])
        context = await assemble_farm_context(FARM_ID, _supabase(tables))
        assert context["csp_assessment"] is None

    async def test_assessment_query_failure_is_logged_with_farm_id(self, caplog):
        supabase = _supabase(_standard_tables())
        supabase.chains["csp_eligibility_assessments"].execute.side_effect = APIError(
            {"message": "permission denied", "code": "42501"}
        )

        with caplog.at_level(logging.WARNING, logger="app.services.context"):
            context = await assemble_farm_context(FARM_ID, supabase)

        assert context["csp_assessment"] is None
        assert "Could not fetch CSP assessment" in context["data_warnings"]
        assert FARM_ID in caplog.text
        assert "permission denied" in caplog.text


@pytest.mark.asyncio
class TestContextQueries:
    async def test_weather_limit_scales_with_field_count(self):
        supabase = _supabase(_standard_tables())

        await assemble_farm_context(FARM_ID, supabase)

        supabase.chains["weather_cache"].limit.assert_called_once_with(14)

    async def test_missing_farm_raises_value_error(self):
        supabase = _supabase(_standard_tables())
        supabase.chains["farms"].execute.side_effect = APIError(
            {"message": "no rows", "code": "PGRST116"}
        )

        with pytest.raises(ValueError, match="not found"):
            await assemble_farm_context(FARM_ID, supabase)
