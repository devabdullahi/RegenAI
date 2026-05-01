import type { CSPScore } from "@/lib/api/types";

// ── Score label color mapping ─────────────────────────────────────────────────

function scoreLabelColor(label: CSPScore["score_label"]): string {
  if (label === "Excellent") return "text-green-600";
  if (label === "Good") return "text-primary";
  if (label === "Fair") return "text-amber-600";
  return "text-red-600";
}

function scoreBarColor(score: number): string {
  if (score >= 70) return "bg-green-500";
  if (score >= 50) return "bg-primary";
  if (score >= 30) return "bg-amber-500";
  return "bg-red-500";
}

// ── Sub-bar: individual resource concern ─────────────────────────────────────

interface ScoreBreakdownRowProps {
  label: string;
  pointsEarned: number;
  maxPoints: number;
  currentlyMet: boolean;
}

function ScoreBreakdownRow({
  label,
  pointsEarned,
  maxPoints,
  currentlyMet,
}: ScoreBreakdownRowProps) {
  const pct = maxPoints > 0 ? Math.round((pointsEarned / maxPoints) * 100) : 0;

  return (
    <li className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${currentlyMet ? "bg-green-500" : "bg-muted-foreground/40"}`}
            aria-hidden="true"
          />
          <span className="sr-only">{currentlyMet ? "Met" : "Not met"}</span>
          <span className="text-sm text-foreground truncate">{label}</span>
        </div>
        <span className="shrink-0 text-xs font-medium text-muted-foreground">
          {pointsEarned}/{maxPoints} pts
        </span>
      </div>
      <div
        className="h-1.5 w-full rounded-full bg-muted overflow-hidden"
        role="progressbar"
        aria-valuenow={pointsEarned}
        aria-valuemin={0}
        aria-valuemax={maxPoints}
        aria-label={`${label}: ${pointsEarned} of ${maxPoints} points`}
      >
        <div
          className={`h-full rounded-full transition-all ${currentlyMet ? "bg-green-500" : "bg-muted-foreground/40"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </li>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface CSPScoreGaugeProps {
  score: CSPScore;
  /** Show the per-concern breakdown list */
  showBreakdown?: boolean;
}

export function CSPScoreGauge({
  score,
  showBreakdown = true,
}: CSPScoreGaugeProps) {
  const {
    stewardship_score,
    score_label,
    percentile_estimate,
    score_breakdown,
    bonus_points,
  } = score;

  const pct = Math.min(100, Math.max(0, stewardship_score));

  return (
    <div className="space-y-5">
      {/* Main score display */}
      <div className="flex items-end gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Your stewardship score
          </p>
          <div className="flex items-baseline gap-2">
            <span
              className={`font-heading text-5xl font-bold leading-none ${scoreLabelColor(score_label)}`}
              aria-label={`Stewardship score: ${stewardship_score} out of 100`}
            >
              {stewardship_score}
            </span>
            <span className="text-lg text-muted-foreground font-medium">/100</span>
          </div>
        </div>
        <div className="mb-1 space-y-0.5">
          <span
            className={`inline-flex rounded-full px-2.5 py-0.5 text-sm font-semibold ${
              score_label === "Excellent"
                ? "bg-green-100 text-green-700"
                : score_label === "Good"
                  ? "bg-primary/10 text-primary"
                  : score_label === "Fair"
                    ? "bg-amber-100 text-amber-700"
                    : "bg-red-100 text-red-700"
            }`}
          >
            {score_label}
          </span>
          <p className="text-base font-semibold text-foreground capitalize">
            {percentile_estimate} for Iowa
          </p>
        </div>
      </div>

      {/* Main progress bar with threshold marker */}
      <div className="space-y-1.5">
        <div className="relative">
          <div
            className="h-4 w-full rounded-full bg-muted overflow-hidden"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Overall stewardship score: ${pct} out of 100`}
          >
            <div
              className={`h-full rounded-full transition-all ${scoreBarColor(pct)}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          {/* ACT NOW threshold marker — overlaid at the 60% position */}
          <div
            className="absolute top-0 h-4 w-0.5 bg-amber-500"
            style={{ left: "60%" }}
            aria-hidden="true"
          />
        </div>
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>0</span>
          <span className="text-sm font-bold text-amber-700">
            Iowa ACT NOW threshold: 60
          </span>
          <span>100</span>
        </div>
      </div>

      {/* Bonus points note */}
      {bonus_points > 0 && (
        <p className="text-xs text-muted-foreground rounded-lg bg-primary/5 border border-primary/20 px-3 py-2">
          Includes {bonus_points} bonus points for Mississippi River Basin
          watershed location.
        </p>
      )}

      {/* Per-concern breakdown */}
      {showBreakdown && score_breakdown.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Points by conservation area
          </p>
          <ul className="space-y-3" aria-label="Score breakdown by resource concern">
            {score_breakdown.map((item) => (
              <ScoreBreakdownRow
                key={item.code}
                label={item.resource_concern}
                pointsEarned={item.points_earned}
                maxPoints={item.max_points}
                currentlyMet={item.currently_met}
              />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
