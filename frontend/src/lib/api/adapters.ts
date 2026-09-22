/**
 * Adapters from backend response models to UI view models.
 *
 * The backend (FastAPI) returns the shapes defined in the "backend models"
 * sections of ./types.ts. Several components were written against richer UI
 * view models; these pure functions bridge the two. Keep this module free of
 * browser-only and server-only imports so both Server and Client Components can
 * use it.
 */

import type {
  ActivityCreateInput,
  ActivityDetails,
  ActivityRecord,
  ActivityType,
  APHResponse,
  APHResult,
  CreditEligibility,
  CreditEligibilityGetResponse,
  CreditReportProgram,
  CSPDeadline,
  CSPDeadlinesResponse,
  CSPEligibility,
  CSPEligibilityResponse,
  CSPEnhancement,
  CSPEnhancementActivity,
  CSPEnhancementsResponse,
  CSPPaymentEstimate,
  CSPPaymentEstimateResponse,
  CSPResourceConcern,
  CSPResourceConcernResult,
  CSPRuleCitation,
  CSPRuleNotes,
  CSPRulesMetadata,
  CSPScore,
  CSPSuggestedActivity,
  FieldActivity,
  ScoutingSeverity,
  VcmEstimate,
  VcmFieldEstimate,
  VcmPracticeEstimate,
  YieldHistoryRecord,
  YieldRecord,
} from "./types";
import { CSP_PAYMENT_DISCLAIMER } from "@/lib/csp-status";

// ── Shared helpers ────────────────────────────────────────────────────────────

/** US federal fiscal year (starts October 1) for an ISO timestamp. */
function fiscalYear(iso: string): number {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return new Date().getFullYear();
  return d.getUTCMonth() >= 9 ? d.getUTCFullYear() + 1 : d.getUTCFullYear();
}

function round(value: number, digits = 0): number {
  const f = 10 ** digits;
  return Math.round(value * f) / f;
}

// ── Credits ───────────────────────────────────────────────────────────────────

/** GET /credits/ returns { eqip, vcm }; components expect a list. */
export function creditsToList(
  resp: CreditEligibilityGetResponse | null | undefined
): CreditEligibility[] {
  if (!resp) return [];
  return [resp.eqip, resp.vcm].filter(
    (c): c is CreditEligibility => c !== null && c !== undefined
  );
}

function vcmPracticeEstimate(raw: unknown): VcmPracticeEstimate | null {
  if (typeof raw !== "object" || raw === null) return null;
  const p = raw as Record<string, unknown>;
  const practiceCode = str(p["practice_code"]);
  if (!practiceCode) return null;
  return {
    practice_code: practiceCode,
    practice_name: str(p["practice_name"]) ?? `Practice ${practiceCode}`,
    rate_credits_per_acre: num(p["rate_credits_per_acre"]) ?? 0,
    estimated_credits: num(p["estimated_credits"]) ?? 0,
  };
}

function vcmFieldEstimate(raw: Record<string, unknown>): VcmFieldEstimate | null {
  const fieldId = str(raw["field_id"]);
  if (!fieldId) return null;
  const practices = Array.isArray(raw["practices"])
    ? raw["practices"]
        .map(vcmPracticeEstimate)
        .filter((p): p is VcmPracticeEstimate => p !== null)
    : [];
  return {
    field_id: fieldId,
    field_name: str(raw["field_name"]) ?? "Unnamed field",
    acres: num(raw["acres"]) ?? 0,
    practices,
    field_total_credits: num(raw["field_total_credits"]) ?? 0,
  };
}

/**
 * VCM estimate from GET /credits/report. field_breakdown is typed loosely by
 * the API (list[dict]), so malformed rows are dropped rather than guessed at.
 * Returns null when there is no estimate to show.
 */
