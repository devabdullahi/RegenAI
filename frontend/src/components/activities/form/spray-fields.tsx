import { useWatch } from "react-hook-form";
import { RestrictedUseBadge } from "../restricted-use-badge";
import { FormInput, ToggleCard, type ActivityFormApi } from "./form-field";

export function SprayFields({ form }: { form: ActivityFormApi }) {
  const restrictedUse = useWatch({ control: form.control, name: "restricted_use" }) === true;

  return (
    <>
      <FormInput
        form={form}
        name="product_name"
        label="Product Name"
        required
        placeholder="e.g. Roundup PowerMAX"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormInput
          form={form}
          name="epa_reg_number"
          label="EPA Registration Number"
          required
          hint="Found on the product label"
          placeholder="e.g. 524-549"
        />
        <FormInput
          form={form}
          name="rate_oz_ac"
          label="Application Rate (oz/ac)"
          required
          type="number"
          step="0.01"
          placeholder="32"
        />
      </div>
      <FormInput
        form={form}
        name="target_pest"
        label="Target Pest or Problem"
        required
        placeholder="e.g. Waterhemp, Soybean Aphid"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormInput
          form={form}
          name="wind_mph"
          label="Wind Speed (mph)"
          required
          type="number"
          step="0.5"
          placeholder="7"
        />
        <FormInput
          form={form}
          name="temp_f"
          label="Temperature (°F)"
          required
          type="number"
          placeholder="72"
        />
      </div>

      <ToggleCard
        id="restricted_use"
        title="Restricted use pesticide?"
        description="Check the label. Restricted use products require a certified applicator."
        checked={restrictedUse}
        onCheckedChange={(checked) =>
          form.setValue("restricted_use", checked, { shouldValidate: form.formState.isSubmitted })
        }
      >
        <div className="mt-4 space-y-4 border-t border-border pt-4">
          <div className="flex flex-wrap items-center gap-2">
            <RestrictedUseBadge />
            <p className="text-sm text-muted-foreground">
              Applicator info is required for this record.
            </p>
          </div>
          <FormInput
            form={form}
            name="applicator_name"
            label="Applicator Name"
            required
            placeholder="Full name of certified applicator"
          />
          <FormInput
            form={form}
            name="applicator_cert_number"
            label="Applicator Certification Number"
            required
            placeholder="As shown on the applicator's license"
          />
        </div>
      </ToggleCard>
    </>
  );
}
