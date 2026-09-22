"""
Prompt templates for the RegenAI recommendation engine.

The system prompt instructs the LLM to produce structured JSON recommendations
that cite specific EQIP practice codes and are grounded in the provided soil
and weather data. Output is framed as decision support, not professional
agronomic advice. CSP dollar figures are interpolated from program_rules so
the prompt never repeats a stale rule.
"""

from app.services.program_rules import (
    CSP_ACT_NOW_NOTE,
    CSP_ANNUAL_PAYMENT_LIMIT,
    CSP_CART_MAX_POINTS_PER_CONCERN,
    CSP_CONTRACT_LIMIT_FY2026_INDIVIDUAL,
    CSP_CONTRACT_LIMIT_FY2026_JOINT,
    CSP_CONTRACT_YEARS,
    CSP_EXISTING_ACTIVITY_PAYMENT,
    CSP_MIN_PRIORITY_CONCERNS,
    CSP_STEWARDSHIP_THRESHOLD_FRACTION,
    NB_440_26_2_AS_OF,
)

_CSP_MIN_CONCERNS = int(CSP_MIN_PRIORITY_CONCERNS.value)
# The scoring model has one entry per NRCS priority resource concern category.
_CSP_PRIORITY_RESOURCE_CONCERN_COUNT = len(CSP_CART_MAX_POINTS_PER_CONCERN)


def _usd(amount: float | int | None) -> str:
    return f"${float(amount or 0):,.0f}"


_EAP_USD = _usd(CSP_EXISTING_ACTIVITY_PAYMENT.value)
_CONTRACT_LIMIT_INDIVIDUAL_USD = _usd(CSP_CONTRACT_LIMIT_FY2026_INDIVIDUAL.value)
_CONTRACT_LIMIT_JOINT_USD = _usd(CSP_CONTRACT_LIMIT_FY2026_JOINT.value)
_ANNUAL_PAYMENT_LIMIT_TEXT = (
    "no annual payment limit"
    if CSP_ANNUAL_PAYMENT_LIMIT.value is None
    else f"{_usd(CSP_ANNUAL_PAYMENT_LIMIT.value)} annual payment limit"
)
_STEWARDSHIP_THRESHOLD_PCT = f"{CSP_STEWARDSHIP_THRESHOLD_FRACTION:.0%}"


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

RECOMMENDATION_SYSTEM_PROMPT = f"""\
You are RegenAI, a regenerative agriculture decision-support assistant. Your \
role is to analyze farm data and suggest conservation practices that a farmer \
could discuss with their local NRCS office or agronomist.

CRITICAL RULES:
1. Your output MUST be valid JSON and nothing else. No markdown, no prose, no \
code fences. Return ONLY a JSON array.
2. Each recommendation MUST reference a practice_code from the EQIP practice \
list provided below. Do NOT invent practice codes.
3. Do NOT recommend practices that are not supported by the provided soil and \
weather data. If the data is insufficient to justify a practice, say so \
explicitly in the rationale rather than guessing.
4. Do NOT re-recommend practices the farmer has already adopted or acted on. \
Check the current_practices and acted_recommendations sections.
5. Limit your response to 3-6 recommendations, prioritized by impact.
6. This is decision support only, NOT professional agronomic advice. Each \
rationale must include the phrase "Discuss with your local NRCS office or \
agronomist before implementing."
7. For EVERY recommendation, include a "csp_impact" field that describes how \
adopting this practice would affect the farm's CSP eligibility, CART score, \
and estimated annual payment. Be specific: name the resource concern category \
addressed, whether it moves the farm closer to or past the stewardship \
threshold, and whether it could be offered as a CSP activity under its NRCS \
practice standard code.

OUTPUT FORMAT — return a JSON array of objects with exactly these fields \
and no others:
[
  {{
    "field_id": "<UUID of the field this recommendation targets>",
    "practice_code": "<EQIP practice code, e.g. 340>",
    "title": "<Short, actionable title, max 120 chars>",
    "rationale": "<2-4 sentences explaining WHY this practice fits this \
field's soil, weather, and crop context. Cite specific data points.>",
    "priority": "<high | medium | low>",
    "csp_impact": "<1-3 sentences describing how this practice affects CSP \
eligibility and payment. Example: 'Adopting cover crops (340) addresses the \
Soil Health and Water Quality resource concern categories. If this brings \
Soil Health above the stewardship threshold, the farm gains a second qualifying \
concern and could become CSP-eligible. Cover crop activities remain a \
higher-payment CSP category; the activity payment would be added to the \
{_EAP_USD}/year existing activity payment.'>"
  }}
]

PRIORITY GUIDELINES:
- high: Addresses an urgent soil health gap (low OM, erosion risk, pH \
imbalance) or is strongly aligned with the farmer's stated goals.
- medium: Beneficial improvement supported by the data but not urgent.
- low: Optional enhancement or long-term investment.

AGRONOMIC REASONING:
- Low organic matter for the field's soil texture supports cover crops (340) or \
conservation cover (327). Do not cite a fixed organic matter cutoff.
- Flag soil pH in the rationale when it is outside the range the state's \
extension service recommends for the crop, and suggest confirming with a soil \
test. Do not cite a fixed pH cutoff.
- High precipitation + sloped land suggests grassed waterways (412) or \
filter strips (393).
- Existing no-till paired with cover crops is a strong soil health combination.
- Consider crop rotation diversity when recommending practice 328.
- For fields with livestock, consider prescribed grazing (528) and fencing (382).
- Windbreak/shelterbelt (380) and tree establishment (612) suit fields with \
wind erosion exposure.

CSP QUALIFICATION REASONING:
The Conservation Stewardship Program (CSP) pays farmers for EXISTING \
conservation AND new activities over a {CSP_CONTRACT_YEARS.value}-year contract. \
Key facts (NRCS rules as of {NB_440_26_2_AS_OF}):
- Eligibility requires meeting the stewardship threshold \
(>={_STEWARDSHIP_THRESHOLD_PCT} of max points) on at least \
{_CSP_MIN_CONCERNS} of {_CSP_PRIORITY_RESOURCE_CONCERN_COUNT} \
Priority Resource Concern categories.
- CART scores at or above the state ranking threshold may be considered for ACT \
NOW fast-track approval if the state offers it. {CSP_ACT_NOW_NOTE} Never promise \
ACT NOW approval.
- FY2026 CSP rules: {_EAP_USD}/year existing activity payment per contract plus \
activity payments; {_ANNUAL_PAYMENT_LIMIT_TEXT}; contract limit of \
{_CONTRACT_LIMIT_INDIVIDUAL_USD} for individuals and legal entities or \
{_CONTRACT_LIMIT_JOINT_USD} for joint operations. \
"E" enhancement codes and bundles were retired. Refer to activities by NRCS \
practice standard code: 328 (conservation crop rotation), 329 (no-till), \
340 (cover crop), 590 (nutrient management). Cover crops and resource \
conserving crop rotations remain higher-payment categories.
- Practices that address multiple resource concerns (e.g., 329 No-Till addresses \
soil health, soil erosion, AND water quality) are especially valuable for \
reaching the {_CSP_MIN_CONCERNS}-concern eligibility threshold \
and raising CART scores.

If the data is too sparse to make confident recommendations, return a JSON \
array with a single object whose practice_code is the most universally \
applicable practice (e.g. 340 Cover Crop), and state in the rationale that \
additional soil testing and field assessment are needed.\
"""


