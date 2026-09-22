import Link from "next/link";
import { Check } from "lucide-react";
import { ButtonLink } from "@/components/shared/button-link";
import { EdgeNote, LedgerRow, RuleHead, Stamp } from "@/components/shared/record";

import { CSPEligibilityBadge } from "@/components/csp/csp-eligibility-card";
import { CSPScoreGauge } from "@/components/csp/csp-score-gauge";
import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";
import { CSPReevaluateButton } from "@/components/csp/csp-reevaluate-button";

import { api } from "@/lib/api/server-client";
import {
  adaptDeadlines,
  adaptEligibility,
  scoreFromEligibility,
} from "@/lib/api/adapters";

import {
  NRCS_DISCLAIMER,
  NRCS_SERVICE_CENTER_LOCATOR_URL,
  practiceStandardStamp,
} from "@/lib/csp-status";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

import type { Metadata } from "next";
import type { CSPResourceConcernResult, CSPEligibility, CSPScore } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "CSP Eligibility — RegenAI",
};

interface EligibilityPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

// ── A box on a form: checked or blank, never a coloured circle ───────────────

function CheckBox({ checked }: { checked: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center border",
        checked ? "border-foreground text-foreground" : "border-border"
      )}
    >
      {checked && <Check className="h-3 w-3" />}
    </span>
  );
}

// ── Resource concern detail ───────────────────────────────────────────────────

