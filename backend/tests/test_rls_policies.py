"""
Drift guard: every UPDATE policy must constrain the row it writes.

A Postgres UPDATE policy checks ``USING`` against the OLD row and ``WITH CHECK``
against the NEW one. A policy with only ``USING`` lets an owner re-parent a row
onto a farm or field somebody else owns, which silently moves the row out of
their own scope. Migrations 003 and 005 shipped four such policies; 009 fixed
them. This test fails on that old behaviour.

The reader is deliberately small: it understands only the ``CREATE POLICY``
shape this repo writes, and keeps the last definition of each
(table, policy name) so a later DROP + CREATE replaces an earlier one the same
way the database does.
"""

import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"

_CREATE_POLICY = re.compile(
    r'create\s+policy\s+"(?P<name>[^"]+)"\s*'
    r"on\s+(?P<table>[\w.]+)\s+"
    r"(?:to\s+\w+\s+)?"
    r"for\s+(?P<command>select|insert|update|delete|all)\b"
    r"(?P<body>.*?);",
    re.IGNORECASE | re.DOTALL,
)


def _latest_policies() -> dict[tuple[str, str], tuple[str, str, Path]]:
    """Map (table, policy name) -> (command, body, defining migration)."""
    policies: dict[tuple[str, str], tuple[str, str, Path]] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        for match in _CREATE_POLICY.finditer(sql):
            table = match.group("table").removeprefix("public.")
            key = (table, match.group("name"))
            policies[key] = (
                match.group("command").upper(),
                match.group("body"),
                path,
            )
    return policies


def test_migrations_define_policies():
    """Guard the reader itself: a silent parse failure must not pass the suite."""
    policies = _latest_policies()
    assert len(policies) >= 20, f"parsed only {len(policies)} policies; reader is broken"


def test_update_policies_have_with_check():
    offenders = [
        f"{table}.{name!r} (migration {path.name})"
        for (table, name), (command, body, path) in sorted(_latest_policies().items())
        if command in {"UPDATE", "ALL"} and "with check" not in body.lower()
    ]
    assert not offenders, (
        "UPDATE policies without WITH CHECK let a row be re-parented to another "
        "owner; add WITH CHECK in a new migration:\n  " + "\n  ".join(offenders)
    )
