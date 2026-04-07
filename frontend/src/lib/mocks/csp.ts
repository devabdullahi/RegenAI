import type {
  CSPEligibility,
  CSPScore,
  CSPPaymentEstimate,
  CSPEnhancement,
  CSPDeadline,
  CSPChecklist,
} from "@/lib/api/types";

// ── Deadlines ─────────────────────────────────────────────────────────────────

export const mockCSPDeadlines: CSPDeadline[] = [
  {
    deadline_id: "dl-1",
    state_code: "IA",
    cutoff_date: "2026-05-09",
    cutoff_name: "FY2026 First Cutoff / ACT NOW Opens",
    is_act_now: true,
    act_now_start: "2026-05-09",
    act_now_end: "2026-07-11",
    days_until: 33,
    alert_severity: "upcoming",
    description:
      "Applications ranked and immediately funded if score meets Iowa's ACT NOW threshold of 60 points.",
  },
  {
    deadline_id: "dl-2",
    state_code: "IA",
    cutoff_date: "2026-11-14",
    cutoff_name: "FY2026 Second Cutoff",
    is_act_now: false,
    act_now_start: null,
    act_now_end: null,
    days_until: 222,
    alert_severity: "upcoming",
    description:
      "Standard ranking cutoff. Applications submitted after this date roll to FY2027.",
  },
];

// ── Resource concerns ─────────────────────────────────────────────────────────

const resourceConcernsMet = [
  {
    code: "SOIL_EROSION",
    name: "Soil Erosion",
    currently_met: true,
    threshold_met: true,
    score: 72,
    points_earned: 13,
    evidence: [
      "No-till on North Quarter (320 acres)",
      "Reduced tillage on South Half (480 acres)",
      "Practice 329 (no-till) acted on 2 fields",
    ],
  },
  {
    code: "SOIL_HEALTH",
    name: "Soil Health and Organic Matter",
    currently_met: true,
    threshold_met: true,
    score: 78,
    points_earned: 17,
    evidence: [
      "Organic matter 3.2% on North Quarter (above 2.5% threshold)",
      "Cover crop (practice 340) acted on South Half",
      "Crop rotation (practice 328) documented",
    ],
  },
  {
    code: "WATER_QUALITY",
    name: "Water Quality",
    currently_met: true,
    threshold_met: true,
    score: 65,
    points_earned: 13,
    evidence: [
      "Nutrient management plan on file",
      "Practice 590 (nutrient management) acted",
    ],
  },
  {
    code: "WATER_QUANTITY",
    name: "Water Quantity",
    currently_met: false,
    threshold_met: false,
    score: 30,
    points_earned: 2,
    evidence: [
      "No irrigation practices documented",
      "County average precipitation: 34 inches/year (above 28-inch threshold — partial credit)",
    ],
  },
  {
    code: "AIR_QUALITY",
    name: "Air Quality",
    currently_met: false,
    threshold_met: false,
    score: 45,
    points_earned: 5,
    evidence: [
      "Cover crop (340) active — reduces N2O emissions",
      "Missing formal crop rotation documentation for practice 328",
    ],
  },
  {
    code: "PLANT_CONDITION",
    name: "Plant Condition",
    currently_met: false,
    threshold_met: false,
    score: 35,
    points_earned: 4,
    evidence: [
      "Two crop types across operation (corn and soybeans)",
      "No forage or native species planting on record",
    ],
  },
  {
    code: "ANIMALS",
    name: "Animals",
    currently_met: false,
    threshold_met: false,
    score: 10,
    points_earned: 1,
    evidence: ["No livestock present — this category not applicable to operation"],
  },
  {
    code: "ENERGY",
    name: "Energy",
    currently_met: false,
    threshold_met: false,
    score: 20,
    points_earned: 1,
    evidence: ["No energy efficiency practices documented"],
  },
];

// ── CSP Eligibility ────────────────────────────────────────────────────────────

export const mockCSPEligibility: CSPEligibility = {
  farm_id: "farm-1",
  fiscal_year: 2026,
  eligibility_status: "eligible",
  is_eligible: true,
  rc_count_above_threshold: 3,
  rc_count_will_meet: 1,
  resource_concerns_met: resourceConcernsMet,
  active_enhancement_codes: ["E328A", "E590A", "E340A"],
  qualifying_eqip_codes: ["328", "329", "340", "590"],
  stewardship_score: 62,
  estimated_ranking_score: 67,
  act_now_eligible: true,
  act_now_threshold: 60,
  estimated_annual_payment: 9175,
  estimated_5yr_payment: 45875,
  application_readiness_pct: 75,
  missing_requirements: [
    "Written nutrient management plan not uploaded in Documents",
    "Select at least one enhancement activity to commit to",
  ],
  ineligibility_reasons: [],
  upcoming_deadlines: mockCSPDeadlines,
  notes:
    "Farm meets stewardship threshold on 3 of 8 resource concerns. Score of 67 places this farm in the competitive tier for Iowa — above the ACT NOW threshold of 60.",
  evaluated_at: "2026-04-06T14:23:11Z",
  from_cache: false,
};

