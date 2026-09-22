"""
Tests for app.routers.csp — CSP Navigator farm endpoints.

Coverage targets:
  - farm_id path/query UUIDs reach Supabase and services as ``str`` (the
    Supabase client cannot JSON-serialize uuid.UUID)
  - response shapes of /eligibility, /score, /payments, /enhancements and
    POST /evaluate match the response_model schemas the frontend reads
  - 404 when the farm is missing or hidden by RLS, 422 for a non-UUID,
    500 on a database error

Auth and Supabase are replaced via FastAPI dependency_overrides.
"""

import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from unittest.mock import MagicMock

from app.auth.middleware import get_authenticated_client, get_current_user
from app.main import app
from app.services.program_rules import (
    CSP_ADDITIONAL_CONCERNS_REQUIRED,
    CSP_CONTRACT_YEARS,
    CSP_MIN_PRIORITY_CONCERNS,
)
from tests.conftest import FIELD_ROWS, SOIL_ROWS

_BASE = "/api/v1/csp"
_FARM_ID = "5b0f3c1e-2a4d-4c1e-9b2a-6d7e8f901234"
_FARM_ROW = {"id": _FARM_ID, "state": "IA", "total_acres": 200.0}


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _chain(data) -> MagicMock:
    chain = MagicMock()
    for method in ("select", "eq", "in_", "order", "single", "limit", "upsert"):
        getattr(chain, method).return_value = chain
    chain.execute.return_value = MagicMock(data=data)
    return chain


def _supabase(tables: dict) -> MagicMock:
    """Supabase mock with one reusable chain per table, so calls can be inspected."""
    chains: dict[str, MagicMock] = {}

    def _table(name: str) -> MagicMock:
        if name not in chains:
            chains[name] = _chain(tables.get(name))
        return chains[name]

    mock = MagicMock()
    mock.table.side_effect = _table
    mock.chains = chains
    return mock


def _farm_supabase(farm_row=_FARM_ROW) -> MagicMock:
    return _supabase(
        {
            "farms": farm_row,
            "fields": [dict(f) for f in FIELD_ROWS],
            "soil_profiles": [dict(r) for r in SOIL_ROWS],
            "recommendations": [],
            "csp_eligibility_assessments": None,
            "csp_enhancement_activities": [],
        }
    )


def _assert_no_uuid_args(supabase: MagicMock) -> None:
    """No filter or write on any table received a uuid.UUID."""
    for name, chain in supabase.chains.items():
        for method in ("eq", "in_", "upsert"):
            for call in getattr(chain, method).call_args_list:
                for arg in (*call.args, *call.kwargs.values()):
                    assert not isinstance(arg, UUID), (name, method, arg)


@pytest.fixture
def client_for():
    def _make(supabase: MagicMock) -> TestClient:
        user = MagicMock()
        user.id = "user-uuid-test-1"
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_authenticated_client] = lambda: supabase
        return TestClient(app)

    try:
        yield _make
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_authenticated_client, None)


# Keys the frontend reads (frontend/src/lib/api/types.ts).
_CONCERN_KEYS = {
    "concern_id", "name", "category", "practices_addressing",
    "meets_threshold", "points_earned", "points_possible",
}
_SCORE_KEYS = {
    "farm_id", "total_points", "max_possible_points", "state_ranking_threshold",
    "meets_ranking_threshold", "gap_to_threshold", "resource_concern_scores",
    "component_scores", "avg_som_pct", "som_tier", "is_estimate", "scoring_rules",
    "evaluated_at",
}
_ELIGIBILITY_KEYS = {
    "farm_id", "status", "is_eligible", "resource_concerns_meeting_threshold",
    "min_concerns_required", "additional_concerns_required", "contract_years",
    "resource_concerns_detail", "cart_score", "state_ranking_threshold",
    "meets_ranking_threshold", "eligibility_notes", "recommended_enhancements",
    "is_estimate", "scoring_rules", "evaluated_at",
    # Additive: reports a failed assessment write instead of a silent success.
    "warnings",
}
_RULES_KEYS = {
    "program", "as_of", "source_title", "source_url", "contract_limit",
    "annual_payment_limit", "annual_payment_limit_note", "existing_activity_payment",
    "contract_years", "activity_rates", "activity_model_note",
}
_PAYMENT_KEYS = {
    "farm_id", "eligible_acres", "resource_concerns_addressed", "eap_annual",
    "activity_payment_annual", "activities_included", "total_annual_payment",
    "total_5year_payment", "contract_years", "contract_fiscal_year", "joint_operation",
    "contract_limit", "annual_payment_limit", "payment_capped", "field_breakdown",
    "state", "rules", "estimated_at",
}