# ---------------------------------------------------------------------------
# User message builder
# ---------------------------------------------------------------------------

def _sanitize(value: str, max_length: int = 200) -> str:
    """Sanitize user-provided strings before inclusion in LLM prompts.

    Strips control characters, collapses whitespace, and truncates to prevent
    prompt injection attacks via farmer-entered farm/field names.
    """
    if not isinstance(value, str):
        return str(value)[:max_length]
    sanitized = value.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    # Collapse multiple spaces
    while "  " in sanitized:
        sanitized = sanitized.replace("  ", " ")
    return sanitized.strip()[:max_length]


def _csp_assessment_lines(assessment: dict) -> list[str]:
    """Render the assessment summary built by context._summarize_assessment().

    Lines for values that are unknown are omitted rather than defaulted.
    """
    lines: list[str] = []

    fiscal_year = assessment.get("fiscal_year")
    if fiscal_year:
        lines.append(f"Assessment fiscal year: FY{fiscal_year}")

    lines.append(f"CSP Eligibility Status: {assessment.get('eligibility_status') or 'unknown'}")

    score = assessment.get("stewardship_score")
    if score is not None:
        max_points = assessment.get("max_possible_points")
        suffix = f" of {float(max_points):.1f} possible" if max_points else ""
        lines.append(f"CART Score: {float(score):.1f}{suffix}")

    concerns_met = assessment.get("rc_count_above_threshold")
    if concerns_met is not None:
        lines.append(
            f"Priority Resource Concerns meeting threshold: {concerns_met} of "
            f"{_CSP_MIN_CONCERNS} required"
        )

    threshold = assessment.get("state_ranking_threshold")
    if threshold is not None:
        lines.append(f"State Ranking Threshold used by the assessment: {float(threshold):.1f}")
        if score is not None:
            gap = max(0.0, float(threshold) - float(score))
            lines.append(f"Gap to state ranking threshold: {gap:.1f} points")

    act_now = assessment.get("act_now_eligible")
    if act_now is not None:
        lines.append(
            "Meets state ranking threshold (ACT NOW is at state discretion): "
            f"{'yes' if act_now else 'no'}"
        )

    resource_concerns = assessment.get("resource_concerns") or []
    if resource_concerns:
        lines.append(
            f"Resource Concern Scores (threshold = {_STEWARDSHIP_THRESHOLD_PCT} of max points):"
        )
        for concern in resource_concerns:
            indicator = "ABOVE" if concern.get("meets_threshold") else "BELOW"
            earned = float(concern.get("points_earned") or 0.0)
            possible = float(concern.get("points_possible") or 0.0)
            lines.append(
                f"  - {_sanitize(concern.get('name', ''))}: "
                f"{earned:.1f} / {possible:.1f} pts [{indicator} threshold]"
            )

    activity_codes = assessment.get("gap_closure_activity_codes") or []
    if activity_codes:
        codes = ", ".join(_sanitize(str(code), 20) for code in activity_codes)
        lines.append(f"Gap-closure activities suggested by the assessment: {codes}")

    notes = assessment.get("notes")
    if notes:
        lines.append(f"Assessment notes: {_sanitize(notes, 600)}")

    return lines


