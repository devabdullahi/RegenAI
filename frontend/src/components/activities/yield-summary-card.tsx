import { TrendingUp, TrendingDown, Minus, Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { APHResult } from "@/lib/api/types";

interface YieldSummaryCardProps {
  aph: APHResult;
  fieldName: string;
}

export function YieldSummaryCard({ aph, fieldName }: YieldSummaryCardProps) {
  const TrendIcon =
    aph.trend_direction === "up"
      ? TrendingUp
      : aph.trend_direction === "down"
        ? TrendingDown
        : Minus;

  const trendColor =
    aph.trend_direction === "up"
      ? "text-green-600"
      : aph.trend_direction === "down"
        ? "text-red-600"
        : "text-muted-foreground";

  const trendLabel =
    aph.trend_direction === "up"
      ? `Up ${aph.trend_pct}% over ${aph.years_used} years`
      : aph.trend_direction === "down"
        ? `Down ${Math.abs(aph.trend_pct)}% over ${aph.years_used} years`
        : "Stable over last 5 years";

  return (
    <Card>
      <CardHeader className="border-b">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold">
            APH Summary — {fieldName}
          </CardTitle>
          <TrendIcon
            className={cn("h-5 w-5", trendColor)}
            aria-label={trendLabel}
          />
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">
          Actual Production History for crop insurance
        </p>
      </CardHeader>

      <CardContent className="pt-4">
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <p className="text-3xl font-bold text-foreground">
              {aph.average_yield_bu_ac}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">avg bu/acre</p>
          </div>
          <div className="text-center border-x border-border">
            <p className="text-3xl font-bold text-foreground">{aph.years_used}</p>
            <p className="text-xs text-muted-foreground mt-0.5">years used</p>
          </div>
          <div className="text-center">
            <p className={cn("text-3xl font-bold", trendColor)}>
              {aph.trend_direction === "up"
                ? `+${aph.trend_pct}%`
                : aph.trend_direction === "down"
                  ? `-${Math.abs(aph.trend_pct)}%`
                  : "—"}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">trend</p>
          </div>
        </div>

        <div className="mt-4 flex items-start gap-2 rounded-lg bg-muted/40 px-3 py-3">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <p className="text-xs text-muted-foreground leading-relaxed">
            Your APH is the average yield per acre calculated from your actual harvest
            records. Your crop insurance coverage is based on this number — a higher
            APH means more coverage per acre if you have a bad year.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
