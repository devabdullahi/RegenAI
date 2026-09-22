import { FormInput, type ActivityFormApi } from "./form-field";
import { yieldUnitForCrop } from "@/lib/crops";

/**
 * The yield unit follows the field's crop (display only — the API stores one
 * number per harvest with no unit column), so a cotton field is not asked for
 * bushels.
 */
export function HarvestFields({
  form,
  cropType,
}: {
  form: ActivityFormApi;
  /** Crop of the selected field; free text from the backend. */
  cropType?: string;
}) {
  const yieldUnit = yieldUnitForCrop(cropType);

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <FormInput
          form={form}
          name="yield_bu_ac"
          label={`Yield (${yieldUnit})`}
          required
          type="number"
          step="0.1"
          placeholder="210"
        />
        <FormInput
          form={form}
          name="moisture_pct"
          label="Moisture (%)"
          required
          type="number"
          step="0.1"
          placeholder="15.5"
        />
        <FormInput
          form={form}
          name="test_weight_lbs_bu"
          label="Test Weight (lbs/bu)"
          required
          type="number"
          step="0.1"
          placeholder="56.0"
        />
      </div>
      <FormInput
        form={form}
        name="elevator_ticket"
        label="Elevator Ticket Number (optional)"
        placeholder="As printed on the scale ticket"
      />
    </>
  );
}
