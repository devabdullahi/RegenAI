/**
 * Validation for the activity form: one zod schema per activity type.
 *
 * The form is a single react-hook-form instance whose `activity_type` value
 * picks the schema, so `activityFormResolver` is static and inline errors show
 * for whichever type is selected. Keys from other types are stripped by
 * z.object, so a planting never submits leftover spray values.
 */

import { z } from "zod";
import type { FieldError, FieldErrors, Resolver } from "react-hook-form";
import type { ActivityType, Field } from "@/lib/api/types";

export type ActivityFormValues = Record<string, unknown>;

/**
 * Today as YYYY-MM-DD in the farmer's time zone. toISOString() uses UTC, which
 * is already tomorrow on a US evening, and the backend rejects future dates.
 */
export function todayLocalIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/** Blank inputs become undefined; z.coerce would turn "" into a fake 0. */
function blankToNumber(value: unknown): unknown {
  if (value === "" || value === null || value === undefined) return undefined;
  return typeof value === "string" ? Number(value) : value;
}

type NumberCheck = (n: z.ZodNumber) => z.ZodNumber;
const noCheck: NumberCheck = (n) => n;

function requiredNumber(label: string, check: NumberCheck = noCheck) {
  return z.preprocess(blankToNumber, check(z.number({ error: `Enter ${label}` })));
}

function optionalNumber(label: string, check: NumberCheck = noCheck) {
  return z.preprocess(
    blankToNumber,
    check(z.number({ error: `Enter ${label} as a number` })).optional()
  );
}

function requiredText(message: string, max = 200) {
  return z
    .string({ error: message })
    .trim()
    .min(1, message)
    .max(max, `Keep this under ${max} characters`);
}

function optionalText(max = 200) {
  return z.string().trim().max(max, `Keep this under ${max} characters`).optional();
}

const greaterThanZero = (label: string): NumberCheck => (n) =>
  n.positive(`${label} must be greater than 0`);
const notNegative = (label: string): NumberCheck => (n) =>
  n.nonnegative(`${label} can't be negative`);

const commonShape = {
  field_id: z.string({ error: "Select a field" }).min(1, "Select a field"),
  activity_date: z
    .string({ error: "Enter the date" })
    .regex(/^\d{4}-\d{2}-\d{2}$/, "Enter the date")
    .refine((date) => date <= todayLocalIso(), "The date can't be in the future"),
  acres: requiredNumber("the acres worked", greaterThanZero("Acres")),
  operator: requiredText("Enter who did this work"),
  equipment: optionalText(),
  cost_per_acre: optionalNumber("the cost per acre", notNegative("Cost")),
  notes: optionalText(2000),
};

const plantSchema = z.object({
  ...commonShape,
  activity_type: z.literal("plant"),
  variety: requiredText("Enter the seed variety"),
  seeding_rate_kac: requiredNumber("the seeding rate", greaterThanZero("Seeding rate")),
  row_spacing_in: requiredNumber("the row spacing", greaterThanZero("Row spacing")),
  depth_in: requiredNumber("the planting depth", greaterThanZero("Planting depth")),
  seed_treatment: optionalText(),
});

// `when: () => true` runs these checks even while other fields are invalid, so
// every missing value shows at once instead of one round at a time.
const spraySchema = z
  .object({
    ...commonShape,
    activity_type: z.literal("spray"),
    product_name: requiredText("Enter the product name"),
    epa_reg_number: requiredText("Enter the EPA registration number"),
    rate_oz_ac: requiredNumber("the application rate", greaterThanZero("Rate")),
    target_pest: requiredText("Enter the target pest or problem"),
    wind_mph: requiredNumber("the wind speed", notNegative("Wind speed")),
    temp_f: requiredNumber("the temperature"),
    restricted_use: z.boolean(),
    applicator_name: optionalText(),
    applicator_cert_number: optionalText(100),
  })
  // FIFRA: restricted-use records must name a certified applicator (the
  // backend enforces the same rule and returns 422 without it).
  .refine((d) => !d.restricted_use || !!d.applicator_name, {
    message: "Enter the certified applicator's name",
    path: ["applicator_name"],
    when: () => true,
  })
  .refine((d) => !d.restricted_use || !!d.applicator_cert_number, {
    message: "Enter the applicator's certification number",
    path: ["applicator_cert_number"],
    when: () => true,
  });

