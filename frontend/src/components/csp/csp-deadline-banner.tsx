import { ExternalLink } from "lucide-react";
import {
  SourceLink,
  daysLeftLabel,
  formatDeadlineDate,
  pickMostUrgentConfirmed,
} from "@/components/shared/deadline-alerts";
import { EdgeNote } from "@/components/shared/record";
import { type Tone } from "@/lib/status-styles";
import { cn } from "@/lib/utils";
import type { CSPDeadline } from "@/lib/api/types";

/**
 * A sign-up cutoff noted in the margin: a bar down the left edge, the days
 * remaining as a figure, the date, and the source it came from. This is the one
 * place implement red-orange is used — a cutoff is the only thing on these
 * sheets that runs out.
 */

function edgeTone(d: CSPDeadline): Tone {
  // A sign-up cutoff is the one place the implement red-orange belongs.
  if (d.alert_severity === "urgent") return "accent";
  if (d.alert_severity === "soon") return "warning";
  return "info";
}

// ── Dated deadline banner ─────────────────────────────────────────────────────

interface CSPDeadlineBannerProps {
  deadline: CSPDeadline;
}

export function CSPDeadlineBanner({ deadline: d }: CSPDeadlineBannerProps) {
  if (!d.cutoff_date || d.days_until === null) {
    return <NotAnnouncedNotice deadline={d} />;
  }
  const urgent = d.alert_severity === "urgent";

  return (
    <div role={urgent ? "alert" : undefined}>
      <EdgeNote tone={edgeTone(d)}>
        <p
          className={cn(
            "font-mono text-xs tracking-[0.08em] uppercase",
            urgent ? "text-accent" : "text-muted-foreground"
          )}
        >
          {daysLeftLabel(d.days_until)} &middot; {d.program}
        </p>
        <p className="mt-1 text-base leading-snug font-semibold text-foreground">
          {d.cutoff_name}
        </p>
        <p className="font-mono text-sm text-foreground">
          Apply by {formatDeadlineDate(d.cutoff_date, "long")}
        </p>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          {d.description}
        </p>
        {d.notes && (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {d.notes}
          </p>
        )}
        <SourceLink
          href={d.source_url}
          asOf={d.as_of}
          className="text-muted-foreground"
        />
      </EdgeNote>
    </div>
  );
}

// ── Not announced notice ──────────────────────────────────────────────────────

function NotAnnouncedNotice({ deadline: d }: CSPDeadlineBannerProps) {
  return (
    <EdgeNote tone="neutral">
      <p className="text-base leading-snug font-semibold text-foreground">
        {d.cutoff_name}
      </p>
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
        Not announced yet. Check your state NRCS office. You can still apply any
        time.
      </p>
      <div className="flex flex-wrap items-center gap-x-3 font-mono text-xs text-muted-foreground">
        <a
          href={d.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-12 items-center gap-1.5 text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          Visit your state NRCS office
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="sr-only">(opens in new tab)</span>
        </a>
        <span>Checked {formatDeadlineDate(d.as_of)}</span>
      </div>
    </EdgeNote>
  );
}

// ── Banner group ──────────────────────────────────────────────────────────────

interface CSPDeadlineBannersProps {
  deadlines: CSPDeadline[];
  /** Show every confirmed deadline instead of only the most urgent one. */
  showAll?: boolean;
}

/**
 * Shows the most urgent confirmed deadline for the farm's state (or all of
 * them with `showAll`), plus a plain notice when the state's NRCS cutoff has
 * not been announced. Renders nothing when there is nothing to show.
 */
export function CSPDeadlineBanners({
  deadlines,
  showAll = false,
}: CSPDeadlineBannersProps) {
  const primary = pickMostUrgentConfirmed(deadlines);
  const confirmed = showAll
    ? deadlines.filter((d) => d.status === "confirmed" && d.cutoff_date)
    : primary
      ? [primary]
      : [];
  const notAnnounced = deadlines.find((d) => d.status === "not_announced");

  if (confirmed.length === 0 && !notAnnounced) return null;

  return (
    <div className="space-y-3" aria-label="Application deadline alerts">
      {confirmed.map((d) => (
        <CSPDeadlineBanner key={d.deadline_id} deadline={d} />
      ))}
      {notAnnounced && <NotAnnouncedNotice deadline={notAnnounced} />}
    </div>
  );
}
