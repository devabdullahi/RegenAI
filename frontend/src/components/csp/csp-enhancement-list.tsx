import { CheckCircle2, Circle, Zap, Package } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { CSPEnhancement } from "@/lib/api/types";

// ── Difficulty label ──────────────────────────────────────────────────────────

function difficultyFromPoints(points: number): {
  label: string;
  color: string;
} {
  if (points >= 13)
    return { label: "High impact", color: "text-green-700 bg-green-100" };
  if (points >= 8)
    return { label: "Medium impact", color: "text-amber-700 bg-amber-100" };
  return { label: "Lower impact", color: "text-muted-foreground bg-muted" };
}

// ── Status chip ───────────────────────────────────────────────────────────────

function StatusChip({
  status,
}: {
  status: CSPEnhancement["status"];
}) {
  if (status === "active") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
        Active
      </span>
    );
  }
  if (status === "committed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
        Committed
      </span>
    );
  }
  if (status === "considering") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">
        <Circle className="h-3 w-3" aria-hidden="true" />
        Considering
      </span>
    );
  }
  return null;
}

// ── Single enhancement item ───────────────────────────────────────────────────

function EnhancementItem({ enhancement }: { enhancement: CSPEnhancement }) {
  const difficulty = difficultyFromPoints(enhancement.point_weight);
  const isSelected =
    enhancement.status === "active" || enhancement.status === "committed";

  return (
    <li
      className={`rounded-xl border p-4 space-y-3 ${isSelected ? "border-primary/30 bg-primary/5" : "border-border bg-card"}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div
            className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${isSelected ? "bg-primary/10" : "bg-muted"}`}
          >
            {enhancement.is_bundle_eligible ? (
              <Package
                className={`h-4 w-4 ${isSelected ? "text-primary" : "text-muted-foreground"}`}
                aria-hidden="true"
              />
            ) : (
              <Zap
                className={`h-4 w-4 ${isSelected ? "text-primary" : "text-muted-foreground"}`}
                aria-hidden="true"
              />
            )}
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5 mb-0.5">
              <span className="font-mono text-xs font-semibold text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                {enhancement.code}
              </span>
              {enhancement.status && <StatusChip status={enhancement.status} />}
            </div>
            <p className="text-sm font-semibold text-foreground leading-snug">
              {enhancement.name}
            </p>
            <p className="text-xs text-muted-foreground">{enhancement.category}</p>
          </div>
        </div>
        {/* Point weight */}
        <div className="shrink-0 text-right">
          <span
            className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${difficulty.color}`}
          >
            +{enhancement.point_weight} pts
          </span>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-muted-foreground leading-relaxed">
        {enhancement.description}
      </p>

      {/* Implementation note */}
      {enhancement.implementation_notes && (
        <p className="rounded-md bg-muted/60 px-3 py-2 text-xs text-muted-foreground leading-relaxed">
          <span className="font-medium text-foreground">How it works: </span>
          {enhancement.implementation_notes}
        </p>
      )}

      {/* Payment info */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>
            ${enhancement.base_payment_rate}/{enhancement.payment_unit}
          </span>
          {enhancement.is_bundle_eligible && (
            <span className="text-amber-600 font-medium">
              Bundle eligible (115% rate)
            </span>
          )}
          {enhancement.eqip_practice_code && (
            <span className="font-mono bg-muted px-1.5 py-0.5 rounded text-foreground">
              EQIP {enhancement.eqip_practice_code}
            </span>
          )}
        </div>
        {enhancement.estimated_payment !== undefined &&
          enhancement.estimated_payment !== null && (
            <span className="text-sm font-semibold text-primary">
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
  title = "Recommended enhancements",
  showEmpty = true,
}: CSPEnhancementListProps) {
  if (enhancements.length === 0 && !showEmpty) return null;

  return (
    <section aria-labelledby="enhancements-heading" className="space-y-4">
      <div>
        <h2
          id="enhancements-heading"
          className="font-heading text-lg font-semibold text-foreground"
        >
          {title}
        </h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Conservation activities that increase your score and add to your
          annual payment
        </p>
      </div>

      {enhancements.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-sm text-muted-foreground">
              No enhancements available. Complete your eligibility evaluation
              first.
            </p>
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-3" aria-label="Enhancement activities">
          {enhancements.map((enh) => (
            <EnhancementItem key={enh.id} enhancement={enh} />
          ))}
        </ul>
      )}
    </section>
  );
}
