import Link from "next/link";
import {
  CheckCircle2,
  Circle,
  ExternalLink,
  Info,
  ChevronRight,
  AlertCircle,
  ShieldCheck,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";
import { api } from "@/lib/api/server-client";

import type { Metadata } from "next";
import type { CSPChecklistItem, CSPEligibility } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "CSP Application Checklist — RegenAI",
};

interface ChecklistPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

// ── Derive checklist from live eligibility data ───────────────────────────────

function buildChecklist(eligibility: CSPEligibility, farmHasFields: boolean): {
  overall_readiness_pct: number;
  checklist: CSPChecklistItem[];
} {
  const hasEnhancements = eligibility.active_enhancement_codes.length > 0;
  const hasCommitment = eligibility.rc_count_will_meet > 0;
  const rcMet = eligibility.rc_count_above_threshold >= 2;
  const readinessPct = eligibility.application_readiness_pct;

  const checklist: CSPChecklistItem[] = [
    {
      item_id: "has_fields",
      label: "Farm has registered fields",
      completed: farmHasFields,
      detail: farmHasFields
        ? "Fields are registered in your farm profile"
        : "Add at least one field to your farm profile",
      action: farmHasFields ? undefined : "Add fields in your farm settings",
    },
    {
      item_id: "rc_threshold_2",
      label: "Meets conservation threshold on 2 or more areas",
      completed: rcMet,
      detail: rcMet
        ? `${eligibility.rc_count_above_threshold} of 8 resource concerns currently above the stewardship threshold`
        : `${eligibility.rc_count_above_threshold} of 2 required areas met — additional practices needed`,
      action: rcMet ? undefined : "Review your resource concerns in the Eligibility tab",
    },
    {
      item_id: "commitment_selected",
      label: "Committed to improving at least 1 more conservation area",
      completed: hasCommitment,
      detail: hasCommitment
        ? "Enhancement activities selected and committed"
        : "Select an enhancement activity to commit to meeting one additional resource concern",
      action: hasCommitment ? undefined : "Choose an enhancement to add to your committed list",
    },
    {
      item_id: "enhancements_selected",
      label: "Enhancement activities selected",
      completed: hasEnhancements,
      detail: hasEnhancements
        ? `${eligibility.active_enhancement_codes.length} enhancement${eligibility.active_enhancement_codes.length !== 1 ? "s" : ""} selected: ${eligibility.active_enhancement_codes.join(", ")}`
        : "No enhancement activities chosen yet",
      action: hasEnhancements ? undefined : "Browse available enhancements",
    },
    {
      item_id: "contact_nrcs",
      label: "Contact your local NRCS office to submit your application",
      completed: false,
      detail:
        "Final step: your local NRCS conservation planner will schedule a site visit and finalize your contract",
      action:
        "Find your local office at farmers.gov/contact/service-center-locator",
    },
  ];

  return { overall_readiness_pct: readinessPct, checklist };
}

// ── Readiness bar ─────────────────────────────────────────────────────────────

