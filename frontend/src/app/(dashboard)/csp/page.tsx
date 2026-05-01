import Link from "next/link";
import { Suspense } from "react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  ShieldCheck,
  ListChecks,
  DollarSign,
  Zap,
  ExternalLink,
  Info,
  Lightbulb,
  ChevronRight,
  AlertCircle,
} from "lucide-react";

import { CSPEligibilityCard } from "@/components/csp/csp-eligibility-card";
import { CSPScoreGauge } from "@/components/csp/csp-score-gauge";
import { CSPPaymentSummary } from "@/components/csp/csp-payment-summary";
import { CSPResourceConcerns } from "@/components/csp/csp-resource-concerns";
import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";

import { api } from "@/lib/api/server-client";

import type { Metadata } from "next";
import type { CSPEligibility, CSPScore, CSPPaymentEstimate } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "CSP Navigator — RegenAI",
  description:
    "Check your Conservation Stewardship Program eligibility, estimate your payment, and prepare your application.",
};

interface CspPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

// ── Helpers: derive CSPScore from CSPEligibility ───────────────────────────────

function deriveScore(eligibility: CSPEligibility): CSPScore {
  const s = eligibility.stewardship_score;
  const score_label: CSPScore["score_label"] =
    s >= 80 ? "Excellent" : s >= 60 ? "Good" : s >= 40 ? "Fair" : "Needs Work";
  const percentile_estimate: CSPScore["percentile_estimate"] =
    s >= 80
      ? "top 10%"
      : s >= 65
        ? "top 25%"
        : s >= 50
          ? "competitive"
          : "below average";

  const score_breakdown = eligibility.resource_concerns_met.map((rc) => ({
    resource_concern: rc.name,
    code: rc.code,
    points_earned: rc.points_earned,
    max_points: Math.round(rc.points_earned / Math.max(rc.score / 100, 0.01)),
    score: rc.score,
    currently_met: rc.currently_met,
  }));

  return {
    farm_id: eligibility.farm_id,
    stewardship_score: s,
    score_label,
    percentile_estimate,
    base_score: s,
    bonus_points: Math.max(
      0,
      eligibility.estimated_ranking_score - s
    ),
    score_breakdown,
    improvement_recommendations: eligibility.missing_requirements,
    from_cache: eligibility.from_cache,
    evaluated_at: eligibility.evaluated_at,
  };
}

function derivePayment(eligibility: CSPEligibility): CSPPaymentEstimate {
  const annual = eligibility.estimated_annual_payment ?? 0;
  return {
    farm_id: eligibility.farm_id,
    state_code: "IA",
    fiscal_year: eligibility.fiscal_year,
    total_cropland_acres: 0,
    rc_count_above_threshold: eligibility.rc_count_above_threshold,
    eap_annual: annual,
    enap_annual: 0,
    raw_annual: annual,
    capped_annual: annual,
    contract_5yr_total: eligibility.estimated_5yr_payment ?? annual * 5,
    per_acre_annual: 0,
    min_applied: false,
    max_applied: false,
    enhancement_breakdown: [],
    disclaimer:
      "This is an estimate based on NRCS payment schedules and may differ from the final payment determined by your local NRCS office.",
  };
}

// ── Static disclaimer ─────────────────────────────────────────────────────────

function NrcsDisclaimer() {
  return (
    <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/30 px-4 py-4">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <p className="text-xs text-muted-foreground leading-relaxed">
        CSP eligibility scores and payment estimates on this page are calculated
        by RegenAI based on publicly available NRCS payment schedules and your
        farm data. They are not official NRCS determinations. Contact your local
        NRCS service center to submit an application and receive official program
        determinations. This tool does not replace professional agronomic or
        legal advice.
      </p>
    </div>
  );
}

// ── Improvement tips ──────────────────────────────────────────────────────────