def build_user_message(context: dict) -> str:
    """Build the user message from an assembled farm context dict.

    The message is a structured text block that presents all available farm
    data so the LLM can reason over it. Sensitive fields (user_id, raw UUIDs
    beyond field_id) are excluded.

    All user-provided text (farm names, field names, crop types, boundary
    descriptions) is sanitized before inclusion to mitigate prompt injection.

    Args:
        context: The dict returned by assemble_farm_context().

    Returns:
        A string suitable for the ``content`` field of a user message in the
        chat completions API.
    """
    farm = context["farm"]
    fields = context["fields"]
    soil_profiles = context["soil_profiles"]
    weather = context["weather"]
    current_practices = context["current_practices"]
    acted = context["acted_recommendations"]
    eqip = context["eqip_practices"]
    warnings = context.get("data_warnings", [])
    csp_assessment = context.get("csp_assessment")

    sections: list[str] = []

    # -- Farm overview
    sections.append("=== FARM OVERVIEW ===")
    sections.append(f"Name: {_sanitize(farm['name'])}")
    sections.append(f"State: {_sanitize(farm['state'])}")
    sections.append(f"County FIPS: {_sanitize(farm['county_fips'])}")
    sections.append(f"Total acres: {farm['total_acres']}")
    if farm.get("goals"):
        sections.append(f"Farmer goals: {_sanitize(farm['goals'])}")
    sections.append("")

    # -- Fields
    sections.append("=== FIELDS ===")
    if fields:
        for f in fields:
            field_practices = (
                ", ".join(_sanitize(str(p)) for p in (f["practices"] or [])) or "none"
            )
            sections.append(
                f"- Field '{_sanitize(f['name'])}' (id: {f['id']}): "
                f"{f['acres']} acres, crop: {_sanitize(f['crop_type'])}, "
                f"current practices: {field_practices}"
            )
    else:
        sections.append("No fields registered.")
    sections.append("")

    # -- Soil profiles
    sections.append("=== SOIL DATA ===")
    if soil_profiles:
        for s in soil_profiles:
            sections.append(
                f"- Field {s['field_id']}: "
                f"texture={s['texture']}, pH={s['ph']}, "
                f"organic_matter={s['organic_matter_pct']}%, "
                f"map_unit={s['ssurgo_map_unit']}"
            )
    else:
        sections.append("No soil data available.")
    sections.append("")

    # -- Weather
    sections.append("=== RECENT WEATHER (7-day forecast) ===")
    if weather:
        for w in weather:
            sections.append(
                f"- Field {w['field_id']} on {w['date']}: "
                f"high={w['temp_high']}C, low={w['temp_low']}C, "
                f"precip={w['precip_mm']}mm, soil_temp={w['soil_temp']}C"
            )
    else:
        sections.append("No weather data available.")
    sections.append("")

    # -- Current practices
    sections.append("=== CURRENT PRACTICES ALREADY IN USE ===")
    if current_practices:
        sections.append(", ".join(current_practices))
    else:
        sections.append("None reported.")
    sections.append("")

    # -- Acted/dismissed recommendations
    sections.append("=== PREVIOUSLY ACTED OR DISMISSED RECOMMENDATIONS ===")
    if acted:
        for r in acted:
            sections.append(
                f"- Field {r['field_id']}: "
                f"practice {r['practice_code']} ({r['title']}) — {r['status']}"
            )
    else:
        sections.append("None.")
    sections.append("")

    # -- EQIP practice reference
    sections.append("=== VALID EQIP PRACTICE CODES (you MUST only use these) ===")
    if eqip:
        for p in eqip:
            sections.append(
                f"- {p['code']}: {p['name']} [{p.get('category', '')}] — "
                f"{p.get('description', '')}"
            )
    else:
        sections.append("EQIP practice list unavailable. Use only well-known NRCS codes.")
    sections.append("")

    # -- CSP assessment context
    sections.append("=== CSP (CONSERVATION STEWARDSHIP PROGRAM) STATUS ===")
    if csp_assessment:
        sections.extend(_csp_assessment_lines(csp_assessment))
    else:
        sections.append(
            "No CSP assessment available yet. When making recommendations, "
            "note which resource concern categories each practice would address "
            "and how it could contribute to CSP eligibility."
        )
    sections.append("")

    # -- Data warnings
    if warnings:
        sections.append("=== DATA QUALITY WARNINGS ===")
        for w in warnings:
            sections.append(f"- {w}")
        sections.append("")

    sections.append(
        "Based on the above data, generate prioritized conservation practice "
        "recommendations for this farm. For EACH recommendation, include the "
        "csp_impact field describing how this practice affects CSP eligibility, "
        "CART score, and payment. Return ONLY a JSON array."
    )

    return "\n".join(sections)
