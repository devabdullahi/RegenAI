import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
} from "lucide-react";

import { CSPEligibilityCard } from "@/components/csp/csp-eligibility-card";
import { CSPScoreGauge } from "@/components/csp/csp-score-gauge";
import { CSPPaymentSummary } from "@/components/csp/csp-payment-summary";
import { CSPResourceConcerns } from "@/components/csp/csp-resource-concerns";
import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";

import { mockFarms } from "@/lib/mocks/farms";
import {
  mockCSPEligibility,
  mockCSPScore,
  mockCSPPayment,
} from "@/lib/mocks/csp";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CSP Navigator — RegenAI",
  description:
    "Check your Conservation Stewardship Program eligibility, estimate your payment, and prepare your application.",
};

interface CspPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
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
      variant: "outline" as const,
    },
    {
      href: `/csp/payment?farm_id=${farmId}`,
      label: "Estimate My Payment",
      sublabel: "Detailed 5-year breakdown",
      icon: DollarSign,
      variant: "outline" as const,
    },
    {
      href: `/csp/enhancements?farm_id=${farmId}`,
      label: "Browse Enhancements",
      sublabel: "Add activities to increase payment",
      icon: Zap,
      variant: "outline" as const,
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

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function CspPage({ searchParams }: CspPageProps) {
  const params = await searchParams;
  const farmIdParam =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  // Default to first farm when no farm_id provided
  const farm =
    mockFarms.find((f) => f.id === farmIdParam) ?? mockFarms[0] ?? null;

  if (!farm) {
    redirect("/farms");
  }

  // Use mock data — will be replaced with API calls
  const eligibility = mockCSPEligibility;
  const score = mockCSPScore;
  const payment = mockCSPPayment;

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
            {farm.name}
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
          {farm.state} &middot; {farm.total_acres.toLocaleString()} total
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
            farmId={farm.id}
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
        <Link href={`/csp/eligibility?farm_id=${farm.id}`}>
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
          <Link href={`/csp/payment?farm_id=${farm.id}`}>
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
        <QuickActions farmId={farm.id} />
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