function ReadinessBar({ pct }: { pct: number }) {
  const color =
    pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-primary" : "bg-amber-500";

  return (
    <div className="space-y-2">
      <div className="flex items-end justify-between">
        <p className="text-sm font-medium text-foreground">
          Application readiness
        </p>
        <p className="font-heading text-2xl font-bold text-foreground">
          {pct}%
        </p>
      </div>
      <div
        className="h-4 w-full rounded-full bg-muted overflow-hidden"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Application readiness: ${pct}%`}
      >
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        {pct >= 80
          ? "You are nearly ready to contact NRCS."
          : pct >= 50
            ? "Good progress. Complete the remaining items below."
            : "Several items need attention before you apply."}
      </p>
    </div>
  );
}

// ── Single checklist item ─────────────────────────────────────────────────────

function ChecklistRow({ item, farmId }: { item: CSPChecklistItem; farmId: string }) {
  const isNrcsLink =
    item.action?.startsWith("https://") ||
    item.action?.includes("farmers.gov");

  const isEnhancementsAction =
    item.item_id === "enhancements_selected" ||
    item.item_id === "commitment_selected";

  return (
    <li
      className={`flex items-start gap-3 rounded-xl border p-4 ${item.completed ? "border-green-200 bg-green-50" : "border-border bg-card"}`}
    >
      <div className="mt-0.5 shrink-0">
        {item.completed ? (
          <CheckCircle2
            className="h-5 w-5 text-green-500"
            aria-hidden="true"
          />
        ) : (
          <Circle
            className="h-5 w-5 text-muted-foreground/60"
            aria-hidden="true"
          />
        )}
      </div>
      <div className="flex-1 min-w-0 space-y-1">
        <p className="text-sm font-medium leading-snug text-foreground">
          {item.label}
        </p>
        <p className="text-xs text-muted-foreground leading-relaxed">
          {item.detail}
        </p>
        {!item.completed && item.action && (
          isNrcsLink ? (
            <a
              href="https://www.farmers.gov/contact/service-center-locator"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline min-h-[44px] sm:min-h-0 py-1"
            >
              Find my local NRCS office
              <ExternalLink className="h-3 w-3" aria-hidden="true" />
            </a>
          ) : isEnhancementsAction ? (
            <Link
              href={`/csp/enhancements?farm_id=${farmId}`}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline min-h-[44px] sm:min-h-0 py-1"
            >
              Browse enhancements
              <ChevronRight className="h-3 w-3" aria-hidden="true" />
            </Link>
          ) : (
            <p className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 bg-amber-50 rounded px-2 py-1 border border-amber-200 mt-0.5">
              <ChevronRight className="h-3 w-3" aria-hidden="true" />
              {item.action}
            </p>
          )
        )}
      </div>
      {item.completed && (
        <span className="shrink-0 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
          Done
        </span>
      )}
    </li>
  );
}

// ── Grouped checklist ─────────────────────────────────────────────────────────

function ChecklistGroup({
  label,
  items,
  farmId,
}: {
  label: string;
  items: CSPChecklistItem[];
  farmId: string;
}) {
  const completedCount = items.filter((i) => i.completed).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </h2>
        <span className="text-xs text-muted-foreground">
          {completedCount}/{items.length}
        </span>
      </div>
      <ul className="space-y-2" aria-label={label}>
        {items.map((item) => (
          <ChecklistRow key={item.item_id} item={item} farmId={farmId} />
        ))}
      </ul>
    </div>
  );
}

// ── Error / no-farm states ────────────────────────────────────────────────────

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50">
        <AlertCircle className="h-7 w-7 text-red-500" aria-hidden="true" />
      </div>
      <div>
        <h2 className="font-heading text-lg font-semibold text-foreground">
          Unable to load checklist
        </h2>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">{message}</p>
      </div>
      <Link href="/farms">
        <Button variant="outline" className="min-h-[48px]">
          Back to farms
        </Button>
      </Link>
    </div>
  );
}

function NoFarmSelected() {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted">
        <ShieldCheck className="h-7 w-7 text-muted-foreground" aria-hidden="true" />
      </div>
      <div>
        <h2 className="font-heading text-lg font-semibold text-foreground">
          Select a farm first
        </h2>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          Choose a farm to view your CSP application checklist.
        </p>
      </div>
      <Link href="/farms">
        <Button className="min-h-[48px]">Go to My Farms</Button>
      </Link>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function CspChecklistPage({
  searchParams,
}: ChecklistPageProps) {
  const params = await searchParams;
  const farmId =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  if (!farmId) {
    return <NoFarmSelected />;
  }

  let eligibility: CSPEligibility;
  let farmName: string;
  let hasFields: boolean;

  try {
    const [elig, farm, fields] = await Promise.all([
      api.csp.getEligibility(farmId),
      api.farms.get(farmId),
      api.fields.list(farmId),
    ]);
    eligibility = elig;
    farmName = farm.name;
    hasFields = fields.length > 0;
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "An unexpected error occurred.";
    return <ErrorState message={message} />;
  }

  const { overall_readiness_pct, checklist } = buildChecklist(eligibility, hasFields);

  const programItems = checklist.filter((i) =>
    ["has_fields", "rc_threshold_2", "commitment_selected", "enhancements_selected"].includes(i.item_id)
  );
  const nextStepItems = checklist.filter((i) =>
    ["contact_nrcs"].includes(i.item_id)
  );

  return (
    <div className="pb-20 sm:pb-0 space-y-8">
      {/* Breadcrumb */}
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Link href="/farms" className="hover:text-foreground transition-colors">
            {farmName}
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <Link
            href={`/csp?farm_id=${farmId}`}
            className="hover:text-foreground transition-colors"
          >
            CSP Navigator
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <span className="text-foreground font-medium">Checklist</span>
        </div>
        <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
          Application Checklist
        </h1>
        <p className="text-sm text-muted-foreground">
          Everything you need to have ready before contacting NRCS
        </p>
      </div>

      {/* Deadline alerts */}
      <CSPDeadlineBanners deadlines={eligibility.upcoming_deadlines} />

      {/* Readiness bar */}
      <Card>
        <CardContent className="pt-5">
          <ReadinessBar pct={overall_readiness_pct} />
        </CardContent>
      </Card>

      {/* Checklist groups */}
      <div className="space-y-6">
        {programItems.length > 0 && (
          <ChecklistGroup
            label="Program requirements"
            items={programItems}
            farmId={farmId}
          />
        )}
        <Separator />
        {nextStepItems.length > 0 && (
          <ChecklistGroup
            label="Next steps"
            items={nextStepItems}
            farmId={farmId}
          />
        )}
      </div>

      {/* Missing requirements callout */}
      {eligibility.missing_requirements.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-4 space-y-2">
          <p className="text-sm font-semibold text-amber-800">
            Still needed to strengthen your application
          </p>
          <ul className="space-y-1">
            {eligibility.missing_requirements.map((req, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-amber-700">
                <span aria-hidden="true" className="mt-1">•</span>
                {req}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Disclaimer */}
      <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/30 px-4 py-4">
        <Info
          className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <p className="text-xs text-muted-foreground leading-relaxed">
          CSP eligibility scores and payment estimates on this page are
          calculated by RegenAI based on publicly available NRCS payment
          schedules and your farm data. They are not official NRCS
          determinations. Contact your local NRCS service center to submit an
          application and receive official program determinations.
        </p>
      </div>
    </div>
  );
}
