/**
 * Semantic tone -> Tailwind classes, built only from tokens in app/globals.css
 * so light and dark mode stay consistent. Use these instead of raw palette
 * classes (bg-green-100, text-red-700, ...).
 *
 * Variants:
 *   toneClasses        soft badge/pill: tinted background + readable text
 *   toneSurfaceClasses callout/card/banner: tinted background + border
 *   toneTextClasses    text only (inline status words, figures)
 *   toneIconClasses    icon color (non-text, 3:1 contrast is enough)
 *
 * Combine with cn(): cn("rounded-full px-2.5 py-0.5 text-xs", toneClasses.success)
 */

export type Tone = "success" | "warning" | "destructive" | "info" | "accent" | "neutral";

// Warning uses warning-foreground for text: the amber token itself is too light
// to meet 4.5:1 as text on a light background.
export const toneClasses: Record<Tone, string> = {
  accent: "bg-accent/10 text-accent",
  success: "bg-success/10 text-success",
  warning: "bg-warning/20 text-warning-foreground",
  destructive: "bg-destructive/10 text-destructive",
  info: "bg-info/10 text-info",
  neutral: "bg-muted text-muted-foreground",
};

export const toneSurfaceClasses: Record<Tone, string> = {
  accent: "border-accent/40 bg-accent/5",
  success: "border-success/30 bg-success/5",
  warning: "border-warning/50 bg-warning/10",
  destructive: "border-destructive/30 bg-destructive/5",
  info: "border-info/30 bg-info/5",
  neutral: "border-border bg-muted/30",
};

export const toneTextClasses: Record<Tone, string> = {
  accent: "text-accent",
  success: "text-success",
  warning: "text-warning-foreground",
  destructive: "text-destructive",
  info: "text-info",
  neutral: "text-muted-foreground",
};

export const toneIconClasses: Record<Tone, string> = {
  accent: "text-accent",
  success: "text-success",
  warning: "text-warning",
  destructive: "text-destructive",
  info: "text-info",
  neutral: "text-muted-foreground",
};

// ── Severity (scouting, alerts) ──────────────────────────────────────────────

export type Severity = "none" | "low" | "moderate" | "high" | "critical";

export const severityTone: Record<Severity, Tone> = {
  none: "neutral",
  low: "success",
  moderate: "warning",
  high: "destructive",
  critical: "destructive",
};

export const severityLabel: Record<Severity, string> = {
  none: "None",
  low: "Low",
  moderate: "Moderate",
  high: "High",
  critical: "Critical",
};

/** Text classes for a severity word; critical is also bold. */
export const severityTextClasses: Record<Severity, string> = {
  none: toneTextClasses.neutral,
  low: toneTextClasses.success,
  moderate: toneTextClasses.warning,
  high: toneTextClasses.destructive,
  critical: `${toneTextClasses.destructive} font-bold`,
};

/**
 * Left edge bar for EdgeNote: status rides the margin of the sheet instead of
 * tinting a floating box.
 */
export const toneEdgeClasses: Record<Tone, string> = {
  accent: "border-l-accent",
  success: "border-l-success",
  warning: "border-l-warning",
  destructive: "border-l-destructive",
  info: "border-l-info",
  neutral: "border-l-border",
};
