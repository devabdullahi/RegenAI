"""
Drift guard: what the code writes must be allowed by the migrations.

Parses every file in supabase/migrations (in order) with a deliberately small
SQL reader that understands only what this repo uses:
  * CREATE TABLE column lists, inline/table CHECK (col IN (...)) constraints
  * ALTER TABLE ADD/DROP COLUMN and ADD/DROP CONSTRAINT
Inline CHECKs get Postgres' auto-name ``<table>_<column>_check`` so a later
``DROP CONSTRAINT IF EXISTS`` replaces them the same way the database does.

Then it asserts:
  (a) every enum/status value the code can write is in the CHECK list;
  (b) every key the services/routers insert, upsert or update is a real column
      (payloads captured with FakeSupabase, which router tests also use).
"""

import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from postgrest.exceptions import APIError

from app.models.schemas import (
    ActivityCreate,
    ActivityResponse,
    ActivityType,
    ActivityUpdate,
    CreditProgram,
    CreditStatus,
    CSPApplicationStatus,
    DocumentResponse,
    DocumentType,
    Priority,
    RecommendationStatus,
    ScoutingSeverity,
    YieldHistoryCreate,
    YieldHistoryResponse,
)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"

# ---------------------------------------------------------------------------
# Minimal SQL reader
# ---------------------------------------------------------------------------

