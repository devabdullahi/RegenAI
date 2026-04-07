// DB Schema v1 — matches backend/Supabase tables

export interface User {
  id: string;
  email: string;
  created_at: string;
  role: "farmer" | "admin";
}

export interface Farm {
  id: string;
  user_id: string;
  name: string;
  state: string;
  county_fips: string;
  total_acres: number;
  goals?: "cost_savings" | "carbon_credits" | "both";
  created_at: string;
}

export interface Field {
  id: string;
  farm_id: string;
  name: string;
  acres: number;
  crop_type: string;
  boundary_geojson?: Record<string, unknown> | null;
  boundary_description?: string; // "Section 14, Township 5N, Range 3W"
  practices?: string[];
  created_at: string;
}

export interface SoilProfile {
  id: string;
  field_id: string;
  ssurgo_map_unit: string;
  texture: string;
  ph: number;
  organic_matter_pct: number;
  source: "ssurgo" | "soilgrids" | "manual";
  fetched_at: string;
}

export interface WeatherData {
  id: string;
  field_id: string;
  date: string;
  temp_high: number;
  temp_low: number;
  precip_mm: number;
  soil_temp: number;
  fetched_at: string;
}

export interface Recommendation {
  id: string;
  field_id: string;
  created_at: string;
  practice_code: string;
  title: string;
  rationale: string;
  priority: "high" | "medium" | "low";
  status: "pending" | "acted" | "dismissed";
}

export interface CreditEligibility {
  id: string;
  farm_id: string;
  program: "EQIP" | "VCM";
  status: "eligible" | "not_eligible" | "pending_review";
  practices_documented: string[];
  notes: string;
  updated_at: string;
}

export interface Document {
  id: string;
  farm_id: string;
  storage_path: string;
  doc_type: "soil_report" | "field_photo" | "compliance" | "other";
  uploaded_at: string;
}

// ── CSP Conservation Stewardship Program ──────────────────────────────────────

export type CSPEligibilityStatus =
  | "eligible"
  | "not_eligible"
  | "conditional"
  | "not_evaluated";

export type CSPDeadlineSeverity = "urgent" | "warning" | "upcoming" | "passed";

export interface CSPResourceConcernResult {
  code: string;
  name: string;
  currently_met: boolean;
  threshold_met: boolean;
  score: number; // 0-100
  points_earned: number;
  evidence: string[];
}

export interface CSPEligibility {
  farm_id: string;
  fiscal_year: number;
  eligibility_status: CSPEligibilityStatus;
  is_eligible: boolean | null;
  rc_count_above_threshold: number;
  rc_count_will_meet: number;
  resource_concerns_met: CSPResourceConcernResult[];
  active_enhancement_codes: string[];
  qualifying_eqip_codes: string[];
  stewardship_score: number;
  estimated_ranking_score: number;
  act_now_eligible: boolean;
  act_now_threshold: number | null;
  estimated_annual_payment: number | null;
  estimated_5yr_payment: number | null;
  application_readiness_pct: number;
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
  score_label: "Excellent" | "Good" | "Fair" | "Needs Work";
  percentile_estimate: "top 10%" | "top 25%" | "competitive" | "below average";
  base_score: number;
  bonus_points: number;
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

export interface CSPEnhancementBreakdownItem {
  code: string;
  name: string;
  base_rate: number;
  acres: number;
  is_bundle: boolean;
  multiplier: number;
  payment: number;
}

export interface CSPPaymentEstimate {
  farm_id: string;
  state_code: string;
  fiscal_year: number;
  total_cropland_acres: number;
  rc_count_above_threshold: number;
  eap_annual: number;
  enap_annual: number;
  raw_annual: number;
  capped_annual: number;
  contract_5yr_total: number;
  per_acre_annual: number;
  min_applied: boolean;
  max_applied: boolean;
  enhancement_breakdown: CSPEnhancementBreakdownItem[];
  disclaimer: string;
}

export interface CSPEnhancement {
  id: string;
  code: string;
  name: string;
  category: string;
  land_use: string;
  description: string;
  implementation_notes: string;
  base_payment_rate: number;
  payment_unit: string;
  is_bundle_eligible: boolean;
  bundle_code: string | null;
  eqip_practice_code: string | null;
  point_weight: number;
  resource_concern_code: string;
  // Farm-level fields (when fetched per-farm)
  status?: "considering" | "committed" | "active" | "removed";
  acres_enrolled?: number;
  estimated_payment?: number;
}

export interface CSPDeadline {
  deadline_id: string;
  state_code: string;
  cutoff_date: string; // ISO date
  cutoff_name: string;
  is_act_now: boolean;
  act_now_start: string | null;
  act_now_end: string | null;
  days_until: number;
  alert_severity: CSPDeadlineSeverity;
  description: string;
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
  overall_readiness_pct: number;
  checklist: CSPChecklistItem[];
}

// ── Field Activity Log ────────────────────────────────────────────────────────

export type ActivityType =
  | "plant"
  | "spray"
  | "fertilize"
  | "scout"
  | "harvest";

export type ScoutingSeverity = "none" | "low" | "medium" | "high" | "critical";

export interface PlantingDetails {
  variety: string;
  seeding_rate_kac: number; // thousands of seeds per acre
  row_spacing_in: number;
  depth_in: number;
}

export interface SprayDetails {
  product_name: string;
  epa_reg_number: string;
  rate_oz_ac: number;
  target_pest: string;
  wind_mph: number;
  temp_f: number;
  restricted_use: boolean;
  applicator_name?: string;
  applicator_cert_number?: string;
}

export interface FertilizeDetails {
  product_name: string;
  n_lbs_ac: number;
  p_lbs_ac: number;
  k_lbs_ac: number;
  method: "broadcast" | "sidedress" | "inject" | "foliar";
}

export interface ScoutDetails {
  pest_type: "insect" | "disease" | "weed" | "other";
  pest_name: string;
  severity: ScoutingSeverity;
  threshold_exceeded: boolean;
  action_taken?: string;
}

export interface HarvestDetails {
  yield_bu_ac: number;
  moisture_pct: number;
  test_weight_lbs_bu: number;
  elevator_ticket?: string;
}

export type ActivityDetails =
  | PlantingDetails
  | SprayDetails
  | FertilizeDetails
  | ScoutDetails
  | HarvestDetails;

export interface FieldActivity {
  id: string;
  field_id: string;
  farm_id: string;
  activity_type: ActivityType;
  activity_date: string; // ISO date string
  acres: number;
  operator: string;
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
  moisture_pct: number;
  acres: number;
  created_at: string;
}

export interface ActivitySummary {
  total_activities: number;
  by_type: Record<ActivityType, number>;
  last_activity_date: string | null;
  recent: FieldActivity[];
}

export interface APHResult {
  field_id: string;
  years_used: number;
  average_yield_bu_ac: number;
  trend_direction: "up" | "down" | "flat";
  trend_pct: number; // % change from oldest to newest year
  records: YieldRecord[];
}
