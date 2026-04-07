"""
Prompt templates for the RegenAI recommendation engine.

The system prompt instructs Claude to produce structured JSON recommendations
that cite specific EQIP practice codes and are grounded in the provided soil
and weather data. Output is framed as decision support, not professional
agronomic advice.
"""

import json

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

RECOMMENDATION_SYSTEM_PROMPT = """\
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
threshold, and whether it could qualify as a CSP enhancement activity.

OUTPUT FORMAT — return a JSON array of objects with exactly these fields:
[
  {
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
concern and becomes CSP-eligible. As a CSP enhancement (E340A), NRCS would \
cover 100% of implementation cost (~$35/acre), adding approximately $X/year \
to the Enhancement Activity Payment.>'>"
  }
]

PRIORITY GUIDELINES:
- high: Addresses an urgent soil health gap (low OM, erosion risk, pH \
imbalance) or is strongly aligned with the farmer's stated goals.
- medium: Beneficial improvement supported by the data but not urgent.
- low: Optional enhancement or long-term investment.

AGRONOMIC REASONING:
- Low organic matter (<2%) warrants cover crops (340) or conservation cover (327).
- Acidic pH (<5.5) or alkaline pH (>8.0) should be flagged in rationale.
- High precipitation + sloped land suggests grassed waterways (412) or \
filter strips (393).
- Existing no-till paired with cover crops is a strong soil health combination.
- Consider crop rotation diversity when recommending practice 328.
- For fields with livestock, consider prescribed grazing (528) and fencing (382).
- Windbreak/shelterbelt (380) and tree establishment (612) suit fields with \
wind erosion exposure.

CSP QUALIFICATION REASONING:
The Conservation Stewardship Program (CSP) pays farmers for EXISTING \
conservation AND new enhancements over a 5-year contract. Key facts:
- Eligibility requires meeting the stewardship threshold (>=50% of max points) \
  on at least 2 of 8 Priority Resource Concern categories.
- CART scores >= the state ranking threshold qualify for ACT NOW fast-track \
  approval ($4,000-$50,000/year).
- CSP Enhancement Activities pay 100% of implementation cost (115% for bundles \
  of 3+ enhancements). Common enhancement codes: E328A (crop rotation), \
  E329A (no-till), E340A (cover crop), E590A (nutrient management).
- Practices that address multiple resource concerns (e.g., 329 No-Till addresses \
  soil health, soil erosion, AND water quality) are especially valuable for \
  reaching the 2-concern eligibility threshold and raising CART scores.

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


def build_user_message(context: dict) -> str:
    """Build the user message from an assembled farm context dict.

    The message is a structured text block that presents all available farm
    data so the LLM can reason over it. Sensitive fields (user_id, raw UUIDs
    beyond field_id) are excluded.

    All user-provided text (farm names, field names, crop types, boundary
    descriptions) is sanitized before inclusion to mitigate prompt injection.

    When a CSP assessment is available in context["csp_assessment"], the
    message includes the farm's current CART score, eligibility status, and
    resource concern breakdown so the LLM can accurately describe CSP impact
    for each recommendation.

    Args:
        context: The dict returned by assemble_farm_context(). May optionally
            contain a "csp_assessment" key with the latest CSP evaluation.

    Returns:
        A string suitable for the ``content`` field of a user message in the
        Anthropic messages API.
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
            sections.append(
                f"- Field '{_sanitize(f['name'])}' (id: {f['id']}): "
                f"{f['acres']} acres, crop: {_sanitize(f['crop_type'])}, "
                f"current practices: {', '.join(_sanitize(str(p)) for p in (f['practices'] or [])) or 'none'}"
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
        cart_score = csp_assessment.get("cart_score", 0.0)
        csp_status = csp_assessment.get("status", "unknown")
        concerns_met = csp_assessment.get("concerns_meeting_threshold", 0)
        ranking_threshold = csp_assessment.get("state_ranking_threshold", 42.0)
        gap = max(0.0, ranking_threshold - cart_score)
        annual_payment = csp_assessment.get("estimated_annual_payment", 0.0)

        sections.append(f"CSP Eligibility Status: {csp_status}")
        sections.append(f"CART Score: {cart_score:.1f} / 100.0")
        sections.append(f"State Ranking Threshold: {ranking_threshold:.1f}")
        sections.append(f"Gap to ACT NOW threshold: {gap:.1f} points")
        sections.append(f"Priority Resource Concerns meeting threshold: {concerns_met} of 2 required")

        if annual_payment:
            sections.append(f"Estimated Current Annual CSP Payment: ${annual_payment:,.2f}")

        # Per-concern detail
        resource_concerns = (
            csp_assessment.get("resource_concerns_detail")
            or csp_assessment.get("score_breakdown", {}).get("resource_concern_scores", [])
        )
        if resource_concerns:
            sections.append("Resource Concern Scores (threshold = 50% of max points):")
            for concern in resource_concerns:
                threshold_indicator = "ABOVE" if concern.get("meets_threshold") else "BELOW"
                sections.append(
                    f"  - {concern.get('name', concern.get('concern_id', ''))}: "
                    f"{concern.get('points_earned', 0.0):.1f} / {concern.get('points_possible', 0.0):.1f} "
                    f"pts [{threshold_indicator} threshold]"
                )

        recommended_enhancements = csp_assessment.get("recommended_enhancements", [])
        if recommended_enhancements:
            sections.append(
                f"Gap-Closure Enhancements Recommended: {', '.join(recommended_enhancements)}"
            )
    else:
        sections.append(
            "No CSP assessment available yet. When making recommendations, "
            "note which resource concern categories each practice would address "
            "and how it could contribute to CSP eligibility. Run POST /csp/evaluate "
            "to generate a detailed assessment."
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
