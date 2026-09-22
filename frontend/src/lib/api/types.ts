// ─────────────────────────────────────────────────────────────────────────────
// RegenAI API types
//
// Two kinds of types live here:
//
//   1. Backend response / request models — these mirror the FastAPI Pydantic
//      schemas in backend/app/models/schemas.py (and the dict shapes returned by
//      backend/app/services/*) EXACTLY. The API clients return these.
//
//   2. UI view models (CSPEligibility, CSPScore, CSPPaymentEstimate,
//      CSPEnhancement, CSPDeadline, FieldActivity, YieldRecord, APHResult,
//      CSPChecklist). Components are written against these. They are NOT returned by the backend directly — use the
//      functions in ./adapters.ts to convert backend responses into them.
// ─────────────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  created_at: string;
  role: "farmer" | "admin";
}

// ── Farms (FarmResponse) ──────────────────────────────────────────────────────

export type FarmGoals = "cost_savings" | "carbon_credits" | "both";

export interface Farm {
  id: string;
  user_id: string;
  name: string;
  state: string;
  county_fips: string;
  total_acres: number;
  goals?: FarmGoals | null;
  created_at: string;
}

/** Body for POST /farms/ (FarmCreate). */
export type FarmCreateInput = Omit<Farm, "id" | "user_id" | "created_at">;
/** Body for PATCH /farms/{id} (FarmUpdate). */
export type FarmUpdateInput = Partial<FarmCreateInput>;

// ── Fields (FieldResponse) ────────────────────────────────────────────────────

export interface Field {
  id: string;
  farm_id: string;
  name: string;
  acres: number;
  crop_type: string;
  boundary_geojson?: Record<string, unknown> | null;
  boundary_description?: string | null; // "Section 14, Township 5N, Range 3W"
  practices?: string[];
  created_at: string;
  updated_at?: string | null;
}

/** Body for POST /fields/ (FieldCreate). */
export type FieldCreateInput = Omit<Field, "id" | "created_at" | "updated_at">;
/** Body for PATCH /fields/{id} (FieldUpdate). farm_id cannot be changed. */
export type FieldUpdateInput = Partial<Omit<FieldCreateInput, "farm_id">>;

/** Response of POST /fields/{id}/enrich (HTTP 202). */
export interface FieldEnrichResponse {
  status: string; // "enrichment_complete"
  field_id: string;
  weather_days_upserted: number;
  soil_profile_saved: boolean;
  warnings: string[];
}

// ── Soil / weather ────────────────────────────────────────────────────────────

/** SoilProfileResponse — GET /fields/{id}/soil returns this or null. */
export interface SoilProfile {
  id: string;
  field_id: string;
  ssurgo_map_unit: string;
  texture: string;
  ph: number | null; // null when the source has no reading
  organic_matter_pct: number | null;
  source: string; // e.g. "ssurgo" | "soilgrids" | "manual"
  fetched_at: string;
}

/**
 * WeatherResponse — GET /fields/{id}/weather returns up to 7 forecast days,
 * newest date first. Readings are null when Open-Meteo has no value.
 */
export interface WeatherData {
  id: string;
  field_id: string;
  date: string; // ISO date (YYYY-MM-DD)
  temp_high: number | null;
  temp_low: number | null;
  precip_mm: number | null;
  soil_temp: number | null;
  fetched_at: string;
}

// ── Recommendations ───────────────────────────────────────────────────────────

export type RecommendationPriority = "high" | "medium" | "low";
export type RecommendationStatus = "pending" | "acted" | "dismissed";

/** RecommendationResponse. */
export interface Recommendation {
  id: string;
  field_id: string;
  created_at: string;
  practice_code: string;
  title: string;
  rationale: string;
  priority: RecommendationPriority;
  status: RecommendationStatus;
}

/** Response of POST /recommendations/generate?farm_id= (HTTP 202). */
export interface RecommendationGenerateResponse {
  status: string; // "generation_complete"
  farm_id: string;
  recommendations_count: number;
  recommendations: Array<
    Pick<
      Recommendation,
      "id" | "field_id" | "practice_code" | "title" | "priority" | "status"
    >
  >;
}

// ── Credits (EQIP / VCM) ──────────────────────────────────────────────────────

export type CreditProgram = "EQIP" | "VCM";
export type CreditStatus = "eligible" | "not_eligible" | "pending_review";

/** CreditEligibilityResponse — a stored credit_eligibility row. */
export interface CreditEligibility {
  id: string;
  farm_id: string;
  program: CreditProgram;
  status: CreditStatus;
  practices_documented: string[];
  notes: string;
  updated_at: string;
}

