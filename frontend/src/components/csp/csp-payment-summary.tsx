import { LedgerRow, RuleHead, Stamp, EdgeNote } from "@/components/shared/record";
import { formatAcres, formatUsd } from "@/lib/format";
import { practiceStandardStamp } from "@/lib/csp-status";
import { cn } from "@/lib/utils";
import { toneTextClasses } from "@/lib/status-styles";
import type { CSPPaymentEstimate, CSPRuleCitation } from "@/lib/api/types";

/**
 * The payment estimate printed as a scale ticket: one line per amount, dotted
 * leaders, a rule above the total, and the total set as the largest figure on
 * the sheet. Every amount keeps the source and as-of date it arrived with.
 */

// ── Rule citation ─────────────────────────────────────────────────────────────

function formatAsOf(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** Small "Rules as of <date> · source" caption, set in mono like a file note. */
export function CSPRulesCitation({
  rules,
  className = "",
}: {
  rules: CSPRuleCitation;
  className?: string;
}) {
  return (
    <p className={cn("font-mono text-xs text-muted-foreground", className)}>
      Rules as of {formatAsOf(rules.as_of)}
      {rules.source_url && (
        <>
          {" "}
          &middot;{" "}
          <a
            href={rules.source_url}
            target="_blank"
            rel="noopener noreferrer"
            title={rules.source_title}
            className="inline-flex min-h-12 items-center underline underline-offset-2 hover:text-foreground"
          >
            source
          </a>
        </>
      )}
    </p>
  );
}

// ── Activity breakdown table ──────────────────────────────────────────────────

const COL_HEAD =
  "py-1.5 font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase";

function ActivityTable({
  items,
  rateBasis,
}: {
  items: CSPPaymentEstimate["activity_breakdown"];
  rateBasis: string;
}) {
  if (items.length === 0) return null;

  return (
    <div className="space-y-2">
      <RuleHead label="Conservation activity payments (estimated)" />
      <div className="overflow-x-auto">
        <table className="w-full text-sm" aria-label="Activity payment breakdown">
          <thead>
            <tr className="border-b border-rule">
              <th scope="col" className={cn(COL_HEAD, "text-left")}>
                Activity
              </th>
              <th scope="col" className={cn(COL_HEAD, "pl-3 text-right")}>
                Est. rate / acre
              </th>
              <th scope="col" className={cn(COL_HEAD, "pl-3 text-right")}>
                Payment
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.code} className="border-b border-rule last:border-0">
                <th
                  scope="row"
                  className="py-2 pr-3 text-left align-top font-normal"
                >
                  <span className="block text-sm text-foreground">
                    {item.name}
                  </span>
                  <span className="mt-1 inline-flex items-center gap-2">
                    <Stamp>{practiceStandardStamp(item.practice_standard_code)}</Stamp>
                    <span className="sr-only">
                      NRCS practice standard {item.practice_standard_code}
                    </span>
                  </span>
                  {item.higher_payment && (
                    <span
                      className={cn(
                        "mt-1 block text-xs font-medium",
                        toneTextClasses.warning
                      )}
                    >
                      Higher payment
                      {item.higher_payment_category
                        ? `: ${item.higher_payment_category}`
                        : ""}
                    </span>
                  )}
                </th>
                <td className="py-2 pl-3 text-right align-top font-mono text-sm whitespace-nowrap text-muted-foreground">
                  ${item.rate_per_acre.toFixed(2)}/ac
                  {item.rate_is_estimate && (
                    <span aria-label="estimate">*</span>
                  )}
                </td>
                <td className="py-2 pl-3 text-right align-top font-mono text-sm whitespace-nowrap text-foreground">
                  {formatUsd(item.payment)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">* {rateBasis}.</p>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface CSPPaymentSummaryProps {
  payment: CSPPaymentEstimate;
  /** Compact mode for the overview: totals only, no line-by-line ticket */
  compact?: boolean;
}

export function CSPPaymentSummary({
  payment,
  compact = false,
}: CSPPaymentSummaryProps) {
  const {
    fiscal_year,
    eap_annual,
    activity_payment_annual,
    annual_total,
    contract_5yr_total,
    contract_years,
    per_acre_annual,
    total_cropland_acres,
    rc_count_above_threshold,
    contract_limit_label,
    contract_limit_applied,
    eap_label,
    annual_payment_limit,
    activity_breakdown,
    activity_rate_basis,
    rules,
    disclaimer,
  } = payment;

  return (
    <div className="space-y-6">
      {/* The ticket */}
      <div>
        <RuleHead
          label="Estimated payment"
          action={<Stamp>FY{fiscal_year}</Stamp>}
        />

        <div className="mt-1">
          {!compact && (
            <div>
              <LedgerRow
                label="Existing Activity Payment (EAP)"
                note={`Fixed payment per contract each year (${eap_label})`}
                value={formatUsd(eap_annual)}
              />
              <LedgerRow
                label="Conservation activity payments"
                note="Estimated from per-acre rates for the activities below"
                value={formatUsd(activity_payment_annual)}
              />
            </div>
          )}

          {/* The total, set above the rule the way a ticket foots up */}
          <div className="border-t border-rule-strong pt-1">
            <LedgerRow
              label="Total estimated each year"
              value={
                <span className="font-mono text-2xl leading-none font-medium text-foreground">
                  {formatUsd(annual_total)}
                </span>
              }
            />
            <LedgerRow
              label={`Total estimated over the ${contract_years}-year contract`}
              note={
                contract_limit_applied
                  ? `Capped at the ${contract_limit_label}`
                  : `Annual payment x ${contract_years} years`
              }
              value={formatUsd(contract_5yr_total)}
            />
            <LedgerRow
              label="Per acre each year"
              value={`$${per_acre_annual.toFixed(2)}/ac`}
            />
          </div>

          {!compact && (
            <div className="mt-1 border-t border-rule pt-1">
              <LedgerRow
                label="Cropland acres in the estimate"
                value={formatAcres(total_cropland_acres, { short: true })}
              />
              <LedgerRow
                label="Conservation areas met"
                value={`${rc_count_above_threshold}`}
              />
            </div>
          )}
        </div>

        <p className="mt-2 text-xs text-muted-foreground">
          Estimate — not an official NRCS determination.
        </p>
      </div>

      {/* Contract limit notice */}
      {contract_limit_applied && (
        <EdgeNote
          tone="warning"
          title={`${contract_years}-year total capped at the ${contract_limit_label}.`}
        />
      )}

      {/* Program limits, printed verbatim from the rules block */}
      <div className="space-y-2">
        <RuleHead label="Program limits" />
        <ul className="space-y-1" aria-label="CSP program limits">
          <li className="font-mono text-xs text-foreground">
            {contract_limit_label}
          </li>
          <li className="font-mono text-xs text-foreground">{eap_label}</li>
          {annual_payment_limit === null && (
            <li className="font-mono text-xs text-foreground">
              No annual payment limit
            </li>
          )}
        </ul>
        <CSPRulesCitation rules={rules} />
      </div>

      {/* Activity table */}
      {!compact && (
        <ActivityTable items={activity_breakdown} rateBasis={activity_rate_basis} />
      )}

      {/* Disclaimer */}
      <p className="border-t border-rule pt-3 text-xs leading-relaxed text-muted-foreground">
        {disclaimer}
      </p>
    </div>
  );
}
