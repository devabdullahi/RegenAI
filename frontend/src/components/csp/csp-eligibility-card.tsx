import {
  CheckCircle2,
  Clock,
  XCircle,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { CSPEligibility, CSPEligibilityStatus } from "@/lib/api/types";

// ── Status badge ──────────────────────────────────────────────────────────────

interface EligibilityBadgeProps {
  status: CSPEligibilityStatus;
  large?: boolean;
}

export function CSPEligibilityBadge({
  status,
  large = false,
}: EligibilityBadgeProps) {
  const base = large
    ? "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold"
    : "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold";

  if (status === "eligible") {
    return (
      <span className={`${base} bg-green-100 text-green-700`}>
        <CheckCircle2
          className={large ? "h-4 w-4" : "h-3 w-3"}
          aria-hidden="true"
        />
        Eligible
      </span>
    );
  }
  if (status === "act_now") {
    return (
      <span className={`${base} bg-amber-100 text-amber-700`}>
        <AlertTriangle
          className={large ? "h-4 w-4" : "h-3 w-3"}
          aria-hidden="true"
        />
        Almost Eligible
      </span>
    );
  }
  if (status === "not_eligible") {
    return (
      <span className={`${base} bg-red-100 text-red-700`}>
        <XCircle
          className={large ? "h-4 w-4" : "h-3 w-3"}
          aria-hidden="true"
        />
        Not Yet Eligible
      </span>
    );
  }
  return (
    <span className={`${base} bg-muted text-muted-foreground`}>
      <Clock
        className={large ? "h-4 w-4" : "h-3 w-3"}
        aria-hidden="true"
      />
      Not Evaluated
    </span>
  );
}

// ── Status explanation text ───────────────────────────────────────────────────

function statusExplanation(
  status: CSPEligibilityStatus,
  rcCount: number
): string {
  if (status === "eligible") {
    return `Your farm currently meets the conservation standards in ${rcCount} out of 8 areas. You qualify to apply for a 5-year CSP contract.`;
  }
  if (status === "act_now") {
    return `Your farm meets standards in ${rcCount} out of 8 areas. You need at least 2 to be eligible. One more improvement gets you there.`;
  }
  if (status === "not_eligible") {
    return `Your farm does not yet meet the minimum conservation standards. The action list below shows exactly what to work on.`;
  }
  return "We have not yet evaluated your farm for CSP eligibility. Request an evaluation to get started.";
}

// ── Main component ────────────────────────────────────────────────────────────

interface CSPEligibilityCardProps {
  eligibility: CSPEligibility;
  farmId: string;
  /** Show the "View Details" link button */
  showDetailLink?: boolean;
}

export function CSPEligibilityCard({
  eligibility,
  farmId,
  showDetailLink = true,
}: CSPEligibilityCardProps) {
  const {
    eligibility_status,
    rc_count_above_threshold,
    estimated_annual_payment,
    act_now_eligible,
    missing_requirements,
  } = eligibility;

  const borderColor =
    eligibility_status === "eligible"
      ? "border-green-200"
      : eligibility_status === "act_now"
        ? "border-amber-200"
        : eligibility_status === "not_eligible"
          ? "border-red-200"
          : "border-border";

  const bgColor =
    eligibility_status === "eligible"
      ? "bg-green-50"
      : eligibility_status === "act_now"
        ? "bg-amber-50"
        : eligibility_status === "not_eligible"
          ? "bg-red-50"
          : "bg-muted/30";

  return (
    <Card className={`border ${borderColor}`}>
      <CardHeader className={`rounded-t-lg ${bgColor} pb-3`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <CSPEligibilityBadge status={eligibility_status} large />
            {act_now_eligible && (
              <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-primary px-2.5 py-0.5 text-xs font-semibold text-primary-foreground">
                <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                ACT NOW — Instant Approval Available
              </span>
            )}
          </div>
          {estimated_annual_payment !== null &&
            estimated_annual_payment !== undefined && (
              <div className="text-right">
                <p className="text-xs text-muted-foreground">Estimated annual payment</p>
                <p className="font-heading text-2xl font-bold text-primary leading-tight">
                  ${estimated_annual_payment.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">per year</p>
              </div>
            )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-4">
        {/* Explanation */}
        <p className="text-sm text-muted-foreground leading-relaxed">
          {statusExplanation(eligibility_status, rc_count_above_threshold)}
        </p>

        {/* RC count summary */}
        <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
            <span className="text-sm font-bold text-primary">
              {rc_count_above_threshold}
            </span>
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">
              {rc_count_above_threshold} of 8 conservation areas currently met
            </p>
            <p className="text-xs text-muted-foreground">
              Minimum required: 2 areas
            </p>
          </div>
        </div>

        {/* Missing requirements */}
        {missing_requirements.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              What you need to do next
            </p>
            <ul className="space-y-2" aria-label="Missing requirements">
              {missing_requirements.map((req, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <Clock
                    className="mt-0.5 h-4 w-4 shrink-0 text-amber-500"
                    aria-hidden="true"
                  />
                  <span className="text-foreground leading-snug">{req}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* CTA */}
        {showDetailLink && (
          <Link href={`/csp/eligibility?farm_id=${farmId}`}>
            <Button
              variant="outline"
              className="w-full min-h-[48px] cursor-pointer text-primary border-primary/30 hover:bg-primary/5 hover:border-primary"
            >
              View Eligibility Details
              <ChevronRight className="ml-1 h-4 w-4" aria-hidden="true" />
            </Button>
          </Link>
        )}
      </CardContent>
    </Card>
  );
}
