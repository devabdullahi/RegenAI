import Link from "next/link";
import { redirect } from "next/navigation";
import {
  CheckCircle2,
  Circle,
  ExternalLink,
  Info,
  ChevronRight,
} from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";
import { mockFarms } from "@/lib/mocks/farms";
import { mockCSPChecklist, mockCSPEligibility } from "@/lib/mocks/csp";

import type { Metadata } from "next";
import type { CSPChecklistItem } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "CSP Application Checklist — RegenAI",
};

interface ChecklistPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
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

function ChecklistRow({ item }: { item: CSPChecklistItem }) {
  const isNrcsLink =
    item.action?.startsWith("https://") ||
    item.action?.includes("farmers.gov");

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
        <p
          className={`text-sm font-medium leading-snug ${item.completed ? "text-foreground" : "text-foreground"}`}
        >
          {item.label}
        </p>
        <p className="text-xs text-muted-foreground leading-relaxed">
          {item.detail}
        </p>
        {!item.completed && item.action && (
          isNrcsLink ? (
            <a
              href={`https://${item.action.replace(/^https?:\/\//, "")}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline min-h-[44px] sm:min-h-0 py-1"
            >
              {item.action.includes("farmers.gov")
                ? "Find my local NRCS office"
                : item.action}
              <ExternalLink className="h-3 w-3" aria-hidden="true" />
            </a>
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
}: {
  label: string;
  items: CSPChecklistItem[];
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
          <ChecklistRow key={item.item_id} item={item} />
        ))}
      </ul>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function CspChecklistPage({
  searchParams,
}: ChecklistPageProps) {
  const params = await searchParams;
  const farmIdParam =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  const farm =
    mockFarms.find((f) => f.id === farmIdParam) ?? mockFarms[0] ?? null;

  if (!farm) {
    redirect("/farms");
  }

  const checklist = mockCSPChecklist;
  const eligibility = mockCSPEligibility;

  // Split checklist into groups by item_id
  const farmDataItems = checklist.checklist.filter((i) =>
    ["has_fields", "has_soil_data", "nutrient_mgmt_plan"].includes(i.item_id)
  );
  const programItems = checklist.checklist.filter((i) =>
    ["rc_threshold_2", "commitment_selected", "enhancements_selected"].includes(
      i.item_id
    )
  );
  const nextStepItems = checklist.checklist.filter((i) =>
    ["contact_nrcs"].includes(i.item_id)
  );

  return (
    <div className="pb-20 sm:pb-0 space-y-8">
      {/* Breadcrumb */}
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Link href="/farms" className="hover:text-foreground transition-colors">
            {farm.name}
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <Link
            href={`/csp?farm_id=${farm.id}`}
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
          <ReadinessBar pct={checklist.overall_readiness_pct} />
        </CardContent>
      </Card>

      {/* Checklist groups */}
      <div className="space-y-6">
        {farmDataItems.length > 0 && (
          <ChecklistGroup label="Your farm data" items={farmDataItems} />
        )}
        <Separator />
        {programItems.length > 0 && (
          <ChecklistGroup label="Program requirements" items={programItems} />
        )}
        <Separator />
        {nextStepItems.length > 0 && (
          <ChecklistGroup label="Next steps" items={nextStepItems} />
        )}
      </div>

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