# ---------------------------------------------------------------------------
# GET /csp/eligibility
# ---------------------------------------------------------------------------

class TestEligibility:
    def test_upsert_payload_farm_id_is_str(self, client_for):
        supabase = _farm_supabase()
        resp = client_for(supabase).get(f"{_BASE}/eligibility", params={"farm_id": _FARM_ID})

        assert resp.status_code == 200, resp.text
        upsert = supabase.chains["csp_eligibility_assessments"].upsert
        upsert.assert_called_once()
        payload = upsert.call_args.args[0]
        assert isinstance(payload["farm_id"], str)
        assert payload["farm_id"] == _FARM_ID
        json.dumps(payload)
        _assert_no_uuid_args(supabase)

    def test_response_shape(self, client_for):
        resp = client_for(_farm_supabase()).get(
            f"{_BASE}/eligibility", params={"farm_id": _FARM_ID}
        )
        body = resp.json()
        assert set(body) == _ELIGIBILITY_KEYS
        assert body["farm_id"] == _FARM_ID
        assert body["status"] in {"act_now", "eligible", "pending_review", "not_eligible"}
        assert body["is_estimate"] is True
        assert body["scoring_rules"]["source_url"] is None
        for concern in body["resource_concerns_detail"]:
            assert set(concern) == _CONCERN_KEYS

    def test_min_concerns_required_comes_from_program_rules(self, client_for):
        """The frontend reads this instead of hard-coding its own minimum."""
        body = client_for(_farm_supabase()).get(
            f"{_BASE}/eligibility", params={"farm_id": _FARM_ID}
        ).json()

        assert body["min_concerns_required"] == CSP_MIN_PRIORITY_CONCERNS.value
        assert isinstance(body["min_concerns_required"], int)

    def test_additional_concerns_and_contract_years_come_from_program_rules(self, client_for):
        body = client_for(_farm_supabase()).get(
            f"{_BASE}/eligibility", params={"farm_id": _FARM_ID}
        ).json()

        assert body["additional_concerns_required"] == CSP_ADDITIONAL_CONCERNS_REQUIRED.value
        assert isinstance(body["additional_concerns_required"], int)
        assert body["contract_years"] == CSP_CONTRACT_YEARS.value
        assert isinstance(body["contract_years"], int)

    def test_state_without_threshold_serializes_nulls(self, client_for):
        """Nationwide: a state with no published threshold returns nulls, not 42.0."""
        supabase = _farm_supabase(farm_row={**_FARM_ROW, "state": "TX"})
        body = client_for(supabase).get(
            f"{_BASE}/eligibility", params={"farm_id": _FARM_ID}
        ).json()

        assert set(body) == _ELIGIBILITY_KEYS
        assert body["state_ranking_threshold"] is None
        assert body["meets_ranking_threshold"] is None
        assert body["status"] != "act_now"
        citation = body["scoring_rules"]["state_ranking_threshold"]
        assert citation == {
            "state": "TX",
            "value": None,
            "status": "not_published",
            "as_of": citation["as_of"],
            "source_url": None,
            "note": citation["note"],
        }

    def test_missing_farm_returns_404(self, client_for):
        resp = client_for(_farm_supabase(farm_row=[])).get(
            f"{_BASE}/eligibility", params={"farm_id": _FARM_ID}
        )
        assert resp.status_code == 404

    def test_non_uuid_returns_422(self, client_for):
        resp = client_for(_farm_supabase()).get(
            f"{_BASE}/eligibility", params={"farm_id": "not-a-uuid"}
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /csp/score
# ---------------------------------------------------------------------------

class TestScore:
    def test_response_shape_and_str_ids(self, client_for):
        supabase = _farm_supabase()
        resp = client_for(supabase).get(f"{_BASE}/score", params={"farm_id": _FARM_ID})

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body) == _SCORE_KEYS
        assert body["farm_id"] == _FARM_ID
        assert len(body["resource_concern_scores"]) == 8
        assert body["is_estimate"] is True
        # Scoring is read-only.
        assert "csp_eligibility_assessments" not in supabase.chains
        _assert_no_uuid_args(supabase)

    def test_database_error_returns_500(self, client_for):
        supabase = _farm_supabase()
        supabase.table("fields").execute.side_effect = APIError(
            {"message": "boom", "code": "XX000"}
        )
        resp = client_for(supabase).get(f"{_BASE}/score", params={"farm_id": _FARM_ID})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /csp/payments
