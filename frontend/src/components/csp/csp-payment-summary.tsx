import { DollarSign, Info } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { CSPPaymentEstimate } from "@/lib/api/types";

// ── Payment line row ──────────────────────────────────────────────────────────

function PaymentRow({
  label,
  amount,
  sublabel,
  highlight = false,
}: {
  label: string;
  amount: number;
  sublabel?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between gap-3 py-3 border-b border-border last:border-0 ${highlight ? "rounded-lg bg-primary/5 px-3 -mx-3" : ""}`}
    >
      <div className="min-w-0">
        <p
          className={`text-sm leading-snug ${highlight ? "font-semibold text-foreground" : "text-foreground"}`}
        >
          {label}
        </p>
        {sublabel && (
          <p className="text-xs text-muted-foreground">{sublabel}</p>
        )}
      </div>
      <p
        className={`shrink-0 font-heading font-bold ${highlight ? "text-xl text-primary" : "text-base text-foreground"}`}
      >
        ${amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      </p>
    </div>
  );
}

// ── Enhancement breakdown table ───────────────────────────────────────────────

function EnhancementTable({
  items,
}: {
  items: CSPPaymentEstimate["enhancement_breakdown"];
}) {
  if (items.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Enhancement activity payments
      </p>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table
          className="w-full text-sm"
          aria-label="Enhancement payment breakdown"
        >
          <thead>
            <tr className="border-b border-border bg-muted/40 text-left">
              <th className="px-3 py-2.5 text-xs font-medium text-muted-foreground">
                Activity
              </th>
              <th className="px-3 py-2.5 text-xs font-medium text-muted-foreground text-right whitespace-nowrap">
                Rate / acre
              </th>
              <th className="px-3 py-2.5 text-xs font-medium text-muted-foreground text-right">
                Payment
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((item) => (
              <tr key={item.code} className="bg-card">
                <td className="px-3 py-2.5">
                  <div>
                    <span className="font-mono text-xs font-semibold text-muted-foreground bg-muted px-1.5 py-0.5 rounded mr-1.5">
                      {item.code}
                    </span>
                    <span className="text-foreground">{item.name}</span>
                  </div>
                  {item.is_bundle && (
                    <span className="mt-0.5 inline-block text-xs text-amber-600 font-medium">
                      Bundle rate (115%)
                    </span>
                  )}
                </td>
                <td className="px-3 py-2.5 text-right text-muted-foreground whitespace-nowrap">
                  ${item.base_rate.toFixed(2)}
                  {item.is_bundle && (
                    <span className="ml-1 text-xs text-amber-600">
                      x{item.multiplier}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2.5 text-right font-medium text-foreground whitespace-nowrap">
                  ${item.payment.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface CSPPaymentSummaryProps {
  payment: CSPPaymentEstimate;
  /** Compact mode for dashboard widget — hides table */
  compact?: boolean;
}

export function CSPPaymentSummary({
  payment,
  compact = false,
}: CSPPaymentSummaryProps) {
  const {
    eap_annual,
    enap_annual,
    capped_annual,
    contract_5yr_total,
    per_acre_annual,
    total_cropland_acres,
    rc_count_above_threshold,
    min_applied,
    max_applied,
    enhancement_breakdown,
    disclaimer,
  } = payment;

  return (
    <div className="space-y-5">
      {/* Hero numbers */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-center">
          <p className="text-xs font-medium text-muted-foreground">Per year</p>
          <p className="font-heading text-2xl font-bold text-primary leading-tight">
            ${capped_annual.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </p>
          <p className="text-xs text-muted-foreground">estimated</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 text-center">
          <p className="text-xs font-medium text-muted-foreground">5-year total</p>
          <p className="font-heading text-2xl font-bold text-foreground leading-tight">
            ${contract_5yr_total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </p>
          <p className="text-xs text-muted-foreground">over contract</p>
        </div>
        <div className="col-span-2 sm:col-span-1 rounded-xl border border-border bg-card p-4 text-center">
          <p className="text-xs font-medium text-muted-foreground">Per acre</p>
          <p className="font-heading text-2xl font-bold text-foreground leading-tight">
            ${per_acre_annual.toFixed(2)}
          </p>
          <p className="text-xs text-muted-foreground">per year</p>
        </div>
      </div>

      {/* Cap notice */}
      {(min_applied || max_applied) && (
        <p className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2.5 text-sm text-amber-700">
          {min_applied
            ? "USDA minimum payment floor of $4,000/year applied."
            : "USDA maximum payment cap of $50,000/year applied."}
        </p>
      )}

      {/* Payment breakdown */}
      {!compact && (
        <Card>
          <CardHeader className="border-b pb-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                <DollarSign className="h-4 w-4 text-primary" aria-hidden="true" />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">
                  Payment breakdown
                </p>
                <p className="text-xs text-muted-foreground">
                  {total_cropland_acres.toLocaleString()} acres &middot;{" "}
                  {rc_count_above_threshold} conservation areas met
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-3">
            <div className="divide-y divide-border">
              <PaymentRow
                label="Existing Activity Payment (EAP)"
                sublabel={`$2.65/acre x ${total_cropland_acres} acres x ${rc_count_above_threshold} areas`}
                amount={eap_annual}
              />
              <PaymentRow
                label="Enhancement Activity Payment (EnAP)"
                sublabel="Sum of all selected enhancement activities"
                amount={enap_annual}
              />
              <PaymentRow
                label="Total estimated annual payment"
                amount={capped_annual}
                highlight
              />
              <PaymentRow
                label="Total estimated over 5-year contract"
                sublabel="Annual payment x 5 years"
                amount={contract_5yr_total}
                highlight
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Enhancement table */}
      {!compact && <EnhancementTable items={enhancement_breakdown} />}

      {/* Disclaimer */}
      <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-3 py-3">
        <Info
          className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <p className="text-xs text-muted-foreground leading-relaxed">
          {disclaimer}
        </p>
      </div>
    </div>
  );
}
