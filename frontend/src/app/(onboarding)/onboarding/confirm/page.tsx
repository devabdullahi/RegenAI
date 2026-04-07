"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Pencil, Loader2, CheckCircle, MapPin, Sprout } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { OnboardingProgress } from "@/components/shared/onboarding-progress";

// ---- Types ----
interface FarmData {
  name: string;
  state: string;
  county: string;
  total_acres: number;
}

interface FieldEntry {
  id: string;
  name: string;
  acres: number;
  crop_type: string;
  boundary_description: string;
}

type GoalId = "cost_savings" | "carbon_credits" | "both";

const GOAL_LABELS: Record<GoalId, string> = {
  cost_savings: "Reduce input costs",
  carbon_credits: "Earn carbon credits",
  both: "Both — reduce costs and earn carbon credits",
};

const PRACTICE_LABELS: Record<string, string> = {
  cover_crops: "Cover crops",
  no_till: "No-till",
  reduced_till: "Reduced-till",
  crop_rotation: "Crop rotation",
  nutrient_management: "Nutrient management plan",
  manure_application: "Manure application",
  integrated_pest: "Integrated pest management",
  conservation_cover: "Conservation cover",
};

const US_STATE_NAMES: Record<string, string> = {
  AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California",
  CO: "Colorado", CT: "Connecticut", DE: "Delaware", FL: "Florida", GA: "Georgia",
  HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa",
  KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland",
  MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi",
  MO: "Missouri", MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire",
  NJ: "New Jersey", NM: "New Mexico", NY: "New York", NC: "North Carolina",
  ND: "North Dakota", OH: "Ohio", OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania",
  RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota", TN: "Tennessee",
  TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia", WA: "Washington",
  WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming",
};

// ---- Helpers ----
function readStorage<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

// ---- Summary section component ----
function SummarySection({
  title,
  editHref,
  children,
}: {
  title: string;
  editHref: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-base font-semibold text-muted-foreground uppercase tracking-wide">
          {title}
        </h2>
        <Link
          href={editHref}
          className="flex items-center gap-1.5 text-sm font-medium text-primary hover:underline transition-colors min-h-[44px] px-2 cursor-pointer"
          aria-label={`Edit ${title}`}
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
          Edit
        </Link>
      </div>
      {children}
    </div>
  );
}

