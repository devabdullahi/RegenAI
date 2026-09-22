"use client";

import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { OnboardingProgress } from "@/components/shared/onboarding-progress";
import {
  ONBOARDING_STORAGE_KEYS,
  STATE_FIPS_PREFIX,
  US_STATES,
} from "@/lib/onboarding";
import { safeGetJSON, safeSetJSON } from "@/lib/storage";

// ---- Validation schema ----
const farmSchema = z
  .object({
    name: z.string().trim().min(1, "Farm name is required").max(200, "Keep the farm name under 200 characters"),
    state: z.string().min(1, "Please select your state or territory"),
    county: z.string().trim().min(1, "County is required"),
    county_fips: z
      .string()
      .trim()
      .regex(/^\d{5}$/, "Enter your 5-digit county code (numbers only)"),
    total_acres: z
      .number({ error: "Enter a valid number of acres" })
      .positive("Acres must be greater than 0"),
  })
  .refine(
    (d) => !d.state || !STATE_FIPS_PREFIX[d.state] || d.county_fips.startsWith(STATE_FIPS_PREFIX[d.state]!),
    {
      message:
        "That county code doesn't match the state you picked. Double-check both.",
      path: ["county_fips"],
    }
  );

type FarmFormValues = z.infer<typeof farmSchema>;

export default function FarmBasicsPage() {
  const router = useRouter();

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    control,
    formState: { errors, isSubmitting },
  } = useForm<FarmFormValues>({
    resolver: zodResolver(farmSchema),
    defaultValues: {
      name: "",
      state: "",
      county: "",
      county_fips: "",
      total_acres: undefined,
    },
  });

  // Pre-populate if the user came back to this step. Read storage in an effect,
  // not during render, so server and client markup match.
  useEffect(() => {
    const saved = safeGetJSON<Partial<FarmFormValues> | null>(
      ONBOARDING_STORAGE_KEYS.farm,
      null
    );
    if (!saved || typeof saved !== "object") return;
    reset({
      name: saved.name ?? "",
      state: saved.state ?? "",
      county: saved.county ?? "",
      county_fips: saved.county_fips ?? "",
      total_acres: saved.total_acres ?? undefined,
    });
  }, [reset]);

  const selectedState = useWatch({ control, name: "state" });
  const countyName = useWatch({ control, name: "county" });

  function onSubmit(data: FarmFormValues) {
    safeSetJSON(ONBOARDING_STORAGE_KEYS.farm, data);
    router.push("/onboarding/fields");
  }

  return (
    <div className="flex flex-col gap-6">
      <OnboardingProgress currentStep={2} />

      <div className="border-b-2 border-rule-strong pb-4">
        <h1 className="font-heading text-2xl font-bold">Tell us about your farm</h1>
        <p className="mt-1 text-base text-muted-foreground">
          Just the basics — you can always update these later.
        </p>
      </div>

      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
        className="flex flex-col gap-5"
      >
        {/* Farm name */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="name">
            Farm name
          </Label>
          <Input
            id="name"
            type="text"
            placeholder="e.g. Sunrise Acres"
            autoComplete="organization"
            aria-describedby={errors.name ? "name-error" : undefined}
            aria-invalid={!!errors.name}
           
            {...register("name")}
          />
          {errors.name && (
            <p id="name-error" role="alert" className="text-sm text-destructive">
              {errors.name.message}
            </p>
          )}
        </div>

        {/* State */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="state-trigger">
            State or territory
          </Label>
          <Select
            value={selectedState}
            onValueChange={(val) =>
              val !== null && setValue("state", val, { shouldValidate: true })
            }
          >
            <SelectTrigger
              id="state-trigger"
              aria-describedby={errors.state ? "state-error" : undefined}
              aria-invalid={!!errors.state}
              className="h-12 w-full text-base px-4"
            >
              <SelectValue placeholder="Select your state or territory" />
            </SelectTrigger>
            <SelectContent>
              {US_STATES.map(({ code, name }) => (
                <SelectItem key={code} value={code} className="text-base py-3">
                  {name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors.state && (
            <p id="state-error" role="alert" className="text-sm text-destructive">
              {errors.state.message}
            </p>
          )}
        </div>

        {/* County */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="county">
            County
          </Label>
          <Input
            id="county"
            type="text"
            placeholder="e.g. Story County"
            aria-describedby={errors.county ? "county-error" : undefined}
            aria-invalid={!!errors.county}
           
            {...register("county")}
          />
          {errors.county && (
            <p id="county-error" role="alert" className="text-sm text-destructive">
              {errors.county.message}
            </p>
          )}
        </div>

        {/* County FIPS code */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="county_fips">
            County code
          </Label>
          <Input
            id="county_fips"
            className="font-mono"
            type="text"
            placeholder={
              selectedState && STATE_FIPS_PREFIX[selectedState]
                ? `e.g. ${STATE_FIPS_PREFIX[selectedState]}169`
                : "5 digits, e.g. 19169"
            }
            inputMode="numeric"
            maxLength={5}
            autoComplete="off"
            aria-describedby={
              errors.county_fips ? "county-fips-help county-fips-error" : "county-fips-help"
            }
            aria-invalid={!!errors.county_fips}
           
            {...register("county_fips")}
          />
          <p id="county-fips-help" className="text-sm text-muted-foreground">
            The 5-digit FIPS number for your county. It helps us find your local
            soil and weather. Your county Farm Service Agency office or a quick
            search for &quot;{countyName || "your county"} FIPS code&quot; will have it.
          </p>
          {errors.county_fips && (
            <p id="county-fips-error" role="alert" className="text-sm text-destructive">
              {errors.county_fips.message}
            </p>
          )}
        </div>

        {/* Total acres */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="total_acres">
            Total acres
          </Label>
          <Input
            id="total_acres"
            className="font-mono"
            type="number"
            placeholder="e.g. 480"
            inputMode="decimal"
            min={0}
            aria-describedby={errors.total_acres ? "acres-error" : undefined}
            aria-invalid={!!errors.total_acres}
           
            {...register("total_acres", { valueAsNumber: true })}
          />
          {errors.total_acres && (
            <p id="acres-error" role="alert" className="text-sm text-destructive">
              {errors.total_acres.message}
            </p>
          )}
        </div>

        {/* Navigation */}
        <div className="flex flex-col gap-3 pt-2">
          <Button
            type="submit"
            disabled={isSubmitting}
            size="lg"
          className="w-full cursor-pointer"
          >
            Next: Add Your Fields
          </Button>

          <Link
            href="/onboarding"
            className="flex items-center justify-center gap-1.5 text-base text-muted-foreground hover:text-foreground transition-colors min-h-[48px] cursor-pointer"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Back
          </Link>
        </div>
      </form>
    </div>
  );
}
