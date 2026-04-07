"use client";

import { useForm } from "react-hook-form";
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

// ---- Validation schema ----
const farmSchema = z.object({
  name: z.string().min(1, "Farm name is required"),
  state: z.string().min(1, "Please select your state"),
  county: z.string().min(1, "County is required"),
  total_acres: z
    .number({ error: "Enter a valid number of acres" })
    .positive("Acres must be greater than 0"),
});

type FarmFormValues = z.infer<typeof farmSchema>;

// ---- Full list of US states ----
const US_STATES = [
  ["AL", "Alabama"],
  ["AK", "Alaska"],
  ["AZ", "Arizona"],
  ["AR", "Arkansas"],
  ["CA", "California"],
  ["CO", "Colorado"],
  ["CT", "Connecticut"],
  ["DE", "Delaware"],
  ["FL", "Florida"],
  ["GA", "Georgia"],
  ["HI", "Hawaii"],
  ["ID", "Idaho"],
  ["IL", "Illinois"],
  ["IN", "Indiana"],
  ["IA", "Iowa"],
  ["KS", "Kansas"],
  ["KY", "Kentucky"],
  ["LA", "Louisiana"],
  ["ME", "Maine"],
  ["MD", "Maryland"],
  ["MA", "Massachusetts"],
  ["MI", "Michigan"],
  ["MN", "Minnesota"],
  ["MS", "Mississippi"],
  ["MO", "Missouri"],
  ["MT", "Montana"],
  ["NE", "Nebraska"],
  ["NV", "Nevada"],
  ["NH", "New Hampshire"],
  ["NJ", "New Jersey"],
  ["NM", "New Mexico"],
  ["NY", "New York"],
  ["NC", "North Carolina"],
  ["ND", "North Dakota"],
  ["OH", "Ohio"],
  ["OK", "Oklahoma"],
  ["OR", "Oregon"],
  ["PA", "Pennsylvania"],
  ["RI", "Rhode Island"],
  ["SC", "South Carolina"],
  ["SD", "South Dakota"],
  ["TN", "Tennessee"],
  ["TX", "Texas"],
  ["UT", "Utah"],
  ["VT", "Vermont"],
  ["VA", "Virginia"],
  ["WA", "Washington"],
  ["WV", "West Virginia"],
  ["WI", "Wisconsin"],
  ["WY", "Wyoming"],
] as const;

export default function FarmBasicsPage() {
  const router = useRouter();

  // Pre-populate from localStorage if the user went back
  const saved =
    typeof window !== "undefined"
      ? JSON.parse(localStorage.getItem("onboarding_farm") ?? "null")
      : null;

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FarmFormValues>({
    resolver: zodResolver(farmSchema),
    defaultValues: {
      name: saved?.name ?? "",
      state: saved?.state ?? "",
      county: saved?.county ?? "",
      total_acres: saved?.total_acres ?? undefined,
    },
  });

  const selectedState = watch("state");

  function onSubmit(data: FarmFormValues) {
    localStorage.setItem("onboarding_farm", JSON.stringify(data));
    router.push("/onboarding/fields");
  }

  return (
    <div className="flex flex-col gap-6">
      <OnboardingProgress currentStep={2} />

      <div>
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
          <Label htmlFor="name" className="text-base font-medium">
            Farm name
          </Label>
          <Input
            id="name"
            type="text"
            placeholder="e.g. Sunrise Acres"
            autoComplete="organization"
            aria-describedby={errors.name ? "name-error" : undefined}
            aria-invalid={!!errors.name}
            className="h-12 text-base px-4"
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
          <Label htmlFor="state-trigger" className="text-base font-medium">
            State
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
              <SelectValue placeholder="Select your state" />
            </SelectTrigger>
            <SelectContent>
              {US_STATES.map(([abbr, name]) => (
                <SelectItem key={abbr} value={abbr} className="text-base py-3">
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
          <Label htmlFor="county" className="text-base font-medium">
            County
          </Label>
          <Input
            id="county"
            type="text"
            placeholder="e.g. Story County"
            aria-describedby={errors.county ? "county-error" : undefined}
            aria-invalid={!!errors.county}
            className="h-12 text-base px-4"
            {...register("county")}
          />
          {errors.county && (
            <p id="county-error" role="alert" className="text-sm text-destructive">
              {errors.county.message}
            </p>
          )}
        </div>

        {/* Total acres */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="total_acres" className="text-base font-medium">
            Total acres
          </Label>
          <Input
            id="total_acres"
            type="number"
            placeholder="e.g. 480"
            inputMode="decimal"
            min={0}
            aria-describedby={errors.total_acres ? "acres-error" : undefined}
            aria-invalid={!!errors.total_acres}
            className="h-12 text-base px-4"
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
            className="h-12 w-full bg-accent text-accent-foreground hover:bg-accent/90 text-base font-semibold cursor-pointer"
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
