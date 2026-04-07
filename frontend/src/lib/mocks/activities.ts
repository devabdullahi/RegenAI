import type {
  FieldActivity,
  YieldRecord,
  ActivitySummary,
  APHResult,
} from "@/lib/api/types";

// ── Field Activities — Johnson Family Farm, Iowa ───────────────────────────

export const mockActivities: FieldActivity[] = [
  // Harvest — North Quarter (most recent)
  {
    id: "act-11",
    field_id: "field-1",
    farm_id: "farm-1",
    activity_type: "harvest",
    activity_date: "2025-10-14",
    acres: 320,
    operator: "Dave Johnson",
    equipment: "John Deere S780 Combine",
    cost_per_acre: 42,
    notes: "Good harvest. Elevator ticket #IOW-2025-8812.",
    details: {
      yield_bu_ac: 218,
      moisture_pct: 16.2,
      test_weight_lbs_bu: 56.4,
      elevator_ticket: "IOW-2025-8812",
    },
    created_at: "2025-10-14T17:30:00Z",
  },

  // Scouting — South Half (aphid threshold exceeded)
  {
    id: "act-10",
    field_id: "field-2",
    farm_id: "farm-1",
    activity_type: "scout",
    activity_date: "2025-07-28",
    acres: 480,
    operator: "Maria Johnson",
    notes: "Soybean aphid counts over 250 per plant across 3 of 10 stops.",
    details: {
      pest_type: "insect",
      pest_name: "Soybean Aphid",
      severity: "high",
      threshold_exceeded: true,
      action_taken: "Scheduled foliar insecticide application for 7/30.",
    },
    created_at: "2025-07-28T14:15:00Z",
  },

  // Spray — South Half (restricted use, aphid follow-up)
  {
    id: "act-9",
    field_id: "field-2",
    farm_id: "farm-1",
    activity_type: "spray",
    activity_date: "2025-07-30",
    acres: 480,
    operator: "Dave Johnson",
    equipment: "Apache 1220 Sprayer, 120 ft boom",
    cost_per_acre: 18,
    notes: "Applied per label. RE-entry interval 12 hrs. Posted field.",
    details: {
      product_name: "Warrior II with Zeon Technology",
      epa_reg_number: "100-1070",
      rate_oz_ac: 1.92,
      target_pest: "Soybean Aphid",
      wind_mph: 6,
      temp_f: 81,
      restricted_use: true,
      applicator_name: "Dave Johnson",
      applicator_cert_number: "IA-LIC-44821",
    },
    created_at: "2025-07-30T07:00:00Z",
  },

  // Scouting — North Quarter (corn rootworm, low pressure)
  {
    id: "act-8",
    field_id: "field-1",
    farm_id: "farm-1",
    activity_type: "scout",
    activity_date: "2025-07-10",
    acres: 320,
    operator: "Maria Johnson",
    notes: "Sticky traps checked. Below economic threshold.",
    details: {
      pest_type: "insect",
      pest_name: "Western Corn Rootworm",
      severity: "low",
      threshold_exceeded: false,
      action_taken: "Monitor weekly. No treatment needed.",
    },
    created_at: "2025-07-10T09:45:00Z",
  },

  // Fertilize — North Quarter (sidedress N)
  {
    id: "act-7",
    field_id: "field-1",
    farm_id: "farm-1",
    activity_type: "fertilize",
    activity_date: "2025-06-18",
    acres: 320,
    operator: "Dave Johnson",
    equipment: "Hagie STS16 High Clearance Sprayer",
    cost_per_acre: 38,
    notes: "UAN 32% sidedress. Applied at V4-V5 growth stage.",
    details: {
      product_name: "UAN 32% Solution",
      n_lbs_ac: 80,
      p_lbs_ac: 0,
      k_lbs_ac: 0,
      method: "sidedress",
    },
    created_at: "2025-06-18T06:30:00Z",
  },

  // Spray — North Quarter (herbicide, not restricted use)
  {
    id: "act-6",
    field_id: "field-1",
    farm_id: "farm-1",
    activity_type: "spray",
    activity_date: "2025-06-02",
    acres: 320,
    operator: "Dave Johnson",
    equipment: "Apache 1220 Sprayer, 120 ft boom",
    cost_per_acre: 14,
    notes: "Post-emerge application at V3. Good coverage.",
    details: {
      product_name: "Halex GT",
      epa_reg_number: "100-1489",
      rate_oz_ac: 3.0,
      target_pest: "Waterhemp, Giant Foxtail",
      wind_mph: 8,
      temp_f: 74,
      restricted_use: false,
    },
    created_at: "2025-06-02T08:00:00Z",
  },

  // Fertilize — South Half (spring pre-plant)
  {
    id: "act-5",
    field_id: "field-2",
    farm_id: "farm-1",
    activity_type: "fertilize",
    activity_date: "2025-04-28",
    acres: 480,
    operator: "Dave Johnson",
    equipment: "Montag Dry Fertilizer Spreader",
    cost_per_acre: 55,
    notes: "Blend applied per soil test recs from March. Good conditions.",
    details: {
      product_name: "11-52-0 MAP + 0-0-60 Potash Blend",
      n_lbs_ac: 20,
      p_lbs_ac: 45,
      k_lbs_ac: 60,
      method: "broadcast",
    },
    created_at: "2025-04-28T07:00:00Z",
  },

  // Spray — South Half (pre-emerge herbicide)
  {
    id: "act-4",
    field_id: "field-2",
    farm_id: "farm-1",
    activity_type: "spray",
    activity_date: "2025-05-06",
    acres: 480,
    operator: "Dave Johnson",
    equipment: "Apache 1220 Sprayer, 120 ft boom",
    cost_per_acre: 16,
    notes: "Applied within 3 days of planting. Good soil moisture for activation.",
    details: {
      product_name: "Dual Magnum",
      epa_reg_number: "100-816",
      rate_oz_ac: 16,
      target_pest: "Annual grasses, small-seeded broadleaves",
      wind_mph: 5,
      temp_f: 62,
      restricted_use: false,
    },
    created_at: "2025-05-06T07:30:00Z",
  },

  // Planting — South Half (soybeans)
  {
    id: "act-3",
    field_id: "field-2",
    farm_id: "farm-1",
    activity_type: "plant",
    activity_date: "2025-05-04",
    acres: 480,
    operator: "Dave Johnson",
    equipment: "John Deere 1775NT MaxEmerge 24-row planter",
    cost_per_acre: 22,
    notes: "Ideal planting conditions. Soil temp 54°F at 2 inch depth.",
    details: {
      variety: "Pioneer P39T67X (Xtend)",
      seeding_rate_kac: 140,
      row_spacing_in: 30,
      depth_in: 1.5,
    },
    created_at: "2025-05-04T06:00:00Z",
  },

  // Planting — North Quarter (corn)
  {
    id: "act-2",
    field_id: "field-1",
    farm_id: "farm-1",
    activity_type: "plant",
    activity_date: "2025-04-30",
    acres: 320,
    operator: "Dave Johnson",
    equipment: "John Deere 1775NT MaxEmerge 24-row planter",
    cost_per_acre: 28,
    notes: "Soil temp averaged 50°F. Surface conditions ideal after 3 dry days.",
    details: {
      variety: "DeKalb DKC52-70RIB",
      seeding_rate_kac: 34.5,
      row_spacing_in: 30,
      depth_in: 2.0,
    },
    created_at: "2025-04-30T05:45:00Z",
  },
];

