"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { OnboardingProgress } from "@/components/shared/onboarding-progress";

// ---- Practice definitions ----
const PRACTICES = [
  {
    id: "cover_crops",
    label: "Cover crops",
    description:
      "Plant non-cash crops between main crop seasons to protect and improve your soil",
  },
  {
    id: "no_till",
    label: "No-till",
    description:
      "Skip tillage entirely — soil stays undisturbed, reducing erosion and fuel costs",
  },
  {
    id: "reduced_till",
    label: "Reduced-till",
    description:
      "Minimize tillage passes to preserve soil structure while still managing residue",
  },
  {
    id: "crop_rotation",
    label: "Crop rotation",
    description:
      "Rotate between different crops each season to break pest cycles and build soil health",
  },
  {
    id: "nutrient_management",
    label: "Nutrient management plan",
    description:
      "Apply the right nutrients at the right rate, time, and place based on soil testing",
  },
  {
    id: "manure_application",
    label: "Manure application",
    description:
      "Use manure as a nutrient source to reduce synthetic fertilizer use",
  },
  {
    id: "integrated_pest",
    label: "Integrated pest management",
    description:
      "Combine scouting, thresholds, and targeted treatments to reduce pesticide use",
  },
  {
    id: "conservation_cover",
    label: "Conservation cover",
    description:
      "Permanent grass or native plantings on erodible ground, waterways, or buffer strips",
  },
] as const;

type PracticeId = (typeof PRACTICES)[number]["id"];

// ---- Helpers ----
function loadPractices(): PracticeId[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(
      localStorage.getItem("onboarding_practices") ?? "[]"
    ) as PracticeId[];
  } catch {
    return [];
  }
}

function savePractices(practices: PracticeId[]) {
  localStorage.setItem("onboarding_practices", JSON.stringify(practices));
}

export default function PracticesPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<PracticeId[]>([]);

  // Hydrate from localStorage after mount
  useEffect(() => {
    setSelected(loadPractices());
  }, []);

  function toggle(id: PracticeId) {
    setSelected((prev) => {
      const next = prev.includes(id)
        ? prev.filter((p) => p !== id)
        : [...prev, id];
      savePractices(next);
      return next;
    });
  }

  function handleNext() {
    savePractices(selected);
    router.push("/onboarding/goals");
  }

  return (
    <div className="flex flex-col gap-6">
      <OnboardingProgress currentStep={4} />

      <div>
        <h1 className="font-heading text-2xl font-bold">
          What are you already doing?
        </h1>
        <p className="mt-1 text-base text-muted-foreground">
          Select everything that applies to your operation. This helps us tailor
          your recommendations and find programs you already qualify for.
        </p>
      </div>

      {/* Practice checklist */}
      <fieldset className="flex flex-col gap-3">
        <legend className="sr-only">Current farming practices</legend>
        {PRACTICES.map((practice) => {
          const isChecked = selected.includes(practice.id);
          return (
            <button
              key={practice.id}
              type="button"
              role="checkbox"
              aria-checked={isChecked}
              onClick={() => toggle(practice.id)}
              className={cn(
                "group flex w-full items-start gap-4 rounded-xl border-2 p-4 text-left transition-all duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                isChecked
                  ? "border-primary bg-primary/5"
                  : "border-border bg-card hover:border-primary/40 hover:bg-primary/5"
              )}
              style={{ minHeight: "64px" }}
            >
              {/* Custom checkbox indicator */}
              <span
                aria-hidden="true"
                className={cn(
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border-2 transition-colors duration-150",
                  isChecked
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-input bg-background group-hover:border-primary/60"
                )}
              >
                {isChecked && <Check className="h-3.5 w-3.5" />}
              </span>

              {/* Label + description */}
              <span className="flex flex-col gap-0.5">
                <span className="text-base font-semibold leading-snug">
                  {practice.label}
                </span>
                <span className="text-sm text-muted-foreground leading-snug">
                  {practice.description}
                </span>
              </span>
            </button>
          );
        })}
      </fieldset>

      {/* "None yet" helper text */}
      {selected.length === 0 && (
        <p className="text-sm text-muted-foreground -mt-2">
          No practices selected — that&apos;s okay. We&apos;ll suggest where to
          start.
        </p>
      )}

      {/* Navigation */}
      <div className="flex flex-col gap-3 pt-2">
        <Button
          type="button"
          onClick={handleNext}
          className="h-12 w-full bg-accent text-accent-foreground hover:bg-accent/90 text-base font-semibold cursor-pointer"
        >
          Next: Set Your Goal
        </Button>

        <Link
          href="/onboarding/fields"
          className="flex items-center justify-center gap-1.5 text-base text-muted-foreground hover:text-foreground transition-colors min-h-[48px] cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back
        </Link>
      </div>
    </div>
  );
}
