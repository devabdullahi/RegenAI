"""Provenance wrappers: a rule value with its source, and an unsourced estimate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class RuleValue:
    """A single program rule value with provenance."""

    key: str
    value: float | int | None
    unit: str
    as_of: str
    source_url: str | None
    source_title: str | None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


RuleStatus = Literal["estimate", "unverified"]


@dataclass(frozen=True)
class EstimatedRule:
    """Provenance for a modelling value that has no primary source."""

    key: str
    status: RuleStatus
    as_of: str
    note: str
    source_url: str | None = None
    source_title: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
