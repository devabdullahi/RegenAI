"""
Tests for app.services.program_deadlines and GET /api/v1/csp/deadlines.

All tests inject "today" so results do not drift as real dates pass.
"""

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.middleware import get_authenticated_client, get_current_user
from app.main import app
from app.models.schemas import DeadlineUrgency, ProgramDeadlineStatus
from app.services.program_deadlines import (
    ALL_STATES,
    PROGRAM_DEADLINES,
    COVERED_STATES,
    build_deadlines_response,
    compute_urgency,
    get_upcoming_deadlines,
    today_central,
)

TODAY = date(2026, 9, 13)


def _ids(items):
    return [i.id for i in items]


# ---------------------------------------------------------------------------
# Urgency thresholds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (0, DeadlineUrgency.urgent),
        (14, DeadlineUrgency.urgent),
        (15, DeadlineUrgency.soon),
        (45, DeadlineUrgency.soon),
        (46, DeadlineUrgency.later),
        (365, DeadlineUrgency.later),
    ],
)
def test_compute_urgency_thresholds(days, expected):
    assert compute_urgency(days) == expected


# ---------------------------------------------------------------------------
# Filtering and sorting
# ---------------------------------------------------------------------------

def test_iowa_sept_25_is_urgent_with_12_days():
    items = get_upcoming_deadlines("IA", TODAY)
    first = items[0]
    assert first.id == "ia-nrcs-fy2027"
    assert first.deadline_date == date(2026, 9, 25)
    assert first.days_remaining == 12
    assert first.urgency == DeadlineUrgency.urgent
    assert first.status == ProgramDeadlineStatus.confirmed


def test_filters_to_state_plus_all_states():
    items = get_upcoming_deadlines("IA", TODAY)
    assert {i.state for i in items} == {"IA", ALL_STATES}
    assert "wi-nrcs-fy2027" not in _ids(items)
    assert "all-sdrp-2026" in _ids(items)


def test_state_is_case_insensitive():
    assert _ids(get_upcoming_deadlines("ia", TODAY)) == _ids(get_upcoming_deadlines("IA", TODAY))


def test_sorted_by_date_then_undated():
    items = get_upcoming_deadlines("IA", TODAY)
    assert _ids(items) == ["ia-nrcs-fy2027", "all-sdrp-2026", "ia-cover-crop-discount-2027"]
    sdrp = items[1]
    assert sdrp.days_remaining == 17
    assert sdrp.urgency == DeadlineUrgency.soon


def test_wisconsin_order_and_urgency():
    items = get_upcoming_deadlines("WI", TODAY)
    assert _ids(items)[:2] == ["wi-nrcs-fy2027", "all-sdrp-2026"]
    assert items[0].days_remaining == 5
    assert items[0].urgency == DeadlineUrgency.urgent


def test_indiana_december_is_later():
    item = next(i for i in get_upcoming_deadlines("IN", TODAY) if i.id == "in-nrcs-fy2027")
    assert item.days_remaining == 96
    assert item.urgency == DeadlineUrgency.later


def test_excludes_past_dates():
    items = get_upcoming_deadlines("IA", date(2026, 9, 26))
    assert "ia-nrcs-fy2027" not in _ids(items)
    assert _ids(items)[0] == "all-sdrp-2026"
    assert items[0].urgency == DeadlineUrgency.urgent

    after_sdrp = get_upcoming_deadlines("IA", date(2026, 10, 1))
    assert "all-sdrp-2026" not in _ids(after_sdrp)
    assert all(i.deadline_date is None for i in after_sdrp)


def test_deadline_today_is_kept_with_zero_days():
    item = get_upcoming_deadlines("IA", date(2026, 9, 25))[0]
    assert item.id == "ia-nrcs-fy2027"
    assert item.days_remaining == 0
    assert item.urgency == DeadlineUrgency.urgent


# ---------------------------------------------------------------------------
# not_announced / expected handling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("state", "slug"),
    [
        ("IL", "state-offices/illinois"),
        ("KS", "state-offices/kansas"),
        ("MN", "state-offices/minnesota"),
        ("MO", "nrcs/missouri"),
        ("NE", "state-offices/nebraska"),
        ("OH", "state-offices/ohio"),
    ],
)
def test_not_announced_states_point_to_state_office(state, slug):
    items = get_upcoming_deadlines(state, TODAY)
    nrcs = next(i for i in items if i.id == f"{state.lower()}-nrcs-fy2027")
    assert nrcs.status == ProgramDeadlineStatus.not_announced
    assert nrcs.deadline_date is None
    assert nrcs.days_remaining is None
    assert nrcs.urgency is None
    assert nrcs.source_url == f"https://www.nrcs.usda.gov/{slug}"


