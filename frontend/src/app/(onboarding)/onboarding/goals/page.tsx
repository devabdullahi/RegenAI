"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { OnboardingProgress } from "@/components/shared/onboarding-progress";
import { ONBOARDING_STORAGE_KEYS, isGoalId, type GoalId } from "@/lib/onboarding";
import { safeGetString, safeSetString } from "@/lib/storage";

// ---- Goal definitions ----
const GOALS: {
  id: GoalId;
  label: string;
  description: string;
}[] = [
  {
    id: "cost_savings",
    label: "Reduce input costs",
    description:
      "Get personalized tips to spend less on fertilizer, fuel, and pesticides — without hurting your yield.",
  },
  {
    id: "carbon_credits",
    label: "Earn carbon credits",
    description:
      "Document your regenerative practices and connect with carbon markets that pay you for healthier soil.",
  },
  {
    id: "both",
    label: "Both — I want it all",
    description:
      "Reduce costs and build a carbon credit program at the same time. We'll help you prioritize.",
  },
];

// ---- Helpers ----
function loadGoal(): GoalId | null {
  const saved = safeGetString(ONBOARDING_STORAGE_KEYS.goal);
  return isGoalId(saved) ? saved : null;
}

function saveGoal(goal: GoalId) {
  safeSetString(ONBOARDING_STORAGE_KEYS.goal, goal);
}

export default function GoalsPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<GoalId | null>(null);
  const [selectionError, setSelectionError] = useState(false);

  // Hydrate from localStorage after mount (not available during prerender)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is unavailable during prerender, so load the saved goal after mount
    setSelected(loadGoal());
  }, []);

  function choose(id: GoalId) {
    setSelected(id);
    saveGoal(id);
    setSelectionError(false);
  }

  function handleNext() {
    if (!selected) {
      setSelectionError(true);
      return;
    }
    router.push("/onboarding/confirm");
  }

  return (
    <div className="flex flex-col gap-6">
      <OnboardingProgress currentStep={5} />

      <div className="border-b-2 border-rule-strong pb-4">
        <h1 className="font-heading text-2xl font-bold">
          What&apos;s your main goal?
        </h1>
        <p className="reading mt-2 text-muted-foreground">
          We put what matters most to you at the top of your dashboard, and we
          weigh it when we write your recommendations.
        </p>
      </div>

      {/* Pick one: a marked box against each choice, the way a form asks. */}
      <div
        className="flex flex-col"
        role="radiogroup"
        aria-label="Your main goal"
      >
        {GOALS.map((goal) => {
          const isSelected = selected === goal.id;
          return (
            <button
              key={goal.id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => choose(goal.id)}
              className={cn(
                "group flex w-full cursor-pointer items-start gap-4 border-b border-border py-4 pr-2 pl-3 text-left transition-colors last:border-b-0 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                isSelected
                  ? "border-l-[3px] border-l-primary bg-card"
                  : "border-l-[3px] border-l-transparent hover:bg-card"
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "mt-1 flex h-5 w-5 shrink-0 items-center justify-center border transition-colors",
                  isSelected
                    ? "border-primary bg-primary"
                    : "border-input bg-card group-hover:border-primary/60"
                )}
              >
                {isSelected && (
                  <span className="h-2 w-2 bg-primary-foreground" />
                )}
              </span>

              <span className="flex flex-col gap-1">
                <span className="font-heading text-base font-semibold">
                  {goal.label}
                </span>
                <span className="text-sm leading-snug text-muted-foreground">
                  {goal.description}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {/* Validation error */}
      {selectionError && (
        <p
          role="alert"
          className="-mt-2 border-l-[3px] border-l-destructive py-2 pl-3 text-sm text-destructive"
        >
          Please choose a goal to continue.
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
          Next: Review &amp; Confirm
        </Button>

        <Link
          href="/onboarding/practices"
          className="flex min-h-[48px] cursor-pointer items-center justify-center gap-1.5 text-base text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back
        </Link>
      </div>
    </div>
  );
}
