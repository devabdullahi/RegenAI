"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ActivityTypePicker } from "./activity-type-picker";
import { RestrictedUseBadge } from "./restricted-use-badge";
import { useState } from "react";
import type { ActivityType, Field } from "@/lib/api/types";
import { cn } from "@/lib/utils";

// ── Zod schemas per activity type ─────────────────────────────────────────────

const commonSchema = z.object({
  field_id: z.string().min(1, "Select a field"),
  activity_date: z.string().min(1, "Date is required"),
  acres: z.coerce.number().positive("Acres must be greater than 0"),
  operator: z.string().min(1, "Operator name is required"),
  equipment: z.string().optional(),
  cost_per_acre: z.coerce.number().nonnegative().optional(),
  notes: z.string().optional(),
});

const plantSchema = commonSchema.extend({
  activity_type: z.literal("plant"),
  variety: z.string().min(1, "Variety is required"),
  seeding_rate_kac: z.coerce.number().positive("Seeding rate required"),
  row_spacing_in: z.coerce.number().positive("Row spacing required"),
  depth_in: z.coerce.number().positive("Depth required"),
});

const spraySchema = commonSchema.extend({
  activity_type: z.literal("spray"),
  product_name: z.string().min(1, "Product name is required"),
  epa_reg_number: z.string().min(1, "EPA registration number required"),
  rate_oz_ac: z.coerce.number().positive("Rate required"),
  target_pest: z.string().min(1, "Target pest required"),
  wind_mph: z.coerce.number().nonnegative("Wind speed required"),
  temp_f: z.coerce.number("Temperature required"),
  restricted_use: z.boolean(),
  applicator_name: z.string().optional(),
  applicator_cert_number: z.string().optional(),
});

const fertilizeSchema = commonSchema.extend({
  activity_type: z.literal("fertilize"),
  product_name: z.string().min(1, "Product name is required"),
  n_lbs_ac: z.coerce.number().nonnegative("Nitrogen rate required"),
  p_lbs_ac: z.coerce.number().nonnegative("Phosphorus rate required"),
  k_lbs_ac: z.coerce.number().nonnegative("Potassium rate required"),
  method: z.enum(["broadcast", "sidedress", "inject", "foliar"]),
});

const scoutSchema = commonSchema.extend({
  activity_type: z.literal("scout"),
  pest_type: z.enum(["insect", "disease", "weed", "other"]),
  pest_name: z.string().min(1, "Pest or problem name required"),
  severity: z.enum(["none", "low", "medium", "high", "critical"]),
  threshold_exceeded: z.boolean(),
  action_taken: z.string().optional(),
});

const harvestSchema = commonSchema.extend({
  activity_type: z.literal("harvest"),
  yield_bu_ac: z.coerce.number().positive("Yield required"),
  moisture_pct: z.coerce.number().positive("Moisture required"),
  test_weight_lbs_bu: z.coerce.number().positive("Test weight required"),
  elevator_ticket: z.string().optional(),
});

// Union — we validate per-type at submission
type PlantFormValues = z.infer<typeof plantSchema>;
type SprayFormValues = z.infer<typeof spraySchema>;
type FertilizeFormValues = z.infer<typeof fertilizeSchema>;
type ScoutFormValues = z.infer<typeof scoutSchema>;
type HarvestFormValues = z.infer<typeof harvestSchema>;

type AnyFormValues =
  | PlantFormValues
  | SprayFormValues
  | FertilizeFormValues
  | ScoutFormValues
  | HarvestFormValues;

// ── Shared form field wrapper ──────────────────────────────────────────────────

