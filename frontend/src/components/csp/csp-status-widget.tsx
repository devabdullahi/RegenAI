import { ButtonLink } from "@/components/shared/button-link";
import { CSPEligibilityBadge } from "@/components/csp/csp-eligibility-card";
import { EdgeNote, LedgerRow, Sheet } from "@/components/shared/record";
import { formatUsd } from "@/lib/format";
import type { CSPEligibility } from "@/lib/api/types";

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
    resource_concerns_met,
    act_now_eligible,
  } = eligibility;

  const cspHref = `/csp?farm_id=${encodeURIComponent(farmId)}`;
  const rcTotal = resource_concerns_met.length;
  const hasPayment =
    estimated_annual_payment !== null && estimated_annual_payment !== undefined;

  return (
    <Sheet className="space-y-3 px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-heading text-base font-semibold text-foreground">
            Conservation Stewardship Program
          </p>
          <p className="font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
            CSP — multi-year USDA contract
          </p>
        </div>
        <CSPEligibilityBadge status={eligibility_status} />
      </div>

      <div className="border-t border-rule pt-1">
        <LedgerRow
          label="Stewardship score"
          value={`${stewardship_score} / 100 pts`}
        />
        <LedgerRow
          label="Conservation areas met"
          value={rcTotal > 0 ? `${rc_count_above_threshold} of ${rcTotal}` : `${rc_count_above_threshold}`}
        />
        <LedgerRow
          label="Estimated payment"
          value={hasPayment ? `${formatUsd(estimated_annual_payment)}/yr` : "—"}
        />
      </div>

      {act_now_eligible && (
        <EdgeNote tone="success">
          Your score meets the estimated state ranking threshold. You may qualify
          for the ACT NOW fast-track if your state offers it.
        </EdgeNote>
      )}

      <ButtonLink href={cspHref} variant="outline" className="w-full">
        View CSP details
      </ButtonLink>
    </Sheet>
  );
}