/** CreditEligibilityGetResponse — GET /credits/?farm_id= */
export interface CreditEligibilityGetResponse {
  farm_id: string;
  eqip: CreditEligibility | null;
  vcm: CreditEligibility | null;
}

/** EvaluatedProgramResult — per-program part of POST /credits/evaluate. */
export interface EvaluatedProgramResult {
  program: string;
  eligibility_status: CreditStatus | null;
  practices_documented: string[];
  notes: string;
  updated_at: string | null;
  program_name: string | null;
  estimated_total_credits: number | null;
  field_breakdown: Array<Record<string, unknown>>;
}

/** CreditEvaluateResponse — POST /credits/evaluate?farm_id= */
export interface CreditEvaluateResponse {
  status: string; // "evaluation_complete"
  farm_id: string;
  eqip: EvaluatedProgramResult;
  vcm: EvaluatedProgramResult;
}

export interface CreditReportProgram {
  status: CreditStatus | null;
  notes: string;
  practices_documented: string[];
  updated_at: string | null;
  program_name: string | null;
  estimated_total_credits: number | null;
  field_breakdown: Array<Record<string, unknown>>;
}

/** CreditReportResponse — GET /credits/report?farm_id= */
export interface CreditReportResponse {
  report_type: string;
  generated_at: string;
  farm: {
    id: string | null;
    name: string | null;
    state: string | null;
    county_fips: string | null;
    total_acres: number | null;
    goals: FarmGoals | null;
  };
  fields: Array<{
    id: string | null;
    name: string | null;
    acres: number | null;
    crop_type: string | null;
    practices: string[];
  }>;
  eqip: CreditReportProgram;
  vcm: CreditReportProgram;
}

// ── Credits — UI view models (see adapters.ts) ───────────────────────────────

export interface VcmPracticeEstimate {
  practice_code: string;
  practice_name: string;
  rate_credits_per_acre: number;
  estimated_credits: number;
}

export interface VcmFieldEstimate {
  field_id: string;
  field_name: string;
  acres: number;
  practices: VcmPracticeEstimate[];
  field_total_credits: number;
}

/** VCM estimate built from GET /credits/report (RegenAI estimate, not a registry protocol). */
export interface VcmEstimate {
  estimated_total_credits: number;
  fields: VcmFieldEstimate[];
}

// ── Documents (DocumentResponse) ──────────────────────────────────────────────

export type DocumentType = "soil_report" | "field_photo" | "compliance";

export interface Document {
  id: string;
  farm_id: string;
  user_id: string;
  doc_type: DocumentType;
  file_name: string;
  storage_path: string;
  size_bytes: number;
  description: string | null;
  created_at: string;
}

export interface DocumentListParams {
  doc_type?: DocumentType;
  limit?: number; // 1-200, default 50
  offset?: number;
}

// ── CSP Navigator — backend response models ───────────────────────────────────

/** CSPApplicationStatus. "act_now" = eligible AND meets the state ranking threshold. */
export type CSPEligibilityStatus =
  | "eligible"
  | "not_eligible"
  | "act_now"
  | "pending_review";

/** CSPResourceConcern. concern_id is lowercase, e.g. "soil_health". */
export interface CSPResourceConcern {
  concern_id: string;
  name: string;
  category: string;
  practices_addressing: string[];
  meets_threshold: boolean;
  points_earned: number;
  points_possible: number;
}

/** CSPEligibilityResponse — GET /csp/eligibility?farm_id= */
export interface CSPEligibilityResponse {
  farm_id: string;
  status: CSPEligibilityStatus;
  is_eligible: boolean;
  resource_concerns_meeting_threshold: number;
  /** Concerns that must meet the stewardship threshold (backend program_rules). */
  min_concerns_required: number;
  /** Further concerns the applicant must commit to meet by contract end (backend program_rules). */
  additional_concerns_required: number;
  /** CSP contract length in years (backend program_rules). */
  contract_years: number;
  resource_concerns_detail: CSPResourceConcern[];
  cart_score: number; // 0-100 points
  /**
   * Estimated state ranking threshold, or null when no sourced threshold
   * exists for the farm's state. Null means NRCS decides ranking and the UI
   * must not print a number or a gap.
   */
  state_ranking_threshold: number | null;
  /** Null when the state has no published threshold to compare against. */
  meets_ranking_threshold: boolean | null;
  eligibility_notes: string;
  recommended_enhancements: string[]; // enhancement codes that would close gaps
  evaluated_at: string;
}