function Field({
  label,
  htmlFor,
  error,
  required,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor} className="text-base font-medium text-foreground">
        {label}
        {required && (
          <span className="ml-1 text-red-500" aria-hidden="true">
            *
          </span>
        )}
      </Label>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {children}
      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

// ── Type-specific form sections ────────────────────────────────────────────────

function PlantFields({
  register,
  errors,
}: {
  register: ReturnType<typeof useForm>["register"];
  errors: Record<string, { message?: string } | undefined>;
}) {
  return (
    <>
      <Field label="Seed Variety" htmlFor="variety" required error={errors.variety?.message}>
        <Input
          id="variety"
          placeholder="e.g. DeKalb DKC52-70RIB"
          className="h-12 text-base"
          {...register("variety")}
        />
      </Field>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field
          label="Seeding Rate (K/ac)"
          htmlFor="seeding_rate_kac"
          required
          hint="Thousands of seeds per acre"
          error={errors.seeding_rate_kac?.message}
        >
          <Input
            id="seeding_rate_kac"
            type="number"
            step="0.1"
            placeholder="34.5"
            className="h-12 text-base"
            {...register("seeding_rate_kac")}
          />
        </Field>
        <Field
          label='Row Spacing (inches)'
          htmlFor="row_spacing_in"
          required
          error={errors.row_spacing_in?.message}
        >
          <Input
            id="row_spacing_in"
            type="number"
            placeholder="30"
            className="h-12 text-base"
            {...register("row_spacing_in")}
          />
        </Field>
        <Field
          label="Planting Depth (inches)"
          htmlFor="depth_in"
          required
          error={errors.depth_in?.message}
        >
          <Input
            id="depth_in"
            type="number"
            step="0.25"
            placeholder="2.0"
            className="h-12 text-base"
            {...register("depth_in")}
          />
        </Field>
      </div>
    </>
  );
}

function SprayFields({
  register,
  watch,
  setValue,
  errors,
}: {
  register: ReturnType<typeof useForm>["register"];
  watch: ReturnType<typeof useForm>["watch"];
  setValue: ReturnType<typeof useForm>["setValue"];
  errors: Record<string, { message?: string } | undefined>;
}) {
  const restrictedUse = watch("restricted_use") as boolean;

  return (
    <>
      <Field
        label="Product Name"
        htmlFor="product_name"
        required
        error={errors.product_name?.message}
      >
        <Input
          id="product_name"
          placeholder="e.g. Roundup PowerMAX"
          className="h-12 text-base"
          {...register("product_name")}
        />
      </Field>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field
          label="EPA Registration Number"
          htmlFor="epa_reg_number"
          required
          hint="Found on the product label"
          error={errors.epa_reg_number?.message}
        >
          <Input
            id="epa_reg_number"
            placeholder="e.g. 524-549"
            className="h-12 text-base"
            {...register("epa_reg_number")}
          />
        </Field>
        <Field
          label="Application Rate (oz/ac)"
          htmlFor="rate_oz_ac"
          required
          error={errors.rate_oz_ac?.message}
        >
          <Input
            id="rate_oz_ac"
            type="number"
            step="0.01"
            placeholder="32"
            className="h-12 text-base"
            {...register("rate_oz_ac")}
          />
        </Field>
      </div>
      <Field
        label="Target Pest or Problem"
        htmlFor="target_pest"
        required
        error={errors.target_pest?.message}
      >
        <Input
          id="target_pest"
          placeholder="e.g. Waterhemp, Soybean Aphid"
          className="h-12 text-base"
          {...register("target_pest")}
        />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field
          label="Wind Speed (mph)"
          htmlFor="wind_mph"
          required
          error={errors.wind_mph?.message}
        >
          <Input
            id="wind_mph"
            type="number"
            step="0.5"
            placeholder="7"
            className="h-12 text-base"
            {...register("wind_mph")}
          />
        </Field>
        <Field
          label="Temperature (°F)"
          htmlFor="temp_f"
          required
          error={errors.temp_f?.message}
        >
          <Input
            id="temp_f"
            type="number"
            placeholder="72"
            className="h-12 text-base"
            {...register("temp_f")}
          />
        </Field>
      </div>

      {/* Restricted use toggle */}
      <div className="rounded-xl border-2 border-border bg-card px-4 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1">
            <p className="text-base font-semibold text-foreground">
              Restricted use pesticide?
            </p>
            <p className="text-sm text-muted-foreground mt-0.5">
              Check the label — restricted use products require a certified applicator.
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={restrictedUse}
            onClick={() => setValue("restricted_use", !restrictedUse, { shouldValidate: true })}
            className={cn(
              "relative inline-flex h-7 w-14 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              restrictedUse ? "bg-red-500" : "bg-muted"
            )}
          >
            <span
              className={cn(
                "pointer-events-none inline-block h-6 w-6 rounded-full bg-white shadow transition-transform",
                restrictedUse ? "translate-x-7" : "translate-x-0"
              )}
            />
            <span className="sr-only">{restrictedUse ? "Yes, restricted use" : "No, not restricted use"}</span>
          </button>
        </div>

        {restrictedUse && (
          <div className="mt-4 space-y-4 border-t border-border pt-4">
            <div className="flex items-center gap-2">
              <RestrictedUseBadge />
              <p className="text-sm text-muted-foreground">
                Applicator info is required for this record.
              </p>
            </div>
            <Field
              label="Applicator Name"
              htmlFor="applicator_name"
              required
              error={errors.applicator_name?.message}
            >
              <Input
                id="applicator_name"
                placeholder="Full name of certified applicator"
                className="h-12 text-base"
                {...register("applicator_name")}
              />
            </Field>
            <Field
              label="Applicator Certification Number"
              htmlFor="applicator_cert_number"
              required
              error={errors.applicator_cert_number?.message}
            >
              <Input
                id="applicator_cert_number"
                placeholder="e.g. IA-LIC-44821"
                className="h-12 text-base"
                {...register("applicator_cert_number")}
              />
            </Field>
          </div>
        )}
      </div>
    </>
  );
}

function FertilizeFields({
  register,
  errors,
}: {
  register: ReturnType<typeof useForm>["register"];
  errors: Record<string, { message?: string } | undefined>;
}) {
  return (
    <>
      <Field
        label="Product Name"
        htmlFor="product_name"
        required
        error={errors.product_name?.message}
      >
        <Input
          id="product_name"
          placeholder="e.g. UAN 32% Solution"
          className="h-12 text-base"
          {...register("product_name")}
        />
      </Field>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field
          label="Nitrogen — N (lbs/ac)"
          htmlFor="n_lbs_ac"
          required
          error={errors.n_lbs_ac?.message}
        >
          <Input
            id="n_lbs_ac"
            type="number"
            placeholder="80"
            className="h-12 text-base"
            {...register("n_lbs_ac")}
          />
        </Field>
        <Field
          label="Phosphorus — P (lbs/ac)"
          htmlFor="p_lbs_ac"
          required
          error={errors.p_lbs_ac?.message}
        >
          <Input
            id="p_lbs_ac"
            type="number"
            placeholder="40"
            className="h-12 text-base"
            {...register("p_lbs_ac")}
          />
        </Field>
        <Field
          label="Potassium — K (lbs/ac)"
          htmlFor="k_lbs_ac"
          required
          error={errors.k_lbs_ac?.message}
        >
          <Input
            id="k_lbs_ac"
            type="number"
            placeholder="60"
            className="h-12 text-base"
            {...register("k_lbs_ac")}
          />
        </Field>
      </div>
      <Field
        label="Application Method"
        htmlFor="method"
        required
        error={errors.method?.message}
      >
        <select
          id="method"
          className="h-12 w-full rounded-lg border border-input bg-background px-3 text-base text-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/50"
          {...register("method")}
        >
          <option value="broadcast">Broadcast (spread over field)</option>
          <option value="sidedress">Sidedress (between rows)</option>
          <option value="inject">Inject (knife into soil)</option>
          <option value="foliar">Foliar (sprayed on leaves)</option>
        </select>
      </Field>
    </>
  );
}

function ScoutFields({
  register,
  watch,
  setValue,
  errors,
}: {
  register: ReturnType<typeof useForm>["register"];
  watch: ReturnType<typeof useForm>["watch"];
  setValue: ReturnType<typeof useForm>["setValue"];
  errors: Record<string, { message?: string } | undefined>;
}) {
  const thresholdExceeded = watch("threshold_exceeded") as boolean;
  const severity = watch("severity") as string;

  const SEVERITY_OPTIONS = [
    { value: "none", label: "None" },
    { value: "low", label: "Low" },
    { value: "medium", label: "Medium" },
    { value: "high", label: "High" },
    { value: "critical", label: "Critical" },
  ];

  const SEVERITY_COLORS: Record<string, string> = {
    none: "bg-muted text-muted-foreground border-border",
    low: "bg-green-100 text-green-700 border-green-300",
    medium: "bg-amber-100 text-amber-700 border-amber-300",
    high: "bg-red-100 text-red-700 border-red-300",
    critical: "bg-red-200 text-red-900 border-red-500",
  };

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field
          label="Type of Problem"
          htmlFor="pest_type"
          required
          error={errors.pest_type?.message}
        >
          <select
            id="pest_type"
            className="h-12 w-full rounded-lg border border-input bg-background px-3 text-base text-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/50"
            {...register("pest_type")}
          >
            <option value="insect">Insect</option>
            <option value="disease">Disease</option>
            <option value="weed">Weed</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field
          label="Pest or Problem Name"
          htmlFor="pest_name"
          required
          error={errors.pest_name?.message}
        >
          <Input
            id="pest_name"
            placeholder="e.g. Soybean Aphid, Gray Leaf Spot"
            className="h-12 text-base"
            {...register("pest_name")}
          />
        </Field>
      </div>

      {/* Severity slider as big buttons */}
      <div className="space-y-1.5">
        <p className="text-base font-medium text-foreground">
          Pressure Level <span className="text-red-500" aria-hidden="true">*</span>
        </p>
        <div className="flex gap-2">
          {SEVERITY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setValue("severity", opt.value, { shouldValidate: true })}
              aria-pressed={severity === opt.value}
              className={cn(
                "flex-1 min-h-[48px] rounded-lg border-2 px-2 py-2 text-sm font-semibold transition-all",
                severity === opt.value
                  ? SEVERITY_COLORS[opt.value]
                  : "border-border bg-background text-muted-foreground hover:bg-muted"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Threshold exceeded toggle */}
      <div className="rounded-xl border-2 border-border bg-card px-4 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1">
            <p className="text-base font-semibold text-foreground">
              Did this exceed the action threshold?
            </p>
            <p className="text-sm text-muted-foreground mt-0.5">
              The point where treatment becomes cost-effective
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={thresholdExceeded}
            onClick={() => setValue("threshold_exceeded", !thresholdExceeded, { shouldValidate: true })}
            className={cn(
              "relative inline-flex h-7 w-14 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              thresholdExceeded ? "bg-red-500" : "bg-muted"
            )}
          >
            <span
              className={cn(
                "pointer-events-none inline-block h-6 w-6 rounded-full bg-white shadow transition-transform",
                thresholdExceeded ? "translate-x-7" : "translate-x-0"
              )}
            />
            <span className="sr-only">
              {thresholdExceeded ? "Threshold exceeded" : "Threshold not exceeded"}
            </span>
          </button>
        </div>
      </div>

      <Field
        label="Action Taken (optional)"
        htmlFor="action_taken"
        error={errors.action_taken?.message}
      >
        <Input
          id="action_taken"
          placeholder="e.g. Scheduled foliar spray for next week"
          className="h-12 text-base"
          {...register("action_taken")}
        />
      </Field>
    </>
  );
}

function HarvestFields({
  register,
  errors,
}: {
  register: ReturnType<typeof useForm>["register"];
  errors: Record<string, { message?: string } | undefined>;
}) {
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field
          label="Yield (bu/acre)"
          htmlFor="yield_bu_ac"
          required
          error={errors.yield_bu_ac?.message}
        >
          <Input
            id="yield_bu_ac"
            type="number"
            step="0.1"
            placeholder="210"
            className="h-12 text-base"
            {...register("yield_bu_ac")}
          />
        </Field>
        <Field
          label="Moisture (%)"
          htmlFor="moisture_pct"
          required
          error={errors.moisture_pct?.message}
        >
          <Input
            id="moisture_pct"
            type="number"
            step="0.1"
            placeholder="15.5"
            className="h-12 text-base"
            {...register("moisture_pct")}
          />
        </Field>
        <Field
          label="Test Weight (lbs/bu)"
          htmlFor="test_weight_lbs_bu"
          required
          error={errors.test_weight_lbs_bu?.message}
        >
          <Input
            id="test_weight_lbs_bu"
            type="number"
            step="0.1"
            placeholder="56.0"
            className="h-12 text-base"
            {...register("test_weight_lbs_bu")}
          />
        </Field>
      </div>
      <Field
        label="Elevator Ticket Number (optional)"
        htmlFor="elevator_ticket"
        error={errors.elevator_ticket?.message}
      >
        <Input
          id="elevator_ticket"
          placeholder="e.g. IOW-2025-8812"
          className="h-12 text-base"
          {...register("elevator_ticket")}
        />
      </Field>
    </>
  );
}