// Sorted newest first (the order the timeline shows)
export const mockActivitiesSorted = [...mockActivities].sort(
  (a, b) =>
    new Date(b.activity_date).getTime() - new Date(a.activity_date).getTime()
);

// ── Yield History — 5 years, both fields ─────────────────────────────────────

export const mockYieldRecords: YieldRecord[] = [
  // North Quarter — Corn
  { id: "yr-1", field_id: "field-1", farm_id: "farm-1", crop_year: 2025, crop_type: "corn", yield_bu_ac: 218, moisture_pct: 16.2, acres: 320, created_at: "2025-10-14T17:30:00Z" },
  { id: "yr-2", field_id: "field-1", farm_id: "farm-1", crop_year: 2024, crop_type: "soybeans", yield_bu_ac: 58, moisture_pct: 12.8, acres: 320, created_at: "2024-10-10T14:00:00Z" },
  { id: "yr-3", field_id: "field-1", farm_id: "farm-1", crop_year: 2023, crop_type: "corn", yield_bu_ac: 201, moisture_pct: 17.5, acres: 320, created_at: "2023-10-12T16:00:00Z" },
  { id: "yr-4", field_id: "field-1", farm_id: "farm-1", crop_year: 2022, crop_type: "soybeans", yield_bu_ac: 52, moisture_pct: 13.1, acres: 320, created_at: "2022-10-18T15:00:00Z" },
  { id: "yr-5", field_id: "field-1", farm_id: "farm-1", crop_year: 2021, crop_type: "corn", yield_bu_ac: 195, moisture_pct: 18.0, acres: 320, created_at: "2021-10-20T14:00:00Z" },

  // South Half — Soybeans
  { id: "yr-6", field_id: "field-2", farm_id: "farm-1", crop_year: 2025, crop_type: "soybeans", yield_bu_ac: 62, moisture_pct: 13.2, acres: 480, created_at: "2025-10-16T17:00:00Z" },
  { id: "yr-7", field_id: "field-2", farm_id: "farm-1", crop_year: 2024, crop_type: "corn", yield_bu_ac: 208, moisture_pct: 15.8, acres: 480, created_at: "2024-10-11T15:00:00Z" },
  { id: "yr-8", field_id: "field-2", farm_id: "farm-1", crop_year: 2023, crop_type: "soybeans", yield_bu_ac: 56, moisture_pct: 12.5, acres: 480, created_at: "2023-10-14T16:00:00Z" },
  { id: "yr-9", field_id: "field-2", farm_id: "farm-1", crop_year: 2022, crop_type: "corn", yield_bu_ac: 196, moisture_pct: 16.4, acres: 480, created_at: "2022-10-20T15:00:00Z" },
  { id: "yr-10", field_id: "field-2", farm_id: "farm-1", crop_year: 2021, crop_type: "soybeans", yield_bu_ac: 54, moisture_pct: 13.8, acres: 480, created_at: "2021-10-22T14:00:00Z" },
];

