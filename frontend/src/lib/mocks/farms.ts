import type { Farm, Field, Recommendation, SoilProfile, WeatherData, CreditEligibility } from "@/lib/api/types";

export const mockFarms: Farm[] = [
  {
    id: "farm-1",
    user_id: "user-1",
    name: "Johnson Family Farm",
    state: "Iowa",
    county_fips: "19153",
    total_acres: 1200,
    goals: "both",
    created_at: "2026-03-15T10:00:00Z",
  },
];

export const mockFields: Field[] = [
  {
    id: "field-1",
    farm_id: "farm-1",
    name: "North Quarter",
    acres: 320,
    crop_type: "corn",
    boundary_description: "Section 14, Township 5N, Range 3W",
    practices: ["no-till", "crop-rotation"],
    created_at: "2026-03-15T10:05:00Z",
  },
  {
    id: "field-2",
    farm_id: "farm-1",
    name: "South Half",
    acres: 480,
    crop_type: "soybeans",
    boundary_description: "Section 23, Township 5N, Range 3W",
    practices: ["cover-crops", "reduced-till"],
    created_at: "2026-03-15T10:10:00Z",
  },
];

export const mockRecommendations: Recommendation[] = [
  {
    id: "rec-1",
    field_id: "field-1",
    created_at: "2026-03-20T08:00:00Z",
    practice_code: "340",
    title: "Plant cover crops after corn harvest",
    rationale:
      "Your soil tests show organic matter at 3.2%. Planting a cereal rye cover crop this fall can increase organic matter by 0.3-0.5% over 2 years, reducing your fertilizer costs by $15-25/acre.",
    priority: "high",
    status: "pending",
  },
  {
    id: "rec-2",
    field_id: "field-1",
    created_at: "2026-03-20T08:00:00Z",
    practice_code: "329",
    title: "Switch to no-till on South Half",
    rationale:
      "Your South Half field has been under reduced-till. Full no-till would qualify you for EQIP cost-share payments and reduce diesel costs by approximately $8/acre.",
    priority: "medium",
    status: "pending",
  },
];

export const mockSoilProfile: SoilProfile = {
  id: "soil-1",
  field_id: "field-1",
  ssurgo_map_unit: "Clarion-Nicollet-Webster",
  texture: "Silty clay loam",
  ph: 6.8,
  organic_matter_pct: 3.2,
  source: "ssurgo",
  fetched_at: "2026-03-16T12:00:00Z",
};

export const mockWeather: WeatherData[] = [
  {
    id: "w-1", field_id: "field-1", date: "2026-04-02",
    temp_high: 62, temp_low: 41, precip_mm: 0, soil_temp: 48,
    fetched_at: "2026-04-02T06:00:00Z",
  },
  {
    id: "w-2", field_id: "field-1", date: "2026-04-03",
    temp_high: 58, temp_low: 39, precip_mm: 12, soil_temp: 47,
    fetched_at: "2026-04-02T06:00:00Z",
  },
  {
    id: "w-3", field_id: "field-1", date: "2026-04-04",
    temp_high: 65, temp_low: 44, precip_mm: 0, soil_temp: 50,
    fetched_at: "2026-04-02T06:00:00Z",
  },
  {
    id: "w-4", field_id: "field-1", date: "2026-04-05",
    temp_high: 70, temp_low: 48, precip_mm: 0, soil_temp: 52,
    fetched_at: "2026-04-02T06:00:00Z",
  },
  {
    id: "w-5", field_id: "field-1", date: "2026-04-06",
    temp_high: 55, temp_low: 38, precip_mm: 25, soil_temp: 49,
    fetched_at: "2026-04-02T06:00:00Z",
  },
];

export const mockCredits: CreditEligibility[] = [
  {
    id: "credit-1",
    farm_id: "farm-1",
    program: "EQIP",
    status: "eligible",
    practices_documented: ["340", "329"],
    notes: "Cover crops and no-till qualify for EQIP cost-share in Polk County.",
    updated_at: "2026-03-22T10:00:00Z",
  },
  {
    id: "credit-2",
    farm_id: "farm-1",
    program: "VCM",
    status: "pending_review",
    practices_documented: ["340"],
    notes: "Estimated 1.2 carbon credits per acre with cover crop adoption.",
    updated_at: "2026-03-22T10:00:00Z",
  },
];