# ---------------------------------------------------------------------------

class TestPayments:
    def test_response_shape_and_str_ids(self, client_for):
        supabase = _farm_supabase()
        resp = client_for(supabase).get(
            f"{_BASE}/payments",
            params={"farm_id": _FARM_ID, "contract_fiscal_year": 2026, "joint_operation": True},
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body) == _PAYMENT_KEYS
        assert set(body["rules"]) == _RULES_KEYS
        assert body["farm_id"] == _FARM_ID
        assert body["contract_limit"]["amount"] == 600_000.0
        assert body["annual_payment_limit"] is None
        for item in body["field_breakdown"]:
            assert set(item) == {
                "field_id", "field_name", "acres", "eap_annual",
                "activity_payment_annual", "total_annual",
            }
        _assert_no_uuid_args(supabase)


# ---------------------------------------------------------------------------
# GET /csp/enhancements
# ---------------------------------------------------------------------------

class TestEnhancements:
    def test_response_shape_and_str_farm_id(self, client_for):
        supabase = _farm_supabase()
        resp = client_for(supabase).get(
            f"{_BASE}/enhancements", params={"farm_id": _FARM_ID}
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body) == {"farm_id", "enhancements", "rules"}
        assert body["farm_id"] == _FARM_ID
        assert set(body["rules"]) == _RULES_KEYS
        assert body["enhancements"]
        assert {"code", "practice_standard_code", "priority_score", "rate_is_estimate"} <= set(
            body["enhancements"][0]
        )
        _assert_no_uuid_args(supabase)


# ---------------------------------------------------------------------------
# POST /csp/evaluate
# ---------------------------------------------------------------------------

class TestEvaluate:
    def test_response_shape_and_str_ids(self, client_for):
        supabase = _farm_supabase()
        resp = client_for(supabase).post(f"{_BASE}/evaluate", params={"farm_id": _FARM_ID})

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body) == {"status", "farm_id", "eligibility", "score", "payments", "evaluated_at"}
        assert body["status"] == "evaluation_complete"
        assert body["farm_id"] == _FARM_ID
        assert set(body["eligibility"]) == {
            "status", "is_eligible", "resource_concerns_meeting_threshold", "cart_score",
            "meets_ranking_threshold", "eligibility_notes", "recommended_enhancements",
        }
        assert set(body["score"]) == {
            "total_points", "max_possible_points", "state_ranking_threshold",
            "gap_to_threshold", "component_scores",
        }
        assert set(body["payments"]) == {
            "total_annual_payment", "total_5year_payment", "eap_annual",
            "activity_payment_annual", "payment_capped", "contract_limit",
            "annual_payment_limit", "rules",
        }
        payload = supabase.chains["csp_eligibility_assessments"].upsert.call_args.args[0]
        assert isinstance(payload["farm_id"], str)
        _assert_no_uuid_args(supabase)