const fertilizeSchema = z.object({
  ...commonShape,
  activity_type: z.literal("fertilize"),
  product_name: requiredText("Enter the product name"),
  n_lbs_ac: requiredNumber("the nitrogen rate", notNegative("Nitrogen rate")),
  p_lbs_ac: requiredNumber("the phosphorus rate", notNegative("Phosphorus rate")),
  k_lbs_ac: requiredNumber("the potassium rate", notNegative("Potassium rate")),
  method: z.enum(["broadcast", "sidedress", "inject", "foliar"], {
    error: "Choose how it was applied",
  }),
});

const scoutSchema = z.object({
  ...commonShape,
  activity_type: z.literal("scout"),
  pest_type: z.enum(["insect", "disease", "weed", "other"], {
    error: "Choose the type of problem",
  }),
  pest_name: requiredText("Enter the pest or problem name"),
  severity: z.enum(["none", "low", "moderate", "high", "critical"], {
    error: "Choose a pressure level",
  }),
  threshold_exceeded: z.boolean(),
  action_taken: optionalText(),
});

const harvestSchema = z.object({
  ...commonShape,
  activity_type: z.literal("harvest"),
  yield_bu_ac: requiredNumber("the yield", greaterThanZero("Yield")),
  moisture_pct: requiredNumber("the moisture", (n) =>
    n.nonnegative("Moisture can't be negative").max(100, "Moisture must be 100% or less")
  ),
  test_weight_lbs_bu: requiredNumber("the test weight", greaterThanZero("Test weight")),
  elevator_ticket: optionalText(),
});

const tillageSchema = z.object({
  ...commonShape,
  activity_type: z.literal("tillage"),
  tillage_depth_in: optionalNumber("the tillage depth", notNegative("Depth")),
});

const coverCropSchema = z.object({
  ...commonShape,
  activity_type: z.literal("cover_crop"),
  cover_crop_species: requiredText("Enter the cover crop species"),
});

const otherSchema = z.object({
  ...commonShape,
  activity_type: z.literal("other"),
  // With no type-specific fields, the notes are the record.
  notes: requiredText("Describe what you did", 2000),
});

const ACTIVITY_SCHEMAS: Record<ActivityType, z.ZodType<ActivityFormValues, unknown>> = {
  plant: plantSchema,
  spray: spraySchema,
  fertilize: fertilizeSchema,
  scout: scoutSchema,
  harvest: harvestSchema,
  tillage: tillageSchema,
  cover_crop: coverCropSchema,
  other: otherSchema,
};

/** Validates with the schema for the form's current activity_type. */
export const activityFormResolver: Resolver<ActivityFormValues> = async (values) => {
  const type = values["activity_type"];
  const schema =
    typeof type === "string" && Object.hasOwn(ACTIVITY_SCHEMAS, type)
      ? ACTIVITY_SCHEMAS[type as ActivityType]
      : undefined;

  if (!schema) {
    return {
      values: {},
      errors: {
        activity_type: { type: "required", message: "Choose an activity type" },
      },
    };
  }

  const result = schema.safeParse(values);
  if (result.success) return { values: result.data, errors: {} };

  const errors: Record<string, FieldError> = {};
  for (const issue of result.error.issues) {
    const name = issue.path.map(String).join(".");
    if (name && !errors[name]) {
      errors[name] = { type: issue.code, message: issue.message };
    }
  }
  return { values: {}, errors: errors as FieldErrors<ActivityFormValues> };
};

/** Initial values; defaultFieldId falls back to the first field if it isn't on this farm. */
export function activityFormDefaults(
  fields: Field[],
  defaultFieldId?: string,
  defaultActivityType?: ActivityType
): ActivityFormValues {
  const field = fields.find((f) => f.id === defaultFieldId) ?? fields[0];
  return {
    activity_type: defaultActivityType,
    field_id: field?.id ?? "",
    activity_date: todayLocalIso(),
    acres: field?.acres ?? "",
    operator: "",
    restricted_use: false,
    threshold_exceeded: false,
    severity: "low",
    pest_type: "insect",
    method: "broadcast",
  };
}