function ImprovementTips({ tips }: { tips: string[] }) {
  if (tips.length === 0) return null;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Lightbulb className="h-4 w-4 text-amber-500" aria-hidden="true" />
        <h2 className="font-heading text-base font-semibold text-foreground">
          How to improve your score
        </h2>
      </div>
      <ul className="space-y-2" aria-label="Score improvement tips">
        {tips.map((tip, i) => (
          <li
            key={i}
            className="flex items-start gap-2 rounded-lg border border-border bg-card px-3 py-3 text-sm text-foreground leading-snug"
          >
            <span
              className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xs font-bold text-amber-700"
              aria-hidden="true"
            >
              {i + 1}
            </span>
            {tip}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Quick action buttons ──────────────────────────────────────────────────────

function QuickActions({ farmId }: { farmId: string }) {
  const actions = [
    {
      href: `/csp/checklist?farm_id=${farmId}`,
      label: "View Application Checklist",
      sublabel: "Step-by-step readiness guide",
      icon: ListChecks,
    },
    {
      href: `/csp/payment?farm_id=${farmId}`,
      label: "Estimate My Payment",
      sublabel: "Detailed 5-year breakdown",
      icon: DollarSign,
    },
    {
      href: `/csp/enhancements?farm_id=${farmId}`,
      label: "Browse Enhancements",
      sublabel: "Add activities to increase payment",
      icon: Zap,
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {actions.map((action) => (
        <Link key={action.href} href={action.href}>
          <div className="flex min-h-[72px] items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 hover:border-primary/40 hover:bg-primary/5 transition-colors cursor-pointer">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <action.icon className="h-5 w-5 text-primary" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground leading-snug">
                {action.label}
              </p>
              <p className="text-xs text-muted-foreground">{action.sublabel}</p>
            </div>
            <ChevronRight className="ml-auto h-4 w-4 text-muted-foreground shrink-0" aria-hidden="true" />
          </div>
        </Link>
      ))}
    </div>
  );
}

// ── Error state ───────────────────────────────────────────────────────────────

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50">
        <AlertCircle className="h-7 w-7 text-red-500" aria-hidden="true" />
      </div>
      <div>
        <h2 className="font-heading text-lg font-semibold text-foreground">
          Unable to load CSP data
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

// ── No farm selected ──────────────────────────────────────────────────────────

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
          Choose a farm to view its CSP eligibility and payment estimates.
        </p>
      </div>
      <Link href="/farms">
        <Button className="min-h-[48px]">Go to My Farms</Button>
      </Link>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function CspPage({ searchParams }: CspPageProps) {
  const params = await searchParams;
  const farmId =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  if (!farmId) {
    return <NoFarmSelected />;
  }

  let eligibility: CSPEligibility;
  let farmName: string;
  let farmState: string;
  let farmAcres: number;

  try {
    [eligibility] = await Promise.all([
      api.csp.getEligibility(farmId),
    ]);

    // Fetch farm details for the breadcrumb / header
    const farm = await api.farms.get(farmId);
    farmName = farm.name;
    farmState = farm.state;
    farmAcres = farm.total_acres;
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "An unexpected error occurred.";
    return <ErrorState message={message} />;
  }

  const score = deriveScore(eligibility);
  const payment = derivePayment(eligibility);
  const upcomingDeadlines = eligibility.upcoming_deadlines ?? [];

  return (
    <div className="pb-20 sm:pb-0 space-y-8">
      {/* Breadcrumb + page header */}
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Link
            href="/farms"
            className="hover:text-foreground transition-colors"
          >
            {farmName}
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <span className="text-foreground font-medium">CSP Navigator</span>
        </div>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
              Conservation Stewardship Program
            </h1>
            <p className="mt-1 text-sm text-muted-foreground max-w-prose leading-relaxed">
              CSP pays you for the good conservation work you are already doing
              on your farm, plus activities you commit to adding over a 5-year
              contract. No cost-share required — you keep farming and get paid.
            </p>
          </div>
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10">
            <ShieldCheck className="h-6 w-6 text-primary" aria-hidden="true" />
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          {farmState} &middot; {farmAcres.toLocaleString()} total
          acres &middot; FY{eligibility.fiscal_year}
        </p>
      </div>

      {/* Deadline alerts (urgent/warning only) */}
      <CSPDeadlineBanners deadlines={upcomingDeadlines} />

      {/* Eligibility status card */}
      <section aria-labelledby="eligibility-section-heading">
        <h2
          id="eligibility-section-heading"
          className="font-heading text-lg font-semibold text-foreground mb-3"
        >
          Are you eligible?
        </h2>
        <Suspense
          fallback={
            <div className="h-48 w-full rounded-xl bg-muted animate-pulse" />
          }
        >
          <CSPEligibilityCard
            eligibility={eligibility}
            farmId={farmId}
            showDetailLink
          />
        </Suspense>
      </section>

      {/* Stewardship score */}
      <section
        aria-labelledby="score-section-heading"
        className="rounded-xl border border-border bg-card px-5 py-5 space-y-4"
      >
        <h2
          id="score-section-heading"
          className="font-heading text-lg font-semibold text-foreground"
        >
          Your stewardship score
        </h2>
        <p className="text-sm text-muted-foreground -mt-2">
          This score determines where your application ranks against other farms
          in Iowa. Higher scores mean faster approval and higher payments.
        </p>
        <Suspense
          fallback={
            <div className="h-40 w-full rounded-lg bg-muted animate-pulse" />
          }
        >
          <CSPScoreGauge score={score} showBreakdown={false} />
        </Suspense>
        <Link href={`/csp/eligibility?farm_id=${farmId}`}>
          <Button
            variant="outline"
            size="sm"
            className="min-h-[44px] cursor-pointer text-primary border-primary/30 hover:bg-primary/5 mt-2"
          >
            See full score breakdown
            <ChevronRight className="ml-1 h-4 w-4" aria-hidden="true" />
          </Button>
        </Link>
      </section>

      {/* Payment summary */}
      <section aria-labelledby="payment-section-heading">
        <h2
          id="payment-section-heading"
          className="font-heading text-lg font-semibold text-foreground mb-3"
        >
          Estimated payment
        </h2>
        <Suspense
          fallback={
            <div className="h-40 w-full rounded-xl bg-muted animate-pulse" />
          }
        >
          <CSPPaymentSummary payment={payment} compact />
        </Suspense>
        <div className="mt-3">
          <Link href={`/csp/payment?farm_id=${farmId}`}>
            <Button
              variant="outline"
              size="sm"
              className="min-h-[44px] cursor-pointer text-primary border-primary/30 hover:bg-primary/5"
            >
              View detailed payment breakdown
              <ChevronRight className="ml-1 h-4 w-4" aria-hidden="true" />
            </Button>
          </Link>
        </div>
      </section>

      <Separator />

      {/* Resource concerns grid */}
      <Suspense
        fallback={
          <div className="grid gap-3 sm:grid-cols-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="h-36 w-full rounded-xl bg-muted animate-pulse"
              />
            ))}
          </div>
        }
      >
        <CSPResourceConcerns
          resourceConcerns={eligibility.resource_concerns_met}
        />
      </Suspense>

      <Separator />

      {/* Improvement tips */}
      <ImprovementTips tips={score.improvement_recommendations} />

      <Separator />

      {/* Quick action buttons */}
      <section aria-labelledby="actions-heading">
        <h2
          id="actions-heading"
          className="font-heading text-lg font-semibold text-foreground mb-3"
        >
          What do you need to do next?
        </h2>
        <QuickActions farmId={farmId} />
      </section>

      {/* NRCS external link */}
      <div className="rounded-xl border border-border bg-card px-4 py-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">
            Ready to apply?
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Contact your local NRCS service center to schedule a site visit and
            submit your official application.
          </p>
        </div>
        <a
          href="https://www.farmers.gov/contact/service-center-locator"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-[48px] items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
          aria-label="Find your local NRCS office (opens in new tab)"
        >
          Find Local NRCS Office
          <ExternalLink className="h-4 w-4" aria-hidden="true" />
        </a>
      </div>

      {/* Disclaimer */}
      <NrcsDisclaimer />
    </div>
  );
}
