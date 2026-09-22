"""Shared logger and the API-field <-> database-column maps."""

import logging

from app.services.program_rules import APH_MAX_YIELD_YEARS, APH_MIN_YIELD_YEARS

logger = logging.getLogger(__name__)


_APH_MAX_YEARS: int = int(APH_MAX_YIELD_YEARS.value)


_APH_MIN_YEARS: int = int(APH_MIN_YIELD_YEARS.value)


# field_activities columns declared NOT NULL that a partial update may name.
_NOT_NULL_UPDATE_FIELDS: tuple[str, ...] = ("activity_type", "activity_date", "restricted_use")


# API field name -> field_activities column name, where they differ.
_API_TO_COLUMN: dict[str, str] = {"pest_disease_found": "pest_name"}


# Text fields that require sanitization before storage (API names).
_TEXT_FIELDS: frozenset[str] = frozenset(
    {
        "seed_variety",
        "seed_treatment",
        "product_name",
        "rate_unit",
        "target_pest",
        "applicator_name",
        "applicator_license",
        "pest_disease_found",
        "cover_crop_species",
        "notes",
        "operator",
        "equipment_used",
        "crop_type",
    }
)
