"use client";

import { useState, useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Trash2, Sprout, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { OnboardingProgress } from "@/components/shared/onboarding-progress";
import { CROP_OPTIONS, CROP_VALUES } from "@/lib/crops";
import { ONBOARDING_STORAGE_KEYS } from "@/lib/onboarding";
import { safeGetJSON, safeSetJSON } from "@/lib/storage";

// ---- Types ----
interface FieldEntry {
  id: string;
  name: string;
  acres: number;
  /**
   * Free text on the backend (`crop_type`, max 100 chars). New entries come
   * from CROP_OPTIONS; drafts saved earlier may hold any string.
   */
  crop_type: string;
  boundary_description: string;
}

// ---- Validation schema ----
const CROP_SET = new Set<string>(CROP_VALUES);

const fieldSchema = z.object({
  name: z.string().min(1, "Field name is required"),
  acres: z
    .number({ error: "Enter a valid number of acres" })
    .positive("Acres must be greater than 0"),
  crop_type: z
    .string({ error: "Please select a crop type" })
    .refine((value) => CROP_SET.has(value), "Please select a crop type"),
  boundary_description: z.string().optional(),
});

type FieldFormValues = z.infer<typeof fieldSchema>;

// ---- Helpers ----
function loadFields(): FieldEntry[] {
  const saved = safeGetJSON<unknown>(ONBOARDING_STORAGE_KEYS.fields, []);
  return Array.isArray(saved) ? (saved as FieldEntry[]) : [];
}

function saveFields(fields: FieldEntry[]) {
  safeSetJSON(ONBOARDING_STORAGE_KEYS.fields, fields);
}

export default function FieldSetupPage() {
  const router = useRouter();
  const [fields, setFields] = useState<FieldEntry[]>([]);
  const [noFieldsError, setNoFieldsError] = useState(false);

  // Hydrate from localStorage after mount
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is unavailable during prerender, so load saved fields after mount
    setFields(loadFields());
  }, []);

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    control,
    formState: { errors },
  } = useForm<FieldFormValues>({
    resolver: zodResolver(fieldSchema),
    defaultValues: {
      name: "",
      acres: undefined,
      crop_type: undefined,
      boundary_description: "",
    },
  });

  const selectedCrop = useWatch({ control, name: "crop_type" });

  function addField(data: FieldFormValues) {
    const newField: FieldEntry = {
      id: crypto.randomUUID(),
      name: data.name,
      acres: data.acres,
      crop_type: data.crop_type,
      boundary_description: data.boundary_description ?? "",
    };
    const updated = [...fields, newField];
    setFields(updated);
    saveFields(updated);
    setNoFieldsError(false);
    reset();
  }

  function removeField(id: string) {
    const updated = fields.filter((f) => f.id !== id);
    setFields(updated);
    saveFields(updated);
  }

  function handleNext() {
    if (fields.length === 0) {
      setNoFieldsError(true);
      return;
    }
    router.push("/onboarding/practices");
  }

  return (
    <div className="flex flex-col gap-6">
      <OnboardingProgress currentStep={3} />

      <div className="border-b-2 border-rule-strong pb-4">
        <h1 className="font-heading text-2xl font-bold">Add your fields</h1>
        <p className="mt-1 text-base text-muted-foreground">
          Add each field one at a time. You can add more fields after setup.
        </p>
      </div>

      {/* Add field form */}
      <Card>
        <CardHeader>
          <CardTitle className="font-heading text-lg">New field</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleSubmit(addField)}
            noValidate
            className="flex flex-col gap-5"
          >
            {/* Field name */}
            <div className="flex flex-col gap-2">
              <Label htmlFor="field-name">
                Field name
              </Label>
              <Input
                id="field-name"
                type="text"
                placeholder="e.g. North 40, Home Quarter"
                aria-describedby={errors.name ? "field-name-error" : undefined}
                aria-invalid={!!errors.name}
               
                {...register("name")}
              />
              {errors.name && (
                <p
                  id="field-name-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.name.message}
                </p>
              )}
            </div>

            {/* Acres */}
            <div className="flex flex-col gap-2">
              <Label htmlFor="field-acres">
                Acres
              </Label>
              <Input
                id="field-acres"
                type="number"
                placeholder="e.g. 120"
                inputMode="decimal"
                min={0}
                aria-describedby={errors.acres ? "field-acres-error" : undefined}
                aria-invalid={!!errors.acres}
               
                {...register("acres", { valueAsNumber: true })}
              />
              {errors.acres && (
                <p
                  id="field-acres-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.acres.message}
                </p>
              )}
            </div>

            {/* Primary crop */}
            <div className="flex flex-col gap-2">
              <Label
                htmlFor="field-crop-trigger"
               
              >
                Primary crop
              </Label>
              <Select
                value={selectedCrop}
                onValueChange={(val) =>
                  val !== null &&
                  setValue("crop_type", val, { shouldValidate: true })
                }
              >
                <SelectTrigger
                  id="field-crop-trigger"
                  aria-describedby={
                    errors.crop_type ? "field-crop-error" : undefined
                  }
                  aria-invalid={!!errors.crop_type}
                  className="h-12 w-full text-base px-4"
                >
                  <SelectValue placeholder="Select a crop" />
                </SelectTrigger>
                <SelectContent>
                  {CROP_OPTIONS.map((crop) => (
                    <SelectItem
                      key={crop.value}
                      value={crop.value}
                      className="text-base py-3"
                    >
                      {crop.value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.crop_type && (
                <p
                  id="field-crop-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.crop_type.message}
                </p>
              )}
            </div>

            {/* Boundary description (optional) */}
            <div className="flex flex-col gap-2">
              <Label
                htmlFor="field-boundary"
               
              >
                Location description{" "}
                <span className="text-muted-foreground font-normal">
                  (optional)
                </span>
              </Label>
              <Textarea
                id="field-boundary"
                placeholder="Section/Township/Range — or skip for now"
                rows={2}
                className="text-base resize-none px-4 py-3"
                {...register("boundary_description")}
              />
            </div>

            <Button
              type="submit"
              variant="outline"
              className="h-12 w-full text-base font-semibold border-primary text-primary hover:bg-primary/5 cursor-pointer"
            >
              <Plus className="h-4 w-4 mr-2" aria-hidden="true" />
              Add This Field
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Added fields list */}
      {fields.length > 0 && (
        <div className="flex flex-col gap-3">
          <Separator />
          <h2 className="font-heading text-lg font-semibold">
            Added fields ({fields.length})
          </h2>
          <ul className="flex flex-col gap-3" aria-label="Fields you have added">
            {fields.map((field) => (
              <li key={field.id}>
                <Card>
                  <CardContent className="flex items-start justify-between gap-4 py-4">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                        <Sprout
                          className="h-4 w-4 text-primary"
                          aria-hidden="true"
                        />
                      </div>
                      <div>
                        <p className="text-base font-semibold">{field.name}</p>
                        <div className="mt-1 flex flex-wrap gap-2">
                          <Badge variant="secondary" className="text-sm">
                            {field.acres} acres
                          </Badge>
                          <Badge variant="outline" className="text-sm">
                            {field.crop_type}
                          </Badge>
                        </div>
                        {field.boundary_description && (
                          <p className="mt-1 text-sm text-muted-foreground">
                            {field.boundary_description}
                          </p>
                        )}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeField(field.id)}
                      aria-label={`Remove ${field.name}`}
                      className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors cursor-pointer"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* No fields validation message */}
      {noFieldsError && (
        <p role="alert" className="text-sm text-destructive">
          Add at least one field before continuing.
        </p>
      )}

      {/* Navigation */}
      <div className="flex flex-col gap-3 pt-2">
        <Button
          type="button"
          onClick={handleNext}
          size="lg"
          className="w-full cursor-pointer"
        >
          Next: Your Practices
        </Button>

        <Link
          href="/onboarding/farm"
          className="flex items-center justify-center gap-1.5 text-base text-muted-foreground hover:text-foreground transition-colors min-h-[48px] cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back
        </Link>
      </div>
    </div>
  );
}
