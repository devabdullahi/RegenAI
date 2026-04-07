"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, TrendingDown, Leaf, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { OnboardingProgress } from "@/components/shared/onboarding-progress";

// ---- Goal definitions ----
type GoalId = "cost_savings" | "carbon_credits" | "both";

const GOALS: {
  id: GoalId;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  {
    id: "cost_savings",
    label: "Reduce input costs",
    description:
      "Get personalized tips to spend less on fertilizer, fuel, and pesticides — without hurting your yield.",
    icon: TrendingDown,
  },
  {
    id: "carbon_credits",
    label: "Earn carbon credits",
    description:
      "Document your regenerative practices and connect with carbon markets that pay you for healthier soil.",
    icon: Leaf,
  },
  {
    id: "both",
    label: "Both — I want it all",
    description:
      "Reduce costs and build a carbon credit program at the same time. We&apos;ll help you prioritize.",
    icon: Sparkles,
  },
];

// ---- Helpers ----
function loadGoal(): GoalId | null {
  if (typeof window === "undefined") return null;
  try {
    return (localStorage.getItem("onboarding_goal") as GoalId) ?? null;
  } catch {
    return null;
  }
}

function saveGoal(goal: GoalId) {
  localStorage.setItem("onboarding_goal", goal);
}

export default function GoalsPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<GoalId | null>(null);
  const [selectionError, setSelectionError] = useState(false);

  useEffect(() => {
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

      <div>
        <h1 className="font-heading text-2xl font-bold">
          What&apos;s your main goal?
        </h1>
        <p className="mt-1 text-base text-muted-foreground">
          We&apos;ll focus your dashboard and recommendations around what matters most to
          you.
        </p>
      </div>

      {/* Goal cards */}
      <div
        className="flex flex-col gap-4"
        role="radiogroup"
        aria-label="Your main goal"
      >
        {GOALS.map((goal) => {
          const isSelected = selected === goal.id;
          const Icon = goal.icon;
          return (
            <button
              key={goal.id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => choose(goal.id)}
              className={cn(
                "group flex w-full items-start gap-4 rounded-xl border-2 p-5 text-left transition-all duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                isSelected
                  ? "border-primary bg-primary/5 shadow-sm"
                  : "border-border bg-card hover:border-primary/40 hover:bg-primary/5"
              )}
              style={{ minHeight: "80px" }}
            >
              {/* Icon */}
              <span
                aria-hidden="true"
                className={cn(
                  "mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-colors duration-150",
                  isSelected
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary"
                )}
              >
                <Icon className="h-5 w-5" />
              </span>

              {/* Text */}
              <span className="flex flex-col gap-1">
                <span className="font-heading text-lg font-semibold leading-snug">
                  {goal.label}
                </span>
                <span className="text-sm text-muted-foreground leading-snug">
                  {goal.id === "both"
                    ? "Reduce costs and build a carbon credit program at the same time. We'll help you prioritize."
                    : goal.description}
                </span>
              </span>

              {/* Selection ring indicator (right side) */}
              <span
                aria-hidden="true"
                className={cn(
                  "ml-auto mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-colors duration-150",
                  isSelected
                    ? "border-primary bg-primary"
                    : "border-input bg-background"
                )}
              >
                {isSelected && (
                  <span className="h-2 w-2 rounded-full bg-white" />
                )}
              </span>
            </button>
          );
        })}
      </div>

      {/* Validation error */}
      {selectionError && (
        <p role="alert" className="text-sm text-destructive -mt-2">
          Please choose a goal to continue.
        </p>
      )}

      {/* Navigation */}
      <div className="flex flex-col gap-3 pt-2">
        <Button
          type="button"
          onClick={handleNext}
          className="h-12 w-full bg-accent text-accent-foreground hover:bg-accent/90 text-base font-semibold cursor-pointer"
        >
          Next: Review &amp; Confirm
        </Button>

        <Link
          href="/onboarding/practices"
          className="flex items-center justify-center gap-1.5 text-base text-muted-foreground hover:text-foreground transition-colors min-h-[48px] cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back
        </Link>
      </div>
    </div>
  );
}
