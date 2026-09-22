import Link from "next/link";
import { Suspense } from "react";
import { ChevronRight } from "lucide-react";
import { ButtonLink } from "@/components/shared/button-link";
import { RuleHead, Stamp } from "@/components/shared/record";

import { CSPEligibilityCard } from "@/components/csp/csp-eligibility-card";
import { CSPScoreGauge } from "@/components/csp/csp-score-gauge";
import { CSPPaymentSummary } from "@/components/csp/csp-payment-summary";
import { CSPResourceConcerns } from "@/components/csp/csp-resource-concerns";
import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";

import { api } from "@/lib/api/server-client";
import {
  adaptDeadlines,
  adaptEligibility,
  adaptPayment,
  scoreFromEligibility,
} from "@/lib/api/adapters";

import { NRCS_DISCLAIMER, NRCS_SERVICE_CENTER_LOCATOR_URL } from "@/lib/csp-status";
import { formatAcres } from "@/lib/format";
import { US_STATE_NAMES } from "@/lib/onboarding";

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

// ── Quiet placeholder while a section streams in ─────────────────────────────

function Loading({ label }: { label: string }) {
  return (
    <p className="py-6 font-mono text-xs text-muted-foreground">{label}</p>
  );
}

// ── Improvement tips ──────────────────────────────────────────────────────────

