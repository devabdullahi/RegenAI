import { LedgerRow, RuleHead, Sheet } from "@/components/shared/record";
import { DEFAULT_YIELD_UNIT, type YieldUnit } from "@/lib/crops";
import { formatNumber, pluralize } from "@/lib/format";
import { toneTextClasses, type Tone } from "@/lib/status-styles";
import type { APHResult } from "@/lib/api/types";

interface YieldSummaryCardProps {
  aph: APHResult;
  fieldName: string;
  /**
   * Unit to print beside the average. Display only — the API returns one
   * number with no unit — so callers pass the unit of the field's crop.
   */
  yieldUnit?: YieldUnit;
}

const TREND: Record<APHResult["trend_direction"], { tone: Tone; sign: string }> = {
  up: { tone: "success", sign: "+" },
  down: { tone: "destructive", sign: "-" },
  flat: { tone: "neutral", sign: "" },
};

/**
 * The field's Actual Production History: the one figure crop insurance is
 * written against, set large with its unit and named in full.
 */
export function YieldSummaryCard({
  aph,
  fieldName,
  yieldUnit = DEFAULT_YIELD_UNIT,
}: YieldSummaryCardProps) {
  const trend = TREND[aph.trend_direction];
  const trendClasses = toneTextClasses[trend.tone];
  const pct = formatNumber(Math.abs(aph.trend_pct));
  const years = `${aph.years_used} ${pluralize(aph.years_used, "year")}`;

  const trendLabel =
    aph.trend_direction === "up"
      ? `Up ${pct}% over ${years}`
      : aph.trend_direction === "down"
        ? `Down ${pct}% over ${years}`
        : `Stable over ${years}`;

  return (
    <Sheet className="p-4 sm:p-5">
      <RuleHead label={`APH — ${fieldName}`} />

      <p className="mt-4 font-mono text-[1.75rem] leading-none font-medium tabular-nums text-foreground">
        {formatNumber(aph.average_yield_bu_ac)}
        <span className="ml-1.5 text-base text-muted-foreground">{yieldUnit}</span>
      </p>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Actual Production History — the average yield per acre your crop
        insurance coverage is written against.
      </p>

      <div className="mt-4 divide-y divide-border border-t border-border">
        <LedgerRow label="Harvest years used" value={`${aph.years_used} yr`} />
        <LedgerRow
          label="Trend"
          value={
            <span className={trendClasses}>
              {aph.trend_direction === "flat" ? "Stable" : `${trend.sign}${pct}%`}
            </span>
          }
          note={trendLabel}
        />
      </div>

      <p className="reading mt-4 max-w-[62ch] text-muted-foreground">
        A higher APH means a higher guarantee per acre, so a bad year pays out
        more. Every harvest you log here goes into the calculation.
      </p>
    </Sheet>
  );
}
