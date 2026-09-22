/**
 * Shared configuration for the onboarding flow (/onboarding/*): US states,
 * current-practice options with their NRCS codes, goal ids, and the
 * localStorage keys that carry answers between steps.
 */

import type { FarmGoals } from "@/lib/api/types";

// ── localStorage keys ─────────────────────────────────────────────────────────

export const ONBOARDING_STORAGE_KEYS = {
  farm: "onboarding_farm",
  fields: "onboarding_fields",
  practices: "onboarding_practices",
  goal: "onboarding_goal",
  /** Database id of a farm already created by a previous (partially failed) attempt. */
  createdFarmId: "onboarding_created_farm_id",
  /** Map of onboarding field id -> database field id for fields already created. */
  createdFieldIds: "onboarding_created_field_ids",
} as const;

// ── States ────────────────────────────────────────────────────────────────────

/**
 * Every place NRCS administers conservation programs, with its 2-digit FIPS
 * prefix (the first 2 digits of every county — or county-equivalent — FIPS
 * code there), per the Census Bureau state FIPS table.
 *
 * The 50 states come first so the common cases are at the top of the picker;
 * the District of Columbia and the territories follow. The backend accepts any
 * two-letter code (`farms.state` is `^[A-Z]{2}$`), so this list only decides
 * what the picker offers and which FIPS prefix a county code is checked
 * against.
 */
export const US_STATES = [
  { code: "AL", name: "Alabama", fips: "01" },
  { code: "AK", name: "Alaska", fips: "02" },
  { code: "AZ", name: "Arizona", fips: "04" },
  { code: "AR", name: "Arkansas", fips: "05" },
  { code: "CA", name: "California", fips: "06" },
  { code: "CO", name: "Colorado", fips: "08" },
  { code: "CT", name: "Connecticut", fips: "09" },
  { code: "DE", name: "Delaware", fips: "10" },
  { code: "FL", name: "Florida", fips: "12" },
  { code: "GA", name: "Georgia", fips: "13" },
  { code: "HI", name: "Hawaii", fips: "15" },
  { code: "ID", name: "Idaho", fips: "16" },
  { code: "IL", name: "Illinois", fips: "17" },
  { code: "IN", name: "Indiana", fips: "18" },
  { code: "IA", name: "Iowa", fips: "19" },
  { code: "KS", name: "Kansas", fips: "20" },
  { code: "KY", name: "Kentucky", fips: "21" },
  { code: "LA", name: "Louisiana", fips: "22" },
  { code: "ME", name: "Maine", fips: "23" },
  { code: "MD", name: "Maryland", fips: "24" },
  { code: "MA", name: "Massachusetts", fips: "25" },
  { code: "MI", name: "Michigan", fips: "26" },
  { code: "MN", name: "Minnesota", fips: "27" },
  { code: "MS", name: "Mississippi", fips: "28" },
  { code: "MO", name: "Missouri", fips: "29" },
  { code: "MT", name: "Montana", fips: "30" },
  { code: "NE", name: "Nebraska", fips: "31" },
  { code: "NV", name: "Nevada", fips: "32" },
  { code: "NH", name: "New Hampshire", fips: "33" },
  { code: "NJ", name: "New Jersey", fips: "34" },
  { code: "NM", name: "New Mexico", fips: "35" },
  { code: "NY", name: "New York", fips: "36" },
  { code: "NC", name: "North Carolina", fips: "37" },
  { code: "ND", name: "North Dakota", fips: "38" },
  { code: "OH", name: "Ohio", fips: "39" },
  { code: "OK", name: "Oklahoma", fips: "40" },
  { code: "OR", name: "Oregon", fips: "41" },
  { code: "PA", name: "Pennsylvania", fips: "42" },
  { code: "RI", name: "Rhode Island", fips: "44" },
  { code: "SC", name: "South Carolina", fips: "45" },
  { code: "SD", name: "South Dakota", fips: "46" },
  { code: "TN", name: "Tennessee", fips: "47" },
  { code: "TX", name: "Texas", fips: "48" },
  { code: "UT", name: "Utah", fips: "49" },
  { code: "VT", name: "Vermont", fips: "50" },
  { code: "VA", name: "Virginia", fips: "51" },
  { code: "WA", name: "Washington", fips: "53" },
  { code: "WV", name: "West Virginia", fips: "54" },
  { code: "WI", name: "Wisconsin", fips: "55" },
  { code: "WY", name: "Wyoming", fips: "56" },
  // District of Columbia and the territories NRCS serves.
  { code: "DC", name: "District of Columbia", fips: "11" },
  { code: "PR", name: "Puerto Rico", fips: "72" },
  { code: "VI", name: "U.S. Virgin Islands", fips: "78" },
  { code: "GU", name: "Guam", fips: "66" },
  { code: "MP", name: "Northern Mariana Islands", fips: "69" },
  { code: "AS", name: "American Samoa", fips: "60" },
] as const;

