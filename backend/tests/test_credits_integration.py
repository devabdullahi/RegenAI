"""
Integration tests for app.routers.credits — Credits router endpoints.

Coverage targets:
  POST /credits/evaluate
  - Valid farm → evaluation_complete with eqip and vcm results
  - Eligible path (with documents) and pending_review path (no documents)
  - Service ValueError → 400, unexpected exception → 500
  - Farm not owned by user → 404

  GET /credits/
  - Returns latest eqip and vcm rows from credit_eligibility
  - No evaluation done → both null

  GET /credits/report
  - Full payload with farm, fields, eqip, vcm, generated_at
  - No prior evaluation → null status + instruction notes
  - VCM re-estimation gating logic
  - Authorization: farm not accessible → 404

All Supabase I/O and auth dependencies are overridden via FastAPI
dependency_overrides. Service functions are patched at the credits router
namespace for POST /evaluate tests.
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.auth.middleware import get_authenticated_client, get_current_user
from app.main import app
from tests.conftest import FIELD_ID_A, FIELD_ID_B, _make_chain


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_FARM_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_NOW_ISO = "2026-04-30T12:00:00+00:00"

_FARM_DB_ROW = {
    "id": _FARM_UUID,
    "name": "Greenfield Farm",
    "state": "IA",
    "county_fips": "19153",
    "total_acres": 320.0,
    "goals": "carbon_credits",
}

_FIELD_ROWS = [
    {
        "id": FIELD_ID_A,
        "name": "North 40",
        "acres": 120.0,
        "crop_type": "corn",
        "practices": ["340", "329"],
    },
    {
        "id": FIELD_ID_B,
        "name": "South 60",
        "acres": 80.0,
        "crop_type": "soybeans",
        "practices": ["328"],
    },
]

_EQIP_ELIGIBILITY_ROW = {
    "id": "elig-eqip-0001",
    "farm_id": _FARM_UUID,
    "program": "EQIP",
    "status": "eligible",
    "practices_documented": ["329", "340"],
    "notes": "EQIP-eligible practices identified.",
    "updated_at": _NOW_ISO,
}

_VCM_ELIGIBILITY_ROW = {
    "id": "elig-vcm-0001",
    "farm_id": _FARM_UUID,
    "program": "VCM",
    "status": "eligible",
    "practices_documented": ["329", "340"],
    "notes": "Soil Carbon Protocol estimate: 180.00 total credit units.",
    "updated_at": _NOW_ISO,
}

_EQIP_SERVICE_RESULT = {
    "farm_id": _FARM_UUID,
    "program": "EQIP",
    "status": "eligible",
    "practices_documented": ["329", "340"],
    "notes": "EQIP-eligible practices identified: 340 – Cover Crop, 329 – No-Till.",
    "updated_at": _NOW_ISO,
}

_VCM_SERVICE_RESULT = {
    "farm_id": _FARM_UUID,
    "program": "VCM",
    "program_name": "Soil Carbon Protocol",
    "status": "eligible",
    "practices_documented": ["329", "340"],
    "estimated_total_credits": 180.0,
    "field_breakdown": [
        {
            "field_id": FIELD_ID_A,
            "field_name": "North 40",
            "acres": 120.0,
            "practices": [
                {
                    "practice_code": "340",
                    "practice_name": "Cover Crop",
                    "rate_credits_per_acre": 1.2,
                    "estimated_credits": 144.0,
                },
                {
                    "practice_code": "329",
                    "practice_name": "No-Till",
                    "rate_credits_per_acre": 0.3,
                    "estimated_credits": 36.0,
                },
            ],
            "field_total_credits": 180.0,
        }
    ],
    "notes": "Soil Carbon Protocol estimate: 180.00 total credit units.",
    "updated_at": _NOW_ISO,
}

_EQIP_SERVICE_RESULT_PENDING = {
    **_EQIP_SERVICE_RESULT,
    "status": "pending_review",
    "notes": (
        "EQIP-eligible practices identified: 340 – Cover Crop. "
        "No supporting documents found. Upload at least one document."
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user(user_id: str = "user-test-001") -> MagicMock:
    user = MagicMock()
    user.id = user_id
    return user


@contextmanager
def _override_auth(supabase):
    """Set FastAPI dependency_overrides for auth, then clean up."""
    user = _mock_user()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_authenticated_client] = lambda: supabase
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_authenticated_client, None)


def _supabase_that_finds_farm(farm_row: dict = _FARM_DB_ROW) -> MagicMock:
    mock = MagicMock()
    chain = _make_chain(data=farm_row)
    mock.table.return_value = chain
    return mock


def _supabase_that_denies_farm() -> MagicMock:
    mock = MagicMock()

    class _FakeAPIError(APIError):
        def __init__(self) -> None:
            Exception.__init__(self, "PGRST116: no rows found")

    def _raise(*_a, **_kw):
        raise _FakeAPIError()

    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.single.return_value = chain
    chain.execute.side_effect = _raise
    mock.table.return_value = chain
    return mock


def _make_credits_supabase(
    farm_row: dict | None = None,
    eligibility_rows: list[dict] | None = None,
    field_rows: list[dict] | None = None,
) -> MagicMock:
    farm_row = farm_row if farm_row is not None else _FARM_DB_ROW
    eligibility_rows = eligibility_rows if eligibility_rows is not None else []
    field_rows = field_rows if field_rows is not None else list(_FIELD_ROWS)

    mock = MagicMock()

    def _table(name: str):
        if name == "farms":
            return _make_chain(data=farm_row)
        if name == "credit_eligibility":
            return _make_chain(data=eligibility_rows)
        if name == "fields":
            return _make_chain(data=field_rows)
        return _make_chain(data=None)

    mock.table.side_effect = _table
    return mock


# ---------------------------------------------------------------------------
# POST /credits/evaluate — happy paths
# ---------------------------------------------------------------------------

class TestEvaluateCreditsHappyPath:

    def test_returns_evaluation_complete_status(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(return_value=_EQIP_SERVICE_RESULT)), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        assert r.status_code == 200
        assert r.json()["status"] == "evaluation_complete"

    def test_returns_farm_id_in_response(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(return_value=_EQIP_SERVICE_RESULT)), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        assert r.json()["farm_id"] == _FARM_UUID

    def test_returns_eqip_section(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(return_value=_EQIP_SERVICE_RESULT)), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        eqip = r.json()["eqip"]
        assert eqip["program"] == "EQIP"
        assert "eligibility_status" in eqip

    def test_returns_vcm_section(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(return_value=_EQIP_SERVICE_RESULT)), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        vcm = r.json()["vcm"]
        assert vcm["program"] == "VCM"
        assert vcm["program_name"] == "Soil Carbon Protocol"

    def test_eqip_eligible_path(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(return_value=_EQIP_SERVICE_RESULT)), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        assert r.json()["eqip"]["eligibility_status"] == "eligible"

    def test_eqip_pending_review_path(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(return_value=_EQIP_SERVICE_RESULT_PENDING)), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        eqip = r.json()["eqip"]
        assert eqip["eligibility_status"] == "pending_review"

    def test_practices_documented_forwarded(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(return_value=_EQIP_SERVICE_RESULT)), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        body = r.json()
        assert "329" in body["eqip"]["practices_documented"]
        assert "329" in body["vcm"]["practices_documented"]

    def test_vcm_estimated_credits(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(return_value=_EQIP_SERVICE_RESULT)), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        assert r.json()["vcm"]["estimated_total_credits"] == 180.0

    def test_eqip_service_called_with_farm_id(self):
        sb = _supabase_that_finds_farm()
        eqip_mock = AsyncMock(return_value=_EQIP_SERVICE_RESULT)
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=eqip_mock), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        eqip_mock.assert_awaited_once()
        assert eqip_mock.await_args.args[0] == _FARM_UUID


# ---------------------------------------------------------------------------
# POST /credits/evaluate — error propagation
# ---------------------------------------------------------------------------

class TestEvaluateCreditsErrors:

    def test_eqip_value_error_returns_400(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(side_effect=ValueError("No fields"))), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        assert r.status_code == 400

    def test_eqip_unexpected_exception_returns_500(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(side_effect=RuntimeError("boom"))), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        assert r.status_code == 500

    def test_vcm_value_error_returns_400(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(return_value=_EQIP_SERVICE_RESULT)), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(side_effect=ValueError("No fields"))):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        assert r.status_code == 400

    def test_vcm_unexpected_exception_returns_500(self):
        sb = _supabase_that_finds_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(return_value=_EQIP_SERVICE_RESULT)), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(side_effect=OSError("timeout"))):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# POST /credits/evaluate — authorization
# ---------------------------------------------------------------------------

class TestEvaluateCreditsAuth:

    def test_farm_not_owned_returns_404(self):
        sb = _supabase_that_denies_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=AsyncMock(return_value=_EQIP_SERVICE_RESULT)), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        assert r.status_code == 404

    def test_services_not_called_when_farm_denied(self):
        sb = _supabase_that_denies_farm()
        eqip_mock = AsyncMock(return_value=_EQIP_SERVICE_RESULT)
        vcm_mock = AsyncMock(return_value=_VCM_SERVICE_RESULT)
        with _override_auth(sb), \
             patch("app.routers.credits.evaluate_eqip_eligibility", new=eqip_mock), \
             patch("app.routers.credits.estimate_vcm_credits", new=vcm_mock):
            TestClient(app).post("/api/v1/credits/evaluate", params={"farm_id": _FARM_UUID})
        eqip_mock.assert_not_awaited()
        vcm_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# GET /credits/ — latest eligibility read
# ---------------------------------------------------------------------------

class TestGetCreditEligibility:

    def test_returns_eqip_and_vcm(self):
        sb = _make_credits_supabase(eligibility_rows=[_EQIP_ELIGIBILITY_ROW, _VCM_ELIGIBILITY_ROW])
        with _override_auth(sb):
            r = TestClient(app).get("/api/v1/credits/", params={"farm_id": _FARM_UUID})
        assert r.status_code == 200
        assert r.json()["eqip"]["program"] == "EQIP"
        assert r.json()["vcm"]["program"] == "VCM"

    def test_returns_farm_id(self):
        sb = _make_credits_supabase(eligibility_rows=[_EQIP_ELIGIBILITY_ROW])
        with _override_auth(sb):
            r = TestClient(app).get("/api/v1/credits/", params={"farm_id": _FARM_UUID})
        assert r.json()["farm_id"] == _FARM_UUID

    def test_null_eqip_when_not_evaluated(self):
        sb = _make_credits_supabase(eligibility_rows=[_VCM_ELIGIBILITY_ROW])
        with _override_auth(sb):
            r = TestClient(app).get("/api/v1/credits/", params={"farm_id": _FARM_UUID})
        assert r.json()["eqip"] is None

    def test_null_vcm_when_not_evaluated(self):
        sb = _make_credits_supabase(eligibility_rows=[_EQIP_ELIGIBILITY_ROW])
        with _override_auth(sb):
            r = TestClient(app).get("/api/v1/credits/", params={"farm_id": _FARM_UUID})
        assert r.json()["vcm"] is None

    def test_both_null_when_no_evaluation(self):
        sb = _make_credits_supabase(eligibility_rows=[])
        with _override_auth(sb):
            r = TestClient(app).get("/api/v1/credits/", params={"farm_id": _FARM_UUID})
        assert r.json()["eqip"] is None
        assert r.json()["vcm"] is None

    def test_farm_not_accessible_returns_404(self):
        sb = _supabase_that_denies_farm()
        with _override_auth(sb):
            r = TestClient(app).get("/api/v1/credits/", params={"farm_id": _FARM_UUID})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /credits/report — full report
# ---------------------------------------------------------------------------

class TestGetCreditReport:

    def test_returns_200_with_report_type(self):
        sb = _make_credits_supabase(eligibility_rows=[_EQIP_ELIGIBILITY_ROW, _VCM_ELIGIBILITY_ROW])
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        assert r.status_code == 200
        assert r.json()["report_type"] == "credit_eligibility"

    def test_report_contains_farm_section(self):
        sb = _make_credits_supabase(eligibility_rows=[_EQIP_ELIGIBILITY_ROW, _VCM_ELIGIBILITY_ROW])
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        farm = r.json()["farm"]
        assert farm["name"] == "Greenfield Farm"
        assert farm["state"] == "IA"
        assert farm["total_acres"] == 320.0

    def test_report_contains_fields(self):
        sb = _make_credits_supabase(eligibility_rows=[_EQIP_ELIGIBILITY_ROW, _VCM_ELIGIBILITY_ROW])
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        fields = r.json()["fields"]
        assert len(fields) == 2
        names = {f["name"] for f in fields}
        assert "North 40" in names

    def test_eqip_status_in_report(self):
        sb = _make_credits_supabase(eligibility_rows=[_EQIP_ELIGIBILITY_ROW, _VCM_ELIGIBILITY_ROW])
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        assert r.json()["eqip"]["status"] == "eligible"

    def test_vcm_estimated_credits_in_report(self):
        sb = _make_credits_supabase(eligibility_rows=[_EQIP_ELIGIBILITY_ROW, _VCM_ELIGIBILITY_ROW])
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        assert r.json()["vcm"]["estimated_total_credits"] == 180.0

    def test_vcm_field_breakdown_in_report(self):
        sb = _make_credits_supabase(eligibility_rows=[_EQIP_ELIGIBILITY_ROW, _VCM_ELIGIBILITY_ROW])
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        breakdown = r.json()["vcm"]["field_breakdown"]
        assert len(breakdown) == 1
        assert breakdown[0]["field_name"] == "North 40"

    def test_report_has_generated_at(self):
        sb = _make_credits_supabase(eligibility_rows=[_EQIP_ELIGIBILITY_ROW, _VCM_ELIGIBILITY_ROW])
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        generated_at = r.json()["generated_at"]
        assert generated_at
        datetime.fromisoformat(generated_at)


# ---------------------------------------------------------------------------
# GET /credits/report — no prior evaluation
# ---------------------------------------------------------------------------

class TestGetCreditReportNoEvaluation:

    def test_eqip_status_null(self):
        sb = _make_credits_supabase(eligibility_rows=[])
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        assert r.status_code == 200
        assert r.json()["eqip"]["status"] is None

    def test_eqip_notes_mention_evaluate(self):
        sb = _make_credits_supabase(eligibility_rows=[])
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        assert "evaluate" in r.json()["eqip"]["notes"].lower()

    def test_vcm_status_null(self):
        sb = _make_credits_supabase(eligibility_rows=[])
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        assert r.json()["vcm"]["status"] is None

    def test_vcm_credits_zero(self):
        sb = _make_credits_supabase(eligibility_rows=[])
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        assert r.json()["vcm"]["estimated_total_credits"] == 0.0

    def test_vcm_not_re_estimated_without_record(self):
        sb = _make_credits_supabase(eligibility_rows=[])
        vcm_mock = AsyncMock(return_value=_VCM_SERVICE_RESULT)
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=vcm_mock):
            TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        vcm_mock.assert_not_awaited()

    def test_vcm_re_estimated_with_record(self):
        sb = _make_credits_supabase(eligibility_rows=[_VCM_ELIGIBILITY_ROW])
        vcm_mock = AsyncMock(return_value=_VCM_SERVICE_RESULT)
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=vcm_mock):
            TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        vcm_mock.assert_awaited_once()


# ---------------------------------------------------------------------------
# GET /credits/report — authorization
# ---------------------------------------------------------------------------

class TestGetCreditReportAuth:

    def test_farm_not_owned_returns_404(self):
        sb = _supabase_that_denies_farm()
        with _override_auth(sb), \
             patch("app.routers.credits.estimate_vcm_credits", new=AsyncMock(return_value=_VCM_SERVICE_RESULT)):
            r = TestClient(app).get("/api/v1/credits/report", params={"farm_id": _FARM_UUID})
        assert r.status_code == 404
