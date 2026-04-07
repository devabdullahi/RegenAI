import { AlertTriangle, Clock, CalendarDays } from "lucide-react";
import type { CSPDeadline, CSPDeadlineSeverity } from "@/lib/api/types";

// ── Severity styling ──────────────────────────────────────────────────────────

function severityStyles(severity: CSPDeadlineSeverity): {
  wrapper: string;
  icon: string;
  heading: string;
} {
  if (severity === "urgent") {
    return {
      wrapper: "border-red-300 bg-red-50",
      icon: "text-red-600",
      heading: "text-red-800",
    };
  }
  if (severity === "warning") {
    return {
      wrapper: "border-amber-300 bg-amber-50",
      icon: "text-amber-600",
      heading: "text-amber-800",
    };
  }
  // upcoming
  return {
    wrapper: "border-primary/30 bg-primary/5",
    icon: "text-primary",
    heading: "text-primary",
  };
}

function SeverityIcon({
  severity,
  className,
}: {
  severity: CSPDeadlineSeverity;
  className?: string;
}) {
  if (severity === "urgent") {
    return <AlertTriangle className={className} aria-hidden="true" />;
  }
  if (severity === "warning") {
    return <Clock className={className} aria-hidden="true" />;
  }
  return <CalendarDays className={className} aria-hidden="true" />;
}

function formatDate(isoDate: string): string {
  const d = new Date(isoDate);
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

// ── Single banner ─────────────────────────────────────────────────────────────

interface CSPDeadlineBannerProps {
  deadline: CSPDeadline;
}

export function CSPDeadlineBanner({ deadline }: CSPDeadlineBannerProps) {
  const styles = severityStyles(deadline.alert_severity);

  return (
    <div
      role="alert"
      className={`flex items-start gap-3 rounded-xl border px-4 py-3.5 ${styles.wrapper}`}
    >
      <SeverityIcon
        severity={deadline.alert_severity}
        className={`mt-0.5 h-5 w-5 shrink-0 ${styles.icon}`}
      />
      <div className="min-w-0 space-y-0.5">
        <p className={`text-sm font-semibold leading-snug ${styles.heading}`}>
          {deadline.alert_severity === "urgent"
            ? "Deadline in " + deadline.days_until + " days"
            : deadline.alert_severity === "warning"
              ? `${deadline.days_until} days until cutoff`
              : `Upcoming: ${deadline.days_until} days away`}
          {deadline.is_act_now && (
            <span className="ml-2 rounded-full bg-primary px-2 py-0.5 text-xs font-semibold text-primary-foreground">
              ACT NOW window
            </span>
          )}
        </p>
        <p className="text-sm text-foreground font-medium">{deadline.cutoff_name}</p>
        <p className="text-xs text-muted-foreground">
          {formatDate(deadline.cutoff_date)}
        </p>
        {deadline.description && (
          <p className="text-xs text-muted-foreground leading-relaxed mt-1">
            {deadline.description}
          </p>
        )}
        {deadline.is_act_now &&
          deadline.act_now_start &&
          deadline.act_now_end && (
            <p className="text-xs text-muted-foreground">
              ACT NOW window:{" "}
              {new Date(deadline.act_now_start).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
              })}{" "}
              &ndash;{" "}
              {new Date(deadline.act_now_end).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </p>
          )}
      </div>
    </div>
  );
}

// ── List of banners (filters to urgent/warning only by default) ───────────────

interface CSPDeadlineBannersProps {
  deadlines: CSPDeadline[];
  /** Show upcoming deadlines too (not just urgent/warning) */
  showAll?: boolean;
}

export function CSPDeadlineBanners({
  deadlines,
  showAll = false,
}: CSPDeadlineBannersProps) {
  const filtered = showAll
    ? deadlines.filter((d) => d.alert_severity !== "passed")
    : deadlines.filter(
        (d) =>
          d.alert_severity === "urgent" || d.alert_severity === "warning",
      );

  if (filtered.length === 0) return null;

  return (
    <div className="space-y-3" aria-label="Application deadline alerts">
      {filtered.map((d) => (
        <CSPDeadlineBanner key={d.deadline_id} deadline={d} />
      ))}
    </div>
  );
}
