import { RuleHead } from "@/components/shared/record";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  FormField,
  FormInput,
  describedBy,
  fieldError,
  type ActivityFormApi,
} from "./form-field";

interface CommonFieldsProps {
  form: ActivityFormApi;
  /** "Other" activities have no type-specific fields, so notes are required. */
  notesRequired: boolean;
}

export function CommonFields({ form, notesRequired }: CommonFieldsProps) {
  const { errors } = form.formState;
  const costError = fieldError(errors, "cost_per_acre");
  const notesError = fieldError(errors, "notes");

  return (
    <section aria-label="Additional info" className="space-y-5">
      <RuleHead label="Additional info" />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormInput
          form={form}
          name="acres"
          label="Total Acres"
          required
          type="number"
          step="0.1"
        />
        <FormInput
          form={form}
          name="operator"
          label="Operator"
          required
          placeholder="Who did this work?"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormInput
          form={form}
          name="equipment"
          label="Equipment Used (optional)"
          placeholder="e.g. John Deere 1775NT Planter"
        />
        <FormField label="Cost per Acre (optional)" htmlFor="cost_per_acre" error={costError}>
          <div className="relative">
            <span
              className="absolute top-1/2 left-3 -translate-y-1/2 font-mono text-muted-foreground"
              aria-hidden="true"
            >
              $
            </span>
            <Input
              id="cost_per_acre"
              type="number"
              step="0.01"
              inputMode="decimal"
              placeholder="0.00"
              className="h-12 pl-7 font-mono text-base tabular-nums"
              aria-invalid={costError ? true : undefined}
              aria-describedby={describedBy("cost_per_acre", { error: costError })}
              {...form.register("cost_per_acre")}
            />
          </div>
        </FormField>
      </div>

      <FormField
        label={notesRequired ? "What did you do?" : "Notes (optional)"}
        htmlFor="notes"
        required={notesRequired}
        error={notesError}
      >
        <Textarea
          id="notes"
          placeholder="Any other details worth recording..."
          className="min-h-20 text-base"
          aria-invalid={notesError ? true : undefined}
          aria-describedby={describedBy("notes", { error: notesError })}
          {...form.register("notes")}
        />
      </FormField>
    </section>
  );
}