export function vcmEstimateFromReport(
  program: CreditReportProgram | null | undefined
): VcmEstimate | null {
  if (!program || program.estimated_total_credits === null) return null;
  const fields = program.field_breakdown
    .map(vcmFieldEstimate)
    .filter((f): f is VcmFieldEstimate => f !== null);
  return { estimated_total_credits: program.estimated_total_credits, fields };
}

// ── CSP ───────────────────────────────────────────────────────────────────────

export function adaptResourceConcern(
  rc: CSPResourceConcern,
  suggestedActivities: CSPSuggestedActivity[] = []
): CSPResourceConcernResult {
  const score =
    rc.points_possible > 0
      ? Math.round((rc.points_earned / rc.points_possible) * 100)
      : 0;
  return {
    code: rc.concern_id.toUpperCase(),
    name: rc.name,
    currently_met: rc.meets_threshold,
    threshold_met: rc.meets_threshold,
    score,
    points_earned: rc.points_earned,
    evidence: rc.practices_addressing.map((code) => `Practice ${code} on file`),
    suggested_activities: suggestedActivities,
  };
}

/**
 * Convert GET /csp/deadlines into banner-ready deadlines. The backend already
 * drops past dates, sorts soonest first, and computes days/urgency.
 */
export function adaptDeadlines(
  resp: CSPDeadlinesResponse | null | undefined
): CSPDeadline[] {
  if (!resp) return [];
  return resp.deadlines.map((d) => ({
    deadline_id: d.id,
    state_code: d.state,
    program: d.program,
    cutoff_date: d.deadline_date,
    cutoff_name: d.title,
    days_until: d.days_remaining,
    alert_severity: d.deadline_date && d.urgency ? d.urgency : "undated",
    status: d.status,
    description: d.description,
    notes: d.notes,
    source_url: d.source_url,
    as_of: d.as_of,
  }));
}

/**
 * A program-rule count from the API. Undefined when a response omits it (older
 * backend), so copy falls back to wording without a number instead of guessing.
 */
