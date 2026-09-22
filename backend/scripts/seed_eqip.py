"""Upsert EQIP practice codes from supabase/seed.sql into a Supabase project.

supabase/seed.sql is the single source of truth for eqip_practices; this
script parses its INSERT values so hosted projects (where `supabase db reset`
is not run) get exactly the same rows. Never add practice data here.

Run from backend/: poetry run python scripts/seed_eqip.py
Requires: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
"""

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

SEED_SQL_PATH = Path(__file__).resolve().parents[2] / "supabase" / "seed.sql"

_COLUMNS = ("code", "name", "category", "description", "unit")
_INSERT_START = "insert into public.eqip_practices (code, name, category, description, unit)"
_SQL_STRING = r"'((?:[^']|'')*)'"
_ROW_PATTERN = re.compile(r"\(\s*" + r"\s*,\s*".join([_SQL_STRING] * len(_COLUMNS)) + r"\s*\)")
_ROW_START_PATTERN = re.compile(r"^\s*\('", re.MULTILINE)


def parse_seed_practices(sql_text: str) -> list[dict[str, str]]:
    """Return the eqip_practices rows from the seed.sql INSERT statement.

    Raises:
        ValueError: if the INSERT is missing or any row does not match the
            five-string-literal shape (so a malformed row is never skipped).
    """
    start = sql_text.lower().find(_INSERT_START)
    if start == -1:
        raise ValueError("eqip_practices INSERT not found in seed.sql")
    end = sql_text.lower().find("on conflict", start)
    values_block = sql_text[start + len(_INSERT_START) : end if end != -1 else None]
    values_block = "\n".join(
        line for line in values_block.splitlines() if not line.lstrip().startswith("--")
    )

    rows = [
        {column: value.replace("''", "'") for column, value in zip(_COLUMNS, match.groups())}
        for match in _ROW_PATTERN.finditer(values_block)
    ]
    expected_row_count = len(_ROW_START_PATTERN.findall(values_block))
    if not rows or len(rows) != expected_row_count:
        raise ValueError(
            f"Parsed {len(rows)} rows but seed.sql has {expected_row_count} value tuples; "
            "every row must be ('code', 'name', 'category', 'description', 'unit')"
        )
    return rows


def main() -> int:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Error: Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
        return 1

    practices = parse_seed_practices(SEED_SQL_PATH.read_text(encoding="utf-8"))
    print(f"Seeding {len(practices)} EQIP practice codes from {SEED_SQL_PATH}...")

    supabase = create_client(url, key)
    result = supabase.table("eqip_practices").upsert(practices, on_conflict="code").execute()
    print(f"Done. {len(result.data)} practices upserted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
