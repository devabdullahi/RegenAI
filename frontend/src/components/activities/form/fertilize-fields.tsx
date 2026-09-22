import {
  FormField,
  FormInput,
  describedBy,
  fieldError,
  selectClasses,
  type ActivityFormApi,
} from "./form-field";

export function FertilizeFields({ form }: { form: ActivityFormApi }) {
  const methodError = fieldError(form.formState.errors, "method");

  return (
    <>
      <FormInput
        form={form}
        name="product_name"
        label="Product Name"
        required
        placeholder="e.g. UAN 32% Solution"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <FormInput
          form={form}
          name="n_lbs_ac"
          label="Nitrogen, N (lbs/ac)"
          required
          type="number"
          placeholder="80"
        />
        <FormInput
          form={form}
          name="p_lbs_ac"
          label="Phosphorus, P (lbs/ac)"
          required
          type="number"
          placeholder="40"
        />
        <FormInput
          form={form}
          name="k_lbs_ac"
          label="Potassium, K (lbs/ac)"
          required
          type="number"
          placeholder="60"
        />
      </div>
      <FormField label="Application Method" htmlFor="method" required error={methodError}>
        <select
          id="method"
          className={selectClasses}
          aria-invalid={methodError ? true : undefined}
          aria-describedby={describedBy("method", { error: methodError })}
          {...form.register("method")}
        >
          <option value="broadcast">Broadcast (spread over field)</option>
          <option value="sidedress">Sidedress (between rows)</option>
          <option value="inject">Inject (knife into soil)</option>
          <option value="foliar">Foliar (sprayed on leaves)</option>
        </select>
      </FormField>
    </>
  );
}
