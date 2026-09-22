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
import { api, ApiRequestError } from "@/lib/api/client";
import {
  ONBOARDING_STORAGE_KEYS,
  US_STATE_NAMES,
  isGoalId,
  practiceLabel,
  toPracticeCodes,
  type GoalId,
} from "@/lib/onboarding";
import {
  safeGetJSON,
  safeGetString,
  safeRemove,
  safeSetJSON,
  safeSetString,
} from "@/lib/storage";

// ---- Types ----
interface FarmData {
  name: string;
  state: string;
  county: string;
  /** 5-digit county FIPS code. Missing on data saved before this field existed. */
  county_fips?: string;
  total_acres: number;
}

interface FieldEntry {
  /** Client-only id generated during onboarding (not the database id). */
  id: string;
  name: string;
  acres: number;
  crop_type: string;
  boundary_description: string;
}

const GOAL_LABELS: Record<GoalId, string> = {
  cost_savings: "Reduce input costs",
  carbon_credits: "Earn carbon credits",
  both: "Both — reduce costs and earn carbon credits",
};

// ---- Helpers ----
function errorMessage(err: unknown): string {
  if (err instanceof ApiRequestError) {
    if (err.code === 0) {
      return "We couldn't reach the server. Check your internet connection.";
    }
    return err.message;
  }
  if (err instanceof Error && err.message) return err.message;
  return "Something went wrong.";
}