// ── CSP Score ─────────────────────────────────────────────────────────────────

export const mockCSPScore: CSPScore = {
  farm_id: "farm-1",
  stewardship_score: 62,
  score_label: "Good",
  percentile_estimate: "competitive",
  base_score: 57,
  bonus_points: 5,
  score_breakdown: [
    {
      resource_concern: "Soil Health and Organic Matter",
      code: "SOIL_HEALTH",
      points_earned: 17,
      max_points: 22,
      score: 78,
      currently_met: true,
    },
    {
      resource_concern: "Water Quality",
      code: "WATER_QUALITY",
      points_earned: 13,
      max_points: 20,
      score: 65,
      currently_met: true,
    },
    {
      resource_concern: "Soil Erosion",
      code: "SOIL_EROSION",
      points_earned: 13,
      max_points: 18,
      score: 72,
      currently_met: true,
    },
    {
      resource_concern: "Air Quality",
      code: "AIR_QUALITY",
      points_earned: 5,
      max_points: 12,
      score: 45,
      currently_met: false,
    },
    {
      resource_concern: "Plant Condition",
      code: "PLANT_CONDITION",
      points_earned: 4,
      max_points: 10,
      score: 35,
      currently_met: false,
    },
    {
      resource_concern: "Water Quantity",
      code: "WATER_QUANTITY",
      points_earned: 2,
      max_points: 8,
      score: 30,
      currently_met: false,
    },
    {
      resource_concern: "Energy",
      code: "ENERGY",
      points_earned: 1,
      max_points: 5,
      score: 20,
      currently_met: false,
    },
    {
      resource_concern: "Animals",
      code: "ANIMALS",
      points_earned: 1,
      max_points: 5,
      score: 10,
      currently_met: false,
    },
  ],
  improvement_recommendations: [
    "Add a formal crop rotation plan (practice 328) across all fields to improve Air Quality score by up to 7 points.",
    "Upload your written Nutrient Management Plan to strengthen the Water Quality score and unlock higher payment rates.",
    "Plant a diverse cover crop mix with legumes on North Quarter to push Soil Health score toward the maximum.",
  ],
  from_cache: true,
  evaluated_at: "2026-04-06T14:23:11Z",
};

// ── CSP Payment Estimate ──────────────────────────────────────────────────────

export const mockCSPPayment: CSPPaymentEstimate = {
  farm_id: "farm-1",
  state_code: "IA",
  fiscal_year: 2026,
  total_cropland_acres: 800,
  rc_count_above_threshold: 3,
  eap_annual: 6375,
  enap_annual: 2800,
  raw_annual: 9175,
  capped_annual: 9175,
  contract_5yr_total: 45875,
  per_acre_annual: 11.47,
  min_applied: false,
  max_applied: false,
  enhancement_breakdown: [
    {
      code: "E328A",
      name: "Resource conserving crop rotation",
      base_rate: 2.5,
      acres: 800,
      is_bundle: false,
      multiplier: 1.0,
      payment: 2000,
    },
    {
      code: "E590A",
      name: "Improving nutrient uptake efficiency",
      base_rate: 0.8,
      acres: 800,
      is_bundle: true,
      multiplier: 1.15,
      payment: 736,
    },
    {
      code: "E340A",
      name: "Multi-species cover crop",
      base_rate: 0.08,
      acres: 800,
      is_bundle: true,
      multiplier: 1.15,
      payment: 64,
    },
  ],
  disclaimer:
    "This is an estimate based on NRCS payment schedules and may differ from the final payment determined by your local NRCS office. Contact your NRCS service center to get an official payment estimate before applying.",
};

// ── Reference Enhancements ────────────────────────────────────────────────────