// ── Derived summaries ─────────────────────────────────────────────────────────

function computeAPH(fieldId: string): APHResult {
  const records = mockYieldRecords
    .filter((r) => r.field_id === fieldId)
    .sort((a, b) => b.crop_year - a.crop_year);

  if (records.length === 0) {
    return {
      field_id: fieldId,
      years_used: 0,
      average_yield_bu_ac: 0,
      trend_direction: "flat",
      trend_pct: 0,
      records: [],
    };
  }

  const avg =
    records.reduce((sum, r) => sum + r.yield_bu_ac, 0) / records.length;

  const oldest = records[records.length - 1].yield_bu_ac;
  const newest = records[0].yield_bu_ac;
  const trendPct = ((newest - oldest) / oldest) * 100;

  return {
    field_id: fieldId,
    years_used: records.length,
    average_yield_bu_ac: Math.round(avg * 10) / 10,
    trend_direction: trendPct > 2 ? "up" : trendPct < -2 ? "down" : "flat",
    trend_pct: Math.round(trendPct * 10) / 10,
    records,
  };
}

export const mockAPHField1 = computeAPH("field-1");
export const mockAPHField2 = computeAPH("field-2");

export function getAPHForField(fieldId: string): APHResult {
  if (fieldId === "field-1") return mockAPHField1;
  if (fieldId === "field-2") return mockAPHField2;
  return computeAPH(fieldId);
}

export function getActivitySummary(farmId: string): ActivitySummary {
  const farmActivities = mockActivities.filter((a) => a.farm_id === farmId);
  const sorted = [...farmActivities].sort(
    (a, b) =>
      new Date(b.activity_date).getTime() - new Date(a.activity_date).getTime()
  );

  const byType = {
    plant: 0,
    spray: 0,
    fertilize: 0,
    scout: 0,
    harvest: 0,
  };
  farmActivities.forEach((a) => {
    byType[a.activity_type]++;
  });

  return {
    total_activities: farmActivities.length,
    by_type: byType,
    last_activity_date: sorted[0]?.activity_date ?? null,
    recent: sorted.slice(0, 5),
  };
}
