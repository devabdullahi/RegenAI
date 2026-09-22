"use client";

import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ActivityTypePicker } from "./activity-type-picker";
import { CommonFields } from "./form/common-fields";
import { CoverCropFields } from "./form/cover-crop-fields";
import { FertilizeFields } from "./form/fertilize-fields";
import {
  FormField,
  describedBy,
  fieldError,
  selectClasses,
  type ActivityFormApi,
} from "./form/form-field";
import { HarvestFields } from "./form/harvest-fields";
import { PlantFields } from "./form/plant-fields";
import {
  activityFormDefaults,
  activityFormResolver,
  todayLocalIso,
  type ActivityFormValues,
} from "./form/schemas";
import { ScoutFields } from "./form/scout-fields";
import { SprayFields } from "./form/spray-fields";
import { TillageFields } from "./form/tillage-fields";
import { EdgeNote, RuleHead } from "@/components/shared/record";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { buildActivityCreatePayload } from "@/lib/api/adapters";
import { formatAcres } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ActivityRecord, ActivityType, Field } from "@/lib/api/types";

function TypeSpecificFields({
  type,
  form,
  cropType,
}: {
  type: ActivityType;
  form: ActivityFormApi;
  /** Crop of the selected field, so harvest asks for the right yield unit. */
  cropType?: string;
}) {
  switch (type) {
    case "plant":
      return <PlantFields form={form} />;
    case "spray":
      return <SprayFields form={form} />;
    case "fertilize":
      return <FertilizeFields form={form} />;
    case "scout":
      return <ScoutFields form={form} />;
    case "harvest":
      return <HarvestFields form={form} cropType={cropType} />;
    case "tillage":
      return <TillageFields form={form} />;
    case "cover_crop":
      return <CoverCropFields form={form} />;
    case "other":
      return (
        <p className="text-sm text-muted-foreground">
          Describe what you did in the box below.
        </p>
      );
  }
}

interface ActivityFormProps {
  /** Farm the fields belong to; kept in every link after saving. */
  farmId: string;
  /** The farm's fields. The page shows an empty state instead when there are none. */
  fields: Field[];
  defaultFieldId?: string;
  defaultActivityType?: ActivityType;
}

export function ActivityForm({
  farmId,
  fields,
  defaultFieldId,
  defaultActivityType,
}: ActivityFormProps) {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(defaultActivityType ? 2 : 1);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const form = useForm<ActivityFormValues>({
    resolver: activityFormResolver,
    defaultValues: activityFormDefaults(fields, defaultFieldId, defaultActivityType),
  });
  const {
    register,
    handleSubmit,
    control,
    setValue,
    clearErrors,
    formState: { errors, isSubmitting, submitCount },
  } = form;

  // useWatch instead of watch(): watch() can't be memoized by React Compiler.
  const selectedType =
    (useWatch({ control, name: "activity_type" }) as ActivityType | undefined) ?? null;
  const selectedFieldId = useWatch({ control, name: "field_id" });
  const currentField = fields.find((f) => f.id === selectedFieldId);
  const farmQuery = `farm_id=${encodeURIComponent(farmId)}`;
  const fieldIdError = fieldError(errors, "field_id");
  const dateError = fieldError(errors, "activity_date");
  const hasErrors = submitCount > 0 && Object.keys(errors).length > 0;

  function handleTypeSelect(type: ActivityType) {
    setValue("activity_type", type);
    // Errors from the previously selected type no longer apply.
    clearErrors();
  }

  function goToStep2() {
    if (!selectedType) return;
    setStep(2);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function onSubmit(values: ActivityFormValues) {
    if (!selectedType) return;
    setSubmitError(null);

    let created: ActivityRecord;
    try {
      created = await api.activities.create(buildActivityCreatePayload(selectedType, values));
    } catch (err) {
      const message =
        err instanceof Error && err.message
          ? err.message
          : "The activity could not be saved. Check your connection and try again.";
      setSubmitError(message);
      toast.error("Activity not saved", { description: message });
      return;
    }

    const fieldName = fields.find((f) => f.id === values["field_id"])?.name ?? "your field";
    toast.success(`Activity saved for ${fieldName}`, {
      description: "Your field log has been updated.",
      action: {
        label: "Log another",
        onClick: () => router.push(`/activities/new?${farmQuery}`),
      },
    });
    // e.g. harvest saved but its yield history row could not be synced.
    for (const warning of created.warnings ?? []) {
      toast.warning(warning);
    }
    router.push(`/activities?${farmQuery}`);
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-8">
      {/* ── Step 1: Choose field + type ── */}
      <section aria-label="Step 1: which field and what you did">
        <RuleHead label="Step 1 · Field and activity" />
        <p className="mt-2 text-sm text-muted-foreground">
          Which field, and what did you do?
        </p>

        <div className="mt-4 mb-6">
          <FormField label="Field" htmlFor="field_id" required error={fieldIdError}>
            <select
              id="field_id"
              className={selectClasses}
              aria-invalid={fieldIdError ? true : undefined}
              aria-describedby={describedBy("field_id", { error: fieldIdError })}
              {...register("field_id", {
                onChange: (event: React.ChangeEvent<HTMLSelectElement>) => {
                  const field = fields.find((f) => f.id === event.target.value);
                  if (field) setValue("acres", field.acres);
                },
              })}
            >
              {fields.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name} ({formatAcres(f.acres)}, {f.crop_type})
                </option>
              ))}
            </select>
          </FormField>
          {currentField?.boundary_description && (
            <p className="mt-1.5 text-xs text-muted-foreground">
              {currentField.boundary_description}
            </p>
          )}
        </div>

        <ActivityTypePicker value={selectedType} onChange={handleTypeSelect} />

        {step === 1 && (
          <Button
            type="button"
            onClick={goToStep2}
            disabled={!selectedType}
            size="lg"
            className="mt-6 w-full cursor-pointer"
          >
            {selectedType ? "Next: enter details" : "Choose an activity type above"}
          </Button>
        )}
      </section>

      {/* ── Step 2: Type-specific + common fields ── */}
      {step === 2 && selectedType && (
        <>
          <section aria-label="Step 2: activity details" className="space-y-5">
            <div>
              <RuleHead label="Step 2 · Activity details" />
              <p className="mt-2 text-sm text-muted-foreground">
                Fill in what happened.
              </p>
            </div>

            <FormField label="Date" htmlFor="activity_date" required error={dateError}>
              <input
                id="activity_date"
                type="date"
                max={todayLocalIso()}
                className={cn(selectClasses, "font-mono")}
                aria-invalid={dateError ? true : undefined}
                aria-describedby={describedBy("activity_date", { error: dateError })}
                {...register("activity_date")}
              />
            </FormField>

            <TypeSpecificFields
              type={selectedType}
              form={form}
              cropType={currentField?.crop_type}
            />
          </section>

          <CommonFields form={form} notesRequired={selectedType === "other"} />

          <div className="space-y-3 border-t border-border pt-5">
            {submitError && (
              <div role="alert">
                <EdgeNote tone="destructive" title="Not saved">
                  {submitError}
                </EdgeNote>
              </div>
            )}
            {hasErrors && !submitError && (
              <p className="text-sm text-destructive">
                Some details need attention. Check the messages above.
              </p>
            )}
            <Button
              type="submit"
              disabled={isSubmitting}
              size="lg"
              className="w-full cursor-pointer"
            >
              {isSubmitting ? "Saving..." : "Save activity"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={() => setStep(1)}
              className="w-full cursor-pointer"
            >
              Back: change field or activity type
            </Button>
          </div>
        </>
      )}
    </form>
  );
}
