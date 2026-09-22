import { FormInput, type ActivityFormApi } from "./form-field";

export function TillageFields({ form }: { form: ActivityFormApi }) {
  return (
    <>
      <FormInput
        form={form}
        name="tillage_depth_in"
        label="Tillage Depth (inches, optional)"
        hint="Leave blank if you didn't measure it. Add the implement under Equipment below."
        type="number"
        step="0.5"
        placeholder="6"
      />
    </>
  );
}
