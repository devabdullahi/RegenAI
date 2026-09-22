import { Stamp } from "@/components/shared/record";
import { practiceStandardStamp } from "@/lib/csp-status";
import { toneTextClasses } from "@/lib/status-styles";
import { cn } from "@/lib/utils";
import type { CSPEnhancement } from "@/lib/api/types";

/**
 * Conservation activities listed the way a practice schedule is printed: the
 * practice code stamped, the points and dollars in a mono column on the right,
 * hairlines between entries.
 */

// ── Impact label ──────────────────────────────────────────────────────────────

function impactLabel(points: number): string {
  if (points >= 13) return "High impact";
  if (points >= 8) return "Medium impact";
  return "Lower impact";
}

// ── Status word ───────────────────────────────────────────────────────────────

const STATUS_WORD: Record<string, { label: string; className: string }> = {
  active: { label: "Active", className: "text-success" },
  committed: { label: "Committed", className: "text-primary" },
  considering: { label: "Considering", className: "text-muted-foreground" },
};

function StatusWord({ status }: { status: CSPEnhancement["status"] }) {
  const entry = status ? STATUS_WORD[status] : undefined;
  if (!entry) return null;
  return (
    <span
      className={cn(
        "font-mono text-[0.6875rem] tracking-[0.08em] uppercase",
        entry.className
      )}
    >
      {entry.label}
    </span>
  );
}

// ── Single activity row ───────────────────────────────────────────────────────

function EnhancementItem({ enhancement }: { enhancement: CSPEnhancement }) {
  return (
    <li className="space-y-2 border-b border-rule py-4 last:border-0">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Stamp>{practiceStandardStamp(enhancement.practice_standard_code)}</Stamp>
            <span className="sr-only">
              NRCS practice standard {enhancement.practice_standard_code}
            </span>
            <StatusWord status={enhancement.status} />
          </div>
          <p className="mt-1.5 text-sm leading-snug font-semibold text-foreground">
            {enhancement.name}
          </p>
          <p className="text-xs text-muted-foreground">{enhancement.category}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-mono text-sm font-medium text-foreground">
            +{enhancement.point_weight} pts
          </p>
          <p className="font-mono text-[0.6875rem] text-muted-foreground uppercase">
            {impactLabel(enhancement.point_weight)}
          </p>
        </div>
      </div>

      <p className="max-w-[62ch] text-sm leading-relaxed text-muted-foreground">
        {enhancement.description}
      </p>

      {enhancement.implementation_notes && (
        <p className="max-w-[62ch] text-xs leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">How it works: </span>
          {enhancement.implementation_notes}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <div className="flex flex-wrap items-center gap-x-4 font-mono text-xs text-muted-foreground">
          <span title={enhancement.rate_is_estimate ? enhancement.rate_basis : undefined}>
            ${enhancement.base_payment_rate.toFixed(2)}/{enhancement.payment_unit}
            {enhancement.rate_is_estimate ? " (est.)" : ""}
          </span>
          {enhancement.higher_payment && (
            <span className={cn("font-medium", toneTextClasses.warning)}>
              Higher payment
              {enhancement.higher_payment_category
                ? `: ${enhancement.higher_payment_category}`
                : ""}
            </span>
          )}
        </div>
        {enhancement.estimated_payment !== undefined &&
          enhancement.estimated_payment !== null && (
            <span className="font-mono text-sm font-medium text-foreground">
              ~${enhancement.estimated_payment.toLocaleString()}/yr
            </span>
          )}
      </div>
    </li>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface CSPEnhancementListProps {
  enhancements: CSPEnhancement[];
  title?: string;
  showEmpty?: boolean;
}

export function CSPEnhancementList({
  enhancements,
  title = "Recommended conservation activities",
  showEmpty = true,
}: CSPEnhancementListProps) {
  if (enhancements.length === 0 && !showEmpty) return null;

  // Two lists can appear on one page, so the heading id follows the title.
  const headingId = `enhancements-${title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")}`;

  return (
    <section aria-labelledby={headingId} className="space-y-2">
      <div className="rule-head">
        <h2 id={headingId}>{title}</h2>
        <span aria-hidden="true" className="h-px flex-1 bg-rule" />
      </div>
      <p className="max-w-[62ch] text-sm text-muted-foreground">
        Conservation activities that increase your score and add to your annual
        payment
      </p>

      {enhancements.length === 0 ? (
        <p className="py-6 text-sm text-muted-foreground">
          No activities available. Complete your eligibility evaluation first.
        </p>
      ) : (
        <ul className="mt-2" aria-label="Conservation activities">
          {enhancements.map((enh) => (
            <EnhancementItem key={enh.id} enhancement={enh} />
          ))}
        </ul>
      )}
    </section>
  );
}