/** Returns a farmer-friendly problem description, or null if the data is ready to save. */
function findMissingInfo(
  farm: FarmData,
  fields: FieldEntry[]
): { title: string; description: string } | null {
  if (!farm.name?.trim() || !/^[A-Z]{2}$/.test(farm.state ?? "")) {
    return {
      title: "Some farm details are missing.",
      description: "Tap \"Edit\" next to Farm and fill in the name and state.",
    };
  }
  if (!/^\d{5}$/.test(farm.county_fips ?? "")) {
    return {
      title: "We need your county code.",
      description:
        "Tap \"Edit\" next to Farm and add the 5-digit county code so we can pull your local soil and weather.",
    };
  }
  if (!(farm.total_acres > 0)) {
    return {
      title: "Total acres is missing.",
      description: "Tap \"Edit\" next to Farm and enter your total acres.",
    };
  }
  if (fields.length === 0) {
    return {
      title: "Add at least one field.",
      description: "Tap \"Edit\" next to Fields to add a field before starting.",
    };
  }
  return null;
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
          className="flex items-center gap-1.5 text-sm font-medium text-primary hover:underline transition-colors min-h-12 px-2 cursor-pointer"
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
  const [hasPartialSave, setHasPartialSave] = useState(false);

  // Hydrate from localStorage after mount (not available during prerender)
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- one-time hydration from localStorage */
    setFarm(safeGetJSON<FarmData | null>(ONBOARDING_STORAGE_KEYS.farm, null));
    const savedFields = safeGetJSON<unknown>(ONBOARDING_STORAGE_KEYS.fields, []);
    setFields(Array.isArray(savedFields) ? (savedFields as FieldEntry[]) : []);
    const savedPractices = safeGetJSON<unknown>(ONBOARDING_STORAGE_KEYS.practices, []);
    setPractices(Array.isArray(savedPractices) ? (savedPractices as string[]) : []);
    const savedGoal = safeGetString(ONBOARDING_STORAGE_KEYS.goal);
    setGoal(isGoalId(savedGoal) ? savedGoal : null);
    setHasPartialSave(Boolean(safeGetString(ONBOARDING_STORAGE_KEYS.createdFarmId)));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  async function handleStartAnalysis() {
    if (!farm || isSubmitting) return;

    const problem = findMissingInfo(farm, fields);
    if (problem) {
      toast.error(problem.title, { description: problem.description });
      return;
    }

    setIsSubmitting(true);

    // ---- 1. Create the farm (skip if a previous attempt already created it) ----
    let farmId = safeGetString(ONBOARDING_STORAGE_KEYS.createdFarmId);
    if (!farmId) {
      try {
        const createdFarm = await api.farms.create({
          name: farm.name.trim(),
          state: farm.state,
          county_fips: farm.county_fips!,
          total_acres: farm.total_acres,
          ...(goal ? { goals: goal } : {}),
        });
        farmId = createdFarm.id;
        safeSetString(ONBOARDING_STORAGE_KEYS.createdFarmId, farmId);
        setHasPartialSave(true);
      } catch (err) {
        console.error("Onboarding: failed to create farm", err);
        toast.error("We couldn't save your farm.", {
          description: `${errorMessage(err)} Your answers are still here — please try again.`,
          duration: 8000,
        });
        setIsSubmitting(false);
        return;
      }
    }

    // ---- 2. Create each field (skip ones already created on a previous attempt) ----
    const createdFieldIds = safeGetJSON<Record<string, string>>(
      ONBOARDING_STORAGE_KEYS.createdFieldIds,
      {}
    );
    const practiceCodes = toPracticeCodes(practices);

    for (const field of fields) {
      if (createdFieldIds[field.id]) continue;
      try {
        const boundary = field.boundary_description?.trim();
        const createdField = await api.fields.create({
          farm_id: farmId,
          name: field.name.trim(),
          acres: field.acres,
          crop_type: field.crop_type,
          practices: practiceCodes,
          ...(boundary ? { boundary_description: boundary } : {}),
        });
        createdFieldIds[field.id] = createdField.id;
        safeSetJSON(ONBOARDING_STORAGE_KEYS.createdFieldIds, createdFieldIds);
      } catch (err) {
        console.error(`Onboarding: failed to create field "${field.name}"`, err);
        toast.error(`Your farm was saved, but the field "${field.name}" wasn't.`, {
          description: `${errorMessage(err)} Tap the button again to finish — we won't create your farm twice.`,
          duration: 8000,
        });
        setIsSubmitting(false);
        return;
      }
    }

    // ---- 3. Kick off soil/weather lookup + recommendations (non-blocking) ----
    const fieldIds = fields
      .map((f) => createdFieldIds[f.id])
      .filter((id): id is string => Boolean(id));
    const savedFarmId = farmId;

    void Promise.allSettled(fieldIds.map((id) => api.fields.enrich(id)))
      .then(async (enrichResults) => {
        const enrichFailed = enrichResults.filter((r) => r.status === "rejected");
        if (enrichFailed.length > 0) {
          console.warn("Onboarding: field enrichment failed", enrichFailed);
        }
        let recsFailed = false;
        try {
          await api.recommendations.generate(savedFarmId);
        } catch (err) {
          recsFailed = true;
          console.warn("Onboarding: recommendation generation failed", err);
        }
        if (enrichFailed.length > 0 || recsFailed) {
          toast.warning("Your farm is saved, but your analysis is still catching up.", {
            description:
              "We couldn't finish pulling soil, weather, or recommendations. Your farm and fields are saved.",
            duration: 8000,
          });
        }
      })
      .catch((err) => {
        console.warn("Onboarding: background analysis error", err);
      });

    // ---- 4. Farm + fields are saved: clear onboarding data and go to dashboard ----
    safeRemove(...Object.values(ONBOARDING_STORAGE_KEYS));

    toast.success("Your farm is saved!", {
      description:
        "We're pulling your soil and weather data and building your recommendations now.",
      duration: 5000,
    });

    router.push(`/dashboard?farm=${encodeURIComponent(savedFarmId)}`);
  }

  // Loading state while hydrating
  if (!farm) {
    return (
      <div className="flex flex-col gap-6">
        <OnboardingProgress currentStep={6} />
        <div className="flex flex-col gap-4">
          <div className="h-8 w-48 rounded-lg bg-muted animate-pulse" />
          <div className="h-4 w-72 rounded-lg bg-muted animate-pulse" />
          <div className="h-40 w-full animate-pulse bg-muted" />
          <div className="h-40 w-full animate-pulse bg-muted" />
          <div className="h-12 w-full rounded-lg bg-muted animate-pulse" />
        </div>
      </div>
    );
  }

  const totalFieldAcres = fields.reduce((sum, f) => sum + f.acres, 0);

  return (
    <div className="flex flex-col gap-6">
      <OnboardingProgress currentStep={6} />

      <div className="border-b-2 border-rule-strong pb-4">
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
              <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center border border-border bg-card">
                <MapPin className="h-5 w-5 text-primary" aria-hidden="true" />
              </div>
              <div>
                <p className="text-lg font-semibold">{farm.name}</p>
                <p className="text-base text-muted-foreground">
                  {farm.county}, {US_STATE_NAMES[farm.state] ?? farm.state}
                  {farm.county_fips ? ` · County code ${farm.county_fips}` : ""}
                </p>
                {!farm.county_fips && (
                  <p className="text-sm text-destructive">
                    County code missing — tap Edit to add it.
                  </p>
                )}
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
                      <span>{field.name}</span>
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
                    {practiceLabel(p)}
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
          className="flex items-center justify-center gap-3 border border-border bg-card px-6 py-4"
        >
          <Loader2
            className="h-5 w-5 shrink-0 animate-spin text-primary"
            aria-hidden="true"
          />
          <span>
            Saving your farm and fields — this only takes a moment&hellip;
          </span>
        </div>
      )}

      {!isSubmitting && hasPartialSave && (
        <p className="text-sm text-muted-foreground text-center">
          Your farm was already saved. Tap the button to finish saving your fields.
        </p>
      )}

      {/* CTA */}
      <Button
        type="button"
        onClick={handleStartAnalysis}
        disabled={isSubmitting}
        size="lg"
        className="w-full cursor-pointer disabled:cursor-not-allowed"
      >
        {isSubmitting ? (
          <>
            <Loader2
              className="mr-2 h-5 w-5 animate-spin"
              aria-hidden="true"
            />
            Saving&hellip;
          </>
        ) : hasPartialSave ? (
          "Finish Setup"
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
