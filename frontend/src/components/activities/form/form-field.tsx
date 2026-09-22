/**
 * Shared building blocks for the activity form sections: labelled field
 * wrapper, text/number input, and a yes/no switch.
 *
 * A field is a blank on a printed form: a mono small-caps caption above a
 * ruled box, with the helper line set small underneath.
 */

import type { ReactNode } from "react";
import type { FieldErrors, UseFormReturn } from "react-hook-form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { ActivityFormValues } from "./schemas";

export type ActivityFormApi = UseFormReturn<ActivityFormValues>;

/** Native select styled to match the Input blank. */
export const selectClasses =
  "h-12 w-full rounded-sm border border-input bg-card px-3 text-base text-foreground transition-colors outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40 aria-invalid:border-destructive aria-invalid:ring-2 aria-invalid:ring-destructive/30";

/** Error message for a field, if any. */
export function fieldError(
  errors: FieldErrors<ActivityFormValues>,
  name: string
): string | undefined {
  const message = errors[name]?.message;
  return typeof message === "string" ? message : undefined;
}

/** aria-describedby value for a field's hint and error, or undefined. */
export function describedBy(
  id: string,
  { hint, error }: { hint?: string; error?: string }
): string | undefined {
  const ids = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean);
  return ids.length > 0 ? ids.join(" ") : undefined;
}

export function RequiredMark() {
  return (
    <span className="ml-1 text-destructive" aria-hidden="true">
      *
    </span>
  );
}

export function FormField({
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
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>
        {label}
        {required && <RequiredMark />}
      </Label>
      {children}
      {hint && (
        <p id={`${htmlFor}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${htmlFor}-error`} className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

interface FormInputProps {
  form: ActivityFormApi;
  name: string;
  label: string;
  required?: boolean;
  hint?: string;
  placeholder?: string;
  type?: "text" | "number";
  step?: string;
}

/** Text or number input registered with the form, with inline error. */
export function FormInput({
  form,
  name,
  label,
  required,
  hint,
  placeholder,
  type = "text",
  step,
}: FormInputProps) {
  const error = fieldError(form.formState.errors, name);
  const isNumber = type === "number";
  return (
    <FormField label={label} htmlFor={name} required={required} hint={hint} error={error}>
      <Input
        id={name}
        type={type}
        step={step}
        inputMode={isNumber ? "decimal" : undefined}
        placeholder={placeholder}
        // Figures are set in mono so a column of rates and depths lines up.
        className={cn("h-12 text-base", isNumber && "font-mono tabular-nums")}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(name, { hint, error })}
        {...form.register(name)}
      />
    </FormField>
  );
}

interface ToggleCardProps {
  id: string;
  title: string;
  description: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  /** Rendered below the switch while checked. */
  children?: ReactNode;
}

/** A yes/no question with a switch; the switch has a 48px hit area. */
export function ToggleCard({
  id,
  title,
  description,
  checked,
  onCheckedChange,
  children,
}: ToggleCardProps) {
  return (
    <div className="border border-border bg-card px-4 py-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1">
          <p id={`${id}-title`} className="text-base font-medium text-foreground">
            {title}
          </p>
          <p id={`${id}-description`} className="mt-0.5 text-sm text-muted-foreground">
            {description}
          </p>
        </div>
        <button
          id={id}
          type="button"
          role="switch"
          aria-checked={checked}
          aria-labelledby={`${id}-title`}
          aria-describedby={`${id}-description`}
          onClick={() => onCheckedChange(!checked)}
          className="flex min-h-12 min-w-12 shrink-0 cursor-pointer items-center justify-center gap-2 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {/* The word carries the answer; the switch only shows it. */}
          <span
            className="font-mono text-xs font-medium tracking-[0.1em] text-foreground uppercase"
            aria-hidden="true"
          >
            {checked ? "Yes" : "No"}
          </span>
          <span
            aria-hidden="true"
            className={cn(
              "relative inline-flex h-7 w-14 items-center border transition-colors",
              checked ? "border-destructive bg-destructive" : "border-border bg-muted"
            )}
          >
            <span
              className={cn(
                "inline-block h-5 w-5 bg-card transition-transform",
                checked ? "translate-x-8" : "translate-x-1"
              )}
            />
          </span>
        </button>
      </div>
      {checked && children}
    </div>
  );
}
