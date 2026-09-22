"""
Tests for app.services.activity_log — Field activity CRUD, APH, and summary.

Coverage targets:
  - create_activity with valid planting data → success
  - create_activity with future date → HTTPException 422
  - create_activity with restricted-use spray and missing credentials → 422
  - create_activity with acres_applied exceeding field acres → 422
  - list_activities with activity_type filter
  - list_activities with date range filter
  - list_activities pagination (offset + limit)
  - get_activity for existing record → returns row
  - get_activity for missing record → 404
  - delete_activity for existing record → calls DB delete
  - get_activity_summary with multi-field farm → correct aggregation
  - get_activity_summary with no fields → returns zero counts
  - calculate_aph with exactly 4 years → success
  - calculate_aph with 3 years → 422
  - calculate_aph with 12 years → uses only last 10
  - create_yield_history upsert → success
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock, call
from uuid import UUID
from fastapi import HTTPException

from tests.conftest import make_supabase_mock, _make_chain
from app.models.schemas import ActivityCreate, ActivityType, ActivityUpdate, YieldHistoryCreate


# ---------------------------------------------------------------------------
# Constants
# Use proper UUID strings throughout so the service's UUID() constructor succeeds.
# ---------------------------------------------------------------------------

_FARM_ID = "12345678-1234-5678-1234-567812345600"
_FIELD_ID_A_STR = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_FIELD_ID_B_STR = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

_FIELD_UUID_A = UUID(_FIELD_ID_A_STR)
_FIELD_UUID_B = UUID(_FIELD_ID_B_STR)
_FARM_UUID = UUID("12345678-1234-5678-1234-567812345678")

_FIELD_ROW_A = {"id": _FIELD_ID_A_STR, "farm_id": _FARM_ID, "acres": 120.0, "name": "North 40"}
_FIELD_ROW_B = {"id": _FIELD_ID_B_STR, "farm_id": _FARM_ID, "acres": 80.0, "name": "South 60"}

_TODAY = date.today()
_YESTERDAY = _TODAY - timedelta(days=1)
_TOMORROW = _TODAY + timedelta(days=1)

_ACTIVITY_ROW = {
    "id": "act-uuid-1",
    "field_id": _FIELD_ID_A_STR,
    "activity_type": "plant",
    "activity_date": _YESTERDAY.isoformat(),
    "restricted_use": False,
    "created_at": "2026-04-01T10:00:00+00:00",
    "updated_at": "2026-04-01T10:00:00+00:00",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_activity_create(**kwargs) -> ActivityCreate:
    defaults = {
        "field_id": _FIELD_UUID_A,
        "activity_type": ActivityType.plant,
        "activity_date": _YESTERDAY,
    }
    defaults.update(kwargs)
    return ActivityCreate(**defaults)


def _make_supabase_for_activity(
    field_data=_FIELD_ROW_A,
    insert_data=None,
    yield_upsert_data=None,
) -> MagicMock:
    """Build a mock Supabase that handles field access check + activity insert."""
    mock = MagicMock()
    calls: dict[str, MagicMock] = {}

    def _table(name: str):
        if name not in calls:
            calls[name] = MagicMock()
        return calls[name]

    mock.table.side_effect = _table

    # Field access check chain
    field_chain = _make_chain(data=field_data)
    calls["fields"] = field_chain

    # Activity insert chain
    if insert_data is not None:
        activity_chain = MagicMock()
        result = MagicMock()
        result.data = insert_data
        activity_chain.execute.return_value = result
        calls["field_activities"] = activity_chain

    # Yield history upsert
    if yield_upsert_data is not None:
        yield_chain = _make_chain(data=yield_upsert_data)
        calls["yield_history"] = yield_chain

    return mock


# ---------------------------------------------------------------------------
# create_activity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCreateActivity:
    async def test_valid_plant_activity_succeeds(self):
        """A valid planting activity should be inserted and the row returned."""
        from app.services.activity_log import create_activity

        data = _make_activity_create(activity_type=ActivityType.plant)

        # Full mock: field check + activity insert
        mock = MagicMock()

        field_chain = _make_chain(data=_FIELD_ROW_A)
        activity_chain = MagicMock()
        activity_result = MagicMock()
        activity_result.data = [_ACTIVITY_ROW]
        activity_chain.execute.return_value = activity_result
        # Make field_activities.insert return the chain
        activities_table = MagicMock()
        activities_table.insert.return_value = activity_chain

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "field_activities":
                return activities_table
            return _make_chain(data=None)

        mock.table.side_effect = _table

        row, warnings = await create_activity(data, mock)

        assert row["id"] == "act-uuid-1"
        assert warnings == []

    async def test_future_date_raises_422(self):
        """activity_date in the future must raise HTTPException 422."""
        from app.services.activity_log import create_activity

        data = _make_activity_create(activity_date=_TOMORROW)

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        mock.table.return_value = field_chain

        with pytest.raises(HTTPException) as exc_info:
            await create_activity(data, mock)

        assert exc_info.value.status_code == 422
        assert "future" in exc_info.value.detail.lower()

    async def test_restricted_spray_missing_applicator_name_raises_422(self):
        """A restricted-use spray without applicator_name must raise 422."""
        from app.services.activity_log import create_activity

        data = _make_activity_create(
            activity_type=ActivityType.spray,
            restricted_use=True,
            applicator_name=None,
            applicator_license="LIC-12345",
        )

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        mock.table.return_value = field_chain

        with pytest.raises(HTTPException) as exc_info:
            await create_activity(data, mock)

        assert exc_info.value.status_code == 422
        assert "applicator" in exc_info.value.detail.lower()

    async def test_restricted_spray_missing_license_raises_422(self):
        """A restricted-use spray without applicator_license must raise 422."""
        from app.services.activity_log import create_activity

        data = _make_activity_create(
            activity_type=ActivityType.spray,
            restricted_use=True,
            applicator_name="John Doe",
            applicator_license=None,
        )

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        mock.table.return_value = field_chain

        with pytest.raises(HTTPException) as exc_info:
            await create_activity(data, mock)

        assert exc_info.value.status_code == 422

    async def test_restricted_spray_with_credentials_succeeds(self):
        """A restricted-use spray WITH both credentials should proceed past validation."""
        from app.services.activity_log import create_activity

        spray_row = {**_ACTIVITY_ROW, "activity_type": "spray", "restricted_use": True,
                     "applicator_name": "John Doe", "applicator_license": "LIC-001"}

        data = _make_activity_create(
            activity_type=ActivityType.spray,
            restricted_use=True,
            applicator_name="John Doe",
            applicator_license="LIC-001",
        )

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        activity_chain = MagicMock()
        activity_result = MagicMock()
        activity_result.data = [spray_row]
        activity_chain.execute.return_value = activity_result
        activities_table = MagicMock()
        activities_table.insert.return_value = activity_chain

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "field_activities":
                return activities_table
            return _make_chain(data=None)

        mock.table.side_effect = _table

        row, warnings = await create_activity(data, mock)
        assert row["activity_type"] == "spray"

    async def test_non_restricted_spray_without_credentials_allowed(self):
        """A non-restricted spray without credentials should be accepted."""
        from app.services.activity_log import create_activity

        spray_row = {**_ACTIVITY_ROW, "activity_type": "spray"}
        data = _make_activity_create(
            activity_type=ActivityType.spray,
            restricted_use=False,
        )

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        activity_chain = MagicMock()
        activity_result = MagicMock()
        activity_result.data = [spray_row]
        activity_chain.execute.return_value = activity_result
        activities_table = MagicMock()
        activities_table.insert.return_value = activity_chain

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "field_activities":
                return activities_table
            return _make_chain(data=None)

        mock.table.side_effect = _table

        row, warnings = await create_activity(data, mock)
        assert row is not None

    async def test_acres_applied_exceeds_field_acres_raises_422(self):
        """acres_applied > field acres must raise HTTPException 422."""
        from app.services.activity_log import create_activity

        # Field has 120 acres; try to apply to 200
        data = _make_activity_create(
            activity_type=ActivityType.fertilize,
            acres_applied=200.0,
        )

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)  # acres=120
        mock.table.return_value = field_chain

        with pytest.raises(HTTPException) as exc_info:
            await create_activity(data, mock)

        assert exc_info.value.status_code == 422
        assert "acres" in exc_info.value.detail.lower()

    async def test_harvest_without_yield_produces_warning(self):
        """A harvest activity without yield_bu_acre should return a warning but not fail."""
        from app.services.activity_log import create_activity

        harvest_row = {**_ACTIVITY_ROW, "activity_type": "harvest"}
        data = _make_activity_create(
            activity_type=ActivityType.harvest,
            yield_bu_acre=None,
        )

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        activity_chain = MagicMock()
        activity_result = MagicMock()
        activity_result.data = [harvest_row]
        activity_chain.execute.return_value = activity_result
        activities_table = MagicMock()
        activities_table.insert.return_value = activity_chain

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "field_activities":
                return activities_table
            return _make_chain(data=None)

        mock.table.side_effect = _table

        row, warnings = await create_activity(data, mock)
        assert len(warnings) == 1
        assert "yield" in warnings[0].lower()

    async def test_field_not_found_raises_404(self):
        """When the field does not exist (RLS filter), expect HTTPException 404."""
        from app.services.activity_log import create_activity

        data = _make_activity_create()

        mock = MagicMock()
        field_chain = _make_chain(data=None)
        mock.table.return_value = field_chain

        with pytest.raises(HTTPException) as exc_info:
            await create_activity(data, mock)

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# list_activities
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestListActivities:
    async def test_list_returns_activities_and_count(self):
        """list_activities should return dict with 'activities' list and 'total_count'."""
        from app.services.activity_log import list_activities

        mock = MagicMock()

        # Field access check
        field_chain = _make_chain(data=_FIELD_ROW_A)
        # Count query — count attribute
        count_result = MagicMock()
        count_result.count = 1
        count_chain = MagicMock()
        count_chain.execute.return_value = count_result
        for method in ("select", "eq", "gte", "lte", "order", "range"):
            getattr(count_chain, method).return_value = count_chain
        # Data query
        data_result = MagicMock()
        data_result.data = [_ACTIVITY_ROW]
        data_chain = MagicMock()
        data_chain.execute.return_value = data_result
        for method in ("select", "eq", "gte", "lte", "order", "range"):
            getattr(data_chain, method).return_value = data_chain

        call_count = {"fields": 0, "field_activities": 0}

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "field_activities":
                call_count["field_activities"] += 1
                # First call = count, second = data
                if call_count["field_activities"] == 1:
                    return count_chain
                return data_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        result = await list_activities(_FIELD_UUID_A, mock)

        assert "activities" in result
        assert "total_count" in result
        assert result["total_count"] == 1
        assert len(result["activities"]) == 1

    async def test_list_with_type_filter(self):
        """Providing activity_type should add an eq filter on that column."""
        from app.services.activity_log import list_activities

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)

        count_result = MagicMock()
        count_result.count = 0
        count_chain = MagicMock()
        count_chain.execute.return_value = count_result
        for method in ("select", "eq", "order", "range"):
            getattr(count_chain, method).return_value = count_chain

        data_result = MagicMock()
        data_result.data = []
        data_chain = MagicMock()
        data_chain.execute.return_value = data_result
        for method in ("select", "eq", "order", "range"):
            getattr(data_chain, method).return_value = data_chain

        call_count = {"fa": 0}

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "field_activities":
                call_count["fa"] += 1
                return count_chain if call_count["fa"] == 1 else data_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        result = await list_activities(
            _FIELD_UUID_A, mock, activity_type="plant", limit=10, offset=0
        )

        # The eq call for activity_type must have been made
        count_chain.eq.assert_any_call("activity_type", "plant")

    async def test_list_with_date_range_filter(self):
        """start_date and end_date should apply gte/lte filters."""
        from app.services.activity_log import list_activities

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)

        count_result = MagicMock()
        count_result.count = 0
        count_chain = MagicMock()
        count_chain.execute.return_value = count_result
        for method in ("select", "eq", "gte", "lte", "order", "range"):
            getattr(count_chain, method).return_value = count_chain

        data_result = MagicMock()
        data_result.data = []
        data_chain = MagicMock()
        data_chain.execute.return_value = data_result
        for method in ("select", "eq", "gte", "lte", "order", "range"):
            getattr(data_chain, method).return_value = data_chain

        call_count = {"fa": 0}

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "field_activities":
                call_count["fa"] += 1
                return count_chain if call_count["fa"] == 1 else data_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        start = date(2026, 1, 1)
        end = date(2026, 4, 30)
        await list_activities(
            _FIELD_UUID_A, mock, start_date=start, end_date=end
        )

        count_chain.gte.assert_any_call("activity_date", start.isoformat())
        count_chain.lte.assert_any_call("activity_date", end.isoformat())

    async def test_list_pagination_passes_offset_and_limit(self):
        """The range() call should use offset and limit values correctly."""
        from app.services.activity_log import list_activities

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)

        count_result = MagicMock()
        count_result.count = 0
        count_chain = MagicMock()
        count_chain.execute.return_value = count_result
        for method in ("select", "eq", "order", "range"):
            getattr(count_chain, method).return_value = count_chain

        data_result = MagicMock()
        data_result.data = []
        data_chain = MagicMock()
        data_chain.execute.return_value = data_result
        for method in ("select", "eq", "order", "range"):
            getattr(data_chain, method).return_value = data_chain

        call_count = {"fa": 0}

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "field_activities":
                call_count["fa"] += 1
                return count_chain if call_count["fa"] == 1 else data_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        await list_activities(_FIELD_UUID_A, mock, limit=25, offset=50)

        # offset=50, limit=25 → range(50, 74)
        data_chain.range.assert_called_once_with(50, 74)


# ---------------------------------------------------------------------------
# get_activity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetActivity:
    async def test_existing_activity_returned(self):
        """get_activity for a known ID should return the row dict."""
        from app.services.activity_log import get_activity

        mock = MagicMock()
        chain = _make_chain(data=_ACTIVITY_ROW)
        mock.table.return_value = chain

        act_id = UUID(_ACTIVITY_ROW["id"].replace("act-uuid-1", "12345678-1234-5678-1234-567812345678"))
        # Use a proper UUID
        act_uuid = UUID("12345678-1234-5678-1234-000000000001")
        activity_row = {**_ACTIVITY_ROW, "id": str(act_uuid)}
        chain2 = _make_chain(data=activity_row)
        mock.table.return_value = chain2

        result = await get_activity(act_uuid, mock)
        assert result["id"] == str(act_uuid)

    async def test_missing_activity_raises_404(self):
        """get_activity for a non-existent ID should raise HTTPException 404."""
        from app.services.activity_log import get_activity

        mock = MagicMock()
        chain = _make_chain(data=None)
        mock.table.return_value = chain

        act_uuid = UUID("99999999-9999-9999-9999-999999999999")
        with pytest.raises(HTTPException) as exc_info:
            await get_activity(act_uuid, mock)

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# delete_activity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDeleteActivity:
    async def test_delete_calls_db_delete(self):
        """delete_activity should issue a DB delete for the correct ID."""
        from app.services.activity_log import delete_activity

        act_uuid = UUID("12345678-1234-5678-1234-000000000001")
        activity_row = {**_ACTIVITY_ROW, "id": str(act_uuid)}

        mock = MagicMock()
        get_chain = _make_chain(data=activity_row)
        delete_chain = MagicMock()
        delete_chain.execute.return_value = MagicMock(data=None)
        delete_chain.eq.return_value = delete_chain

        call_count = {"n": 0}

        def _table(name):
            if name == "field_activities":
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return get_chain  # get_activity call
                tbl = MagicMock()
                tbl.delete.return_value = delete_chain
                return tbl
            return _make_chain(data=None)

        mock.table.side_effect = _table

        await delete_activity(act_uuid, mock)

        delete_chain.eq.assert_called_once_with("id", str(act_uuid))

    async def test_delete_nonexistent_activity_raises_404(self):
        """delete_activity on a non-existent ID should raise 404 (from get_activity)."""
        from app.services.activity_log import delete_activity

        mock = MagicMock()
        chain = _make_chain(data=None)
        mock.table.return_value = chain

        act_uuid = UUID("99999999-9999-9999-9999-999999999999")
        with pytest.raises(HTTPException) as exc_info:
            await delete_activity(act_uuid, mock)

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# get_activity_summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetActivitySummary:
    async def test_summary_aggregates_counts_by_type(self):
        """Summary should count activities per type across all fields."""
        from app.services.activity_log import get_activity_summary

        farm_uuid = UUID("12345678-1234-5678-1234-567812345600")
        activities = [
            {"id": "a1", "field_id": _FIELD_ID_A_STR, "activity_type": "plant", "activity_date": "2026-03-01"},
            {"id": "a2", "field_id": _FIELD_ID_A_STR, "activity_type": "spray", "activity_date": "2026-03-15"},
            {"id": "a3", "field_id": _FIELD_ID_B_STR, "activity_type": "plant", "activity_date": "2026-03-05"},
        ]

        mock = MagicMock()

        farm_chain = _make_chain(data={"id": str(farm_uuid)})
        fields_chain = _make_chain(data=[
            {"id": _FIELD_ID_A_STR, "name": "North 40"},
            {"id": _FIELD_ID_B_STR, "name": "South 60"},
        ])
        activities_chain = _make_chain(data=activities)

        def _table(name):
            if name == "farms":
                return farm_chain
            if name == "fields":
                return fields_chain
            if name == "field_activities":
                return activities_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        result = await get_activity_summary(farm_uuid, mock)

        assert result["farm_id"] == str(farm_uuid)
        assert result["total_activities"] == 3
        assert result["count_by_type"]["plant"] == 2
        assert result["count_by_type"]["spray"] == 1

    async def test_summary_no_fields_returns_zero_counts(self):
        """A farm with no fields should return zero counts and empty field list."""
        from app.services.activity_log import get_activity_summary

        farm_uuid = UUID("12345678-1234-5678-1234-567812345601")

        mock = MagicMock()
        farm_chain = _make_chain(data={"id": str(farm_uuid)})
        fields_chain = _make_chain(data=[])

        def _table(name):
            if name == "farms":
                return farm_chain
            if name == "fields":
                return fields_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        result = await get_activity_summary(farm_uuid, mock)

        assert result["total_activities"] == 0
        assert result["count_by_type"] == {}
        assert result["last_activity_per_field"] == []

    async def test_summary_last_activity_per_field(self):
        """last_activity_per_field should show the most recent date per field."""
        from app.services.activity_log import get_activity_summary

        farm_uuid = UUID("12345678-1234-5678-1234-567812345602")
        activities = [
            {"id": "a1", "field_id": _FIELD_ID_A_STR, "activity_type": "plant", "activity_date": "2026-02-01"},
            {"id": "a2", "field_id": _FIELD_ID_A_STR, "activity_type": "spray", "activity_date": "2026-04-10"},
        ]

        mock = MagicMock()
        farm_chain = _make_chain(data={"id": str(farm_uuid)})
        fields_chain = _make_chain(data=[{"id": _FIELD_ID_A_STR, "name": "North 40"}])
        activities_chain = _make_chain(data=activities)

        def _table(name):
            if name == "farms":
                return farm_chain
            if name == "fields":
                return fields_chain
            if name == "field_activities":
                return activities_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        result = await get_activity_summary(farm_uuid, mock)

        last_entries = {
            item["field_id"]: item["last_activity_date"]
            for item in result["last_activity_per_field"]
        }
        assert last_entries[_FIELD_ID_A_STR] == "2026-04-10"

    async def test_summary_farm_not_found_raises_404(self):
        """When farm does not exist (RLS filter), expect HTTPException 404."""
        from app.services.activity_log import get_activity_summary

        farm_uuid = UUID("99999999-9999-9999-9999-999999999999")

        mock = MagicMock()
        farm_chain = _make_chain(data=None)
        mock.table.return_value = farm_chain

        with pytest.raises(HTTPException) as exc_info:
            await get_activity_summary(farm_uuid, mock)

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# calculate_aph
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCalculateAPH:
    def _make_yield_rows(self, n: int, start_year: int = 2020) -> list[dict]:
        return [
            {
                "id": f"yh-{i}",
                "field_id": _FIELD_ID_A_STR,
                "crop_year": start_year + i,
                "crop_type": "corn",
                "yield_bu_acre": 180.0 + i,
                "moisture_pct": 15.0,
                "acres_harvested": 120.0,
                "notes": None,
                "created_at": "2026-01-01T00:00:00+00:00",
            }
            for i in range(n)
        ]

    async def test_exactly_4_years_returns_aph(self):
        """4 years of data (the minimum) should produce a valid APH result."""
        from app.services.activity_log import calculate_aph

        rows = self._make_yield_rows(4, start_year=2022)  # 2022-2025

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        yield_chain = _make_chain(data=rows)

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "yield_history":
                return yield_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        result = await calculate_aph(_FIELD_UUID_A, mock)

        assert result["years_used"] == 4
        assert result["aph_yield"] == pytest.approx(181.5, abs=0.01)  # avg of 180,181,182,183
        assert result["field_id"] == str(_FIELD_UUID_A)
        assert "year_range" in result
        assert "records" in result

    async def test_fewer_than_4_years_raises_422(self):
        """Fewer than 4 years of yield data must raise HTTPException 422."""
        from app.services.activity_log import calculate_aph

        rows = self._make_yield_rows(3, start_year=2023)

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        yield_chain = _make_chain(data=rows)

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "yield_history":
                return yield_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        with pytest.raises(HTTPException) as exc_info:
            await calculate_aph(_FIELD_UUID_A, mock)

        assert exc_info.value.status_code == 422
        assert "4" in exc_info.value.detail

    async def test_zero_years_raises_422(self):
        """Zero years of yield data must raise 422."""
        from app.services.activity_log import calculate_aph

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        yield_chain = _make_chain(data=[])

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "yield_history":
                return yield_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        with pytest.raises(HTTPException) as exc_info:
            await calculate_aph(_FIELD_UUID_A, mock)

        assert exc_info.value.status_code == 422

    async def test_more_than_10_years_uses_only_last_10(self):
        """12 years of data should only use the 10 most recent (rows already ordered DESC)."""
        from app.services.activity_log import calculate_aph

        # list_yield_history returns rows ordered by crop_year DESC
        rows = self._make_yield_rows(12, start_year=2010)
        rows_desc = list(reversed(rows))  # newest first

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        yield_chain = _make_chain(data=rows_desc)

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "yield_history":
                return yield_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        result = await calculate_aph(_FIELD_UUID_A, mock)

        assert result["years_used"] == 10
        # The 10 most recent: years 2021-2012 (yields 191-182 when start=2010, i=12..2)
        # rows_desc[0..9] = years 2021, 2020, ..., 2012 → yields 191, 190, ..., 182
        expected_avg = round(sum(180 + i for i in range(2, 12)) / 10, 2)  # i=2..11
        assert result["aph_yield"] == pytest.approx(expected_avg, abs=0.01)

    async def test_aph_year_range_format(self):
        """year_range should be formatted as 'YYYY–YYYY'."""
        from app.services.activity_log import calculate_aph

        rows = self._make_yield_rows(4, start_year=2022)

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        yield_chain = _make_chain(data=rows)

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "yield_history":
                return yield_chain
            return _make_chain(data=None)

        mock.table.side_effect = _table

        result = await calculate_aph(_FIELD_UUID_A, mock)

        assert "2022" in result["year_range"]
        assert "2025" in result["year_range"]


# ---------------------------------------------------------------------------
# create_yield_history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCreateYieldHistory:
    async def test_valid_yield_history_upserted(self):
        """A valid YieldHistoryCreate should result in an upsert and returned row."""
        from app.services.activity_log import create_yield_history

        yield_row = {
            "id": "yh-uuid-1",
            "field_id": _FIELD_ID_A_STR,
            "crop_year": 2025,
            "crop_type": "corn",
            "yield_bu_acre": 185.0,
            "moisture_pct": 14.5,
            "acres_harvested": 120.0,
            "notes": None,
            "created_at": "2026-01-01T00:00:00+00:00",
        }

        data = YieldHistoryCreate(
            field_id=_FIELD_UUID_A,
            crop_year=2025,
            crop_type="corn",
            yield_bu_acre=185.0,
            moisture_pct=14.5,
            acres_harvested=120.0,
        )

        mock = MagicMock()
        field_chain = _make_chain(data=_FIELD_ROW_A)
        upsert_chain = MagicMock()
        upsert_result = MagicMock()
        upsert_result.data = [yield_row]
        upsert_chain.execute.return_value = upsert_result
        yield_table = MagicMock()
        yield_table.upsert.return_value = upsert_chain

        def _table(name):
            if name == "fields":
                return field_chain
            if name == "yield_history":
                return yield_table
            return _make_chain(data=None)

        mock.table.side_effect = _table

        result = await create_yield_history(data, mock)

        assert result["crop_year"] == 2025
        assert result["yield_bu_acre"] == 185.0
        yield_table.upsert.assert_called_once()

    async def test_yield_history_field_not_found_raises_404(self):
        """create_yield_history should raise 404 when the field does not exist."""
        from app.services.activity_log import create_yield_history

        data = YieldHistoryCreate(
            field_id=_FIELD_UUID_A,
            crop_year=2025,
            crop_type="corn",
            yield_bu_acre=180.0,
        )

        mock = MagicMock()
        field_chain = _make_chain(data=None)
        mock.table.return_value = field_chain

        with pytest.raises(HTTPException) as exc_info:
            await create_yield_history(data, mock)

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Write-path fixes: column mapping, yield sync, error mapping, shared rules
# ---------------------------------------------------------------------------

_PINNED_TODAY = date(2026, 9, 13)
_ACT_UUID = UUID("12345678-1234-5678-1234-000000000001")
_FIELD_ROW_WITH_CROP = {**_FIELD_ROW_A, "crop_type": "corn"}


def _db_error(code: str = "XX000") -> "APIError":
    from postgrest.exceptions import APIError

    return APIError({"message": "boom", "code": code, "hint": None, "details": None})


@pytest.fixture
def pinned_today():
    with patch("app.services.activity_log.helpers._today", return_value=_PINNED_TODAY):
        yield


class TestCheckRules:
    def test_future_date_uses_injectable_clock(self, pinned_today):
        from app.services.activity_log.helpers import _check_rules

        common = dict(
            activity_type="plant", restricted_use=False, applicator_name=None,
            applicator_license=None, acres_applied=None, field_acres=None,
        )
        _check_rules(activity_date=_PINNED_TODAY, **common)  # today is allowed
        with pytest.raises(HTTPException) as exc_info:
            _check_rules(activity_date=date(2026, 9, 14), **common)
        assert exc_info.value.status_code == 422

    def test_restricted_spray_and_acreage(self, pinned_today):
        from app.services.activity_log.helpers import _check_rules

        with pytest.raises(HTTPException):
            _check_rules(
                activity_type="spray", activity_date=None, restricted_use=True,
                applicator_name="A", applicator_license=None, acres_applied=None,
                field_acres=None,
            )
        with pytest.raises(HTTPException) as exc_info:
            _check_rules(
                activity_type="plant", activity_date=None, restricted_use=False,
                applicator_name=None, applicator_license=None, acres_applied=121,
                field_acres=120,
            )
        assert "acres" in exc_info.value.detail


@pytest.mark.asyncio
class TestErrorMapping:
    async def test_get_activity_no_rows_is_404(self):
        from app.services.activity_log import get_activity
        from tests.test_schema_drift import FakeSupabase

        with pytest.raises(HTTPException) as exc_info:
            await get_activity(_ACT_UUID, FakeSupabase(rows={"field_activities": []}))
        assert exc_info.value.status_code == 404

    async def test_get_activity_db_error_is_500(self):
        from app.services.activity_log import get_activity
        from tests.test_schema_drift import FakeSupabase

        supabase = FakeSupabase(errors={("field_activities", "select"): _db_error()})
        with pytest.raises(HTTPException) as exc_info:
            await get_activity(_ACT_UUID, supabase)
        assert exc_info.value.status_code == 500

    async def test_field_lookup_db_error_is_500(self):
        from app.services.activity_log.helpers import _assert_field_access
        from tests.test_schema_drift import FakeSupabase

        supabase = FakeSupabase(errors={("fields", "select"): _db_error()})
        with pytest.raises(HTTPException) as exc_info:
            await _assert_field_access(_FIELD_UUID_A, supabase)
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
class TestWritePaths:
    async def test_create_maps_pest_disease_found_to_pest_name(self, pinned_today):
        from app.services.activity_log import create_activity
        from tests.test_schema_drift import FakeSupabase

        supabase = FakeSupabase(rows={"fields": [_FIELD_ROW_A]})
        data = ActivityCreate(
            field_id=_FIELD_UUID_A, activity_type=ActivityType.scout,
            activity_date=date(2026, 9, 1), pest_disease_found="aphid",
        )

        row, _ = await create_activity(data, supabase)

        (payload,) = supabase.writes_for("field_activities", "insert")
        assert payload["pest_name"] == "aphid"
        assert "pest_disease_found" not in payload
        assert payload["field_id"] == _FIELD_ID_A_STR
        assert row["pest_disease_found"] == "aphid"
        assert "pest_name" not in row

    async def test_harvest_yield_sync_includes_crop_type(self, pinned_today):
        from app.services.activity_log import create_activity
        from tests.test_schema_drift import FakeSupabase

        supabase = FakeSupabase(rows={"fields": [_FIELD_ROW_WITH_CROP]})
        data = ActivityCreate(
            field_id=_FIELD_UUID_A, activity_type=ActivityType.harvest,
            activity_date=date(2026, 9, 1), yield_bu_acre=200, crop_year=2026,
        )

        _, warnings = await create_activity(data, supabase)

        (yield_payload,) = supabase.writes_for("yield_history", "upsert")
        assert yield_payload["crop_type"] == "corn"
        assert warnings == []

    async def test_harvest_yield_sync_failure_returns_warning_and_logs(
        self, pinned_today, caplog
    ):
        from app.services.activity_log import create_activity
        from tests.test_schema_drift import FakeSupabase

        supabase = FakeSupabase(
            rows={"fields": [_FIELD_ROW_WITH_CROP]},
            errors={("yield_history", "upsert"): _db_error()},
        )
        data = ActivityCreate(
            field_id=_FIELD_UUID_A, activity_type=ActivityType.harvest,
            activity_date=date(2026, 9, 1), yield_bu_acre=200, crop_year=2026,
        )

        with caplog.at_level("WARNING"):
            _, warnings = await create_activity(data, supabase)

        assert len(warnings) == 1 and "yield history" in warnings[0]
        assert any(r.exc_info for r in caplog.records if "sync failed" in r.getMessage())

    async def test_harvest_without_field_crop_type_warns(self, pinned_today):
        from app.services.activity_log import create_activity
        from tests.test_schema_drift import FakeSupabase

        supabase = FakeSupabase(rows={"fields": [{**_FIELD_ROW_A, "crop_type": None}]})
        data = ActivityCreate(
            field_id=_FIELD_UUID_A, activity_type=ActivityType.harvest,
            activity_date=date(2026, 9, 1), yield_bu_acre=200, crop_year=2026,
        )

        _, warnings = await create_activity(data, supabase)

        assert supabase.writes_for("yield_history", "upsert") == []
        assert len(warnings) == 1

    async def test_update_maps_columns_and_logs_skipped_acreage_check(
        self, pinned_today, caplog
    ):
        from app.services.activity_log import update_activity
        from tests.test_schema_drift import FakeSupabase

        existing = {**_ACTIVITY_ROW, "id": str(_ACT_UUID)}
        # Field lookup returns no rows: acreage rule is skipped, with a log line.
        supabase = FakeSupabase(rows={"field_activities": [existing], "fields": []})

        with caplog.at_level("WARNING"):
            row = await update_activity(
                _ACT_UUID,
                ActivityUpdate(pest_disease_found="mites", acres_applied=10),
                supabase,
            )

        (payload,) = supabase.writes_for("field_activities", "update")
        assert payload["pest_name"] == "mites"
        assert row["pest_disease_found"] == "mites"
        assert any(str(_ACT_UUID) in r.getMessage() for r in caplog.records)

    async def test_update_db_error_is_500(self, pinned_today):
        from app.services.activity_log import update_activity
        from tests.test_schema_drift import FakeSupabase

        existing = {**_ACTIVITY_ROW, "id": str(_ACT_UUID)}
        supabase = FakeSupabase(
            rows={"field_activities": [existing]},
            errors={("field_activities", "update"): _db_error()},
        )
        with pytest.raises(HTTPException) as exc_info:
            await update_activity(_ACT_UUID, ActivityUpdate(notes="x"), supabase)
        assert exc_info.value.status_code == 500