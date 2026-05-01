import Link from "next/link";
import {
  ShieldCheck,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
} from "lucide-react";
import type { CSPEligibility, CSPEligibilityStatus } from "@/lib/api/types";

// ── Compact status badge ──────────────────────────────────────────────────────

function CompactBadge({ status }: { status: CSPEligibilityStatus }) {
  if (status === "eligible") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
        Eligible
      </span>
    );
  }
  if (status === "act_now") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
        <AlertTriangle className="h-3 w-3" aria-hidden="true" />
        Almost Eligible
      </span>
    );
  }
  if (status === "not_eligible") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
        <XCircle className="h-3 w-3" aria-hidden="true" />
        Not Yet Eligible
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">
      <Clock className="h-3 w-3" aria-hidden="true" />
      Not Evaluated
    </span>
  );
}

// ── Widget ─────────────────────────────────────────────────────────────────────

interface CspStatusWidgetProps {
  eligibility: CSPEligibility;
  farmId: string;
}

export function CspStatusWidget({ eligibility, farmId }: CspStatusWidgetProps) {
  const {
    eligibility_status,
    stewardship_score,
    estimated_annual_payment,
    rc_count_above_threshold,
    act_now_eligible,
  } = eligibility;

  const cspHref = `/csp?farm_id=${farmId}`;

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
            <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">
              Conservation Stewardship Program
            </p>
            <p className="text-xs text-muted-foreground">
              CSP — 5-year USDA contract
            </p>
          </div>
        </div>
        <CompactBadge status={eligibility_status} />
      </div>

      {/* Key metrics row */}
      <div className="grid grid-cols-3 gap-2 rounded-lg bg-muted/40 px-2 py-2">
        <div className="text-center">
          <p className="font-heading text-lg font-bold text-foreground leading-tight">
            {stewardship_score}
          </p>
          <p className="text-xs text-muted-foreground">Score /100</p>
        </div>
        <div className="text-center border-x border-border">
          <p className="font-heading text-lg font-bold text-foreground leading-tight">
            {rc_count_above_threshold}
            <span className="text-xs font-normal text-muted-foreground">/8</span>
          </p>
          <p className="text-xs text-muted-foreground">Areas met</p>
        </div>
        <div className="text-center">
          {estimated_annual_payment !== null &&
          estimated_annual_payment !== undefined ? (
            <>
              <p className="font-heading text-lg font-bold text-primary leading-tight">
                $
                {estimated_annual_payment.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </p>
              <p className="text-xs text-muted-foreground">Per year</p>
            </>
          ) : (
            <>
              <p className="font-heading text-lg font-bold text-muted-foreground">
                —
              </p>
              <p className="text-xs text-muted-foreground">Estimate</p>
            </>
          )}
        </div>
      </div>

      {/* ACT NOW callout */}
      {act_now_eligible && (
        <p className="rounded-lg bg-primary/5 border border-primary/20 px-3 py-2 text-xs font-medium text-primary">
          Your score qualifies for ACT NOW — instant contract approval available
          during the application window.
        </p>
      )}

      {/* CTA */}
      <Link href={cspHref}>
        <button
          type="button"
          className="flex w-full min-h-[48px] items-center justify-center gap-1 rounded-lg border border-primary/30 bg-transparent px-4 py-2.5 text-sm font-semibold text-primary hover:bg-primary/5 hover:border-primary transition-colors cursor-pointer"
          aria-label="View CSP Navigator details"
        >
          View CSP Details
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </Link>
    </div>
  );
}
