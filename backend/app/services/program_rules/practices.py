"""The single practice -> resource concern catalog and its gap-closure map."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.services.program_rules.csp_scoring import (
    CSP_CART_MAX_POINTS_RULE,
    CSP_SCORING_MODEL_AS_OF,
    CSP_SOM_RULE,
    CSP_STATE_RANKING_THRESHOLD_RULE,
    CSP_STEWARDSHIP_THRESHOLD_RULE,
)
from app.services.program_rules.rule_types import EstimatedRule


@dataclass(frozen=True)
class CspPractice:
    """One conservation practice known to RegenAI's CSP scoring and estimates.

    Attributes:
        code: RegenAI identifier. The NRCS practice standard code, with a
            suffix where one standard has distinct higher-payment activities
            (``328-RCCR``, ``328-IRCCR``).
        practice_standard_code: NRCS conservation practice standard code.
        resource_concerns: Concern ids this practice earns points for. The
            payment ranking uses the same list.
        base_points: RegenAI points earned per concern (estimate).
        estimated_rate_per_acre: Pre-FY2026 per-acre payment estimate, or None
            when RegenAI does not offer the practice as a CSP activity
            (scoring only).
        higher_payment_category: Key into ``CSP_HIGHER_PAYMENT_CATEGORIES``.
        legacy_codes: Retired "E" enhancement codes this activity replaces.
        as_of: Date the entry was last reviewed.
        note: Provenance or open questions for this entry.
    """

    code: str
    practice_standard_code: str
    name: str
    category: str
    resource_concerns: tuple[str, ...]
    base_points: float
    estimated_rate_per_acre: float | None = None
    higher_payment_category: str | None = None
    legacy_codes: tuple[str, ...] = ()
    description: str = ""
    as_of: str = CSP_SCORING_MODEL_AS_OF
    note: str = ""

    @property
    def is_csp_activity(self) -> bool:
        """True when the practice has a CSP payment estimate."""
        return self.estimated_rate_per_acre is not None


_ADDED_FOR_GAP_CLOSURE_NOTE = (
    "Added to scoring so gap-closure recommendations earn points; base points "
    "set to the catalog median (3.0) pending review."
)


#: NRCS national list of conservation practice standards (code -> practice name).
NRCS_PRACTICE_STANDARDS_URL: Final[str] = (
    "https://www.nrcs.usda.gov/resources/guides-and-instructions/"
    "conservation-practice-standards"
)


NRCS_PRACTICE_CODES_VERIFIED_AS_OF: Final[str] = "2026-09-13"


_CODE_CORRECTED_NOTE = (
    "Code checked against the NRCS practice standards list "
    f"({NRCS_PRACTICE_STANDARDS_URL}) on {NRCS_PRACTICE_CODES_VERIFIED_AS_OF}. "
    "Earlier code keyed this practice under 484 (Mulching) / 657 (Wetland "
    "Restoration). Concern mapping and points are still RegenAI estimates."
)


_CSP_PRACTICES: Final[tuple[CspPractice, ...]] = (
    # --- CSP activities (have a payment estimate) ---
    CspPractice(
        code="340",
        practice_standard_code="340",
        name="Cover Crop",
        category="Soil Health and Organic Matter",
        resource_concerns=("soil_health", "soil_erosion", "water_quality", "air_quality"),
        base_points=5.0,
        estimated_rate_per_acre=9.00,
        higher_payment_category="cover_crop",
        legacy_codes=("E340A", "E340B", "E340E"),
        description=(
            "Plant a cover crop between cash crops to protect soil, scavenge "
            "nutrients, and build organic matter."
        ),
    ),
    CspPractice(
        code="328-RCCR",
        practice_standard_code="328",
        name="Conservation Crop Rotation — Resource Conserving Crop Rotation (RCCR)",
        category="Soil Health and Organic Matter",
        resource_concerns=("soil_health", "soil_erosion"),
        base_points=4.0,
        estimated_rate_per_acre=2.50,
        higher_payment_category="rccr",
        legacy_codes=("E328A",),
        description=(
            "Add a resource-conserving crop (e.g. small grain, grass, or legume) "
            "to the rotation beyond corn and soybeans."
        ),
        note="Base points match practice 328.",
    ),
    CspPractice(
        code="328-IRCCR",
        practice_standard_code="328",
        name="Conservation Crop Rotation — Improved Resource Conserving Crop Rotation (IRCCR)",
        category="Soil Health and Organic Matter",
        resource_concerns=("soil_health", "soil_erosion", "plant_condition"),
        base_points=4.0,
        estimated_rate_per_acre=4.75,
        higher_payment_category="irccr",
        legacy_codes=("E328B",),
        description=(
            "Improve an existing resource conserving crop rotation, for example "
            "by adding a perennial resource-conserving crop year."
        ),
        note="Base points match practice 328.",
    ),
    CspPractice(
        code="329",
        practice_standard_code="329",
        name="Residue and Tillage Management, No Till",
        category="Soil Erosion",
        resource_concerns=("soil_health", "soil_erosion", "water_quality", "air_quality"),
        base_points=5.0,
        estimated_rate_per_acre=5.50,
        legacy_codes=("E329A", "E329B"),
        description=(
            "Limit soil disturbance to planting operations and keep crop "
            "residue on the surface year-round."
        ),
    ),
    CspPractice(
        code="345",
        practice_standard_code="345",
        name="Residue and Tillage Management, Reduced Till",
        category="Soil Erosion",
        resource_concerns=("soil_erosion", "soil_health"),
        base_points=3.0,
        estimated_rate_per_acre=3.25,
        legacy_codes=("E345A",),
        description=(
            "Reduce tillage intensity and maintain surface residue cover after "
            "planting."
        ),
        note=_ADDED_FOR_GAP_CLOSURE_NOTE,
    ),
    CspPractice(
        code="590",
        practice_standard_code="590",
        name="Nutrient Management",
        category="Water Quality",
        resource_concerns=("water_quality", "air_quality"),
        base_points=4.0,
        estimated_rate_per_acre=0.80,
        legacy_codes=("E590A", "E590B", "E590C", "E590D", "E511A"),
        description=(
            "Manage the source, rate, timing, and placement of nutrients to "
            "improve uptake and reduce losses."
        ),
    ),
    CspPractice(
        code="595",
        practice_standard_code="595",
        name="Pest Management Conservation System",
        category="Plant Condition",
        resource_concerns=("plant_condition", "water_quality"),
        base_points=3.0,
        estimated_rate_per_acre=0.60,
        legacy_codes=("E595A", "E595B"),
        description=(
            "Use scouting and economic thresholds to guide pest control and "
            "reduce pesticide risk."
        ),
        note=_ADDED_FOR_GAP_CLOSURE_NOTE,
    ),
    CspPractice(
        code="449",
        practice_standard_code="449",
        name="Irrigation Water Management",
        category="Water Quantity",
        resource_concerns=("water_quantity", "energy"),
        base_points=3.0,
        estimated_rate_per_acre=8.75,
        legacy_codes=("E449B",),
        description=(
            "Schedule irrigation from soil moisture or ET data to apply water "
            "only when crops need it."
        ),
        note=_ADDED_FOR_GAP_CLOSURE_NOTE,
    ),
    CspPractice(
        code="554",
        practice_standard_code="554",
        name="Drainage Water Management",
        category="Water Quantity",
        resource_concerns=("water_quality", "water_quantity"),
        base_points=3.0,
        estimated_rate_per_acre=6.50,
        legacy_codes=("E449A",),
        description=(
            "Use control structures on subsurface drainage to manage the water "
            "table and reduce nutrient loss."
        ),
        note=_ADDED_FOR_GAP_CLOSURE_NOTE,
    ),
    CspPractice(
        code="393",
        practice_standard_code="393",
        name="Filter Strip",
        category="Water Quality",
        resource_concerns=("water_quality", "soil_erosion"),
        base_points=3.0,
        estimated_rate_per_acre=45.00,
        legacy_codes=("E393A",),
        description=(
            "Establish a strip of permanent vegetation between cropland and "
            "water to trap sediment and nutrients."
        ),
    ),
    CspPractice(
        code="528",
        practice_standard_code="528",
        name="Prescribed Grazing",
        category="Animals",
        resource_concerns=("animals", "plant_condition", "soil_health"),
        base_points=2.5,
        estimated_rate_per_acre=7.50,
        higher_payment_category="agm",
        legacy_codes=("E528A",),
        description=(
            "Manage grazing timing, intensity, and rest. Advanced grazing "
            "management (AGM) activities are eligible for higher CSP payments."
        ),
    ),
    CspPractice(
        code="374",
        practice_standard_code="374",
        name="Energy Efficient Agricultural Operation",
        category="Energy",
        resource_concerns=("energy", "air_quality"),
        base_points=3.0,
        estimated_rate_per_acre=1.25,
        legacy_codes=("E374A",),
        description=(
            "Reduce on-farm energy use, for example through grain dryer or "
            "pumping efficiency improvements."
        ),
        note=_ADDED_FOR_GAP_CLOSURE_NOTE,
    ),
    # --- Scoring only (no CSP payment estimate) ---
    CspPractice(
        code="327",
        practice_standard_code="327",
        name="Conservation Cover",
        category="Soil Health and Organic Matter",
        resource_concerns=("soil_health", "plant_condition"),
        base_points=3.0,
    ),
    CspPractice(
        code="328",
        practice_standard_code="328",
        name="Conservation Crop Rotation",
        category="Soil Health and Organic Matter",
        resource_concerns=("soil_health", "soil_erosion"),
        base_points=4.0,
    ),
    CspPractice(
        code="330",
        practice_standard_code="330",
        name="Contour Farming",
        category="Soil Erosion",
        resource_concerns=("soil_erosion", "water_quality"),
        base_points=3.0,
    ),
    CspPractice(
        code="380",
        practice_standard_code="380",
        name="Windbreak/Shelterbelt Establishment",
        category="Soil Erosion",
        resource_concerns=("soil_erosion", "air_quality"),
        base_points=2.0,
    ),
    CspPractice(
        code="382",
        practice_standard_code="382",
        name="Fence",
        category="Animals",
        resource_concerns=("animals", "water_quality"),
        base_points=1.5,
    ),
    CspPractice(
        code="412",
        practice_standard_code="412",
        name="Grassed Waterway",
        category="Water Quality",
        resource_concerns=("water_quality", "soil_erosion"),
        base_points=3.0,
    ),
    CspPractice(
        code="430",
        practice_standard_code="430",
        name="Irrigation Pipeline",
        category="Water Quantity",
        resource_concerns=("water_quantity",),
        base_points=2.0,
        note=_CODE_CORRECTED_NOTE,
    ),
    CspPractice(
        code="600",
        practice_standard_code="600",
        name="Terrace",
        category="Water Quality",
        resource_concerns=("water_quality", "water_quantity"),
        base_points=3.0,
    ),
    CspPractice(
        code="612",
        practice_standard_code="612",
        name="Tree/Shrub Establishment",
        category="Plant Condition",
        resource_concerns=("soil_erosion", "air_quality", "plant_condition"),
        base_points=2.5,
    ),
    CspPractice(
        code="441",
        practice_standard_code="441",
        name="Irrigation System, Microirrigation",
        category="Water Quantity",
        # NRCS 441 is an efficient irrigation practice (small, frequent
        # applications at the root zone), so it addresses inefficient water use
        # as well as the pumping energy that less applied water saves.
        resource_concerns=("water_quantity", "energy"),
        base_points=2.0,
        note=(
            f"{_CODE_CORRECTED_NOTE} Water quantity added {NRCS_PRACTICE_CODES_VERIFIED_AS_OF} "
            "per the NRCS 441 standard: "
            "https://www.nrcs.usda.gov/resources/guides-and-instructions/"
            "irrigation-system-microirrigation-ac-441-conservation-practice"
        ),
    ),
    # Irrigation Water Management is standard 449 (a CSP activity above). The
    # former "666" entry duplicated it under Forest Stand Improvement's code.
)


#: Every practice RegenAI scores or estimates, keyed by ``code``.
CSP_PRACTICE_CATALOG: Final[dict[str, CspPractice]] = {p.code: p for p in _CSP_PRACTICES}


CSP_PRACTICE_CATALOG_RULE: Final[EstimatedRule] = EstimatedRule(
    key="csp_practice_catalog",
    status="estimate",
    as_of=CSP_SCORING_MODEL_AS_OF,
    note=(
        "Concern mappings merge RegenAI's former scoring and payment tables; "
        "base points are RegenAI weights. Neither is verified against NRCS "
        "practice standard purposes or CART."
    ),
)


#: Activities recommended to close a gap on each resource concern, best first.
#: Every code must be a CSP activity whose ``resource_concerns`` include the
#: concern (tests/test_csp_scoring.py enforces this).
CSP_GAP_CLOSURE_ACTIVITIES: Final[dict[str, tuple[str, ...]]] = {
    "soil_health": ("340", "328-RCCR", "329"),
    "soil_erosion": ("329", "345", "340"),
    "water_quality": ("590", "393", "554"),
    "water_quantity": ("449", "554"),
    "air_quality": ("340", "590"),
    "plant_condition": ("328-IRCCR", "595"),
    "animals": ("528",),
    "energy": ("374", "449"),
}


#: Every unsourced value the scoring model depends on.
CSP_SCORING_ESTIMATED_RULES: Final[tuple[EstimatedRule, ...]] = (
    CSP_CART_MAX_POINTS_RULE,
    CSP_STEWARDSHIP_THRESHOLD_RULE,
    CSP_STATE_RANKING_THRESHOLD_RULE,
    CSP_SOM_RULE,
    CSP_PRACTICE_CATALOG_RULE,
)