/** CSPScoreBreakdown — GET /csp/score?farm_id= */
export interface CSPScoreBreakdown {
  farm_id: string;
  total_points: number;
  max_possible_points: number;
  /** Null when the farm's state has no published ranking threshold. */
  state_ranking_threshold: number | null;
  /** Null when there is no threshold to compare against. */
  meets_ranking_threshold: boolean | null;
  /** Null when there is no threshold, so no gap can be calculated. */
  gap_to_threshold: number | null;
  resource_concern_scores: CSPResourceConcern[];
  component_scores: Record<string, number>;
  avg_som_pct: number | null;
  som_tier: string;
  evaluated_at: string;
}

export interface CSPPaymentFieldBreakdown {
  field_id: string;
  field_name: string;
  acres: number;
  eap_annual: number;
  activity_payment_annual: number;
  total_annual: number;
}

/** Contract limit applied to a CSP estimate (FY2026 rules, NRCS NB 440-26-2). */
export interface CSPContractLimit {
  amount: number;
  label: string; // e.g. "$300,000 contract limit (FY2026+)"
  rule_key: string;
  applies_to: "individual_or_entity" | "joint_operation";
  contract_fiscal_year: number;
  rules_period: "FY2026+" | "pre-FY2026";
  as_of: string; // ISO date
  source_url: string | null;
  source_title: string | null;
}

/** Rule citation block returned by CSP payment/enhancement endpoints. */
export interface CSPRulesMetadata {
  program: string;
  as_of: string; // ISO date
  source_title: string;
  source_url: string;
  contract_limit: CSPContractLimit;
  annual_payment_limit: number | null; // null = no annual payment limit
  annual_payment_limit_note: string;
  existing_activity_payment: {
    amount: number;
    unit: string;
    label: string; // e.g. "EAP $4,000/contract/yr"
    note: string;
    as_of: string;
    source_url: string | null;
  };
  contract_years: number;
  activity_rates: {
    status: string; // "estimate"
    basis: string;
    as_of: string;
    source_url: string | null;
    source_title: string;
  };
  activity_model_note: string;
}

/** One conservation activity in a payment estimate (keyed by practice standard). */
export interface CSPActivityPaymentItem {
  code: string; // e.g. "340", "328-RCCR"
  practice_standard_code: string; // e.g. "340"
  name: string;
  higher_payment: boolean;
  higher_payment_category: string | null;
  estimated_rate_per_acre: number;
  rate_is_estimate: boolean;
  acres: number;
  estimated_annual_payment: number;
}

/** CSPPaymentEstimate (backend) — GET /csp/payments?farm_id= */
export interface CSPPaymentEstimateResponse {
  farm_id: string;
  eligible_acres: number;
  resource_concerns_addressed: number;
  eap_annual: number; // fixed per contract per year
  activity_payment_annual: number;
  activities_included: CSPActivityPaymentItem[];
  total_annual_payment: number;
  total_5year_payment: number;
  contract_years: number;
  contract_fiscal_year: number;
  joint_operation: boolean;
  contract_limit: CSPContractLimit;
  annual_payment_limit: number | null;
  payment_capped: boolean; // contract total capped at contract limit
  field_breakdown: CSPPaymentFieldBreakdown[];
  state: string;
  rules: CSPRulesMetadata;
  estimated_at: string;
}

/** CSPEnhancementActivity — items of GET /csp/enhancements?farm_id= */
export interface CSPEnhancementActivity {
  code: string; // e.g. "340", "328-RCCR"
  practice_standard_code: string;
  name: string;
  category: string;
  land_use: string;
  description: string;
  implementation_notes: string;
  estimated_rate_per_acre: number;
  rate_is_estimate: boolean;
  rate_basis: string;
  estimated_annual_payment: number;
  applicable_acres: number;
  resource_concerns_addressed: string[];
  priority_score: number;
  higher_payment: boolean;
  higher_payment_category: string | null;
}

export interface CSPEnhancementsResponse {
  farm_id: string;
  enhancements: CSPEnhancementActivity[];
  rules?: CSPRulesMetadata;
}

