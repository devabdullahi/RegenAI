"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

const STEPS = [
  { number: 1, label: "Welcome" },
  { number: 2, label: "Farm Info" },
  { number: 3, label: "Fields" },
  { number: 4, label: "Practices" },
  { number: 5, label: "Goals" },
  { number: 6, label: "Confirm" },
];

interface OnboardingProgressProps {
  currentStep: number;
}

export function OnboardingProgress({ currentStep }: OnboardingProgressProps) {
  return (
    <nav
      aria-label="Onboarding progress"
      className="mb-8"
    >
      {/* Desktop: full horizontal stepper */}
      <ol className="hidden sm:flex items-center w-full">
        {STEPS.map((step, index) => {
          const isCompleted = step.number < currentStep;
          const isActive = step.number === currentStep;
          const isLast = index === STEPS.length - 1;

          return (
            <li
              key={step.number}
              className={cn(
                "flex items-center",
                !isLast && "flex-1"
              )}
            >
              {/* Step bubble + label */}
              <div className="flex flex-col items-center gap-1.5">
                <div
                  aria-current={isActive ? "step" : undefined}
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors duration-200",
                    isCompleted &&
                      "border-primary bg-primary text-primary-foreground",
                    isActive &&
                      "border-primary bg-primary text-primary-foreground ring-4 ring-primary/20",
                    !isCompleted &&
                      !isActive &&
                      "border-border bg-card text-muted-foreground"
                  )}
                >
                  {isCompleted ? (
                    <Check className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <span>{step.number}</span>
                  )}
                </div>
                <span
                  className={cn(
                    "text-xs font-medium whitespace-nowrap",
                    isActive && "text-primary",
                    isCompleted && "text-primary",
                    !isActive && !isCompleted && "text-muted-foreground"
                  )}
                >
                  {step.label}
                </span>
              </div>

              {/* Connector line between steps */}
              {!isLast && (
                <div
                  aria-hidden="true"
                  className={cn(
                    "mx-2 h-0.5 flex-1 rounded-full transition-colors duration-200",
                    isCompleted ? "bg-primary" : "bg-border"
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>

      {/* Mobile: compact "Step X of 6 — Label" indicator */}
      <div className="flex sm:hidden items-center gap-3">
        <div className="flex gap-1.5">
          {STEPS.map((step) => {
            const isCompleted = step.number < currentStep;
            const isActive = step.number === currentStep;
            return (
              <div
                key={step.number}
                aria-hidden="true"
                className={cn(
                  "h-2 rounded-full transition-all duration-200",
                  isActive && "w-6 bg-primary",
                  isCompleted && "w-2 bg-primary",
                  !isActive && !isCompleted && "w-2 bg-border"
                )}
              />
            );
          })}
        </div>
        <span className="text-sm font-medium text-muted-foreground">
          Step {currentStep} of {STEPS.length}
          <span className="text-foreground">
            {" "}— {STEPS[currentStep - 1]?.label}
          </span>
        </span>
      </div>
    </nav>
  );
}
