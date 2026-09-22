"""
Drift guard for EQIP seed data: supabase/seed.sql is the single source of truth
and scripts/seed_eqip.py must parse every row from it.
"""

import pytest

from app.services.program_rules import CSP_PRACTICE_CATALOG
from scripts.seed_eqip import SEED_SQL_PATH, parse_seed_practices


def test_parses_every_row_in_seed_sql():
    practices = parse_seed_practices(SEED_SQL_PATH.read_text(encoding="utf-8"))
    codes = [practice["code"] for practice in practices]

    assert len(codes) == len(set(codes)), "duplicate practice codes in seed.sql"
    assert set(practices[0]) == {"code", "name", "category", "description", "unit"}
    assert all(practice["name"] and practice["unit"] for practice in practices)


def test_seed_includes_csp_activity_practice_standards():
    """Codes activated as FY2026 CSP activities must pass the eqip_practices guard."""
    practices = parse_seed_practices(SEED_SQL_PATH.read_text(encoding="utf-8"))
    codes = {practice["code"] for practice in practices}

    assert {"340", "328", "329", "345", "590", "595", "449", "554", "393", "528", "374"} <= codes


def test_every_scoring_catalog_practice_standard_is_seeded():
    """Drift guard: a practice the scoring catalog can award must pass the
    eqip_practices hallucination guard, or recommendations for it are dropped
    (430 Irrigation Pipeline once was)."""
    practices = parse_seed_practices(SEED_SQL_PATH.read_text(encoding="utf-8"))
    seeded_names = {practice["code"]: practice["name"] for practice in practices}

    missing = {
        practice.practice_standard_code
        for practice in CSP_PRACTICE_CATALOG.values()
        if practice.practice_standard_code not in seeded_names
    }
    assert not missing, f"catalog practice standards missing from seed.sql: {sorted(missing)}"
    assert seeded_names["430"] == CSP_PRACTICE_CATALOG["430"].name


def test_unescapes_sql_quotes():
    sql = (
        "insert into public.eqip_practices (code, name, category, description, unit)\n"
        "values\n"
        "  -- comment with a ' quote\n"
        "  ('999', 'Farmer''s Practice', 'Cat', 'Desc', 'acre')\n"
        "on conflict (code) do nothing;"
    )

    assert parse_seed_practices(sql) == [
        {
            "code": "999",
            "name": "Farmer's Practice",
            "category": "Cat",
            "description": "Desc",
            "unit": "acre",
        }
    ]


def test_malformed_row_raises_instead_of_being_skipped():
    sql = (
        "insert into public.eqip_practices (code, name, category, description, unit)\n"
        "values\n"
        "  ('998', 'Complete', 'Cat', 'Desc', 'acre'),\n"
        "  ('999', 'Missing unit', 'Cat', 'Desc')\n"
        "on conflict (code) do nothing;"
    )

    with pytest.raises(ValueError):
        parse_seed_practices(sql)