/** POST /csp/evaluate?farm_id= */
export interface CSPEvaluateResponse {
  status: string; // "evaluation_complete"
  farm_id: string;
  eligibility: Pick<
    CSPEligibilityResponse,
    | "status"
    | "is_eligible"
    | "resource_concerns_meeting_threshold"
    | "cart_score"
    | "meets_ranking_threshold"
    | "eligibility_notes"
    | "recommended_enhancements"
  >;
  score: Pick<
    CSPScoreBreakdown,
    | "total_points"
    | "max_possible_points"
    | "state_ranking_threshold"
    | "gap_to_threshold"
    | "component_scores"
  >;
  payments: Pick<
    CSPPaymentEstimateResponse,
    | "total_annual_payment"
    | "total_5year_payment"
    | "eap_annual"
    | "activity_payment_annual"
    | "payment_capped"
    | "contract_limit"
    | "annual_payment_limit"
    | "rules"
  >;
  evaluated_at: string;
}

/** confirmed = published date; expected = recurring, dates not out; not_announced = no cutoff yet */
export type ProgramDeadlineStatus = "confirmed" | "expected" | "not_announced";

/** urgent <= 14 days, soon <= 45 days, later beyond that */
export type DeadlineUrgency = "urgent" | "soon" | "later";

export interface CSPDeadlineEntry {
  id: string;
  program: string; // e.g. "EQIP and CSP", "SDRP"
  state: string; // two-letter code or "ALL"
  title: string;
  description: string;
  status: ProgramDeadlineStatus;
  source_url: string;
  as_of: string; // ISO date the entry was last verified
  period_label: string; // e.g. "FY2027 funding"
  fiscal_year: number | null;
  deadline_date: string | null; // ISO date; null unless confirmed
  notes: string | null;
  days_remaining: number | null;
  urgency: DeadlineUrgency | null;
  /** Legacy alias of deadline_date. */
  cutoff_date: string | null;
  /** Legacy alias of period_label. */
  signup_period: string | null;
}

/** GET /csp/deadlines[?state=] — upcoming only, soonest first */
export interface CSPDeadlinesResponse {
  state: string; // two-letter code or "NATIONAL"
  today: string; // ISO date used for days_remaining
  deadlines: CSPDeadlineEntry[];
  advisory: string;
  program_url: string;
}

// ── CSP Navigator — UI view models (see adapters.ts) ─────────────────────────

/** Urgency of a dated deadline, or "undated" for expected / not announced. */
export type CSPDeadlineSeverity = DeadlineUrgency | "undated";

export interface CSPResourceConcernResult {
  code: string; // uppercase concern id, e.g. "SOIL_HEALTH"
  name: string;
  currently_met: boolean;
  threshold_met: boolean;
  score: number; // 0-100
  points_earned: number;
  evidence: string[];
  /** Gap-closing activities from the API for an unmet concern; empty when met. */
  suggested_activities: CSPSuggestedActivity[];
}

/** An activity the API recommends to close a stewardship gap. */
export interface CSPSuggestedActivity {
  code: string;
  practice_standard_code: string;
  name: string;
}

export interface CSPEligibility {
  farm_id: string;
  fiscal_year: number;
  eligibility_status: CSPEligibilityStatus;
  is_eligible: boolean | null;
  rc_count_above_threshold: number;
  /**
   * Concerns that must meet the stewardship threshold to be eligible, from the
   * API. Undefined if the response omits it: show copy without a number.
   */
  min_concerns_required?: number;
  /** True when the farm meets the minimum-concerns requirement. */
  meets_min_concerns: boolean;
  /** Further concerns to commit to meeting by contract end, from the API. Undefined if omitted. */
  additional_concerns_required?: number;
  /** Contract length in years, from the API. Undefined if omitted. */
  contract_years?: number;
  rc_count_will_meet: number;
  resource_concerns_met: CSPResourceConcernResult[];
  /** Enhancements the farmer has actually selected (backend has no selection yet). */
  active_enhancement_codes: string[];
  /** Enhancement codes the backend recommends to close stewardship gaps. */
  recommended_enhancement_codes?: string[];
  qualifying_eqip_codes: string[];
  stewardship_score: number;
  estimated_ranking_score: number;
  act_now_eligible: boolean;
  act_now_threshold: number | null;
  estimated_annual_payment: number | null;
  estimated_5yr_payment: number | null;
  missing_requirements: string[];
  ineligibility_reasons: string[];
  upcoming_deadlines: CSPDeadline[];
  notes: string;
  evaluated_at: string;
  from_cache: boolean;
}

