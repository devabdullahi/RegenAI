"""
Shared pytest fixtures for CSP Navigator tests.

Provides a reusable mock Supabase client that prevents any real network
calls. Each builder method (table → select/eq/in_/order/single/upsert)
returns a chainable MagicMock so test files can configure return values
per-test without touching real infrastructure.
"""

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Global test isolation
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    """Disable slowapi limits during tests.

    The limiter is a process-wide in-memory singleton (app.rate_limit), so
    without this, request counts accumulate across TestClient instances and
    router tests become order-dependent (429s once a limit such as 30/hour
    is exhausted).
    """
    from app.rate_limit import limiter

    previous = limiter.enabled
    limiter.enabled = False
    try:
        yield
    finally:
        limiter.enabled = previous


# ---------------------------------------------------------------------------
# Supabase mock helpers
# ---------------------------------------------------------------------------

def _make_chain(**execute_return):
    """Return a MagicMock that supports arbitrary chaining and ends with .execute().

    Any attribute access or call returns the same object, except .execute()
    which returns a MagicMock with the provided keyword attrs set.
    """
    chain = MagicMock()
    result = MagicMock()
    for k, v in execute_return.items():
        setattr(result, k, v)
    chain.execute.return_value = result
    # Make every chainable method return the chain itself
    for method in ("select", "eq", "in_", "order", "single", "limit", "upsert"):
        getattr(chain, method).return_value = chain
    return chain


def make_supabase_mock(table_responses: dict | None = None):
    """Build a Supabase client mock pre-configured with table-level responses.

    Args:
        table_responses: Mapping of table-name → dict with key 'data' set to
            whatever .execute().data should return for that table.  Tables not
            listed default to returning data=None.

    Returns:
        A MagicMock that implements supabase.table(name).select(...).execute()
        and supabase.table(name).upsert(...).execute() call chains.
    """
    table_responses = table_responses or {}

    def _table(name: str):
        resp_data = table_responses.get(name, {}).get("data", None)
        return _make_chain(data=resp_data)

    mock = MagicMock()
    mock.table.side_effect = _table
    return mock


# ---------------------------------------------------------------------------
# Canonical farm/field fixtures used across multiple test modules
# ---------------------------------------------------------------------------

FARM_ID = "farm-uuid-1234"
FIELD_ID_A = "field-uuid-aaaa"
FIELD_ID_B = "field-uuid-bbbb"

FARM_ROW = {
    "id": FARM_ID,
    "state": "IA",
    "total_acres": 200.0,
}

FIELD_ROWS = [
    {
        "id": FIELD_ID_A,
        "name": "North 40",
        "acres": 120.0,
        "crop_type": "corn",
        "practices": ["340", "329", "590"],
    },
    {
        "id": FIELD_ID_B,
        "name": "South 60",
        "acres": 80.0,
        "crop_type": "soybeans",
        "practices": ["328", "393"],
    },
]

SOIL_ROWS = [
    {"field_id": FIELD_ID_A, "organic_matter_pct": 3.5},  # medium tier
    {"field_id": FIELD_ID_B, "organic_matter_pct": 2.0},  # low tier
]

RECOMMENDATION_ROWS: list[dict] = []  # no acted recs by default


@pytest.fixture
def farm_row():
    return dict(FARM_ROW)


@pytest.fixture
def field_rows():
    return [dict(f) for f in FIELD_ROWS]


@pytest.fixture
def soil_rows():
    return [dict(r) for r in SOIL_ROWS]


@pytest.fixture
def standard_supabase(farm_row, field_rows, soil_rows):
    """Full mock for scoring/eligibility/payment tests with a realistic farm."""
    return make_supabase_mock(
        {
            "farms": {"data": farm_row},
            "fields": {"data": field_rows},
            "soil_profiles": {"data": soil_rows},
            "recommendations": {"data": RECOMMENDATION_ROWS},
            "csp_eligibility_assessments": {"data": None},
            "csp_enhancement_activities": {"data": []},
        }
    )