export const mockCSPEnhancements: CSPEnhancement[] = [
  {
    id: "enh-1",
    code: "E328A",
    name: "Resource conserving crop rotation",
    category: "Soil Health and Organic Matter",
    land_use: "cropland",
    description:
      "Implement a resource-conserving crop rotation that includes at least one grass or legume species.",
    implementation_notes:
      "Corn-soy counts as a rotation. Adding a small grain or hay crop earns higher points.",
    base_payment_rate: 2.5,
    payment_unit: "acre",
    is_bundle_eligible: true,
    bundle_code: "B000CPL24",
    eqip_practice_code: "328",
    point_weight: 15,
    resource_concern_code: "SOIL_HEALTH",
    status: "active",
    acres_enrolled: 800,
    estimated_payment: 2000,
  },
  {
    id: "enh-2",
    code: "E590A",
    name: "Improving nutrient uptake efficiency",
    category: "Water Quality",
    land_use: "cropland",
    description:
      "Implement a written nutrient management plan that applies fertilizer based on soil tests and crop needs.",
    implementation_notes:
      "Requires a current written plan. Variable-rate application earns additional points.",
    base_payment_rate: 0.8,
    payment_unit: "acre",
    is_bundle_eligible: true,
    bundle_code: "B000CPL24",
    eqip_practice_code: "590",
    point_weight: 12,
    resource_concern_code: "WATER_QUALITY",
    status: "committed",
    acres_enrolled: 800,
    estimated_payment: 736,
  },
  {
    id: "enh-3",
    code: "E340A",
    name: "Multi-species cover crop",
    category: "Soil Health and Organic Matter",
    land_use: "cropland",
    description:
      "Plant a cover crop mix with at least 2 species, including one legume, after cash crop harvest.",
    implementation_notes:
      "Cereal rye + hairy vetch is a common low-cost mix. Seeding rate and termination timing matter.",
    base_payment_rate: 0.08,
    payment_unit: "acre",
    is_bundle_eligible: true,
    bundle_code: "B000CPL24",
    eqip_practice_code: "340",
    point_weight: 10,
    resource_concern_code: "SOIL_HEALTH",
    status: "active",
    acres_enrolled: 800,
    estimated_payment: 64,
  },
  {
    id: "enh-4",
    code: "E345A",
    name: "Residue and tillage management (no-till)",
    category: "Soil Erosion",
    land_use: "cropland",
    description:
      "Eliminate primary tillage across the entire operation and maintain crop residue on the soil surface.",
    implementation_notes:
      "Must apply to at least 50% of cropland acres to qualify. Equipment modifications may be needed.",
    base_payment_rate: 1.2,
    payment_unit: "acre",
    is_bundle_eligible: false,
    bundle_code: null,
    eqip_practice_code: "345",
    point_weight: 14,
    resource_concern_code: "SOIL_EROSION",
    status: "considering",
    acres_enrolled: undefined,
    estimated_payment: undefined,
  },
  {
    id: "enh-5",
    code: "E412A",
    name: "Grassed waterway installation",
    category: "Water Quality",
    land_use: "cropland",
    description:
      "Establish grass-lined channels to safely carry runoff water through the field without causing erosion.",
    implementation_notes:
      "NRCS will help design and engineer the waterway. Installation is cost-shared under EQIP.",
    base_payment_rate: 3.5,
    payment_unit: "foot",
    is_bundle_eligible: false,
    bundle_code: null,
    eqip_practice_code: "412",
    point_weight: 8,
    resource_concern_code: "WATER_QUALITY",
    status: "considering",
    acres_enrolled: undefined,
    estimated_payment: undefined,
  },
];

// ── Application Checklist ─────────────────────────────────────────────────────

export const mockCSPChecklist: CSPChecklist = {
  farm_id: "farm-1",
  overall_readiness_pct: 75,
  checklist: [
    {
      item_id: "has_fields",
      label: "Farm has registered fields",
      completed: true,
      detail: "2 fields registered totaling 800 acres",
    },
    {
      item_id: "has_soil_data",
      label: "Soil data on file for all fields",
      completed: true,
      detail: "SSURGO soil data on file for both fields",
    },
    {
      item_id: "rc_threshold_2",
      label: "Meets conservation threshold on 2 or more areas",
      completed: true,
      detail:
        "3 of 8 resource concerns currently above the stewardship threshold",
    },
    {
      item_id: "nutrient_mgmt_plan",
      label: "Written Nutrient Management Plan",
      completed: false,
      detail: "No nutrient management plan document uploaded yet",
      action:
        "Upload your nutrient management plan PDF in the Documents section",
    },
    {
      item_id: "commitment_selected",
      label: "Committed to improving at least 1 more conservation area",
      completed: false,
      detail:
        "Select an enhancement activity to commit to meeting one additional resource concern",
      action: "Choose an enhancement below to add to your committed list",
    },
    {
      item_id: "enhancements_selected",
      label: "Enhancement activities selected",
      completed: true,
      detail: "3 enhancements selected: E328A, E590A, E340A",
    },
    {
      item_id: "contact_nrcs",
      label: "Contact your local NRCS office to submit your application",
      completed: false,
      detail:
        "Final step: your local NRCS conservation planner will schedule a site visit and finalize your contract",
      action:
        "Find your local office at farmers.gov/contact-your-local-service-center",
    },
  ],
};