export interface CSPScore {
  farm_id: string;
  stewardship_score: number;
  /** Backend status; the only qualitative label shown next to the score. */
  eligibility_status: CSPEligibilityStatus;
  /** Estimated state ranking threshold from the API (unverified estimate); null if unknown. */
  ranking_threshold?: number | null;
  score_breakdown: Array<{
    resource_concern: string;
    code: string;
    points_earned: number;
    max_points: number;
    score: number;
    currently_met: boolean;
  }>;
  improvement_recommendations: string[];
  from_cache: boolean;
  evaluated_at: string;
}

export interface CSPActivityBreakdownItem {
  code: string;
  practice_standard_code: string;
  name: string;
  higher_payment: boolean;
  higher_payment_category: string | null;
  rate_per_acre: number;
  rate_is_estimate: boolean;
  acres: number;
  payment: number;
}

/** Short rule citation rendered as "Rules as of <date> · source". */
export interface CSPRuleCitation {
  as_of: string; // ISO date
  source_title: string;
  source_url: string | null;
}

/** Rule notes from the backend rules block (program_rules.py), shown verbatim. */
export interface CSPRuleNotes {
  existing_activity_payment: string;
  annual_payment_limit: string;
  activity_model: string;
  activity_rate_basis: string;
}

export interface CSPPaymentEstimate {
  farm_id: string;
  state_code: string;
  fiscal_year: number;
  total_cropland_acres: number;
  rc_count_above_threshold: number;
  eap_annual: number;
  activity_payment_annual: number;
  annual_total: number;
  contract_5yr_total: number;
  per_acre_annual: number;
  contract_years: number;
  contract_limit_amount: number;
  contract_limit_label: string; // e.g. "$300,000 contract limit (FY2026+)"
  contract_limit_applied: boolean;
  eap_label: string; // e.g. "EAP $4,000/contract/yr"
  annual_payment_limit: number | null; // null = no annual payment limit
  activity_breakdown: CSPActivityBreakdownItem[];
  activity_rate_basis: string;
  rules: CSPRuleCitation;
  rule_notes: CSPRuleNotes;
  disclaimer: string;
}

export interface CSPEnhancement {
  id: string;
  code: string;
  practice_standard_code: string;
  name: string;
  category: string;
  land_use: string;
  description: string;
  implementation_notes: string;
  base_payment_rate: number;
  payment_unit: string;
  rate_is_estimate: boolean;
  rate_basis: string;
  higher_payment: boolean;
  higher_payment_category: string | null;
  point_weight: number;
  resource_concern_code: string;
  // Farm-level fields (when fetched per-farm)
  status?: "considering" | "committed" | "active" | "removed";
  acres_enrolled?: number;
  estimated_payment?: number;
}

export interface CSPDeadline {
  deadline_id: string;
  state_code: string; // two-letter code or "ALL"
  program: string;
  cutoff_date: string | null; // ISO date; null when not announced / expected
  cutoff_name: string;
  days_until: number | null;
  alert_severity: CSPDeadlineSeverity;
  status: ProgramDeadlineStatus;
  description: string;
  notes: string | null;
  source_url: string;
  as_of: string; // ISO date
}

export interface CSPChecklistItem {
  item_id: string;
  label: string;
  completed: boolean;
  detail: string;
  action?: string;
}

export interface CSPChecklist {
  farm_id: string;
  checklist: CSPChecklistItem[];
}

// ── Field Activity Log — backend models ───────────────────────────────────────

export type ActivityType =
  | "plant"
  | "spray"
  | "fertilize"
  | "scout"
  | "harvest"
  | "tillage"
  | "cover_crop"
  | "other";

export type ScoutingSeverity = "none" | "low" | "moderate" | "high" | "critical";

/** ActivityResponse — a flat field_activities row. */
export interface ActivityRecord {
  id: string;
  field_id: string;
  activity_type: ActivityType;
  activity_date: string; // ISO date

  seed_variety: string | null;
  seeding_rate: number | null;
  seed_treatment: string | null;

  product_name: string | null;
  rate_per_acre: number | null;
  rate_unit: string | null;
  target_pest: string | null;
  restricted_use: boolean;
  applicator_name: string | null;
  applicator_license: string | null;

  yield_bu_acre: number | null;
  moisture_pct: number | null;
  crop_year: number | null;

  pest_disease_found: string | null;
  severity: ScoutingSeverity | null;

  tillage_depth_in: number | null;
  cover_crop_species: string | null;

  notes: string | null;
  operator: string | null;
  equipment_used: string | null;
  cost_per_acre: number | null;
  acres_applied: number | null;

  created_at: string;
  updated_at: string;

  /** Non-fatal notices from POST (e.g. harvest saved but yield history not synced). */
  warnings?: string[];
}

