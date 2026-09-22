"""
Tests for app.routers.credits — EQIP/VCM eligibility endpoints.

Coverage targets:
  - GET /api/v1/credits/?farm_id= → latest EQIP and VCM rows; 404 unknown farm
  - POST /api/v1/credits/evaluate → both results with pinned timestamps and VCM
    estimate provenance; 500 (and nothing saved) on read failure; 500 on
    upsert failure; 404 unknown farm
  - GET /api/v1/credits/report → full report with data_warnings; read failures
    reported instead of silently dropped

The real EQIP/VCM services run against an in-memory fake Supabase client.
Auth, the Supabase client and the clock are replaced via dependency_overrides.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.auth.middleware import get_authenticated_client, get_current_user
from app.main import app
from app.routers.credits import get_utc_now
from app.services.credit_rules import VCM_METHOD_LABEL, VCM_RULES_AS_OF

_BASE = "/api/v1/credits"
_FARM_ID = "5b0f3c1e-2a4d-4c1e-9b2a-6d7e8f901234"
_FIELD_ID = "7c2d4e6f-1a3b-4c5d-8e9f-0a1b2c3d4e5f"
_PINNED_NOW = datetime(2026, 5, 4, 15, 30, tzinfo=timezone.utc)


def _api_error(message: str) -> APIError:
    """An APIError shaped like the one postgrest-py raises for a failed request."""
    return APIError({"message": message, "code": "XX000", "hint": None, "details": None})


# ---------------------------------------------------------------------------
# Fake Supabase
# ---------------------------------------------------------------------------

class _FakeQuery:
    def __init__(self, db: "_FakeSupabase", table: str):
        self._db = db
        self._table = table
        self._upsert_payload: dict | None = None

    def select(self, *_args, **_kwargs):
        return self

    eq = in_ = order = limit = single = select

    def upsert(self, payload, **_kwargs):
        self._upsert_payload = payload
        return self

    def execute(self):
        if self._upsert_payload is not None:
            if self._db.fail_upserts:
                raise _api_error("write failed")
            self._db.upserts.append(self._upsert_payload)
            return MagicMock(data=[{"id": f"row-{len(self._db.upserts)}", **self._upsert_payload}])
        if self._table in self._db.failing_reads:
            raise _api_error(f"{self._table} read failed")
        return MagicMock(data=self._db.tables.get(self._table, []))


class _FakeSupabase:
    def __init__(self, tables: dict, failing_reads: set[str] | None = None):
        self.tables = tables
        self.failing_reads = failing_reads or set()
        self.fail_upserts = False
        self.upserts: list[dict] = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self, name)


def _farm_tables(**overrides) -> dict:
    tables = {
        "farms": [{"id": _FARM_ID, "name": "Home Farm", "state": "IA", "county_fips": "19153",
                   "total_acres": 120.0, "goals": "both"}],
        "fields": [{"id": _FIELD_ID, "name": "North 40", "acres": 100.0, "crop_type": "corn",
                    "practices": ["340"]}],
        "recommendations": [{"field_id": _FIELD_ID, "practice_code": "340",
                             "title": "Cover Crop"}],
        "eqip_practices": [{"code": "340", "name": "Cover Crop", "category": "soil_health"}],
        "documents": [{"doc_type": "soil_report"}],
        "soil_profiles": [],
        "credit_eligibility": [],
    }
    tables.update(overrides)
    return tables


def _stored_row(program: str, status: str = "eligible") -> dict:
    return {
        "id": f"elig-{program}",
        "farm_id": _FARM_ID,
        "program": program,
        "status": status,
        "practices_documented": ["340"],
        "notes": f"stored {program} notes",
        "updated_at": "2026-04-01T00:00:00+00:00",
    }


@pytest.fixture
def make_client():
    def _make(supabase) -> TestClient:
        user = MagicMock()
        user.id = "user-credits-test"
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_authenticated_client] = lambda: supabase
        app.dependency_overrides[get_utc_now] = lambda: _PINNED_NOW
        return TestClient(app)

    try:
        yield _make
    finally:
        for dep in (get_current_user, get_authenticated_client, get_utc_now):
            app.dependency_overrides.pop(dep, None)


# ---------------------------------------------------------------------------
# GET /api/v1/credits/
# ---------------------------------------------------------------------------

class TestGetCreditEligibility:
    def test_returns_latest_rows_per_program(self, make_client):
        db = _FakeSupabase(_farm_tables(
            credit_eligibility=[_stored_row("VCM"), _stored_row("EQIP", "pending_review")]
        ))
        response = make_client(db).get(f"{_BASE}/?farm_id={_FARM_ID}")

        assert response.status_code == 200
        body = response.json()
        assert body["eqip"]["status"] == "pending_review"
        assert body["vcm"]["program"] == "VCM"

    def test_not_evaluated_programs_are_null(self, make_client):
        db = _FakeSupabase(_farm_tables())
        body = make_client(db).get(f"{_BASE}/?farm_id={_FARM_ID}").json()

        assert body["eqip"] is None
        assert body["vcm"] is None

    def test_unknown_farm_returns_404(self, make_client):
        db = _FakeSupabase(_farm_tables(farms=[]))
        response = make_client(db).get(f"{_BASE}/?farm_id={_FARM_ID}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/credits/evaluate
# ---------------------------------------------------------------------------

class TestEvaluateCredits:
    def test_evaluate_returns_both_programs(self, make_client):
        db = _FakeSupabase(_farm_tables())
        response = make_client(db).post(f"{_BASE}/evaluate?farm_id={_FARM_ID}")

        assert response.status_code == 200
        body = response.json()
        assert body["eqip"]["eligibility_status"] == "eligible"
        assert body["vcm"]["eligibility_status"] == "eligible"
        # 100 ac × 0.5 lower-bound rate (no soil data)
        assert body["vcm"]["estimated_total_credits"] == pytest.approx(50.0)
        assert {u["program"] for u in db.upserts} == {"EQIP", "VCM"}

    def test_evaluate_uses_pinned_clock(self, make_client):
        db = _FakeSupabase(_farm_tables())
        body = make_client(db).post(f"{_BASE}/evaluate?farm_id={_FARM_ID}").json()

        assert all(u["updated_at"] == _PINNED_NOW.isoformat() for u in db.upserts)
        assert body["eqip"]["updated_at"].startswith("2026-05-04T15:30:00")

    def test_vcm_result_is_labelled_as_estimate(self, make_client):
        db = _FakeSupabase(_farm_tables())
        vcm = make_client(db).post(f"{_BASE}/evaluate?farm_id={_FARM_ID}").json()["vcm"]

        assert vcm["is_estimate"] is True
        assert vcm["method_label"] == VCM_METHOD_LABEL
        assert vcm["program_name"] == VCM_METHOD_LABEL
        assert vcm["rules_as_of"] == VCM_RULES_AS_OF
        assert vcm["rules_source_url"] is None

    @pytest.mark.parametrize("failing_table", ["recommendations", "documents", "soil_profiles"])
    def test_read_failure_returns_500_and_saves_nothing_wrong(self, make_client, failing_table):
        """A failed read must not be persisted as a not_eligible result."""
        db = _FakeSupabase(_farm_tables(), failing_reads={failing_table})
        response = make_client(db).post(f"{_BASE}/evaluate?farm_id={_FARM_ID}")

        assert response.status_code == 500
        assert "could not be loaded or saved" in response.json()["detail"]
        assert all(u["status"] != "not_eligible" for u in db.upserts)

    def test_upsert_failure_returns_500(self, make_client):
        db = _FakeSupabase(_farm_tables())
        db.fail_upserts = True
        response = make_client(db).post(f"{_BASE}/evaluate?farm_id={_FARM_ID}")

        assert response.status_code == 500
        assert response.json()["detail"].startswith("EQIP evaluation could not be completed")

    def test_data_error_detail_is_fixed_and_logged_with_farm_id(self, make_client, caplog):
        """The internal CreditDataError text (it names tables) must not reach the client."""
        db = _FakeSupabase(_farm_tables(), failing_reads={"documents"})
        with caplog.at_level("ERROR", logger="app.routers.credits"):
            response = make_client(db).post(f"{_BASE}/evaluate?farm_id={_FARM_ID}")

        detail = response.json()["detail"]
        assert response.status_code == 500
        assert "documents" not in detail
        assert "could not read" not in detail
        assert any(
            _FARM_ID in r.getMessage() and "could not read documents" in r.getMessage()
            for r in caplog.records
        )

    def test_non_data_error_is_not_masked(self, make_client, monkeypatch):
        """A bug in an engine propagates instead of being reported as a data error."""
        async def _broken_engine(*_args, **_kwargs):
            raise TypeError("bug")

        monkeypatch.setattr("app.routers.credits.evaluate_eqip_eligibility", _broken_engine)
        db = _FakeSupabase(_farm_tables())
        with pytest.raises(TypeError):
            make_client(db).post(f"{_BASE}/evaluate?farm_id={_FARM_ID}")

    def test_unknown_farm_returns_404(self, make_client):
        db = _FakeSupabase(_farm_tables(farms=[]))
        response = make_client(db).post(f"{_BASE}/evaluate?farm_id={_FARM_ID}")

        assert response.status_code == 404
        assert db.upserts == []


# ---------------------------------------------------------------------------
# GET /api/v1/credits/report
# ---------------------------------------------------------------------------

class TestCreditReport:
    def test_report_with_stored_results(self, make_client):
        db = _FakeSupabase(_farm_tables(
            credit_eligibility=[_stored_row("EQIP"), _stored_row("VCM")]
        ))
        response = make_client(db).get(f"{_BASE}/report?farm_id={_FARM_ID}")

        assert response.status_code == 200
        body = response.json()
        assert body["generated_at"] == _PINNED_NOW.isoformat()
        assert body["data_warnings"] == []
        assert body["farm"]["name"] == "Home Farm"
        assert body["fields"][0]["id"] == _FIELD_ID
        assert body["eqip"]["notes"] == "stored EQIP notes"
        assert body["vcm"]["field_breakdown"][0]["field_id"] == _FIELD_ID
        assert body["vcm"]["is_estimate"] is True
        assert body["vcm"]["rules_as_of"] == VCM_RULES_AS_OF

    def test_report_rerun_of_vcm_writes_credit_eligibility(self, make_client):
        """Documents the GET side effect: the VCM re-run upserts the stored row."""
        db = _FakeSupabase(_farm_tables(credit_eligibility=[_stored_row("VCM")]))
        make_client(db).get(f"{_BASE}/report?farm_id={_FARM_ID}")

        assert [u["program"] for u in db.upserts] == ["VCM"]

    def test_report_without_evaluations(self, make_client):
        db = _FakeSupabase(_farm_tables())
        body = make_client(db).get(f"{_BASE}/report?farm_id={_FARM_ID}").json()

        assert body["eqip"]["status"] is None
        assert "has not been run" in body["eqip"]["notes"]
        assert body["vcm"]["status"] is None
        assert body["vcm"]["is_estimate"] is True
        assert db.upserts == []

    def test_fields_read_failure_is_reported(self, make_client):
        db = _FakeSupabase(_farm_tables(), failing_reads={"fields"})
        response = make_client(db).get(f"{_BASE}/report?farm_id={_FARM_ID}")

        assert response.status_code == 200
        body = response.json()
        assert body["fields"] == []
        assert any("Field list" in w for w in body["data_warnings"])

    def test_eligibility_read_failure_is_reported(self, make_client):
        db = _FakeSupabase(_farm_tables(), failing_reads={"credit_eligibility"})
        body = make_client(db).get(f"{_BASE}/report?farm_id={_FARM_ID}").json()

        assert any("EQIP and VCM" in w for w in body["data_warnings"])
        assert "could not be loaded" in body["eqip"]["notes"]

    def test_vcm_rerun_failure_falls_back_to_stored_row_with_warning(self, make_client):
        db = _FakeSupabase(
            _farm_tables(credit_eligibility=[_stored_row("VCM")]),
            failing_reads={"recommendations"},
        )
        body = make_client(db).get(f"{_BASE}/report?farm_id={_FARM_ID}").json()

        assert body["vcm"]["notes"] == "stored VCM notes"
        assert body["vcm"]["field_breakdown"] == []
        assert any("recalculated" in w for w in body["data_warnings"])

    def test_unknown_farm_returns_404(self, make_client):
        db = _FakeSupabase(_farm_tables(farms=[]))
        response = make_client(db).get(f"{_BASE}/report?farm_id={_FARM_ID}")
        assert response.status_code == 404