function ruleCount(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function minConcernsRequired(e: CSPEligibilityResponse): number | undefined {
  return ruleCount(e.min_concerns_required);
}

/**
 * The state's estimated ranking threshold, or null when the API has none for
 * that state. A missing threshold is not a zero: with no published figure the
 * UI must say NRCS decides ranking rather than print a number or a gap.
 */
function rankingThreshold(e: {
  state_ranking_threshold?: number | null;
}): number | null {
  const value = e.state_ranking_threshold;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function buildMissingRequirements(e: CSPEligibilityResponse): string[] {
  const missing: string[] = [];
  const minRequired = minConcernsRequired(e);
  if (minRequired !== undefined) {
    const needed = Math.max(0, minRequired - e.resource_concerns_meeting_threshold);
    if (needed > 0) {
      missing.push(
        `Meet the stewardship threshold on ${needed} more conservation area${needed === 1 ? "" : "s"} (at least ${minRequired} are required).`
      );
    }
  } else if (!e.is_eligible) {
    missing.push(
      "Meet the stewardship threshold on the required number of conservation areas."
    );
  }
  // With no published threshold there is nothing to fall short of, so no
  // requirement is listed: NRCS ranks the application instead.
  const threshold = rankingThreshold(e);
  if (threshold !== null && e.meets_ranking_threshold === false) {
    const gap = Math.max(0, round(threshold - e.cart_score, 1));
    missing.push(
      `Earn ${gap} more points to reach the ${threshold}-point state ranking threshold.`
    );
  }
  const unmet = e.resource_concerns_detail
    .filter((rc) => !rc.meets_threshold && rc.points_possible > 0)
    .sort(
      (a, b) =>
        b.points_possible - b.points_earned - (a.points_possible - a.points_earned)
    )
    .slice(0, 3);
  for (const rc of unmet) {
    missing.push(
      `Improve ${rc.name} (${rc.points_earned} of ${rc.points_possible} points).`
    );
  }
  return missing;
}

/**
 * Gap-closing activities for one unmet concern: the codes the eligibility
 * response recommends, narrowed to activities whose API-listed concerns
 * include this one. Names come from GET /csp/enhancements.
 */
function suggestedActivitiesFor(
  rc: CSPResourceConcern,
  recommendedCodes: ReadonlySet<string>,
  enhancements: CSPEnhancementActivity[]
): CSPSuggestedActivity[] {
  if (rc.meets_threshold) return [];
  return enhancements
    .filter(
      (a) =>
        recommendedCodes.has(a.code) &&
        a.resource_concerns_addressed.includes(rc.concern_id)
    )
    .map((a) => ({
      code: a.code,
      practice_standard_code: a.practice_standard_code,
      name: a.name,
    }));
}

/** Convert GET /csp/eligibility (+ optional payments/deadlines/enhancements) into the view model. */
export function adaptEligibility(
  e: CSPEligibilityResponse,
  extras: {
    payments?: CSPPaymentEstimateResponse | null;
    deadlines?: CSPDeadline[];
    enhancements?: CSPEnhancementsResponse | null;
  } = {}
): CSPEligibility {
  const qualifyingCodes = Array.from(
    new Set(e.resource_concerns_detail.flatMap((rc) => rc.practices_addressing))
  );
  const score = Math.round(e.cart_score);
  const minRequired = minConcernsRequired(e);
  const recommendedCodes = new Set(e.recommended_enhancements);
  const enhancementItems = extras.enhancements?.enhancements ?? [];

  return {
    farm_id: e.farm_id,
    fiscal_year: fiscalYear(e.evaluated_at),
    eligibility_status: e.status,
    is_eligible: e.is_eligible,
    rc_count_above_threshold: e.resource_concerns_meeting_threshold,
    min_concerns_required: minRequired,
    // The backend sets is_eligible exactly when the minimum is met; use it
    // when the minimum itself is missing from the response.
    meets_min_concerns:
      minRequired !== undefined
        ? e.resource_concerns_meeting_threshold >= minRequired
        : e.is_eligible,
    additional_concerns_required: ruleCount(e.additional_concerns_required),
    contract_years: ruleCount(e.contract_years),
    rc_count_will_meet: 0, // backend has no enhancement commitments yet
    resource_concerns_met: e.resource_concerns_detail.map((rc) =>
      adaptResourceConcern(
        rc,
        suggestedActivitiesFor(rc, recommendedCodes, enhancementItems)
      )
    ),
    active_enhancement_codes: [], // backend has no enhancement selection yet
    recommended_enhancement_codes: e.recommended_enhancements,
    qualifying_eqip_codes: qualifyingCodes,
    stewardship_score: score,
    estimated_ranking_score: score,
    act_now_eligible: e.status === "act_now",
    act_now_threshold: rankingThreshold(e),
    estimated_annual_payment: extras.payments?.total_annual_payment ?? null,
    estimated_5yr_payment: extras.payments?.total_5year_payment ?? null,
    missing_requirements: buildMissingRequirements(e),
    ineligibility_reasons: [],
    upcoming_deadlines: extras.deadlines ?? [],
    notes: e.eligibility_notes,
    evaluated_at: e.evaluated_at,
    from_cache: false,
  };
}

/** Build the score-gauge view model from the concern scores on an eligibility response. */
export function scoreFromEligibility(
  e: CSPEligibilityResponse,
  improvementRecommendations: string[] = []
): CSPScore {
  return {
    farm_id: e.farm_id,
    stewardship_score: Math.round(e.cart_score),
    // No published score bands exist, so the only label is the backend status.
    eligibility_status: e.status,
    ranking_threshold: rankingThreshold(e),
    score_breakdown: e.resource_concerns_detail.map((rc) => {
      const adapted = adaptResourceConcern(rc);
      return {
        resource_concern: rc.name,
        code: adapted.code,
        points_earned: rc.points_earned,
        max_points: rc.points_possible,
        score: adapted.score,
        currently_met: rc.meets_threshold,
      };
    }),
    improvement_recommendations: improvementRecommendations,
    from_cache: false,
    evaluated_at: e.evaluated_at,
  };
}

/** Short rule citation from backend rules metadata. */
export function ruleCitation(rules: CSPRulesMetadata): CSPRuleCitation {
  return {
    as_of: rules.as_of,
    source_title: rules.source_title,
    source_url: rules.source_url,
  };
}

/** Rule notes from the backend rules block, so pages never restate rules by hand. */
export function ruleNotes(rules: CSPRulesMetadata): CSPRuleNotes {
  return {
    existing_activity_payment: rules.existing_activity_payment.note,
    annual_payment_limit: rules.annual_payment_limit_note,
    activity_model: rules.activity_model_note,
    activity_rate_basis: rules.activity_rates.basis,
  };
}

/**
 * Convert GET /csp/payments into the payment-summary view model. Amounts,
 * limits and rule notes all come from the response's `rules` block; activity
 * payments come straight from the backend breakdown.
 */
export function adaptPayment(
  p: CSPPaymentEstimateResponse,
  disclaimer: string = CSP_PAYMENT_DISCLAIMER
): CSPPaymentEstimate {
  return {
    farm_id: p.farm_id,
    state_code: p.state,
    fiscal_year: fiscalYear(p.estimated_at),
    total_cropland_acres: p.eligible_acres,
    rc_count_above_threshold: p.resource_concerns_addressed,
    eap_annual: p.eap_annual,
    activity_payment_annual: p.activity_payment_annual,
    annual_total: p.total_annual_payment,
    contract_5yr_total: p.total_5year_payment,
    per_acre_annual:
      p.eligible_acres > 0 ? p.total_annual_payment / p.eligible_acres : 0,
    contract_years: p.contract_years,
    contract_limit_amount: p.contract_limit.amount,
    contract_limit_label: p.contract_limit.label,
    contract_limit_applied: p.payment_capped,
    eap_label: p.rules.existing_activity_payment.label,
    annual_payment_limit: p.annual_payment_limit,
    activity_breakdown: p.activities_included.map((a) => ({
      code: a.code,
      practice_standard_code: a.practice_standard_code,
      name: a.name,
      higher_payment: a.higher_payment,
      higher_payment_category: a.higher_payment_category,
      rate_per_acre: a.estimated_rate_per_acre,
      rate_is_estimate: a.rate_is_estimate,
      acres: a.acres,
      payment: round(a.estimated_annual_payment, 2),
    })),
    activity_rate_basis: p.rules.activity_rates.basis,
    rules: ruleCitation(p.rules),
    rule_notes: ruleNotes(p.rules),
    disclaimer,
  };
}

/** Convert one GET /csp/enhancements item into the enhancement-list view model. */
export function adaptEnhancement(e: CSPEnhancementActivity): CSPEnhancement {
  return {
    id: `enh-${e.code}`,
    code: e.code,
    practice_standard_code: e.practice_standard_code,
    name: e.name,
    category: e.category || e.resource_concerns_addressed[0] || "Conservation activity",
    land_use: e.land_use,
    description: e.description,
    implementation_notes: e.implementation_notes ?? "",
    base_payment_rate: e.estimated_rate_per_acre,
    payment_unit: "acre",
    rate_is_estimate: e.rate_is_estimate,
    rate_basis: e.rate_basis,
    higher_payment: e.higher_payment,
    higher_payment_category: e.higher_payment_category,
    point_weight: e.priority_score,
    resource_concern_code: e.resource_concerns_addressed[0] ?? "",
    status: "considering", // backend has no enhancement selection yet
    acres_enrolled: e.applicable_acres,
    estimated_payment: e.estimated_annual_payment,
  };
}

// ── Activities ────────────────────────────────────────────────────────────────

/** null (column not recorded) -> undefined, so the UI hides the row. */
function opt<T>(value: T | null | undefined): T | undefined {
  return value ?? undefined;
}

/**
 * Typed detail block for a flat activity row. Only columns the backend stores
 * are mapped; missing values stay undefined rather than becoming 0 or "".
 */
function activityDetails(a: ActivityRecord): ActivityDetails {
  switch (a.activity_type) {
    case "plant":
      return {
        variety: opt(a.seed_variety),
        seeding_rate_kac: opt(a.seeding_rate),
        seed_treatment: opt(a.seed_treatment),
      };
    case "spray":
      return {
        product_name: opt(a.product_name),
        rate: opt(a.rate_per_acre),
        rate_unit: opt(a.rate_unit),
        target_pest: opt(a.target_pest),
        restricted_use: a.restricted_use,
        applicator_name: opt(a.applicator_name),
        applicator_cert_number: opt(a.applicator_license),
      };
    case "fertilize":
      return {
        product_name: opt(a.product_name),
        rate: opt(a.rate_per_acre),
        rate_unit: opt(a.rate_unit),
      };
    case "scout":
      return {
        pest_name: opt(a.pest_disease_found),
        severity: opt(a.severity),
      };
    case "harvest":
      return {
        yield_bu_ac: opt(a.yield_bu_acre),
        moisture_pct: opt(a.moisture_pct),
        crop_year: opt(a.crop_year),
      };
    case "tillage":
      return { depth_in: opt(a.tillage_depth_in) };
    case "cover_crop":
      return { species: opt(a.cover_crop_species) };
    default:
      return {};
  }
}

/** Convert a flat backend ActivityRecord into the card/widget view model. */
export function activityToView(
  a: ActivityRecord,
  farmId: string,
  fallbackAcres = 0
): FieldActivity {
  return {
    id: a.id,
    field_id: a.field_id,
    farm_id: farmId,
    activity_type: a.activity_type,
    activity_date: a.activity_date,
    acres: a.acres_applied ?? fallbackAcres,
    operator: opt(a.operator),
    equipment: opt(a.equipment_used),
    cost_per_acre: opt(a.cost_per_acre),
    notes: opt(a.notes),
    details: activityDetails(a),
    created_at: a.created_at,
  };
}

function num(v: unknown): number | undefined {
  if (v === undefined || v === null || v === "") return undefined;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : undefined;
}

function str(v: unknown): string | undefined {
  if (typeof v !== "string") return undefined;
  const t = v.trim();
  return t.length > 0 ? t : undefined;
}

/**
 * Build a POST /activities body from the activity form's validated values.
 * Form fields the backend has no column for are appended to `notes` so they
 * are not silently lost.
 */
export function buildActivityCreatePayload(
  activityType: ActivityType,
  values: Record<string, unknown>
): ActivityCreateInput {
  const activityDate = str(values["activity_date"]) ?? "";
  const payload: ActivityCreateInput = {
    field_id: str(values["field_id"]) ?? "",
    activity_type: activityType,
    activity_date: activityDate,
    acres_applied: num(values["acres"]),
    operator: str(values["operator"]),
    equipment_used: str(values["equipment"]),
    cost_per_acre: num(values["cost_per_acre"]),
  };

  const extras: string[] = [];
  const addExtra = (label: string, v: unknown, suffix = "") => {
    if (v === undefined || v === null || v === "") return;
    extras.push(`${label}: ${String(v)}${suffix}`);
  };

  switch (activityType) {
    case "plant":
      payload.seed_variety = str(values["variety"]);
      payload.seeding_rate = num(values["seeding_rate_kac"]);
      payload.seed_treatment = str(values["seed_treatment"]);
      addExtra("Row spacing", values["row_spacing_in"], " in");
      addExtra("Planting depth", values["depth_in"], " in");
      break;
    case "spray":
      payload.product_name = str(values["product_name"]);
      payload.rate_per_acre = num(values["rate_oz_ac"]);
      payload.rate_unit = "oz/ac";
      payload.target_pest = str(values["target_pest"]);
      payload.restricted_use = values["restricted_use"] === true;
      payload.applicator_name = str(values["applicator_name"]);
      payload.applicator_license = str(values["applicator_cert_number"]);
      addExtra("EPA reg #", values["epa_reg_number"]);
      addExtra("Wind", values["wind_mph"], " mph");
      addExtra("Temperature", values["temp_f"], "°F");
      break;
    case "fertilize":
      payload.product_name = str(values["product_name"]);
      payload.rate_per_acre = num(values["n_lbs_ac"]);
      payload.rate_unit = "lbs N/ac";
      addExtra("N-P-K (lbs/ac)", [values["n_lbs_ac"], values["p_lbs_ac"], values["k_lbs_ac"]].map((x) => x ?? 0).join("-"));
      addExtra("Method", values["method"]);
      break;
    case "scout":
      payload.pest_disease_found = str(values["pest_name"]);
      payload.severity = (str(values["severity"]) as ScoutingSeverity | undefined) ?? undefined;
      addExtra("Pest type", values["pest_type"]);
      if (values["threshold_exceeded"] === true) extras.push("Economic threshold exceeded");
      addExtra("Action taken", values["action_taken"]);
      break;
    case "harvest": {
      payload.yield_bu_acre = num(values["yield_bu_ac"]);
      payload.moisture_pct = num(values["moisture_pct"]);
      const year = Number(activityDate.slice(0, 4));
      if (Number.isInteger(year) && year >= 1990) payload.crop_year = year;
      addExtra("Test weight", values["test_weight_lbs_bu"], " lbs/bu");
      addExtra("Elevator ticket", values["elevator_ticket"]);
      break;
    }
    case "tillage":
      payload.tillage_depth_in = num(values["tillage_depth_in"]);
      break;
    case "cover_crop":
      payload.cover_crop_species = str(values["cover_crop_species"]);
      break;
    default:
      break;
  }

  const notes = [str(values["notes"]), extras.length > 0 ? extras.join("; ") : undefined]
    .filter((n): n is string => !!n)
    .join("\n");
  if (notes) payload.notes = notes.slice(0, 2000);

  return payload;
}

// ── Yield history / APH ───────────────────────────────────────────────────────

export function yieldRecordToView(
  r: YieldHistoryRecord,
  farmId: string
): YieldRecord {
  return {
    id: r.id,
    field_id: r.field_id,
    farm_id: farmId,
    crop_year: r.crop_year,
    crop_type: r.crop_type,
    yield_bu_ac: r.yield_bu_acre,
    moisture_pct: r.moisture_pct,
    acres: r.acres_harvested,
    created_at: r.created_at,
  };
}

/** Combine GET /yield-history/aph with a trend computed from its records. */
export function aphToView(aph: APHResponse, farmId: string): APHResult {
  const records = aph.records.map((r) => yieldRecordToView(r, farmId));
  const byYear = [...records].sort((a, b) => a.crop_year - b.crop_year);
  const oldest = byYear[0];
  const newest = byYear[byYear.length - 1];
  const trendPct =
    oldest && newest && oldest.yield_bu_ac > 0
      ? round(((newest.yield_bu_ac - oldest.yield_bu_ac) / oldest.yield_bu_ac) * 100, 1)
      : 0;
  const trend_direction: APHResult["trend_direction"] =
    trendPct >= 2 ? "up" : trendPct <= -2 ? "down" : "flat";

  return {
    field_id: aph.field_id,
    years_used: aph.years_used,
    average_yield_bu_ac: aph.aph_yield,
    trend_direction,
    trend_pct: trendPct,
    records,
  };
}