_DOLLAR_TAG = re.compile(r"\$\w*\$")
_CHECK_IN = re.compile(r"check\s*\(\s*(\w+)\s+in\s*\(([^)]*)\)", re.IGNORECASE)
_QUOTED = re.compile(r"'((?:[^']|'')*)'")
_CREATE_TABLE = re.compile(
    r"^create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?(\w+)\s*\(", re.IGNORECASE
)
_ALTER_TABLE = re.compile(
    r"^alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?(?:public\.)?(\w+)\s+(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_ADD_COLUMN = re.compile(r"^add\s+column\s+(?:if\s+not\s+exists\s+)?(\w+)(.*)$", re.I | re.S)
_DROP_COLUMN = re.compile(r"^drop\s+column\s+(?:if\s+exists\s+)?(\w+)", re.IGNORECASE)
_ADD_CONSTRAINT = re.compile(r"^add\s+constraint\s+(\w+)\s+(.*)$", re.IGNORECASE | re.DOTALL)
_DROP_CONSTRAINT = re.compile(r"^drop\s+constraint\s+(?:if\s+exists\s+)?(\w+)", re.IGNORECASE)
_TABLE_CONSTRAINT_WORDS = frozenset({"unique", "primary", "foreign", "check", "exclude"})
_LEADING_WORD = re.compile(r'\s*"?(\w+)')
_UNIQUE_COLUMNS = re.compile(r"(?:unique|primary\s+key)\s*\(([^)]*)\)", re.IGNORECASE)
_INLINE_UNIQUE = re.compile(r"\b(?:unique|primary\s+key)\b", re.IGNORECASE)
_CREATE_POLICY = re.compile(
    r'^create\s+policy\s+"[^"]*"\s+on\s+(?:public\.)?(\w+)\s+for\s+(\w+)', re.IGNORECASE
)


def _strip_comments(sql: str) -> str:
    """Remove ``--`` comments that are outside quotes and $$ bodies."""
    out: list[str] = []
    i, length = 0, len(sql)
    in_quote = False
    dollar: str | None = None
    while i < length:
        if dollar:
            if sql.startswith(dollar, i):
                out.append(dollar)
                i += len(dollar)
                dollar = None
            else:
                out.append(sql[i])
                i += 1
            continue
        char = sql[i]
        if in_quote:
            in_quote = char != "'"  # '' escapes close and reopen the quote
            out.append(char)
            i += 1
            continue
        if char == "'":
            in_quote = True
        elif sql.startswith("--", i):
            newline = sql.find("\n", i)
            i = length if newline == -1 else newline
            continue
        elif char == "$" and (tag := _DOLLAR_TAG.match(sql, i)):
            dollar = tag.group(0)
            out.append(dollar)
            i = tag.end()
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _split_top_level(text: str, separator: str) -> list[str]:
    """Split on ``separator`` outside quotes, $$ bodies and parentheses."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_quote = False
    dollar: str | None = None
    i = 0
    while i < len(text):
        char = text[i]
        if dollar:
            if text.startswith(dollar, i):
                current.append(dollar)
                i += len(dollar)
                dollar = None
                continue
        elif in_quote:
            in_quote = char != "'"
        elif char == "'":
            in_quote = True
        elif char == "$" and (tag := _DOLLAR_TAG.match(text, i)):
            dollar = tag.group(0)
            current.append(dollar)
            i = tag.end()
            continue
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == separator and depth == 0:
            parts.append("".join(current))
            current = []
            i += 1
            continue
        current.append(char)
        i += 1
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def _paren_body(text: str, open_index: int) -> str:
    """Return the text between the '(' at open_index and its matching ')'."""
    depth = 0
    in_quote = False
    for i in range(open_index, len(text)):
        char = text[i]
        if in_quote:
            in_quote = char != "'"
        elif char == "'":
            in_quote = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[open_index + 1 : i]
    raise ValueError("Unbalanced parentheses in CREATE TABLE")


@dataclass
class Schema:
    columns: dict[str, set[str]] = field(default_factory=dict)
    # table -> constraint name -> (column, allowed values)
    checks: dict[str, dict[str, tuple[str, frozenset[str]]]] = field(default_factory=dict)
    # table -> column sets covered by a UNIQUE or PRIMARY KEY constraint
    unique_keys: dict[str, set[frozenset[str]]] = field(default_factory=dict)
    # table -> RLS policy commands (select, insert, update, delete, all)
    policies: dict[str, set[str]] = field(default_factory=dict)

    def record_unique(self, table: str, text: str) -> None:
        for match in _UNIQUE_COLUMNS.finditer(text):
            columns = frozenset(c.strip().strip('"').lower() for c in match.group(1).split(","))
            self.unique_keys.setdefault(table, set()).add(columns)

    def record_checks(self, table: str, text: str, name: str | None = None) -> None:
        for match in _CHECK_IN.finditer(text):
            column = match.group(1).lower()
            values = frozenset(_QUOTED.findall(match.group(2)))
            constraint_name = (name or f"{table}_{column}_check").lower()
            self.checks.setdefault(table, {})[constraint_name] = (column, values)

    def allowed_values(self, table: str, column: str) -> frozenset[str] | None:
        """Values permitted by every CHECK on the column (None if unconstrained)."""
        value_sets = [
            values for col, values in self.checks.get(table, {}).values() if col == column
        ]
        return frozenset.intersection(*value_sets) if value_sets else None


def _apply_create_table(schema: Schema, statement: str) -> None:
    match = _CREATE_TABLE.match(statement)
    if not match:
        return
    table = match.group(1).lower()
    schema.columns.setdefault(table, set())
    for item in _split_top_level(_paren_body(statement, match.end() - 1), ","):
        words = item.split()
        # Regex, not split(): "UNIQUE(farm_id, fiscal_year)" has no space before "(".
        first_word = _LEADING_WORD.match(item).group(1).lower()
        if first_word == "constraint":
            schema.record_checks(table, item, name=words[1])
            schema.record_unique(table, item)
        elif first_word in _TABLE_CONSTRAINT_WORDS:
            schema.record_checks(table, item)
            schema.record_unique(table, item)
        else:
            column = first_word.strip('"')
            schema.columns[table].add(column)
            schema.record_checks(table, item)
            if _INLINE_UNIQUE.search(item):
                schema.unique_keys.setdefault(table, set()).add(frozenset({column}))


def _apply_alter_table(schema: Schema, statement: str) -> None:
    match = _ALTER_TABLE.match(statement)
    if not match:
        return
    table = match.group(1).lower()
    for action in _split_top_level(match.group(2), ","):
        if add_column := _ADD_COLUMN.match(action):
            schema.columns.setdefault(table, set()).add(add_column.group(1).lower())
            schema.record_checks(table, add_column.group(2))
        elif drop_column := _DROP_COLUMN.match(action):
            schema.columns.get(table, set()).discard(drop_column.group(1).lower())
        elif add_constraint := _ADD_CONSTRAINT.match(action):
            schema.record_checks(table, add_constraint.group(2), name=add_constraint.group(1))
            schema.record_unique(table, add_constraint.group(2))
        elif drop_constraint := _DROP_CONSTRAINT.match(action):
            schema.checks.get(table, {}).pop(drop_constraint.group(1).lower(), None)


def _apply_create_policy(schema: Schema, statement: str) -> None:
    if match := _CREATE_POLICY.match(statement):
        schema.policies.setdefault(match.group(1).lower(), set()).add(match.group(2).lower())


def load_schema(migration_files: tuple[Path, ...]) -> Schema:
    schema = Schema()
    for path in migration_files:
        sql = _strip_comments(path.read_text(encoding="utf-8"))
        for statement in _split_top_level(sql, ";"):
            _apply_create_table(schema, statement)
            _apply_alter_table(schema, statement)
            _apply_create_policy(schema, statement)
    return schema


def _migration_files() -> tuple[Path, ...]:
    return tuple(sorted(MIGRATIONS_DIR.glob("*.sql")))


@lru_cache(maxsize=1)
def current_schema() -> Schema:
    return load_schema(_migration_files())


def table_columns(table: str) -> set[str]:
    """Columns of ``table`` after applying all migrations (asserts the table exists)."""
    columns = current_schema().columns.get(table)
    assert columns, f"table {table!r} not found in migrations"
    return columns


# ---------------------------------------------------------------------------
# FakeSupabase — records queries and writes (shared with router tests)
# ---------------------------------------------------------------------------

_ROW_DEFAULTS = {
    "id": "00000000-0000-4000-8000-00000000abcd",
    "created_at": "2026-09-01T00:00:00+00:00",
    "updated_at": "2026-09-01T00:00:00+00:00",
}


def _no_rows_error() -> APIError:
    return APIError(
        {"message": "JSON object requested, no rows", "code": "PGRST116", "hint": None,
         "details": None}
    )


class FakeQuery:
    """One ``supabase.table(name)`` builder chain."""

    def __init__(self, client: "FakeSupabase", table: str):
        self.client = client
        self.table = table
        self.op = "select"
        self.payload = None
        self.filters: list[tuple[str, tuple]] = []
        self.is_single = False

    def select(self, *columns, **kwargs):
        self.op = "select"
        return self

    def insert(self, payload, **kwargs):
        return self._write("insert", payload)

    def upsert(self, payload, **kwargs):
        self.client.upsert_targets.append((self.table, kwargs.get("on_conflict")))
        return self._write("upsert", payload)

    def update(self, payload, **kwargs):
        return self._write("update", payload)

    def delete(self, **kwargs):
        return self._write("delete", None)

    def single(self):
        self.is_single = True
        return self

    def _write(self, op: str, payload):
        self.op, self.payload = op, payload
        self.client.writes.append((self.table, op, payload))
        return self

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        def _filter(*args, **kwargs):  # eq, gte, lte, in_, order, range, limit, ...
            self.filters.append((name, args))
            return self

        return _filter

    def execute(self):
        error = self.client.errors.get((self.table, self.op))
        if error is not None:
            raise error
        existing = self.client.rows.get(self.table, [])
        if self.op in ("insert", "upsert", "update"):
            base = existing[0] if existing else {}
            payloads = self.payload if isinstance(self.payload, list) else [self.payload]
            rows = [{**_ROW_DEFAULTS, **base, **payload} for payload in payloads]
        elif self.op == "delete":
            rows = []
        else:
            rows = existing
        if self.is_single:
            if not rows:
                raise _no_rows_error()
            return SimpleNamespace(data=rows[0], count=1)
        return SimpleNamespace(data=rows, count=len(rows))


class FakeSupabase:
    """Supabase client stand-in: per-table rows, per-(table, op) errors."""

    def __init__(
        self,
        rows: dict[str, list[dict]] | None = None,
        errors: dict[tuple[str, str], Exception] | None = None,
    ):
        self.rows = rows or {}
        self.errors = errors or {}
        self.writes: list[tuple[str, str, object]] = []
        self.upsert_targets: list[tuple[str, str | None]] = []
        self.queries: list[FakeQuery] = []
        self.storage = MagicMock()

    def table(self, name: str) -> FakeQuery:
        query = FakeQuery(self, name)
        self.queries.append(query)
        return query

    def writes_for(self, table: str, op: str) -> list:
        return [payload for t, o, payload in self.writes if t == table and o == op]

    def last_query(self, table: str) -> FakeQuery:
        return [q for q in self.queries if q.table == table][-1]

    def tables_queried(self) -> set[str]:
        return {q.table for q in self.queries}


# ---------------------------------------------------------------------------
# Parser sanity (so an unparsed file cannot make the guards pass vacuously)
# ---------------------------------------------------------------------------


class TestParser:
    def test_finds_all_guarded_tables(self):
        for table in ("documents", "field_activities", "yield_history",
                      "csp_eligibility_assessments", "recommendations", "credit_eligibility"):
            assert table_columns(table)

    def test_reads_create_and_alter_columns(self):
        assert {"storage_path", "doc_type", "uploaded_at"} <= table_columns("documents")
        assert {"file_name", "size_bytes", "created_at", "user_id"} <= table_columns("documents")
        assert "pest_name" in table_columns("field_activities")
        assert "fsa_farm_number" in table_columns("fields")

    def test_drop_constraint_replaces_inline_check(self):
        schema = load_schema(())
        _apply_create_table(schema, "create table public.t (s text check (s in ('a', 'b')))")
        _apply_alter_table(schema, "alter table public.t drop constraint if exists t_s_check")
        _apply_alter_table(schema, "alter table public.t add constraint t_s_check "
                                   "check (s in ('a', 'c'))")
        assert schema.allowed_values("t", "s") == frozenset({"a", "c"})

    def test_comments_and_quoted_semicolons_are_ignored(self):
        sql = "-- create table nope (x int);\ncreate table t (a text default 'x;--y');"
        statements = _split_top_level(_strip_comments(sql), ";")
        assert len(statements) == 1
        schema = load_schema(())
        _apply_create_table(schema, statements[0])
        assert schema.columns["t"] == {"a"}


# ---------------------------------------------------------------------------
# (a) CHECK lists cover every value the code writes
# ---------------------------------------------------------------------------


def _allowed(table: str, column: str) -> frozenset[str]:
    allowed = current_schema().allowed_values(table, column)
    assert allowed is not None, f"no CHECK found for {table}.{column}"
    return allowed


class TestCheckConstraints:
    def test_csp_eligibility_status(self):
        from app.services.csp_eligibility import ELIGIBILITY_STATUSES

        allowed = _allowed("csp_eligibility_assessments", "eligibility_status")
        assert set(ELIGIBILITY_STATUSES) <= allowed
        assert {s.value for s in CSPApplicationStatus} <= allowed

    def test_guard_detects_the_original_drift(self):
        """Before migration 008 the CHECK rejected act_now/pending_review."""
        before_fix = tuple(p for p in _migration_files() if p.name < "20260913000008")
        allowed = load_schema(before_fix).allowed_values(
            "csp_eligibility_assessments", "eligibility_status"
        )
        assert "act_now" not in allowed
        assert "pending_review" not in allowed

    def test_field_activity_type_and_severity(self):
        assert {t.value for t in ActivityType} <= _allowed("field_activities", "activity_type")
        assert {s.value for s in ScoutingSeverity} <= _allowed("field_activities", "severity")

    def test_document_type(self):
        assert {t.value for t in DocumentType} <= _allowed("documents", "doc_type")

    def test_recommendation_status_and_priority(self):
        assert {s.value for s in RecommendationStatus} <= _allowed("recommendations", "status")
        assert {p.value for p in Priority} <= _allowed("recommendations", "priority")

    def test_credit_program_and_status(self):
        assert {p.value for p in CreditProgram} <= _allowed("credit_eligibility", "program")
        assert {s.value for s in CreditStatus} <= _allowed("credit_eligibility", "status")


# ---------------------------------------------------------------------------
# (b) Written keys and response fields are real columns
# ---------------------------------------------------------------------------

_FIELD_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_ACTIVITY_ID = UUID("12345678-1234-4678-8234-000000000001")
_FIELD_ROW = {
    "id": str(_FIELD_ID), "farm_id": "f", "acres": 500.0, "name": "N", "crop_type": "corn"
}
_ACTIVITY_ROW = {
    "id": str(_ACTIVITY_ID),
    "field_id": str(_FIELD_ID),
    "activity_type": "harvest",
    "activity_date": "2026-09-01",
    "restricted_use": False,
}

# Every ActivityCreate field with a valid value (kept complete by an assertion).
_ALL_ACTIVITY_FIELDS = {
    "field_id": _FIELD_ID,
    "activity_type": ActivityType.harvest,
    "activity_date": date(2026, 9, 1),
    "seed_variety": "P1",
    "seeding_rate": 34000,
    "seed_treatment": "fungicide",
    "product_name": "Product",
    "rate_per_acre": 1.5,
    "rate_unit": "oz_per_acre",
    "target_pest": "weeds",
    "restricted_use": True,
    "applicator_name": "A. Applicator",
    "applicator_license": "LIC-1",
    "yield_bu_acre": 200.0,
    "moisture_pct": 15.0,
    "crop_year": 2026,
    "pest_disease_found": "rootworm",
    "severity": "low",
    "tillage_depth_in": 4.0,
    "cover_crop_species": "cereal rye",
    "notes": "note",
    "operator": "Op",
    "equipment_used": "Combine",
    "cost_per_acre": 12.0,
    "acres_applied": 100.0,
}

# Response fields that are not columns.
_ACTIVITY_RESPONSE_ONLY = {"warnings"}
_ACTIVITY_API_TO_COLUMN = {"pest_disease_found": "pest_name"}


def _as_columns(names) -> set[str]:
    return {_ACTIVITY_API_TO_COLUMN.get(name, name) for name in names}


@pytest.fixture
def pinned_today():
    with patch("app.services.activity_log.helpers._today", return_value=date(2026, 9, 13)):
        yield


class TestWrittenColumns:
    def test_test_payload_covers_every_activity_field(self):
        assert set(_ALL_ACTIVITY_FIELDS) == set(ActivityCreate.model_fields)
        assert set(_ALL_ACTIVITY_FIELDS) - {"field_id"} == set(ActivityUpdate.model_fields)

    @pytest.mark.asyncio
    async def test_create_activity_and_yield_sync_payloads(self, pinned_today):
        from app.services.activity_log import create_activity

        supabase = FakeSupabase(rows={"fields": [_FIELD_ROW]})
        await create_activity(ActivityCreate(**_ALL_ACTIVITY_FIELDS), supabase)

        (activity_payload,) = supabase.writes_for("field_activities", "insert")
        assert set(activity_payload) <= table_columns("field_activities")
        (yield_payload,) = supabase.writes_for("yield_history", "upsert")
        assert set(yield_payload) <= table_columns("yield_history")

    @pytest.mark.asyncio
    async def test_update_activity_payload(self, pinned_today):
        from app.services.activity_log import update_activity

        supabase = FakeSupabase(
            rows={"fields": [_FIELD_ROW], "field_activities": [_ACTIVITY_ROW]}
        )
        update_fields = {k: v for k, v in _ALL_ACTIVITY_FIELDS.items() if k != "field_id"}
        await update_activity(_ACTIVITY_ID, ActivityUpdate(**update_fields), supabase)

        (payload,) = supabase.writes_for("field_activities", "update")
        assert set(payload) <= table_columns("field_activities")

    @pytest.mark.asyncio
    async def test_create_yield_history_payload(self):
        from app.services.activity_log import create_yield_history

        supabase = FakeSupabase(rows={"fields": [_FIELD_ROW]})
        data = YieldHistoryCreate(
            field_id=_FIELD_ID, crop_year=2025, crop_type="corn", yield_bu_acre=190,
            moisture_pct=15, acres_harvested=100, notes="n",
        )
        await create_yield_history(data, supabase)

        (payload,) = supabase.writes_for("yield_history", "upsert")
        assert set(payload) <= table_columns("yield_history")

    @pytest.mark.asyncio
    async def test_csp_assessment_payload(self):
        from app.services.csp_eligibility import evaluate_csp_eligibility

        class _ScoreData(dict):
            """Scoring output; keys only echoed into the response default to None,
            so this test tracks the persisted payload, not the response shape."""

            def __missing__(self, key):
                return None

        score_data = _ScoreData({
            "total_points": 50.0,
            "max_possible_points": 100.0,
            "state_ranking_threshold": 40.0,
            "meets_ranking_threshold": True,
            "gap_to_threshold": 0.0,
            "resource_concern_scores": [
                {"concern_id": "soil_health", "meets_threshold": True},
                {"concern_id": "water_quality", "meets_threshold": True},
                {"concern_id": "energy", "meets_threshold": False},
            ],
        })
        supabase = FakeSupabase()
        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=score_data),
        ):
            await evaluate_csp_eligibility("farm-1", supabase)

        (payload,) = supabase.writes_for("csp_eligibility_assessments", "upsert")
        assert set(payload) <= table_columns("csp_eligibility_assessments")

    def test_response_models_read_real_columns(self):
        assert set(DocumentResponse.model_fields) <= table_columns("documents")
        assert set(YieldHistoryResponse.model_fields) <= table_columns("yield_history")
        activity_fields = set(ActivityResponse.model_fields) - _ACTIVITY_RESPONSE_ONLY
        assert _as_columns(activity_fields) <= table_columns("field_activities")


# ---------------------------------------------------------------------------
# (c) Service statuses, upsert conflict targets and RLS policies
# ---------------------------------------------------------------------------

_FARM_ID = "farm-1"
_ACTED_COVER_CROP = [
    {"field_id": str(_FIELD_ID), "practice_code": "340", "title": "Cover Crop"}
]
_EQIP_COVER_CROP = [{"code": "340", "name": "Cover Crop", "category": "soil"}]

# Inputs that drive the credit engines through every status they can write.
_CREDIT_SCENARIOS: tuple[dict[str, list[dict]], ...] = (
    {},  # no fields
    {"fields": [_FIELD_ROW], "recommendations": _ACTED_COVER_CROP,
     "eqip_practices": _EQIP_COVER_CROP},  # EQIP: no documents
    {"fields": [_FIELD_ROW], "recommendations": _ACTED_COVER_CROP,
     "eqip_practices": _EQIP_COVER_CROP, "documents": [{"doc_type": "soil_report"}]},
    {"fields": [{**_FIELD_ROW, "acres": 0.0}], "recommendations": _ACTED_COVER_CROP},  # VCM: 0
)


def _score_data(concerns_met: int, meets_ranking_threshold: bool) -> dict:
    return {
        "total_points": 50.0 if meets_ranking_threshold else 10.0,
        "max_possible_points": 100.0,
        "state_ranking_threshold": 40.0,
        "meets_ranking_threshold": meets_ranking_threshold,
        "gap_to_threshold": 0.0 if meets_ranking_threshold else 30.0,
        "resource_concern_scores": [
            {"concern_id": f"concern_{i}", "meets_threshold": i < concerns_met}
            for i in range(8)
        ],
        "is_estimate": True,
        "scoring_rules": {},
    }


async def _run_credit_engines() -> list[FakeSupabase]:
    from app.services.eqip import evaluate_eqip_eligibility
    from app.services.vcm import estimate_vcm_credits

    clients: list[FakeSupabase] = []
    for rows in _CREDIT_SCENARIOS:
        for engine in (evaluate_eqip_eligibility, estimate_vcm_credits):
            supabase = FakeSupabase(rows=rows)
            await engine(_FARM_ID, supabase)
            clients.append(supabase)
    return clients


async def _run_csp_eligibility() -> list[FakeSupabase]:
    from app.services.csp_eligibility import evaluate_csp_eligibility

    clients: list[FakeSupabase] = []
    for concerns_met, meets_ranking in ((2, True), (2, False), (1, False), (0, False)):
        supabase = FakeSupabase()
        with patch(
            "app.services.csp_eligibility.calculate_stewardship_score",
            new=AsyncMock(return_value=_score_data(concerns_met, meets_ranking)),
        ):
            await evaluate_csp_eligibility(_FARM_ID, supabase)
        clients.append(supabase)
    return clients


async def _run_other_upserts() -> list[FakeSupabase]:
    from app.services.activity_log import create_yield_history
    from app.services.enrichment import _upsert_weather_rows

    yield_client = FakeSupabase(rows={"fields": [_FIELD_ROW]})
    await create_yield_history(
        YieldHistoryCreate(field_id=_FIELD_ID, crop_year=2025, crop_type="corn",
                           yield_bu_acre=190),
        yield_client,
    )
    weather_client = FakeSupabase()
    weather_row = {
        "field_id": str(_FIELD_ID), "date": "2026-09-13", "temp_high": 25.0, "temp_low": 12.0,
        "precip_mm": 0.0, "soil_temp": None, "fetched_at": "2026-09-13T00:00:00+00:00",
    }
    _upsert_weather_rows(weather_client, str(_FIELD_ID), [weather_row])
    return [yield_client, weather_client]


def _conflict_columns(on_conflict: str) -> frozenset[str]:
    return frozenset(column.strip() for column in on_conflict.split(","))


class TestServiceWritesMatchConstraints:
    def test_parser_reads_unique_keys_and_policies(self):
        schema = current_schema()
        assert frozenset({"farm_id", "fiscal_year"}) in schema.unique_keys[
            "csp_eligibility_assessments"
        ]
        assert frozenset({"farm_id", "program"}) in schema.unique_keys["credit_eligibility"]
        assert frozenset({"code"}) in schema.unique_keys["eqip_practices"]
        assert {"insert", "update"} <= schema.policies["weather_cache"]

    def test_guards_detect_the_original_drift(self):
        """Before 008 weather_cache had no UPDATE policy; farm_id alone was never unique."""
        before_fix = tuple(p for p in _migration_files() if p.name < "20260913000008")
        assert "update" not in load_schema(before_fix).policies["weather_cache"]
        assert frozenset({"farm_id"}) not in current_schema().unique_keys[
            "csp_eligibility_assessments"
        ]

    @pytest.mark.asyncio
    async def test_credit_statuses_written_are_allowed(self):
        clients = await _run_credit_engines()
        statuses = {
            payload["status"]
            for client in clients
            for payload in client.writes_for("credit_eligibility", "upsert")
        }
        assert statuses == {"not_eligible", "pending_review", "eligible"}
        assert statuses <= _allowed("credit_eligibility", "status")

    @pytest.mark.asyncio
    async def test_csp_statuses_written_are_declared_and_allowed(self):
        from app.services.csp_eligibility import ELIGIBILITY_STATUSES

        clients = await _run_csp_eligibility()
        statuses = {
            payload["eligibility_status"]
            for client in clients
            for payload in client.writes_for("csp_eligibility_assessments", "upsert")
        }
        assert statuses == set(ELIGIBILITY_STATUSES)
        assert statuses <= _allowed("csp_eligibility_assessments", "eligibility_status")

    @pytest.mark.asyncio
    async def test_every_upsert_targets_a_unique_key_and_has_insert_update_policies(self):
        clients = (
            await _run_credit_engines() + await _run_csp_eligibility() + await _run_other_upserts()
        )
        targets = {target for client in clients for target in client.upsert_targets}
        assert {table for table, _ in targets} == {
            "credit_eligibility", "csp_eligibility_assessments", "yield_history", "weather_cache",
        }

        schema = current_schema()
        for table, on_conflict in targets:
            assert on_conflict, f"{table} upsert has no on_conflict target"
            assert _conflict_columns(on_conflict) in schema.unique_keys.get(table, set()), (
                table, on_conflict,
            )
            assert {"insert", "update"} <= schema.policies.get(table, set()), table
        for client in clients:
            for table, _, payload in client.writes:
                rows = payload if isinstance(payload, list) else [payload]
                for row in rows:
                    assert set(row) <= table_columns(table), table

    def test_inserted_tables_have_insert_policy(self):
        from app.services.enrichment import _insert_soil_profile
        from app.services.recommendations import _store_recommendations
        from app.services.validators import LLMRecommendation

        supabase = FakeSupabase()
        _insert_soil_profile(supabase, str(_FIELD_ID), {
            "field_id": str(_FIELD_ID), "ssurgo_map_unit": "WbA", "texture": "Silty clay loam",
            "ph": 6.8, "organic_matter_pct": 3.5, "source": "ssurgo",
            "fetched_at": "2026-09-13T00:00:00+00:00",
        })
        _store_recommendations(supabase, [LLMRecommendation(
            field_id=_FIELD_ID, practice_code="340", title="Plant cover crops",
            rationale="Low organic matter on this field.", priority="high",
        )], _FARM_ID)

        inserted_tables = {table for table, op, _ in supabase.writes if op == "insert"}
        assert inserted_tables == {"soil_profiles", "recommendations"}
        for table, _, payload in supabase.writes:
            rows = payload if isinstance(payload, list) else [payload]
            assert all(set(row) <= table_columns(table) for row in rows), table
            assert "insert" in current_schema().policies.get(table, set()), table
