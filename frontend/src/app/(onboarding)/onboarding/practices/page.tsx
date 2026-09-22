"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { OnboardingProgress } from "@/components/shared/onboarding-progress";
import {
  ONBOARDING_PRACTICES,
  ONBOARDING_STORAGE_KEYS,
  type OnboardingPracticeId,
} from "@/lib/onboarding";
import { safeGetJSON, safeSetJSON } from "@/lib/storage";

// ---- Helpers ----
function loadPractices(): OnboardingPracticeId[] {
  const saved = safeGetJSON<unknown>(ONBOARDING_STORAGE_KEYS.practices, []);
  return Array.isArray(saved) ? (saved as OnboardingPracticeId[]) : [];
}

function savePractices(practices: OnboardingPracticeId[]) {
  safeSetJSON(ONBOARDING_STORAGE_KEYS.practices, practices);
}

export default function PracticesPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<OnboardingPracticeId[]>([]);

  // Hydrate from localStorage after mount
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is unavailable during prerender, so load saved choices after mount
    setSelected(loadPractices());
  }, []);

  function toggle(id: OnboardingPracticeId) {
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

      <div className="border-b-2 border-rule-strong pb-4">
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
        {ONBOARDING_PRACTICES.map((practice) => {
          const isChecked = selected.includes(practice.id);
          return (
            <button
              key={practice.id}
              type="button"
              role="checkbox"
              aria-checked={isChecked}
              onClick={() => toggle(practice.id)}
              className={cn(
                "group flex w-full cursor-pointer items-start gap-4 border border-border bg-card p-4 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                isChecked
                  ? "border-l-[3px] border-l-primary"
                  : "hover:border-primary/50"
              )}
              style={{ minHeight: "64px" }}
            >
              {/* Custom checkbox indicator */}
              <span
                aria-hidden="true"
                className={cn(
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center border border-input transition-colors",
                  isChecked
                    ? "border-primary bg-primary text-primary-foreground"
                    : "bg-card group-hover:border-primary/60"
                )}
              >
                {isChecked && <Check className="h-3.5 w-3.5" aria-hidden="true" />}
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
          size="lg"
          className="w-full cursor-pointer"
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