// ---- Main page ----
export default function ConfirmPage() {
  const router = useRouter();
  const [farm, setFarm] = useState<FarmData | null>(null);
  const [fields, setFields] = useState<FieldEntry[]>([]);
  const [practices, setPractices] = useState<string[]>([]);
  const [goal, setGoal] = useState<GoalId | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Hydrate from localStorage after mount
  useEffect(() => {
    setFarm(readStorage<FarmData | null>("onboarding_farm", null));
    setFields(readStorage<FieldEntry[]>("onboarding_fields", []));
    setPractices(readStorage<string[]>("onboarding_practices", []));
    const rawGoal = localStorage.getItem("onboarding_goal") as GoalId | null;
    setGoal(rawGoal);
  }, []);

  async function handleStartAnalysis() {
    setIsSubmitting(true);

    // Simulated 2-second analysis delay
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Clean up localStorage
    [
      "onboarding_farm",
      "onboarding_fields",
      "onboarding_practices",
      "onboarding_goal",
    ].forEach((key) => localStorage.removeItem(key));

    toast.success("Farm setup complete! Your analysis is ready.", {
      description: "Welcome to RegenAI — your recommendations are loading.",
      duration: 5000,
    });

    router.push("/farms");
  }

  // Loading state while hydrating
  if (!farm) {
    return (
      <div className="flex flex-col gap-6">
        <OnboardingProgress currentStep={6} />
        <div className="flex flex-col gap-4">
          <div className="h-8 w-48 rounded-lg bg-muted animate-pulse" />
          <div className="h-4 w-72 rounded-lg bg-muted animate-pulse" />
          <div className="h-40 w-full rounded-xl bg-muted animate-pulse" />
          <div className="h-40 w-full rounded-xl bg-muted animate-pulse" />
          <div className="h-12 w-full rounded-lg bg-muted animate-pulse" />
        </div>
      </div>
    );
  }

  const totalFieldAcres = fields.reduce((sum, f) => sum + f.acres, 0);

  return (
    <div className="flex flex-col gap-6">
      <OnboardingProgress currentStep={6} />

      <div>
        <h1 className="font-heading text-2xl font-bold">
          Everything look right?
        </h1>
        <p className="mt-1 text-base text-muted-foreground">
          Review your farm details below. Click any &quot;Edit&quot; link to go back and make changes.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="font-heading text-lg">Your setup summary</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">

          {/* Farm details */}
          <SummarySection title="Farm" editHref="/onboarding/farm">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                <MapPin className="h-5 w-5 text-primary" aria-hidden="true" />
              </div>
              <div>
                <p className="text-lg font-semibold">{farm.name}</p>
                <p className="text-base text-muted-foreground">
                  {farm.county}, {US_STATE_NAMES[farm.state] ?? farm.state}
                </p>
                <p className="text-base text-muted-foreground">
                  {farm.total_acres.toLocaleString()} total acres
                </p>
              </div>
            </div>
          </SummarySection>

          <Separator />

          {/* Fields */}
          <SummarySection title="Fields" editHref="/onboarding/fields">
            {fields.length === 0 ? (
              <p className="text-base text-muted-foreground">
                No fields added yet.
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                <p className="text-sm text-muted-foreground mb-1">
                  {fields.length} field{fields.length !== 1 ? "s" : ""} &middot;{" "}
                  {totalFieldAcres.toLocaleString()} acres total
                </p>
                <ul className="flex flex-col gap-2">
                  {fields.map((field) => (
                    <li key={field.id} className="flex items-center gap-3">
                      <Sprout
                        className="h-4 w-4 shrink-0 text-primary"
                        aria-hidden="true"
                      />
                      <span className="text-base font-medium">{field.name}</span>
                      <span className="flex gap-1.5 ml-auto">
                        <Badge variant="secondary" className="text-sm">
                          {field.acres} ac
                        </Badge>
                        <Badge variant="outline" className="text-sm">
                          {field.crop_type}
                        </Badge>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </SummarySection>

          <Separator />

          {/* Practices */}
          <SummarySection title="Current practices" editHref="/onboarding/practices">
            {practices.length === 0 ? (
              <p className="text-base text-muted-foreground">
                None selected — we&apos;ll suggest where to start.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {practices.map((p) => (
                  <Badge key={p} variant="secondary" className="text-sm py-1 px-3">
                    <CheckCircle
                      className="mr-1.5 h-3.5 w-3.5 text-primary"
                      aria-hidden="true"
                    />
                    {PRACTICE_LABELS[p] ?? p}
                  </Badge>
                ))}
              </div>
            )}
          </SummarySection>

          <Separator />

          {/* Goal */}
          <SummarySection title="Your goal" editHref="/onboarding/goals">
            {goal ? (
              <p className="text-base font-semibold text-foreground">
                {GOAL_LABELS[goal]}
              </p>
            ) : (
              <p className="text-base text-muted-foreground">No goal selected.</p>
            )}
          </SummarySection>
        </CardContent>
      </Card>

      {/* Loading state overlay message */}
      {isSubmitting && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center justify-center gap-3 rounded-xl border border-border bg-card px-6 py-4"
        >
          <Loader2
            className="h-5 w-5 shrink-0 animate-spin text-primary"
            aria-hidden="true"
          />
          <span className="text-base font-medium">
            Analyzing your farm data — this only takes a moment&hellip;
          </span>
        </div>
      )}

      {/* CTA */}
      <Button
        type="button"
        onClick={handleStartAnalysis}
        disabled={isSubmitting}
        className="h-14 w-full bg-accent text-accent-foreground hover:bg-accent/90 text-lg font-bold cursor-pointer disabled:cursor-not-allowed"
      >
        {isSubmitting ? (
          <>
            <Loader2
              className="mr-2 h-5 w-5 animate-spin"
              aria-hidden="true"
            />
            Analyzing&hellip;
          </>
        ) : (
          "Start My Analysis"
        )}
      </Button>

      {!isSubmitting && (
        <Link
          href="/onboarding/goals"
          className="flex items-center justify-center gap-1.5 text-base text-muted-foreground hover:text-foreground transition-colors min-h-[48px] cursor-pointer"
        >
          Back
        </Link>
      )}
    </div>
  );
}