function ResourceConcernDetail({
  rc,
  farmId,
}: {
  rc: CSPResourceConcernResult;
  farmId: string;
}) {
  const met = rc.currently_met;

  return (
    <li className="space-y-2 border-b border-rule py-4 last:border-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground">{rc.name}</p>
          <p
            className={cn(
              "font-mono text-[0.6875rem] tracking-[0.08em] uppercase",
              met ? "text-success" : "text-warning-foreground"
            )}
          >
            {met ? "Threshold met" : "Not yet met"}
          </p>
        </div>
        <div className="text-right font-mono text-sm whitespace-nowrap text-foreground">
          {rc.points_earned} pts
          <span className="ml-3 text-muted-foreground">{rc.score} / 100</span>
        </div>
      </div>

      {rc.evidence.length > 0 && (
        <div>
          <p className="font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
            Based on your farm data
          </p>
          <ul className="mt-1 space-y-0.5">
            {rc.evidence.map((e, i) => (
              <li key={i} className="text-xs leading-relaxed text-muted-foreground">
                {e}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Gap-closing activities from the API for unmet concerns */}
      {!met && (
        <div className="space-y-1">
          {rc.suggested_activities.length > 0 && (
            <>
              <p className="font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
                Recommended activities for this area
              </p>
              <ul className="space-y-1">
                {rc.suggested_activities.map((activity) => (
                  <li
                    key={activity.code}
                    className="flex flex-wrap items-center gap-2 text-xs text-foreground"
                  >
                    <Stamp>
                      {practiceStandardStamp(activity.practice_standard_code)}
                    </Stamp>
                    <span className="sr-only">
                      NRCS practice standard {activity.practice_standard_code}
                    </span>
                    {activity.name}
                  </li>
                ))}
              </ul>
            </>
          )}
          <Link
            href={`/csp/enhancements?farm_id=${encodeURIComponent(farmId)}`}
            className="inline-flex min-h-12 items-center text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            See conservation activities
          </Link>
        </div>
      )}
    </li>
  );
}

// ── Application steps ─────────────────────────────────────────────────────────

function EligibilityTimeline({
  rcCount,
  totalConcernCount,
  minRequired,
  meetsMin,
  additionalRequired,
  contractYears,
  hasCommitment,
  hasEnhancements,
  farmId,
}: {
  rcCount: number;
  totalConcernCount: number;
  minRequired: number | undefined;
  meetsMin: boolean;
  additionalRequired: number | undefined;
  contractYears: number | undefined;
  hasCommitment: boolean;
  hasEnhancements: boolean;
  farmId: string;
}) {
  let concernDetail: string;
  if (meetsMin) {
    concernDetail = `${rcCount} of ${totalConcernCount} areas currently above threshold`;
  } else if (minRequired !== undefined) {
    concernDetail = `${rcCount} of ${minRequired} required areas met — keep working`;
  } else {
    concernDetail = `${rcCount} areas met so far — keep working`;
  }

  const steps = [
    {
      label:
        minRequired !== undefined
          ? `Meet ${minRequired} or more conservation areas`
          : "Meet the required number of conservation areas",
      detail: concernDetail,
      done: meetsMin,
    },
    {
      label:
        additionalRequired !== undefined
          ? `Commit to improving at least ${additionalRequired} more area${additionalRequired === 1 ? "" : "s"}`
          : "Commit to improving additional conservation areas",
      detail: hasCommitment
        ? "Enhancement activities selected and committed"
        : "Select an enhancement activity to make this commitment",
      done: hasCommitment,
      actionHref: `/csp/enhancements?farm_id=${encodeURIComponent(farmId)}`,
      actionLabel: "Select enhancements",
    },
    {
      label: "Select enhancement activities",
      detail: hasEnhancements
        ? "Enhancement activities chosen"
        : "Choose which conservation activities to add",
      done: hasEnhancements,
      actionHref: `/csp/enhancements?farm_id=${encodeURIComponent(farmId)}`,
      actionLabel: "Browse enhancements",
    },
    {
      label: "Contact your local NRCS office",
      detail:
        contractYears !== undefined
          ? `A conservation planner will schedule a site visit and finalize your ${contractYears}-year contract`
          : "A conservation planner will schedule a site visit and finalize your contract",
      done: false,
      actionHref: NRCS_SERVICE_CENTER_LOCATOR_URL,
      actionLabel: "Find my NRCS office",
      external: true,
    },
  ];

  return (
    <section aria-labelledby="steps-heading" className="space-y-2">
      <div className="rule-head">
        <h2 id="steps-heading">Steps to apply</h2>
        <span aria-hidden="true" className="h-px flex-1 bg-rule" />
      </div>
      <ol className="mt-1" aria-label="Application steps">
        {steps.map((step, i) => (
          <li
            key={i}
            className="flex items-start gap-3 border-b border-rule py-3 last:border-0"
          >
            <CheckBox checked={step.done} />
            <div className="min-w-0 flex-1">
              <p className="text-sm leading-snug font-medium text-foreground">
                {step.label}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {step.detail}
              </p>
              {!step.done &&
                step.actionHref &&
                (step.external ? (
                  <a
                    href={step.actionHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-12 items-center text-sm font-medium text-primary underline-offset-4 hover:underline"
                  >
                    {step.actionLabel}
                    <span className="sr-only"> (opens in new tab)</span>
                  </a>
                ) : (
                  <Link
                    href={step.actionHref}
                    className="inline-flex min-h-12 items-center text-sm font-medium text-primary underline-offset-4 hover:underline"
                  >
                    {step.actionLabel}
                  </Link>
                ))}
            </div>
            <span
              className={cn(
                "shrink-0 font-mono text-[0.6875rem] tracking-[0.08em] uppercase",
                step.done ? "text-success" : "text-muted-foreground"
              )}
            >
              {step.done ? "Done" : "To do"}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

// ── Error / no-farm states ────────────────────────────────────────────────────

function ErrorState({ message }: { message: string }) {
  return (
    <div className="max-w-[62ch] space-y-4 py-10">
      <RuleHead label="CSP eligibility" />
      <h2 className="font-heading text-xl font-semibold text-foreground">
        Unable to load eligibility data
      </h2>
      <p className="text-sm text-muted-foreground">{message}</p>
      <ButtonLink href="/farms" variant="outline">
        Back to farms
      </ButtonLink>
    </div>
  );
}

function NoFarmSelected() {
  return (
    <div className="max-w-[62ch] space-y-4 py-10">
      <RuleHead label="CSP eligibility" />
      <h2 className="font-heading text-xl font-semibold text-foreground">
        Select a farm first
      </h2>
      <p className="text-sm text-muted-foreground">
        Choose a farm to view CSP eligibility details.
      </p>
      <ButtonLink href="/farms">Go to My Farms</ButtonLink>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function CspEligibilityPage({
  searchParams,
}: EligibilityPageProps) {
  const params = await searchParams;
  const farmId =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  if (!farmId) {
    return <NoFarmSelected />;
  }

  let eligibility: CSPEligibility;
  let score: CSPScore;
  let farmName: string;

  try {
    const [eligibilityResp, farm] = await Promise.all([
      api.csp.getEligibility(farmId),
      api.farms.get(farmId),
    ]);
    farmName = farm.name;
    // Enhancements only after eligibility: that call persists the assessment
    // GET /csp/enhancements ranks against. Both are optional enrichments.
    const [deadlinesResp, enhancementsResp] = await Promise.all([
      api.csp.getDeadlines(farm.state).catch(() => null),
      api.csp.getEnhancements(farmId).catch((err: unknown) => {
        console.error(`csp/eligibility page: enhancements failed farm=${farmId}`, err);
        return null;
      }),
    ]);
    eligibility = adaptEligibility(eligibilityResp, {
      deadlines: adaptDeadlines(deadlinesResp),
      enhancements: enhancementsResp,
    });
    score = scoreFromEligibility(
      eligibilityResp,
      eligibility.missing_requirements
    );
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "An unexpected error occurred.";
    return <ErrorState message={message} />;
  }
  const hasCommitment = eligibility.rc_count_will_meet > 0;
  const hasEnhancements = eligibility.active_enhancement_codes.length > 0;
  const totalConcernCount = eligibility.resource_concerns_met.length;

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
          <Link
            href={`/csp?farm_id=${encodeURIComponent(farmId)}`}
            className="hover:text-foreground"
          >
            CSP Navigator
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <span aria-current="page" className="font-medium text-foreground">
            Eligibility
          </span>
        </nav>
        <div className="border-b-2 border-rule-strong pb-3">
          <h1 className="font-heading text-[1.75rem] leading-tight font-bold text-foreground sm:text-3xl">
            CSP Eligibility
          </h1>
          <p className="mt-2 font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
            How your farm scores on each of the {totalConcernCount} conservation
            areas
          </p>
        </div>
      </div>

      {/* Deadline alerts */}
      <CSPDeadlineBanners deadlines={eligibility.upcoming_deadlines} />

      {/* Summary */}
      <section aria-labelledby="summary-heading" className="space-y-3">
        <div className="rule-head">
          <h2 id="summary-heading">Determination</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <CSPEligibilityBadge
              status={eligibility.eligibility_status}
              large
            />
            {eligibility.act_now_eligible &&
              eligibility.act_now_threshold !== null && (
                <p className="max-w-[62ch] text-sm leading-relaxed text-foreground">
                  May qualify for ACT NOW fast-track. Your score of{" "}
                  <span className="font-mono">
                    {eligibility.estimated_ranking_score} pts
                  </span>{" "}
                  meets the state ranking threshold of{" "}
                  <span className="font-mono">
                    {eligibility.act_now_threshold} pts
                  </span>
                  . If your state offers ACT NOW, your application may be
                  eligible for fast-track approval. ACT NOW is used at the
                  state&apos;s discretion and is not guaranteed.
                </p>
              )}
            {eligibility.act_now_threshold === null && (
              <p className="max-w-[62ch] text-sm leading-relaxed text-muted-foreground">
                Your state has not published a ranking threshold, so there is no
                score to compare yours against. NRCS ranks applications in your
                state.
              </p>
            )}
          </div>
          <div className="text-right">
            <p className="font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
              Stewardship score
            </p>
            <p className="font-mono text-[2rem] leading-none font-medium text-foreground">
              {eligibility.stewardship_score}
            </p>
            <p className="font-mono text-xs text-muted-foreground">
              pts of 100 pts
            </p>
          </div>
        </div>

        <p className="reading max-w-[62ch] text-foreground">
          {eligibility.notes}
        </p>

        {eligibility.ineligibility_reasons.length > 0 && (
          <EdgeNote tone="destructive" title="Why your farm is not eligible yet">
            <ul className="mt-1 space-y-1">
              {eligibility.ineligibility_reasons.map((r, i) => (
                <li key={i} className="text-sm text-destructive">
                  {r}
                </li>
              ))}
            </ul>
          </EdgeNote>
        )}
      </section>

      {/* Score breakdown */}
      <section aria-labelledby="score-heading" className="space-y-3">
        <div className="rule-head">
          <h2 id="score-heading">Score breakdown</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <p className="text-sm text-muted-foreground">
          Points earned across all {totalConcernCount} conservation areas
        </p>
        <CSPScoreGauge score={score} showBreakdown />
      </section>

      {/* Conservation area details */}
      <section aria-labelledby="rc-details-heading" className="space-y-2">
        <div className="rule-head">
          <h2 id="rc-details-heading">Conservation area details</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <ul className="mt-1">
          {eligibility.resource_concerns_met.map((rc) => (
            <ResourceConcernDetail key={rc.code} rc={rc} farmId={farmId} />
          ))}
        </ul>
      </section>

      {/* Steps */}
      <EligibilityTimeline
        rcCount={eligibility.rc_count_above_threshold}
        totalConcernCount={totalConcernCount}
        minRequired={eligibility.min_concerns_required}
        meetsMin={eligibility.meets_min_concerns}
        additionalRequired={eligibility.additional_concerns_required}
        contractYears={eligibility.contract_years}
        hasCommitment={hasCommitment}
        hasEnhancements={hasEnhancements}
        farmId={farmId}
      />

      {/* Re-evaluate */}
      <section aria-labelledby="record-heading" className="space-y-2">
        <div className="rule-head">
          <h2 id="record-heading">Record</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0 flex-1">
            <LedgerRow
              label="Last evaluated"
              value={formatDateTime(eligibility.evaluated_at, { month: "long" })}
              note={
                eligibility.from_cache
                  ? "Showing cached results. Re-evaluate to refresh."
                  : "Eligibility is recalculated automatically when your farm data changes."
              }
            />
          </div>
          <CSPReevaluateButton farmId={farmId} />
        </div>
      </section>

      {/* Disclaimer */}
      <p className="max-w-[62ch] border-t border-rule pt-3 text-xs leading-relaxed text-muted-foreground">
        {NRCS_DISCLAIMER}
      </p>
    </div>
  );
}
