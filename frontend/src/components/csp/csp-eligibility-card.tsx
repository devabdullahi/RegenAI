import { ButtonLink } from "@/components/shared/button-link";
import { LedgerRow, RuleHead, Sheet } from "@/components/shared/record";
import { Badge } from "@/components/ui/badge";
import { formatUsd } from "@/lib/format";
import { type Tone } from "@/lib/status-styles";
import { cn } from "@/lib/utils";
import type { CSPEligibility, CSPEligibilityStatus } from "@/lib/api/types";

// ── Status stamp ──────────────────────────────────────────────────────────────

// Backend semantics: "act_now" = eligible AND meets the state ranking
// threshold; ACT NOW is at state discretion, so this is "may qualify", not a
// guarantee. "pending_review" = some but not all required concerns met.
const STATUS_BADGE: Record<CSPEligibilityStatus, { label: string; tone: Tone }> = {
  eligible: { label: "Eligible", tone: "success" },
  act_now: { label: "Eligible · May qualify for ACT NOW", tone: "success" },
  pending_review: { label: "Almost Eligible", tone: "warning" },
  not_eligible: { label: "Not Yet Eligible", tone: "destructive" },
};

const NOT_EVALUATED_BADGE = { label: "Not Evaluated", tone: "neutral" as Tone };

/** Square, mono, stamped — the status as it would be inked on a form. */
const TONE_BADGE_CLASSES: Record<Tone, string> = {
  accent: "border-accent bg-transparent text-accent",
  success: "border-success bg-transparent text-success",
  warning: "border-warning bg-transparent text-warning-foreground",
  destructive: "border-destructive bg-transparent text-destructive",
  info: "border-info bg-transparent text-info",
  neutral: "border-border bg-transparent text-muted-foreground",
};

interface EligibilityBadgeProps {
  status: CSPEligibilityStatus;
  large?: boolean;
}

export function CSPEligibilityBadge({
  status,
  large = false,
}: EligibilityBadgeProps) {
  const { label, tone } = STATUS_BADGE[status] ?? NOT_EVALUATED_BADGE;

  return (
    <Badge
      variant="outline"
      className={cn(
        TONE_BADGE_CLASSES[tone],
        large && "h-auto min-h-6 px-2 py-0.5 text-xs whitespace-normal"
      )}
    >
      {label}
    </Badge>
  );
}

// ── Status explanation text ───────────────────────────────────────────────────

/** "2 of 8" when the total is known, otherwise just "2". */
export function concernCountLabel(count: number, total: number): string {
  return total > 0 ? `${count} of ${total}` : `${count}`;
}

function statusExplanation(
  status: CSPEligibilityStatus,
  rcCount: number,
  rcTotal: number,
  minRequired: number | undefined
): string {
  const areas = `${concernCountLabel(rcCount, rcTotal)} conservation areas`;
  if (status === "eligible") {
    return `Your farm currently meets the conservation standards in ${areas}. You qualify to apply for a CSP contract.`;
  }
  if (status === "act_now") {
    return `Your farm meets the conservation standards in ${areas} and your score meets the estimated state ranking threshold. You may qualify for the ACT NOW fast-track if your state offers it. Approval is not guaranteed.`;
  }
  if (status === "pending_review") {
    const need =
      minRequired !== undefined
        ? ` You need at least ${minRequired} to be eligible.`
        : " You need the required number of conservation areas to be eligible.";
    return `Your farm meets standards in ${areas}.${need}`;
  }
  if (status === "not_eligible") {
    return "Your farm does not yet meet the minimum conservation standards. The action list below shows exactly what to work on.";
  }
  return "We have not yet evaluated your farm for CSP eligibility. Request an evaluation to get started.";
}

// ── Main component ────────────────────────────────────────────────────────────

interface CSPEligibilityCardProps {
  eligibility: CSPEligibility;
  farmId: string;
  /** Show the "View eligibility details" link button */
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
    resource_concerns_met,
    min_concerns_required,
    estimated_annual_payment,
    act_now_eligible,
    missing_requirements,
  } = eligibility;

  const rcTotal = resource_concerns_met.length;

  return (
    <Sheet className="space-y-4 px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <CSPEligibilityBadge status={eligibility_status} large />
          {act_now_eligible && (
            <p className="max-w-[46ch] text-sm text-foreground">
              May qualify for ACT NOW fast-track (if your state offers it)
            </p>
          )}
        </div>
        {estimated_annual_payment !== null &&
          estimated_annual_payment !== undefined && (
            <div className="text-right">
              <p className="font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
                Estimated annual payment
              </p>
              <p className="font-mono text-2xl leading-tight font-medium text-foreground">
                {formatUsd(estimated_annual_payment)}
              </p>
              <p className="font-mono text-xs text-muted-foreground">per year</p>
            </div>
          )}
      </div>

      {/* Explanation */}
      <p className="reading max-w-[62ch] text-foreground">
        {statusExplanation(
          eligibility_status,
          rc_count_above_threshold,
          rcTotal,
          min_concerns_required
        )}
      </p>

      {/* Count of areas met */}
      <div className="border-t border-rule pt-1">
        <LedgerRow
          label="Conservation areas currently met"
          note={
            min_concerns_required !== undefined
              ? `Minimum required: ${min_concerns_required} areas`
              : undefined
          }
          value={concernCountLabel(rc_count_above_threshold, rcTotal)}
        />
      </div>

      {/* Missing requirements */}
      {missing_requirements.length > 0 && (
        <div className="space-y-2">
          <RuleHead label="What you need to do next" />
          <ul className="space-y-1.5" aria-label="Missing requirements">
            {missing_requirements.map((req) => (
              <li key={req} className="text-sm leading-snug text-foreground">
                {req}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* CTA */}
      {showDetailLink && (
        <ButtonLink
          href={`/csp/eligibility?farm_id=${encodeURIComponent(farmId)}`}
          variant="outline"
          className="w-full"
        >
          View eligibility details
        </ButtonLink>
      )}
    </Sheet>
  );
}