def test_undated_nrcs_sorted_before_expected():
    items = get_upcoming_deadlines("IL", TODAY)
    assert _ids(items) == ["all-sdrp-2026", "il-nrcs-fy2027", "il-cover-crop-discount-2027"]
    assert items[2].status == ProgramDeadlineStatus.expected
    assert "NRCS cost-share" in (items[2].notes or "")


def test_covered_state_without_a_published_cutoff_is_not_announced():
    # Alabama is covered nationwide but NRCS has not published an FY2027
    # cutoff, so it still gets its own entry (pointing at the state office)
    # with no date rather than a generic or invented one.
    items = get_upcoming_deadlines("AL", TODAY)
    assert _ids(items) == ["all-sdrp-2026", "al-nrcs-fy2027"]
    assert items[1].status == ProgramDeadlineStatus.not_announced
    assert items[1].deadline_date is None


def test_covered_state_with_a_sourced_cutoff_is_confirmed():
    items = get_upcoming_deadlines("TX", TODAY)
    assert _ids(items) == ["all-sdrp-2026", "tx-nrcs-fy2027"]
    assert items[1].status == ProgramDeadlineStatus.confirmed
    assert items[1].deadline_date == date(2026, 11, 13)
    assert items[1].source_url


def test_unknown_state_code_gets_generic_entry():
    items = get_upcoming_deadlines("ZZ", TODAY)
    assert _ids(items) == ["all-sdrp-2026", "zz-nrcs-generic"]
    assert items[1].status == ProgramDeadlineStatus.not_announced


def test_no_state_returns_national():
    resp = build_deadlines_response(None, TODAY)
    assert resp.state == "NATIONAL"
    assert resp.today == TODAY
    assert _ids(resp.deadlines) == ["all-sdrp-2026", "national-nrcs-generic"]


def test_legacy_fields_populated():
    item = get_upcoming_deadlines("IA", TODAY)[0]
    assert item.cutoff_date == item.deadline_date
    assert item.signup_period == item.period_label


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------

def test_every_target_state_has_an_nrcs_entry():
    for state in COVERED_STATES:
        assert any(e.id == f"{state.lower()}-nrcs-fy2027" for e in PROGRAM_DEADLINES), state


def test_table_entries_are_consistent():
    ids = [e.id for e in PROGRAM_DEADLINES]
    assert len(ids) == len(set(ids))
    for e in PROGRAM_DEADLINES:
        assert e.source_url.startswith("https://"), e.id
        assert e.state in (*COVERED_STATES, ALL_STATES), e.id
        if e.status == ProgramDeadlineStatus.confirmed:
            assert e.deadline_date is not None, e.id
        else:
            assert e.deadline_date is None, e.id


def test_today_central_returns_date():
    assert isinstance(today_central(), date)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_authenticated_client] = lambda: MagicMock()
    app.dependency_overrides[today_central] = lambda: TODAY
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_authenticated_client, None)
        app.dependency_overrides.pop(today_central, None)


def test_router_returns_state_deadlines(client):
    resp = client.get("/api/v1/csp/deadlines", params={"state": "IA"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "IA"
    assert body["today"] == "2026-09-13"
    first = body["deadlines"][0]
    assert first["id"] == "ia-nrcs-fy2027"
    assert first["deadline_date"] == "2026-09-25"
    assert first["cutoff_date"] == "2026-09-25"
    assert first["days_remaining"] == 12
    assert first["urgency"] == "urgent"
    assert first["status"] == "confirmed"
    assert first["source_url"].startswith("https://")
    assert first["as_of"] == "2026-09-13"


def test_router_rejects_invalid_state(client):
    resp = client.get("/api/v1/csp/deadlines", params={"state": "Iowa"})
    assert resp.status_code == 400


def test_router_without_state(client):
    resp = client.get("/api/v1/csp/deadlines")
    assert resp.status_code == 200
    assert resp.json()["state"] == "NATIONAL"
