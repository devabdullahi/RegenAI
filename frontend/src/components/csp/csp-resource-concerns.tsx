import {
  CheckCircle2,
  XCircle,
  Wind,
  Droplets,
  Leaf,
  Zap,
  Sun,
  Tractor,
  Fish,
  Waves,
} from "lucide-react";
import type { CSPResourceConcernResult } from "@/lib/api/types";

// ── Icon map per resource concern code ───────────────────────────────────────

const RC_ICONS: Record<string, React.ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" | "false" }>> = {
  SOIL_EROSION: Tractor,
  SOIL_HEALTH: Leaf,
  WATER_QUALITY: Droplets,
  WATER_QUANTITY: Waves,
  AIR_QUALITY: Wind,
  PLANT_CONDITION: Sun,
  ANIMALS: Fish,
  ENERGY: Zap,
};

// ── Score bar ─────────────────────────────────────────────────────────────────

function ScoreBar({
  score,
  met,
}: {
  score: number;
  met: boolean;
}) {
  return (
    <div
      className="h-1.5 w-full rounded-full bg-muted overflow-hidden"
      role="progressbar"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={`h-full rounded-full transition-all ${met ? "bg-green-500" : "bg-muted-foreground/40"}`}
        style={{ width: `${score}%` }}
      />
    </div>
  );
}

// ── Single resource concern card ──────────────────────────────────────────────

function ResourceConcernCard({ rc }: { rc: CSPResourceConcernResult }) {
  const Icon = RC_ICONS[rc.code] ?? Leaf;
  const met = rc.currently_met;

  return (
    <div
      className={`rounded-xl border p-4 space-y-3 ${met ? "border-green-200 bg-green-50" : "border-border bg-card"}`}
      aria-label={`${rc.name}: ${met ? "threshold met" : "not yet met"}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${met ? "bg-green-100" : "bg-muted"}`}
          >
            <Icon
              className={`h-4 w-4 ${met ? "text-green-600" : "text-muted-foreground"}`}
              aria-hidden="true"
            />
          </div>
          <p className="text-sm font-semibold text-foreground leading-snug">
            {rc.name}
          </p>
        </div>
        {met ? (
          <CheckCircle2
            className="h-5 w-5 shrink-0 text-green-500"
            aria-hidden="true"
          />
        ) : (
          <XCircle
            className="h-5 w-5 shrink-0 text-muted-foreground/60"
            aria-hidden="true"
          />
        )}
      </div>

      {/* Score bar */}
      <ScoreBar score={rc.score} met={met} />

      {/* Points */}
      <div className="flex items-center justify-between text-xs">
        <span
          className={`font-semibold ${met ? "text-green-700" : "text-muted-foreground"}`}
        >
          {met ? "Threshold met" : "Not yet met"}
        </span>
        <span className="text-muted-foreground">
          {rc.points_earned} pts earned
        </span>
      </div>

      {/* Evidence (collapsed list — show top 2) */}
      {rc.evidence.length > 0 && (
        <ul
          className="space-y-0.5"
          aria-label={`Evidence for ${rc.name}`}
        >
          {rc.evidence.slice(0, 2).map((e, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
              <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-muted-foreground/40" aria-hidden="true" />
              {e}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Main grid component ───────────────────────────────────────────────────────

interface CSPResourceConcernsProps {
  resourceConcerns: CSPResourceConcernResult[];
}

export function CSPResourceConcerns({
  resourceConcerns,
}: CSPResourceConcernsProps) {
  const metCount = resourceConcerns.filter((rc) => rc.currently_met).length;
  const total = resourceConcerns.length;

  return (
    <section aria-labelledby="resource-concerns-heading" className="space-y-4">
      <div>
        <h2
          id="resource-concerns-heading"
          className="font-heading text-lg font-semibold text-foreground"
        >
          Conservation areas
        </h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          {metCount} of {total} areas currently above the stewardship threshold
        </p>
      </div>

      {/* Summary bar */}
      <div
        className="h-2.5 w-full rounded-full bg-muted overflow-hidden"
        role="progressbar"
        aria-valuenow={metCount}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-label={`${metCount} of ${total} resource concerns met`}
      >
        <div
          className="h-full rounded-full bg-green-500 transition-all"
          style={{ width: `${Math.round((metCount / total) * 100)}%` }}
        />
      </div>

      {/* Grid */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-2">
        {resourceConcerns.map((rc) => (
          <ResourceConcernCard key={rc.code} rc={rc} />
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5 text-green-500" aria-hidden="true" />
          Threshold met — earns points toward your score
        </span>
        <span className="flex items-center gap-1.5">
          <XCircle className="h-3.5 w-3.5 text-muted-foreground/60" aria-hidden="true" />
          Not yet met — see recommendations to improve
        </span>
      </div>
    </section>
  );
}
