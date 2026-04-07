import Link from "next/link";
import { redirect } from "next/navigation";
import {
  CheckCircle2,
  Circle,
  Info,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

import { CSPEligibilityBadge } from "@/components/csp/csp-eligibility-card";
import { CSPScoreGauge } from "@/components/csp/csp-score-gauge";
import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";

import { mockFarms } from "@/lib/mocks/farms";
import { mockCSPEligibility, mockCSPScore } from "@/lib/mocks/csp";

import type { Metadata } from "next";
import type { CSPResourceConcernResult } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "CSP Eligibility — RegenAI",
};

interface EligibilityPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

// ── Resource concern detail card ──────────────────────────────────────────────

function ResourceConcernDetailCard({ rc }: { rc: CSPResourceConcernResult }) {
  const met = rc.currently_met;

  return (
    <div
      className={`rounded-xl border p-4 space-y-3 ${met ? "border-green-200 bg-green-50" : "border-amber-200 bg-amber-50/30"}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{rc.name}</p>
          <span
            className={`mt-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${met ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}
          >
            {met ? (
              <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
            ) : (
              <Circle className="h-3 w-3" aria-hidden="true" />
            )}
            {met ? "Threshold met" : "Not yet met"}
          </span>
        </div>
        <div className="text-right shrink-0">
          <p className="text-lg font-bold text-foreground leading-tight">
            {rc.points_earned}
          </p>
          <p className="text-xs text-muted-foreground">points earned</p>
        </div>
      </div>

      {/* Score bar */}
      <div className="space-y-1">
        <div
          className="h-2 w-full rounded-full bg-muted overflow-hidden"
          role="progressbar"
          aria-valuenow={rc.score}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${rc.name} score: ${rc.score}%`}
        >
          <div
            className={`h-full rounded-full transition-all ${met ? "bg-green-500" : "bg-amber-400"}`}
            style={{ width: `${rc.score}%` }}
          />
        </div>
        <p className="text-xs text-muted-foreground text-right">
          {rc.score}/100
        </p>
      </div>

      {/* Evidence */}
      {rc.evidence.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1.5">
            Based on your farm data
          </p>
          <ul className="space-y-1">
            {rc.evidence.map((e, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-muted-foreground/50" aria-hidden="true" />
                {e}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Improvement hint for unmet concerns */}
      {!met && (
        <p className="rounded-md bg-amber-100 border border-amber-200 px-3 py-2 text-xs text-amber-800 leading-relaxed">
          <span className="font-medium">To meet this threshold: </span>
          {rc.code === "WATER_QUANTITY" &&
            "Document irrigation efficiency practices or leverage your county's above-average rainfall."}
          {rc.code === "AIR_QUALITY" &&
            "Add a formal crop rotation plan (practice 328) alongside your existing cover crops."}
          {rc.code === "PLANT_CONDITION" &&
            "Introduce a third crop species or native species planting on at least one field."}
          {rc.code === "ANIMALS" &&
            "This category is less relevant for row-crop operations without livestock."}
          {rc.code === "ENERGY" &&
            "Document any energy efficiency measures on farm equipment or irrigation systems."}
          {![
            "WATER_QUANTITY",
            "AIR_QUALITY",
            "PLANT_CONDITION",
            "ANIMALS",
            "ENERGY",
          ].includes(rc.code) &&
            "Contact your local NRCS office to discuss documentation needed to meet this threshold."}
        </p>
      )}
    </div>
  );
}

// ── Application timeline ──────────────────────────────────────────────────────

function EligibilityTimeline({
  rcCount,
  hasCommitment,
  hasEnhancements,
  farmId,
}: {
  rcCount: number;
  hasCommitment: boolean;
  hasEnhancements: boolean;
  farmId: string;
}) {
  const steps = [
    {
      label: "Meet 2 or more conservation areas",
      detail:
        rcCount >= 2
          ? `${rcCount} of 8 areas currently above threshold`
          : `${rcCount} of 2 required areas met — keep working`,
      done: rcCount >= 2,
    },
    {
      label: "Commit to improving at least 1 more area",
      detail: hasCommitment
        ? "Enhancement activities selected and committed"
        : "Select an enhancement activity to make this commitment",
      done: hasCommitment,
      actionHref: `/csp/enhancements?farm_id=${farmId}`,
      actionLabel: "Select enhancements",
    },
    {
      label: "Select enhancement activities",
      detail: hasEnhancements
        ? "Enhancement activities chosen"
        : "Choose which conservation activities to add",
      done: hasEnhancements,
      actionHref: `/csp/enhancements?farm_id=${farmId}`,
      actionLabel: "Browse enhancements",
    },
    {
      label: "Contact your local NRCS office",
      detail:
        "A conservation planner will schedule a site visit and finalize your 5-year contract",
      done: false,
      actionHref:
        "https://www.farmers.gov/contact/service-center-locator",
      actionLabel: "Find my NRCS office",
      external: true,
    },
  ];

  return (
    <div className="space-y-3">
      <h2 className="font-heading text-lg font-semibold text-foreground">
        Steps to apply
      </h2>
      <ol className="space-y-3" aria-label="Application steps">
        {steps.map((step, i) => (
          <li key={i} className="flex items-start gap-3">
            <div
              className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold ${step.done ? "border-green-500 bg-green-50 text-green-600" : "border-muted-foreground/30 bg-muted text-muted-foreground"}`}
              aria-hidden="true"
            >
              {step.done ? <CheckCircle2 className="h-4 w-4" /> : i + 1}
            </div>
            <div className="flex-1 min-w-0 pt-0.5">
              <p
                className={`text-sm font-medium leading-snug ${step.done ? "text-foreground line-through decoration-muted-foreground/40" : "text-foreground"}`}
              >
                {step.label}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {step.detail}
              </p>
              {!step.done && step.actionHref && (
                step.external ? (
                  <a
                    href={step.actionHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline min-h-[44px] sm:min-h-0"
                  >
                    {step.actionLabel}
                    <ExternalLink className="h-3 w-3" aria-hidden="true" />
                  </a>
                ) : (
                  <Link
                    href={step.actionHref}
                    className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline min-h-[44px] sm:min-h-0"
                  >
                    {step.actionLabel}
                  </Link>
                )
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function CspEligibilityPage({
  searchParams,
}: EligibilityPageProps) {
  const params = await searchParams;
  const farmIdParam =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  const farm =
    mockFarms.find((f) => f.id === farmIdParam) ?? mockFarms[0] ?? null;

  if (!farm) {
    redirect("/farms");
  }

  const eligibility = mockCSPEligibility;
  const score = mockCSPScore;
  const hasCommitment = eligibility.rc_count_will_meet > 0;
  const hasEnhancements = eligibility.active_enhancement_codes.length > 0;

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
          <span className="text-foreground font-medium">Eligibility</span>
        </div>
        <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
          CSP Eligibility
        </h1>
        <p className="text-sm text-muted-foreground">
          How your farm scores on each of the 8 conservation areas
        </p>
      </div>

      {/* Deadline alerts */}
      <CSPDeadlineBanners deadlines={eligibility.upcoming_deadlines} />

      {/* Summary banner */}
      <Card
        className={`border-2 ${eligibility.eligibility_status === "eligible" ? "border-green-300 bg-green-50" : eligibility.eligibility_status === "conditional" ? "border-amber-300 bg-amber-50" : "border-red-200 bg-red-50"}`}
      >
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
              <CSPEligibilityBadge
                status={eligibility.eligibility_status}
                large
              />
              {eligibility.act_now_eligible && (
                <div>
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-primary px-3 py-1 text-sm font-semibold text-primary-foreground">
                    <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                    ACT NOW Eligible — Instant Approval Available
                  </span>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Your score of {eligibility.estimated_ranking_score} meets Iowa&apos;s ACT NOW
                    threshold of {eligibility.act_now_threshold}. Apply during the
                    ACT NOW window for immediate contract approval.
                  </p>
                </div>
              )}
            </div>
            <div className="text-right">
              <p className="text-xs text-muted-foreground">Stewardship score</p>
              <p className="font-heading text-4xl font-bold text-foreground">
                {eligibility.stewardship_score}
              </p>
              <p className="text-xs text-muted-foreground">/100</p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {eligibility.notes}
          </p>
          {eligibility.ineligibility_reasons.length > 0 && (
            <ul className="mt-3 space-y-1">
              {eligibility.ineligibility_reasons.map((r, i) => (
                <li key={i} className="text-sm text-red-700 flex items-start gap-2">
                  <span aria-hidden="true">•</span> {r}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Score gauge */}
      <Card>
        <CardHeader className="border-b pb-3">
          <p className="font-heading text-base font-semibold text-foreground">
            Score breakdown
          </p>
          <p className="text-sm text-muted-foreground">
            Points earned across all 8 conservation areas
          </p>
        </CardHeader>
        <CardContent className="pt-4">
          <CSPScoreGauge score={score} showBreakdown />
        </CardContent>
      </Card>

      <Separator />

      {/* Resource concern detail cards */}
      <section aria-labelledby="rc-details-heading" className="space-y-4">
        <h2
          id="rc-details-heading"
          className="font-heading text-lg font-semibold text-foreground"
        >
          Conservation area details
        </h2>
        <div className="space-y-3">
          {eligibility.resource_concerns_met.map((rc) => (
            <ResourceConcernDetailCard key={rc.code} rc={rc} />
          ))}
        </div>
      </section>

      <Separator />

      {/* Timeline */}
      <EligibilityTimeline
        rcCount={eligibility.rc_count_above_threshold}
        hasCommitment={hasCommitment}
        hasEnhancements={hasEnhancements}
        farmId={farm.id}
      />

      {/* Re-evaluate button */}
      <div className="rounded-xl border border-border bg-card px-4 py-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-foreground">
            Last evaluated:{" "}
            {new Date(eligibility.evaluated_at).toLocaleDateString("en-US", {
              month: "long",
              day: "numeric",
              year: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
          <p className="text-xs text-muted-foreground">
            Eligibility is recalculated automatically when your farm data
            changes.
          </p>
        </div>
        <Button
          variant="outline"
          className="min-h-[48px] cursor-pointer"
          disabled
          aria-label="Re-evaluate eligibility (coming with live API)"
        >
          <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
          Re-evaluate
        </Button>
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
          application and receive official program determinations. This tool
          does not replace professional agronomic or legal advice.
        </p>
      </div>
    </div>
  );
}
