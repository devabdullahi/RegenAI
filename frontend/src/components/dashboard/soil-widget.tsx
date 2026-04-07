import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Sprout } from "lucide-react";
import type { SoilProfile } from "@/lib/api/types";

function getPhNote(ph: number): string {
  if (ph < 5.5) return "Too acidic — lime may help";
  if (ph < 6.0) return "Slightly acidic — works for most crops";
  if (ph <= 7.0) return "Good for most crops";
  if (ph <= 7.5) return "Slightly alkaline — watch micronutrients";
  return "Too alkaline — may limit nutrients";
}

function getOrganicMatterNote(pct: number): string {
  if (pct >= 4) return "Excellent — your soil is thriving";
  if (pct >= 2) return "Room for improvement — cover crops can help";
  return "Low — focus on building organic matter";
}

function OrganicMatterBar({ pct }: { pct: number }) {
  // Cap display at 6% as "full"
  const fillPct = Math.min((pct / 6) * 100, 100);

  let barColor = "bg-red-500";
  if (pct >= 4) barColor = "bg-green-500";
  else if (pct >= 2) barColor = "bg-amber-500";

  let labelColor = "text-red-600";
  if (pct >= 4) labelColor = "text-green-600";
  else if (pct >= 2) labelColor = "text-amber-600";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">Organic matter</span>
        <span className={`text-sm font-semibold ${labelColor}`}>
          {pct}%
        </span>
      </div>
      <div
        className="h-2.5 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={6}
        aria-label={`Organic matter ${pct}%`}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${fillPct}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        {getOrganicMatterNote(pct)}
      </p>
    </div>
  );
}

interface SoilWidgetProps {
  soil: SoilProfile | null | undefined;
}

export function SoilWidget({ soil }: SoilWidgetProps) {
  if (!soil) {
    return <SoilWidgetEmpty />;
  }

  return (
    <Card>
      <CardHeader className="border-b pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold font-heading">
          <Sprout className="h-5 w-5 text-primary" />
          Soil Health
        </CardTitle>
      </CardHeader>

      <CardContent className="pt-4 space-y-4">
        {/* Soil type */}
        <div className="flex items-start justify-between gap-2">
          <span className="text-sm text-muted-foreground">Soil type</span>
          <span className="text-sm font-medium text-right text-foreground">
            {soil.texture}
          </span>
        </div>

        {/* Map unit */}
        {soil.ssurgo_map_unit && (
          <div className="flex items-start justify-between gap-2">
            <span className="text-sm text-muted-foreground">Map unit</span>
            <span className="text-sm font-medium text-right text-foreground max-w-[60%]">
              {soil.ssurgo_map_unit}
            </span>
          </div>
        )}

        <div className="border-t pt-3 space-y-3">
          {/* pH */}
          <div className="space-y-0.5">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Soil pH</span>
              <span className="text-sm font-semibold text-foreground">
                {soil.ph}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              {getPhNote(soil.ph)}
            </p>
          </div>

          {/* Organic matter progress bar */}
          <OrganicMatterBar pct={soil.organic_matter_pct} />
        </div>

        {/* Data source note */}
        <p className="text-xs text-muted-foreground border-t pt-2">
          Data source: {soil.source.toUpperCase()} &middot; Updated{" "}
          {new Date(soil.fetched_at).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </p>
      </CardContent>
    </Card>
  );
}

export function SoilWidgetEmpty() {
  return (
    <Card>
      <CardHeader className="border-b pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold font-heading">
          <Sprout className="h-5 w-5 text-primary" />
          Soil Health
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4 space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-28" />
        </div>
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-8" />
        </div>
        <div className="border-t pt-3 space-y-3">
          <Skeleton className="h-2.5 w-full rounded-full" />
          <Skeleton className="h-3 w-40" />
        </div>
        <p className="text-center text-sm text-muted-foreground pt-1">
          We&apos;re fetching your soil data...
        </p>
      </CardContent>
    </Card>
  );
}