type ActivityRecordOptionalFields = Omit<
  ActivityRecord,
  "id" | "field_id" | "activity_type" | "activity_date" | "created_at" | "updated_at" | "warnings"
>;

/** Body for POST /activities (ActivityCreate). */
export type ActivityCreateInput = {
  field_id: string;
  activity_type: ActivityType;
  activity_date: string;
} & Partial<ActivityRecordOptionalFields>;

/** Body for PATCH /activities/{id} (ActivityUpdate). */
export type ActivityUpdateInput = Partial<Omit<ActivityCreateInput, "field_id">>;

/** Query params for GET /activities (field_id is passed separately). */
export interface ActivityListParams {
  activity_type?: ActivityType;
  start_date?: string; // ISO date, inclusive
  end_date?: string; // ISO date, inclusive
  limit?: number; // 1-200, default 50
  offset?: number;
}

/** ActivityListResponse — GET /activities?field_id= */
export interface ActivityListResponse {
  activities: ActivityRecord[];
  total_count: number;
}

/** GET /activities/summary?farm_id= */
export interface ActivitySummaryResponse {
  farm_id: string;
  total_activities: number;
  count_by_type: Partial<Record<ActivityType, number>>;
  last_activity_per_field: Array<{
    field_id: string;
    field_name: string;
    last_activity_date: string;
  }>;
}

/** YieldHistoryResponse — items of GET /yield-history?field_id= */
export interface YieldHistoryRecord {
  id: string;
  field_id: string;
  crop_year: number;
  crop_type: string;
  yield_bu_acre: number;
  moisture_pct: number | null;
  acres_harvested: number | null;
  notes: string | null;
  created_at: string;
}

/** Body for POST /yield-history (YieldHistoryCreate). */
export interface YieldHistoryCreateInput {
  field_id: string;
  crop_year: number;
  crop_type: string;
  yield_bu_acre: number;
  moisture_pct?: number | null;
  acres_harvested?: number | null;
  notes?: string | null;
}

/** APHResponse — GET /yield-history/aph?field_id= (HTTP 422 if < 4 years). */
export interface APHResponse {
  field_id: string;
  aph_yield: number;
  years_used: number;
  year_range: string;
  records: YieldHistoryRecord[];
}

// ── Field Activity Log — UI view models (see adapters.ts) ────────────────────

// Detail fields are optional: they mirror only what field_activities stores, and
// a value the farmer did not record is left undefined (never shown as 0 or "").
// Form-only extras (row spacing, EPA reg #, wind, N-P-K split, ...) are kept in
// `notes` by buildActivityCreatePayload.

export interface PlantingDetails {
  variety?: string;
  seeding_rate_kac?: number; // thousands of seeds per acre
  seed_treatment?: string;
}

export interface SprayDetails {
  product_name?: string;
  rate?: number;
  rate_unit?: string; // e.g. "oz/ac"
  target_pest?: string;
  restricted_use: boolean;
  applicator_name?: string;
  applicator_cert_number?: string;
}

export interface FertilizeDetails {
  product_name?: string;
  rate?: number;
  rate_unit?: string; // e.g. "lbs N/ac"
}

export interface ScoutDetails {
  pest_name?: string;
  severity?: ScoutingSeverity;
}

export interface HarvestDetails {
  yield_bu_ac?: number;
  moisture_pct?: number;
  crop_year?: number;
}

export interface TillageDetails {
  depth_in?: number;
}

export interface CoverCropDetails {
  species?: string;
}

export type ActivityDetails =
  | PlantingDetails
  | SprayDetails
  | FertilizeDetails
  | ScoutDetails
  | HarvestDetails
  | TillageDetails
  | CoverCropDetails
  | Record<string, never>;

export interface FieldActivity {
  id: string;
  field_id: string;
  farm_id: string;
  activity_type: ActivityType;
  activity_date: string; // ISO date string
  acres: number;
  operator?: string;
  equipment?: string;
  cost_per_acre?: number;
  notes?: string;
  details: ActivityDetails;
  created_at: string;
}

export interface YieldRecord {
  id: string;
  field_id: string;
  farm_id: string;
  crop_year: number;
  crop_type: string;
  yield_bu_ac: number;
  moisture_pct: number | null;
  acres: number | null;
  created_at: string;
}

export interface APHResult {
  field_id: string;
  years_used: number;
  average_yield_bu_ac: number;
  trend_direction: "up" | "down" | "flat";
  trend_pct: number; // % change from oldest to newest year
  records: YieldRecord[];
}