// ── Main form ──────────────────────────────────────────────────────────────────

interface ActivityFormProps {
  fields: Field[];
  defaultFieldId?: string;
  defaultActivityType?: ActivityType;
}

export function ActivityForm({
  fields,
  defaultFieldId,
  defaultActivityType,
}: ActivityFormProps) {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(defaultActivityType ? 2 : 1);
  const [selectedType, setSelectedType] = useState<ActivityType | null>(
    defaultActivityType ?? null
  );

  // We use a single RHF instance with loose typing; per-type schema is applied at submit
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Record<string, unknown>>({
    defaultValues: {
      field_id: defaultFieldId ?? (fields[0]?.id ?? ""),
      activity_date: new Date().toISOString().slice(0, 10),
      acres: fields.find((f) => f.id === (defaultFieldId ?? fields[0]?.id))?.acres ?? "",
      operator: "Dave Johnson",
      restricted_use: false,
      threshold_exceeded: false,
      severity: "low",
      pest_type: "insect",
      method: "broadcast",
    },
  });

  // When field changes, pre-fill acres
  const watchedFieldId = watch("field_id") as string;

  function handleFieldChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const fieldId = e.target.value;
    setValue("field_id", fieldId);
    const f = fields.find((fi) => fi.id === fieldId);
    if (f) setValue("acres", f.acres);
  }

  function handleTypeSelect(type: ActivityType) {
    setSelectedType(type);
    setValue("activity_type", type);
  }

  function goToStep2() {
    if (!selectedType) return;
    setStep(2);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function onSubmit(data: Record<string, unknown>) {
    // Validate with the appropriate Zod schema
    let result;
    const schema =
      selectedType === "plant"
        ? plantSchema
        : selectedType === "spray"
          ? spraySchema
          : selectedType === "fertilize"
            ? fertilizeSchema
            : selectedType === "scout"
              ? scoutSchema
              : harvestSchema;

    result = schema.safeParse({ ...data, activity_type: selectedType });
    if (!result.success) {
      toast.error("Please fix the errors before saving.");
      return;
    }

    // Simulate save
    await new Promise((r) => setTimeout(r, 600));

    const fieldName = fields.find((f) => f.id === data.field_id)?.name ?? "your field";
    toast.success(`Activity saved for ${fieldName}!`, {
      description: "Your field log has been updated.",
      action: {
        label: "Log Another",
        onClick: () => {
          reset();
          setSelectedType(null);
          setStep(1);
        },
      },
    });

    setTimeout(() => {
      router.push("/activities");
    }, 1200);
  }

  // Sync field_id's acres on mount / field change
  const currentField = fields.find((f) => f.id === watchedFieldId);

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">

      {/* ── Step 1: Choose field + type ── */}
      <section aria-labelledby="step1-heading">
        <div className="mb-4">
          <h2
            id="step1-heading"
            className="font-heading text-lg font-semibold text-foreground"
          >
            Step 1: Which field and what did you do?
          </h2>
        </div>

        {/* Field selector */}
        <div className="space-y-1.5 mb-6">
          <label
            htmlFor="field_id"
            className="block text-base font-medium text-foreground"
          >
            Field <span className="text-red-500" aria-hidden="true">*</span>
          </label>
          <select
            id="field_id"
            className="h-12 w-full rounded-lg border border-input bg-background px-3 text-base text-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/50"
            {...register("field_id")}
            onChange={handleFieldChange}
          >
            {fields.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name} ({f.acres} acres — {f.crop_type})
              </option>
            ))}
          </select>
          {currentField?.boundary_description && (
            <p className="text-xs text-muted-foreground">
              {currentField.boundary_description}
            </p>
          )}
        </div>

        {/* Activity type picker */}
        <ActivityTypePicker
          value={selectedType}
          onChange={handleTypeSelect}
        />

        {step === 1 && (
          <div className="mt-6">
            <button
              type="button"
              onClick={goToStep2}
              disabled={!selectedType}
              className="w-full min-h-[56px] rounded-xl bg-primary px-6 py-3 text-base font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {selectedType ? "Next: Enter details" : "Choose an activity type above"}
            </button>
          </div>
        )}
      </section>

      {/* ── Step 2: Type-specific fields ── */}
      {step === 2 && selectedType && (
        <>
          <hr className="border-border" />

          <section aria-labelledby="step2-heading" className="space-y-5">
            <div>
              <h2
                id="step2-heading"
                className="font-heading text-lg font-semibold text-foreground"
              >
                Step 2: Activity details
              </h2>
              <p className="text-sm text-muted-foreground mt-0.5">
                Fill in what happened.
              </p>
            </div>

            {/* Date */}
            <Field label="Date" htmlFor="activity_date" required error={errors.activity_date?.message as string | undefined}>
              <input
                id="activity_date"
                type="date"
                className="h-12 w-full rounded-lg border border-input bg-background px-3 text-base text-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/50"
                {...register("activity_date")}
              />
            </Field>

            {/* Type-specific fields */}
            {selectedType === "plant" && (
              <PlantFields register={register} errors={errors as Record<string, { message?: string } | undefined>} />
            )}
            {selectedType === "spray" && (
              <SprayFields
                register={register}
                watch={watch}
                setValue={setValue}
                errors={errors as Record<string, { message?: string } | undefined>}
              />
            )}
            {selectedType === "fertilize" && (
              <FertilizeFields register={register} errors={errors as Record<string, { message?: string } | undefined>} />
            )}
            {selectedType === "scout" && (
              <ScoutFields
                register={register}
                watch={watch}
                setValue={setValue}
                errors={errors as Record<string, { message?: string } | undefined>}
              />
            )}
            {selectedType === "harvest" && (
              <HarvestFields register={register} errors={errors as Record<string, { message?: string } | undefined>} />
            )}
          </section>

          <hr className="border-border" />

          {/* ── Common fields ── */}
          <section aria-labelledby="common-heading" className="space-y-5">
            <h2
              id="common-heading"
              className="font-heading text-base font-semibold text-foreground"
            >
              Additional info
            </h2>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field
                label="Total Acres"
                htmlFor="acres"
                required
                error={errors.acres?.message as string | undefined}
              >
                <Input
                  id="acres"
                  type="number"
                  step="0.1"
                  className="h-12 text-base"
                  {...register("acres")}
                />
              </Field>
              <Field
                label="Operator"
                htmlFor="operator"
                required
                error={errors.operator?.message as string | undefined}
              >
                <Input
                  id="operator"
                  placeholder="Who did this work?"
                  className="h-12 text-base"
                  {...register("operator")}
                />
              </Field>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field
                label="Equipment Used (optional)"
                htmlFor="equipment"
                error={errors.equipment?.message as string | undefined}
              >
                <Input
                  id="equipment"
                  placeholder="e.g. John Deere 1775NT Planter"
                  className="h-12 text-base"
                  {...register("equipment")}
                />
              </Field>
              <Field
                label="Cost per Acre (optional)"
                htmlFor="cost_per_acre"
                error={errors.cost_per_acre?.message as string | undefined}
              >
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                    $
                  </span>
                  <Input
                    id="cost_per_acre"
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    className="h-12 pl-7 text-base"
                    {...register("cost_per_acre")}
                  />
                </div>
              </Field>
            </div>

            <Field
              label="Notes (optional)"
              htmlFor="notes"
              error={errors.notes?.message as string | undefined}
            >
              <Textarea
                id="notes"
                placeholder="Any other details worth recording..."
                className="min-h-[80px] text-base"
                {...register("notes")}
              />
            </Field>
          </section>

          {/* Save button */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full min-h-[56px] rounded-xl bg-accent px-6 py-3 text-base font-semibold text-accent-foreground transition-colors hover:bg-accent/90 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {isSubmitting ? "Saving..." : "Save Activity"}
            </button>
          </div>

          <button
            type="button"
            onClick={() => setStep(1)}
            className="w-full min-h-[48px] rounded-xl border border-border bg-background px-6 py-2 text-base font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Back — change field or activity type
          </button>
        </>
      )}
    </form>
  );
}
