import { FormInput, type ActivityFormApi } from "./form-field";

export function PlantFields({ form }: { form: ActivityFormApi }) {
  return (
    <>
      <FormInput
        form={form}
        name="variety"
        label="Seed Variety"
        required
        placeholder="e.g. DeKalb DKC52-70RIB"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <FormInput
          form={form}
          name="seeding_rate_kac"
          label="Seeding Rate (K/ac)"
          required
          hint="Thousands of seeds per acre"
          type="number"
          step="0.1"
          placeholder="34.5"
        />
        <FormInput
          form={form}
          name="row_spacing_in"
          label="Row Spacing (inches)"
          required
          type="number"
          placeholder="30"
        />
        <FormInput
          form={form}
          name="depth_in"
          label="Planting Depth (inches)"
          required
          type="number"
          step="0.25"
          placeholder="2.0"
        />
      </div>
      <FormInput
        form={form}
        name="seed_treatment"
        label="Seed Treatment (optional)"
        placeholder="e.g. fungicide + insecticide"
      />
    </>
  );
}