function ImprovementTips({ tips }: { tips: string[] }) {
  if (tips.length === 0) return null;
  return (
    <section aria-labelledby="improve-heading" className="space-y-2">
      <div className="rule-head">
        <h2 id="improve-heading">How to improve your score</h2>
        <span aria-hidden="true" className="h-px flex-1 bg-rule" />
      </div>
      <ol className="mt-1" aria-label="Score improvement tips">
        {tips.map((tip, i) => (
          <li
            key={tip}
            className="flex items-baseline gap-3 border-b border-rule py-3 last:border-0"
          >
            <span className="font-mono text-xs text-muted-foreground" aria-hidden="true">
              {i + 1}
            </span>
            <span className="max-w-[62ch] text-sm leading-snug text-foreground">
              {tip}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

// ── Quick actions ─────────────────────────────────────────────────────────────

function QuickActions({ farmId }: { farmId: string }) {
  const actions = [
    {
      href: `/csp/checklist?farm_id=${encodeURIComponent(farmId)}`,
      label: "Application checklist",
      sublabel: "Step-by-step readiness guide",
    },
    {
      href: `/csp/payment?farm_id=${encodeURIComponent(farmId)}`,
      label: "Estimate my payment",
      sublabel: "Annual and full-contract totals",
    },
    {
      href: `/csp/enhancements?farm_id=${encodeURIComponent(farmId)}`,
      label: "Browse conservation activities",
      sublabel: "Add activities to increase payment",
    },
  ];

  return (
    <ul>
      {actions.map((action) => (
        <li key={action.href} className="border-b border-rule last:border-0">
          <Link
            href={action.href}
            className="flex min-h-12 items-center gap-3 py-3 hover:text-primary"
          >
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-foreground">
                {action.label}
              </span>
              <span className="block text-xs text-muted-foreground">
                {action.sublabel}
              </span>
            </span>
            <ChevronRight
              className="ml-auto h-4 w-4 shrink-0 text-muted-foreground"
              aria-hidden="true"
            />
          </Link>
        </li>
      ))}
    </ul>
  );
}

// ── Error state ───────────────────────────────────────────────────────────────

function ErrorState({ message }: { message: string }) {
  return (
    <div className="max-w-[62ch] space-y-4 py-10">
      <RuleHead label="CSP Navigator" />
      <h2 className="font-heading text-xl font-semibold text-foreground">
        Unable to load CSP data
      </h2>
      <p className="text-sm text-muted-foreground">{message}</p>
      <ButtonLink href="/farms" variant="outline">
        Back to farms
      </ButtonLink>
    </div>
  );
}

// ── No farm selected ──────────────────────────────────────────────────────────

function NoFarmSelected() {
  return (
    <div className="max-w-[62ch] space-y-4 py-10">
      <RuleHead label="CSP Navigator" />
      <h2 className="font-heading text-xl font-semibold text-foreground">
        Select a farm first
      </h2>
      <p className="text-sm text-muted-foreground">
        Choose a farm to view its CSP eligibility and payment estimates.
      </p>
      <ButtonLink href="/farms">Go to My Farms</ButtonLink>
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
  let score: CSPScore;
  let payment: CSPPaymentEstimate | null;
  let farmName: string;
  let farmState: string;
  let farmAcres: number;

  try {
    const [eligibilityResp, farm] = await Promise.all([
      api.csp.getEligibility(farmId),
      api.farms.get(farmId),
    ]);
    farmName = farm.name;
    farmState = farm.state;
    farmAcres = farm.total_acres;

    // Payments and deadlines are optional enrichments — don't fail the page.
    const [paymentsResp, deadlinesResp] = await Promise.all([
      api.csp.getPayments(farmId).catch(() => null),
      api.csp.getDeadlines(farm.state).catch(() => null),
    ]);

    eligibility = adaptEligibility(eligibilityResp, {
      payments: paymentsResp,
      deadlines: adaptDeadlines(deadlinesResp),
    });
    score = scoreFromEligibility(
      eligibilityResp,
      eligibility.missing_requirements
    );
    payment = paymentsResp ? adaptPayment(paymentsResp) : null;
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "An unexpected error occurred.";
    return <ErrorState message={message} />;
  }

  const upcomingDeadlines = eligibility.upcoming_deadlines;
  const stateName = US_STATE_NAMES[farmState] ?? farmState;

  return (
    <div className="space-y-8 pb-20 sm:pb-0">
      {/* Breadcrumb + masthead */}
      <div className="space-y-2">
        <nav
          aria-label="Breadcrumb"
          className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
        >
          <Link href="/farms" className="hover:text-foreground">
            {farmName}
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <span aria-current="page" className="font-medium text-foreground">
            CSP Navigator
          </span>
        </nav>

        <div className="border-b-2 border-rule-strong pb-3">
          <h1 className="font-heading text-[1.75rem] leading-tight font-bold text-foreground sm:text-3xl">
            Conservation Stewardship Program
          </h1>
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
            <span>{farmState}</span>
            <span aria-hidden="true">&middot;</span>
            <span>{formatAcres(farmAcres, { short: true })} total</span>
            <Stamp>FY{eligibility.fiscal_year}</Stamp>
          </p>
        </div>

        <p className="reading max-w-[62ch] text-foreground">
          CSP pays you for the good conservation work you are already doing on
          your farm, plus activities you commit to adding over a
          {eligibility.contract_years !== undefined
            ? ` ${eligibility.contract_years}-year `
            : " multi-year "}
          contract. No cost-share required — you keep farming and get paid.
        </p>
      </div>

      {/* Most urgent confirmed deadline + notice if the state cutoff is not announced */}
      <CSPDeadlineBanners deadlines={upcomingDeadlines} />

      {/* Eligibility */}
      <section aria-labelledby="eligibility-section-heading" className="space-y-2">
        <div className="rule-head">
          <h2 id="eligibility-section-heading">Are you eligible?</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <Suspense fallback={<Loading label="Loading eligibility…" />}>
          <CSPEligibilityCard
            eligibility={eligibility}
            farmId={farmId}
            showDetailLink
          />
        </Suspense>
      </section>

      {/* Stewardship score */}
      <section aria-labelledby="score-section-heading" className="space-y-3">
        <div className="rule-head">
          <h2 id="score-section-heading">Your stewardship score</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <p className="reading max-w-[62ch] text-foreground">
          This score decides where your application ranks against other farms in{" "}
          {stateName}. A higher score means faster approval and a higher payment.
        </p>
        <Suspense fallback={<Loading label="Loading score…" />}>
          <CSPScoreGauge score={score} showBreakdown={false} />
        </Suspense>
        <ButtonLink
          href={`/csp/eligibility?farm_id=${encodeURIComponent(farmId)}`}
          variant="outline"
        >
          See full score breakdown
        </ButtonLink>
      </section>

      {/* Payment summary */}
      <section aria-labelledby="payment-section-heading" className="space-y-3">
        <div className="rule-head">
          <h2 id="payment-section-heading">Estimated payment</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <Suspense fallback={<Loading label="Loading payment estimate…" />}>
          {payment ? (
            <CSPPaymentSummary payment={payment} compact />
          ) : (
            <p className="max-w-[62ch] text-sm text-muted-foreground">
              A payment estimate is not available yet. Make sure your farm has
              registered fields, then try again.
            </p>
          )}
        </Suspense>
        <ButtonLink
          href={`/csp/payment?farm_id=${encodeURIComponent(farmId)}`}
          variant="outline"
        >
          View detailed payment breakdown
        </ButtonLink>
      </section>

      {/* Resource concerns */}
      <Suspense fallback={<Loading label="Loading conservation areas…" />}>
        <CSPResourceConcerns
          resourceConcerns={eligibility.resource_concerns_met}
        />
      </Suspense>

      {/* Improvement tips */}
      <ImprovementTips tips={score.improvement_recommendations} />

      {/* Next steps */}
      <section aria-labelledby="actions-heading" className="space-y-2">
        <div className="rule-head">
          <h2 id="actions-heading">What to do next</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <QuickActions farmId={farmId} />
      </section>

      {/* Apply */}
      <section aria-labelledby="apply-heading" className="space-y-3">
        <div className="rule-head">
          <h2 id="apply-heading">Ready to apply?</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <p className="reading max-w-[62ch] text-foreground">
          Your local NRCS service center schedules the site visit and takes your
          official application. Nothing you do here replaces that visit.
        </p>
        <ButtonLink
          href={NRCS_SERVICE_CENTER_LOCATOR_URL}
          external
          aria-label="Find your local NRCS office"
        >
          Find local NRCS office
        </ButtonLink>
      </section>

      {/* Disclaimer */}
      <p className="max-w-[62ch] border-t border-rule pt-3 text-xs leading-relaxed text-muted-foreground">
        {NRCS_DISCLAIMER}
      </p>
    </div>
  );
}
