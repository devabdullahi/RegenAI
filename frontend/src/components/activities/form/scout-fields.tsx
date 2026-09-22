import { useWatch } from "react-hook-form";
import {
  severityLabel,
  severityTone,
  toneTextClasses,
  type Severity,
} from "@/lib/status-styles";
import { cn } from "@/lib/utils";
import {
  FormField,
  FormInput,
  RequiredMark,
  ToggleCard,
  describedBy,
  fieldError,
  selectClasses,
  type ActivityFormApi,
} from "./form-field";

const SEVERITIES: readonly Severity[] = ["none", "low", "moderate", "high", "critical"];

export function ScoutFields({ form }: { form: ActivityFormApi }) {
  const { errors, isSubmitted } = form.formState;
  const thresholdExceeded =
    useWatch({ control: form.control, name: "threshold_exceeded" }) === true;
  const severity = useWatch({ control: form.control, name: "severity" });
  const pestTypeError = fieldError(errors, "pest_type");
  const severityError = fieldError(errors, "severity");

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormField label="Type of Problem" htmlFor="pest_type" required error={pestTypeError}>
          <select
            id="pest_type"
            className={selectClasses}
            aria-invalid={pestTypeError ? true : undefined}
            aria-describedby={describedBy("pest_type", { error: pestTypeError })}
            {...form.register("pest_type")}
          >
            <option value="insect">Insect</option>
            <option value="disease">Disease</option>
            <option value="weed">Weed</option>
            <option value="other">Other</option>
          </select>
        </FormField>
        <FormInput
          form={form}
          name="pest_name"
          label="Pest or Problem Name"
          required
          placeholder="e.g. Soybean Aphid, Gray Leaf Spot"
        />
      </div>

      <div className="space-y-1.5">
        <p
          id="severity-label"
          className="flex items-center font-mono text-xs font-medium tracking-[0.1em] text-muted-foreground uppercase"
        >
          Pressure Level
          <RequiredMark />
        </p>
        <div
          role="group"
          aria-labelledby="severity-label"
          aria-describedby={describedBy("severity", { error: severityError })}
          className="flex flex-wrap gap-2"
        >
          {SEVERITIES.map((level) => {
            const selected = severity === level;
            return (
              <button
                key={level}
                type="button"
                onClick={() =>
                  form.setValue("severity", level, { shouldValidate: isSubmitted })
                }
                aria-pressed={selected}
                className={cn(
                  "min-h-12 min-w-20 flex-1 rounded-sm border px-2 py-2 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                  selected
                    ? cn(toneTextClasses[severityTone[level]], "border-current bg-muted font-semibold")
                    : "border-border bg-card text-muted-foreground hover:bg-muted"
                )}
              >
                {severityLabel[level]}
              </button>
            );
          })}
        </div>
        {severityError && (
          <p id="severity-error" className="text-sm text-destructive" role="alert">
            {severityError}
          </p>
        )}
      </div>

      <ToggleCard
        id="threshold_exceeded"
        title="Did this exceed the action threshold?"
        description="The point where treatment becomes cost-effective."
        checked={thresholdExceeded}
        onCheckedChange={(checked) =>
          form.setValue("threshold_exceeded", checked, { shouldValidate: isSubmitted })
        }
      />

      <FormInput
        form={form}
        name="action_taken"
        label="Action Taken (optional)"
        placeholder="e.g. Scheduled foliar spray for next week"
      />
    </>
  );
}
