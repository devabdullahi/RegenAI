import { FormInput, type ActivityFormApi } from "./form-field";

export function CoverCropFields({ form }: { form: ActivityFormApi }) {
  return (
    <FormInput
      form={form}
      name="cover_crop_species"
      label="Cover Crop Species"
      required
      hint="List each species in the mix"
      placeholder="e.g. Cereal rye, crimson clover"
    />
  );
}
