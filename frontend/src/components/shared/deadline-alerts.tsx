import { ExternalLink } from "lucide-react";
import { RuleHead, Stamp } from "@/components/shared/record";
import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/format";
import type { Tone } from "@/lib/status-styles";
import type { CSPDeadline, CSPDeadlineSeverity } from "@/lib/api/types";

// ── Shared helpers (also used by csp-deadline-banner) ─────────────────────────

/** Format an ISO date (YYYY-MM-DD); falls back to the raw string if unparseable. */
export function formatDeadlineDate(
  isoDate: string,
  style: "long" | "short" = "short"
): string {
  return formatDate(isoDate, {
    weekday: style === "long" ? "long" : undefined,
    month: style === "long" ? "long" : "short",
    day: "numeric",
    year: "numeric",
    fallback: isoDate,
  });
}

export function daysLeftLabel(days: number): string {
  if (days <= 0) return "Due today";
  if (days === 1) return "1 day left";
  return `${days} days left`;
}

/** Most urgent deadline with a published date (list order is soonest first). */
export function pickMostUrgentConfirmed(
  deadlines: CSPDeadline[]
): CSPDeadline | undefined {
  return deadlines
    .filter((d) => d.status === "confirmed" && d.cutoff_date && d.days_until !== null)
    .sort((a, b) => (a.days_until ?? 0) - (b.days_until ?? 0))[0];
}

export function SourceLink({
  href,
  asOf,
  className,
}: {
  href: string;
  asOf: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-x-3 text-xs", className)}>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex min-h-[48px] items-center gap-1.5 text-sm font-medium underline underline-offset-4"
      >
        Source
        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="sr-only">(opens in new tab)</span>
      </a>
      <span>
        Checked <span className="font-mono">{formatDeadlineDate(asOf)}</span>
      </span>
    </div>
  );
}

/** How many days are left, stamped — the word is always there with the color. */
function stampFor(d: CSPDeadline): { label: string; tone: Tone } {
  const severity: CSPDeadlineSeverity = d.alert_severity;
  if (d.days_until !== null) {
    if (severity === "urgent") {
      return { label: daysLeftLabel(d.days_until), tone: "destructive" };
    }
    if (severity === "soon") {
      return { label: daysLeftLabel(d.days_until), tone: "warning" };
    }
    if (severity === "later") {
      return { label: daysLeftLabel(d.days_until), tone: "neutral" };
    }
  }
  return {
    label: d.status === "expected" ? "Dates expected" : "Not announced",
    tone: "neutral",
  };
}

function whenLine(d: CSPDeadline): string {
  if (d.cutoff_date) return `Apply by ${formatDeadlineDate(d.cutoff_date)}`;
  if (d.status === "not_announced") {
    return "Not announced yet. Check your state NRCS office.";
  }
  return "Not announced yet. Usually opens around the same time each year.";
}

// ── Dashboard widget ──────────────────────────────────────────────────────────

interface UpcomingDeadlinesProps {
  deadlines: CSPDeadline[];
  limit?: number;
  className?: string;
}

/** Compact list of the next few deadlines. Renders nothing when empty. */
export function UpcomingDeadlines({
  deadlines,
  limit = 3,
  className,
}: UpcomingDeadlinesProps) {
  const items = deadlines.slice(0, limit);
  if (items.length === 0) return null;

  return (
    <section className={className}>
      <RuleHead label="Upcoming deadlines" />
      <ul className="divide-y divide-border" aria-label="Upcoming program deadlines">
        {items.map((d) => {
          const stamp = stampFor(d);
          return (
            <li key={d.deadline_id} className="py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm leading-snug font-semibold text-foreground">
                    {d.cutoff_name}
                  </p>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {whenLine(d)}
                  </p>
                </div>
                <Stamp tone={stamp.tone} className="shrink-0">
                  {stamp.label}
                </Stamp>
              </div>
              <SourceLink
                href={d.source_url}
                asOf={d.as_of}
                className="text-muted-foreground"
              />
            </li>
          );
        })}
      </ul>
    </section>
  );
}
