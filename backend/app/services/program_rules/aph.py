"""Crop insurance Actual Production History (APH) rules (7 CFR 400.55)."""

from __future__ import annotations

from typing import Final

from app.services.program_rules.rule_types import RuleValue

APH_CFR_URL: Final[str] = "https://www.ecfr.gov/current/title-7/section-400.55"


APH_CFR_TITLE: Final[str] = (
    "7 CFR 400.55, Qualification for actual production history coverage program"
)


APH_RULES_AS_OF: Final[str] = "2026-09-13"


APH_MIN_YIELD_YEARS: Final[RuleValue] = RuleValue(
    key="aph_min_yield_years",
    value=4,
    unit="crop_years",
    as_of=APH_RULES_AS_OF,
    source_url=APH_CFR_URL,
    source_title=APH_CFR_TITLE,
    note=(
        "The approved APH yield is calculated from a database containing a "
        "minimum of four yields. With fewer actual yields RMA fills the "
        "database with T-Yields, which RegenAI does not model, so it reports "
        "no APH instead."
    ),
)


APH_MAX_YIELD_YEARS: Final[RuleValue] = RuleValue(
    key="aph_max_yield_years",
    value=10,
    unit="crop_years",
    as_of=APH_RULES_AS_OF,
    source_url=APH_CFR_URL,
    source_title=APH_CFR_TITLE,
    note="The APH database holds at most the 10 most recent crop years.",
)
