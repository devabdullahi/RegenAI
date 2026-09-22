/**
 * The crops a farmer can pick for a field, and the unit their yield is
 * normally reported in. One list, reused by onboarding, the activity form and
 * the yield sheet, so the options never drift between screens.
 *
 * Scope: US row and field crops. The backend stores `crop_type` as free text
 * (max 100 chars), so this list is a convenience for entry, not a constraint.
 * Values saved before a crop appeared here keep working — every lookup falls
 * back rather than failing.
 */

/**
 * Yield unit shown next to a yield figure. Display only: the backend stores a
 * single number per harvest (`yield_bu_acre`) with no unit column, so changing
 * the label here does not convert or re-unit anything already saved.
 */
export type YieldUnit = "bu/ac" | "lb/ac" | "cwt/ac" | "ton/ac";

/**
 * Units follow how USDA NASS reports each crop: bushels for the small grains
 * and oilseeds sold by the bushel, pounds for cotton, rice, canola, sunflower
 * and peanuts, hundredweight for dry beans, tons for hay and sugarbeets.
 */
export interface CropOption {
  /** Stored in `field.crop_type`, and shown as the label. */
  readonly value: string;
  readonly yieldUnit: YieldUnit;
}

export const CROP_OPTIONS: readonly CropOption[] = [
  { value: "Corn", yieldUnit: "bu/ac" },
  { value: "Soybeans", yieldUnit: "bu/ac" },
  { value: "Wheat", yieldUnit: "bu/ac" },
  { value: "Alfalfa / hay", yieldUnit: "ton/ac" },
  { value: "Barley", yieldUnit: "bu/ac" },
  { value: "Canola", yieldUnit: "lb/ac" },
  { value: "Cotton", yieldUnit: "lb/ac" },
  { value: "Dry beans", yieldUnit: "cwt/ac" },
  { value: "Oats", yieldUnit: "bu/ac" },
  { value: "Peanuts", yieldUnit: "lb/ac" },
  { value: "Rice", yieldUnit: "lb/ac" },
  { value: "Rye", yieldUnit: "bu/ac" },
  { value: "Sorghum", yieldUnit: "bu/ac" },
  { value: "Sugarbeets", yieldUnit: "ton/ac" },
  { value: "Sunflower", yieldUnit: "lb/ac" },
  { value: "Other", yieldUnit: "bu/ac" },
] as const;

/** The values the picker offers, in the order they are listed. */
export const CROP_VALUES: readonly string[] = CROP_OPTIONS.map((c) => c.value);

/**
 * Unit for a crop whose name we do not recognise, including "Other" and any
 * free text saved before this list existed. bu/ac matches the backend column
 * (`yield_bu_acre`) and what the harvest form has always asked for.
 */
export const DEFAULT_YIELD_UNIT: YieldUnit = "bu/ac";

const UNIT_BY_CROP: ReadonlyMap<string, YieldUnit> = new Map(
  CROP_OPTIONS.map((c) => [c.value.toLowerCase(), c.yieldUnit])
);

/** Display unit for a crop name, matched case-insensitively. */
export function yieldUnitForCrop(cropType: string | null | undefined): YieldUnit {
  if (!cropType) return DEFAULT_YIELD_UNIT;
  return UNIT_BY_CROP.get(cropType.trim().toLowerCase()) ?? DEFAULT_YIELD_UNIT;
}
