import { RuleHead, Stamp } from "@/components/shared/record";
import { getCspStatusConfig } from "@/lib/csp-status";
import { cn } from "@/lib/utils";
import type { CSPScore } from "@/lib/api/types";

// ── Printed scale ─────────────────────────────────────────────────────────────

/** Ticks every 10 points, the way a ruled scale is engraved. */
const TICKS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

function clampPct(value: number): number {
  return Math.min(100, Math.max(0, value));
}

/**
 * Keep a mark's label inside the measure: it is centred in the middle of the
 * scale, but pinned at either end so a score of 0 or 100 is not clipped.
 */
function labelPlacement(pct: number): { left: string; translate: string } {
  if (pct <= 8) return { left: "0%", translate: "translateX(0)" };
  if (pct >= 92) return { left: "100%", translate: "translateX(-100%)" };
  return { left: `${pct}%`, translate: "translateX(-50%)" };
}

interface ScoreScaleProps {
  score: number;
  threshold: number | null;
}

/**
 * The score as a mark on a ruled scale: ink bar for the farm's own reading,
 * a labelled rule for the estimated state ranking threshold. No arc, no glow.
 */
function ScoreScale({ score, threshold }: ScoreScaleProps) {
  const pct = clampPct(score);
  const thresholdPct = threshold === null ? null : clampPct(threshold);
  const scoreLabel = labelPlacement(pct);
  const thresholdLabel =
    thresholdPct === null ? null : labelPlacement(thresholdPct);

  return (
    <div className="pt-1">
      <div className="relative h-16" aria-hidden="true">
        {/* Score figure, printed above its mark */}
        <span
          className="absolute top-0 font-mono text-xs font-medium whitespace-nowrap text-foreground"
          style={{ left: scoreLabel.left, transform: scoreLabel.translate }}
        >
          {score} pts
        </span>

        {/* Baseline rule with its ticks */}
        <span className="absolute inset-x-0 top-8 h-px bg-rule" />
        {TICKS.map((tick) => (
          <span
            key={tick}
            className="absolute top-8 h-1.5 w-px bg-rule"
            style={{ left: `${tick}%` }}
          />
        ))}

        {/* The farm's own reading, measured from zero */}
        <span
          className="absolute top-[1.9375rem] left-0 h-[3px] bg-primary"
          style={{ width: `${pct}%` }}
        />
        <span
          className="absolute top-5 h-5 w-[2px] bg-primary"
          style={{ left: `${pct}%`, transform: "translateX(-50%)" }}
        />

        {/* Estimated state ranking threshold */}
        {thresholdPct !== null && thresholdLabel !== null && (
          <>
            <span
              className="absolute top-6 h-4 w-px bg-rule-strong"
              style={{ left: `${thresholdPct}%`, transform: "translateX(-50%)" }}
            />
            <span
              className="absolute top-11 font-mono text-[0.6875rem] whitespace-nowrap text-muted-foreground"
              style={{
                left: thresholdLabel.left,
                transform: thresholdLabel.translate,
              }}
            >
              Est. threshold {threshold} pts
            </span>
          </>
        )}
      </div>

      <div className="flex items-center justify-between font-mono text-[0.6875rem] text-muted-foreground">
        <span>0 pts</span>
        <span>100 pts</span>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface CSPScoreGaugeProps {
  score: CSPScore;
  /** Show the per-concern breakdown table */
  showBreakdown?: boolean;
}

export function CSPScoreGauge({
  score,
  showBreakdown = true,
}: CSPScoreGaugeProps) {
  const {
    stewardship_score,
    eligibility_status,
    score_breakdown,
    ranking_threshold,
  } = score;

  const status = getCspStatusConfig(eligibility_status);
  // The threshold is a per-state estimate from the API. When the state has
  // published none, say so plainly: no number, and no gap calculated from one.
  const threshold =
    typeof ranking_threshold === "number" && Number.isFinite(ranking_threshold)
      ? ranking_threshold
      : null;
  const clearsThreshold =
    threshold === null ? null : stewardship_score >= threshold;
  const gap = threshold === null ? null : Math.abs(stewardship_score - threshold);

  let verdict: string;
  if (threshold === null) {
    verdict =
      "Your state has not published a ranking threshold, so there is no score to compare yours against. NRCS ranks applications in your state.";
  } else if (clearsThreshold) {
    verdict = `Clears the estimated state ranking threshold of ${threshold} pts by ${gap} pts.`;
  } else {
    verdict = `${gap} pts below the estimated state ranking threshold of ${threshold} pts.`;
  }

  return (
    <div className="space-y-4">
      {/* The reading */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-2">
        <span className="font-mono text-[1.75rem] leading-none font-medium text-foreground">
          {stewardship_score}
        </span>
        <span className="font-mono text-sm text-muted-foreground">
          pts of 100 pts
        </span>
        <Stamp tone={status.tone} className="ml-auto">
          {status.shortLabel}
        </Stamp>
      </div>

      <ScoreScale score={stewardship_score} threshold={threshold} />

      <p className="text-sm text-foreground">{verdict}</p>

      {/* Per-concern breakdown */}
      {showBreakdown && score_breakdown.length > 0 && (
        <div className="space-y-2 pt-2">
          <RuleHead label="Points by conservation area" />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[20rem] text-sm">
              <caption className="sr-only">
                Points earned by conservation area
              </caption>
              <thead>
                <tr className="border-b border-rule">
                  <th
                    scope="col"
                    className="py-1.5 text-left font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase"
                  >
                    Area
                  </th>
                  <th
                    scope="col"
                    className="py-1.5 text-right font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase"
                  >
                    Points
                  </th>
                  <th
                    scope="col"
                    className="py-1.5 pl-3 text-right font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase"
                  >
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {score_breakdown.map((item) => (
                  <tr key={item.code} className="border-b border-rule last:border-0">
                    <th
                      scope="row"
                      className="py-2 pr-3 text-left text-sm font-normal text-foreground"
                    >
                      {item.resource_concern}
                    </th>
                    <td className="py-2 text-right font-mono text-sm whitespace-nowrap text-foreground">
                      {item.points_earned} / {item.max_points} pts
                    </td>
                    <td
                      className={cn(
                        "py-2 pl-3 text-right font-mono text-[0.6875rem] tracking-[0.08em] uppercase",
                        item.currently_met ? "text-success" : "text-muted-foreground"
                      )}
                    >
                      {item.currently_met ? "Met" : "Not met"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
