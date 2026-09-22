import { LedgerRow, RuleHead, Sheet } from "@/components/shared/record";
import { formatDate, formatNumber } from "@/lib/format";
import { toneTextClasses, type Tone } from "@/lib/status-styles";
import { cn } from "@/lib/utils";
import type { SoilProfile } from "@/lib/api/types";

// Organic matter at or above this percentage fills the bar.
const ORGANIC_MATTER_FULL_PCT = 6;

const BAR_FILL_CLASSES: Record<Tone, string> = {
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
  info: "bg-info",
  neutral: "bg-muted-foreground",
};

function getPhNote(ph: number): string {
  if (ph < 5.5) return "Too acidic — lime may help";
  if (ph < 6.0) return "Slightly acidic — works for most crops";
  if (ph <= 7.0) return "Good for most crops";
  if (ph <= 7.5) return "Slightly alkaline — watch micronutrients";
  return "Too alkaline — may limit nutrients";
}

function organicMatterTone(pct: number): Tone {
  if (pct >= 4) return "success";
  if (pct >= 2) return "warning";
  return "destructive";
}

function getOrganicMatterNote(pct: number): string {
  if (pct >= 4) return "Excellent — your soil is thriving";
  if (pct >= 2) return "Room for improvement — cover crops can help";
  return "Low — focus on building organic matter";
}

/** Organic matter as a ledger line, with a flat gauge under it. */
function OrganicMatter({ pct }: { pct: number | null }) {
  if (pct === null) {
    return <LedgerRow label="Organic matter" value="—" />;
  }

  const tone = organicMatterTone(pct);
  const fillPct = Math.min((pct / ORGANIC_MATTER_FULL_PCT) * 100, 100);
  const pctLabel = `${formatNumber(pct)}%`;

  return (
    <div>
      <LedgerRow
        label="Organic matter"
        note={getOrganicMatterNote(pct)}
        value={<span className={toneTextClasses[tone]}>{pctLabel}</span>}
      />
      <div
        className="h-1.5 w-full bg-muted"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={ORGANIC_MATTER_FULL_PCT}
        aria-label={`Organic matter ${pctLabel}`}
      >
        <div
          className={cn("h-full transition-all", BAR_FILL_CLASSES[tone])}
          style={{ width: `${fillPct}%` }}
        />
      </div>
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
    <Sheet className="p-4">
      <RuleHead label="Soil" />

      <div className="mt-2 divide-y divide-border">
        <LedgerRow label="Soil type" value={soil.texture || "—"} />
        {soil.ssurgo_map_unit && (
          <LedgerRow label="Map unit" value={soil.ssurgo_map_unit} />
        )}
        <LedgerRow
          label="Soil pH"
          note={soil.ph !== null ? getPhNote(soil.ph) : undefined}
          value={formatNumber(soil.ph)}
        />
      </div>

      <div className="mt-2 border-t border-border pt-1">
        <OrganicMatter pct={soil.organic_matter_pct} />
      </div>

      <p className="mt-4 border-t border-border pt-2 text-xs text-muted-foreground">
        Source {soil.source.toUpperCase()} &middot; updated{" "}
        <span className="font-mono">{formatDate(soil.fetched_at)}</span>
      </p>
    </Sheet>
  );
}

export function SoilWidgetEmpty() {
  return (
    <Sheet className="p-4">
      <RuleHead label="Soil" />
      <p className="mt-3 text-sm text-muted-foreground">
        No soil data for this field yet. It is added when the field&apos;s
        location is looked up.
      </p>
    </Sheet>
  );
}