export const US_STATE_NAMES: Record<string, string> = Object.fromEntries(
  US_STATES.map((s) => [s.code, s.name])
);

export const STATE_FIPS_PREFIX: Record<string, string> = Object.fromEntries(
  US_STATES.map((s) => [s.code, s.fips])
);

// ── Practices ─────────────────────────────────────────────────────────────────

/**
 * Practices a farmer can say they already use, each mapped to its NRCS
 * Conservation Practice Standard code. fields.practices stores the codes
 * (not the UI ids) because the backend scoring/credit services (csp_scoring,
 * vcm) and the hallucination guard match on codes in eqip_practices.
 *
 * Codes and standard names verified against supabase/seed.sql, the single
 * source for eqip_practices. Note: "integrated pest management" is standard
 * 595 Pest Management Conservation System; 600 is Terrace.
 */
export const ONBOARDING_PRACTICES = [
  {
    id: "cover_crops",
    label: "Cover crops",
    description:
      "Plant non-cash crops between main crop seasons to protect and improve your soil",
    nrcsCode: "340", // Cover Crop
  },
  {
    id: "no_till",
    label: "No-till",
    description:
      "Skip tillage entirely — soil stays undisturbed, reducing erosion and fuel costs",
    nrcsCode: "329", // Residue and Tillage Management, No-Till
  },
  {
    id: "reduced_till",
    label: "Reduced-till",
    description:
      "Minimize tillage passes to preserve soil structure while still managing residue",
    nrcsCode: "345", // Residue and Tillage Management, Reduced Till
  },
  {
    id: "crop_rotation",
    label: "Crop rotation",
    description:
      "Rotate between different crops each season to break pest cycles and build soil health",
    nrcsCode: "328", // Conservation Crop Rotation
  },
  {
    id: "nutrient_management",
    label: "Nutrient management plan",
    description:
      "Apply the right nutrients at the right rate, time, and place based on soil testing",
    nrcsCode: "590", // Nutrient Management
  },
  {
    id: "manure_application",
    label: "Manure application",
    description: "Use manure as a nutrient source to reduce synthetic fertilizer use",
    nrcsCode: "633", // Waste Recycling
  },
  {
    id: "integrated_pest",
    label: "Integrated pest management",
    description:
      "Combine scouting, thresholds, and targeted treatments to reduce pesticide use",
    nrcsCode: "595", // Pest Management Conservation System
  },
  {
    id: "conservation_cover",
    label: "Conservation cover",
    description:
      "Permanent grass or native plantings on erodible ground, waterways, or buffer strips",
    nrcsCode: "327", // Conservation Cover
  },
] as const;

export type OnboardingPracticeId = (typeof ONBOARDING_PRACTICES)[number]["id"];

const PRACTICES_BY_ID: Record<string, (typeof ONBOARDING_PRACTICES)[number]> =
  Object.fromEntries(ONBOARDING_PRACTICES.map((p) => [p.id, p]));

export function practiceLabel(practiceId: string): string {
  return PRACTICES_BY_ID[practiceId]?.label ?? practiceId;
}

/** Map onboarding practice ids to unique NRCS codes, dropping unknown ids. */
export function toPracticeCodes(practiceIds: readonly string[]): string[] {
  const codes = practiceIds.flatMap((id) => {
    const code = PRACTICES_BY_ID[id]?.nrcsCode;
    return code ? [code] : [];
  });
  return Array.from(new Set(codes));
}

// ── Goals ─────────────────────────────────────────────────────────────────────

/** Same values the backend accepts for farms.goals. */
export type GoalId = FarmGoals;

export const GOAL_IDS: readonly GoalId[] = ["cost_savings", "carbon_credits", "both"];

export function isGoalId(value: unknown): value is GoalId {
  return typeof value === "string" && (GOAL_IDS as readonly string[]).includes(value);
}
