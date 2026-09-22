"use client";

import { cn } from "@/lib/utils";

const STEPS = [
  { number: 1, label: "Welcome" },
  { number: 2, label: "Farm info" },
  { number: 3, label: "Fields" },
  { number: 4, label: "Practices" },
  { number: 5, label: "Goals" },
  { number: 6, label: "Confirm" },
];

interface OnboardingProgressProps {
  currentStep: number;
}

/**
 * Setup progress as the parts of a form: each step names itself over a rule,
 * and the rule thickens under the part being filled in. Finished parts keep an
 * ink rule; parts still to come keep a hairline.
 */
export function OnboardingProgress({ currentStep }: OnboardingProgressProps) {
  const current = STEPS[currentStep - 1];

  return (
    <nav aria-label="Setup progress" className="mb-8">
      <ol className="hidden gap-3 sm:flex">
        {STEPS.map((step) => {
          const isCompleted = step.number < currentStep;
          const isActive = step.number === currentStep;

          return (
            <li key={step.number} className="flex-1">
              <div
                aria-hidden="true"
                className={cn(
                  "h-[3px]",
                  isActive && "bg-primary",
                  isCompleted && "bg-rule-strong",
                  !isActive && !isCompleted && "bg-rule"
                )}
              />
              <p
                aria-current={isActive ? "step" : undefined}
                className={cn(
                  "mt-2 font-mono text-[0.6875rem] tracking-[0.1em] uppercase",
                  isActive && "text-primary",
                  isCompleted && "text-foreground",
                  !isActive && !isCompleted && "text-muted-foreground"
                )}
              >
                <span className="tabular-nums">
                  {String(step.number).padStart(2, "0")}
                </span>{" "}
                {step.label}
                {isCompleted ? <span className="sr-only"> (done)</span> : null}
              </p>
            </li>
          );
        })}
      </ol>

      {/* Phone: the same rule, one line of type. */}
      <div className="sm:hidden">
        <div aria-hidden="true" className="flex gap-1">
          {STEPS.map((step) => (
            <span
              key={step.number}
              className={cn(
                "h-[3px] flex-1",
                step.number === currentStep && "bg-primary",
                step.number < currentStep && "bg-rule-strong",
                step.number > currentStep && "bg-rule"
              )}
            />
          ))}
        </div>
        <p className="mt-2 font-mono text-[0.6875rem] tracking-[0.12em] text-muted-foreground uppercase">
          Step <span className="tabular-nums">{currentStep}</span> of{" "}
          <span className="tabular-nums">{STEPS.length}</span>
          {current ? (
            <span className="text-foreground"> · {current.label}</span>
          ) : null}
        </p>
      </div>
    </nav>
  );
}
